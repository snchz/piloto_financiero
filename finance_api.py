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

def resolve_ticker(isin_or_ticker):
    if len(isin_or_ticker) == 12 and isin_or_ticker[:2].isalpha() and isin_or_ticker[2:].isdigit():
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
                for q in quotes:
                    if sym := q.get('symbol'):
                        return sym
            except Exception:
                continue
        return None
    return isin_or_ticker

def fetch_asset_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        
        # Para los fondos de inversión, Yahoo Finance suele guardar el nombre real
        # en 'longName', mientras que 'shortName' a veces solo contiene el símbolo.
        # Priorizamos longName para obtener la descripción correcta.
        name = info.get('longName') or info.get('shortName') or ""
        currency = info.get('currency') or ""
        return name, currency
    except Exception:
        return "", ""

def fetch_historical_price(ticker, date_str):
    try:
        t = yf.Ticker(ticker)
        from datetime import datetime, timedelta
        start_date = datetime.strptime(date_str, '%Y-%m-%d')
        end_date = start_date + timedelta(days=7) # Margen amplio por festivos/fines de semana
        hist = t.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if not hist.empty:
            return float(hist['Close'].iloc[0])
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
            if not hist.empty: current_price = float(hist['Close'].iloc[-1])
        except Exception: pass
            
    if not current_price:
        params = {"symbols": ticker}
        if YAHOO_CRUMB: params["crumb"] = YAHOO_CRUMB
            
        try:
            res = session.get("https://query1.finance.yahoo.com/v7/finance/quote", params=params, headers=SEARCH_HEADERS, timeout=10)
            res.raise_for_status()
            quote = res.json().get('quoteResponse', {}).get('result', [])[0]
            current_price = quote.get('regularMarketPrice')
            if not previous_close:
                previous_close = quote.get('regularMarketPreviousClose')
        except Exception: pass
        
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