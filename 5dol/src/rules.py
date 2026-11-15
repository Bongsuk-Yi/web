"""5돌이 매매 규칙 (구글시트 '5돌 돌려차기'의 3.5돌이매매 / 호가계산 시트와 동일).

- 내일 5일선(예측) = (당일종가×2 + 전일종가 + 2일전종가 + 3일전종가) / 5
  (내일 종가가 오늘 종가와 같다고 가정)
- 1차매수가 = 내일 5일선(예측) × 93.85%
- 2차매수가 = 1차매수가 × 94.8%
- 매도가     = 내일 5일선(예측)
- 세 가격 모두 호가단위로 올림(CEILING)
"""
import math


def tick_size(price, mode="sheet"):
    """호가단위. mode='sheet' 는 시트의 CHOOSE 수식과 동일(20만원 이상만 실제 KRX 단위로 보정),
    mode='krx' 는 2023년 개편된 실제 KRX 호가단위."""
    if mode == "krx":
        bands = [(2000, 1), (5000, 5), (20000, 10), (50000, 50),
                 (200000, 100), (500000, 500)]
        top = 1000
    else:
        bands = [(1000, 1), (5000, 5), (10000, 10), (50000, 50),
                 (200000, 100), (500000, 500)]
        top = 1000
    for limit, tick in bands:
        if price < limit:
            return tick
    return top


def ceil_tick(price, mode="sheet"):
    """호가단위 올림 = 시트의 CEILING(가격, 호가)."""
    t = tick_size(price, mode)
    return int(math.ceil(price / t - 1e-9) * t)


def predict_ma5(closes):
    """closes: 과거→최근 순서의 종가 리스트(최소 4개). 내일 5일선 예측값."""
    if len(closes) < 4:
        raise ValueError("종가가 4일치 이상 필요합니다")
    today, d1, d2, d3 = closes[-1], closes[-2], closes[-3], closes[-4]
    return (today * 2 + d1 + d2 + d3) / 5


def ma5(closes):
    """오늘 기준 5일선(종가 5개 평균). 5개 미만이면 None."""
    if len(closes) < 5:
        return None
    return sum(closes[-5:]) / 5


def prices_from_pred(pred, buy1_ratio=0.9385, buy2_ratio=0.948, mode="sheet"):
    """예측 5일선 → (1차매수가, 2차매수가, 매도가) 호가 보정값."""
    raw1 = pred * buy1_ratio
    raw2 = raw1 * buy2_ratio
    return ceil_tick(raw1, mode), ceil_tick(raw2, mode), ceil_tick(pred, mode)
