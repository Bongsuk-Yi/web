"""시트에 남아있는 실제 계산값과 일치하는지 검증. 실행: python tests/test_rules.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import rules

# (예측5일선, 1차매수가, 2차매수가, 매도가) — 시트 3.5돌이매매 W/T/V/X열 값
SHEET = [
    (117660, 110500, 104700, 117700),  # 신풍제약우
    (151600, 142300, 134900, 151600),  # 두산2우B
    (6402, 6010, 5700, 6410),          # 보성파워텍
    (7340, 6890, 6540, 7340),          # 한성기업
    (2048, 1925, 1825, 2050),          # 카이노스메드
]
for pred, b1, b2, sell in SHEET:
    got = rules.prices_from_pred(pred)
    assert got == (b1, b2, sell), (pred, got, (b1, b2, sell))

assert rules.predict_ma5([100, 110, 120, 130]) == (130 * 2 + 120 + 110 + 100) / 5
assert rules.ma5([1, 2, 3, 4, 5]) == 3
assert rules.ma5([1, 2, 3, 4]) is None
assert rules.tick_size(250000) == 500 and rules.tick_size(600000) == 1000
assert rules.tick_size(1500, "krx") == 1 and rules.tick_size(15000, "krx") == 10
print("OK - 시트 값과 일치")
