"""F23 자체검사: python -m tests.test_f23_popups (외부 호출 없음, 실데이터 안 건드림)."""
import json, tempfile
from datetime import date, timedelta
from pathlib import Path
from src import popups, rank
from src.common import load_config, latest, read_rows

cfg = load_config(app_regions=False)
st = cfg["nearby"]["stations"][0]
today = date.today().isoformat()
soon = (date.today() + timedelta(days=5)).isoformat()
near = lambda c, v, a="": (st["lat"] + 0.002, st["lng"], "서울 어딘가 1", "https://place.map.kakao.com/1")  # 역에서 약 220m
far = lambda c, v, a="": (st["lat"] + 0.05, st["lng"] + 0.05, "", "")  # 수 km
none = lambda c, v, a="": None

ok = {"name": "테스트 팝업", "venue": "어느 백화점", "start": today, "end": soon, "summary": "한 줄\n기간: …", "link": "u"}
# 1) 이름·장소·종료일이 있고, 아직 안 끝났고, 지도에서 찾은 장소가 역 반경 안이면 통과 → 실제 역·좌표·기간으로 기록
rows, why = popups.check(cfg, ok, today, near)
a = {r["field"]: r["value"] for r in rows}
assert why is None and a["station"] == st["name"] and a["popup_source"] == "curated" and a["period_end"] == soon
assert a["address"] == "서울 어딘가 1" and 150 < a["distance_m"] < 300 and a["tier"] == 2
# 2) 빠지는 경우: 종료일 없음, 이미 끝남, 장소 못 찾음, 역에서 멂, 날짜 형식 틀림
assert popups.check(cfg, {**ok, "end": ""}, today, near)[1] == "이름·장소·종료일 중 빠진 것"
assert popups.check(cfg, {**ok, "end": "2000-01-01"}, today, near)[1] == "이미 끝남"
assert popups.check(cfg, ok, today, none)[1] == "장소를 지도에서 못 찾음"
assert popups.check(cfg, ok, today, far)[1].startswith("역에서 멀음")
assert popups.check(cfg, {**ok, "end": "12월 1일"}, today, near)[1] == "날짜 형식(YYYY-MM-DD)"
# 3) import: 통과한 것만 candidates.csv 에, 같은 이름+장소는 같은 place_id
tmp = Path(tempfile.mkdtemp())
f = tmp / "p.json"
f.write_text(json.dumps([ok, {**ok, "name": "끝난 팝업", "end": "2000-01-01"}], ensure_ascii=False), encoding="utf-8")
popups.import_file(f, where=near, data=tmp, rebuild=False)
got = latest(read_rows(tmp / "candidates.csv"))
assert len(got) == 1 and next(iter(got.values()))["name"] == "테스트 팝업"
# 4) 카드: 확인된 팝업만(제목 자동 추출 팝업은 안 나감)
assert cfg["popup"]["curated_only"] is True
pid = next(iter(got))
cands = {pid: {"place_id": pid, **got[pid]},
         "pauto": {"place_id": "pauto", "tier": "2", "category": "팝업스토어", "name": "굿즈 팝업", "station": st["name"]}}
ids = [c["place_id"] for c in rank.build_cards(cfg, cands, [], [], taste_path=tmp / "taste.md")]
assert ids == [pid], ids
print("F23 OK")
