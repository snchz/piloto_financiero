"""
Sentiment Service - Medidor de Sentimiento de Mercado (Estilo José Luis Cava)
Consolida:
1. Índice de Volatilidad VIX (^VIX)
2. Índice Fear & Greed de CNN (API JSON directa)
3. Cadena de opciones de SPY:
   - Ratio Put/Call (Volumen y Open Interest) + Media Móvil 10 sesiones
   - Muro de Calls (Call Wall) y Muro de Puts (Put Wall)
   - Exposición Gamma de los Dealers (GEX) y Nivel de Gamma Cero (Volatility Trigger)
4. Diagnóstico consolidado de mercado (Pánico / Complacencia / Régimen Gamma)
"""

import logging
import math
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import yfinance as yf

import db

logger = logging.getLogger(__name__)

_sentiment_lock = threading.Lock()

# Headers para simular navegador moderno y evitar bloqueos
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}


def _norm_pdf(x: float) -> float:
    """Función de densidad de probabilidad normal estándar."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    """Función de distribución acumulada normal estándar."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _calculate_black_scholes_gamma(s: float, k: float, t: float, r: float, sigma: float) -> float:
    """
    Calcula la Gamma de una opción europea según el modelo Black-Scholes.
    Gamma es idéntica para Call y Put.
    """
    if s <= 0 or k <= 0 or t <= 0 or sigma <= 0.001:
        return 0.0
    try:
        d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
        gamma = _norm_pdf(d1) / (s * sigma * math.sqrt(t))
        return gamma if not math.isnan(gamma) and not math.isinf(gamma) else 0.0
    except (ValueError, OverflowError, ZeroDivisionError):
        return 0.0


def fetch_vix() -> Dict[str, Any]:
    """Obtiene la cotización actual del índice VIX (^VIX) y su variación."""
    try:
        ticker = yf.Ticker("^VIX")
        # Intentar fast_info o history
        price = None
        prev_close = None

        try:
            fi = getattr(ticker, "fast_info", None)
            if fi:
                price = fi.get("lastPrice")
                prev_close = fi.get("previousClose")
        except Exception:
            pass

        if price is None or prev_close is None:
            hist = ticker.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if len(hist) > 1:
                    prev_close = float(hist["Close"].iloc[-2])
                else:
                    prev_close = price

        price = round(float(price), 2) if price else 0.0
        prev_close = round(float(prev_close), 2) if prev_close else price
        change = round(price - prev_close, 2)
        pct_change = round((change / prev_close) * 100, 2) if prev_close else 0.0

        # Clasificación según el rango VIX
        if price < 13.0:
            regimen = "Complacencia Extrema"
            color = "success"
        elif price < 17.0:
            regimen = "Complacencia / Calma"
            color = "success"
        elif price < 22.0:
            regimen = "Neutral / Tensión Moderada"
            color = "warning"
        elif price < 30.0:
            regimen = "Alta Volatilidad / Temor"
            color = "danger"
        else:
            regimen = "Pánico / Extrema Volatilidad"
            color = "danger"

        return {
            "symbol": "^VIX",
            "current_price": price,
            "previous_close": prev_close,
            "change": change,
            "pct_change": pct_change,
            "regimen": regimen,
            "color": color
        }
    except Exception as e:
        logger.error(f"Error extrayendo cotización del VIX: {e}")
        return {
            "symbol": "^VIX",
            "current_price": 0.0,
            "previous_close": 0.0,
            "change": 0.0,
            "pct_change": 0.0,
            "regimen": "No disponible",
            "color": "secondary"
        }


def fetch_fear_and_greed() -> Dict[str, Any]:
    """
    Obtiene el índice Fear & Greed de CNN consumiendo directamente su endpoint JSON oficial.
    URL: https://production.dataviz.cnn.io/index/fearandgreed/graphdata
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            fg = data.get("fear_and_greed", {})
            score = round(float(fg.get("score", 50)), 1)
            rating = fg.get("rating", "neutral").capitalize()
            prev_close = round(float(fg.get("previous_close", score)), 1)
            prev_week = round(float(fg.get("previous_1_week", score)), 1)
            prev_month = round(float(fg.get("previous_1_month", score)), 1)

            # Clasificación de color
            if score <= 25:
                color = "danger"
                label_es = "Miedo Extremo"
            elif score <= 45:
                color = "warning"
                label_es = "Miedo"
            elif score <= 55:
                color = "secondary"
                label_es = "Neutral"
            elif score <= 75:
                color = "info"
                label_es = "Codicia"
            else:
                color = "success"
                label_es = "Codicia Extrema"

            return {
                "score": score,
                "rating": rating,
                "rating_es": label_es,
                "color": color,
                "previous_close": prev_close,
                "previous_1_week": prev_week,
                "previous_1_month": prev_month,
                "timestamp": fg.get("timestamp")
            }
        else:
            logger.warning(f"CNN Fear & Greed retornó status {resp.status_code}")
    except Exception as e:
        logger.error(f"Error consultando Fear & Greed de CNN: {e}")

    # Fallback si CNN no responde
    return {
        "score": 50.0,
        "rating": "Neutral",
        "rating_es": "Neutral (Estimado)",
        "color": "secondary",
        "previous_close": 50.0,
        "previous_1_week": 50.0,
        "previous_1_month": 50.0,
        "timestamp": None
    }


def fetch_spy_options_and_gex() -> Dict[str, Any]:
    """
    Descarga la cadena de opciones de SPY (vencimiento semanal activo y próximo mensual)
    para calcular:
    1. Ratio Put/Call diario (Volumen) y estructural (Open Interest).
    2. Muros de Opciones: Call Wall y Put Wall (en SPY y escala S&P 500 = Strike x 10).
    3. Exposición Gamma de los Dealers (GEX) y Nivel de Gamma Cero (Volatility Trigger).
    """
    try:
        spy = yf.Ticker("SPY")
        
        # Precio actual de SPY
        current_price = None
        try:
            fi = getattr(spy, "fast_info", None)
            if fi:
                current_price = fi.get("lastPrice")
        except Exception:
            pass

        if current_price is None:
            hist = spy.history(period="2d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
            else:
                current_price = 580.0  # Fallback razonable

        current_price = round(float(current_price), 2)
        spx_equivalent = round(current_price * 10, 1)

        available_expirations = spy.options
        if not available_expirations:
            raise ValueError("No se encontraron vencimientos de opciones para SPY")

        # Seleccionar vencimientos estratégicos:
        # 1) El vencimiento más próximo (front-week)
        # 2) El próximo vencimiento mensual (tercer viernes del mes) o las 3 fechas más inmediatas
        target_dates = []
        now_dt = datetime.now()

        # Añadir el más cercano
        target_dates.append(available_expirations[0])

        # Buscar el próximo mensual relevante
        for exp_str in available_expirations[1:]:
            try:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
                # Si es un viernes entre los días 15 y 21 (OPEX mensual típico) o si es a menos de 45 días
                days_diff = (exp_dt - now_dt).days
                if (15 <= exp_dt.day <= 21 and exp_dt.weekday() == 4) or (days_diff <= 35 and len(target_dates) < 3):
                    if exp_str not in target_dates:
                        target_dates.append(exp_str)
                if len(target_dates) >= 3:
                    break
            except Exception:
                continue

        # Si solo tenemos 1, tomar el segundo disponible
        if len(target_dates) < 2 and len(available_expirations) > 1:
            target_dates.append(available_expirations[1])

        total_call_vol = 0
        total_put_vol = 0
        total_call_oi = 0
        total_put_oi = 0

        calls_oi_by_strike: Dict[float, int] = {}
        puts_oi_by_strike: Dict[float, int] = {}

        # Estructura para cálculo de Gamma (GEX)
        options_for_gex: List[Dict[str, Any]] = []
        risk_free_rate = 0.045  # Tasa libre de riesgo ~4.5%

        for exp_str in target_dates:
            try:
                chain = spy.option_chain(exp_str)
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
                days_to_exp = max((exp_dt - now_dt).days, 0.5)
                t_years = days_to_exp / 365.25

                # Procesar Calls
                if chain.calls is not None and not chain.calls.empty:
                    for _, row in chain.calls.iterrows():
                        k = float(row.get("strike", 0))
                        vol = int(row.get("volume", 0) or 0)
                        oi = int(row.get("openInterest", 0) or 0)
                        iv = float(row.get("impliedVolatility", 0) or 0.20)

                        total_call_vol += vol
                        total_call_oi += oi
                        calls_oi_by_strike[k] = calls_oi_by_strike.get(k, 0) + oi

                        if oi > 0 and 0.01 < iv < 2.5:
                            options_for_gex.append({
                                "type": "call",
                                "strike": k,
                                "oi": oi,
                                "t": t_years,
                                "sigma": iv
                            })

                # Procesar Puts
                if chain.puts is not None and not chain.puts.empty:
                    for _, row in chain.puts.iterrows():
                        k = float(row.get("strike", 0))
                        vol = int(row.get("volume", 0) or 0)
                        oi = int(row.get("openInterest", 0) or 0)
                        iv = float(row.get("impliedVolatility", 0) or 0.20)

                        total_put_vol += vol
                        total_put_oi += oi
                        puts_oi_by_strike[k] = puts_oi_by_strike.get(k, 0) + oi

                        if oi > 0 and 0.01 < iv < 2.5:
                            options_for_gex.append({
                                "type": "put",
                                "strike": k,
                                "oi": oi,
                                "t": t_years,
                                "sigma": iv
                            })

            except Exception as e:
                logger.warning(f"Error procesando vencimiento {exp_str}: {e}")
                continue

        # 1. Ratios Put / Call
        pcr_volume = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else 1.0
        pcr_oi = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else 1.0

        # 2. Localizar Muros (Strikes con mayor Open Interest)
        call_wall_spy = max(calls_oi_by_strike, key=calls_oi_by_strike.get) if calls_oi_by_strike else current_price
        put_wall_spy = max(puts_oi_by_strike, key=puts_oi_by_strike.get) if puts_oi_by_strike else current_price

        call_wall_spx = round(call_wall_spy * 10, 0)
        put_wall_spx = round(put_wall_spy * 10, 0)
        max_call_oi = calls_oi_by_strike.get(call_wall_spy, 0)
        max_put_oi = puts_oi_by_strike.get(put_wall_spy, 0)

        # 3. Modelado de Gamma Exposure (GEX) de Dealers y Gamma Cero
        # Regla institucional estándar (SpotGamma):
        # Dealers son longs de Calls (Gamma +) y shorts de Puts (Gamma -) frente al flujo retail.
        # GEX_call = + Gamma * OI * 100 * S^2
        # GEX_put  = - Gamma * OI * 100 * S^2
        net_gamma_at_current_price = 0.0
        for opt in options_for_gex:
            g = _calculate_black_scholes_gamma(
                s=current_price,
                k=opt["strike"],
                t=opt["t"],
                r=risk_free_rate,
                sigma=opt["sigma"]
            )
            # Valor en millones de $ de exposición gamma por variación del 1% del subyacente
            gex_val = g * opt["oi"] * 100 * (current_price ** 2) * 0.01 / 1e6
            if opt["type"] == "call":
                net_gamma_at_current_price += gex_val
            else:
                net_gamma_at_current_price -= gex_val

        net_gamma_at_current_price = round(net_gamma_at_current_price, 2)

        # Encontrar el Nivel de Gamma Cero (Volatility Trigger)
        # Evaluamos la Gamma neta simulando un barrido de precios en torno al precio actual (-15% a +15%)
        zero_gamma_spy = current_price
        min_p = current_price * 0.85
        max_p = current_price * 1.15
        steps = 60
        step_size = (max_p - min_p) / steps

        prev_sim_gex = None
        prev_sim_p = None
        crossed_zero = False

        for i in range(steps + 1):
            sim_p = min_p + i * step_size
            sim_total_gex = 0.0
            for opt in options_for_gex:
                g = _calculate_black_scholes_gamma(
                    s=sim_p,
                    k=opt["strike"],
                    t=opt["t"],
                    r=risk_free_rate,
                    sigma=opt["sigma"]
                )
                gex_val = g * opt["oi"] * 100 * (sim_p ** 2) * 0.01 / 1e6
                if opt["type"] == "call":
                    sim_total_gex += gex_val
                else:
                    sim_total_gex -= gex_val

            if prev_sim_gex is not None:
                # Cruce por cero
                if (prev_sim_gex < 0 and sim_total_gex >= 0) or (prev_sim_gex >= 0 and sim_total_gex < 0):
                    # Interpolación lineal simple
                    diff_gex = sim_total_gex - prev_sim_gex
                    if diff_gex != 0:
                        zero_gamma_spy = prev_sim_p + (0.0 - prev_sim_gex) * (sim_p - prev_sim_p) / diff_gex
                    else:
                        zero_gamma_spy = sim_p
                    crossed_zero = True
                    break

            prev_sim_gex = sim_total_gex
            prev_sim_p = sim_p

        # Si no cruzó en el rango, asignar un valor coherente basado en soporte/put wall
        if not crossed_zero:
            zero_gamma_spy = put_wall_spy if net_gamma_at_current_price > 0 else current_price * 1.02

        zero_gamma_spy = round(zero_gamma_spy, 1)
        zero_gamma_spx = round(zero_gamma_spy * 10, 0)

        # Determinar régimen de Gamma
        es_gamma_positiva = current_price >= zero_gamma_spy
        regimen_gamma = "Gamma Positiva" if es_gamma_positiva else "Gamma Negativa"
        regimen_gamma_desc = (
            "Dealers compran en caídas y venden en subidas. Volatilidad contenida y amortiguada."
            if es_gamma_positiva
            else "Dealers venden en caídas amplificando la presión bajista. Alerta de aceleración."
        )

        return {
            "current_price_spy": current_price,
            "spx_equivalent": spx_equivalent,
            "analyzed_expirations": target_dates,
            "put_call": {
                "pcr_volume": pcr_volume,
                "pcr_oi": pcr_oi,
                "total_call_volume": total_call_vol,
                "total_put_volume": total_put_vol,
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi
            },
            "walls": {
                "call_wall_spy": call_wall_spy,
                "call_wall_spx": call_wall_spx,
                "call_wall_oi": max_call_oi,
                "put_wall_spy": put_wall_spy,
                "put_wall_spx": put_wall_spx,
                "put_wall_oi": max_put_oi,
                "distancia_call_wall_pct": round(((call_wall_spy - current_price) / current_price) * 100, 2),
                "distancia_put_wall_pct": round(((put_wall_spy - current_price) / current_price) * 100, 2)
            },
            "gamma_exposure": {
                "net_gex_millones": net_gamma_at_current_price,
                "zero_gamma_spy": zero_gamma_spy,
                "zero_gamma_spx": zero_gamma_spx,
                "is_positive_gamma": es_gamma_positiva,
                "regimen": regimen_gamma,
                "regimen_desc": regimen_gamma_desc,
                "distancia_zero_gamma_pct": round(((current_price - zero_gamma_spy) / zero_gamma_spy) * 100, 2)
            }
        }
    except Exception as e:
        logger.error(f"Error procesando opciones de SPY: {e}", exc_info=True)
        return {
            "current_price_spy": 0.0,
            "spx_equivalent": 0.0,
            "analyzed_expirations": [],
            "put_call": {"pcr_volume": 1.0, "pcr_oi": 1.0, "total_call_volume": 0, "total_put_volume": 0, "total_call_oi": 0, "total_put_oi": 0},
            "walls": {"call_wall_spy": 0.0, "call_wall_spx": 0, "call_wall_oi": 0, "put_wall_spy": 0.0, "put_wall_spx": 0, "put_wall_oi": 0, "distancia_call_wall_pct": 0.0, "distancia_put_wall_pct": 0.0},
            "gamma_exposure": {
                "net_gex_millones": 0.0,
                "zero_gamma_spy": 0.0,
                "zero_gamma_spx": 0,
                "is_positive_gamma": True,
                "regimen": "No disponible",
                "regimen_desc": "",
                "distancia_zero_gamma_pct": 0.0
            }
        }


def _calcular_diagnostico_cava(vix: Dict[str, Any], fg: Dict[str, Any], options_data: Dict[str, Any], pcr_10d_ma: Optional[float]) -> Dict[str, Any]:
    """
    Sintetiza todos los indicadores bajo la lógica de José Luis Cava:
    - Extremos de complacencia (peligro de corrección)
    - Extremos de pánico (suelo y oportunidad de compra)
    - Régimen de Gamma de los Creadores de Mercado
    """
    vix_val = vix.get("current_price", 18.0)
    fg_val = fg.get("score", 50.0)
    pcr_vol = options_data.get("put_call", {}).get("pcr_volume", 1.0)
    pcr_effective = pcr_10d_ma if (pcr_10d_ma is not None and pcr_10d_ma > 0) else pcr_vol

    gex = options_data.get("gamma_exposure", {})
    is_positive_gamma = gex.get("is_positive_gamma", True)
    walls = options_data.get("walls", {})
    dist_call_wall = walls.get("distancia_call_wall_pct", 5.0)
    dist_put_wall = walls.get("distancia_put_wall_pct", -5.0)

    # Evaluación de señales
    # 1. Pánico Extremo (Oportunidad Contraría de Suelo)
    if (fg_val <= 25 or vix_val >= 25.0) and pcr_effective >= 1.05:
        estado = "PÁNICO EXTREMO (Suelo Cercano / Oportunidad)"
        color = "success"  # Oportunidad para inversores
        badge_class = "bg-success"
        resumen = (
            f"El mercado muestra capitulación con VIX en {vix_val}, Fear & Greed en {fg_val} y ratio Put/Call en {pcr_effective:.2f}. "
            f"Históricamente, estos extremos señalan zonas de suelo o rebote contrarío inminente."
        )
    # 2. Complacencia Extrema (Peligro de Techo / Ajuste)
    elif (fg_val >= 75 or vix_val <= 13.5) and pcr_effective <= 0.65:
        estado = "COMPLACENCIA EXTREMA (Alerta de Techo)"
        color = "danger"  # Peligro de corrección
        badge_class = "bg-danger"
        resumen = (
            f"Exceso de optimismo con VIX contenido en {vix_val}, Fear & Greed en {fg_val} y ratio Put/Call en {pcr_effective:.2f}. "
            f"El S&P 500 cotiza a un {abs(dist_call_wall):.1f}% del Muro de Calls ({walls.get('call_wall_spx')}), donde los dealers frenan la subida vendiendo futuros."
        )
    # 3. Alerta de Volatilidad por Gamma Negativa
    elif not is_positive_gamma:
        estado = "ALERTA DE VOLATILIDAD (Gamma Negativa)"
        color = "warning"
        badge_class = "bg-warning text-dark"
        resumen = (
            f"El S&P 500 cotiza por debajo del Nivel de Gamma Cero ({gex.get('zero_gamma_spx')}). "
            f"Los creadores de mercado están en gamma negativa y amplifican las caídas vendiendo para cubrir delta. Prudencia."
        )
    # 4. Tendencia Favorable en Gamma Positiva
    else:
        estado = "RÉGIMEN ESTABLE (Gamma Positiva)"
        color = "info"
        badge_class = "bg-primary"
        resumen = (
            f"El S&P 500 se mantiene por encima del nivel de Gamma Cero ({gex.get('zero_gamma_spx')}). "
            f"Los creadores de mercado amortiguan las caídas comprando contra tendencia. Soporte clave en Muro de Puts ({walls.get('put_wall_spx')})."
        )

    return {
        "estado": estado,
        "color": color,
        "badge_class": badge_class,
        "resumen": resumen,
        "pcr_usado": round(pcr_effective, 3),
        "es_10d_ma": bool(pcr_10d_ma is not None and pcr_10d_ma > 0)
    }


def get_consolidated_sentiment(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Devuelve las métricas consolidadas de sentimiento de mercado.
    Implementa caché con TTL de 30 minutos en SQLite para no saturar APIs externas.
    """
    if not force_refresh:
        cached = db.get_sentiment_cache("market_sentiment", max_age_seconds=1800)
        if cached:
            return cached

    with _sentiment_lock:
        # Doble verificación tras adquirir el lock
        if not force_refresh:
            cached = db.get_sentiment_cache("market_sentiment", max_age_seconds=1800)
            if cached:
                return cached

        logger.info("Actualizando métricas de sentimiento de mercado...")

        # 1. Obtener VIX
        vix_data = fetch_vix()

        # 2. Obtener CNN Fear & Greed
        fg_data = fetch_fear_and_greed()

        # 3. Obtener Opciones de SPY, Muros y GEX
        spy_options_data = fetch_spy_options_and_gex()

        # 4. Obtener histórico de Put/Call para calcular la media de 10 sesiones
        history_rows = db.get_put_call_history(limit=12)
        pcr_values = [float(r["pcr_volume"]) for r in history_rows if r.get("pcr_volume") is not None]
        
        # Añadir el ratio actual
        current_pcr = spy_options_data.get("put_call", {}).get("pcr_volume", 1.0)
        if current_pcr:
            pcr_values.append(float(current_pcr))

        pcr_10d_ma = None
        if len(pcr_values) >= 3:
            recent_pcr = pcr_values[-10:]
            pcr_10d_ma = round(sum(recent_pcr) / len(recent_pcr), 3)

        # 5. Generar diagnóstico Cava
        diagnostico = _calcular_diagnostico_cava(vix_data, fg_data, spy_options_data, pcr_10d_ma)

        result = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vix": vix_data,
            "fear_and_greed": fg_data,
            "spy_price": spy_options_data.get("current_price_spy"),
            "spx_price": spy_options_data.get("spx_equivalent"),
            "put_call": {
                **spy_options_data.get("put_call", {}),
                "pcr_10d_ma": pcr_10d_ma,
                "history_points": len(pcr_values)
            },
            "walls": spy_options_data.get("walls", {}),
            "gamma_exposure": spy_options_data.get("gamma_exposure", {}),
            "diagnostico": diagnostico,
            "from_cache": False,
            "cache_age_seconds": 0
        }

        # Guardar en base de datos SQLite
        db.save_sentiment_cache("market_sentiment", result)
        return result
