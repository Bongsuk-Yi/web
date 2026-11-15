"""파서·신호 계산 검증(네트워크 불필요). 실행: python tests/test_parse.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import naver, run_daily

UPPER = """
<div class="box_type_l"><h4 class="top_tlt"><em>코스피</em></h4>
<table class="type_5"><tr><th>N</th><th>연속</th><th>누적</th><th>종목명</th><th>현재가</th>
<th>전일비</th><th>등락률</th><th>거래량</th><th>시가</th><th>고가</th><th>저가</th><th>PER</th></tr>
<tr><td class="no">1</td><td class="number">1</td><td class="number">2</td>
<td><a href="/item/main.naver?code=002880" class="tltle">디와이에이</a></td>
<td class="number">4,030</td><td class="number"><em><span class="blind">상한가</span></em>
<span class="tah p11 red02">930</span></td><td class="number"><span class="tah p11 red01">+30.00%</span></td>
<td class="number">635,297</td><td class="number">3,150</td><td class="number">4,030</td>
<td class="number">3,100</td><td class="number">N/A</td></tr></table></div>
<div class="box_type_l"><h4 class="top_tlt"><em>코스닥</em></h4><table class="type_5">
<tr><td class="no">1</td><td class="number">1</td><td class="number">1</td>
<td><a href="/item/main.naver?code=301300" class="tltle">바이브컴퍼니</a></td>
<td class="number">2,365</td><td class="number">상한가 545</td><td class="number">+29.95%</td>
<td class="number">649,815</td><td class="number">1,900</td><td class="number">2,365</td>
<td class="number">1,880</td><td class="number">-3.2</td></tr></table></div>"""
u = naver.parse_upper(UPPER)
assert [(x["market"], x["code"], x["name"], x["close"], x["change"], x["pct"], x["low"]) for x in u] == [
    ("코스피", "002880", "디와이에이", 4030, 930, 30.0, 3100),
    ("코스닥", "301300", "바이브컴퍼니", 2365, 545, 29.95, 1880)], u

FCHART = """[['날짜', '시가', '고가', '저가', '종가', '거래량', '외국인소진율'],
["20261112", 100, 120, 95, 110, 1000, 1.5],
["20261113", 110, 143, 108, 143, 2000, 1.6]]"""
d = naver.parse_fchart(FCHART)
assert d[-1] == {"date": "2026-11-13", "open": 110, "high": 143, "low": 108, "close": 143, "volume": 2000}

DAY = """<table><tr><th>날짜</th><th>종가</th><th>전일비</th><th>시가</th><th>고가</th><th>저가</th><th>거래량</th></tr>
<tr><td><span>2026.11.13</span></td><td><span>129,500</span></td><td>상승 <span>1,000</span></td>
<td><span>128,000</span></td><td><span>130,000</span></td><td><span>127,500</span></td><td><span>12,345</span></td></tr></table>"""
s = naver.parse_sise_day(DAY)
assert s == [{"date": "2026-11-13", "close": 129500, "open": 128000, "high": 130000, "low": 127500, "volume": 12345}]

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
