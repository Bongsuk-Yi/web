"""5돌이 일일 배치.

1) 당일 상한가 종목을 DB(data/upper_limit.csv)에 누적 저장
2) 최근 N거래일(기본 5) 상한가 종목의 내일 5일선을 예측해 1차/2차 매수가·매도가 계산
3) 계산값을 그날 기준으로 고정 저장(data/signals.csv, latest.json, latest.csv)
   → 시트에서 '수동 복사'하던 감시 Dashboard 값이 자동으로 고정됨
"""
import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
import naver  # noqa: E402
import rules  # noqa: E402

UPPER_COLS = ["date", "market", "code", "name", "streak", "total", "close",
              "change", "pct", "volume", "open", "high", "low"]
SIGNAL_COLS = ["date", "code", "name", "market", "limit_date", "limit_count",
               "close", "low", "high", "ma5", "gap", "pred_ma5",
               "buy1", "buy2", "sell", "buy1_pct", "buy2_pct", "sell_pct",
               "prev_buy1", "prev_buy2", "prev_sell",
               "touch_buy1", "touch_buy2", "touch_sell", "status"]
KO = {"date": "기준일", "code": "종목코드", "name": "종목", "market": "시장",
      "limit_date": "상한가일", "limit_count": "상한가횟수", "close": "종가",
      "low": "당일저가", "high": "당일고가", "ma5": "금일5일선", "gap": "이격률",
      "pred_ma5": "내일5일선(예측)", "buy1": "1차매수가", "buy2": "2차매수가",
      "sell": "매도가(5일선)", "buy1_pct": "1차 종가대비", "buy2_pct": "2차 종가대비",
      "sell_pct": "5일선 종가대비", "prev_buy1": "전일 1차매수가",
      "prev_buy2": "전일 2차매수가", "prev_sell": "전일 매도가",
      "touch_buy1": "1차매수 터치", "touch_buy2": "2차매수 터치",
      "touch_sell": "5일선 터치", "status": "상태"}


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, cols, header=None):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header or cols)
        for r in rows:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])


def build_signal(date, item, daily, prev, cfg):
    """한 종목의 당일 분석 + 내일 매매가. daily: 과거→최근 시세."""
    daily = [d for d in daily if d["date"] <= date and d.get("close")]
    closes = [d["close"] for d in daily]
    today = daily[-1]
    pred = rules.predict_ma5(closes)
    buy1, buy2, sell = rules.prices_from_pred(
        pred, cfg["buy1_ratio"], cfg["buy2_ratio"], cfg["tick_mode"])
    close = today["close"]
    m5 = rules.ma5(closes)
    gap = None if m5 is None else round(close / m5 - 1, 4)
    row = {
        "date": date, "code": item["code"], "name": item["name"],
        "market": item["market"], "limit_date": item["limit_date"],
        "limit_count": item["limit_count"], "close": close,
        "low": today["low"], "high": today["high"],
        "ma5": None if m5 is None else round(m5, 1), "gap": gap,
        "pred_ma5": round(pred, 1), "buy1": buy1, "buy2": buy2, "sell": sell,
        "buy1_pct": round(buy1 / close - 1, 4),
        "buy2_pct": round(buy2 / close - 1, 4),
        "sell_pct": round(sell / close - 1, 4),
    }
    # 전일에 고정해 둔 매매가를 오늘 저가/고가가 건드렸는지
    t1 = t2 = ts = ""
    if prev:
        row["prev_buy1"], row["prev_buy2"], row["prev_sell"] = (
            prev["buy1"], prev["buy2"], prev["sell"])
        t1 = "O" if today["low"] <= int(prev["buy1"]) else ""
        t2 = "O" if today["low"] <= int(prev["buy2"]) else ""
        ts = "O" if today["high"] >= int(prev["sell"]) else ""
    row["touch_buy1"], row["touch_buy2"], row["touch_sell"] = t1, t2, ts
    # 시트 2.Analysis 의 매수대기목록 기준
    status = ""
    if gap is not None:
        if t1 == "O" and gap < cfg["gap_wait"]:
            status = "매수선터치"
        elif gap < cfg["gap_near"]:
            status = "5일선근접"
        elif gap < cfg["gap_wait"]:
            status = "대기"
    row["status"] = status
    return row


def main():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    os.makedirs(DATA, exist_ok=True)
    errors = []

    # 거래일 달력: 삼성전자 일별 시세의 날짜
    cal = [d["date"] for d in naver.get_daily("005930", days=40)]
    if not cal:
        raise SystemExit("거래일을 확인하지 못했습니다")
    date = cal[-1]

    # 1) 상한가 종목 DB 누적
    upper_path = os.path.join(DATA, "upper_limit.csv")
    upper_db = read_csv(upper_path)
    try:
        today_upper = naver.get_upper_limit()
    except Exception as e:  # noqa: BLE001
        today_upper = []
        errors.append(f"상한가 목록 수집 실패: {e}")
    upper_db = [r for r in upper_db if r["date"] != date]
    for u in today_upper:
        upper_db.append(dict(u, date=date))
    upper_db.sort(key=lambda r: (r["date"], r["code"]), reverse=True)
    write_csv(upper_path, upper_db, UPPER_COLS)

    # 2) 감시 대상 = 최근 N거래일 안에 상한가를 친 종목
    window = set(cal[-cfg["watch_days"]:])
    excluded = set(cfg.get("exclude_codes", []))
    watch = {}
    for r in sorted(upper_db, key=lambda r: r["date"]):
        if r["date"] not in window or r["code"] in excluded:
            continue
        w = watch.setdefault(r["code"], {"code": r["code"], "limit_count": 0})
        w.update(name=r["name"], market=r["market"], limit_date=r["date"])
        w["limit_count"] += 1

    sig_path = os.path.join(DATA, "signals.csv")
    sig_db = [r for r in read_csv(sig_path) if r["date"] != date]
    prev_by_code = {}
    for r in sorted(sig_db, key=lambda r: r["date"]):
        prev_by_code[r["code"]] = r
    prev_date = cal[-2] if len(cal) > 1 else None

    signals = []
    for code, item in watch.items():
        try:
            daily = naver.get_daily(code)
            prev = prev_by_code.get(code)
            if prev and prev["date"] != prev_date:
                prev = None
            signals.append(build_signal(date, item, daily, prev, cfg))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{item.get('name')}({code}): {e}")
        time.sleep(0.2)
    signals.sort(key=lambda r: (r["gap"] is None, r["gap"] if r["gap"] is not None else 0))

    # 3) 고정 저장
    sig_db = signals + sig_db
    sig_db.sort(key=lambda r: r["date"], reverse=True)
    write_csv(sig_path, sig_db, SIGNAL_COLS)
    write_csv(os.path.join(DATA, "latest.csv"), signals, SIGNAL_COLS,
              header=[KO[c] for c in SIGNAL_COLS])
    latest = {
        "date": date,
        "generated_at": time.strftime("%Y-%m-%d %H:%M KST", time.gmtime(time.time() + 9 * 3600)),
        "config": cfg,
        "signals": signals,
        "upper_today": [r for r in upper_db if r["date"] == date],
        "upper_recent": [r for r in upper_db if r["date"] in window],
        "errors": errors,
    }
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)
    print(f"[{date}] 상한가 {len(latest['upper_today'])}종목, 감시 {len(signals)}종목, 오류 {len(errors)}건")
    for e in errors:
        print("  !", e)


if __name__ == "__main__":
    main()
