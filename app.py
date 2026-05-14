import json
import os
import time
import uuid
from datetime import datetime, timedelta
import traceback
import io
import pandas as pd

from flask import Flask, jsonify, render_template, request, send_file

import db
import finance_api
import notifications
import monitor_worker
import portfolio_math

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

# --- Cache ---
ASSET_INFO_CACHE = {}
EXCHANGE_RATES_CACHE = {}
HISTORICAL_RATES_CACHE = {}

def get_exchange_rate(from_currency, to_currency="EUR"):
    if not from_currency or from_currency.upper() == to_currency.upper() or from_currency == '-':
        return 1.0
    
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    if pair in EXCHANGE_RATES_CACHE:
        return EXCHANGE_RATES_CACHE[pair]
        
    try:
        price, _ = finance_api.fetch_price(pair)
        EXCHANGE_RATES_CACHE[pair] = price
        return price
    except Exception:
        return 1.0  # Fallback si no encuentra la divisa

def get_historical_exchange_rate(from_currency, date_str, to_currency="EUR"):
    if not from_currency or from_currency.upper() == to_currency.upper() or from_currency == '-':
        return 1.0
    
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    cache_key = f"{pair}_{date_str}"
    
    if cache_key in HISTORICAL_RATES_CACHE:
        return HISTORICAL_RATES_CACHE[cache_key]
        
    price = finance_api.fetch_historical_price(pair, date_str)
    if price:
        HISTORICAL_RATES_CACHE[cache_key] = price
        return price
        
    return get_exchange_rate(from_currency, to_currency)

def get_asset_info_cached(ticker):
    if ticker in ASSET_INFO_CACHE:
        return ASSET_INFO_CACHE[ticker]
    try:
        sym = finance_api.resolve_ticker(ticker)
        if sym:
            name, currency = finance_api.fetch_asset_info(sym)
            if not currency:
                currency = 'USD'
            ASSET_INFO_CACHE[ticker] = {'sym': sym, 'name': name, 'currency': currency}
            return ASSET_INFO_CACHE[ticker]
    except Exception as e:
        log_debug(f"Error fetching info for {ticker}: {e}", "WARNING")
    
    return {'sym': ticker, 'name': ticker, 'currency': 'USD'}

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
            conn.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('activity_retention_days', ?)", (str(data.get('activity_retention_days', 2)),))
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

# --- Operaciones API ---
@app.route('/api/operaciones', methods=['GET'])
def get_operaciones():
    try:
        with db.get_db() as conn:
            rows = conn.execute("SELECT * FROM operaciones ORDER BY fecha ASC").fetchall()
            operaciones = [dict(row) for row in rows]
            
        # Sanear todas las fechas extraídas de la base de datos
        for op in operaciones:
            fecha_val = str(op['fecha']).strip()
            if fecha_val.isdigit():
                try:
                    # Intentar convertir desde número de serie de Excel (común en importaciones)
                    excel_serial_date = int(fecha_val)
                    op['fecha'] = (datetime(1899, 12, 30) + timedelta(days=excel_serial_date)).strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    op['fecha'] = fecha_val.split(' ')[0] # Si falla, volver al comportamiento anterior
            else:
                op['fecha'] = fecha_val.split(' ')[0]
            
        # Agrupar por ticker
        activos = {}
        for op in operaciones:
            t = op['ticker']
            if t not in activos:
                activos[t] = []
            activos[t].append(op)
            
        # Calcular FIFO y métricas por activo
        cartera = {}
        flujos_caja = [] # Para TIR
        total_pnl_realizado = 0.0
        
        activos_info = {}
        
        for ticker, ops in activos.items():
            info = get_asset_info_cached(ticker)
            activos_info[ticker] = info
            
            # Obtener tipo de cambio a EUR (Divisa base de la cartera)
            currency = info.get('currency', 'EUR') or 'EUR'
            tasa_cambio_actual = get_exchange_rate(currency, 'EUR')
            
            # Inyectar tasa de cambio histórica a cada operación
            for op in ops:
                fecha_str = str(op['fecha']).strip().split(' ')[0]
                op['tasa_cambio'] = get_historical_exchange_rate(currency, fecha_str, 'EUR')

            resultado = portfolio_math.calcular_fifo(ops)
            total_pnl_realizado += resultado['beneficio_realizado_base']

            if resultado['cantidad_actual'] > 0:
                # Intentar obtener precio actual
                precio_actual = 0.0
                current_price_time = 'N/A'
                if info['sym']:
                    try:
                        precio_actual, _ = finance_api.fetch_price(info['sym'])
                        current_price_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    except Exception as e:
                        log_debug(f"Error fetching price for {info['sym']}: {e}", "WARNING")
                
                valor_actual = resultado['cantidad_actual'] * precio_actual
                inversion_actual = resultado['cantidad_actual'] * resultado['coste_medio']
                pnl_latente = valor_actual - inversion_actual
                
                coste_medio_base = resultado.get('coste_medio_base', resultado['coste_medio'] * tasa_cambio_actual)
                inversion_actual_base = resultado['cantidad_actual'] * coste_medio_base
                pnl_latente_base = (valor_actual * tasa_cambio_actual) - inversion_actual_base
                
                tasa_cambio_media = (inversion_actual_base / inversion_actual) if inversion_actual > 0 else tasa_cambio_actual
                pnl_activo_base = pnl_latente * tasa_cambio_actual
                pnl_divisa_base = inversion_actual * (tasa_cambio_actual - tasa_cambio_media)
                
                cartera[ticker] = {
                    'name': info['name'],
                    'currency': info['currency'],
                    'tasa_cambio': tasa_cambio_actual,
                    'cantidad': resultado['cantidad_actual'],
                    'coste_medio': resultado['coste_medio'],
                    'precio_actual': precio_actual,
                    'current_price_time': current_price_time,
                    'valor_actual': valor_actual,
                    'pnl_latente': pnl_latente,
                    'pnl_latente_base': pnl_latente_base,
                    'pnl_activo_base': pnl_activo_base,
                    'pnl_divisa_base': pnl_divisa_base,
                    'pnl_realizado': resultado['beneficio_realizado'],
                    'rentabilidad_pct': (pnl_latente / inversion_actual) if inversion_actual > 0 else 0
                }
                
                # Añadir al flujo de caja el valor actual (como si lo vendiéramos hoy)
                if valor_actual > 0:
                    flujos_caja.append((datetime.now(), valor_actual * tasa_cambio_actual))
                    
            for op in ops:
                fecha_str = str(op['fecha']).strip().split(' ')[0]
                try:
                    dt = datetime.strptime(fecha_str, '%Y-%m-%d')
                except ValueError:
                    dt = datetime.now()
                    
                cash_flow = 0.0
                if op['tipo'] in ('COMPRA', 'APORTACION'):
                    cash_flow = -(op['cantidad'] * op['precio'] + op.get('comisiones',0) + op.get('impuestos',0))
                elif op['tipo'] in ('VENTA', 'DIVIDENDO'):
                    cash_flow = (op['cantidad'] * op['precio']) - op.get('comisiones',0) - op.get('impuestos',0)
                if cash_flow != 0:
                    flujos_caja.append((dt, cash_flow * op['tasa_cambio']))
        
        tir = portfolio_math.xirr(flujos_caja) if flujos_caja else None
        
        return jsonify({
            "operaciones": operaciones,
            "cartera": cartera,
            "activos_info": activos_info,
            "tir_anualizada": tir,
            "total_pnl_realizado": total_pnl_realizado
        })
    except Exception as e:
        tb = traceback.format_exc()
        log_debug(f"Error en /api/operaciones: {e}\nTraceback:\n{tb}", "ERROR")
        return jsonify({"error": str(e)}), 500

@app.route('/api/operaciones/add', methods=['POST'])
def add_operacion():
    data = request.json
    try:
        op_id = str(uuid.uuid4())
        fecha = data.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        ticker = data.get('ticker', '').upper().strip()
        tipo = data.get('tipo', 'COMPRA').upper()
        cantidad = float(data.get('cantidad', 0))
        precio = float(data.get('precio', 0))
        comisiones = float(data.get('comisiones', 0))
        impuestos = float(data.get('impuestos', 0))
        
        if not ticker or cantidad <= 0 or precio < 0:
            return jsonify({"error": "Datos inválidos"}), 400
            
        with db.get_db() as conn:
            conn.execute('''
                INSERT INTO operaciones (id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (op_id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos))
            conn.commit()
            
        log_debug(f"Añadida operación {tipo} de {ticker}")
        return jsonify({"ok": True})
    except Exception as e:
        log_debug(f"Error añadiendo operación: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

@app.route('/api/operaciones/<op_id>', methods=['DELETE'])
def delete_operacion(op_id):
    try:
        with db.get_db() as conn:
            conn.execute("DELETE FROM operaciones WHERE id = ?", (op_id,))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/export/monitores', methods=['GET'])
def export_monitores():
    try:
        with db.get_db() as conn:
            rows = conn.execute("SELECT * FROM monitores").fetchall()
            df = pd.DataFrame([dict(row) for row in rows])
        
        csv_data = df.to_csv(index=False)
        output = io.BytesIO(csv_data.encode('utf-8'))
        
        return send_file(output, mimetype='text/csv', download_name="monitores.csv", as_attachment=True)
    except Exception as e:
        log_debug(f"Error exporting monitores: {e}", "ERROR")
        return jsonify({"error": str(e)}), 500

@app.route('/api/import/monitores', methods=['POST'])
def import_monitores():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    try:
        df = pd.read_csv(file)
        # Requerimos ciertas columnas básicas
        required_cols = ['ticker', 'target']
        if not all(col in df.columns for col in required_cols):
            return jsonify({"error": "CSV format invalid. Required columns: ticker, target"}), 400
        
        with db.get_db() as conn:
            for _, row in df.iterrows():
                ticker = str(row['ticker']).strip()
                target = float(row['target'])
                target_pct = float(row.get('target_pct', 0)) if pd.notna(row.get('target_pct')) else 0.0
                if not ticker or target <= 0:
                    continue
                
                sym = finance_api.resolve_ticker(ticker)
                if not sym:
                    continue
                
                current_price, previous_close = finance_api.fetch_price(sym)
                name, currency = finance_api.fetch_asset_info(sym)
                tipo = 'superior' if target > current_price else 'inferior'
                
                m_id = str(row.get('id', ''))
                if pd.isna(row.get('id')) or not m_id or m_id == 'nan' or m_id.strip() == '':
                    m_id = str(uuid.uuid4())
                
                conn.execute('''
                    INSERT OR REPLACE INTO monitores (id, ticker, symbol, name, currency, target, current, tipo, triggered, target_pct, previous_close, current_price_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                ''', (str(m_id), ticker, sym, name, currency, target, current_price, tipo, target_pct, current_price if not previous_close else previous_close, time.strftime('%d/%m/%Y %H:%M:%S')))
            conn.commit()
        monitor_worker.sse_subs.notify()
        return jsonify({"ok": True})
    except Exception as e:
        log_debug(f"Error importing monitores: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

@app.route('/api/export/operaciones', methods=['GET'])
def export_operaciones():
    try:
        with db.get_db() as conn:
            rows = conn.execute("SELECT * FROM operaciones ORDER BY fecha ASC").fetchall()
            df = pd.DataFrame([dict(row) for row in rows])
        
        if 'fecha' in df.columns:
            def format_date(x):
                if pd.isna(x): return ''
                x_str = str(x).strip()
                try:
                    return (datetime(1899, 12, 30) + timedelta(days=int(float(x_str)))).strftime('%Y-%m-%d')
                except ValueError:
                    return x_str.split(' ')[0]
            df['fecha'] = df['fecha'].apply(format_date)
            
        csv_data = df.to_csv(index=False)
        output = io.BytesIO(csv_data.encode('utf-8-sig'))
        
        return send_file(output, mimetype='text/csv', download_name="operaciones.csv", as_attachment=True)
    except Exception as e:
        log_debug(f"Error exporting operaciones: {e}", "ERROR")
        return jsonify({"error": str(e)}), 500

@app.route('/api/import/operaciones', methods=['POST'])
def import_operaciones():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    filename = file.filename.lower()
    
    try:
        # Procesamiento de archivos de Inversis (.xls html-based)
        if filename.endswith('.xls'):
            import importer
            temp_path = os.path.join(DATA_DIR, f"temp_import_{uuid.uuid4().hex}.xls")
            file.save(temp_path)
            try:
                res = importer.process_inversis_xls(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            # Avisar a UI de la recarga de cartera
            return jsonify(res)

        # Procesamiento de archivos CSV genéricos (lógica existente adaptada)
        df = pd.read_csv(file)
        required_cols = ['fecha', 'ticker', 'tipo', 'cantidad', 'precio']
        if not all(col in df.columns for col in required_cols):
            return jsonify({"error": "CSV format invalid. Required columns: fecha, ticker, tipo, cantidad, precio"}), 400
            
        with db.get_db() as conn:
            for _, row in df.iterrows():
                try:
                    op_id = str(row.get('id', ''))
                    if pd.isna(row.get('id')) or not op_id or op_id == 'nan' or op_id.strip() == '':
                        op_id = str(uuid.uuid4())
                    
                    # Formatear fecha
                    if pd.notna(row['fecha']):
                        fecha_val = str(row['fecha']).strip()
                        if isinstance(row['fecha'], datetime):
                            fecha = row['fecha'].strftime('%Y-%m-%d')
                        else:
                            try:
                                fecha = (datetime(1899, 12, 30) + timedelta(days=int(float(fecha_val)))).strftime('%Y-%m-%d')
                            except ValueError:
                                fecha = fecha_val.split(' ')[0]
                    else:
                        fecha = datetime.now().strftime('%Y-%m-%d')

                    ticker = str(row['ticker']).strip().upper()
                    tipo = str(row['tipo']).strip().upper()
                    cantidad = float(row['cantidad'])
                    precio = float(row['precio'])
                    comisiones = float(row.get('comisiones', 0)) if pd.notna(row.get('comisiones')) else 0.0
                    impuestos = float(row.get('impuestos', 0)) if pd.notna(row.get('impuestos')) else 0.0
                    external_id = str(row.get('external_id', '')).strip() if 'external_id' in df.columns and pd.notna(row['external_id']) else None
                    
                    if not ticker or cantidad <= 0 or precio < 0 or tipo not in ['COMPRA', 'VENTA', 'APORTACION', 'DIVIDENDO']:
                        continue
                        
                    conn.execute('''
                        INSERT OR REPLACE INTO operaciones (id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, external_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (op_id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, external_id))
                except Exception as row_e:
                    log_debug(f"Row import error: {row_e}", "WARNING")
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        log_debug(f"Error importing operaciones: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

# --- UI Template ---

@app.route('/')
def index():
    cfg = db.get_config()
    app_title = cfg.get("app_title", "Piloto Financiero")
    return render_template('index.html', version=VERSION, app_title=app_title)

if __name__ == '__main__':
    log_debug(f"Starting Piloto Financiero v{VERSION} on port 5000")
    # Notificar inicio por Telegramsud
    cfg = db.get_config()
    app_title = cfg.get("app_title", "Piloto Financiero").upper()
    startup_msg = f"🚀 *{app_title} INICIADO*\nVersión: *{VERSION}*\nFecha: *{time.strftime('%Y-%m-%d %H:%M:%S')}*\nEstado: *Listo para monitorear activos*"
    notifications.enviar_mensaje_telegram(startup_msg)
    app.run(host='0.0.0.0', port=5000, threaded=True)