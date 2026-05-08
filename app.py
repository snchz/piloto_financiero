from flask import Flask, render_template_string, request, jsonify
import yfinance as yf
import threading
import time
import uuid
import os

app = Flask(__name__)

monitores = {}
historial_alertas = []

# Cargar versión desde archivo
def cargar_version():
    try:
        version_file = os.path.join(os.path.dirname(__file__), 'version.txt')
        with open(version_file, 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"

VERSION = cargar_version()

def monitor_background():
    while True:
        for m_id, data in list(monitores.items()):
            if data['triggered']: continue
            try:
                ticker = yf.Ticker(data['ticker'])
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
    <script>
        let versionActual = '{{ version }}';
        
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
            } catch(e) {}
        }
        setInterval(actualizar, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index(): 
    return render_template_string(HTML_TEMPLATE, version=cargar_version())

@app.route('/api/data')
def get_data(): 
    return jsonify({"monitores": monitores, "alertas": historial_alertas, "version": cargar_version()})

def es_isin(codigo):
    """Verifica si el código parece ser un ISIN (formato: 2 letras + 9 dígitos)"""
    return len(codigo) == 12 and codigo[:2].isalpha() and codigo[2:].isdigit()

def obtener_precio(ticker_str):
    """Intenta obtener el precio de varias formas para mayor robustez"""
    try:
        t = yf.Ticker(ticker_str)
        # Intento 1: fast_info (más rápido pero menos confiable)
        try:
            precio = t.fast_info.get('last_price')
            if precio and precio > 0:
                return precio
        except:
            pass
        
        # Intento 2: history (más confiable)
        hist = t.history(period="1d")
        if not hist.empty:
            return hist['Close'].iloc[-1]
        
        # Intento 3: info (último recurso)
        info = t.info
        if 'regularMarketPrice' in info and info['regularMarketPrice']:
            return info['regularMarketPrice']
        
        raise ValueError(f"No data available for {ticker_str}")
    except Exception as e:
        raise Exception(f"No se pudo obtener precio: {e}")

@app.route('/api/add', methods=['POST'])
def add_monitor():
    try:
        data = request.json
        ticker_input = data.get('ticker', '').upper().strip()
        if not ticker_input: return jsonify({"ok":False}), 400
        
        target = float(data['target'])
        ticker_name = ticker_input
        
        # Intentar obtener precio con la función robusta
        precio = obtener_precio(ticker_input)

        m_id = str(uuid.uuid4())
        monitores[m_id] = {
            'ticker': ticker_name, 
            'target': target, 
            'current': round(precio, 2), 
            'tipo': 'superior' if target > precio else 'inferior', 
            'triggered': False
        }
        return jsonify({"ok":True})
    except Exception as e:
        print(f"Error añadiendo {ticker_input}: {e}")
        return jsonify({"ok":False}), 400

@app.route('/api/delete/<m_id>', methods=['DELETE'])
def delete_monitor(m_id):
    if m_id in monitores: del monitores[m_id]
    return jsonify({"ok":True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)