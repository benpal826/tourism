"""F19 자체검사: python -m tests.test_f19_region_request (외부 호출 없음, 실데이터 안 건드림)."""
import tempfile
from pathlib import Path
from src import common, run
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
# 1) 앱: 새 역 좌표 기억, 바꾸면 시트로(실패·옛 스크립트면 다음에 다시), 데이터 없는 역엔 안내
assert 'SV("region_pos",pos)' in html and 'SV("regions_dirty",Date.now());syncRegions();' in html
assert 'body:JSON.stringify({type:"regions",regions:list})' in html and 'if(j.ok&&j.regions!==undefined&&LS("regions_dirty")===ver)' in html
assert "if(RSYNC||!ver||" in html and "if(now&&now!==ver)syncRegions()" in html  # 한 번에 하나, 보내는 중 바뀌면 다시
assert 'SUBWAY=await jf("subway.json",[])' in html and "if(list.every(Boolean))" in html  # F18 때 더한 역 좌표 보충, 없으면 안 보냄
assert 'if(LS("regions")&&LS("regions_dirty")===null)SV("regions_dirty",1);syncRegions()});' in html and "다음 갱신 때 들어와요" in html
# 2) Apps Script: regions 받기(검증)·?sheet=regions 로 내보내기
gs = (ROOT / "apps_script/Code.gs").read_text(encoding="utf-8")
assert "d.type === 'regions') return regions_(d)" in gs and "e.parameter.sheet === 'regions'" in gs
assert "Number(r.lat) > 33 && Number(r.lat) < 39" in gs and "r && typeof r === 'object'" in gs
assert "rs.getDataRange().getValues() : [])" in gs  # 시트가 없으면 빈 응답(머리줄 없음)
# 3) 시트 목록 → data/regions.csv → load_config 가 config.yaml 역에 더함(이미 있는 역은 그대로)
tmp = Path(tempfile.mkdtemp())
common.DATA = run.DATA = tmp
n0 = len(common.load_config()["nearby"]["stations"])
assert run.import_regions("") == 0 and run.import_regions("place_id,action,ts\nk1,save,x\n") == 0  # 머리줄 없음·옛 스크립트는 그대로
run.import_regions("name,lat,lng,ts\n잠원,37.51,127.01,x\n신논현,37.50421,127.02521,x\n이상한곳,10,10,x\n")
st = common.load_config()["nearby"]["stations"]
assert len(st) == n0 + 1 and st[-1] == {"name": "신논현", "lat": 37.50421, "lng": 127.02521, "from_app": True}, st[-1]
# 4) 앱에서 뺀 역은 active=0 → 수집에서 빠짐
run.import_regions("name,lat,lng,ts\n잠원,37.51,127.01,x\n")
assert len(common.load_config()["nearby"]["stations"]) == n0
# 5) 같은 날 다시 더하면 다시 켜짐, 같은 목록 재수신은 행을 더하지 않음
both = "name,lat,lng,ts\n잠원,37.51,127.01,x\n신논현,37.50421,127.02521,x\n"
assert run.import_regions(both) == 1 and len(common.load_config()["nearby"]["stations"]) == n0 + 1
assert run.import_regions(both) == 0
assert len(common.load_config(app_regions=False)["nearby"]["stations"]) == n0  # 샘플은 앱 역 안 씀
# 6) 앱에서 다 빼면(머리줄만) 앱 역 모두 꺼짐
run.import_regions("name,lat,lng,ts\n")
assert len(common.load_config()["nearby"]["stations"]) == n0
print("F19 OK")
