"""네이버 금융 수집 (표준 라이브러리만 사용).

- 상한가 종목: https://finance.naver.com/sise/sise_upper.naver  (시트 0.금일의상한가종목 과 동일 출처)
- 일별 시세  : fchart API, 실패 시 https://finance.naver.com/item/sise_day.naver (시트와 동일 출처)
"""
import re
import time
import urllib.request
from html.parser import HTMLParser

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch(url, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": "https://finance.naver.com/"})
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
                charset = r.headers.get_content_charset()
            for enc in [charset, "utf-8", "euc-kr", "cp949"]:
                if not enc:
                    continue
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"fetch 실패: {url} ({last})")


class _Rows(HTMLParser):
    """HTML의 모든 <tr>을 (셀 텍스트 리스트, 종목코드, 직전 제목) 으로 추출."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._cells = None
        self._buf = None
        self._code = None
        self._head = None
        self.heading = ""

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._cells, self._code = [], None
        elif tag in ("td", "th") and self._cells is not None:
            self._buf = []
        elif tag == "a" and self._cells is not None:
            m = re.search(r"code=(\w{6})", dict(attrs).get("href") or "")
            if m:
                self._code = m.group(1)
        elif tag in ("h3", "h4", "caption"):
            self._head = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._buf is not None and self._cells is not None:
            self._cells.append(" ".join("".join(self._buf).split()))
            self._buf = None
        elif tag == "tr" and self._cells is not None:
            self.rows.append((self._cells, self._code, self.heading))
            self._cells = None
        elif tag in ("h3", "h4", "caption") and self._head is not None:
            text = "".join(self._head)
            if "코스닥" in text:
                self.heading = "코스닥"
            elif "코스피" in text:
                self.heading = "코스피"
            self._head = None

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)
        if self._head is not None:
            self._head.append(data)


def _num(text, as_float=False):
    s = re.sub(r"[^0-9.\-]", "", text or "")
    if s in ("", "-", "."):
        return None
    try:
        return float(s) if as_float else int(float(s))
    except ValueError:
        return None


def parse_upper(html):
    """상한가 페이지 → [{market, code, name, streak, total, close, change, pct, volume, open, high, low}]"""
    p = _Rows()
    p.feed(html)
    out, seen = [], set()
    for cells, code, market in p.rows:
        # 열: N, 연속, 누적, 종목명, 현재가, 전일비, 등락률, 거래량, 시가, 고가, 저가, PER
        if not code or len(cells) < 11 or code in seen:
            continue
        close = _num(cells[4])
        if close is None:
            continue
        seen.add(code)
        out.append({
            "market": market, "code": code, "name": cells[3],
            "streak": _num(cells[1]), "total": _num(cells[2]),
            "close": close, "change": _num(cells[5]),
            "pct": _num(cells[6], as_float=True), "volume": _num(cells[7]),
            "open": _num(cells[8]), "high": _num(cells[9]), "low": _num(cells[10]),
        })
    return out


def get_upper_limit():
    return parse_upper(fetch("https://finance.naver.com/sise/sise_upper.naver"))


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


def parse_sise_day(html):
    p = _Rows()
    p.feed(html)
    rows = []
    for cells, _, _ in p.rows:
        # 열: 날짜, 종가, 전일비, 시가, 고가, 저가, 거래량
        if len(cells) < 7 or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
            continue
        rows.append({"date": cells[0].replace(".", "-"), "close": _num(cells[1]),
                     "open": _num(cells[3]), "high": _num(cells[4]),
                     "low": _num(cells[5]), "volume": _num(cells[6])})
    return sorted(rows, key=lambda r: r["date"])


def get_daily(code, days=30):
    """일별 시세(과거→최근). 최근 약 days 달력일."""
    end = time.strftime("%Y%m%d", time.gmtime(time.time() + 9 * 3600))
    start = time.strftime("%Y%m%d", time.gmtime(time.time() + 9 * 3600 - days * 86400))
    try:
        rows = parse_fchart(fetch(
            "https://fchart.stock.naver.com/siseJson.naver?symbol=%s&requestType=1"
            "&startTime=%s&endTime=%s&timeframe=day" % (code, start, end)))
        if len(rows) >= 4:
            return rows
    except Exception:  # noqa: BLE001
        pass
    return parse_sise_day(fetch("https://finance.naver.com/item/sise_day.naver?code=%s&page=1" % code))
