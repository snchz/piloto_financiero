import re

def update_monitor_worker():
    with open('monitor_worker.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # We want to insert the cleanup and news fetching after:
    # sse_subs.notify()
    
    target_block = """            # Notificar siempre para actualizar "Última actualización" en la UI
            sse_subs.notify()"""

    new_block = """            # Notificar siempre para actualizar "Última actualización" en la UI
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
"""

    if "# --- Cleanup and News Fetching ---" not in code:
        code = code.replace(target_block, new_block)
        with open('monitor_worker.py', 'w', encoding='utf-8') as f:
            f.write(code)

if __name__ == '__main__':
    update_monitor_worker()
