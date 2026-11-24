"""F02 자체검사: python -m tests.test_f02_map
정적 검사만 한다. 실제 지도 표시는 localhost 브라우저에서 확인(progress.md 기록)."""
import os, re
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
cfg = (ROOT / "docs/config.js").read_text(encoding="utf-8")
assert "leaflet" not in html.lower() and "openstreetmap" not in html.lower(), "Leaflet/OSM 이 남아 있음"
assert "oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=" in html, "네이버 지도 SDK 로드 없음"
assert "navermap_authFailure" in html and "nomap" in html, "인증 실패 안내 처리 없음"
m = re.search(r'window\.NAVER_MAP_ID\s*=\s*"([^"]+)"', cfg)
assert m, "docs/config.js 에 NAVER_MAP_ID 없음"
secret = os.environ.get("NAVER_MAP_CLIENT_SECRET", "").strip()
for f in (ROOT / "docs").rglob("*"):  # Secret 이 공개 폴더에 새지 않았는지
    if secret and f.is_file() and f.suffix in (".js", ".html", ".json"):
        assert secret not in f.read_text(encoding="utf-8", errors="ignore"), f"Secret 노출: {f}"
print("F02 OK")
