import logging
import os
import re
import time
from typing import Final, Optional, Tuple, List, Dict, Any
from urllib3.util.retry import Retry
import requests
from requests.adapters import HTTPAdapter
import yfinance as yf

logger: logging.Logger = logging.getLogger(__name__)

# --- External Configurable Endpoints ---
YAHOO_FC_URL: Final[str] = os.getenv("YAHOO_FC_URL", "https://fc.yahoo.com")
YAHOO_CRUMB_URL: Final[str] = os.getenv("YAHOO_CRUMB_URL", "https://query1.finance.yahoo.com/v1/test/getcrumb")
YAHOO_SEARCH_URL: Final[str] = os.getenv("YAHOO_SEARCH_URL", "https://query1.finance.yahoo.com/v1/finance/search")
YAHOO_SEARCH_FALLBACK_URL: Final[str] = os.getenv(
    "YAHOO_SEARCH_FALLBACK_URL", "https://query2.finance.yahoo.com/v1/finance/search"
)
YAHOO_QUOTE_URL: Final[str] = os.getenv("YAHOO_QUOTE_URL", "https://query1.finance.yahoo.com/v7/finance/quote")
JUSTETF_URL_TEMPLATE: Final[str] = os.getenv(
    "JUSTETF_URL_TEMPLATE", "https://www.justetf.com/en/etf-profile.html?isin="
)

SEARCH_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

EUR_HIGH_QUALITY_SUFFIXES: Final[Tuple[str, ...]] = ('.DE', '.MI', '.PA', '.AS', '.MC')
EUR_LOW_QUALITY_SUFFIXES: Final[Tuple[str, ...]] = ('.SG', '.F')
USD_SUFFIXES: Final[Tuple[str, ...]] = ('', '.NX', '.O')


class YahooMarketService:
    """Encapsulates Yahoo Finance and JustETF market data fetching with session & crumb caching."""

    def __init__(self) -> None:
        self.session = self._init_session()
        self._crumb: Optional[str] = None
        self._names_cache: Dict[str, str] = {}

    @staticmethod
    def _init_session() -> requests.Session:
        s = requests.Session()
        retries = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        s.mount("https://", HTTPAdapter(max_retries=retries))
        return s

    def get_crumb(self, force_refresh: bool = False) -> Optional[str]:
        if self._crumb and not force_refresh:
            return self._crumb

        try:
            self.session.get(YAHOO_FC_URL, headers=SEARCH_HEADERS, timeout=10)
            time.sleep(0.5)
            res = self.session.get(YAHOO_CRUMB_URL, headers=SEARCH_HEADERS, timeout=10)
            if res.status_code == 200:
                self._crumb = res.text.strip()
                return self._crumb
            logger.debug("Crumb fetch returned HTTP %s", res.status_code)
        except requests.RequestException as err:
            logger.debug("Failed to fetch Yahoo crumb: %s", err)
        return None

    def resolve_ticker(self, isin_or_ticker: str) -> str:
        if not self._is_isin(isin_or_ticker):
            return isin_or_ticker

        for endpoint in (YAHOO_SEARCH_URL, YAHOO_SEARCH_FALLBACK_URL):
            symbol = self._query_isin_endpoint(endpoint, isin_or_ticker)
            if symbol:
                return symbol
        return isin_or_ticker

    @staticmethod
    def _is_isin(identifier: str) -> bool:
        return len(identifier) == 12 and identifier[:2].isalpha() and identifier[2:].isalnum()

    def _query_isin_endpoint(self, url: str, isin: str) -> Optional[str]:
        try:
            res = self.session.get(url, params={"q": isin, "quotesCount": 5}, headers=SEARCH_HEADERS, timeout=10)
            if res.status_code != 200:
                return None
            quotes = res.json().get('quotes', [])
            best_q = self._select_best_quote(quotes)
            if not best_q:
                return None
            sym = best_q.get('symbol')
            name = best_q.get('longname') or best_q.get('shortname')
            if sym and name:
                self._names_cache[sym] = name
            return sym
        except requests.RequestException as err:
            logger.debug("Error querying ISIN at %s: %s", url, err)
            return None

    @staticmethod
    def _select_best_quote(quotes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best_q: Optional[Dict[str, Any]] = None
        for q in quotes:
            sym = q.get('symbol')
            if not sym:
                continue
            if not best_q:
                best_q = q
                continue
            curr_sym = best_q.get('symbol', '')
            is_curr_low = ('.SG' in curr_sym or 'PNK' in best_q.get('exchange', ''))
            is_new_high = ('.SG' not in sym and 'PNK' not in q.get('exchange', ''))
            if is_curr_low and is_new_high:
                best_q = q
        return best_q

    def find_symbol_by_name(self, name: str, target_currency: str) -> Optional[str]:
        if not name:
            return None

        candidates = self._fetch_search_candidates(name)
        ranked = self._rank_candidates(candidates, target_currency)
        return self._find_matching_currency_symbol(ranked, target_currency)

    def _fetch_search_candidates(self, name: str) -> List[str]:
        try:
            res = self.session.get(
                YAHOO_SEARCH_URL,
                params={"q": name, "quotesCount": 15},
                headers=SEARCH_HEADERS,
                timeout=10
            )
            res.raise_for_status()
            quotes = res.json().get('quotes', [])
            return [q.get('symbol') for q in quotes if q.get('symbol')]
        except requests.RequestException as err:
            logger.debug("Error searching candidates for %s: %s", name, err)
            return []

    def _rank_candidates(self, candidates: List[str], target_currency: str) -> List[str]:
        def rank_candidate(sym: str) -> int:
            if target_currency == 'EUR':
                if any(sym.endswith(suf) for suf in EUR_HIGH_QUALITY_SUFFIXES):
                    return 0
                if any(sym.endswith(suf) for suf in EUR_LOW_QUALITY_SUFFIXES):
                    return 1
            elif target_currency == 'USD':
                if any(sym.endswith(suf) for suf in USD_SUFFIXES) or '.' not in sym:
                    return 0
            return 2

        return sorted(candidates, key=rank_candidate)

    @staticmethod
    def _find_matching_currency_symbol(candidates: List[str], target_currency: str) -> Optional[str]:
        for sym in candidates[:5]:
            try:
                info = yf.Ticker(sym).info
                if info.get('currency') == target_currency:
                    return sym
            except Exception as err:
                logger.debug("Failed reading currency for %s: %s", sym, err)
        return None

    def fetch_asset_info(self, ticker: str, isin: Optional[str] = None) -> Tuple[str, str]:
        name = self._names_cache.get(ticker, "")
        currency = ""

        try:
            info = yf.Ticker(ticker).info
            if not name:
                name = info.get('longName') or info.get('shortName') or ""
            currency = info.get('currency') or ""
        except Exception as err:
            logger.debug("Failed reading yfinance info for %s: %s", ticker, err)

        if not name:
            target_isin = isin if (isin and len(isin) == 12) else (ticker if len(ticker) == 12 else None)
            if target_isin and self._is_isin(target_isin):
                name = self._fetch_justetf_name(target_isin)

        return name, currency

    def _fetch_justetf_name(self, isin: str) -> str:
        try:
            url = f"{JUSTETF_URL_TEMPLATE}{isin}"
            res = self.session.get(url, headers=SEARCH_HEADERS, timeout=10)
            if res.status_code != 200:
                return ""
            match = re.search(r'<title>(.*?)</title>', res.text)
            if not match:
                return ""
            parts = match.group(1).split('|')
            if len(parts) >= 3 and isin in parts[2]:
                return parts[0].strip()
        except requests.RequestException as err:
            logger.debug("JustETF request failed for %s: %s", isin, err)
        return ""

    def fetch_price(self, ticker: str) -> Tuple[float, Optional[float]]:
        t = yf.Ticker(ticker)
        current_price, previous_close = self._price_from_yfinance(t)

        if not current_price:
            current_price, previous_close = self._price_from_yahoo_api(ticker, previous_close)

        if not current_price:
            raise ValueError(f"Unable to fetch price for {ticker}")

        if not previous_close:
            previous_close = self._fallback_previous_close(t)

        return current_price, previous_close

    @staticmethod
    def _price_from_yfinance(t: yf.Ticker) -> Tuple[Optional[float], Optional[float]]:
        curr: Optional[float] = None
        prev: Optional[float] = None
        try:
            info = t.info
            curr = info.get('regularMarketPrice')
            prev = info.get('regularMarketPreviousClose') or info.get('previousClose')
        except Exception as err:
            logger.debug("yfinance info failed: %s", err)

        if not curr:
            try:
                curr = t.fast_info.get('last_price')
            except Exception as err:
                logger.debug("yfinance fast_info failed: %s", err)

        if not curr:
            try:
                hist = t.history(period="1d")
                if not hist.empty and not hist['Close'].dropna().empty:
                    curr = float(hist['Close'].dropna().iloc[-1])
            except Exception as err:
                logger.debug("yfinance 1d history failed: %s", err)

        return curr, prev

    def _price_from_yahoo_api(self, ticker: str, existing_prev: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
        curr: Optional[float] = None
        prev: Optional[float] = existing_prev
        params: Dict[str, Any] = {"symbols": ticker}

        for attempt in range(2):
            crumb = self.get_crumb(force_refresh=(attempt > 0))
            if crumb:
                params["crumb"] = crumb
            try:
                res = self.session.get(YAHOO_QUOTE_URL, params=params, headers=SEARCH_HEADERS, timeout=10)
                if res.status_code in (401, 403) and attempt == 0:
                    continue
                res.raise_for_status()
                quotes = res.json().get('quoteResponse', {}).get('result', [])
                if quotes:
                    curr = quotes[0].get('regularMarketPrice')
                    if not prev:
                        prev = quotes[0].get('regularMarketPreviousClose')
                break
            except requests.RequestException as err:
                logger.debug("Direct quote attempt failed for %s: %s", ticker, err)
                break

        return curr, prev

    @staticmethod
    def _fallback_previous_close(t: yf.Ticker) -> Optional[float]:
        try:
            hist = t.history(period="2d")
            if len(hist) >= 2:
                return float(hist['Close'].iloc[-2])
        except Exception as err:
            logger.debug("2d history previous close fallback failed: %s", err)
        return None


# Global singleton service for app-wide use
_service = YahooMarketService()
session = _service.session
YAHOO_CRUMB = _service.get_crumb()
RESOLVED_NAMES_CACHE = _service._names_cache

# Exported module-level functions preserving backward compatibility
resolve_ticker = _service.resolve_ticker
find_symbol_by_name_and_currency = _service.find_symbol_by_name
fetch_asset_info = _service.fetch_asset_info
fetch_price = _service.fetch_price


def fetch_historical_price(ticker: str, date_str: str) -> Optional[float]:
    """Fetches closing price for a specific historical date."""
    try:
        from datetime import datetime, timedelta
        req_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = req_date - timedelta(days=5)
        end_date = req_date + timedelta(days=1)
        
        t = yf.Ticker(ticker)
        hist = t.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        if not hist.empty and not hist['Close'].dropna().empty:
            return float(hist['Close'].dropna().iloc[-1])
    except Exception as err:
        logger.debug("Failed fetching historical price for %s @ %s: %s", ticker, date_str, err)
    return None


def fetch_news(ticker: str, limit: int = 3) -> List[Dict[str, Optional[str]]]:
    """Fetches recent news items for a given ticker."""
    try:
        news = yf.Ticker(ticker).news
        if not news:
            return []

        parsed: List[Dict[str, Optional[str]]] = []
        for n in news[:limit]:
            title = n.get('title')
            if title:
                parsed.append({
                    "title": title,
                    "publisher": n.get('publisher'),
                    "link": n.get('link')
                })
        return parsed
    except Exception as err:
        logger.debug("Failed fetching news for %s: %s", ticker, err)
        return []


def is_market_open(ticker_symbol: str) -> bool:
    """Checks whether the market for the given ticker is currently open."""
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
    except Exception as err:
        logger.debug("Error checking market hours for %s: %s", ticker_symbol, err)
        return True