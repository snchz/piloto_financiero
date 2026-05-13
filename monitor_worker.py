import json
import os
import threading
import time
import uuid
import queue
from flask import Response
from datetime import datetime

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
                    
                    if cfg.get("check_market_hours", True) and not finance_api.is_market_open(sym):
                        log_debug(f"El mercado está cerrado para {sym}, omitiendo actualización.", "INFO")
                        if not m['current_price_time']:
                            current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                            with db.get_db() as conn:
                                conn.execute("UPDATE monitores SET current_price_time = ? WHERE id = ?", (current_time, m_id))
                                conn.commit()
                            changes_made = True
                        continue
                        
                    current_price, previous_close = finance_api.fetch_price(sym)
                    current = round(current_price, 2)
                    current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    log_debug(f"Precio obtenido para {m['ticker']}: {current} @ {current_time}", "INFO")
                    
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
                            log_debug(f"Actualizando alerta objetivo para {m['ticker']} - timestamp: {current_time}", "INFO")
                            conn.execute("UPDATE monitores SET current = ?, triggered = 1, current_price_time = ? WHERE id = ?", (current, current_time, m_id))
                            conn.execute("INSERT INTO alertas (id, msg, time) VALUES (?, ?, ?)", 
                                         (str(uuid.uuid4()), msg, time.strftime('%H:%M:%S')))
                            conn.commit()
                            changes_made = True
                            
                            telegram_msg = f"🔔 *ALERTA DE MERCADO*\nEl activo *{m['ticker']}* ha alcanzado tu objetivo de *{m['target']}*.\nPrecio actual: *{current_price:.2f}*"
                            notifications.enviar_mensaje_telegram(telegram_msg)
                        
                        elif pct_alert_triggered and previous_close:
                            variacion_pct = ((current_price - previous_close) / previous_close) * 100
                            msg = f"📈 Volatilidad: {m['ticker']} se ha movido un {variacion_pct:.1f}% hoy"
                            log_debug(f"Actualizando alerta volatilidad para {m['ticker']} - timestamp: {current_time}", "INFO")
                            conn.execute("UPDATE monitores SET pct_triggered_date = ?, current = ?, current_price_time = ? WHERE id = ?", (today_date, current, current_time, m_id))
                            conn.execute("INSERT INTO alertas (id, msg, time) VALUES (?, ?, ?)", 
                                         (str(uuid.uuid4()), msg, time.strftime('%H:%M:%S')))
                            conn.commit()
                            changes_made = True
                            
                            telegram_msg = f"📈 *ALERTA DE VOLATILIDAD*\nEl activo *{m['ticker']}* se ha movido un *{variacion_pct:.1f}%* hoy.\nPrecio anterior: *{previous_close:.2f}*\nPrecio actual: *{current_price:.2f}*"
                            notifications.enviar_mensaje_telegram(telegram_msg)
                        
                        elif m['current'] != current or not m['current_price_time']:
                            log_debug(f"Actualizando precio para {m['ticker']}: {m['current']} -> {current}, timestamp: {current_time}", "INFO")
                            conn.execute("UPDATE monitores SET current = ?, previous_close = ?, current_price_time = ? WHERE id = ?", (current, m['current'], current_time, m_id))
                            conn.commit()
                            changes_made = True
                        else:
                            # El precio no ha cambiado, pero actualizamos la hora de última revisión
                            conn.execute("UPDATE monitores SET current_price_time = ? WHERE id = ?", (current_time, m_id))
                            conn.commit()
                            changes_made = True
                except Exception as e:
                    log_debug(f"Monitor update failed for {m['ticker']}: {e}", "WARNING")
            
            # Notificar siempre para actualizar "Última actualización" en la UI
            sse_subs.notify()
            
            # --- Cleanup and News Fetching ---
            try:
                retention_days = int(cfg.get("activity_retention_days", "2"))
                with db.get_db() as conn:
                    # Limpiar alertas antiguas
                    conn.execute("DELETE FROM alertas WHERE timestamp < datetime('now', '-{} days')".format(retention_days))
                    
                    # Obtener símbolos de la cartera (operaciones) y monitores
                    symbols_to_check = set()
                    for m in monitores:
                        if m['symbol']: symbols_to_check.add((m['ticker'], m['symbol']))
                        
                    ops = conn.execute("SELECT ticker FROM operaciones").fetchall()
                    for op in ops:
                        t = op['ticker']
                        sym = finance_api.resolve_ticker(t)
                        if sym: symbols_to_check.add((t, sym))
                        
                    # Fetch news and insert as alerts if not present
                    for ticker, sym in symbols_to_check:
                        news = finance_api.fetch_news(sym, limit=2)
                        for n in news:
                            title = n['title']
                            publisher = n['publisher']
                            msg = f"📰 Noticia {ticker}: {title} ({publisher})"
                            
                            # Comprobar si ya existe
                            exists = conn.execute("SELECT 1 FROM alertas WHERE msg = ?", (msg,)).fetchone()
                            if not exists:
                                conn.execute("INSERT INTO alertas (id, msg, time) VALUES (?, ?, ?)", 
                                             (str(uuid.uuid4()), msg, time.strftime('%H:%M:%S')))
                                changes_made = True
                    conn.commit()
                    
                if changes_made:
                    sse_subs.notify()
            except Exception as e:
                log_debug(f"Cleanup or news fetch error: {e}", "ERROR")

                
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
            price_time = r['current_price_time'] or 'N/A'
            if price_time == 'N/A':
                log_debug(f"Monitor {r['ticker']} (ID: {r['id']}) sin timestamp - valor NULL en BD", "WARNING")
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
                'previous_close': r['previous_close'],
                'current_price_time': price_time
            }
        
        def format_ts(ts, fallback_time):
            if not ts: return fallback_time
            try:
                dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                return dt.strftime('%d/%m/%Y %H:%M:%S')
            except:
                return fallback_time

        alertas = [{'id': r['id'], 'msg': r['msg'], 'time': format_ts(r['timestamp'], r['time'])} for r in alertas_rows]
        
        data = {
            "monitores": monitores,
            "alertas": alertas,
            "version": VERSION
        }
        log_debug(f"Enviando datos SSE con {len(monitores)} monitores", "INFO")
        if monitores:
            first_ticker = list(monitores.values())[0]['ticker']
            first_time = list(monitores.values())[0]['current_price_time']
            log_debug(f"Primer monitor: {first_ticker} con timestamp: {first_time}", "INFO")
        
        return data
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