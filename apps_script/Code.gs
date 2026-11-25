// 구글 시트에 스와이프를 쌓는 Apps Script 웹앱 (시트 탭: swipes, 열: place_id | action | ts | id | region)
const SHEET = 'swipes';
const ID_RE = /^[kps][0-9a-f]{3,16}$/;        // 카카오 장소(k+숫자), 팝업(p+hex), 행사(s+hex)
const ACTIONS = ['save', 'pass', 'undo'];
const REGION_SHEET = 'regions';             // F19: 앱 설정의 내 지역(열: name | lat | lng | ts), 보낼 때마다 통째로 바꿈

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const s = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
  if (s.getLastRow() === 0) s.appendRow(['place_id', 'action', 'ts', 'id', 'region']);
  else if (s.getRange(1, 5).getValue() === '') s.getRange(1, 5).setValue('region');  // F18: 예전 시트에 열 추가
  return s;
}
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function regions_(d) {
  const list = (Array.isArray(d.regions) ? d.regions : []).slice(0, 30).filter(r =>
    r && typeof r === 'object' && typeof r.name === 'string' && r.name.length > 0 && r.name.length <= 20 &&
    Number(r.lat) > 33 && Number(r.lat) < 39 && Number(r.lng) > 124 && Number(r.lng) < 132);  // 한국 좌표만
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const s = ss.getSheetByName(REGION_SHEET) || ss.insertSheet(REGION_SHEET);
  const ts = new Date().toISOString();
  s.clearContents();
  s.getRange(1, 1, list.length + 1, 4).setValues([['name', 'lat', 'lng', 'ts']].concat(list.map(r => [r.name, Number(r.lat), Number(r.lng), ts])));
  return json_({ ok: true, regions: list.length });
}

function doPost(e) {
  if (!e.postData || e.postData.length > 20000) return json_({ ok: false, error: 'too large' });
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return json_({ ok: false, error: 'bad json' }); }
  const events = (Array.isArray(d) ? d : [d]).slice(0, 200);
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    if (d && !Array.isArray(d) && d.type === 'regions') return regions_(d);  // F19
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
      rows.push([r.place_id, r.action, ts.toISOString(), id, String(r.region || '').slice(0, 20)]);  // F18: 지역 태그
    });
    if (rows.length) s.getRange(s.getLastRow() + 1, 1, rows.length, 5).setValues(rows);
    return json_({ ok: true, ids: acked });
  } finally { lock.releaseLock(); }
}

function doGet(e) {  // 저장소 동기화용 CSV (?sheet=regions 면 내 지역 목록. 앱이 아직 안 보냈으면 빈 응답 → 저장소는 아무것도 안 바꿈)
  const want = e && e.parameter && e.parameter.sheet === 'regions';
  const rs = want ? SpreadsheetApp.getActiveSpreadsheet().getSheetByName(REGION_SHEET) : null;
  const rows = want ? (rs && rs.getLastRow() ? rs.getDataRange().getValues() : []) : sheet_().getDataRange().getValues();
  const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\n');
  return ContentService.createTextOutput(csv).setMimeType(ContentService.MimeType.CSV);
}
