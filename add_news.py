def add_fetch_news():
    with open('finance_api.py', 'r', encoding='utf-8') as f:
        code = f.read()

    news_func = """
def fetch_news(ticker, limit=3):
    try:
        import yfinance as yf
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
"""

    if 'def fetch_news' not in code:
        code += '\n' + news_func
        with open('finance_api.py', 'w', encoding='utf-8') as f:
            f.write(code)

if __name__ == '__main__':
    add_fetch_news()
