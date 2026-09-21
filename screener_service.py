"""
Equity Screener Service - Williams %R (14) & Target Net Gain
Escáner de sobreventa para el S&P 500 y Mercado Continuo Español (.MC)
"""

import io
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


import pandas as pd
import requests
import yfinance as yf

import db

logger = logging.getLogger(__name__)

DEFAULT_SPANISH_TICKERS = [
    # IBEX 35 + Claves Mercado Continuo
    "SAN.MC", "BBVA.MC", "ITX.MC", "IBE.MC", "TEF.MC", "REP.MC", "CABK.MC", "AMS.MC",
    "FER.MC", "GRF.MC", "IAG.MC", "ACS.MC", "ENG.MC", "ELE.MC", "RED.MC", "MAP.MC",
    "COL.MC", "MRL.MC", "SAB.MC", "BKT.MC", "ANE.MC", "ACX.MC", "FDR.MC", "ROVI.MC",
    "SLR.MC", "MEL.MC", "IDR.MC", "LOG.MC", "UNI.MC", "SCYR.MC", "VIS.MC", "CIE.MC",
    "PHM.MC", "GCT.MC", "ALM.MC", "CAF.MC", "VID.MC", "TLGO.MC", "TRE.MC", "DOM.MC",
    "TUB.MC", "TRG.MC", "APPS.MC", "GSJ.MC", "AIR.MC", "EDR.MC", "GEST.MC", "EBRO.MC",
    "ENR.MC", "NTX.MC"
]

# Fallback constituyentes principales S&P 500 si Wikipedia no responde
SP500_FALLBACK_SAMPLE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "TSLA", "UNH", "JNJ",
    "XOM", "JPM", "V", "PG", "MA", "AVGO", "HD", "CVX", "MRK", "ABBV",
    "COST", "PEP", "KO", "ADBE", "WMT", "MCD", "CSCO", "CRM", "BAC", "PFE",
    "TMO", "ACN", "NFLX", "LIN", "AMD", "ABT", "ORCL", "DIS", "NKE", "INTC",
    "WFC", "PM", "TXN", "DHR", "COP", "VZ", "NEE", "QCOM", "CAT", "AMGN"
]

# Estado del escaneo en memoria para feedback inmediato
_scan_lock = threading.Lock()
_scan_state = {
    "is_scanning": False,
    "progress": 0,
    "total": 0,
    "current_batch": "",
    "message": "Inactivo",
    "start_time": None,
    "last_error": None
}


def get_scan_state() -> Dict[str, Any]:
    with _scan_lock:
        return dict(_scan_state)


def set_scan_state(**kwargs) -> None:
    with _scan_lock:
        _scan_state.update(kwargs)


def fetch_sp500_constituents() -> List[Tuple[str, str]]:
    """
    Obtiene la lista oficial de componentes del S&P 500 desde Wikipedia.
    Retorna lista de tuplas (ticker, nombre_empresa).
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PilotoFinanciero/1.0"}
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            tables = pd.read_html(io.StringIO(resp.text))
            df = tables[0]
            tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
            names = df["Security"].tolist() if "Security" in df.columns else tickers
            return list(zip(tickers, names))
    except Exception as e:
        logger.warning(f"No se pudo descargar componentes S&P 500 de Wikipedia: {e}")

    # Fallback si falla la conexión externa
    return [(t, t) for t in SP500_FALLBACK_SAMPLE]


def get_configured_spanish_tickers() -> List[str]:
    """Recupera la lista de tickers españoles configurados en BD o retorna los por defecto."""
    val = db.get_screener_config("spanish_tickers")
    if val:
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass
    return DEFAULT_SPANISH_TICKERS


def save_configured_spanish_tickers(tickers: List[str]) -> bool:
    """Guarda la lista personalizada de tickers españoles."""
    clean = [t.strip().upper() for t in tickers if t.strip()]
    # Asegurar sufijo .MC
    clean = [t if t.endswith(".MC") else f"{t}.MC" for t in clean]
    clean = sorted(list(set(clean)))
    db.set_screener_config("spanish_tickers", json.dumps(clean))
    return True


def calculate_williams_r(df: pd.DataFrame, period: int = 14) -> Optional[Dict[str, Any]]:
    """
    Calcula el Williams %R de 14 períodos para un activo:
    W%R = ((H14 - C) / (H14 - L14)) * -100
    Rango de -100 (máxima sobreventa) a 0 (máxima sobrecompra).
    """
    if df is None or len(df) < period:
        return None

    # Limpiar filas con NaN en High, Low, Close
    clean_df = df[["High", "Low", "Close"]].dropna()
    if len(clean_df) < period:
        return None

    sub = clean_df.tail(period)
    h14 = float(sub["High"].max())
    l14 = float(sub["Low"].min())
    close = float(sub["Close"].iloc[-1])

    denom = h14 - l14
    if denom > 0:
        w_r = ((h14 - close) / denom) * -100.0
    else:
        w_r = -50.0  # Rango nulo

    latest_date = str(sub.index[-1]).split(" ")[0]

    return {
        "close": round(close, 4),
        "high_14": round(h14, 4),
        "low_14": round(l14, 4),
        "williams_r": round(w_r, 2),
        "date": latest_date
    }


def calculate_target_sell_price(
    close_price: float,
    comision_in_pct: float = 0.12,
    comision_out_pct: float = 0.12,
    target_gain_pct: float = 5.0
) -> Dict[str, float]:
    """
    Calcula el precio de venta límite para lograr un +5.00% neto limpio.
    P_sell = P_buy * [ (1 + c_in) * (1 + r_target) ] / (1 - c_out)
    """
    c_in = comision_in_pct / 100.0
    c_out = comision_out_pct / 100.0
    r_target = target_gain_pct / 100.0

    if c_out >= 1.0:
        c_out = 0.0012

    factor = ((1.0 + c_in) * (1.0 + r_target)) / (1.0 - c_out)
    target_price = close_price * factor
    gross_gain_pct = (factor - 1.0) * 100.0

    return {
        "target_price": round(target_price, 4),
        "gross_gain_pct": round(gross_gain_pct, 2),
        "net_gain_pct": target_gain_pct
    }


def fetch_ticker_fundamentals(ticker: str) -> Dict[str, Optional[float]]:
    """
    Obtiene métricas fundamentales vía yfinance para los filtros Value:
    - trailingPE (PER)
    - priceToBook (P/B)
    - returnOnEquity (ROE)
    - trailingEps (BPA)
    - debtToEquity (Deuda / Capital)
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        def _clean(val):
            if val is None:
                return None
            try:
                f = float(val)
                return None if (f != f) else round(f, 4)
            except (ValueError, TypeError):
                return None

        return {
            "trailing_pe": _clean(info.get("trailingPE")),
            "price_to_book": _clean(info.get("priceToBook")),
            "return_on_equity": _clean(info.get("returnOnEquity")),
            "trailing_eps": _clean(info.get("trailingEps")),
            "debt_to_equity": _clean(info.get("debtToEquity"))
        }
    except Exception as e:
        logger.debug(f"Error obteniendo fundamentales de {ticker}: {e}")
        return {
            "trailing_pe": None,
            "price_to_book": None,
            "return_on_equity": None,
            "trailing_eps": None,
            "debt_to_equity": None
        }


def check_graham(pe: Optional[float], pb: Optional[float]) -> bool:
    """Filtro Benjamin Graham: PER < 15 y P/B < 1.5 (ambos positivos)."""
    if pe is None or pb is None:
        return False
    return (0 < pe < 15.0) and (0 < pb < 1.5)


def check_buffett(roe: Optional[float], eps: Optional[float]) -> bool:
    """Filtro Warren Buffett: ROE > 10% (0.10) y EPS > 0."""
    if roe is None or eps is None:
        return False
    return (roe > 0.10) and (eps > 0)


def check_deuda(de: Optional[float]) -> bool:
    """Filtro Deuda: Deuda/Capital < 100."""
    if de is None:
        return False
    return (0 <= de < 100.0)


def _run_scan_thread(batch_size: int = 50):
    """Worker en background que procesa el universo de activos en batches y persiste resultados."""
    try:
        set_scan_state(is_scanning=True, progress=0, message="Recuperando constituyentes S&P 500...", start_time=time.time())

        # 1. Obtener tickers
        sp500_list = fetch_sp500_constituents()
        sp500_names = {t: n for t, n in sp500_list}
        sp500_tickers = [t for t, _ in sp500_list]

        spanish_tickers = get_configured_spanish_tickers()

        # Marcar mercados
        all_items: List[Tuple[str, str, str]] = []  # (ticker, name, market)
        for t in sp500_tickers:
            all_items.append((t, sp500_names.get(t, t), "S&P 500"))
        for t in spanish_tickers:
            all_items.append((t, t.replace(".MC", ""), "Mercado Continuo (.MC)"))

        total_assets = len(all_items)
        set_scan_state(total=total_assets, message=f"Descargando históricos para {total_assets} activos...")

        results = []
        scanned_count = 0

        # 2. Descargar en lotes de batch_size con yfinance
        for i in range(0, total_assets, batch_size):
            batch = all_items[i:i + batch_size]
            batch_tickers = [item[0] for item in batch]
            batch_info_map = {item[0]: item for item in batch}

            batch_str = f"{batch_tickers[0]} ... {batch_tickers[-1]}"
            pct = int((scanned_count / total_assets) * 100)
            set_scan_state(progress=pct, current_batch=batch_str, message=f"Analizando lote ({scanned_count}/{total_assets})...")

            try:
                # Descarga masiva con multithreading interno
                data = yf.download(
                    batch_tickers,
                    period="6mo",
                    interval="1d",
                    group_by="ticker",
                    threads=True,
                    progress=False
                )

                for t in batch_tickers:
                    try:
                        # Extraer DataFrame del activo
                        if len(batch_tickers) == 1:
                            df_asset = data
                        elif t in data:
                            df_asset = data[t]
                        else:
                            df_asset = None

                        if df_asset is not None and not df_asset.empty:
                            metrics = calculate_williams_r(df_asset, period=14)
                            if metrics:
                                item_meta = batch_info_map[t]
                                curr = "EUR" if t.endswith(".MC") else "USD"
                                target_info = calculate_target_sell_price(metrics["close"])

                                results.append({
                                    "ticker": t,
                                    "name": item_meta[1],
                                    "market": item_meta[2],
                                    "currency": curr,
                                    "close_price": metrics["close"],
                                    "high_14": metrics["high_14"],
                                    "low_14": metrics["low_14"],
                                    "williams_r": metrics["williams_r"],
                                    "target_price": target_info["target_price"],
                                    "gross_gain_pct": target_info["gross_gain_pct"],
                                    "date": metrics["date"]
                                })
                    except Exception as e_ticker:
                        logger.debug(f"Error procesando ticker individual {t}: {e_ticker}")
            except Exception as e_batch:
                logger.warning(f"Error descargando lote {batch_str}: {e_batch}")

            scanned_count += len(batch)

        # 2.5 Descargar métricas fundamentales en paralelo para candidatos en sobreventa (W%R <= -70.0)
        candidates = [r["ticker"] for r in results if r.get("williams_r", 0) <= -70.0]
        if candidates:
            set_scan_state(
                message=f"Descargando fundamentales Value (Graham, Buffett, Deuda) para {len(candidates)} candidatos..."
            )
            try:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    fund_results = list(executor.map(fetch_ticker_fundamentals, candidates))
                fund_map = dict(zip(candidates, fund_results))
                for r in results:
                    t = r["ticker"]
                    if t in fund_map:
                        r.update(fund_map[t])
            except Exception as e_fund:
                logger.warning(f"Error descargando fundamentales concurrentes: {e_fund}")

        # 3. Guardar en SQLite
        scan_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.save_screener_results(results, scan_timestamp=scan_timestamp, total_scanned=total_assets)

        signals_count = len([r for r in results if r["williams_r"] < -80.0])
        set_scan_state(
            is_scanning=False,
            progress=100,
            message=f"Escaneo completado. {signals_count} señales detectadas de {total_assets} activos.",
            total=total_assets
        )

    except Exception as e:
        logger.error(f"Error en ejecución del screener: {e}", exc_info=True)
        set_scan_state(is_scanning=False, message=f"Error en escaneo: {str(e)}", last_error=str(e))


def backfill_fundamentals(max_workers: int = 10) -> int:
    """
    Rellena métricas fundamentales en SQLite para todas las señales en sobreventa
    que aún tengan los campos en NULL.
    """
    try:
        raw_signals = db.get_screener_results()
        pending = [
            s["ticker"] for s in raw_signals
            if s.get("trailing_pe") is None and s.get("williams_r", 0) <= -70.0
        ]
        if not pending:
            return 0

        logger.info(f"Rellenando fundamentales para {len(pending)} activos en BD...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            fund_data = list(executor.map(fetch_ticker_fundamentals, pending))

        updates = []
        for ticker, data in zip(pending, fund_data):
            u = {"ticker": ticker}
            u.update(data)
            updates.append(u)

        db.update_screener_fundamentals_batch(updates)
        logger.info(f"Fundamentales actualizados con éxito para {len(updates)} activos.")
        return len(updates)
    except Exception as e:
        logger.error(f"Error en backfill de fundamentales: {e}")
        return 0


def trigger_screener_scan(batch_size: int = 50) -> bool:
    """Inicia el escaneo en segundo plano si no hay otro en curso."""
    with _scan_lock:
        if _scan_state["is_scanning"]:
            return False  # Ya está corriendo
        _scan_state["is_scanning"] = True
        _scan_state["progress"] = 0
        _scan_state["message"] = "Iniciando escáner..."

    thread = threading.Thread(target=_run_scan_thread, args=(batch_size,), daemon=True)
    thread.start()
    return True


def get_screener_data(
    umbral_wr: float = -80.0,
    comision_in: float = 0.12,
    comision_out: float = 0.12,
    target_gain: float = 5.0,
    market_filter: str = "ALL",
    filtro_graham: bool = False,
    filtro_buffett: bool = False,
    filtro_deuda: bool = False,
    filtro_gem: bool = False
) -> Dict[str, Any]:
    """
    Retorna el estado del escáner y la lista de señales filtradas por W%R y filtros Value.
    """
    raw_signals = db.get_screener_results()
    meta = db.get_screener_meta()
    scan_state = get_scan_state()

    filtered_signals = []
    total_gems = 0
    total_graham = 0
    total_buffett = 0
    total_deuda = 0

    for s in raw_signals:
        wr = float(s.get("williams_r", 0))
        # Filtro de sobreventa W%R <= umbral (ej. -80)
        if wr <= umbral_wr:
            market = s.get("market", "")
            if market_filter == "SP500" and "S&P" not in market:
                continue
            if market_filter == "MC" and ".MC" not in market:
                continue

            pe = s.get("trailing_pe")
            pb = s.get("price_to_book")
            roe = s.get("return_on_equity")
            eps = s.get("trailing_eps")
            de = s.get("debt_to_equity")

            passes_g = check_graham(pe, pb)
            passes_b = check_buffett(roe, eps)
            passes_d = check_deuda(de)
            is_gem = passes_g and passes_b and passes_d

            if passes_g:
                total_graham += 1
            if passes_b:
                total_buffett += 1
            if passes_d:
                total_deuda += 1
            if is_gem:
                total_gems += 1

            # Filtrar según los filtros activos de Value Investing
            if filtro_gem and not is_gem:
                continue
            if filtro_graham and not passes_g:
                continue
            if filtro_buffett and not passes_b:
                continue
            if filtro_deuda and not passes_d:
                continue

            # Recalcular precio de venta límite según comisiones del usuario
            close = float(s.get("close_price", 0))
            calc = calculate_target_sell_price(
                close,
                comision_in_pct=comision_in,
                comision_out_pct=comision_out,
                target_gain_pct=target_gain
            )

            filtered_signals.append({
                "ticker": s.get("ticker"),
                "name": s.get("name") or s.get("ticker"),
                "market": market,
                "currency": s.get("currency", "USD"),
                "close_price": close,
                "high_14": float(s.get("high_14", 0)),
                "low_14": float(s.get("low_14", 0)),
                "williams_r": wr,
                "date": s.get("date"),
                "target_price": calc["target_price"],
                "gross_gain_pct": calc["gross_gain_pct"],
                "net_gain_pct": calc["net_gain_pct"],
                # Fundamentales Value Investing
                "trailing_pe": pe,
                "price_to_book": pb,
                "return_on_equity": roe,
                "trailing_eps": eps,
                "debt_to_equity": de,
                "passes_graham": passes_g,
                "passes_buffett": passes_b,
                "passes_deuda": passes_d,
                "is_value_gem": is_gem
            })

    # Ordenar por mayor sobreventa (W%R más bajo / negativo primero)
    filtered_signals.sort(key=lambda x: x["williams_r"])

    total_scanned = int(meta.get("total_scanned", 0))
    last_scan_time = meta.get("last_scan_time", "Nunca")

    avg_wr = round(sum(s["williams_r"] for s in filtered_signals) / len(filtered_signals), 2) if filtered_signals else None

    return {
        "status": scan_state,
        "last_scan_time": last_scan_time,
        "total_scanned": total_scanned,
        "total_signals": len(filtered_signals),
        "total_gems": total_gems,
        "total_graham": total_graham,
        "total_buffett": total_buffett,
        "total_deuda": total_deuda,
        "avg_williams_r": avg_wr,
        "params": {
            "umbral_wr": umbral_wr,
            "comision_in": comision_in,
            "comision_out": comision_out,
            "target_gain": target_gain,
            "market_filter": market_filter,
            "filtro_graham": filtro_graham,
            "filtro_buffett": filtro_buffett,
            "filtro_deuda": filtro_deuda,
            "filtro_gem": filtro_gem
        },
        "signals": filtered_signals
    }

