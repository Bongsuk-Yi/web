"""구글 시트(5dol)에 행을 직접 쌓는다.

- 상한가DB / 매매가이력 탭: 시트에 없는 날짜의 행만 맨 아래에 추가(누적)
- 매매가 탭: 최신 기준일 값으로 교체
환경변수 GSHEET_SA_KEY(서비스 계정 JSON 키)가 없으면 아무것도 하지 않는다.
"""
import csv
import datetime
import json
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
API = "https://sheets.googleapis.com/v4/spreadsheets/"

UPPER_KO = {"date": "상한가일", "market": "시장", "code": "종목코드", "name": "종목",
            "streak": "연속", "total": "누적", "close": "종가", "change": "전일비",
            "pct": "등락률", "volume": "거래량", "open": "시가", "high": "고가", "low": "저가"}
SIGNAL_KO = {"date": "기준일", "code": "종목코드", "name": "종목", "market": "시장",
             "limit_date": "상한가일", "limit_count": "상한가횟수", "close": "종가",
             "low": "당일저가", "high": "당일고가", "ma5": "금일5일선", "gap": "이격률",
             "pred_ma5": "내일5일선(예측)", "buy1": "1차매수가", "buy2": "2차매수가",
             "sell": "매도가(5일선)", "buy1_pct": "1차 종가대비", "buy2_pct": "2차 종가대비",
             "sell_pct": "5일선 종가대비", "prev_buy1": "전일 1차매수가",
             "prev_buy2": "전일 2차매수가", "prev_sell": "전일 매도가",
             "touch_buy1": "1차매수 터치", "touch_buy2": "2차매수 터치",
             "touch_sell": "5일선 터치", "status": "상태"}

PCT_KEYS = ["gap", "buy1_pct", "buy2_pct", "sell_pct"]   # 이격률, 1차/2차/5일선 종가대비


def read_csv(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cell(col, v):
    """종목코드는 앞자리 0이 지워지지 않도록 텍스트로 넣는다."""
    if col == "code":
        return "'" + v
    return v


def to_rows(records, ko):
    return [[cell(c, r.get(c, "")) for c in ko] for r in records]


def iso(v):
    """시트 A열 값(날짜 일련번호 또는 문자열) → YYYY-MM-DD"""
    if isinstance(v, (int, float)):
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(v))).isoformat()
    return str(v).strip()


class Sheet:
    def __init__(self, session, sheet_id):
        self.s, self.base = session, API + sheet_id

    def _rng(self, tab, a1):
        return urllib.parse.quote(f"'{tab}'!{a1}", safe="")

    def _call(self, method, path, **kw):
        r = self.s.request(method, self.base + path, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"Sheets API {r.status_code}: {r.text[:300]}")
        return r.json()

    def ensure_tabs(self, tabs):
        have = {s["properties"]["title"] for s in
                self._call("GET", "?fields=sheets.properties.title")["sheets"]}
        reqs = [{"addSheet": {"properties": {"title": t}}} for t in tabs if t not in have]
        if reqs:
            self._call("POST", ":batchUpdate", json={"requests": reqs})

    def sheet_ids(self):
        d = self._call("GET", "?fields=sheets.properties.title,sheets.properties.sheetId")
        return {x["properties"]["title"]: x["properties"]["sheetId"] for x in d["sheets"]}

    def format_percent(self, tab, cols):
        """열 전체(머리글 제외)에 -16.2% 형식 적용. 새로 추가되는 행에도 그대로 적용된다."""
        sid = self.sheet_ids()[tab]
        reqs = [{"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 1,
                      "startColumnIndex": c, "endColumnIndex": c + 1},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}},
            "fields": "userEnteredFormat.numberFormat"}} for c in cols]
        self._call("POST", ":batchUpdate", json={"requests": reqs})

    def get(self, tab, a1, render="UNFORMATTED_VALUE"):
        return self._call("GET", f"/values/{self._rng(tab, a1)}", params={
            "valueRenderOption": render, "dateTimeRenderOption": "SERIAL_NUMBER"}).get("values", [])

    def clear(self, tab):
        self._call("POST", f"/values/{self._rng(tab, 'A:Z')}:clear", json={})

    def put(self, tab, rows):
        self._call("PUT", f"/values/{self._rng(tab, 'A1')}",
                   params={"valueInputOption": "USER_ENTERED"}, json={"values": rows})

    def append(self, tab, rows):
        self._call("POST", f"/values/{self._rng(tab, 'A1')}:append", params={
            "valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            json={"values": rows})


def sync_log(sh, tab, records, ko):
    """누적 탭: 시트에 없는 날짜의 행만 추가. 추가한 행 수를 돌려준다."""
    header = list(ko.values())
    a1 = sh.get(tab, "A1", render="FORMULA")
    first = str(a1[0][0]) if a1 and a1[0] else ""
    if first != header[0]:           # 비어 있거나 IMPORTDATA 수식이면 새로 시작
        sh.clear(tab)
        sh.put(tab, [header])
        have = set()
    else:
        have = {iso(r[0]) for r in sh.get(tab, "A2:A") if r}
    new = sorted((r for r in records if r["date"] not in have), key=lambda r: r["date"])
    if new:
        sh.append(tab, to_rows(new, ko))
    return len(new)


def sync_latest(sh, tab, records, ko):
    sh.clear(tab)
    sh.put(tab, [list(ko.values())] + to_rows(records, ko))
    return len(records)


def run(session, sheet_id):
    sh = Sheet(session, sheet_id)
    sh.ensure_tabs(["매매가", "상한가DB", "매매가이력"])
    signals = read_csv("signals.csv")
    latest_date = max((r["date"] for r in signals), default=None)
    n1 = sync_log(sh, "상한가DB", read_csv("upper_limit.csv"), UPPER_KO)
    n2 = sync_log(sh, "매매가이력", signals, SIGNAL_KO)
    n3 = sync_latest(sh, "매매가", [r for r in signals if r["date"] == latest_date], SIGNAL_KO)
    pct_cols = [list(SIGNAL_KO).index(k) for k in PCT_KEYS]
    for tab in ("매매가", "매매가이력"):
        sh.format_percent(tab, pct_cols)
    print(f"시트 반영: 상한가DB +{n1}행, 매매가이력 +{n2}행, 매매가 {n3}행")


def main():
    key = os.environ.get("GSHEET_SA_KEY", "").strip()
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        sheet_id = json.load(f).get("gsheet_id", "")
    if not key or not sheet_id:
        print("GSHEET_SA_KEY 또는 gsheet_id 가 없어 시트 반영을 건너뜁니다")
        return
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        json.loads(key), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    run(AuthorizedSession(creds), sheet_id)


if __name__ == "__main__":
    sys.exit(main())
