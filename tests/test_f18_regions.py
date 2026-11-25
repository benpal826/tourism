"""F18 자체검사: python -m tests.test_f18_regions (외부 호출 없음, 실데이터 안 건드림)."""
import json, tempfile
from pathlib import Path
from src import run
from src.common import ROOT, load_config, read_rows

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 탭바: 패스 오른쪽에 설정, 설정은 내 지역 칩 + 역 검색(subway.json)
tab = html[html.index('<div class="tabbar">'):]
assert tab.index('data-v="pass"') < tab.index('data-v="settings"')
assert 'jf("subway.json",[])' in html and "showSettings()" in html and 'SV("regions",m)' in html
assert "다음 갱신 때 들어와요" in html
# 2) 스와이프·목록은 내 지역(가장 가까운 역 = c.station)만
assert "&&inRegion(c))}" in html and "return Object.values(m).filter(inRegion);" in html
assert "const inRegion=c=>myRegions().includes(c.station);" in html
# 3) 기록에 지역 태그
assert "region:regionOf(place_id)" in html
# 4) 역 목록 파일: 기본 지역 역이 노선과 함께 있음
sub = {s["name"]: s for s in json.loads((ROOT / "docs/subway.json").read_text(encoding="utf-8"))}
assert "3호선" in sub["잠원"]["lines"] and len(sub) > 200
# 5) 기본 지역: config.yaml default_regions → stations.json default (교대는 데이터는 있지만 기본 아님)
cfg = load_config()
assert cfg["nearby"]["default_regions"] == ["잠원", "신사", "고속터미널", "압구정"]
st = json.loads((ROOT / "docs/stations.json").read_text(encoding="utf-8"))
assert [n for n, s in st.items() if s["default"]] == ["압구정", "신사", "잠원", "고속터미널"] and st["교대"]["default"] is False
assert '"default": st["name"] in cfg["nearby"].get("default_regions"' in (ROOT / "src/run.py").read_text(encoding="utf-8")
# 6) 시트 CSV 의 region 열 → places.csv region 행(예전 4열 CSV 도 그대로 받음)
tmp = Path(tempfile.mkdtemp()); run.DATA = tmp
(tmp / "s.csv").write_text("place_id,action,ts,id,region\nk1,save,2026-11-25T10:00:00Z,a,잠원\nk2,pass,2026-11-25T10:01:00Z,b,\n", encoding="utf-8")
run.import_swipes(str(tmp / "s.csv"))
rows = {(r["place_id"], r["field"]): r["value"] for r in read_rows(tmp / "places.csv")}
assert rows == {("k1", "swipe"): "save", ("k1", "region"): "잠원", ("k2", "swipe"): "pass"}, rows
gs = (ROOT / "apps_script/Code.gs").read_text(encoding="utf-8")
assert "'region'" in gs and "String(r.region || '').slice(0, 20)" in gs and "rows.length, 5)" in gs
print("F18 OK")
