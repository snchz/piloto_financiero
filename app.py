import json
import os
import time
import uuid

from flask import Flask, jsonify, render_template, request

import db
import finance_api
import notifications
import monitor_worker

app = Flask(__name__)

# --- Configuration & Setup ---

DATA_DIR = 'data'
DATA_FILE = os.path.join(DATA_DIR, 'monitores.json')
DB_FILE = os.path.join(DATA_DIR, 'piloto.db')
VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version.txt')

# --- Initialization ---
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

db.init_db()

def load_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "1.0.0"

VERSION = load_version()

# --- Logging ---
def log_debug(msg, level="INFO"):
    monitor_worker.log_debug(msg, level)

# --- Data Management ---
def migrate_json_to_sqlite():
    if not os.path.exists(DATA_FILE):
        return
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        with db.get_db() as conn:
            if conn.execute("SELECT COUNT(*) FROM monitores").fetchone()[0] == 0:
                monitores = data.get('monitores', {})
                for m_id, m in monitores.items():
                    conn.execute('''
                        INSERT INTO monitores (id, ticker, symbol, name, currency, target, current, tipo, triggered)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (m_id, m.get('ticker'), m.get('symbol'), m.get('name'), m.get('currency'), 
                          m.get('target'), m.get('current'), m.get('tipo'), 1 if m.get('triggered') else 0))
                
                alertas = data.get('alertas', [])
                for a in reversed(alertas):
                    conn.execute('''
                        INSERT INTO alertas (id, msg, time) VALUES (?, ?, ?)
                    ''', (a.get('id', str(uuid.uuid4())), a.get('msg'), a.get('time')))
                conn.commit()
                
        os.rename(DATA_FILE, DATA_FILE + '.bak')
        log_debug("Migrated data from JSON to SQLite")
    except Exception as e:
        log_debug(f"Migration failed: {e}", "ERROR")

migrate_json_to_sqlite()
monitor_worker.start_background_monitor()

# --- API Endpoints ---
@app.route('/api/stream')
def stream():
    return monitor_worker.create_sse_stream()

@app.route('/api/data')
def get_data():
    return jsonify(monitor_worker.get_all_data())

@app.route('/api/config', methods=['GET'])
def api_get_config():
    return jsonify(db.get_config())

@app.route('/api/config', methods=['POST'])
def api_set_config():
    data = request.json
    try:
        with db.get_db() as conn:
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'telegram_token'", (data.get('telegram_token', ''),))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'telegram_chat_id'", (data.get('telegram_chat_id', ''),))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'refresh_interval'", (str(data.get('refresh_interval', 30)),))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'check_market_hours'", ("1" if data.get('check_market_hours') else "0",))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'debug_ui'", ("1" if data.get('debug_ui') else "0",))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'app_title'", (data.get('app_title', 'Piloto Financiero'),))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/add', methods=['POST'])
def add_monitor():
    data = request.json
    raw_input = data.get('ticker', '').upper().strip()
    target = float(data.get('target', 0))
    target_pct = float(data.get('target_pct', 0) or 0)
    
    if not raw_input or target <= 0:
        return jsonify({"error": "Parámetros inválidos"}), 400
        
    try:
        sym = finance_api.resolve_ticker(raw_input)
        if not sym:
            raise ValueError(f"No se encontró el activo para {raw_input}")
            
        current_price, previous_close = finance_api.fetch_price(sym)
        name, currency = finance_api.fetch_asset_info(sym)
        
        m_id = str(uuid.uuid4())
        ticker_display = f"{raw_input} ({sym})" if raw_input != sym else raw_input
        current = round(current_price, 2)
        tipo = 'superior' if target > current_price else 'inferior'
        
        with db.get_db() as conn:
            conn.execute('''
                INSERT INTO monitores (id, ticker, symbol, name, currency, target, current, tipo, triggered, target_pct, previous_close, current_price_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            ''', (m_id, ticker_display, sym, name, currency, target, current, tipo, target_pct, current_price if not previous_close else previous_close, time.strftime('%d/%m/%Y %H:%M:%S')))
            conn.commit()
            
        log_debug(f"Added monitor for {sym} at {target} with pct alert {target_pct}%")
        monitor_worker.sse_subs.notify()
        return jsonify({"ok": True})
        
    except Exception as e:
        log_debug(f"Add monitor failed: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

@app.route('/api/edit/<m_id>', methods=['PUT'])
def edit_monitor(m_id):
    try:
        target = float(request.json.get('target'))
        target_pct = float(request.json.get('target_pct', 0) or 0)
        with db.get_db() as conn:
            m = conn.execute("SELECT current FROM monitores WHERE id = ?", (m_id,)).fetchone()
            if not m:
                return jsonify({"error": "No encontrado"}), 404
                
            tipo = 'superior' if target > (m['current'] or 0) else 'inferior'
            conn.execute('''
                UPDATE monitores SET target = ?, tipo = ?, triggered = 0, target_pct = ? WHERE id = ?
            ''', (target, tipo, target_pct, m_id))
            conn.commit()
            
        monitor_worker.sse_subs.notify()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/delete/<m_id>', methods=['DELETE'])
def delete_monitor(m_id):
    with db.get_db() as conn:
        conn.execute("DELETE FROM monitores WHERE id = ?", (m_id,))
        conn.commit()
    monitor_worker.sse_subs.notify()
    return jsonify({"ok": True})

@app.route('/api/logs', methods=['GET', 'DELETE'])
def handle_logs():
    if request.method == 'DELETE':
        monitor_worker.state["logs"].clear()
        return jsonify({"ok": True})
    return jsonify({"logs": monitor_worker.state["logs"]})

@app.route('/health')
def health_check():
    try:
        with db.get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        return jsonify({"status": "healthy"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# --- UI Template ---

@app.route('/')
def index():
    cfg = db.get_config()
    app_title = cfg.get("app_title", "Piloto Financiero")
    return render_template('index.html', version=VERSION, app_title=app_title)

if __name__ == '__main__':
    log_debug(f"Starting Piloto Financiero v{VERSION} on port 5000")
    # Notificar inicio por Telegram
    cfg = db.get_config()
    app_title = cfg.get("app_title", "Piloto Financiero").upper()
    startup_msg = f"🚀 *{app_title} INICIADO*\nVersión: *{VERSION}*\nFecha: *{time.strftime('%Y-%m-%d %H:%M:%S')}*\nEstado: *Listo para monitorear activos*"
    notifications.enviar_mensaje_telegram(startup_msg)
    app.run(host='0.0.0.0', port=5000, threaded=True)