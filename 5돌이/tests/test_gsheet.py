"""시트 누적 로직 검증(가짜 시트 사용, 네트워크 불필요). 실행: python tests/test_gsheet.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import gsheet_sync as g


class Fake:
    def __init__(self, tabs): self.t = tabs
    def get(self, tab, a1, render="UNFORMATTED_VALUE"):
        rows = self.t[tab]
        if a1 == "A1": return [rows[0][:1]] if rows else []
        return [r[:1] for r in rows[1:]]
    def clear(self, tab): self.t[tab] = []
    def put(self, tab, rows): self.t[tab] = [list(r) for r in rows]
    def append(self, tab, rows): self.t[tab] += [list(r) for r in rows]


recs = [{"date": "2026-11-13", "market": "코스피", "code": "002880", "name": "디와이에이"},
        {"date": "2026-11-12", "market": "코스닥", "code": "301300", "name": "바이브컴퍼니"}]
sh = Fake({"상한가DB": [['=IMPORTDATA("x")']]})
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 2          # 수식 탭 → 새로 시작
assert sh.t["상한가DB"][0][0] == "상한가일" and sh.t["상한가DB"][1][0] == "2026-11-12"
assert sh.t["상한가DB"][1][2] == "'301300"                        # 코드 앞자리 0 보존
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 0          # 재실행해도 중복 없음
sh.t["상한가DB"][1][0] = 46338                                    # 시트가 날짜로 바꿔 저장한 경우
assert g.iso(46338) == "2026-11-12"
recs.append({"date": "2026-11-16", "market": "코스피", "code": "000001", "name": "신규"})
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 1 and len(sh.t["상한가DB"]) == 4
print("OK - 시트 누적")
