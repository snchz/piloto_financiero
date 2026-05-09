import sqlite3
import os

DATA_DIR = 'data'
DATA_FILE = os.path.join(DATA_DIR, 'monitores.json')
DB_FILE = os.path.join(DATA_DIR, 'piloto.db')

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
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
        if c.execute("SELECT COUNT(*) FROM config").fetchone()[0] == 0:
            defaults = [
                ("telegram_token", ""),
                ("telegram_chat_id", ""),
                ("refresh_interval", "30"),
                ("check_market_hours", "1"),
                ("debug_ui", "0")
            ]
            c.executemany("INSERT INTO config (clave, valor) VALUES (?, ?)", defaults)
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
                "debug_ui": cfg.get("debug_ui", "0") == "1"
            }
    except Exception as e:
        return {
            "telegram_token": "", "telegram_chat_id": "",
            "refresh_interval": 30, "check_market_hours": True, "debug_ui": False
        }