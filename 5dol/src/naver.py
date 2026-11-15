"""네이버 증권 수집 (표준 라이브러리만 사용).

시트가 쓰던 finance.naver.com 의 HTML 표(sise_upper, sise_day)는 개편으로 사라져
IMPORTHTML 이 #N/A 가 된다. 같은 데이터를 네이버 증권 JSON API 에서 가져온다.

- 상한가 종목: stock.naver.com 상승률 순위 중 상한(upDownGb=1) 종목
- 일별 시세  : fchart API, 실패 시 api.stock.naver.com 차트 API
"""
import json
import re
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
UPPER_URL = ("https://stock.naver.com/api/domestic/market/stock/default"
             "?tradeType=KRX&marketType=ALL&orderType=up&startIdx=0&pageSize=100")
MARKET = {"0": "코스피", "1": "코스닥"}


def fetch(url, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://stock.naver.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"fetch 실패: {url} ({last})")


def _num(v, as_float=False):
    s = re.sub(r"[^0-9.\-]", "", str(v if v is not None else ""))
    if s in ("", "-", "."):
        return None
    try:
        return float(s) if as_float else int(float(s))
    except ValueError:
        return None


def parse_upper(items):
    """상승률 순위 JSON → 상한가 종목만.
    [{market, code, name, streak, total, close, change, pct, volume, open, high, low}]"""
    out = []
    for it in items:
        close, limit = _num(it.get("nowPrice")), _num(it.get("upperLimitPrice"))
        if str(it.get("upDownGb")) != "1" and not (close and close == limit):
            continue
        out.append({
            "market": MARKET.get(str(it.get("sosok")), ""),
            "code": it.get("itemcode"), "name": it.get("itemname"),
            "streak": _num(it.get("continualUpperLimit")),
            "total": _num(it.get("accumUpper")),
            "close": close, "change": _num(it.get("prevChangePrice")),
            "pct": _num(it.get("prevChangeRate"), as_float=True),
            "volume": _num(it.get("tradeVolume")),
            "open": _num(it.get("openPrice")), "high": _num(it.get("highPrice")),
            "low": _num(it.get("lowPrice")),
        })
    return out


def get_upper_limit():
    items = json.loads(fetch(UPPER_URL))
    if not isinstance(items, list) or not items:
        raise RuntimeError("상승률 순위 응답이 비어 있습니다")
    return parse_upper(items)


def parse_fchart(text):
    rows = []
    for m in re.finditer(
            r'\[\s*"?(\d{8})"?\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)',
            text):
        d = m.group(1)
        o, h, l, c, v = (int(float(x)) for x in m.groups()[1:])
        rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "open": o, "high": h,
                     "low": l, "close": c, "volume": v})
    return sorted(rows, key=lambda r: r["date"])


def parse_chart_api(items):
    rows = []
    for it in items:
        d = str(it["localDate"])
        rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                     "open": _num(it.get("openPrice")), "high": _num(it.get("highPrice")),
                     "low": _num(it.get("lowPrice")), "close": _num(it.get("closePrice")),
                     "volume": _num(it.get("accumulatedTradingVolume"))})
    return sorted(rows, key=lambda r: r["date"])


def get_daily(code, days=30):
    """일별 시세(과거→최근). 최근 약 days 달력일."""
    now = time.time() + 9 * 3600
    end = time.strftime("%Y%m%d", time.gmtime(now))
    start = time.strftime("%Y%m%d", time.gmtime(now - days * 86400))
    try:
        rows = parse_fchart(fetch(
            "https://fchart.stock.naver.com/siseJson.naver?symbol=%s&requestType=1"
            "&startTime=%s&endTime=%s&timeframe=day" % (code, start, end)))
        if len(rows) >= 4:
            return rows
    except Exception:  # noqa: BLE001
        pass
    return parse_chart_api(json.loads(fetch(
        "https://api.stock.naver.com/chart/domestic/item/%s/day"
        "?startDateTime=%s&endDateTime=%s" % (code, start, end))))
