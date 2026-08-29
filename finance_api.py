import requests
import yfinance as yf
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

# --- Session Setup ---
def setup_session():
    s = requests.Session()
    retries = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["HEAD", "GET", "OPTIONS"])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

session = setup_session()

# --- Yahoo Finance Integration ---
def fetch_yahoo_crumb():
    try:
        session.get('https://fc.yahoo.com', headers=SEARCH_HEADERS, timeout=10)
        time.sleep(0.5)
        res = session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", headers=SEARCH_HEADERS, timeout=10)
        return res.text.strip() if res.status_code == 200 else None
    except Exception:
        return None

YAHOO_CRUMB = fetch_yahoo_crumb()

RESOLVED_NAMES_CACHE = {}

def resolve_ticker(isin_or_ticker):
    if len(isin_or_ticker) == 12 and isin_or_ticker[:2].isalpha() and isin_or_ticker[2:].isalnum():
        # Buscar por ISIN
        endpoints = [
            "https://query1.finance.yahoo.com/v1/finance/search",
            "https://query2.finance.yahoo.com/v1/finance/search"
        ]
        
        for url in endpoints:
            try:
                res = session.get(url, params={"q": isin_or_ticker, "quotesCount": 5}, headers=SEARCH_HEADERS, timeout=10)
                if res.status_code == 429:
                    time.sleep(2)
                    continue
                res.raise_for_status()
                quotes = res.json().get('quotes', [])
                best_q = None
                for q in quotes:
                    sym = q.get('symbol')
                    if not sym:
                        continue
                    if not best_q:
                        best_q = q
                    else:
                        curr_sym = best_q.get('symbol')
                        is_curr_low_quality = ('.SG' in curr_sym or 'PNK' in best_q.get('exchange', ''))
                        is_new_high_quality = ('.SG' not in sym and 'PNK' not in q.get('exchange', ''))
                        if is_curr_low_quality and is_new_high_quality:
                            best_q = q
                if best_q:
                    sym = best_q.get('symbol')
                    name = best_q.get('longname') or best_q.get('shortname')
                    if name:
                        RESOLVED_NAMES_CACHE[sym] = name
                    return sym
            except Exception:
                continue
        return None
    return isin_or_ticker

def find_symbol_by_name_and_currency(name, target_currency):
    if not name:
        return None
    try:
        res = session.get("https://query1.finance.yahoo.com/v1/finance/search", params={"q": name, "quotesCount": 15}, headers=SEARCH_HEADERS, timeout=10)
        res.raise_for_status()
        quotes = res.json().get('quotes', [])
        
        candidates = []
        for q in quotes:
            sym = q.get('symbol')
            if not sym:
                continue
            candidates.append(sym)
            
        eur_high_quality = ('.DE', '.MI', '.PA', '.AS', '.MC')
        eur_low_quality = ('.SG', '.F')
        usd_suffixes = ('', '.NX', '.O')
        
        def rank_candidate(sym):
            if target_currency == 'EUR':
                if any(sym.endswith(suf) for suf in eur_high_quality):
                    return 0
                if any(sym.endswith(suf) for suf in eur_low_quality):
                    return 1
            elif target_currency == 'USD':
                if any(sym.endswith(suf) for suf in usd_suffixes) or '.' not in sym:
                    return 0
            return 2
            
        candidates = sorted(candidates, key=rank_candidate)
        
        for sym in candidates[:5]:
            try:
                info = yf.Ticker(sym).info
                curr = info.get('currency')
                if curr == target_currency:
                    return sym
            except Exception:
                continue
    except Exception:
        pass
    return None

def fetch_asset_info(ticker, isin=None):
    try:
        # Priorizar caché de nombres resueltos en la búsqueda (ej. de Yahoo Search)
        name = RESOLVED_NAMES_CACHE.get(ticker) or ""
        currency = ""
        
        if not name:
            info = yf.Ticker(ticker).info
            name = info.get('longName') or info.get('shortName') or ""
            currency = info.get('currency') or ""
        else:
            try:
                info = yf.Ticker(ticker).info
                currency = info.get('currency') or ""
            except Exception:
                pass
        
        # Fallback a JustETF si sigue sin nombre y se trata de un ISIN
        if not name:
            target_isin = isin if (isin and len(isin) == 12) else (ticker if len(ticker) == 12 else None)
            if target_isin and target_isin[:2].isalpha() and target_isin[2:].isalnum():
                import re
                try:
                    res = session.get(f"https://www.justetf.com/en/etf-profile.html?isin={target_isin}", headers=SEARCH_HEADERS, timeout=10)
                    if res.status_code == 200:
                        title_match = re.search(r'<title>(.*?)</title>', res.text)
                        if title_match:
                            title_text = title_match.group(1)
                            parts = title_text.split('|')
                            if len(parts) >= 3 and target_isin in parts[2]:
                                name = parts[0].strip()
                except Exception:
                    pass
                    
        return name, currency
    except Exception:
        return "", ""

def fetch_historical_price(ticker, date_str):
    try:
        t = yf.Ticker(ticker)
        from datetime import datetime, timedelta
        req_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = req_date - timedelta(days=5) # 5 días atrás para buscar el último cierre válido
        end_date = req_date + timedelta(days=1)   # +1 día porque 'end' es exclusivo en yfinance
        hist = t.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if not hist.empty:
            closes = hist['Close'].dropna()
            if not closes.empty:
                return float(closes.iloc[-1])
    except Exception:
        pass
    return None

def fetch_news(ticker, limit=3):
    try:
        news = yf.Ticker(ticker).news
        if not news: return []
        
        parsed = []
        for n in news[:limit]:
            title = n.get('title')
            publisher = n.get('publisher')
            link = n.get('link')
            if title:
                parsed.append({"title": title, "publisher": publisher, "link": link})
        return parsed
    except Exception:
        return []

def fetch_price(ticker):
    t = yf.Ticker(ticker)
    current_price = None
    previous_close = None
    
    try:
        info = t.info
        current_price = info.get('regularMarketPrice')
        previous_close = info.get('regularMarketPreviousClose') or info.get('previousClose')
    except Exception:
        pass
    
    if not current_price:
        try:
            if p := t.fast_info.get('last_price'): current_price = p
        except Exception: pass
            
    if not current_price:
        try:
            hist = t.history(period="1d")
            if not hist.empty:
                closes = hist['Close'].dropna()
                if not closes.empty:
                    current_price = float(closes.iloc[-1])
        except Exception: pass
            
    if not current_price:
        global YAHOO_CRUMB
        params = {"symbols": ticker}
            
        for attempt in range(2):
            if YAHOO_CRUMB: params["crumb"] = YAHOO_CRUMB
            try:
                res = session.get("https://query1.finance.yahoo.com/v7/finance/quote", params=params, headers=SEARCH_HEADERS, timeout=10)
                if res.status_code in (401, 403) and attempt == 0:
                    YAHOO_CRUMB = fetch_yahoo_crumb()
                    continue
                res.raise_for_status()
                quote = res.json().get('quoteResponse', {}).get('result', [])[0]
                current_price = quote.get('regularMarketPrice')
                if not previous_close:
                    previous_close = quote.get('regularMarketPreviousClose')
                break
            except Exception:
                break
        
    if not current_price:
        raise ValueError(f"Unable to fetch price for {ticker}")
    
    # Si no tenemos previous_close, intentar obtenerlo de historial
    if not previous_close:
        try:
            hist = t.history(period="2d")
            if len(hist) >= 2:
                previous_close = float(hist['Close'].iloc[-2])
        except Exception:
            pass
    
    return current_price, previous_close

def is_market_open(ticker_symbol):
    # Las criptomonedas y pares de divisas (ej. BTC-USD) cotizan 24/7
    if '-' in ticker_symbol:
        return True

    try:
        info = yf.Ticker(ticker_symbol).info
        if info.get('quoteType') == 'CRYPTOCURRENCY':
            return True
            
        tz_name = info.get('exchangeTimezoneName')
        if not tz_name:
            return True
            
        import pytz
        from datetime import datetime
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        
        if now.weekday() > 4:
            return False
            
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    except Exception:
        return True