import pandas as pd
import re
import uuid
from datetime import datetime
import db

def process_inversis_xls(file_path):
    """
    Procesa archivos .xls exportados desde Inversis (MyInvestor).
    Estos archivos son técnicamente tablas HTML, por lo que usamos read_html.
    """
    try:
        # Los archivos de Inversis en español suelen usar codificación latin1
        with open(file_path, 'r', encoding='latin1') as f:
            html_content = f.read()
            
        # read_html extrae todas las tablas detectadas en el HTML
        dfs = pd.read_html(html_content, decimal=',', thousands='.')
    except Exception:
        # Fallback a utf-8 por si cambiaron la codificación
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        dfs = pd.read_html(html_content, decimal=',', thousands='.')

    df = None
    
    # 1. Lectura Robusta: Buscamos el DataFrame que contiene la cabecera real
    for temp_df in dfs:
        # Inspeccionamos las primeras filas para encontrar la cabecera
        for i in range(min(10, len(temp_df))):
            row_values = temp_df.iloc[i].astype(str).values
            # Identificadores clave de Inversis
            if any("Fecha operación" in val for val in row_values) and any("Referencia" in val for val in row_values):
                temp_df.columns = temp_df.iloc[i] # Promovemos esta fila a cabecera
                df = temp_df.iloc[i+1:].copy()    # Recortamos los datos inútiles de arriba
                break
        if df is not None:
            break
            
    if df is None or df.empty:
        raise ValueError("No se pudo encontrar una tabla de operaciones válida en el archivo de Inversis.")
    
    # Limpiamos los nombres de las columnas para asegurar coincidencias
    df.columns = [str(c).strip() for c in df.columns]
    
    operaciones_procesadas = 0
    operaciones_ignoradas = 0
    warnings = []

    with db.get_db() as conn:
        for _, row in df.iterrows():
            try:
                # --- 2. Mapeo de Columnas ---
                referencia = str(row.get('Referencia', '')).strip()
                if not referencia or referencia.lower() == 'nan':
                    continue # Si no tiene referencia, no es una fila de operación válida
                    
                # --- 3. Lógica Anti-Duplicados ---
                existe = conn.execute("SELECT 1 FROM operaciones WHERE external_id = ?", (referencia,)).fetchone()
                if existe:
                    operaciones_ignoradas += 1
                    continue

                # Fecha
                fecha_str = str(row.get('Fecha operación', ''))
                try:
                    fecha = pd.to_datetime(fecha_str, format='%d/%m/%Y', errors='coerce')
                    fecha_format = fecha.strftime('%Y-%m-%d') if pd.notna(fecha) else datetime.now().strftime('%Y-%m-%d')
                except Exception:
                    fecha_format = datetime.now().strftime('%Y-%m-%d')

                # Ticker/ISIN: Extraer mediante regex lo que está entre corchetes
                titulo_isin = str(row.get('Título / I.S.I.N.', ''))
                match_isin = re.search(r'\[([A-Z0-9]+)\]', titulo_isin)
                ticker = match_isin.group(1) if match_isin else titulo_isin[:20].strip()

                # Concepto (Tipo de Operación)
                concepto = str(row.get('Concepto', '')).upper()
                if "SUSCRIPCION" in concepto or "COMPRA" in concepto:
                    tipo = "COMPRA"
                elif "REEMBOLSO" in concepto or "VENTA" in concepto:
                    tipo = "VENTA"
                elif "DIVIDENDO" in concepto:
                    tipo = "DIVIDENDO"
                else:
                    tipo = "COMPRA" # Por defecto

                # Importe
                importe_raw = str(row.get('Importe', '0')).replace('€', '').replace('.', '').replace(',', '.').strip()
                try:
                    importe = float(importe_raw)
                except ValueError:
                    importe = 0.0

                # --- 4. Manejo de Datos Faltantes ---
                cantidad = 1.0
                precio = abs(importe)
                
                if precio > 0:
                    warnings.append(f"<b>{ticker}</b> ({fecha_format}): Importada sin datos de participaciones. Asignado Precio={precio} y Cantidad=1. <u>Requiere revisión manual.</u>")

                # Insertar en BD
                op_id = str(uuid.uuid4())
                conn.execute('''
                    INSERT INTO operaciones (id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, external_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (op_id, fecha_format, ticker, tipo, cantidad, precio, 0.0, 0.0, referencia))
                operaciones_procesadas += 1
            except Exception as e:
                continue
        conn.commit()
        
    return {"ok": True, "procesadas": operaciones_procesadas, "ignoradas": operaciones_ignoradas, "warnings": warnings}