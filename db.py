import sqlite3
import os
import time

DATA_DIR = 'data'
DATA_FILE = os.path.join(DATA_DIR, 'monitores.json')
DB_FILE = os.path.join(DATA_DIR, 'piloto.db')

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS monitores (
                id TEXT PRIMARY KEY,
                ticker TEXT,
                symbol TEXT,
                name TEXT,
                currency TEXT,
                target REAL,
                current REAL,
                tipo TEXT,
                triggered INTEGER
            )
        ''')
        # Añadir nuevas columnas si no existen
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN target_pct REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN pct_triggered_date TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN previous_close REAL DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN current_price_time TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN comunidad_autonoma TEXT DEFAULT 'NACIONAL'")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN pct_titularidad REAL DEFAULT 1.0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN precio_compra_total REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE monitores ADD COLUMN hipoteca_inicial REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS alertas (
                id TEXT PRIMARY KEY,
                msg TEXT,
                time TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS operaciones (
                id TEXT PRIMARY KEY,
                fecha TEXT,
                ticker TEXT,
                tipo TEXT,
                cantidad REAL,
                precio REAL,
                comisiones REAL,
                impuestos REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                external_id TEXT UNIQUE DEFAULT NULL,
                moneda TEXT DEFAULT NULL,
                tasa_cambio REAL DEFAULT NULL
            )
        ''')
        
        try:
            c.execute("ALTER TABLE operaciones ADD COLUMN external_id TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
        try:
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_operaciones_external_id ON operaciones(external_id)")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE operaciones ADD COLUMN moneda TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Columna ya existe
        try:
            c.execute("ALTER TABLE operaciones ADD COLUMN amortizacion REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE operaciones ADD COLUMN intereses REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass
            
        # Crear tablas para la caché persistente
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache_activos (
                ticker TEXT PRIMARY KEY,
                sym TEXT,
                name TEXT,
                currency TEXT,
                timestamp REAL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache_tasas_cambio (
                pair TEXT PRIMARY KEY,
                price REAL,
                timestamp REAL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache_tasas_historicas (
                cache_key TEXT PRIMARY KEY,
                price REAL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache_precios_historicos (
                ticker TEXT,
                fecha TEXT,
                precio REAL,
                PRIMARY KEY (ticker, fecha)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS cache_ine_ipv (
                series_code TEXT,
                anyo INTEGER,
                trimestre INTEGER,
                valor REAL,
                PRIMARY KEY (series_code, anyo, trimestre)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS sync_ine_log (
                series_code TEXT PRIMARY KEY,
                last_sync REAL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS inmuebles_config (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                comunidad_autonoma TEXT DEFAULT 'NACIONAL',
                pct_titularidad REAL DEFAULT 1.0,
                precio_compra_total REAL DEFAULT 0.0,
                hipoteca_inicial REAL DEFAULT 0.0
            )
        ''')
        c.execute("DELETE FROM monitores WHERE tipo = 'INMUEBLE'")
        
        if c.execute("SELECT COUNT(*) FROM config").fetchone()[0] == 0:
            defaults = [
                ("telegram_token", ""),
                ("telegram_chat_id", ""),
                ("refresh_interval", "30"),
                ("check_market_hours", "1"),
                ("debug_ui", "0"),
                ("app_title", "Piloto Financiero"),
                ("activity_retention_days", "2"),
                ("exchange_rate_ttl_hours", "12")
            ]
            c.executemany("INSERT INTO config (clave, valor) VALUES (?, ?)", defaults)
        else:
            c.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('app_title', 'Piloto Financiero')")
            c.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('activity_retention_days', '2')")
            c.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('exchange_rate_ttl_hours', '12')")
        conn.commit()

def get_config():
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT clave, valor FROM config").fetchall()
            cfg = {r['clave']: r['valor'] for r in rows}
            return {
                "telegram_token": cfg.get("telegram_token", ""),
                "telegram_chat_id": cfg.get("telegram_chat_id", ""),
                "refresh_interval": int(cfg.get("refresh_interval", "30")),
                "check_market_hours": cfg.get("check_market_hours", "1") == "1",
                "debug_ui": cfg.get("debug_ui", "0") == "1",
                "app_title": cfg.get("app_title", "Piloto Financiero"),
                "activity_retention_days": int(cfg.get("activity_retention_days", "2")),
                "exchange_rate_ttl_hours": float(cfg.get("exchange_rate_ttl_hours", "12"))
            }
    except Exception as e:
        return {
            "telegram_token": "", "telegram_chat_id": "",
            "refresh_interval": 30, "check_market_hours": True, "debug_ui": False, "app_title": "Piloto Financiero", "activity_retention_days": 2, "exchange_rate_ttl_hours": 12.0
        }

# --- Cache Helpers ---
def get_cached_asset(ticker):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT sym, name, currency, timestamp FROM cache_activos WHERE ticker = ?", (ticker,)).fetchone()
            if row:
                return {
                    'sym': row['sym'],
                    'name': row['name'],
                    'currency': row['currency'],
                    'timestamp': row['timestamp']
                }
    except Exception:
        pass
    return None

def set_cached_asset(ticker, sym, name, currency):
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_activos (ticker, sym, name, currency, timestamp) VALUES (?, ?, ?, ?, ?)",
                (ticker, sym, name, currency, time.time())
            )
            conn.commit()
    except Exception:
        pass

def get_cached_rate(pair):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT price, timestamp FROM cache_tasas_cambio WHERE pair = ?", (pair,)).fetchone()
            if row:
                return {'price': row['price'], 'timestamp': row['timestamp']}
    except Exception:
        pass
    return None

def set_cached_rate(pair, price):
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_tasas_cambio (pair, price, timestamp) VALUES (?, ?, ?)",
                (pair, price, time.time())
            )
            conn.commit()
    except Exception:
        pass

def get_cached_historical_rate(cache_key):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT price FROM cache_tasas_historicas WHERE cache_key = ?", (cache_key,)).fetchone()
            if row:
                return row['price']
    except Exception:
        pass
    return None

def set_cached_historical_rate(cache_key, price):
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_tasas_historicas (cache_key, price) VALUES (?, ?)",
                (cache_key, price)
            )
            conn.commit()
    except Exception:
        pass

def get_cached_historical_prices(ticker, start_date_str, end_date_str):
    import pandas as pd
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT fecha, precio FROM cache_precios_historicos WHERE ticker = ? AND fecha >= ? AND fecha <= ? ORDER BY fecha ASC",
                (ticker, start_date_str, end_date_str)
            ).fetchall()
            if not rows:
                return None
            index = pd.to_datetime([r['fecha'] for r in rows])
            series = pd.Series([r['precio'] for r in rows], index=index)
            return series
    except Exception:
        pass
    return None

def save_historical_prices(ticker, prices_series):
    import pandas as pd
    try:
        with get_db() as conn:
            data = []
            for date, price in prices_series.items():
                if pd.isna(price):
                    continue
                date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)[:10]
                data.append((ticker, date_str, float(price)))
            if data:
                conn.executemany("INSERT OR REPLACE INTO cache_precios_historicos (ticker, fecha, precio) VALUES (?, ?, ?)", data)
                conn.commit()
    except Exception:
        pass

# --- INE Cache Helpers ---
def get_ine_last_sync(series_code):
    try:
        with get_db() as conn:
            row = conn.execute("SELECT last_sync FROM sync_ine_log WHERE series_code = ?", (series_code,)).fetchone()
            if row:
                return row['last_sync']
    except Exception:
        pass
    return None

def save_ine_ipv_data(series_code, rows):
    try:
        with get_db() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO cache_ine_ipv (series_code, anyo, trimestre, valor) VALUES (?, ?, ?, ?)",
                rows
            )
            conn.execute(
                "INSERT OR REPLACE INTO sync_ine_log (series_code, last_sync) VALUES (?, ?)",
                (series_code, time.time())
            )
            conn.commit()
    except Exception as e:
        print(f"Error saving INE IPV data: {e}")

def get_ine_ipv_value(series_code, year, quarter):
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT valor FROM cache_ine_ipv WHERE series_code = ? AND anyo = ? AND trimestre = ?",
                (series_code, year, quarter)
            ).fetchone()
            if row:
                return row['valor']
    except Exception:
        pass
    return None

def get_ine_ipv_closest(series_code, year, quarter):
    try:
        with get_db() as conn:
            target_period = year * 10 + quarter
            rows = conn.execute(
                "SELECT anyo, trimestre, valor FROM cache_ine_ipv WHERE series_code = ?",
                (series_code,)
            ).fetchall()
            if not rows:
                return None
            best_row = min(rows, key=lambda r: abs((r['anyo'] * 10 + r['trimestre']) - target_period))
            return best_row['valor']
    except Exception:
        pass
    return None

def get_ine_ipv_first_available(series_code):
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT valor FROM cache_ine_ipv WHERE series_code = ? ORDER BY anyo ASC, trimestre ASC LIMIT 1",
                (series_code,)
            ).fetchone()
            if row:
                return row['valor']
    except Exception:
        pass
    return None

def get_ine_ipv_latest(series_code):
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT valor FROM cache_ine_ipv WHERE series_code = ? ORDER BY anyo DESC, trimestre DESC LIMIT 1",
                (series_code,)
            ).fetchone()
            if row:
                return row['valor']
    except Exception:
        pass
    return None

# --- Inmuebles Config Helpers ---
def get_inmueble_config(ticker, conn=None):
    try:
        if conn is not None:
            row = conn.execute("SELECT name, comunidad_autonoma, pct_titularidad, precio_compra_total, hipoteca_inicial FROM inmuebles_config WHERE ticker = ?", (ticker,)).fetchone()
        else:
            with get_db() as local_conn:
                row = local_conn.execute("SELECT name, comunidad_autonoma, pct_titularidad, precio_compra_total, hipoteca_inicial FROM inmuebles_config WHERE ticker = ?", (ticker,)).fetchone()
        if row:
            return {
                'name': row['name'],
                'comunidad_autonoma': row['comunidad_autonoma'],
                'pct_titularidad': row['pct_titularidad'],
                'precio_compra_total': row['precio_compra_total'],
                'hipoteca_inicial': row['hipoteca_inicial']
            }
    except Exception:
        pass
    return None

def save_inmueble_config(ticker, name, comunidad, pct_tit, precio_compra, hipoteca_ini, conn=None):
    try:
        if conn is not None:
            conn.execute('''
                INSERT OR REPLACE INTO inmuebles_config (ticker, name, comunidad_autonoma, pct_titularidad, precio_compra_total, hipoteca_inicial)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticker, name, comunidad, pct_tit, precio_compra, hipoteca_ini))
        else:
            with get_db() as local_conn:
                local_conn.execute('''
                    INSERT OR REPLACE INTO inmuebles_config (ticker, name, comunidad_autonoma, pct_titularidad, precio_compra_total, hipoteca_inicial)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (ticker, name, comunidad, pct_tit, precio_compra, hipoteca_ini))
                local_conn.commit()
    except Exception as e:
        print(f"Error saving inmueble config: {e}")
