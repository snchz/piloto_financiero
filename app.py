import json
import os
import threading
import time
import uuid

import requests
import yfinance as yf
from flask import Flask, jsonify, render_template_string, request
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# --- Configuration & Setup ---

DATA_DIR = 'data'
DATA_FILE = os.path.join(DATA_DIR, 'monitores.json')
VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version.txt')
DEBUG_LOG = os.getenv('DEBUG_LOG', 'false').lower() == 'true'

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

# --- State ---
state = {
    "monitores": {},
    "alertas": [],
    "logs": [],
    "isin_cache": {}
}

# --- Initialization ---
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "1.0.0"

VERSION = load_version()

def setup_session():
    s = requests.Session()
    retries = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["HEAD", "GET", "OPTIONS"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

session = setup_session()

def fetch_yahoo_crumb():
    try:
        session.get('https://fc.yahoo.com', headers=SEARCH_HEADERS, timeout=10)
        time.sleep(0.5)
        res = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", headers=SEARCH_HEADERS, timeout=10)
        return res.text.strip() if res.status_code == 200 else None
    except Exception:
        return None

YAHOO_CRUMB = fetch_yahoo_crumb()

# --- Logging ---
def log_debug(msg, level="INFO"):
    print(f"[{level}] {msg}")
    if not DEBUG_LOG:
        return
    entry = {
        'id': str(uuid.uuid4()),
        'timestamp': time.strftime('%H:%M:%S'),
        'level': level,
        'message': msg
    }
    state["logs"].insert(0, entry)
    if len(state["logs"]) > 100:
        state["logs"].pop()

# --- Data Management ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            state["monitores"] = data.get('monitores', {})
            state["alertas"] = data.get('alertas', [])
    except Exception as e:
        log_debug(f"Failed to load data: {e}", "ERROR")

def save_data():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'monitores': state["monitores"],
                'alertas': state["alertas"]
            }, f, ensure_ascii=False, indent=4)
    except Exception as e:
        log_debug(f"Failed to save data: {e}", "ERROR")

load_data()

# --- Core Logic ---
def resolve_ticker(isin_or_ticker):
    if len(isin_or_ticker) == 12 and isin_or_ticker[:2].isalpha() and isin_or_ticker[2:].isdigit():
        if isin_or_ticker in state["isin_cache"]:
            return state["isin_cache"][isin_or_ticker]
            
        endpoints = [
            "https://query1.finance.yahoo.com/v1/finance/search",
            "https://query2.finance.yahoo.com/v1/finance/search"
        ]
        
        for url in endpoints:
            try:
                res = session.get(url, params={"q": isin_or_ticker, "quotesCount": 5}, headers=SEARCH_HEADERS, timeout=10)
                if res.status_code == 429:
                    time.sleep(2)
                    continue
                res.raise_for_status()
                quotes = res.json().get('quotes', [])
                for q in quotes:
                    if sym := q.get('symbol'):
                        state["isin_cache"][isin_or_ticker] = sym
                        return sym
            except Exception:
                continue
        return None
    return isin_or_ticker

def fetch_asset_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        name = info.get('shortName') or info.get('longName') or ""
        currency = info.get('currency') or ""
        return name, currency
    except Exception:
        return "", ""

def fetch_price(ticker):
    t = yf.Ticker(ticker)
    
    try:
        if p := t.fast_info.get('last_price'): return p
    except Exception: pass
        
    try:
        hist = t.history(period="1d")
        if not hist.empty: return float(hist['Close'].iloc[-1])
    except Exception: pass
        
    try:
        info = t.info
        if p := info.get('regularMarketPrice'): return p
    except Exception: pass
        
    params = {"symbols": ticker}
    if YAHOO_CRUMB: params["crumb"] = YAHOO_CRUMB
        
    try:
        res = session.get("https://query1.finance.yahoo.com/v7/finance/quote", params=params, headers=SEARCH_HEADERS, timeout=10)
        res.raise_for_status()
        quote = res.json().get('quoteResponse', {}).get('result', [])[0]
        if p := quote.get('regularMarketPrice'): return p
    except Exception: pass
        
    raise ValueError(f"Unable to fetch price for {ticker}")

# --- Background Worker ---
def background_monitor():
    while True:
        for m_id, data in list(state["monitores"].items()):
            if data.get('triggered'):
                continue
                
            try:
                sym = data.get('symbol', data['ticker'])
                precio = fetch_price(sym)
                data['current'] = round(precio, 2)
                
                is_above_target = data['tipo'] == 'superior' and precio >= data['target']
                is_below_target = data['tipo'] == 'inferior' and precio <= data['target']
                
                if is_above_target or is_below_target:
                    data['triggered'] = True
                    msg = f"🔔 {data['ticker']} alcanzó {data['target']} (Actual: {precio:.2f})"
                    state["alertas"].insert(0, {
                        'id': str(uuid.uuid4()), 
                        'msg': msg, 
                        'time': time.strftime('%H:%M:%S')
                    })
                    save_data()
            except Exception as e:
                log_debug(f"Monitor update failed for {data.get('ticker')}: {e}", "WARNING")
                
        time.sleep(15)

threading.Thread(target=background_monitor, daemon=True).start()

# --- API Endpoints ---
@app.route('/api/data')
def get_data():
    return jsonify({
        "monitores": state["monitores"], 
        "alertas": state["alertas"], 
        "version": VERSION
    })

@app.route('/api/add', methods=['POST'])
def add_monitor():
    data = request.json
    raw_input = data.get('ticker', '').upper().strip()
    target = float(data.get('target', 0))
    
    if not raw_input or target <= 0:
        return jsonify({"error": "Parámetros inválidos"}), 400
        
    try:
        sym = resolve_ticker(raw_input)
        if not sym:
            raise ValueError(f"No se encontró el activo para {raw_input}")
            
        price = fetch_price(sym)
        name, currency = fetch_asset_info(sym)
        
        m_id = str(uuid.uuid4())
        state["monitores"][m_id] = {
            'ticker': f"{raw_input} ({sym})" if raw_input != sym else raw_input,
            'symbol': sym,
            'name': name,
            'currency': currency,
            'target': target,
            'current': round(price, 2),
            'tipo': 'superior' if target > price else 'inferior',
            'triggered': False
        }
        
        save_data()
        log_debug(f"Added monitor for {sym} at {target}")
        return jsonify({"ok": True})
        
    except Exception as e:
        log_debug(f"Add monitor failed: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

@app.route('/api/edit/<m_id>', methods=['PUT'])
def edit_monitor(m_id):
    if m_id not in state["monitores"]:
        return jsonify({"error": "No encontrado"}), 404
        
    try:
        target = float(request.json.get('target'))
        monitor = state["monitores"][m_id]
        
        monitor['target'] = target
        if monitor.get('current'):
            monitor['tipo'] = 'superior' if target > monitor['current'] else 'inferior'
        monitor['triggered'] = False
        
        save_data()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/delete/<m_id>', methods=['DELETE'])
def delete_monitor(m_id):
    if state["monitores"].pop(m_id, None):
        save_data()
    return jsonify({"ok": True})

@app.route('/api/logs', methods=['GET', 'DELETE'])
def handle_logs():
    if request.method == 'DELETE':
        state["logs"].clear()
        return jsonify({"ok": True})
    return jsonify({"logs": state["logs"], "enabled": DEBUG_LOG})

# --- UI Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Piloto Financiero</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0f1115;
            --bg-surface: #181a20;
            --bg-surface-hover: #22252d;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --border-color: rgba(255, 255, 255, 0.05);
        }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            -webkit-font-smoothing: antialiased;
        }
        .glass-panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .table {
            --bs-table-bg: transparent;
            --bs-table-color: var(--text-primary);
            margin-bottom: 0;
        }
        .table th {
            border-bottom-color: var(--border-color);
            color: var(--text-secondary);
            font-weight: 500;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .table td {
            border-bottom-color: var(--border-color);
            vertical-align: middle;
        }
        .table tbody tr {
            transition: background-color 0.2s;
        }
        .table tbody tr:hover {
            background-color: var(--bg-surface-hover);
        }
        .form-control {
            background-color: rgba(255,255,255,0.03);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-radius: 8px;
            transition: all 0.2s;
        }
        .form-control:focus {
            background-color: rgba(255,255,255,0.05);
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
            color: var(--text-primary);
        }
        .btn-primary {
            background-color: var(--accent);
            border: none;
            border-radius: 8px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-primary:hover {
            background-color: var(--accent-hover);
            transform: translateY(-1px);
        }
        .badge-status {
            font-weight: 500;
            padding: 0.35em 0.65em;
            border-radius: 6px;
            font-size: 0.8rem;
        }
        .badge-active {
            background-color: rgba(16, 185, 129, 0.1);
            color: #34d399;
        }
        .badge-alert {
            background-color: rgba(239, 68, 68, 0.1);
            color: #f87171;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .action-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            transition: color 0.2s;
            padding: 4px;
        }
        .action-btn:hover {
            color: var(--text-primary);
        }
        .action-btn.delete:hover {
            color: #f87171;
        }
        /* Layout adjustments */
        .page-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        .brand {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            background: linear-gradient(to right, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .version-badge {
            font-size: 0.75rem;
            color: var(--text-secondary);
            background: rgba(255,255,255,0.05);
            padding: 4px 8px;
            border-radius: 99px;
        }
        .alerts-feed {
            max-height: 400px;
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: var(--border-color) transparent;
        }
        .alerts-feed::-webkit-scrollbar {
            width: 4px;
        }
        .alerts-feed::-webkit-scrollbar-thumb {
            background-color: var(--border-color);
            border-radius: 4px;
        }
        .alert-item {
            background: rgba(245, 158, 11, 0.05);
            border-left: 3px solid #f59e0b;
            color: #fbbf24;
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 8px;
            font-size: 0.875rem;
        }
        
        /* Debug panel */
        .debug-toggle {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--bg-surface);
            color: var(--text-secondary);
            border: 1px solid var(--border-color);
            border-radius: 50%;
            width: 44px;
            height: 44px;
            cursor: pointer;
            z-index: 1001;
            transition: all 0.2s;
        }
        .debug-toggle:hover {
            color: var(--text-primary);
            background: var(--bg-surface-hover);
        }
        .debug-panel {
            position: fixed;
            bottom: 70px;
            right: 20px;
            width: 450px;
            max-height: 400px;
            background: rgba(15, 17, 21, 0.95);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            font-family: monospace;
            font-size: 12px;
            z-index: 1000;
            display: none;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
        }
        .debug-logs {
            max-height: 320px;
            overflow-y: auto;
        }
        .log-entry { margin: 4px 0; }
        .log-timestamp { color: #6b7280; margin-right: 8px; }
        .log-level-ERROR { color: #ef4444; }
        .log-level-WARNING { color: #f59e0b; }
        .log-level-INFO { color: #60a5fa; }
    </style>
</head>
<body>
    <div class="container py-5">
        <header class="page-header">
            <div class="brand">✨ Piloto Financiero</div>
            <div class="version-badge">v<span id="version">{{ version }}</span></div>
        </header>

        <main class="row g-4">
            <div class="col-xl-8">
                <!-- Add Form -->
                <div class="glass-panel p-4 mb-4">
                    <form id="add-form" class="row g-3 align-items-end">
                        <div class="col-md-5">
                            <label class="form-label text-secondary small mb-1">Activo (Ticker o ISIN)</label>
                            <input type="text" id="ticker" class="form-control" placeholder="Ej. AAPL, ES0105065009" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label text-secondary small mb-1">Precio Objetivo</label>
                            <input type="number" step="0.01" id="target" class="form-control" placeholder="0.00" required>
                        </div>
                        <div class="col-md-3">
                            <button type="submit" class="btn btn-primary w-100" id="submit-btn">
                                Añadir Alerta
                            </button>
                        </div>
                    </form>
                </div>

                <!-- Table -->
                <div class="glass-panel overflow-hidden">
                    <div class="table-responsive">
                        <table class="table table-borderless align-middle">
                            <thead class="bg-dark bg-opacity-25">
                                <tr>
                                    <th class="ps-4">Activo</th>
                                    <th>Moneda</th>
                                    <th class="text-end">Actual</th>
                                    <th class="text-end">Objetivo</th>
                                    <th class="text-center">Estado</th>
                                    <th class="pe-4 text-end">Acciones</th>
                                </tr>
                            </thead>
                            <tbody id="monitors-table">
                                <tr><td colspan="6" class="text-center py-4 text-secondary"><div class="spinner-border spinner-border-sm"></div> Cargando...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-xl-4">
                <div class="glass-panel p-4 h-100">
                    <h5 class="mb-4 fs-6 text-uppercase text-secondary" style="letter-spacing: 0.05em">Actividad Reciente</h5>
                    <div id="alerts-feed" class="alerts-feed">
                        <div class="text-secondary small">Sin actividad reciente</div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Debug Toggle -->
    <button class="debug-toggle" onclick="toggleDebug()" title="Ver Logs del Sistema">
        <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 17l6-6-6-6M12 19h8"></path></svg>
    </button>

    <div class="debug-panel" id="debugPanel">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <span class="text-secondary small text-uppercase fw-bold">System Logs</span>
            <div>
                <button class="action-btn" onclick="clearLogs()" title="Limpiar">
                    <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
        </div>
        <div class="debug-logs" id="debugLogs"></div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const API = {
            async fetch(url, options = {}) {
                const res = await fetch(url, options);
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(data.error || 'Error de comunicación con el servidor');
                }
                return res.json();
            }
        };

        const UI = {
            version: '{{ version }}',
            debugEnabled: {{ debug_enabled|tojson }},
            
            showToast(message, type = 'success') {
                const container = document.querySelector('.toast-container');
                const id = 'toast-' + Date.now();
                const icon = type === 'success' ? '✓' : '⚠️';
                const bg = type === 'success' ? 'text-bg-success' : 'text-bg-danger';
                
                const toastHtml = `
                    <div id="${id}" class="toast align-items-center ${bg} border-0 mb-2 shadow" role="alert" aria-live="assertive" aria-atomic="true">
                        <div class="d-flex">
                            <div class="toast-body">
                                <strong>${icon}</strong> ${message}
                            </div>
                            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                        </div>
                    </div>
                `;
                container.insertAdjacentHTML('beforeend', toastHtml);
                const toastEl = document.getElementById(id);
                const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
                toast.show();
                toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
            },

            renderTable(monitores) {
                const entries = Object.entries(monitores);
                if (entries.length === 0) {
                    document.getElementById('monitors-table').innerHTML = '<tr><td colspan="6" class="text-center py-4 text-secondary">No hay alertas configuradas</td></tr>';
                    return;
                }

                const html = entries.map(([id, m]) => `
                    <tr>
                        <td class="ps-4">
                            <div class="fw-semibold text-white">${m.ticker}</div>
                            <div class="text-secondary" style="font-size: 0.75rem">${m.name || 'Desconocido'}</div>
                        </td>
                        <td><span class="badge bg-dark border border-secondary border-opacity-25">${m.currency || '-'}</span></td>
                        <td class="text-end font-monospace fs-6">${m.current ? m.current.toFixed(2) : '...'}</td>
                        <td class="text-end font-monospace fs-6 text-white">${m.target.toFixed(2)}</td>
                        <td class="text-center">
                            <span class="badge-status ${m.triggered ? 'badge-alert' : 'badge-active'}">
                                ${m.triggered ? 'ALERTA' : 'Vigilando'}
                            </span>
                        </td>
                        <td class="pe-4 text-end">
                            <button onclick="handleEdit('${id}', ${m.target})" class="action-btn me-1" title="Editar objetivo">
                                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                            </button>
                            <button onclick="handleDelete('${id}')" class="action-btn delete" title="Eliminar">
                                <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            </button>
                        </td>
                    </tr>
                `).join('');
                document.getElementById('monitors-table').innerHTML = html;
            },

            renderFeed(alertas) {
                if (alertas.length === 0) return;
                const html = alertas.map(a => `
                    <div class="alert-item d-flex flex-column">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="opacity-75 font-monospace" style="font-size:0.75rem">${a.time}</span>
                        </div>
                        <div>${a.msg}</div>
                    </div>
                `).join('');
                document.getElementById('alerts-feed').innerHTML = html;
            },

            checkVersion(newVersion) {
                if (this.version !== newVersion) {
                    this.version = newVersion;
                    document.getElementById('version').textContent = newVersion;
                    this.showToast(`Actualizado a v${newVersion}`, 'success');
                }
            }
        };

        // DOM Events
        document.getElementById('add-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submit-btn');
            const ticker = document.getElementById('ticker').value;
            const target = document.getElementById('target').value;
            
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
            
            try {
                await API.fetch('/api/add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ ticker, target })
                });
                document.getElementById('add-form').reset();
                UI.showToast('Alerta añadida correctamente');
                await syncData();
            } catch (err) {
                UI.showToast(err.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Añadir Alerta';
            }
        });

        window.handleDelete = async (id) => {
            if (!confirm('¿Seguro que deseas eliminar esta alerta?')) return;
            try {
                await API.fetch(`/api/delete/${id}`, { method: 'DELETE' });
                UI.showToast('Alerta eliminada');
                syncData();
            } catch (err) {
                UI.showToast('No se pudo eliminar', 'error');
            }
        };

        window.handleEdit = async (id, currentTarget) => {
            const newTarget = prompt("Introduce el nuevo precio objetivo:", currentTarget);
            if (newTarget === null || newTarget.trim() === "") return;
            
            const num = parseFloat(newTarget.replace(',', '.'));
            if (isNaN(num)) return UI.showToast('Formato de precio inválido', 'error');
            
            try {
                await API.fetch(`/api/edit/${id}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ target: num })
                });
                UI.showToast('Objetivo actualizado con éxito');
                syncData();
            } catch (err) {
                UI.showToast('No se pudo actualizar el objetivo', 'error');
            }
        };

        async function syncData() {
            try {
                const data = await API.fetch('/api/data');
                UI.checkVersion(data.version);
                UI.renderTable(data.monitores);
                UI.renderFeed(data.alertas);
                if (UI.debugEnabled) syncLogs();
            } catch (err) {
                console.error('Data sync failed:', err);
            }
        }

        async function syncLogs() {
            try {
                const data = await API.fetch('/api/logs');
                document.getElementById('debugLogs').innerHTML = data.logs.map(l => 
                    `<div class="log-entry font-monospace">
                        <span class="log-timestamp">${l.timestamp}</span>
                        <span class="log-level-${l.level}">[${l.level}]</span> 
                        <span class="text-light">${l.message}</span>
                    </div>`
                ).join('');
            } catch (err) {}
        }

        window.toggleDebug = () => {
            const panel = document.getElementById('debugPanel');
            const isHidden = panel.style.display === 'none' || panel.style.display === '';
            panel.style.display = isHidden ? 'block' : 'none';
            if (isHidden) syncLogs();
        };

        window.clearLogs = async () => {
            try {
                await API.fetch('/api/logs', { method: 'DELETE' });
                document.getElementById('debugLogs').innerHTML = '';
            } catch (e) {}
        };

        // Initialize
        syncData();
        setInterval(syncData, 10000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, version=VERSION, debug_enabled=DEBUG_LOG)

if __name__ == '__main__':
    log_debug(f"Starting Piloto Financiero v{VERSION} on port 5000")
    app.run(host='0.0.0.0', port=5000)