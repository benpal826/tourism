"""F20 자체검사: python -m tests.test_f20_send_button (앱 코드 확인. 실제 전송은 모바일 화면에서)."""
from src.common import ROOT

html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
head = html[html.index("<header>"):html.index("</header>")]
assert '<button id="send"' in head and "전송 대기" not in html          # '전송 대기' 글자 대신 버튼
assert 'SEND.textContent=sending?"보내는 중…":n?`저장 ${n}`:"✓ 저장됨"' in html
assert "SEND.onclick=()=>{if(!queue.length||sending)return;clearTimeout(timer);fails=0;flush()};" in html
assert "sending=true;pending();" in html                                 # 보내는 동안 표시
assert "if(queue.length){clearTimeout(timer);timer=setTimeout(flush," in html  # 자동 전송·재시도는 그대로
print("F20 OK")
