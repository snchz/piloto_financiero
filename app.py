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
import ine_api

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
HISTORICAL_PRICES_CACHE = {}

def get_exchange_rate(from_currency, to_currency="EUR"):
    if not from_currency or from_currency.upper() == to_currency.upper() or from_currency == '-':
        return 1.0
    
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    
    cfg = db.get_config()
    ttl_hours = cfg.get("exchange_rate_ttl_hours", 12)
    ttl_seconds = ttl_hours * 3600

    if pair in EXCHANGE_RATES_CACHE:
        cached_data = EXCHANGE_RATES_CACHE[pair]
        if time.time() - cached_data['timestamp'] < ttl_seconds:
            return cached_data['price']
            
    db_cached = db.get_cached_rate(pair)
    if db_cached:
        if time.time() - db_cached['timestamp'] < ttl_seconds:
            EXCHANGE_RATES_CACHE[pair] = db_cached
            return db_cached['price']
        
    try:
        price, _ = finance_api.fetch_price(pair)
        db.set_cached_rate(pair, price)
        EXCHANGE_RATES_CACHE[pair] = {'price': price, 'timestamp': time.time()}
        return price
    except Exception:
        if db_cached:
            return db_cached['price']
        if pair in EXCHANGE_RATES_CACHE:
            return EXCHANGE_RATES_CACHE[pair]['price']
        return 1.0  # Fallback si no encuentra la divisa

def get_historical_exchange_rate(from_currency, date_str, to_currency="EUR"):
    if not from_currency or from_currency.upper() == to_currency.upper() or from_currency == '-':
        return 1.0
    
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    cache_key = f"{pair}_{date_str}"
    
    if cache_key in HISTORICAL_RATES_CACHE:
        return HISTORICAL_RATES_CACHE[cache_key]
        
    db_price = db.get_cached_historical_rate(cache_key)
    if db_price is not None:
        HISTORICAL_RATES_CACHE[cache_key] = db_price
        return db_price
        
    price = finance_api.fetch_historical_price(pair, date_str)
    if price:
        db.set_cached_historical_rate(cache_key, price)
        if len(HISTORICAL_RATES_CACHE) >= 1000:
            try:
                HISTORICAL_RATES_CACHE.pop(next(iter(HISTORICAL_RATES_CACHE)))
            except (StopIteration, KeyError):
                pass
        HISTORICAL_RATES_CACHE[cache_key] = price
        return price
        
    return get_exchange_rate(from_currency, to_currency)

def get_asset_info_cached(ticker):
    try:
        with db.get_db() as conn:
            row_inm = conn.execute("SELECT name, tipo, comunidad_autonoma, pct_titularidad, precio_compra_total, hipoteca_inicial FROM monitores WHERE ticker = ?", (ticker,)).fetchone()
            if row_inm and row_inm['tipo'] == 'INMUEBLE':
                info_inm = {
                    'sym': None,
                    'name': row_inm['name'] or ticker,
                    'currency': 'EUR',
                    'tipo': 'INMUEBLE',
                    'comunidad_autonoma': row_inm['comunidad_autonoma'] or 'NACIONAL',
                    'pct_titularidad': float(row_inm['pct_titularidad'] or 1.0),
                    'precio_compra_total': float(row_inm['precio_compra_total'] or 0.0),
                    'hipoteca_inicial': float(row_inm['hipoteca_inicial'] or 0.0)
                }
                ASSET_INFO_CACHE[ticker] = info_inm
                return info_inm
            row = conn.execute("SELECT DISTINCT moneda FROM operaciones WHERE ticker = ? AND moneda IS NOT NULL AND moneda != ''", (ticker,)).fetchone()
            if row:
                pref_currency = row['moneda']
    except Exception:
        pass

    if ticker in ASSET_INFO_CACHE:
        cached_info = ASSET_INFO_CACHE[ticker]
        if not pref_currency or cached_info.get('currency') == pref_currency:
            return cached_info
        
    cached = db.get_cached_asset(ticker)
    if cached:
        if not pref_currency or cached['currency'] == pref_currency:
            if time.time() - cached['timestamp'] < 7 * 86400:
                res = {'sym': cached['sym'], 'name': cached['name'], 'currency': cached['currency']}
                ASSET_INFO_CACHE[ticker] = res
                return res
            
    try:
        sym = finance_api.resolve_ticker(ticker)
        if sym:
            name, currency = finance_api.fetch_asset_info(sym, isin=ticker)
            if pref_currency and currency != pref_currency:
                better_sym = finance_api.find_symbol_by_name_and_currency(name or ticker, pref_currency)
                if better_sym:
                    better_name, better_currency = finance_api.fetch_asset_info(better_sym, isin=ticker)
                    if better_currency == pref_currency:
                        sym = better_sym
                        name = better_name or name
                        currency = better_currency

            if not currency:
                currency = 'EUR'
            db.set_cached_asset(ticker, sym, name, currency)
            ASSET_INFO_CACHE[ticker] = {'sym': sym, 'name': name, 'currency': currency}
            return ASSET_INFO_CACHE[ticker]
    except Exception as e:
        log_debug(f"Error fetching info for {ticker}: {e}", "WARNING")
        
    if cached:
        res = {'sym': cached['sym'], 'name': cached['name'], 'currency': cached['currency']}
        ASSET_INFO_CACHE[ticker] = res
        return res
    
    return {'sym': ticker, 'name': ticker, 'currency': 'EUR'}

def normalize_date(date_input):
    """Convierte cualquier formato de fecha a 'YYYY-MM-DD'."""
    if pd.isna(date_input) or date_input is None or str(date_input).strip() == '':
        return datetime.now().strftime('%Y-%m-%d')

    if isinstance(date_input, datetime):
        return date_input.strftime('%Y-%m-%d')

    date_str = str(date_input).strip()

    try:
        # Verificar si es un número (ej. fecha serial de Excel)
        if date_str.replace('.', '', 1).isdigit():
            excel_val = float(date_str)
            if excel_val > 10000:
                return (datetime(1899, 12, 30) + timedelta(days=int(excel_val))).strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        pass

    return date_str.split(' ')[0].split('T')[0]

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
    data = request.json or {}
    try:
        with db.get_db() as conn:
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'telegram_token'", (data.get('telegram_token', ''),))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'telegram_chat_id'", (data.get('telegram_chat_id', ''),))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'refresh_interval'", (str(data.get('refresh_interval', 30)),))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'check_market_hours'", ("1" if data.get('check_market_hours') else "0",))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'debug_ui'", ("1" if data.get('debug_ui') else "0",))
            conn.execute("UPDATE config SET valor = ? WHERE clave = 'app_title'", (data.get('app_title', 'Piloto Financiero'),))
            conn.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('activity_retention_days', ?)", (str(data.get('activity_retention_days', 2)),))
            conn.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('exchange_rate_ttl_hours', ?)", (str(data.get('exchange_rate_ttl_hours', 12)),))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/add', methods=['POST'])
def add_monitor():
    data = request.json or {}
    raw_input = (data.get('ticker') or '').upper().strip()
    target = float(data.get('target') or 0)
    target_pct = float(data.get('target_pct') or 0)
    tipo_activo = (data.get('tipo_activo') or '').upper().strip()
    
    if not raw_input:
        return jsonify({"error": "Parámetros inválidos"}), 400

    if tipo_activo == 'INMUEBLE':
        try:
            m_id = str(uuid.uuid4())
            name_input = data.get('name') or raw_input
            comunidad = (data.get('comunidad_autonoma') or 'NACIONAL').upper().strip()
            pct_tit = float(data.get('pct_titularidad') or 1.0)
            precio_total = float(data.get('precio_compra_total') or 0.0)
            hipoteca_ini = float(data.get('hipoteca_inicial') or 0.0)

            with db.get_db() as conn:
                conn.execute('''
                    INSERT INTO monitores (id, ticker, symbol, name, currency, target, current, tipo, triggered, target_pct, comunidad_autonoma, pct_titularidad, precio_compra_total, hipoteca_inicial)
                    VALUES (?, ?, NULL, ?, 'EUR', 0, 0, 'INMUEBLE', 0, 0, ?, ?, ?, ?)
                ''', (m_id, raw_input, name_input, comunidad, pct_tit, precio_total, hipoteca_ini))
                conn.commit()

            log_debug(f"Añadido inmueble {raw_input} en {comunidad}")
            monitor_worker.sse_subs.notify()
            return jsonify({"ok": True})
        except Exception as e:
            log_debug(f"Error añadiendo inmueble: {e}", "ERROR")
            return jsonify({"error": str(e)}), 400
        
    if target <= 0:
        return jsonify({"error": "Parámetros inválidos"}), 400
        
    try:
        sym = finance_api.resolve_ticker(raw_input)
        if not sym:
            raise ValueError(f"No se encontró el activo para {raw_input}")
            
        current_price, previous_close = finance_api.fetch_price(sym)
        name, currency = finance_api.fetch_asset_info(sym, isin=raw_input)
        
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
        data = request.json or {}
        target = float(data.get('target') or 0)
        target_pct = float(data.get('target_pct') or 0)
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

@app.route('/api/alertas', methods=['DELETE'])
def clear_alertas():
    try:
        with db.get_db() as conn:
            conn.execute("DELETE FROM alertas")
            conn.commit()
        # Notificamos a los clientes SSE para que la UI se actualice al instante
        monitor_worker.sse_subs.notify()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/info/<ticker>', methods=['GET'])
def get_info(ticker):
    try:
        info = get_asset_info_cached(ticker.upper().strip())
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Operaciones API ---
@app.route('/api/operaciones', methods=['GET'])
def get_operaciones():
    try:
        include_real_estate = request.args.get('include_real_estate', '1') == '1'

        with db.get_db() as conn:
            rows = conn.execute("SELECT * FROM operaciones ORDER BY fecha ASC").fetchall()
            operaciones = [dict(row) for row in rows]
            
        # Sanear todas las fechas extraídas de la base de datos
        for op in operaciones:
            op['fecha'] = normalize_date(op['fecha'])

        if not include_real_estate:
            # Filtrar operaciones de activos tipo INMUEBLE
            operaciones_filtradas = []
            for op in operaciones:
                info_t = get_asset_info_cached(op['ticker'])
                if info_t.get('tipo') != 'INMUEBLE':
                    operaciones_filtradas.append(op)
            operaciones = operaciones_filtradas
            
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
        flujos_caja_dict = {} # Para simulación de benchmark
        
        activos_info = {}
        warning_api_error = False
        
        for ticker, ops in activos.items():
            info = get_asset_info_cached(ticker)
            activos_info[ticker] = info
            
            if not include_real_estate and info.get('tipo') == 'INMUEBLE':
                continue

            # Obtener tipo de cambio a EUR (Divisa base de la cartera)
            currency = info.get('currency', 'EUR') or 'EUR'
            tasa_cambio_actual = get_exchange_rate(currency, 'EUR')
            
            # Inyectar tasa de cambio histórica a cada operación
            for op in ops:
                if op.get('tasa_cambio') is not None:
                    op['tasa_cambio'] = float(op['tasa_cambio'])
                else:
                    fecha_str = str(op['fecha']).strip().split(' ')[0]
                    op_currency = op.get('moneda') or currency
                    op['tasa_cambio'] = get_historical_exchange_rate(op_currency, fecha_str, 'EUR')

            resultado = portfolio_math.calcular_fifo(ops)
            total_pnl_realizado += resultado['beneficio_realizado_base']

            if resultado['cantidad_actual'] > 0:
                if info.get('tipo') == 'INMUEBLE':
                    fecha_primera_op = sorted(ops, key=lambda x: str(x['fecha']))[0]['fecha']
                    comunidad = info.get('comunidad_autonoma', 'NACIONAL')
                    rev_factor = ine_api.calculate_ine_revalorization(comunidad, str(fecha_primera_op))
                    
                    pct_tit = info.get('pct_titularidad', 1.0)
                    precio_compra_total = info.get('precio_compra_total', 0.0)
                    valor_bruto = (precio_compra_total * pct_tit) * rev_factor if precio_compra_total > 0 else (resultado['coste_medio'] * rev_factor)
                    
                    total_amortizado = sum(float(op.get('amortizacion', 0) or (float(op['precio']) - float(op.get('comisiones', 0)))) for op in ops if op['tipo'] == 'HIPOTECA_CUOTA')
                    deuda_pendiente = max(info.get('hipoteca_inicial', 0.0) - total_amortizado, 0.0)
                    valor_neto = max(valor_bruto - deuda_pendiente, 0.0)
                    
                    precio_actual = valor_neto / resultado['cantidad_actual'] if resultado['cantidad_actual'] > 0 else valor_neto
                    valor_actual = valor_neto
                    inversion_actual = resultado['cantidad_actual'] * resultado['coste_medio']
                    pnl_latente = valor_actual - inversion_actual
                    
                    cartera[ticker] = {
                        'name': info['name'],
                        'currency': 'EUR',
                        'tipo': 'INMUEBLE',
                        'tasa_cambio': 1.0,
                        'cantidad': resultado['cantidad_actual'],
                        'coste_medio': resultado['coste_medio'],
                        'precio_actual': precio_actual,
                        'previous_close': None,
                        'current_price_time': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                        'valor_actual': valor_actual,
                        'valor_bruto': valor_bruto,
                        'deuda_pendiente': deuda_pendiente,
                        'comunidad_autonoma': comunidad,
                        'pnl_latente': pnl_latente,
                        'pnl_latente_base': pnl_latente,
                        'pnl_activo_base': pnl_latente,
                        'pnl_divisa_base': 0.0,
                        'pnl_realizado': resultado['beneficio_realizado'],
                        'rentabilidad_pct': (pnl_latente / inversion_actual) if inversion_actual > 0 else 0
                    }
                    if valor_actual > 0:
                        flujos_caja.append((datetime.now(), valor_actual))
                else:
                    # Intentar obtener precio actual para activos financieros
                    precio_actual = 0.0
                    current_price_time = 'N/A'
                    prev_close = None
                    if info['sym']:
                        try:
                            precio_actual, prev_close = finance_api.fetch_price(info['sym'])
                            current_price_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                        except Exception as e:
                            warning_api_error = True
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
                        'previous_close': prev_close,
                        'current_price_time': current_price_time,
                        'valor_actual': valor_actual,
                        'pnl_latente': pnl_latente,
                        'pnl_latente_base': pnl_latente_base,
                        'pnl_activo_base': pnl_activo_base,
                        'pnl_divisa_base': pnl_divisa_base,
                        'pnl_realizado': resultado['beneficio_realizado'],
                        'rentabilidad_pct': (pnl_latente / inversion_actual) if inversion_actual > 0 else 0
                    }
                    
                    if valor_actual > 0:
                        flujos_caja.append((datetime.now(), valor_actual * tasa_cambio_actual))
                    
            for op in ops:
                fecha_str = str(op['fecha']).strip().split(' ')[0]
                try:
                    dt = datetime.strptime(fecha_str, '%Y-%m-%d')
                except ValueError:
                    dt = datetime.now()
                    
                cash_flow = 0.0
                if op['tipo'] in ('COMPRA', 'APORTACION', 'ENTRADA_INMUEBLE', 'REFORMA_MEJORA'):
                    cash_flow = -(op['cantidad'] * op['precio'] + op.get('comisiones',0) + op.get('impuestos',0))
                elif op['tipo'] == 'HIPOTECA_CUOTA':
                    amort = float(op.get('amortizacion', 0) or (op['precio'] - op.get('comisiones',0)))
                    cash_flow = -(amort + op.get('comisiones',0) + op.get('impuestos',0))
                elif op['tipo'] in ('VENTA', 'DIVIDENDO'):
                    cash_flow = (op['cantidad'] * op['precio']) - op.get('comisiones',0) - op.get('impuestos',0)
                if cash_flow != 0:
                    flujo_base = cash_flow * op['tasa_cambio']
                    flujos_caja.append((dt, flujo_base))

                    fecha_key = dt.date()
                    flujos_caja_dict[fecha_key] = flujos_caja_dict.get(fecha_key, 0.0) - flujo_base
        
        tir = portfolio_math.xirr(flujos_caja) if flujos_caja else None
        
        # --- Generar Historial ---
        history = {"labels": [], "capital": [], "values": []}
        if operaciones:
            import yfinance as yf
            
            fechas_ops = [datetime.strptime(str(op['fecha']).split(' ')[0], '%Y-%m-%d') for op in operaciones]
            start_date = min(fechas_ops)
            end_date = datetime.now()
            
            historicos_precios = {}
            for ticker, info in activos_info.items():
                if not include_real_estate and info.get('tipo') == 'INMUEBLE':
                    continue
                    
                if info.get('tipo') == 'INMUEBLE':
                    ops_inm = activos.get(ticker, [])
                    fecha_ini_str = str(start_date)[:10]
                    rango_dias = pd.date_range(start=start_date, end=end_date, freq='B')
                    series_inm = []
                    pct_tit = info.get('pct_titularidad', 1.0)
                    precio_compra_total = info.get('precio_compra_total', 0.0)
                    comunidad = info.get('comunidad_autonoma', 'NACIONAL')
                    coste_m = cartera.get(ticker, {}).get('coste_medio', 0.0)
                    
                    for d in rango_dias:
                        d_str = d.strftime('%Y-%m-%d')
                        rev_d = ine_api.calculate_ine_revalorization(comunidad, fecha_ini_str, d_str)
                        v_bruto_d = (precio_compra_total * pct_tit) * rev_d if precio_compra_total > 0 else (coste_m * rev_d)
                        amort_hasta_d = sum(float(op.get('amortizacion', 0) or (float(op['precio']) - float(op.get('comisiones', 0)))) for op in ops_inm if op['tipo'] == 'HIPOTECA_CUOTA' and str(op['fecha'])[:10] <= d_str)
                        deuda_d = max(info.get('hipoteca_inicial', 0.0) - amort_hasta_d, 0.0)
                        series_inm.append(max(v_bruto_d - deuda_d, 0.0))
                    historicos_precios[ticker] = pd.Series(series_inm, index=rango_dias)
                else:
                    sym = info.get('sym')
                    if sym:
                        info['tasa_cambio_actual'] = get_exchange_rate(info.get('currency', 'EUR'), 'EUR')
                        
                        cached_series = db.get_cached_historical_prices(sym, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                        needs_download = True
                        if cached_series is not None and not cached_series.empty:
                            last_cached_date = cached_series.index[-1].date()
                            if last_cached_date >= (end_date - timedelta(days=2)).date():
                                needs_download = False
                                HISTORICAL_PRICES_CACHE[sym] = {
                                    'data': cached_series,
                                    'start_date': cached_series.index[0].date(),
                                    'end_date': last_cached_date
                                }
                        
                        if needs_download:
                            try:
                                df = yf.Ticker(sym).history(start=start_date.strftime('%Y-%m-%d'))
                                if not df.empty:
                                    df.index = df.index.tz_localize(None).normalize()
                                    db.save_historical_prices(sym, df['Close'])
                                    cached_series = db.get_cached_historical_prices(sym, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                                    HISTORICAL_PRICES_CACHE[sym] = {
                                        'data': cached_series,
                                        'start_date': start_date.date(),
                                        'end_date': end_date.date()
                                    }
                                else:
                                    if cached_series is not None:
                                        HISTORICAL_PRICES_CACHE[sym] = {
                                            'data': cached_series,
                                            'start_date': start_date.date(),
                                            'end_date': end_date.date()
                                        }
                                    else:
                                        HISTORICAL_PRICES_CACHE[sym] = {
                                            'data': pd.Series(dtype=float),
                                            'start_date': start_date.date(),
                                            'end_date': end_date.date()
                                        }
                            except Exception as e:
                                log_debug(f"Error fetching historical data for {sym}: {e}", "WARNING")
                                if sym not in HISTORICAL_PRICES_CACHE:
                                    HISTORICAL_PRICES_CACHE[sym] = {
                                        'data': cached_series if cached_series is not None else pd.Series(dtype=float),
                                        'start_date': start_date.date(),
                                        'end_date': end_date.date()
                                    }
                        
                        historicos_precios[sym] = HISTORICAL_PRICES_CACHE[sym]['data']
            
            history = portfolio_math.calcular_historico_cartera(operaciones, historicos_precios, activos_info, start_date, end_date)

            # Calcular Max/Min desde la primera compra
            for ticker, c_data in cartera.items():
                info = activos_info.get(ticker, {})
                sym = info.get('sym')
                if sym and sym in historicos_precios and not historicos_precios[sym].empty:
                    ops_ticker = activos[ticker]
                    compras = [op for op in ops_ticker if op['tipo'] in ('COMPRA', 'APORTACION')]
                    if compras:
                        fecha_primera_compra = min([datetime.strptime(str(op['fecha']).split(' ')[0], '%Y-%m-%d') for op in compras])
                        serie = historicos_precios[sym]
                        serie_desde_compra = serie[serie.index >= pd.Timestamp(fecha_primera_compra.date())]
                        
                        precios_reales = [op['precio'] for op in compras] + [c_data['precio_actual']]
                        candidatos_max = precios_reales.copy()
                        candidatos_min = precios_reales.copy()
                        
                        if not serie_desde_compra.empty:
                            max_hist = serie_desde_compra.max()
                            min_hist = serie_desde_compra.min()
                            if pd.notna(max_hist): candidatos_max.append(float(max_hist))
                            if pd.notna(min_hist): candidatos_min.append(float(min_hist))
                            
                        c_data['max_price'] = max(candidatos_max)
                        c_data['min_price'] = min(candidatos_min)
                else:
                    c_data['max_price'] = c_data['precio_actual']
                    c_data['min_price'] = c_data['precio_actual']

            # --- Simular Benchmark ---
            metricas_riesgo = {"volatilidad": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "twr": 0.0}
            if history and history.get("labels"):
                benchmark_values = portfolio_math.simular_benchmark_cartera(
                    fechas=history["labels"],
                    flujos_caja=flujos_caja_dict,
                    ticker="VWCE.DE",
                    cache=HISTORICAL_PRICES_CACHE
                )
                history["benchmark_values"] = benchmark_values
                metricas_riesgo = portfolio_math.calcular_metricas_avanzadas(history)
        else:
            dt_now = datetime.now()
            history = {
                "labels": [dt_now.strftime('%Y-%m-%d')],
                "capital": [0],
                "values": [0]
            }
            metricas_riesgo = {"volatilidad": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "twr": 0.0}

        return jsonify({
            "operaciones": operaciones,
            "cartera": cartera,
            "activos_info": activos_info,
            "tir_anualizada": tir,
            "total_pnl_realizado": total_pnl_realizado,
            "history": history,
            "metricas_riesgo": metricas_riesgo,
            "warning_api_error": warning_api_error
        })
    except Exception as e:
        tb = traceback.format_exc()
        log_debug(f"Error en /api/operaciones: {e}\nTraceback:\n{tb}", "ERROR")
        return jsonify({"error": str(e)}), 500

@app.route('/api/operaciones/add', methods=['POST'])
def add_operacion():
    data = request.json or {}
    try:
        op_id = str(uuid.uuid4())
        fecha = normalize_date(data.get('fecha'))
        ticker = data.get('ticker', '').upper().strip()
        tipo = data.get('tipo', 'COMPRA').upper()
        cantidad = float(data.get('cantidad', 0))
        precio = float(data.get('precio', 0))
        comisiones = float(data.get('comisiones', 0))
        impuestos = float(data.get('impuestos', 0))
        amortizacion = float(data.get('amortizacion', 0) or 0)
        intereses = float(data.get('intereses', 0) or 0)
        moneda = str(data.get('moneda') or '').upper().strip() or None
        tasa_cambio = data.get('tasa_cambio')
        
        if not ticker or cantidad <= 0 or precio < 0:
            return jsonify({"error": "Datos inválidos"}), 400
            
        if not tasa_cambio:
            info = get_asset_info_cached(ticker)
            op_currency = moneda or info.get('currency', 'EUR') or 'EUR'
            tasa_cambio = get_historical_exchange_rate(op_currency, fecha, 'EUR')
            if tasa_cambio == 1.0 and op_currency.upper() not in ['EUR', '-']:
                return jsonify({"error": f"No se encontraron datos en Yahoo Finance para la tasa de cambio {op_currency}/EUR. Por favor, introduzca la 'Tasa Cambio' manualmente."}), 400
        else:
            tasa_cambio = float(tasa_cambio)
            
        with db.get_db() as conn:
            conn.execute('''
                INSERT INTO operaciones (id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, moneda, tasa_cambio, amortizacion, intereses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (op_id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, moneda, tasa_cambio, amortizacion, intereses))
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

@app.route('/api/operaciones/edit/<op_id>', methods=['PUT'])
def edit_operacion(op_id):
    data = request.json or {}
    try:
        fecha = normalize_date(data.get('fecha'))
        ticker = data.get('ticker', '').upper().strip()
        tipo = data.get('tipo', 'COMPRA').upper()
        cantidad = float(data.get('cantidad', 0))
        precio = float(data.get('precio', 0))
        comisiones = float(data.get('comisiones', 0))
        impuestos = float(data.get('impuestos', 0))
        amortizacion = float(data.get('amortizacion', 0) or 0)
        intereses = float(data.get('intereses', 0) or 0)
        moneda = str(data.get('moneda') or '').upper().strip() or None
        tasa_cambio = data.get('tasa_cambio')
        
        if not ticker or cantidad <= 0 or precio < 0:
            return jsonify({"error": "Datos inválidos"}), 400
            
        if not tasa_cambio:
            info = get_asset_info_cached(ticker)
            op_currency = moneda or info.get('currency', 'EUR') or 'EUR'
            tasa_cambio = get_historical_exchange_rate(op_currency, fecha, 'EUR')
            if tasa_cambio == 1.0 and op_currency.upper() not in ['EUR', '-']:
                return jsonify({"error": f"No se encontraron datos en Yahoo Finance para la tasa de cambio {op_currency}/EUR. Por favor, introduzca la 'Tasa Cambio' manualmente."}), 400
        else:
            tasa_cambio = float(tasa_cambio)
            
        with db.get_db() as conn:
            conn.execute('''
                UPDATE operaciones 
                SET fecha = ?, ticker = ?, tipo = ?, cantidad = ?, precio = ?, comisiones = ?, impuestos = ?, moneda = ?, tasa_cambio = ?, amortizacion = ?, intereses = ?
                WHERE id = ?
            ''', (fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, moneda, tasa_cambio, amortizacion, intereses, op_id))
            conn.commit()
            
        log_debug(f"Editada operación {op_id} de {ticker}")
        return jsonify({"ok": True})
    except Exception as e:
        log_debug(f"Error editando operación: {e}", "ERROR")
        return jsonify({"error": str(e)}), 400

@app.route('/api/operaciones/split', methods=['POST'])
def apply_split():
    data = request.json or {}
    try:
        ticker = data.get('ticker', '').upper().strip()
        fecha_limite = data.get('fecha_limite')
        ratio = float(data.get('ratio'))

        if not ticker or not fecha_limite or ratio <= 0:
            return jsonify({"error": "Parámetros inválidos: se requiere ticker, fecha_limite y un ratio positivo."}), 400

        with db.get_db() as conn:
            cursor = conn.execute('''
                UPDATE operaciones
                SET
                    cantidad = cantidad * ?,
                    precio = precio / ?
                WHERE
                    ticker = ? AND fecha < ?
            ''', (ratio, ratio, ticker, fecha_limite))
            conn.commit()
            log_debug(f"Aplicado split/contrasplit con ratio {ratio} para {ticker} en operaciones anteriores a {fecha_limite}. Filas afectadas: {cursor.rowcount}")
            return jsonify({"ok": True, "affected_rows": cursor.rowcount})
    except (ValueError, TypeError):
        return jsonify({"error": "Parámetros inválidos. El ratio debe ser un número."}), 400
    except Exception as e:
        log_debug(f"Error aplicando split: {e}", "ERROR")
        return jsonify({"error": str(e)}), 500

@app.route('/api/export/monitores', methods=['GET'])
def export_monitores():
    try:
        with db.get_db() as conn:
            rows = conn.execute("SELECT * FROM monitores").fetchall()
            df = pd.DataFrame([dict(row) for row in rows])
        
        csv_data = df.to_csv(index=False, sep=';', decimal=',')
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
        df = pd.read_csv(file, sep=';', decimal=',')
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
                name, currency = finance_api.fetch_asset_info(sym, isin=ticker)
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
            ops_list = []
            for row in rows:
                op = dict(row)
                if not op.get('moneda'):
                    info = get_asset_info_cached(op['ticker'])
                    op['moneda'] = info.get('currency', 'EUR')
                if not op.get('tasa_cambio'):
                    info = get_asset_info_cached(op['ticker'])
                    fecha_str = str(op['fecha']).strip().split(' ')[0]
                    op_currency = op.get('moneda') or info.get('currency', 'EUR')
                    op['tasa_cambio'] = get_historical_exchange_rate(op_currency, fecha_str, 'EUR')
                ops_list.append(op)
            df = pd.DataFrame(ops_list)
        
        if 'fecha' in df.columns:
            df['fecha'] = df['fecha'].apply(normalize_date)
            
        csv_data = df.to_csv(index=False, sep=';', decimal=',')
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
    
    try:
        df = pd.read_csv(file, sep=';', decimal=',')
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
                    fecha = normalize_date(row.get('fecha'))

                    ticker = str(row['ticker']).strip().upper()
                    tipo = str(row['tipo']).strip().upper()
                    cantidad = float(row['cantidad'])
                    precio = float(row['precio'])
                    comisiones = float(row.get('comisiones', 0)) if pd.notna(row.get('comisiones')) else 0.0
                    impuestos = float(row.get('impuestos', 0)) if pd.notna(row.get('impuestos')) else 0.0
                    moneda = str(row.get('moneda', '')).strip().upper() if 'moneda' in df.columns and pd.notna(row['moneda']) else None
                    if moneda in ['NAN', '']: moneda = None
                    tasa_cambio = float(row['tasa_cambio']) if 'tasa_cambio' in df.columns and pd.notna(row['tasa_cambio']) else None
                    
                    if moneda:
                        info = get_asset_info_cached(ticker)
                        default_curr = str(info.get('currency') or 'EUR').strip().upper()
                        if moneda == default_curr:
                            moneda = None
                            
                    if not tasa_cambio:
                        info = get_asset_info_cached(ticker)
                        op_currency = moneda or info.get('currency', 'EUR') or 'EUR'
                        tasa_cambio = get_historical_exchange_rate(op_currency, fecha, 'EUR')
                            
                    external_id = str(row.get('external_id', '')).strip() if 'external_id' in df.columns and pd.notna(row['external_id']) else None
                    
                    if not ticker or cantidad <= 0 or precio < 0 or tipo not in ['COMPRA', 'VENTA', 'APORTACION', 'DIVIDENDO']:
                        continue
                        
                    conn.execute('''
                        INSERT OR REPLACE INTO operaciones (id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, external_id, moneda, tasa_cambio)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (op_id, fecha, ticker, tipo, cantidad, precio, comisiones, impuestos, external_id, moneda, tasa_cambio))
                except Exception as row_e:
                    log_debug(f"Row import error: {row_e}", "WARNING")
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        tb = traceback.format_exc()
        log_debug(f"Error importing operaciones: {e}\nTraceback:\n{tb}", "ERROR")
        return jsonify({"error": str(e)}), 400

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
    
    from waitress import serve
    import logging
    logger = logging.getLogger('waitress')
    logger.setLevel(logging.ERROR) # Solo mostrar errores reales, no trazas de red
    
    # Waitress maneja de forma segura las desconexiones de clientes SSE sin imprimir stack traces
    serve(app, host='0.0.0.0', port=5000, threads=16, clear_untrusted_proxy_headers=False)