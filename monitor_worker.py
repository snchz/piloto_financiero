import json
import os
import threading
import time
import uuid
import queue
from flask import Response

import db
import finance_api
import notifications

VERSION_FILE = os.path.join(os.path.dirname(__file__), 'version.txt')

def load_version():
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return '1.0.0'

VERSION = load_version()

# --- SSE Management ---
class SSESubscriptions:
    def __init__(self):
        self.listeners = []
        self.lock = threading.Lock()

    def add_listener(self, q):
        with self.lock:
            self.listeners.append(q)

    def remove_listener(self, q):
        with self.lock:
            if q in self.listeners:
                self.listeners.remove(q)

    def notify(self):
        with self.lock:
            for q in self.listeners:
                q.put(True)

sse_subs = SSESubscriptions()

# --- Background Worker ---
def background_monitor():
    while True:
        cfg = db.get_config()
        interval = cfg.get("refresh_interval", 30) * 60
        
        try:
            with db.get_db() as conn:
                monitores = conn.execute("SELECT * FROM monitores").fetchall()  # Cambiado para incluir todos los monitores
            
            changes_made = False
            today_date = time.strftime('%Y-%m-%d')
            
            for m in monitores:
                try:
                    m_id = m['id']
                    sym = m['symbol']
                    
                    if not finance_api.is_market_open(sym):
                        log_debug(f"El mercado está cerrado para {sym}, omitiendo actualización.", "INFO")
                        continue
                        
                    current_price, previous_close = finance_api.fetch_price(sym)
                    current = round(current_price, 2)
                    
                    # Lógica de alertas de precio objetivo (existente)
                    is_above_target = m['tipo'] == 'superior' and current_price >= m['target']
                    is_below_target = m['tipo'] == 'inferior' and current_price <= m['target']
                    
                    # Lógica de alertas porcentuales (nueva)
                    pct_alert_triggered = False
                    if m['target_pct'] and m['target_pct'] > 0 and previous_close:
                        variacion_pct = ((current_price - previous_close) / previous_close) * 100
                        if abs(variacion_pct) >= m['target_pct']:
                            if m['pct_triggered_date'] != today_date:
                                pct_alert_triggered = True
                    
                    with db.get_db() as conn:
                        if is_above_target or is_below_target:
                            msg = f"🔔 {m['ticker']} alcanzó {m['target']} (Actual: {current_price:.2f})"
                            conn.execute("UPDATE monitores SET current = ?, triggered = 1 WHERE id = ?", (current, m_id))
                            conn.execute("INSERT INTO alertas (id, msg, time) VALUES (?, ?, ?)", 
                                         (str(uuid.uuid4()), msg, time.strftime('%H:%M:%S')))
                            conn.commit()
                            changes_made = True
                            
                            telegram_msg = f"🔔 *ALERTA DE MERCADO*\nEl activo *{m['ticker']}* ha alcanzado tu objetivo de *{m['target']}*.\nPrecio actual: *{current_price:.2f}*"
                            notifications.enviar_mensaje_telegram(telegram_msg)
                        
                        elif pct_alert_triggered and previous_close:
                            variacion_pct = ((current_price - previous_close) / previous_close) * 100
                            msg = f"📈 Volatilidad: {m['ticker']} se ha movido un {variacion_pct:.1f}% hoy"
                            conn.execute("UPDATE monitores SET pct_triggered_date = ? WHERE id = ?", (today_date, m_id))
                            conn.execute("INSERT INTO alertas (id, msg, time) VALUES (?, ?, ?)", 
                                         (str(uuid.uuid4()), msg, time.strftime('%H:%M:%S')))
                            conn.commit()
                            changes_made = True
                            
                            telegram_msg = f"📈 *ALERTA DE VOLATILIDAD*\nEl activo *{m['ticker']}* se ha movido un *{variacion_pct:.1f}%* hoy.\nPrecio anterior: *{previous_close:.2f}*\nPrecio actual: *{current_price:.2f}*"
                            notifications.enviar_mensaje_telegram(telegram_msg)
                        
                        elif m['current'] != current:
                            conn.execute("UPDATE monitores SET current = ?, previous_close = ? WHERE id = ?", (current, m['current'], m_id))
                            conn.commit()
                            changes_made = True
                except Exception as e:
                    log_debug(f"Monitor update failed for {m['ticker']}: {e}", "WARNING")
            
            if changes_made:
                sse_subs.notify()
                
        except Exception as e:
            log_debug(f"Background monitor loop error: {e}", "ERROR")
            
        time.sleep(interval)

# --- SSE Stream ---
def create_sse_stream():
    def event_stream():
        q = queue.Queue()
        sse_subs.add_listener(q)
        try:
            yield f"data: {json.dumps(get_all_data())}\n\n"
            while True:
                try:
                    q.get(timeout=30)
                    yield f"data: {json.dumps(get_all_data())}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        except GeneratorExit:
            sse_subs.remove_listener(q)
    return Response(event_stream(), mimetype="text/event-stream")

# --- Data Functions ---
def get_all_data():
    try:
        with db.get_db() as conn:
            monitores_rows = conn.execute("SELECT * FROM monitores").fetchall()
            alertas_rows = conn.execute("SELECT * FROM alertas ORDER BY timestamp DESC LIMIT 50").fetchall()
            
        monitores = {}
        for r in monitores_rows:
            monitores[r['id']] = {
                'ticker': r['ticker'],
                'symbol': r['symbol'],
                'name': r['name'],
                'currency': r['currency'],
                'target': r['target'],
                'current': r['current'],
                'tipo': r['tipo'],
                'triggered': bool(r['triggered']),
                'target_pct': r['target_pct'] or 0,
                'pct_triggered_date': r['pct_triggered_date'],
                'previous_close': r['previous_close']
            }
        
        alertas = [{'id': r['id'], 'msg': r['msg'], 'time': r['time']} for r in alertas_rows]
        
        return {
            "monitores": monitores,
            "alertas": alertas,
            "version": VERSION
        }
    except Exception as e:
        log_debug(f"Error fetching data from DB: {e}", "ERROR")
        return {"monitores": {}, "alertas": [], "version": VERSION}

# --- Logging ---
state = {"logs": []}

def log_debug(msg, level="INFO"):
    print(f"[{level}] {msg}")
    
    try:
        debug_enabled = db.get_config()['debug_ui']
    except Exception:
        debug_enabled = False
        
    if not debug_enabled:
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


def start_background_monitor():
    threading.Thread(target=background_monitor, daemon=True).start()