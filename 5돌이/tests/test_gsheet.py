"""시트 APPEND 로직 검증(가짜 시트 사용, 네트워크 불필요). 실행: python tests/test_gsheet.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import gsheet_sync as g


class Fake:
    """append 외에 값을 바꾸는 호출이 오면 실패한다."""
    def __init__(self, tabs): self.t = tabs
    def get(self, tab, a1, render="UNFORMATTED_VALUE"):
        assert a1 == "A:A"
        return [r[:1] for r in self.t[tab]]
    def append(self, tab, rows): self.t[tab] += [list(r) for r in rows]
    def put(self, *a): raise AssertionError("덮어쓰기 금지")
    def clear(self, *a): raise AssertionError("지우기 금지")


recs = [{"date": "2026-11-13", "market": "코스피", "code": "002880", "name": "디와이에이"},
        {"date": "2026-11-12", "market": "코스닥", "code": "301300", "name": "바이브컴퍼니"}]

# 빈 탭: 머리글 + 행 추가
sh = Fake({"상한가DB": []})
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 2
assert sh.t["상한가DB"][0][0] == "상한가일" and sh.t["상한가DB"][1][0] == "2026-11-12"
assert sh.t["상한가DB"][1][2] == "'301300"                        # 코드 앞자리 0 보존

# 재실행: 중복 없음
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 0 and len(sh.t["상한가DB"]) == 3

# 시트가 날짜를 일련번호로 저장한 경우도 같은 날짜로 인식
sh.t["상한가DB"][1][0] = 46338
assert g.iso(46338) == "2026-11-12"
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 0

# 새 날짜는 맨 아래에 추가되고 기존 행은 그대로
before = [list(r) for r in sh.t["상한가DB"]]
recs.append({"date": "2026-11-16", "market": "코스피", "code": "000001", "name": "신규"})
assert g.sync_log(sh, "상한가DB", recs, g.UPPER_KO) == 1
assert sh.t["상한가DB"][:3] == before and sh.t["상한가DB"][3][0] == "2026-11-16"

# 사용자가 직접 적어둔 내용이 있어도 지우지 않고 아래에 추가
sh = Fake({"매매가": [["내 메모"], ["2026-11-13", "x"]]})
assert g.sync_log(sh, "매매가", [{"date": "2026-11-16", "code": "000001"}], g.SIGNAL_KO) == 1
assert sh.t["매매가"][0] == ["내 메모"] and sh.t["매매가"][2][0] == "2026-11-16"
print("OK - 시트 APPEND")
