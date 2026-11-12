// 구글 시트에 스와이프를 쌓는 Apps Script 웹앱 (시트 탭: swipes, 열: place_id | action | ts | id)
const SHEET = 'swipes';
const ID_RE = /^[kps][0-9a-f]{3,16}$/;        // 카카오 장소(k+숫자), 팝업(p+hex), 행사(s+hex)
const ACTIONS = ['save', 'pass', 'undo'];

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const s = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
  if (s.getLastRow() === 0) s.appendRow(['place_id', 'action', 'ts', 'id']);
  return s;
}
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function doPost(e) {
  if (!e.postData || e.postData.length > 20000) return json_({ ok: false, error: 'too large' });
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'bad json' }); }
  const events = (Array.isArray(d) ? d : [d]).slice(0, 200);
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const s = sheet_();
    const last = s.getLastRow();
    const have = new Set(last > 1 ? s.getRange(2, 4, last - 1, 1).getValues().map(r => String(r[0])) : []);
    const acked = [], rows = [];
    events.forEach(r => {
      const id = String(r.id || ''), ts = new Date(r.ts);
      if (!ID_RE.test(String(r.place_id)) || ACTIONS.indexOf(r.action) < 0 || !id || id.length > 64 || isNaN(ts)) return; // 잘못된 이벤트는 응답에서 제외
      acked.push(id);
      if (have.has(id)) return;                    // 재전송된 같은 이벤트는 한 번만 기록
      have.add(id);
      rows.push([r.place_id, r.action, ts.toISOString(), id]);
    });
    if (rows.length) s.getRange(s.getLastRow() + 1, 1, rows.length, 4).setValues(rows);
    return json_({ ok: true, ids: acked });
  } finally { lock.releaseLock(); }
}

function doGet() {  // 저장소 동기화용 CSV
  const rows = sheet_().getDataRange().getValues();
  const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\n');
  return ContentService.createTextOutput(csv).setMimeType(ContentService.MimeType.CSV);
}
