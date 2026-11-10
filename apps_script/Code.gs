// 구글 시트에 스와이프를 쌓는 Apps Script 웹앱.
// 시트 1행: place_id | action | ts   (시트 이름: swipes)
const SHEET = 'swipes';
function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let s = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
  if (s.getLastRow() === 0) s.appendRow(['place_id', 'action', 'ts']);
  return s;
}
function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  const s = sheet_();
  (Array.isArray(d) ? d : [d]).forEach(r => s.appendRow([r.place_id, r.action, r.ts || new Date().toISOString()]));
  return ContentService.createTextOutput('ok');
}
function doGet() {  // 저장소 동기화용 CSV
  const rows = sheet_().getDataRange().getValues();
  const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\n');
  return ContentService.createTextOutput(csv).setMimeType(ContentService.MimeType.CSV);
}
