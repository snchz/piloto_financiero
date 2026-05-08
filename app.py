from flask import Flask, render_template_string, request, jsonify
import yfinance as yf
import threading
import time
import uuid

app = Flask(__name__)

monitores = {}
historial_alertas = []

def monitor_background():
    while True:
        for m_id, data in list(monitores.items()):
            if data['triggered']: continue
            try:
                ticker = yf.Ticker(data['ticker'])
                precio_actual = ticker.fast_info['last_price']
                data['current'] = round(precio_actual, 2)
                if (data['tipo'] == 'superior' and precio_actual >= data['target']) or \
                   (data['tipo'] == 'inferior' and precio_actual <= data['target']):
                    data['triggered'] = True
                    mensaje = f"🔔 {data['ticker']} alcanzó {data['target']} (Actual: {precio_actual:.2f})"
                    historial_alertas.insert(0, {'id': str(uuid.uuid4()), 'msg': mensaje, 'time': time.strftime('%H:%M:%S')})
            except: pass
        time.sleep(10)

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
        <h3>📈 Piloto Financiero</h3>
        <div class="card p-3 mb-4">
            <form onsubmit="event.preventDefault(); añadir();" class="row g-3">
                <div class="col-md-4"><input type="text" id="t" class="form-control" placeholder="Ticker (AAPL, BTC-USD)" required></div>
                <div class="col-md-4"><input type="number" step="0.01" id="obj" class="form-control" placeholder="Precio Objetivo" required></div>
                <div class="col-md-4"><button class="btn btn-primary w-100">Añadir Alerta</button></div>
            </form>
        </div>
        <div class="row">
            <div class="col-md-8">
                <table class="table bg-white shadow-sm">
                    <thead><tr><th>Ticker</th><th>Actual</th><th>Objetivo</th><th>Estado</th><th>-</th></tr></thead>
                    <tbody id="tabla"></tbody>
                </table>
            </div>
            <div class="col-md-4" id="alertas"></div>
        </div>
    </div>
    <script>
        async function añadir() {
            await fetch('/api/add', {method:'POST', headers:{'Content-Type':'application/json'}, 
            body: JSON.stringify({ticker: document.getElementById('t').value, target: document.getElementById('obj').value})});
            actualizar();
        }
        async function eliminar(id) { await fetch('/api/delete/'+id, {method:'DELETE'}); actualizar(); }
        async function actualizar() {
            const r = await fetch('/api/data'); const d = await r.json();
            document.getElementById('tabla').innerHTML = Object.entries(d.monitores).map(([id, v]) => `
                <tr><td>${v.ticker}</td><td>${v.current || '...'}</td><td>${v.target}</td>
                <td><span class="badge ${v.triggered?'bg-danger':'bg-success'}">${v.triggered?'ALERTA':'Vigilando'}</span></td>
                <td><button onclick="eliminar('${id}')" class="btn btn-sm btn-danger">x</button></td></tr>`).join('');
            document.getElementById('alertas').innerHTML = d.alertas.map(a => `<div class="alert alert-warning">${a.time}: ${a.msg}</div>`).join('');
        }
        setInterval(actualizar, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data(): return jsonify({"monitores": monitores, "alertas": historial_alertas})

@app.route('/api/add', methods=['POST'])
def add_monitor():
    data = request.json
    ticker = data['ticker'].upper()
    target = float(data['target'])
    precio = yf.Ticker(ticker).fast_info['last_price']
    m_id = str(uuid.uuid4())
    monitores[m_id] = {'ticker':ticker, 'target':target, 'current':round(precio,2), 'tipo':'superior' if target > precio else 'inferior', 'triggered':False}
    return jsonify({"ok":True})

@app.route('/api/delete/<m_id>', methods=['DELETE'])
def delete_monitor(m_id):
    if m_id in monitores: del monitores[m_id]
    return jsonify({"ok":True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)