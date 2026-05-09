from flask import Flask, render_template_string, request, jsonify
import yfinance as yf
import threading
import time
import uuid
import os
import importlib.metadata
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}
SEARCH_SESSION = requests.Session()
def obtener_yahoo_cookie_y_crumb(session, headers):
    """Obtiene una cookie válida y su crumb asociado para saltarse el error 401."""
    crumb = None
    try:
        # 1. Visitar un endpoint base para que Yahoo nos asigne una Cookie
        # fc.yahoo.com es un dominio de consentimiento/redirección que suele asignar la cookie rápidamente
        session.get('https://fc.yahoo.com', headers=headers, timeout=10)
        time.sleep(0.5)  # Breve pausa para asentar la cookie
        
        # 2. Solicitar el crumb a la API dedicada de Yahoo usando la sesión que ya tiene la cookie
        respuesta_crumb = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb", 
            headers=headers, 
            timeout=10
        )
        
        if respuesta_crumb.status_code == 200:
            crumb = respuesta_crumb.text.strip()
            # print(f"Crumb obtenido: {crumb}") # O usa tu add_debug_log si ya está definida
        else:
            pass # Manejo silencioso, el crumb quedará como None
            
    except Exception as e:
        pass # Si falla, continuaremos sin crumb (los fallbacks lo intentarán sin él)
        
    return crumb

# Inicializamos la variable global con el crumb al arrancar la app
YAHOO_CRUMB = obtener_yahoo_cookie_y_crumb(SEARCH_SESSION, SEARCH_HEADERS)
RETRY_STRATEGY = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
)
SEARCH_SESSION.mount("https://", HTTPAdapter(max_retries=RETRY_STRATEGY))

monitores = {}
historial_alertas = []
debug_logs = []  # Lista para almacenar logs de debug
isin_cache = {}

# Cargar versión desde archivo
def cargar_version():
    try:
        version_file = os.path.join(os.path.dirname(__file__), 'version.txt')
        with open(version_file, 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"

VERSION = cargar_version()
DEBUG_LOG = os.getenv('DEBUG_LOG', 'false').lower() == 'true'

def add_debug_log(message, level="INFO"):
    """Añade un log de debug si está habilitado"""
    if DEBUG_LOG:
        timestamp = time.strftime('%H:%M:%S')
        log_entry = {
            'id': str(uuid.uuid4()),
            'timestamp': timestamp,
            'level': level,
            'message': message
        }
        debug_logs.insert(0, log_entry)  # Insertar al principio
        # Mantener solo los últimos 100 logs
        if len(debug_logs) > 100:
            debug_logs.pop()

# Mostrar información al iniciar
print("=" * 60)
print(f"🚀 Piloto Financiero v{VERSION} - INICIANDO")
print(f"   Debug Mode: {'ACTIVADO' if DEBUG_LOG else 'Desactivado'}")
print(f"   Hora: {time.strftime('%d/%m/%Y %H:%M:%S')}")
print(f"   Python Version: {__import__('sys').version}")
print(f"   Flask Version: {importlib.metadata.version('flask')}")
print(f"   YFinance Version: {importlib.metadata.version('yfinance')}")
print("=" * 60)

# Log inicial de debug
add_debug_log("Aplicación iniciada correctamente", "INFO")
add_debug_log(f"Versión: {VERSION}", "INFO")
add_debug_log(f"Debug Mode: {'ACTIVADO' if DEBUG_LOG else 'Desactivado'}", "INFO")

def monitor_background():
    while True:
        for m_id, data in list(monitores.items()):
            if data['triggered']: continue
            try:
                ticker_str = data.get('symbol', data['ticker'])
                ticker = yf.Ticker(ticker_str)
                # Usamos basic_info o history como alternativa más estable si fast_info falla
                precio_actual = ticker.fast_info['last_price']
                if precio_actual is None: continue
                
                data['current'] = round(precio_actual, 2)
                if (data['tipo'] == 'superior' and precio_actual >= data['target']) or \
                   (data['tipo'] == 'inferior' and precio_actual <= data['target']):
                    data['triggered'] = True
                    mensaje = f"🔔 {data['ticker']} alcanzó {data['target']} (Actual: {precio_actual:.2f})"
                    historial_alertas.insert(0, {'id': str(uuid.uuid4()), 'msg': mensaje, 'time': time.strftime('%H:%M:%S')})
            except: pass
        time.sleep(15) # Aumentamos un poco el margen para evitar bloqueos

threading.Thread(target=monitor_background, daemon=True).start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Monitor Bolsa</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .debug-panel {
            position: fixed;
            bottom: 10px;
            right: 10px;
            width: 400px;
            max-height: 300px;
            background: rgba(0,0,0,0.9);
            color: #fff;
            border-radius: 8px;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
            z-index: 1000;
            display: none;
        }
        .debug-toggle {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            cursor: pointer;
            z-index: 1001;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
        .debug-toggle:hover {
            background: #0056b3;
        }
        .debug-logs {
            max-height: 250px;
            overflow-y: auto;
        }
        .log-entry {
            margin: 2px 0;
            padding: 2px 4px;
            border-radius: 3px;
        }
        .log-INFO { background: rgba(0,123,255,0.1); }
        .log-ERROR { background: rgba(220,53,69,0.1); color: #ff6b6b; }
        .log-WARNING { background: rgba(255,193,7,0.1); color: #ffc107; }
    </style>
</head>
<body class="bg-light" onload="actualizar()">
    <div class="container mt-5">
        <div style="position:absolute;top:10px;right:15px;font-size:12px;color:#666;padding:8px;border:1px solid #ddd;border-radius:4px;background:#f9f9f9;">
            📦 v<span id="version">{{ version }}</span>
        </div>
        <h3>📈 Piloto Financiero</h3>
        <div class="card p-3 mb-4">
            <form onsubmit="event.preventDefault(); añadir();" class="row g-3">
                <div class="col-md-4"><input type="text" id="t" class="form-control" placeholder="Ticker o ISIN (AAPL, ES0105065009)" required></div>
                <div class="col-md-4"><input type="number" step="0.01" id="obj" class="form-control" placeholder="Precio Objetivo" required></div>
                <div class="col-md-4"><button class="btn btn-primary w-100">Añadir Alerta</button></div>
            </form>
            <div id="error-msg" class="text-danger mt-2" style="display:none;">⚠️ Ticker no válido o error de conexión.</div>
        </div>
        <div class="row">
            <div class="col-md-8">
                <table class="table bg-white shadow-sm rounded">
                    <thead><tr><th>Ticker</th><th>Actual</th><th>Objetivo</th><th>Estado</th><th>-</th></tr></thead>
                    <tbody id="tabla"></tbody>
                </table>
            </div>
            <div class="col-md-4" id="alertas"></div>
        </div>
    </div>
    
    <!-- Panel de Debug -->
    <button class="debug-toggle" onclick="toggleDebug()" title="Toggle Debug Logs">🐛</button>
    <div class="debug-panel" id="debugPanel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;gap:8px;">
            <strong>Debug Logs</strong>
            <div>
                <button onclick="copyLogs()" style="background:none;border:none;color:#fff;cursor:pointer;" title="Copiar logs al portapapeles">📋</button>
                <button onclick="clearLogs()" style="background:none;border:none;color:#fff;cursor:pointer;" title="Limpiar logs">🗑️</button>
            </div>
        </div>
        <div class="debug-logs" id="debugLogs"></div>
    </div>
    
    <script>
        let versionActual = '{{ version }}';
        let debugEnabled = {{ debug_enabled|tojson }};
        
        async function añadir() {
            const err = document.getElementById('error-msg');
            err.style.display = 'none';
            const res = await fetch('/api/add', {
                method:'POST', 
                headers:{'Content-Type':'application/json'}, 
                body: JSON.stringify({ticker: document.getElementById('t').value, target: document.getElementById('obj').value})
            });
            if (res.ok) {
                document.getElementById('t').value = '';
                document.getElementById('obj').value = '';
                actualizar();
            } else {
                err.style.display = 'block';
            }
        }
        async function eliminar(id) { await fetch('/api/delete/'+id, {method:'DELETE'}); actualizar(); }
        async function actualizar() {
            try {
                const r = await fetch('/api/data'); 
                const d = await r.json();
                
                // Verificar si la versión ha cambiado
                if (d.version && d.version !== versionActual) {
                    console.log('Nueva versión detectada:', d.version);
                    versionActual = d.version;
                    document.getElementById('version').textContent = d.version;
                    // Mostrar notificación de actualización
                    const alert = document.createElement('div');
                    alert.className = 'alert alert-info position-fixed top-0 start-50 translate-middle-x mt-3';
                    alert.textContent = '🔄 Aplicación actualizada a v' + d.version;
                    alert.style.zIndex = '9999';
                    document.body.appendChild(alert);
                    setTimeout(() => alert.remove(), 3000);
                }
                
                document.getElementById('tabla').innerHTML = Object.entries(d.monitores).map(([id, v]) => `
                    <tr><td><strong>${v.ticker}</strong></td><td>${v.current || '...'}</td><td>${v.target}</td>
                    <td><span class="badge ${v.triggered?'bg-danger':'bg-success'}">${v.triggered?'ALERTA':'Vigilando'}</span></td>
                    <td><button onclick="eliminar('${id}')" class="btn btn-sm btn-outline-danger">x</button></td></tr>`).join('');
                document.getElementById('alertas').innerHTML = d.alertas.map(a => `<div class="alert alert-warning p-2">${a.time}: ${a.msg}</div>`).join('');
                
                // Actualizar logs de debug si están habilitados
                if (debugEnabled) {
                    actualizarLogs();
                }
            } catch(e) {
                console.error('Error actualizando:', e);
            }
        }
        
        async function actualizarLogs() {
            try {
                const r = await fetch('/api/logs');
                const d = await r.json();
                if (d.enabled) {
                    document.getElementById('debugLogs').innerHTML = d.logs.map(log => 
                        `<div class="log-entry log-${log.level}">[${log.timestamp}] ${log.level}: ${log.message}</div>`
                    ).join('');
                }
            } catch(e) {
                console.error('Error obteniendo logs:', e);
            }
        }
        
        function toggleDebug() {
            const panel = document.getElementById('debugPanel');
            const toggle = document.querySelector('.debug-toggle');
            
            if (panel.style.display === 'none' || panel.style.display === '') {
                panel.style.display = 'block';
                toggle.style.display = 'none';
                if (debugEnabled) actualizarLogs();
            } else {
                panel.style.display = 'none';
                toggle.style.display = 'block';
            }
        }
        
        function clearLogs() {
            fetch('/api/logs', {method: 'DELETE'});
            document.getElementById('debugLogs').innerHTML = '';
        }

        function copyLogs() {
            const logs = document.getElementById('debugLogs').innerText;
            if (!logs) {
                alert('No hay logs para copiar.');
                return;
            }
            navigator.clipboard.writeText(logs)
                .then(() => alert('Logs copiados al portapapeles.'))
                .catch(() => alert('No se pudo copiar los logs. Intenta de nuevo.'));
        }
        
        setInterval(actualizar, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index(): 
    return render_template_string(HTML_TEMPLATE, version=cargar_version(), debug_enabled=DEBUG_LOG)

@app.route('/api/data')
def get_data(): 
    return jsonify({"monitores": monitores, "alertas": historial_alertas, "version": cargar_version()})

@app.route('/api/logs')
def get_logs():
    """Endpoint para obtener logs de debug (solo si está habilitado)"""
    if not DEBUG_LOG:
        return jsonify({"logs": [], "enabled": False})
    return jsonify({"logs": debug_logs, "enabled": True})

@app.route('/api/logs', methods=['DELETE'])
def clear_logs():
    """Endpoint para limpiar logs de debug"""
    if DEBUG_LOG:
        debug_logs.clear()
        add_debug_log("Logs limpiados manualmente")
    return jsonify({"ok": True})

def buscar_ticker_por_isin(isin):
    """Intenta encontrar el ticker correspondiente a un ISIN usando la API de búsqueda de Yahoo Finance."""
    search_endpoints = [
        "https://query1.finance.yahoo.com/v1/finance/search",
        "https://query2.finance.yahoo.com/v1/finance/search"
    ]
    params = {"q": isin, "quotesCount": 5}

    if isin in isin_cache:
        add_debug_log(f"Usando cache de ISIN para {isin}: {isin_cache[isin]}")
        return isin_cache[isin]

    for url in search_endpoints:
        try:
            add_debug_log(f"Buscando ticker para ISIN: {isin} via {url}")
            response = SEARCH_SESSION.get(url, params=params, headers=SEARCH_HEADERS, timeout=10)
            add_debug_log(f"Yahoo Search respuesta: status={response.status_code} content_type={response.headers.get('Content-Type')} text={response.text[:300]!r}")
            if response.status_code == 429:
                add_debug_log("✗ 429 rate limit de Yahoo Search, esperando 2 segundos")
                time.sleep(2)
                continue
            response.raise_for_status()
            if not response.text.strip():
                add_debug_log("✗ Respuesta vacía de búsqueda Yahoo")
                continue

            data = response.json()
            quotes = data.get('quotes', []) or []
            if not quotes:
                add_debug_log(f"No se encontraron resultados de búsqueda para ISIN: {isin}")
                continue

            for quote in quotes:
                ticker = quote.get('symbol')
                if not ticker:
                    continue
                add_debug_log(f"Encontrado ticker candidato: {ticker}")
                add_debug_log(f"Asumiendo ticker alternativo válido para ISIN {isin}: {ticker}")
                isin_cache[isin] = ticker
                return ticker
        except requests.exceptions.RequestException as e:
            add_debug_log(f"✗ Error buscando ticker para ISIN {isin}: {e}")
            continue
        except ValueError as e:
            add_debug_log(f"✗ Error parseando JSON para ISIN {isin}: {e}")
            continue

    add_debug_log(f"No se encontró ticker válido para ISIN: {isin}")
    isin_cache[isin] = None
    return None

def es_isin(codigo):
    """Verifica si el código parece ser un ISIN (formato: 2 letras + 9 dígitos)"""
    return len(codigo) == 12 and codigo[:2].isalpha() and codigo[2:].isdigit()

def obtener_precio_yahoo_quote(ticker_str):
    """Obtiene precio desde el endpoint quote de Yahoo Finance como fallback."""
    search_endpoints = [
        "https://query1.finance.yahoo.com/v7/finance/quote",
        "https://query2.finance.yahoo.com/v7/finance/quote",
    ]
    
    # Añadimos el crumb a los parámetros si logramos obtenerlo al inicio
    params = {"symbols": ticker_str}
    if YAHOO_CRUMB:
        params["crumb"] = YAHOO_CRUMB

    for url in search_endpoints:
        try:
            add_debug_log(f"Fallback quote Yahoo para {ticker_str}: {url} {params}")
            
            # Al usar SEARCH_SESSION, las cookies obtenidas en el paso 1 se envían automáticamente
            response = SEARCH_SESSION.get(url, params=params, headers=SEARCH_HEADERS, timeout=10)
            add_debug_log(f"Yahoo Quote respuesta: status={response.status_code} content_type={response.headers.get('Content-Type')} text={response.text[:500]!r}")
            if response.status_code == 401:
                add_debug_log(f"✗ Quote Yahoo 401 para {ticker_str} en {url}")
                continue
            response.raise_for_status()
            data = response.json()
            result = data.get('quoteResponse', {}).get('result', [])
            if not result:
                add_debug_log(f"✗ Quote Yahoo sin result para {ticker_str} en {url}")
                continue
            quote = result[0]
            precio = quote.get('regularMarketPrice')
            if precio is not None:
                add_debug_log(f"✓ Precio obtenido via Yahoo Quote para {ticker_str}: {precio}")
                return precio
            add_debug_log(f"✗ Quote Yahoo no contiene regularMarketPrice para {ticker_str}: {quote}")
        except ValueError as e:
            add_debug_log(f"✗ Error parseando JSON en Yahoo Quote para {ticker_str}: {e}")
        except Exception as e:
            add_debug_log(f"✗ Error en Yahoo Quote para {ticker_str}: {e}")
    return None


def obtener_precio_yahoo_chart(ticker_str):
    """Obtiene precio desde el endpoint chart de Yahoo Finance como fallback."""
    chart_endpoints = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker_str}",
    ]
    params = {"interval": "1d", "range": "1mo"}

    for url in chart_endpoints:
        try:
            add_debug_log(f"Fallback chart Yahoo para {ticker_str}: {url} {params}")
            response = SEARCH_SESSION.get(url, params=params, headers=SEARCH_HEADERS, timeout=10)
            add_debug_log(f"Yahoo Chart respuesta: status={response.status_code} content_type={response.headers.get('Content-Type')} text={response.text[:500]!r}")
            if response.status_code == 404:
                add_debug_log(f"✗ Chart Yahoo 404 para {ticker_str} en {url}")
                continue
            response.raise_for_status()
            data = response.json()
            result = data.get('chart', {}).get('result')
            if not result:
                add_debug_log(f"✗ Chart Yahoo sin result para {ticker_str} en {url}")
                continue
            indicators = result[0].get('indicators', {}).get('quote', [])
            if not indicators:
                add_debug_log(f"✗ Chart Yahoo sin indicadores para {ticker_str} en {url}")
                continue
            close_prices = indicators[0].get('close', [])
            if not close_prices:
                add_debug_log(f"✗ Chart Yahoo sin precios de cierre para {ticker_str} en {url}")
                continue
            for precio in reversed(close_prices):
                if precio is not None:
                    add_debug_log(f"✓ Precio obtenido via Yahoo Chart para {ticker_str}: {precio}")
                    return precio
            add_debug_log(f"✗ Chart Yahoo no devolvió precio válido para {ticker_str} en {url}")
        except ValueError as e:
            add_debug_log(f"✗ Error parseando JSON en Yahoo Chart para {ticker_str}: {e}")
        except Exception as e:
            add_debug_log(f"✗ Error en Yahoo Chart para {ticker_str}: {e}")
    return None

def obtener_precio(ticker_str):
    """Intenta obtener el precio de varias formas para mayor robustez"""
    try:
        add_debug_log(f"Intentando obtener precio para: {ticker_str}")
        t = yf.Ticker(ticker_str)
        
        # Intento 1: fast_info (más rápido pero menos confiable)
        try:
            precio = t.fast_info.get('last_price')
            if precio and precio > 0:
                add_debug_log(f"✓ Precio obtenido via fast_info: {precio}")
                return precio
            else:
                add_debug_log(f"✗ fast_info devolvió precio inválido: {precio}")
        except Exception as e:
            add_debug_log(f"✗ Error en fast_info: {e}")
        
        # Intento 2: history (más confiable)
        try:
            hist = t.history(period="1d")
            if not hist.empty:
                precio = hist['Close'].iloc[-1]
                add_debug_log(f"✓ Precio obtenido via history 1d: {precio}")
                return precio
            add_debug_log("✗ History 1d devolvió datos vacíos, intento 5d")
        except Exception as e:
            add_debug_log(f"✗ Error en history 1d: {e}")

        try:
            hist = t.history(period="5d")
            if not hist.empty:
                precio = hist['Close'].iloc[-1]
                add_debug_log(f"✓ Precio obtenido via history 5d: {precio}")
                return precio
            add_debug_log("✗ History 5d devolvió datos vacíos")
        except Exception as e:
            add_debug_log(f"✗ Error en history 5d: {e}")
        
        # Intento 3: info (último recurso)
        try:
            info = t.info
            if info and 'regularMarketPrice' in info and info['regularMarketPrice']:
                precio = info['regularMarketPrice']
                add_debug_log(f"✓ Precio obtenido via info: {precio}")
                return precio
            else:
                add_debug_log(f"✗ Info no contiene regularMarketPrice válido: {info.get('regularMarketPrice') if info else 'None'}")
        except Exception as e:
            add_debug_log(f"✗ Error en info: {e}")

        # Intento 4: fallback directo a Yahoo Quote
        add_debug_log(f"Intentando fallback Yahoo Quote para {ticker_str}")
        precio_quote = obtener_precio_yahoo_quote(ticker_str)
        if precio_quote is not None:
            return precio_quote

        # Intento 5: fallback directo a Yahoo Chart
        add_debug_log(f"Intentando fallback Yahoo Chart para {ticker_str}")
        precio_chart = obtener_precio_yahoo_chart(ticker_str)
        if precio_chart is not None:
            return precio_chart

        add_debug_log(f"✗ No se pudo obtener precio para {ticker_str}")
        raise ValueError(f"No data available for {ticker_str}")
    except Exception as e:
        add_debug_log(f"✗ Error general obteniendo precio para {ticker_str}: {e}")
        raise Exception(f"No se pudo obtener precio: {e}")

@app.route('/api/add', methods=['POST'])
def add_monitor():
    try:
        data = request.json
        ticker_input = data.get('ticker', '').upper().strip()
        if not ticker_input: 
            add_debug_log("Intento de añadir monitor sin ticker")
            return jsonify({"ok":False}), 400
        
        target = float(data['target'])
        ticker_name = ticker_input
        actual_ticker = ticker_input
        add_debug_log(f"Añadiendo monitor para {ticker_input} con objetivo {target}")
        
        # Intentar obtener precio con la función robusta
        try:
            precio = obtener_precio(ticker_input)
        except Exception as e:
            # Si es ISIN y falló, intentar buscar el ticker correspondiente
            if es_isin(ticker_input):
                add_debug_log(f"ISIN {ticker_input} falló, buscando ticker alternativo...")
                ticker_alternativo = buscar_ticker_por_isin(ticker_input)
                if ticker_alternativo:
                    add_debug_log(f"Intentando con ticker alternativo: {ticker_alternativo}")
                    try:
                        precio = obtener_precio(ticker_alternativo)
                        ticker_name = f"{ticker_input} ({ticker_alternativo})"  # Mostrar ISIN + ticker
                        actual_ticker = ticker_alternativo
                        add_debug_log(f"✓ Éxito con ticker alternativo: {ticker_alternativo}")
                    except Exception as e2:
                        add_debug_log(f"✗ Ticker alternativo también falló: {e2}")
                        raise Exception(f"ISIN no encontrado ni como ISIN ni como ticker alternativo")
                else:
                    raise Exception(f"ISIN no encontrado y no se pudo encontrar ticker alternativo")
            else:
                raise e

        m_id = str(uuid.uuid4())
        monitores[m_id] = {
            'ticker': ticker_name,
            'symbol': actual_ticker,
            'target': target,
            'current': round(precio, 2),
            'tipo': 'superior' if target > precio else 'inferior',
            'triggered': False
        }
        add_debug_log(f"✓ Monitor añadido exitosamente: {ticker_name} (ID: {m_id})")
        return jsonify({"ok":True})
    except Exception as e:
        add_debug_log(f"✗ Error añadiendo monitor para {ticker_input}: {e}")
        return jsonify({"ok":False}), 400

@app.route('/api/delete/<m_id>', methods=['DELETE'])
def delete_monitor(m_id):
    if m_id in monitores: del monitores[m_id]
    return jsonify({"ok":True})

if __name__ == '__main__':
    print("=" * 60)
    print(f"✅ Aplicación lista para recibir requests en puerto 5000")
    print("=" * 60)
    add_debug_log("Iniciando servidor Flask en puerto 5000", "INFO")
    app.run(host='0.0.0.0', port=5000)