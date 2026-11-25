"""F19 자체검사: python -m tests.test_f19_region_request (외부 호출 없음, 실데이터 안 건드림)."""
import tempfile
from pathlib import Path
from src import common, run
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 앱: 새 역 좌표 기억, 바꾸면 시트로(실패·옛 스크립트면 다음에 다시), 데이터 없는 역엔 안내
assert 'SV("region_pos",pos)' in html and 'SV("regions_dirty",1);syncRegions();' in html
assert 'body:JSON.stringify({type:"regions",regions:list})' in html and "if(j.ok&&j.regions!==undefined)" in html
assert "flush();syncRegions()});" in html and "다음 갱신 때 들어와요" in html
# 2) Apps Script: regions 받기(검증)·?sheet=regions 로 내보내기
gs = (ROOT / "apps_script/Code.gs").read_text(encoding="utf-8")
assert "d.type === 'regions') return regions_(d)" in gs and "e.parameter.sheet === 'regions'" in gs
assert "Number(r.lat) > 33 && Number(r.lat) < 39" in gs
# 3) 시트 목록 → data/regions.csv → load_config 가 config.yaml 역에 더함(이미 있는 역은 그대로)
tmp = Path(tempfile.mkdtemp())
common.DATA = run.DATA = tmp
n0 = len(common.load_config()["nearby"]["stations"])
assert run.import_regions("name,lat,lng,ts\n") == 0  # 빈 목록은 아무것도 안 바꿈
run.import_regions("name,lat,lng,ts\n잠원,37.51,127.01,x\n신논현,37.50421,127.02521,x\n이상한곳,10,10,x\n")
st = common.load_config()["nearby"]["stations"]
assert len(st) == n0 + 1 and st[-1] == {"name": "신논현", "lat": 37.50421, "lng": 127.02521, "from_app": True}, st[-1]
# 4) 앱에서 뺀 역은 active=0 → 수집에서 빠짐
run.import_regions("name,lat,lng,ts\n잠원,37.51,127.01,x\n")
assert len(common.load_config()["nearby"]["stations"]) == n0
print("F19 OK")
