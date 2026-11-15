import os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naver
out = []
html = naver.fetch("https://finance.naver.com/sise/sise_upper.naver")
body = re.sub(r"<link[^>]*>|<script src[^>]*></script>", "", html)
out.append(f"len={len(html)} stripped={len(body)}")
for kw in ["itemCode", "상한가", "/api/", "stockName", "UPPER", "closePrice"]:
    idx = [m.start() for m in re.finditer(re.escape(kw), body)]
    out.append(f"## {kw}: {len(idx)}")
    for i in idx[:3]:
        out.append(body[max(0, i - 300): i + 700].replace("\n", " "))
urls = [
 "https://m.stock.naver.com/api/stocks/up/KOSPI?page=1&pageSize=5",
 "https://m.stock.naver.com/api/stocks/upperLimit/KOSPI?page=1&pageSize=5",
 "https://m.stock.naver.com/api/stocks/upper/KOSPI?page=1&pageSize=5",
 "https://m.stock.naver.com/api/stocks/high/KOSPI?page=1&pageSize=5",
 "https://m.stock.naver.com/api/stocks/priceTop/KOSPI?page=1&pageSize=5",
 "https://stock.naver.com/api/domestic/market/stock/default?tradeType=KRX&marketType=KOSPI&orderType=priceTop&startIdx=0&pageSize=5",
 "https://stock.naver.com/api/domestic/market/stock/default?tradeType=KRX&marketType=ALL&orderType=up&startIdx=0&pageSize=5",
 "https://finance.naver.com/sise/sise_rise.naver",
 "https://finance.naver.com/item/sise_day.naver?code=005930&page=1",
 "https://api.stock.naver.com/chart/domestic/item/005930/day?startDateTime=20261101&endDateTime=20261115",
]
for u in urls:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": naver.UA, "Referer": "https://m.stock.naver.com/"})
        with urllib.request.urlopen(req, timeout=20) as r:
            t = r.read().decode("utf-8", "replace")
            out.append(f"## {u}\n{r.status} len={len(t)} tables={t.count('<table')}\n{t[:1500]}")
    except Exception as e:
        out.append(f"## {u}\nERR {e}")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "_debug.txt"), "w", encoding="utf-8").write("\n".join(out))
