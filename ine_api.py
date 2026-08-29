import urllib.request
import json
import time
from datetime import datetime
import db

INE_IPV_SERIES = {
    "NACIONAL": {"code": "IPV769", "name": "España (Nacional)"},
    "ANDALUCIA": {"code": "IPV766", "name": "Andalucía"},
    "ARAGON": {"code": "IPV763", "name": "Aragón"},
    "ASTURIAS": {"code": "IPV760", "name": "Asturias, Principado de"},
    "BALEARES": {"code": "IPV757", "name": "Balears, Illes"},
    "CANARIAS": {"code": "IPV754", "name": "Canarias"},
    "CANTABRIA": {"code": "IPV751", "name": "Cantabria"},
    "CASTILLA_LEON": {"code": "IPV748", "name": "Castilla y León"},
    "CASTILLA_MANCHA": {"code": "IPV745", "name": "Castilla - La Mancha"},
    "CATALUNA": {"code": "IPV742", "name": "Cataluña"},
    "VALENCIA": {"code": "IPV739", "name": "Comunitat Valenciana"},
    "EXTREMADURA": {"code": "IPV736", "name": "Extremadura"},
    "GALICIA": {"code": "IPV733", "name": "Galicia"},
    "MADRID": {"code": "IPV730", "name": "Madrid, Comunidad de"},
    "MURCIA": {"code": "IPV727", "name": "Murcia, Región de"},
    "NAVARRA": {"code": "IPV724", "name": "Navarra, Comunidad Foral de"},
    "PAIS_VASCO": {"code": "IPV721", "name": "País Vasco"},
    "LA_RIOJA": {"code": "IPV718", "name": "Rioja, La"},
    "CEUTA": {"code": "IPV715", "name": "Ceuta"},
    "MELILLA": {"code": "IPV710", "name": "Melilla"}
}

# Mapeo de FK_Periodo del INE a número de trimestre (1..4)
PERIODO_TRIMESTRE = {
    19: 1,
    20: 2,
    21: 3,
    22: 4
}

def get_community_info(key):
    if not key:
        return INE_IPV_SERIES["NACIONAL"]
    norm_key = key.upper().strip()
    return INE_IPV_SERIES.get(norm_key, INE_IPV_SERIES["NACIONAL"])

def sync_ine_series(series_code):
    """
    Sincroniza la serie del INE con la base de datos local si no ha sido sincronizada en las últimas 72 horas.
    """
    try:
        last_sync = db.get_ine_last_sync(series_code)
        # Si han pasado menos de 3 días desde la última sync, usamos la caché local
        if last_sync and (time.time() - last_sync < 3 * 86400):
            return True

        url = f"https://servicios.ine.es/wstempus/js/es/DATOS_SERIE/{series_code}?nult=100"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        datapoints = data.get('Data', [])
        rows_to_save = []
        for dp in datapoints:
            anyo = dp.get('Anyo')
            periodo = dp.get('FK_Periodo')
            valor = dp.get('Valor')
            trimestre = PERIODO_TRIMESTRE.get(periodo)
            if anyo and trimestre and valor is not None:
                rows_to_save.append((series_code, int(anyo), int(trimestre), float(valor)))
                
        if rows_to_save:
            db.save_ine_ipv_data(series_code, rows_to_save)
            return True
    except Exception as e:
        print(f"[INE API] Error enviando/descargando serie {series_code}: {e}")
        
    return False

def get_ipv_value(series_code, year, quarter):
    """
    Obtiene el valor del IPV para un año y trimestre dado desde la BD (o intentando sync).
    """
    val = db.get_ine_ipv_value(series_code, year, quarter)
    if val is not None:
        return val
        
    # Intentar sincronizar
    if sync_ine_series(series_code):
        val = db.get_ine_ipv_value(series_code, year, quarter)
        if val is not None:
            return val
            
    # Si no se encuentra para ese trimestre exacto, buscar el trimestre más cercano disponible
    val_closest = db.get_ine_ipv_closest(series_code, year, quarter)
    return val_closest

def calculate_ine_revalorization(community_key, start_date_str, end_date_str=None):
    """
    Calcula el coeficiente de revalorización desde start_date hasta end_date (o fecha actual).
    Ejemplo: si IPV_start = 100 y IPV_end = 115, retorna 1.15 (+15%).
    """
    info = get_community_info(community_key)
    series_code = info['code']
    
    # Asegurar sync
    sync_ine_series(series_code)
    
    try:
        dt_start = datetime.strptime(start_date_str[:10], '%Y-%m-%d')
    except Exception:
        dt_start = datetime.now()
        
    if end_date_str:
        try:
            dt_end = datetime.strptime(end_date_str[:10], '%Y-%m-%d')
        except Exception:
            dt_end = datetime.now()
    else:
        dt_end = datetime.now()
        
    q_start = (dt_start.month - 1) // 3 + 1
    q_end = (dt_end.month - 1) // 3 + 1
    
    val_start = get_ipv_value(series_code, dt_start.year, q_start)
    val_end = get_ipv_value(series_code, dt_end.year, q_end)
    
    if not val_start:
        # Fallback al primer dato histórico disponible
        val_start = db.get_ine_ipv_first_available(series_code)
        
    if not val_end:
        val_end = db.get_ine_ipv_latest(series_code)
        
    if val_start and val_end and val_start > 0:
        return val_end / val_start
        
    return 1.0  # Fallback si no hay datos disponibles
