"""파서·신호 계산 검증(네트워크 불필요). 실행: python tests/test_parse.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import naver, run_daily

ITEMS = [
 {"itemname": "디와이에이", "itemcode": "002880", "sosok": "0", "upDownGb": "1", "upperLimitPrice": "4030",
  "nowPrice": "4030", "openPrice": "3100", "highPrice": "4030", "lowPrice": "3075", "prevChangePrice": "930",
  "prevChangeRate": "30.0", "tradeVolume": "641665", "continualUpperLimit": "0", "accumUpper": "1"},
 {"itemname": "바이브컴퍼니", "itemcode": "301300", "sosok": "1", "upDownGb": "1", "upperLimitPrice": "2365",
  "nowPrice": "2365", "openPrice": "1900", "highPrice": "2365", "lowPrice": "1880", "prevChangePrice": "545",
  "prevChangeRate": "29.95", "tradeVolume": "649815", "continualUpperLimit": "1", "accumUpper": "2"},
 {"itemname": "상승만", "itemcode": "000001", "sosok": "0", "upDownGb": "2", "upperLimitPrice": "1300",
  "nowPrice": "1250", "openPrice": "1000", "highPrice": "1300", "lowPrice": "1000", "prevChangePrice": "250",
  "prevChangeRate": "25.0", "tradeVolume": "1"},
]
u = naver.parse_upper(ITEMS)
assert [(x["market"], x["code"], x["name"], x["close"], x["change"], x["pct"], x["low"], x["total"]) for x in u] == [
    ("코스피", "002880", "디와이에이", 4030, 930, 30.0, 3075, 1),
    ("코스닥", "301300", "바이브컴퍼니", 2365, 545, 29.95, 1880, 2)], u

FCHART = """[['날짜', '시가', '고가', '저가', '종가', '거래량', '외국인소진율'],
["20261112", 100, 120, 95, 110, 1000, 1.5],
["20261113", 110, 143, 108, 143, 2000, 1.6]]"""
d = naver.parse_fchart(FCHART)
assert d[-1] == {"date": "2026-11-13", "open": 110, "high": 143, "low": 108, "close": 143, "volume": 2000}

API = [{"localDate": "20261113", "closePrice": 129500.0, "openPrice": 128000.0, "highPrice": 130000.0,
        "lowPrice": 127500.0, "accumulatedTradingVolume": 12345}]
s = naver.parse_chart_api(API)
assert s == [{"date": "2026-11-13", "open": 128000, "high": 130000, "low": 127500, "close": 129500, "volume": 12345}]

cfg = {"buy1_ratio": 0.9385, "buy2_ratio": 0.948, "tick_mode": "sheet", "gap_near": 0.05, "gap_wait": 0.10}
daily = [{"date": f"2026-11-{9+i:02d}", "close": c, "low": c - 100, "high": c + 100}
         for i, c in enumerate([6000, 6200, 6400, 6500, 6400])]
item = {"code": "006910", "name": "보성파워텍", "market": "코스피", "limit_date": "2026-11-10", "limit_count": 1}
prev = {"buy1": "6350", "buy2": "6000", "sell": "6600"}
r = run_daily.build_signal("2026-11-13", item, daily, prev, cfg)
assert r["pred_ma5"] == (6400 * 2 + 6500 + 6400 + 6200) / 5 == 6380.0
assert (r["buy1"], r["buy2"], r["sell"]) == (5990, 5680, 6380), r
assert r["ma5"] == 6300.0 and r["gap"] == round(6400 / 6300 - 1, 4)
assert (r["touch_buy1"], r["touch_buy2"], r["touch_sell"]) == ("O", "", ""), r
assert r["status"] == "매수선터치"
print("OK - 파서/신호 계산")
