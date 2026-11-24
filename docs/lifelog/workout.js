// 자동 생성: python scripts/build_dash.py (직접 고치지 말 것 — app/core.js·app/ui.js를 고친다)
(function () {
"use strict";
// ---- app/core.js ----
// 운동 화면 로직 (DOM 없음 — node --test로 검증, index.html이 그대로 import)

// shortcut: 따옴표·쉼표 든 칸은 못 읽음, gyms/muscles.csv에 그런 값이 생기면 제대로 된 파서로
function parseCSV(text) {
  const [head, ...rows] = text.trim().split(/\r?\n/).map((l) => l.split(","));
  return rows.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

// gyms.csv: place,equipment,exercise ("-"는 기구 목록 없는 장소)
function buildCatalog(gymsText, musclesText) {
  const muscles = {};
  for (const r of parseCSV(musclesText)) {
    (muscles[r.exercise] ??= []).push({ muscle: r.muscle, share: Number(r.share) });
  }
  const places = [];
  const equipment = {};
  for (const r of parseCSV(gymsText)) {
    if (!equipment[r.place]) { equipment[r.place] = {}; places.push(r.place); }
    if (r.equipment !== "-") (equipment[r.place][r.equipment] ??= []).push(r.exercise);
  }
  return { places, equipment, muscles };
}

function candidates(catalog, place) {
  const eq = catalog.equipment[place] ?? {};
  const list = [...new Set(Object.entries(eq).filter(([k]) => k !== "유산소").flatMap(([, v]) => v))]; // 유산소는 F12 버튼으로만
  if (list.length === 0) return { list: Object.keys(catalog.muscles), notice: "이 장소의 기구 목록이 아직 없음" };
  return { list, notice: null };
}

// ---- F02 검색 ----
const NO_MATCH = "일치하는 운동 없음";
const MAX = 8;

// entries.csv의 실제 기록(kind=quant, unit=kg) + 아직 안 가져온 화면 세트 → 최근 순·자주 순 종목 (같은 종목·date,time = 1회)
function workoutHistory(entriesText, sets = []) {
  const last = {}, count = {}, seen = new Set();
  const add = (ex, at) => {
    if (seen.has(`${ex}|${at}`)) return;
    seen.add(`${ex}|${at}`);
    count[ex] = (count[ex] ?? 0) + 1;
    if (!(last[ex] > at)) last[ex] = at;
  };
  for (const r of parseCSV(entriesText)) {
    if (r.kind === "quant" && r.unit === "kg" && r.item?.startsWith("workout:")) add(r.item.slice(8), `${r.date} ${r.time}`);
  }
  for (const s of sets) add(s.exercise, `${s.date} ${s.time}`);
  const names = Object.keys(last);
  return {
    recent: [...names].sort((a, b) => last[b].localeCompare(last[a])),
    frequent: [...names].sort((a, b) => count[b] - count[a] || last[b].localeCompare(last[a])),
  };
}

function search(list, query, history) {
  const q = query.trim();
  if (q) return list.filter((e) => e.includes(q)).slice(0, MAX);
  const first = [...(history?.recent ?? []).slice(0, 3), ...(history?.frequent ?? [])];
  return [...new Set([...first.filter((e) => list.includes(e)), ...list])].slice(0, MAX);
}

const pick = (state, exercise) => ({ ...state, screen: "set", exercise });

// ---- F03 부위 ----
const MUSCLES = ["가슴", "등", "어깨", "이두", "삼두", "코어", "대퇴사두", "햄스트링", "둔근", "종아리"];


// 자주 한 순(history.frequent: 횟수·최근 순), 기록 없는 건 뒤에 원래 목록 순
const freqRank = (history) => (e) => { const i = history?.frequent.indexOf(e) ?? -1; return i < 0 ? Infinity : i; };

// 주동근 묶음 먼저, 묶음 안에서는 자주 한 순 (history = workoutHistory: frequent가 횟수·최근 순). 기록 없는 건 뒤, 목록 순
function exercisesFor(catalog, muscle, list, history) {
  const share = (e) => catalog.muscles[e]?.find((x) => x.muscle === muscle)?.share ?? 0;
  const rank = freqRank(history);
  return list.filter((e) => share(e) > 0).sort((a, b) => share(b) - share(a) || rank(a) - rank(b));
}

const tapMuscle = (muscle) => ({ squish: muscle, vibrate: [15] });

// 몸 앞·뒤 그림 (대시보드 dashboard/index.html 'body' 그림과 같은 모양). 부위 영역은 class="rg" data-m
function bodySvg() {
  const out = [];
  const tag = (t, a, m) => out.push(`<${t} ${Object.entries(a).map(([k, v]) => `${k}="${v}"`).join(" ")} ${m ? `class="rg" tabindex="0" data-m="${m}"` : 'class="nt"'}/>`);
  const fig = (ox, back) => {
    const R = (x, y, width, height, m, rx = 5) => tag("rect", { x: ox + x, y, width, height, rx }, m);
    tag("circle", { cx: ox + 50, cy: 16, r: 11 });
    R(45, 27, 10, 6, null, 2);
    tag("circle", { cx: ox + 27, cy: 41, r: 9 }, "어깨"); tag("circle", { cx: ox + 73, cy: 41, r: 9 }, "어깨");
    if (!back) { R(34, 34, 15, 21, "가슴", 4); R(51, 34, 15, 21, "가슴", 4); R(37, 57, 26, 34, "코어"); }
    else { R(33, 34, 34, 38, "등", 6); R(37, 74, 26, 17, "등", 5); }
    R(14, 50, 10, 30, back ? "삼두" : "이두"); R(76, 50, 10, 30, back ? "삼두" : "이두");
    R(12, 82, 9, 28, null, 4); R(79, 82, 9, 28, null, 4);
    if (!back) R(35, 93, 30, 11, null, 4); else R(35, 93, 30, 16, "둔근", 6);
    R(35, back ? 111 : 106, 13, back ? 40 : 45, back ? "햄스트링" : "대퇴사두", 6);
    R(52, back ? 111 : 106, 13, back ? 40 : 45, back ? "햄스트링" : "대퇴사두", 6);
    R(36, 155, 11, 38, back ? "종아리" : null); R(53, 155, 11, 38, back ? "종아리" : null);
    out.push(`<text x="${ox + 50}" y="210" text-anchor="middle">${back ? "뒤" : "앞"}</text>`);
  };
  fig(10, false); fig(130, true);
  return `<svg viewBox="0 0 240 216" role="img" aria-label="부위를 눌러 운동 고르기">${out.join("")}</svg>`;
}

// ---- F04 세트 입력 ----
// 화면 세트 = {date, time, exercise, kg, rep} (버티는 운동은 rep 대신 sec). entries.csv로 옮길 땐 kg·set(=1)·rep(또는 초) 3줄 (F09)
const KG = Array.from({ length: 121 }, (_, i) => i * 2.5);
const REP = Array.from({ length: 30 }, (_, i) => i + 1);
const SEC = Array.from({ length: 35 }, (_, i) => 10 + i * 5);
// 직전 값이 목록 밖(예 72kg)이면 넣어서 칸에 보이게 — 숨은 값이 저장되지 않도록
const withValue = (list, v) => (v == null || list.includes(v) ? list : [...list, v].sort((a, b) => a - b));
const HOLD = ["플랭크", "사이드 플랭크"];
const isHold = (exercise) => HOLD.includes(exercise);
const countKey = (exercise) => (isHold(exercise) ? "sec" : "rep");
function kstNow(now = new Date()) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(now).map((x) => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}` };
}

function lastFromEntries(entriesText, exercise) {
  const g = {}, unit = isHold(exercise) ? "초" : "rep";
  for (const r of parseCSV(entriesText)) {
    if (r.kind !== "quant" || r.item !== `workout:${exercise}`) continue;
    (g[`${r.date} ${r.time}`] ??= {})[r.unit] = Number(r.value);
  }
  const at = Object.keys(g).filter((k) => "kg" in g[k] && unit in g[k]).sort().pop();
  return at ? { at, kg: g[at].kg, [countKey(exercise)]: g[at][unit] } : null;
}

function setForm(entriesText, sets, exercise, now = new Date()) {
  const mine = sets.filter((s) => s.exercise === exercise);
  const app = mine.at(-1), old = lastFromEntries(entriesText, exercise);
  const last = app && (!old || `${app.date} ${app.time}` > old.at) ? app : old;
  const today = kstNow(now).date;
  const setNo = 1 + mine.filter((s) => s.date === today).length; // 세트 번호는 오늘 것만
  const c = countKey(exercise);
  return { kg: last?.kg ?? null, [c]: last?.[c] ?? null, setNo };
}

// shortcut: 기구 목록 없는 장소(서울)용 기본 맨몸 종목, 새 맨몸 종목이 생기면 여기나 gyms.csv '맨몸' 줄에 추가
const BODYWEIGHT = ["푸시업", "풀업", "친업", "딥스", "플랭크", "사이드 플랭크", "크런치", "클램쉘", "카프레이즈"];
const isBodyweight = (catalog, exercise) => BODYWEIGHT.includes(exercise) ||
  Object.values(catalog.equipment).some((eq) => eq["맨몸"]?.includes(exercise));

// ---- F11 맨몸 버튼 ----
// 고른 장소 gyms '맨몸' 줄, 기구 목록 없는 장소(서울)는 기본 맨몸 목록, 자주 한 순
// 기구 목록 있는 장소엔 기본 목록을 안 붙임 — 거기 없는 기구(풀업 바 등)가 필요한 운동이 섞이지 않게 (F01)
function bodyweightFor(catalog, place, history) {
  const listed = candidates(catalog, place).notice == null;
  const list = [...new Set([...(catalog.equipment[place]?.["맨몸"] ?? []), ...(listed ? [] : BODYWEIGHT)])];
  const rank = freqRank(history);
  return list.sort((a, b) => rank(a) - rank(b));
}
// 검색·부위 목록에 쓰는 장소 운동 목록: 기구 후보 + 맨몸 (맨몸은 어디서나 됨)
const placeList = (catalog, place) => [...new Set([...candidates(catalog, place).list, ...bodyweightFor(catalog, place)])];
const tapButton = () => ({ squish: true, vibrate: [15] });
// F16 토스트: 문구를 ms 동안 보여줌. 빈 문구는 무시, 새 문구가 오면 숨김 타이머를 새로 건다
// F17 진동 세기(ms): 일반 버튼 · 탭/화면 이동 · 선택 확정
const HAPTIC = { tap: [25], nav: [40], pick: [20, 40, 20] };
const TABS = ["day", "week", "month", "input"];
const SCREENS = ["home", "set", "cardio"]; // home → 다른 화면은 앞으로, 반대는 뒤로
function slideDir(order, from, to) {
  const a = order.indexOf(from), b = order.indexOf(to);
  return a < 0 || b < 0 || a === b ? null : b > a ? "fwd" : "back";
}
// 방향 class를 떼었다 붙여 애니메이션을 다시 재생 (CSS는 village.js, 움직임 줄이기면 규칙 없음)
function slideIn(el, dir) {
  if (!el || !dir) return;
  el.classList.remove("ll-in-fwd", "ll-in-back");
  void el.offsetWidth;
  el.classList.add("ll-in-" + dir);
}

function toast(el, msg, ms = 2000, later = setTimeout) {
  if (!el || !msg) return;
  el.textContent = msg; el.classList.add("on");
  if (el._t) clearTimeout(el._t);
  el._t = later(() => el.classList.remove("on"), ms);
}

function validateSet(catalog, exercise, form) {
  const err = {}, { kg } = form, c = countKey(exercise), rep = form[c];
  const bw = isBodyweight(catalog, exercise);
  if (kg == null || Number.isNaN(kg)) err.kg = "무게를 고르세요";
  else if (bw ? kg < 0 : kg <= 0) err.kg = bw ? "0 이상이어야 해요" : "0보다 커야 해요";
  if (rep == null || Number.isNaN(rep)) err[c] = c === "sec" ? "초를 고르세요" : "횟수를 고르세요";
  else if (rep <= 0) err[c] = "0보다 커야 해요";
  return err;
}

// 시각은 누른 순간 그대로. 같은 종목·같은 분 세트가 여럿이어도 밀지 않음 (F09가 개수로 중복을 가림)
function completeSet(sets, exercise, form, now = new Date()) {
  const c = countKey(exercise);
  return { ...kstNow(now), exercise, kg: form.kg, [c]: form[c] };
}

async function saveSet(store, catalog, sets, exercise, form, now = new Date()) {
  const errors = validateSet(catalog, exercise, form);
  if (Object.keys(errors).length) return { ok: false, errors };
  const rec = completeSet(sets, exercise, form, now);
  await store.add(rec);
  return { ok: true, rec, form: { ...form, setNo: form.setNo + 1 } };
}

// ---- F10 세트 삭제 ----
// 칸 키 = date,time,종목#몇 번째 (같은 종목·같은 분 세트가 여럿일 수 있음, F04)
const setKey = (s) => `${s.date} ${s.time}|${s.exercise}`;
const keyed = (sets) => {
  const n = {};
  return sets.map((s) => { const k = setKey(s); n[k] = (n[k] ?? 0) + 1; return [`${k}#${n[k]}`, s]; });
};
const todaySets = (sets, exercise, now = new Date()) => {
  const today = kstNow(now).date;
  return keyed(sets).filter(([, s]) => s.exercise === exercise && s.date === today)
    .map(([key, s]) => ({ key, label: s.sec != null ? `${s.kg}kg×${s.sec}초` : `${s.kg}kg×${s.rep}` }));
};
// 확인창 없이 바로 지움. 남은 세트를 돌려주면 화면이 setForm·tierOf·workoutHistory를 그걸로 다시 계산
async function deleteSet(store, sets, key) {
  const s = keyed(sets).find(([k]) => k === key)?.[1];
  if (!s) return [...sets];
  await store.remove(s);
  return sets.filter((x) => x !== s);
}

// ---- F05 타격 연출 ----
// 연출은 '계획'만 만든다. 실제 진동·소리·애니메이션은 index.html이 계획대로 재생
const TIERS = {
  normal: { vibrate: [40], sound: "hit", durationMs: 450, primaryScale: 1, shake: false, burst: false, pauseMs: 0 },
  strong: { vibrate: [40, 60, 60], sound: "strong", durationMs: 700, primaryScale: 1.4, shake: true, burst: false, pauseMs: 0 },
  best: { vibrate: [400], sound: "best", durationMs: 1600, primaryScale: 1.6, shake: true, burst: true, pauseMs: 350 },
};

function hitPlan(catalog, exercise, tier = "normal", env = {}) {
  const t = TIERS[tier] ?? TIERS.normal;
  const ms = catalog.muscles[exercise] ?? [];
  return {
    tier, sound: t.sound, durationMs: t.durationMs, shake: t.shake, burst: t.burst, pauseMs: t.pauseMs,
    vibrate: env.canVibrate ? (env.haptic?.hit?.[tier] ?? t.vibrate) : null, // F19 세기는 테마가
    primary: ms.filter((m) => m.share >= 1).map((m) => m.muscle),
    secondary: ms.filter((m) => m.share < 1).map((m) => m.muscle),
    squish: true, flash: true, primaryScale: t.primaryScale, secondaryScale: t.primaryScale * 0.4,
  };
}

// 저장 중(saving)에도 busy: 저장이 연출보다 느려도 두 번 저장되지 않게
function makePlayer() {
  let until = 0, saving = false;
  return {
    busy: (now) => saving || now.getTime() < until,
    start: (now, ms) => { until = now.getTime() + ms; },
    saving: (v) => { saving = v; },
  };
}

// 세트 완료 버튼: 검사 → (재생 중이면 무시) → 연출 시작 → 저장. 연출이 저장을 기다리지 않는다
async function handleDone(ctx, exercise, form, now = new Date()) {
  const errors = validateSet(ctx.catalog, exercise, form);
  if (Object.keys(errors).length) return { ok: false, errors };
  if (ctx.player.busy(now)) return { ok: false, busy: true };
  const tier = ctx.tierOf?.(exercise, form) ?? "normal";
  let plan = hitPlan(ctx.catalog, exercise, tier, ctx.env);
  if (ctx.settings) plan = applySettings(plan, ctx.settings);
  ctx.player.start(now, plan.off ? 300 : plan.durationMs); // 연출을 꺼도 짧게 막아 두 번 저장 방지
  if (!plan.off) ctx.play(plan);
  ctx.player.saving?.(true);
  try {
    const r = await saveSet(ctx.store, ctx.catalog, ctx.sets, exercise, form, now);
    return { ...r, plan };
  } catch { return { ok: false, message: SAVE_FAIL, plan }; } // F13 실패해도 번호·타이머 그대로
  finally { ctx.player.saving?.(false); }
}

// ---- F13 저장 실패·연결 안내 ----
const SAVE_FAIL = "저장 실패 — 다시 눌러 주세요";
const NOT_CONNECTED = "저장소 연결 안 됨 — 이 화면을 닫으면 기록이 사라져요";
// onSnapshot이 저장 완료보다 먼저 왔으면 이미 들어 있음
const addSaved = (sets, rec) => (rec._id != null && sets.some((x) => x._id === rec._id) ? sets : [...sets, rec]);
const CARDIO_READ_FAIL = "유산소 기록 읽기 실패 — 새로 저장은 시도하지만 여기 목록엔 안 보일 수 있어요";
// 저장됨이라고 말해도 되는 건 연결됐고 읽기도 되는 때뿐
const cardioState = (connected, readOk) => ({ persisted: connected && readOk, warn: !connected ? NOT_CONNECTED : readOk ? "" : CARDIO_READ_FAIL });
const cardioDoneText = (rec, persisted) => (persisted ? `완주! ${rec.min}분 저장됨` : `완주! ${rec.min}분 (이 화면에만 저장)`);

// ---- F06 연출 단계 ----
// 개인 최고 = 최고 무게, 같은 무게면 더 많은 횟수 (progress.md 가정)
function tierOf(entriesText, sets, exercise, { kg, rep }) {
  const item = `workout:${exercise}`, cur = {}, done = [];
  let goal = null, goalDate = "";
  for (const r of parseCSV(entriesText)) {
    if (r.item !== item) continue;
    if (r.kind === "goal" && r.unit === "kg" && r.date >= goalDate) { goal = Number(r.value); goalDate = r.date; }
    if (r.kind !== "quant") continue;
    // 같은 date,time에 3줄 세트가 여러 번 올 수 있음: kg 줄마다 새 세트, 뒤따르는 set·rep은 그 세트에 붙음
    const at = `${r.date} ${r.time}`;
    if (r.unit === "kg") done.push(cur[at] = { kg: Number(r.value) });
    else if (cur[at]) cur[at][r.unit] = Number(r.value);
  }
  const past = [...done, ...sets.filter((x) => x.exercise === exercise)];
  if (past.length && kg > 0) { // 맨몸(kg=0)은 최고 판정 안 함
    const top = Math.max(...past.map((x) => x.kg));
    const topRep = Math.max(...past.filter((x) => x.kg === top).map((x) => x.rep ?? 0));
    if (kg > top || (kg === top && rep > topRep)) return "best";
  }
  return goal != null && kg >= goal ? "strong" : "normal";
}

// ---- F07 휴식 타이머 ----
const REST_DEFAULT_SEC = 90; // prd 미정 → 가정(progress.md), F08 설정에서 바꿈

// 시작 시각만 기억하고 매번 다시 계산 → 화면이 꺼졌다 켜져도 맞다
function makeRestTimer(restSec = REST_DEFAULT_SEC) {
  let startMs = null, alerted = false;
  return {
    start(nowMs) { startMs = nowMs; alerted = false; },
    setRest(sec) { restSec = sec; },
    tick(nowMs) {
      if (startMs == null) return { running: false, remainingSec: 0, recovery: 1, done: false, alert: null };
      const left = Math.max(0, restSec * 1000 - (nowMs - startMs));
      const done = left === 0;
      const alert = done && !alerted ? { vibrate: [30, 80, 30], sound: "ding" } : null;
      if (alert) alerted = true;
      return { running: !done, remainingSec: Math.ceil(left / 1000), recovery: 1 - left / (restSec * 1000), done, alert };
    },
  };
}

// ---- F08 연출 설정 (브라우저 저장: 이 폰에서만 쓰는 편의 설정) ----
const DEFAULT_SETTINGS = { vibrate: true, sound: true, intensity: "strong", restSec: REST_DEFAULT_SEC };
const KEY = "lifelog.fx";

function loadSettings(storage) {
  try {
    const v = JSON.parse(storage?.getItem(KEY) ?? "null");
    return v && typeof v === "object" ? { ...DEFAULT_SETTINGS, ...v } : { ...DEFAULT_SETTINGS };
  } catch { return { ...DEFAULT_SETTINGS }; }
}

function saveSettings(storage, settings) {
  try { storage?.setItem(KEY, JSON.stringify(settings)); } catch {}
}

function applySettings(plan, s) {
  const p = { ...plan };
  if (!s.vibrate) p.vibrate = null;
  if (!s.sound) p.sound = null;
  if (s.intensity === "weak") {
    p.primaryScale = 1 + (p.primaryScale - 1) / 2; p.secondaryScale = p.primaryScale * 0.4;
    p.shake = false; p.vibrate = p.vibrate?.map((ms) => Math.round(ms / 2)) ?? null;
  }
  if (s.intensity === "off") p.off = true;
  return p;
}

// 휴식 중 캐릭터 회복 모양(--r). 연출을 끄면 늘 원래 모양(1)
const restRecovery = (tick, s) => (s.intensity === "off" ? 1 : tick.recovery);

// ---- F12 유산소 ----
// 화면 유산소 = {date, time, exercise, min, kmh, deg} (kmh·deg 없으면 null). entries.csv로 옮길 땐 cardio:<종목> 분·km/h·도 줄 (F09)
const CARDIO = ["트레드밀", "인클라인 트레드밀", "스텝밀"]; // 유산소 기구 목록 없는 장소(서울)용 기본
const MIN = Array.from({ length: 120 }, (_, i) => i + 1);
const KMH = Array.from({ length: 30 }, (_, i) => (i + 1) / 2);
const DEG = Array.from({ length: 16 }, (_, i) => i);

function cardioRuns(entriesText, recs, exercise) {
  const g = {};
  for (const r of parseCSV(entriesText)) {
    if (r.kind !== "quant" || !r.item?.startsWith("cardio:") || (exercise && r.item !== `cardio:${exercise}`)) continue;
    (g[`${r.date} ${r.time}|${r.item.slice(7)}`] ??= { ex: r.item.slice(7), at: `${r.date} ${r.time}` })[r.unit] = Number(r.value);
  }
  const runs = Object.values(g).filter((x) => "분" in x).map((x) => ({ ex: x.ex, at: x.at, min: x["분"], kmh: x["km/h"] ?? null, deg: x["도"] ?? null }));
  for (const c of recs) if (!exercise || c.exercise === exercise) runs.push({ ex: c.exercise, at: `${c.date} ${c.time}`, min: c.min, kmh: c.kmh ?? null, deg: c.deg ?? null });
  return runs;
}

// 자주 한 순(같으면 최근 것). workoutHistory와 같은 모양 {frequent}
function cardioHistory(entriesText, recs = []) {
  const count = {}, last = {};
  for (const r of cardioRuns(entriesText, recs)) { count[r.ex] = (count[r.ex] ?? 0) + 1; if (!(last[r.ex] > r.at)) last[r.ex] = r.at; }
  return { frequent: Object.keys(count).sort((a, b) => count[b] - count[a] || last[b].localeCompare(last[a])) };
}

function cardioFor(catalog, place, history) {
  const list = [...(catalog.equipment[place]?.["유산소"] ?? CARDIO)];
  const rank = freqRank(history);
  return list.sort((a, b) => rank(a) - rank(b));
}

function cardioForm(entriesText, recs, exercise) {
  const last = cardioRuns(entriesText, recs, exercise).sort((a, b) => a.at.localeCompare(b.at)).pop();
  return { min: last?.min ?? null, kmh: last?.kmh ?? null, deg: last?.deg ?? null };
}

function validateCardio({ min }) {
  if (min == null || Number.isNaN(min)) return { min: "시간을 고르세요" };
  return min <= 0 ? { min: "0보다 커야 해요" } : {};
}

async function saveCardio(store, exercise, form, now = new Date()) {
  const errors = validateCardio(form);
  if (Object.keys(errors).length) return { ok: false, errors };
  const rec = { ...kstNow(now), exercise, min: form.min, kmh: form.kmh ?? null, deg: form.deg ?? null };
  await store.add(rec);
  return { ok: true, rec };
}

// 오늘 그 종목 유산소 칸(15분·4km/h·15도). 칸 키·삭제는 세트와 같은 규칙(date,time,종목#몇 번째)
const todayCardio = (recs, exercise, now = new Date()) => {
  const today = kstNow(now).date;
  return keyed(recs).filter(([, c]) => c.exercise === exercise && c.date === today)
    .map(([key, c]) => ({ key, label: [`${c.min}분`, c.kmh != null && `${c.kmh}km/h`, c.deg != null && `${c.deg}도`].filter(Boolean).join("·") }));
};
const deleteCardio = deleteSet;

// 홈 화면 목록(검색·부위/맨몸·유산소)은 하나만 열림. open = 남길 목록, null이면 전부 닫음
const LISTS = ["drop", "mdrop", "cdrop"];
const listsToClear = (open) => LISTS.filter((x) => x !== open);

// 완주 연출: 짧은 3연타 진동 + 소리 + 캐릭터 통통. F08 설정·F05 잠금 그대로
async function handleCardio(ctx, exercise, form, now = new Date()) {
  const errors = validateCardio(form);
  if (Object.keys(errors).length) return { ok: false, errors };
  if (ctx.player.busy(now)) return { ok: false, busy: true };
  let plan = { tier: "finish", sound: "finish", durationMs: 600, vibrate: ctx.env?.canVibrate ? (ctx.env.haptic?.finish ?? [30, 40, 30, 40, 120]) : null,
    primary: [], secondary: [], squish: true, flash: true, primaryScale: 1.3, secondaryScale: 0.5, shake: false, burst: false, pauseMs: 0 };
  if (ctx.settings) plan = applySettings(plan, ctx.settings);
  ctx.player.start(now, plan.off ? 300 : plan.durationMs);
  if (!plan.off) ctx.play(plan);
  ctx.player.saving?.(true);
  try { return { ...(await saveCardio(ctx.store, exercise, form, now)), plan }; }
  catch { return { ok: false, message: SAVE_FAIL, plan }; }
  finally { ctx.player.saving?.(false); }
}

// ---- F14 브리핑과 합치기 ----
// 화면 기록(db sets·cardio) 중 entries에 아직 안 옮긴 것만 entries 행 모양으로 (scripts/import_sets.py와 같은 규칙)
const isNum = (x) => typeof x === "number" && Number.isFinite(x);
const numText = (x) => String(x);
function recLines(s) {
  if (!s || typeof s !== "object") return null;
  const { date, time } = s, ex = typeof s.exercise === "string" ? s.exercise.trim() : "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date ?? "") || !/^\d{2}:\d{2}$/.test(time ?? "") || !ex || ex.includes(",")) return null;
  if ("min" in s) {
    if (!isNum(s.min) || s.min <= 0) return null;
    const out = [[numText(s.min), "분"]];
    for (const [k, u] of [["kmh", "km/h"], ["deg", "도"]]) {
      if (s[k] == null) continue;
      if (!isNum(s[k]) || s[k] < 0) return null;
      out.push([numText(s[k]), u]);
    }
    return { date, time, item: `cardio:${ex}`, out };
  }
  const [k, u] = s.sec != null ? ["sec", "초"] : ["rep", "rep"];
  if (!isNum(s.kg) || s.kg < 0 || !Number.isInteger(s[k]) || s[k] <= 0) return null;
  return { date, time, item: `workout:${ex}`, out: [[numText(s.kg), "kg"], ["1", "set"], [String(s[k]), u]] };
}
function appRows(entriesRows, sets = [], cardio = []) {
  const have = {}, seen = {}, rows = [];
  for (const r of entriesRows) if (r.source === "app" && (r.unit === "kg" || r.unit === "분")) { const k = `${r.date}|${r.time}|${r.item}`; have[k] = (have[k] ?? 0) + 1; }
  for (const s of [...sets, ...cardio]) {
    const l = recLines(s);
    if (!l) continue; // 틀린 기록은 그것만 건너뜀 (페이지가 멈추지 않게)
    const k = `${l.date}|${l.time}|${l.item}`;
    seen[k] = (seen[k] ?? 0) + 1;
    if (seen[k] <= (have[k] ?? 0)) continue;
    for (const [value, unit] of l.out) rows.push({ date: l.date, time: l.time, kind: "quant", item: l.item, value, unit, source: "app" });
  }
  return rows;
}
const COLS = ["date", "time", "kind", "item", "value", "unit", "source"];
// 대시보드 entries 행 → core가 읽는 CSV 글 (parseCSV는 따옴표를 모르니 쉼표는 공백으로)
const toCSV = (rows) => [COLS.join(","), ...rows.map((r) => COLS.map((c) => String(r[c] ?? "").replace(/[,\r\n]/g, " ")).join(","))].join("\n");

// ---- app/village.js ----
// 승인된 동숲풍 시안의 래스터 소재와 화면 공통 표현. 저장/운동 계산과 분리한다.
const VILLAGE_ASSETS = {
  villagers: 'data:image/webp;base64,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',
  background: 'data:image/webp;base64,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',
  exercises: globalThis.LLW_EXERCISE_ASSETS?.main || '../app/assets/village/exercises.png', // 대시보드는 exercises-main.js(먼저 로드)
  font: '../app/assets/village/Jua-Regular.ttf',
};

// 전체 PNG(1536×1024)에 맞춘 부위 좌표. 앞/뒤 캐릭터 위에만 색을 입힌다.
const VILLAGE_REGIONS = [
  ['가슴',23,52,10,8], ['등',68,52,11,13],
  ['어깨',20,49,3,7], ['어깨',32,49,3,7],
  ['이두',17,56,4,7], ['이두',35,56,4,7],
  ['삼두',63,56,4,8], ['삼두',80,56,4,8],
  ['코어',24,61,8,7], ['둔근',67,70,13,8],
  ['대퇴사두',21,78,5,6], ['대퇴사두',29,78,5,6],
  ['햄스트링',67,78,5,6], ['햄스트링',75,78,5,6],
  ['종아리',67,84,5,4], ['종아리',75,84,5,4],
];
function villageBody(interactive = true) {
  const tag = interactive ? 'button' : 'span';
  return `<div class="village-body"><img class="village-people" src="${VILLAGE_ASSETS.villagers}" alt="운동 부위를 보여주는 캐릭터 앞모습과 뒷모습" draggable="false">${VILLAGE_REGIONS.map(([m,x,y,w,h]) => `<${tag} ${interactive ? 'type="button" data-action="region"' : ''} class="village-region rg" data-m="${m}" data-muscle="${m}" aria-label="${m}" style="left:${x}%;top:${y}%;width:${w}%;height:${h}%"></${tag}>`).join('')}<div class="village-views"><span>앞</span><span>뒤</span></div></div>`;
}

// 아틀라스마다 같은 3열×2행 좌표를 사용한다. 기존 그림과 신규 소재를 분리한다.
const EXERCISE_SHEETS = {
  exercises: ['체스트프레스','벤치프레스','펙덱 플라이','푸시업','딥스','케이블 플라이'],
  pull: ['랫풀다운','케이블 로우','스트레이트 암 풀다운','바벨로우','풀업','친업'],
  shoulders: ['숄더프레스','오버헤드프레스','덤벨 사이드 레터럴','덤벨 벤치프레스','스미스 벤치프레스','스미스 스쿼트'],
  legs: ['레그프레스','레그 익스텐션','레그 컬','스쿼트','데드리프트','스미스 루마니안 데드리프트'],
  floor: ['플랭크','사이드 플랭크','크런치','클램쉘','카프레이즈','트레드밀'],
  cardio: ['인클라인 트레드밀','스텝밀'],
};
const EXTRA_EXERCISE_ASSETS = {
  pull: '../app/assets/village/exercises-pull.png',
  shoulders: '../app/assets/village/exercises-shoulders.png',
  legs: '../app/assets/village/exercises-legs.png',
  floor: '../app/assets/village/exercises-floor.png',
  cardio: '../app/assets/village/exercises-cardio.png',
};
const EXERCISE_TILES = Object.fromEntries(Object.entries(EXERCISE_SHEETS).flatMap(([sheet,names]) => names.map((name,i) => [name,{sheet,i}])));
function villageExerciseArt(name) {
  const tile = EXERCISE_TILES[name];
  // 아직 등록되지 않은 새 종목에만 공통 캐릭터를 사용한다.
  if (!tile) return `<span class="village-exart village-exart-generic" aria-hidden="true"><img src="${VILLAGE_ASSETS.villagers}" alt=""></span>`;
  const {sheet,i} = tile;
  const src = sheet === 'exercises' ? VILLAGE_ASSETS.exercises : (globalThis.LLW_EXERCISE_ASSETS?.[sheet] || EXTRA_EXERCISE_ASSETS[sheet]);
  return `<span class="village-exart" aria-hidden="true"><img src="${src}" alt="" style="left:${-(i%3)*100}%;top:${-Math.floor(i/3)*100}%"></span>`;
}

const VILLAGE_CSS = `

.village-theme{word-break:keep-all;overflow-wrap:anywhere;--v-ink:#583b23;--v-muted:#867456;--v-paper:#fff8e3;--v-soft:#e7edc2;--v-green:#639d47;--v-orange:#f7a04c;--color-fg:var(--v-ink);--color-fg-muted:var(--v-muted);--color-panel:var(--v-paper);--color-bg:#f9f4df;--color-border-line:#e1d9b9;--cds-chart-grid:#e3e5c6;--cds-text-secondary:var(--v-muted);--cds-font-size-body:16px;--cds-font-size-caption:13px;--cds-radius:26px;--font-anthropic-sans:Jua,'Malgun Gothic',sans-serif;--font-anthropic-serif:var(--font-anthropic-sans);font:16px/1.5 var(--font-anthropic-sans);color:var(--v-ink);color-scheme:light}
.village-theme *{box-sizing:border-box}.village-theme button,.village-theme select,.village-theme input{font-family:inherit;color:inherit}.village-theme button{cursor:pointer}.village-theme :focus-visible{outline:3px solid #bd6428;outline-offset:3px}.village-theme button:disabled{cursor:wait;opacity:.6}
.village-theme.village-world{background-color:#92c94f;background-image:url("${VILLAGE_ASSETS.background}");background-size:100% auto;background-position:center top;background-repeat:no-repeat;border-radius:28px;padding:20px 22px 24px;max-width:640px;margin:0 auto;min-height:100vh}
.village-body{position:relative;width:100%;aspect-ratio:1.5;isolation:isolate;margin-bottom:38px}.village-people{display:block;width:100%;height:100%;object-fit:contain;user-select:none;pointer-events:none}.village-region{position:absolute;display:block;border:0;padding:0;margin:0;background:transparent;border-radius:28%;color:transparent;transition:background .18s,scale .18s;mix-blend-mode:multiply}.village-region.on,.village-region.active{background:var(--v-orange);opacity:.86}.village-region:hover{background:#f7a04c88}.village-views{position:absolute;left:0;right:0;top:calc(100% + 10px);height:22px}.village-views span{position:absolute;transform:translateX(-50%);font-size:13px;line-height:20px;padding:0 10px;border-radius:11px;background:var(--v-soft);color:var(--v-muted)}.village-views span:first-child{left:28%}.village-views span:last-child{left:73.5%}
.village-exart{display:block;position:relative;width:100%;aspect-ratio:1;overflow:hidden;pointer-events:none}.village-exart img{position:absolute;width:300%;max-width:none;height:200%;object-fit:fill;pointer-events:none}.village-exart-generic img{width:200%;height:100%;object-fit:fill;left:0;top:0}
.village-leaf{display:inline-block;width:22px;height:26px;border-radius:90% 5% 85% 15%;background:#699b49;rotate:25deg;vertical-align:middle;margin-right:7px}.village-brand{display:inline-flex;align-items:center;background:var(--v-paper);padding:7px 16px;border-radius:50px;font-size:25px;letter-spacing:.4px;text-decoration:none;color:var(--v-ink)}
.village-theme .village-paper{background:var(--v-paper);padding:22px;border-radius:32px}.village-theme .village-pill{border:0;border-radius:30px;background:var(--v-soft);padding:9px 16px}.village-theme .village-title{background:var(--v-paper);border-radius:45% 38% 35% 30% / 25% 30% 28% 35%;padding:20px 12px;text-align:center;font-size:32px;line-height:1.3;font-weight:400;letter-spacing:-.8px;margin:18px 0}
@media(max-width:420px){.village-theme.village-world{padding:14px 12px 22px;border-radius:0}.village-theme .village-title{font-size:27px;padding:17px 8px}.village-theme .village-paper{padding:16px;border-radius:26px}}
@media(prefers-reduced-motion:reduce){.village-theme *{animation:none!important;transition:none!important}}
@media (prefers-reduced-motion:no-preference){.ll-in-fwd{animation:ll-in-fwd .24s cubic-bezier(.2,.8,.2,1)}.ll-in-back{animation:ll-in-back .24s cubic-bezier(.2,.8,.2,1)}@keyframes ll-in-fwd{from{opacity:0;translate:36px 0}to{opacity:1;translate:0}}@keyframes ll-in-back{from{opacity:0;translate:-36px 0}to{opacity:1;translate:0}}}
/* F16 테마 드롭다운 (ui.js pickMenu) */
.village-theme select.ll-native{display:none}
.village-theme .ll-pickwrap{position:relative;display:inline-block;max-width:100%;vertical-align:middle}
.village-theme .ll-pickbtn{display:inline-flex;align-items:center;gap:8px;min-height:44px;max-width:100%;text-align:left;cursor:pointer}
.village-theme .ll-pickbtn>span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.village-theme .ll-pickbtn::after{content:"";flex:none;width:8px;height:8px;border:solid currentColor;border-width:0 2px 2px 0;rotate:45deg;margin:-4px 2px 0 4px;transition:rotate .2s}
.village-theme .ll-pickbtn[aria-expanded=true]::after{rotate:225deg;margin-top:4px}
.village-theme .ll-menu{position:absolute;left:0;top:calc(100% + 6px);z-index:40;box-sizing:border-box;min-width:100%;width:max-content;max-width:min(320px,calc(100vw - 32px));max-height:300px;overflow:auto;overscroll-behavior:contain;margin:0;padding:6px;list-style:none;background:var(--v-paper);color:var(--v-ink);border:2px solid var(--v-ink);border-radius:22px;box-shadow:0 10px 24px rgba(60,40,20,.22);font-size:17px;text-align:left}
.village-theme .ll-menu[hidden]{display:none}
.village-theme .ll-menu [role=option]{display:flex;align-items:center;gap:8px;min-height:44px;padding:8px 14px;border-radius:16px;cursor:pointer;white-space:nowrap;outline:none}
.village-theme .ll-menu [role=option]:is(:hover,:focus-visible){background:var(--v-soft)}
.village-theme .ll-menu [role=option][aria-selected=true]{background:var(--v-green);color:#fff}
.village-theme .ll-menu [role=option][aria-selected=true]::after{content:"✓";margin-left:auto}
@media (prefers-reduced-motion:no-preference){.village-theme .ll-menu{animation:llmenu .16s ease-out}@keyframes llmenu{from{opacity:0;translate:0 -6px}to{opacity:1;translate:0}}.village-theme .ll-menu [role=option]:active{scale:.97}}
`;

const VILLAGE_WORKOUT_CSS = `
.wk.village-theme{--bg:transparent;--fg:var(--v-ink);--muted:var(--v-muted);--accent:var(--v-green);--card:var(--v-paper);font:16px/1.5 Jua,'Malgun Gothic',sans-serif;padding:0;background:transparent;border-radius:0}
.wk .village-topbar{display:flex;align-items:center;justify-content:space-between;gap:12px}.wk .village-place{display:flex;align-items:center;gap:5px;background:var(--v-paper);padding:6px 12px;border-radius:40px;font-size:16px}.wk #wk-place{font-size:17px;border:0;padding:4px;background:transparent;max-width:130px}.wk #wk-notice:empty{display:none}.wk #wk-notice{background:var(--v-paper);border-radius:16px;color:#7b4f26;padding:8px 14px;font-size:13px;min-height:0}
.wk #wk-q{border:0;background:var(--v-paper);border-radius:40px;padding:15px 22px;font-size:18px;margin:0 0 16px}.wk .village-picker{display:grid;grid-template-columns:1.12fr 1fr;align-items:center;gap:12px;background:var(--v-paper);border-radius:34px;padding:20px 14px;margin:0 0 16px}.wk #wk-body{width:100%;max-width:none;margin:0}.wk .village-muscles h2{font-size:20px;font-weight:400;margin:0 0 12px}.wk .village-muscle-list{display:grid;grid-template-columns:1fr 1fr;gap:7px}.wk .village-muscle-list button{border:0;border-radius:30px;padding:7px 3px;background:var(--v-soft);font-size:14px;min-height:44px}.wk .village-muscle-list button.on{background:var(--v-orange)}
.wk .btns{max-width:none;background:var(--v-paper);padding:10px;border-radius:28px;margin:0 0 16px}.wk .btns button{border-radius:24px;background:var(--v-soft);font-size:17px;padding:9px}.wk .btns button:focus{background:#c8dda1}.wk ul.drop{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));padding:12px;gap:9px;border-radius:30px;margin:12px 0 16px}.wk ul.drop:empty{display:none}.wk ul.drop li{border:0;min-width:0;padding:8px 4px;border-radius:22px;background:#f4efd6;text-align:center;font-size:14px;line-height:1.35}.wk ul.drop li:hover,.wk ul.drop li:focus-within{background:#deebbb;box-shadow:inset 0 0 0 2px #78a957}.wk ul.drop li button{width:100%;border:0;background:none;padding:0;display:flex;flex-direction:column;align-items:center;gap:5px}.wk ul.drop li small{font-size:12px}.wk ul.drop li.none{grid-column:1/-1;padding:18px}.wk #wk-drop{grid-template-columns:repeat(2,minmax(0,1fr))}.wk #wk-drop .village-exart{width:88px}.wk .village-catalog-title{font-size:19px;font-weight:400;margin:14px 12px 6px;background:var(--v-paper);display:inline-block;padding:6px 15px;border-radius:25px}
.wk #wk-back,.wk #wk-cBack{background:var(--v-paper);border:0;border-radius:30px;padding:0 15px;min-height:44px;font-size:14px;margin-top:16px}.wk #wk-setTitle,.wk #wk-cTitle{font-size:31px;font-weight:400;text-align:center;background:var(--v-paper);border-radius:38px;padding:14px 12px;margin:12px 0 10px}.wk #wk-setMuscles{text-align:center;background:var(--v-soft);border-radius:30px;padding:6px 16px;margin:0 auto 16px;width:fit-content;font-size:15px}.wk #wk-stage{background:var(--v-paper);border-radius:30px;padding:12px 20px;min-height:0;margin:0 0 16px;display:block}.wk #wk-stage .village-body{max-width:320px;margin:auto}.wk #wk-stage .village-people{width:100%;height:100%;transform-origin:center 85%}.wk #wk-stage .village-region{position:absolute}.wk #wk-stage .village-body{transform:scale(calc(1 + (1 - var(--r,1))*.08),calc(1 - (1 - var(--r,1))*.08));transition:transform .9s linear}.wk #wk-stage .village-region.hit{animation:wk-patch .42s ease-out}.wk #wk-stage .village-region.hit-sm{animation:wk-patch .3s ease-out}.wk #wk-stage .village-region.secondary{opacity:.4}.wk .village-entry{background:var(--v-paper);border-radius:32px;padding:20px}.wk #wk-setNo{text-align:center;font-size:27px;background:var(--v-soft);padding:5px 20px;border-radius:30px;width:fit-content;margin:0 auto 18px;color:var(--v-ink)}
.wk .row{display:grid;grid-template-columns:48px 44px minmax(0,1fr) 30px 44px;gap:8px;background:#edf0d1;border-radius:30px;padding:10px 12px;margin:10px 0}.wk .row .village-step{border:0;border-radius:50%;background:var(--v-green);color:white;font-size:26px;width:44px;height:44px;padding:0;line-height:1}.wk .row :is(select,.ll-pickbtn){width:100%;min-width:0;padding:8px 6px;font-size:25px;justify-content:center;border:1px solid #d7cda8;background:#fffaf0;text-align:center;border-radius:24px}.wk .row label{font-size:18px}.wk .row .err{grid-column:1/-1;min-width:0;text-align:center;font:12px/1.4 sans-serif}.wk .row .err:empty{display:none}.wk #wk-previous{text-align:center;font-size:14px;color:var(--v-muted);margin:12px 0}.wk #wk-done,.wk #wk-cDone{font-size:24px;border-radius:50px;border:3px solid #e8efcf;box-shadow:0 3px 0 #d4dcb3;padding:13px;margin:10px 0 0;background:var(--v-green)}
.wk #wk-rest:empty{display:none}.wk #wk-rest{font-size:27px;background:var(--v-soft);border-radius:25px;margin-top:15px;padding:6px}.wk .village-records{background:var(--v-paper);padding:18px 20px;border-radius:30px;margin-top:16px}.wk .village-records h3{font-size:21px;font-weight:400;margin:0 0 12px}.wk #wk-today,.wk #wk-cToday{display:flex;flex-direction:column;gap:7px;margin:0}.wk #wk-today li,.wk #wk-cToday li{border-radius:18px;padding:8px 10px 8px 15px;background:var(--v-soft);font-size:16px;justify-content:space-between}.wk #wk-today li::before{content:'✓';color:white;background:#7fa655;padding:0 5px;border-radius:7px;margin-right:8px}.wk #wk-today button{font-size:19px}.wk #wk-today:empty::after{content:'첫 세트를 기록해 보세요';font-size:14px;padding:8px;color:var(--v-muted)}.wk #wk-saveNote,.wk #wk-cWarn{font-family:system-ui,sans-serif;font-size:12px;margin:12px 0 0;line-height:1.5}.wk #wk-saveNote:empty{display:none}.wk #wk-fx{background:var(--v-paper);border-radius:24px;padding:15px 18px;margin-top:16px}.wk #wk-fx summary{cursor:pointer;font-size:17px}.wk #wk-fx :is(select,.ll-pickbtn){background:#f7f2dc;border:1px solid #ddd2ad;border-radius:24px;font-size:15px}.wk .village-foot{display:flex;justify-content:space-around;background:var(--v-paper);border-radius:30px;padding:12px;margin:16px 0 0}.wk .village-foot a{color:var(--v-ink);text-decoration:none;padding:6px 18px;border-radius:20px}.wk .village-foot .current{background:#dce8b6}.wk #wk-cardio .row{grid-template-columns:80px minmax(0,1fr) 50px}.wk #wk-cardio .row :is(select,.ll-pickbtn){font-size:23px}.wk #wk-cardio{background:var(--v-paper);border-radius:28px;padding:15px;margin-top:15px}.wk #wk-runner img{width:150px;height:100px;object-fit:contain}
@keyframes wk-patch{20%{scale:calc(1.2 * var(--k,1)) calc(.78 / var(--k,1));background:#ffd690;box-shadow:0 0 0 calc((var(--k,1) - 1) * 30px) #ffd69099}60%{scale:.95 1.08}100%{scale:1}}
@media(max-width:420px){.wk .village-picker{gap:5px;padding:14px 8px}.wk .village-muscles h2{font-size:18px}.wk .village-muscle-list{gap:5px}.wk .village-muscle-list button{font-size:13px;min-height:44px;padding:5px 2px}.wk .village-entry{padding:16px 12px}.wk .row{grid-template-columns:40px 44px minmax(0,1fr) 22px 44px;gap:5px;padding:8px}.wk .row .village-step{width:44px;height:44px}.wk .row :is(select,.ll-pickbtn){font-size:23px}.wk ul.drop{gap:6px;padding:9px}.wk ul.drop li{font-size:12px}.wk .village-foot a{padding:6px 14px}}
`;

const VILLAGE_DASH_CSS = `
:root .ll.village-theme.village-world{max-width:640px;gap:18px;--ll-accent:#659b46;--ll-push:#efa04b;--ll-pull:#8cae56;--ll-legs:#659b46;--ll-core:#bd9c55;--ll-good:#659b46;--ll-hero-bg:#fff8e3;--ll-push-bg:#eef0d2;--ll-pull-bg:#edf1d9;--ll-legs-bg:#e9efce;--ll-core-bg:#f3ebd1}
.ll.village-theme .ll-headrow{display:block}.ll.village-theme .ll-title{display:flex;justify-content:space-between;font:27px/1.2 Jua,sans-serif;margin:3px 0 16px;background:var(--v-paper);border-radius:40px;padding:15px 20px}.ll.village-theme .ll-brand{background:none;color:var(--v-green);font:19px Jua,sans-serif;padding:0}.ll.village-theme .ll-tabs{justify-content:space-around;background:var(--v-paper);border:0;padding:7px;border-radius:35px;gap:4px}.ll.village-theme .ll-tab{font-size:17px;flex:1;padding:9px 5px;color:var(--v-ink)}.ll.village-theme .ll-tab.on{background:#dce9b8;color:var(--v-ink);font-weight:400}
.ll.village-theme .ll-banner{background:var(--v-paper);color:var(--v-ink);border-radius:24px;box-shadow:none;padding:13px 40px 13px 15px;min-height:0}.ll.village-theme .ll-banner svg{display:none}.ll.village-theme .ll-banner .bc{color:var(--v-muted)}.ll.village-theme .ll-banner .bt{color:var(--v-muted)}
.ll.village-theme .ll-sub-head{background:var(--v-paper);padding:13px 16px;border-radius:27px;gap:9px}.ll.village-theme .ll-line{font-size:13px}.ll.village-theme :is(select,.ll-pickbtn){background:#edf0d1;border:0;border-radius:25px;padding:9px 12px;font-size:15px}.ll.village-theme .ll-go{border:3px solid #e8efcf;border-radius:40px;padding:0 18px;min-height:44px;font-size:17px}.ll.village-theme .ll-hero{background:var(--v-paper);border:0;box-shadow:none;border-radius:32px;padding:20px;gap:16px}.ll.village-theme .ll-hero-top{flex-direction:column;align-items:center}.ll.village-theme .ll-hero-top>.ll-h2{font-size:27px;font-weight:400}.ll.village-theme .ll-grade{justify-content:center}.ll.village-theme .ll-grade b{font:28px Jua,sans-serif;color:var(--v-green)}.ll.village-theme .ll-grade span{font-size:12px;max-width:200px}.ll.village-theme .ll-bodywrap{display:flex;flex-direction:column;gap:18px}.ll.village-theme .ll-bodywrap>div{width:100%}.ll.village-theme .ll-body{max-width:380px}.ll.village-theme .ll-body .village-body{margin:0 auto 38px}.ll.village-theme .ll-glegend{justify-content:center;font-size:12px}.ll.village-theme .ll-stats{justify-content:center;gap:8px}.ll.village-theme .ll-stat{background:var(--v-soft);border:0;border-radius:20px;padding:6px 10px;font-size:13px}.ll.village-theme .ll-stat b{font-size:19px}.ll.village-theme .ll-stat i{display:none}.ll.village-theme .ll-cmt li{border:0;border-radius:18px;background:#eef0d3}.ll.village-theme .ll-ppl{padding:12px;background:#f1eed7;border-radius:20px}
.ll.village-theme .ll-page>.ll-sec:not(#workout){background:var(--v-paper);padding:20px;border-radius:30px}.ll.village-theme .ll-h2{font-size:21px;font-weight:400}.ll.village-theme .ll-focus{background:var(--v-paper);border:0;border-radius:28px;padding:18px}.ll.village-theme .ll-focus p{font-size:17px}.ll.village-theme .ll-note{font-size:12px;color:var(--v-muted)}.ll.village-theme .ll-mrow{padding:9px 0;gap:10px;grid-template-columns:85px minmax(0,1fr) 65px}.ll.village-theme .ll-mbar{height:16px;background:#e7e7c8;border-radius:9px}.ll.village-theme .ll-mbar span{border-radius:9px}.ll.village-theme .ll-mrow .nm,.ll.village-theme .ll-mrow .vl{font-size:15px}.ll.village-theme .ll-mrow .nm i{display:none}.ll.village-theme .ll-table th,.ll.village-theme .ll-table td{padding:10px 6px;font-size:13px;border-color:#e6ddbd}.ll.village-theme .ll-table th{color:var(--v-muted)}.ll.village-theme .ll-big{font:29px Jua,sans-serif}.ll.village-theme .ll-card{background:var(--v-soft);border:0;border-radius:22px;padding:15px}.ll.village-theme .ll-tiles{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.ll.village-theme .ll-dot{width:14px;height:14px}.ll.village-theme .ll-strip{gap:5px;min-height:120px}.ll.village-theme .ll-day{border:0;background:#edf0d4;border-radius:22px;padding:10px 0}.ll.village-theme .ll-day.today{box-shadow:inset 0 0 0 2px var(--v-green)}.ll.village-theme .ll-barbox{background:#dedfbd}.ll.village-theme .ll-chart{background:var(--v-paper);border-radius:20px}.ll.village-theme .ll-chip{border:0;background:var(--v-soft)}.ll.village-theme .ll-wk{max-width:none;width:100%}.ll.village-theme:has(#input:not([hidden]))>.ll-banner{display:none}.ll.village-theme .wk .village-brand{display:none}.ll.village-theme .ll-row{font-size:14px}.ll.village-theme .ll-hbar{height:14px;background:#e4e5c7}.ll.village-theme .ll-body .ll-tip{background:var(--v-paper);border:1px solid #d9cead;padding:5px 10px;border-radius:18px;z-index:3}
.village-theme .village-week-title{font-size:27px;text-align:center;font-weight:400;margin:0 0 14px}.village-theme #week .ll-sub-head{justify-content:center}
@media(max-width:420px){.ll.village-theme .ll-hero{padding:16px}.ll.village-theme .ll-mrow{grid-template-columns:72px minmax(0,1fr) 54px;gap:7px}.ll.village-theme .ll-mrow .nm,.ll.village-theme .ll-mrow .vl{font-size:13px}.ll.village-theme .ll-stat{font-size:12px;padding:5px 8px}.ll.village-theme .ll-stat b{font-size:17px}}
.ll.village-theme .ll-title{justify-content:flex-start;gap:8px}.ll.village-theme .ll-tabs .ll-pickwrap{flex:1;display:flex}.ll.village-theme .ll-tabs .ll-pickbtn{flex:1;gap:6px;justify-content:center;background:transparent;font-size:17px;padding:9px 5px}.ll.village-theme .ll-tabs .ll-pickbtn.on{background:#dce9b8}.ll.village-theme .ll-tabs .ll-pickbtn::after{position:static;translate:none;width:8px;height:8px}.ll.village-theme .ll-tab.ll-input{flex:1.4;background:var(--v-orange);color:#fff;box-shadow:0 3px 0 rgba(120,70,20,.25)}.ll.village-theme .ll-tab.ll-input.on{outline:3px solid var(--v-ink);outline-offset:-3px}
`;

// F19 마을 테마: 화면이 쓰는 것은 모두 이 묶음으로만 (app/theme.js에 등록)
const VILLAGE = {
  id: "village", name: "마을", swatch: "#92c94f",
  font: { family: "Jua", href: "https://fonts.googleapis.com/css2?family=Jua&display=swap" },
  classes: { dash: "village-theme village-world", workout: "village-theme" },
  css: { base: VILLAGE_CSS, dash: VILLAGE_DASH_CSS, workout: VILLAGE_WORKOUT_CSS },
  assets: VILLAGE_ASSETS,
  // 진동(ms): 버튼·이동·고르기·부위/버튼 찌그러짐·휴식 끝·세트 타격 단계·유산소 완주
  haptic: { tap: [25], nav: [40], pick: [20, 40, 20], touch: [15], rest: [30, 80, 30],
    hit: { normal: [40], strong: [40, 60, 60], best: [400] }, finish: [30, 40, 30, 40, 120] },
  body: villageBody,
  exerciseArt: villageExerciseArt,
  slots: {}, // 기본 조각(app/ui.js SLOTS) 그대로
};

// ---- app/usagi.js ----
// 승인된 평면 우사기 상점 테마. 저장/계산/액션은 기존 테마 공용 구현 사용.

const USAGI_ASSETS = Object.fromEntries(['body','shop','chest','pull','shoulders','legs','floor','cardio','awake','fire','seoulupper','seoullower','seoulcore'].map(name => [name, globalThis.LLW_USAGI_ASSETS?.[name] || `../app/assets/usagi/${name}.png`]));
// 터치 팝콘 6포즈: 대시보드는 usagi-pop.js 한 문서로 받음(USAGI_ASSETS와 따로)
const USAGI_POP = [1,2,3,4,5,6].map(i => globalThis.LLW_USAGI_ASSETS?.['pop'+i] || `../app/assets/usagi/pop${i}.png`);
const USAGI_SHEETS = {
  chest: ['체스트프레스','벤치프레스','펙덱 플라이','푸시업','딥스','케이블 플라이'],
  pull: ['랫풀다운','케이블 로우','스트레이트 암 풀다운','바벨로우','풀업','친업'],
  shoulders: ['숄더프레스','오버헤드프레스','덤벨 사이드 레터럴','덤벨 벤치프레스','스미스 벤치프레스','스미스 스쿼트'],
  legs: ['레그프레스','레그 익스텐션','레그 컬','스쿼트','데드리프트','스미스 루마니안 데드리프트'],
  floor: ['플랭크','사이드 플랭크','크런치','클램쉘','카프레이즈','트레드밀'],
  cardio: ['인클라인 트레드밀','스텝밀'],
  seoulupper: ['머신 컬','프리처 컬','머신 로우','리어 델트 로우','트라이셉스 익스텐션','시티드 딥'],
  seoullower: ['디클라인 벤치프레스','머신 스쿼트','힙 어덕션','힙 어브덕션','힙 쓰러스트','머신 크런치'],
  seoulcore: ['로터리 토르소','백 익스텐션','케틀벨 스윙','커브드 트레드밀','로잉'],
};
const USAGI_TILES = Object.fromEntries(Object.entries(USAGI_SHEETS).flatMap(([sheet,names]) => names.map((name,i) => [name,{sheet,i}])));
function usagiExerciseArt(name) {
  const {sheet,i} = USAGI_TILES[name] || {sheet:'cardio',i:2};
  return `<span class="village-exart" aria-hidden="true"><img src="${USAGI_ASSETS[sheet]}" alt="" style="left:${-(i%3)*100}%;top:${-Math.floor(i/3)*100}%"></span>`;
}
// PNG 전체에 대한 백분율. 2026-11-21 새 앞뒤 그림(분홍·주황 자극 표시 자리)에서 잰 위치.
const USAGI_REGIONS = [
  ['가슴',16.8,62.8,10.9,9.2],['가슴',28.9,62.8,10.9,9.2],
  ['어깨',11.9,62.7,4.0,5.1],['어깨',40.0,62.7,4.0,5.1],
  ['이두',11.5,67.6,4.0,6.5],['이두',40.4,67.6,4.0,6.5],
  ['코어',21.5,72.9,13.5,11.8],['대퇴사두',20.3,85.8,5.7,7.0],
  ['대퇴사두',30.1,85.8,5.8,7.0],['등',62.7,57.9,21.9,15.5],
  ['삼두',57.3,65.5,4.7,9.1],['삼두',85.5,65.5,4.9,9.1],
  ['둔근',62.7,76.3,8.6,9.4],['둔근',76.5,76.3,8.5,9.4],
  ['햄스트링',65.4,86.2,4.9,4.6],['햄스트링',77.4,86.2,4.7,4.6],
  ['종아리',66.2,90.8,3.8,4.1],['종아리',77.8,90.8,3.7,4.1],
];
function usagiBody(interactive=true) {
  const tag = interactive ? 'button' : 'span';
  return `<div class="village-body usagi-body"><img class="village-people" src="${USAGI_ASSETS.body}" alt="우사기 앞모습과 뒷모습" draggable="false">${USAGI_REGIONS.map(([m,x,y,w,h]) => `<${tag} ${interactive?'type="button" data-action="region"':''} class="village-region rg" data-m="${m}" aria-label="${m}" style="left:${x}%;top:${y}%;width:${w}%;height:${h}%"></${tag}>`).join('')}<div class="village-views"><span>앞</span><span>뒤</span></div></div>`;
}
const usagiScope = css => css.replaceAll('.village-theme','.usagi-theme').replaceAll('.village-world','.usagi-world');
const USAGI_BASE = `
.usagi-theme{--v-ink:#38251f;--v-muted:#88766b;--v-paper:#fff9e9;--v-soft:#d9f2df;--v-green:#77b394;--v-orange:#f5a6bd;--color-border-line:#b9a895;--cds-chart-grid:#eee8d9;--cds-border:#b9a895;--color-bg:#fff9e9;color:var(--v-ink)}
.usagi-theme.usagi-world{background:#fff9e9;padding:12px 16px 24px;border-radius:22px;max-width:640px}
.usagi-theme button,.usagi-theme .ll-pickbtn{box-shadow:none}
.usagi-theme .village-region{border-radius:50%;mix-blend-mode:multiply}.usagi-theme .village-region.active,.usagi-theme .village-region.on{background:var(--rg,#f692b2)}/* 부위 색은 앞뒤 그림 시안 그대로: 분홍=가슴·어깨·대퇴사두·등·둔근, 주황=이두·코어·삼두·햄스트링, 진주황=종아리 */.usagi-theme .village-region:is([data-m=가슴],[data-m=대퇴사두],[data-m=등],[data-m=둔근]){--rg:#f47fa3}.usagi-theme .village-region:is([data-m=이두],[data-m=코어],[data-m=삼두],[data-m=햄스트링]){--rg:#f8a256}.usagi-theme .village-region:is([data-m=어깨],[data-m=종아리]){--rg:#e07b3c}
.usagi-theme .village-views span{background:#fff9e9;border:1px solid #b9a895;padding:0 12px}.usagi-theme .village-views span:first-child{left:27%}.usagi-theme .village-views span:last-child{left:73%}
.usagi-theme .ll-menu{background:#fff9e9;border:2px solid #594136;border-radius:18px}.usagi-theme .ll-menu [role=option][aria-selected=true]{background:#f8c0d1}.usagi-theme .ll-menu [role=option]:hover{background:#d9f2df}
@media(max-width:420px){.usagi-theme.usagi-world{padding:8px 10px 20px;border-radius:0}}
`;
const USAGI_DASH = `
:root .ll.usagi-theme.usagi-world{--ll-accent:#ed97b2;--ll-push:#ed97b2;--ll-pull:#7fbda6;--ll-legs:#b6c780;--ll-core:#cfacd1;--ll-good:#77b394;--ll-push-bg:#fce4eb;--ll-pull-bg:#e0f1e7;--ll-legs-bg:#edf1d9;--ll-core-bg:#f3e8f2;gap:14px}
.ll.usagi-theme .ll-title .ll-flame{display:none}.ll.usagi-theme .ll-headrow{background: url("${USAGI_ASSETS.shop}") center top/100% auto no-repeat;padding-top:1px;min-height:160px}
.ll.usagi-theme .ll-title{height:auto;aspect-ratio:3.5;background:transparent;border:0;margin:0;padding:0 20% 3%;align-items:center;justify-content:center;font-size:clamp(26px,5vw,38px);white-space:nowrap;letter-spacing:2px;color:#38251f}
.ll.usagi-theme .ll-headrow>.ll-pickwrap{top:22px;right:8px}.ll.usagi-theme .ll-headrow .ll-themepick.ll-pickbtn{background:#fff9e9;border:2px solid #594136}
.ll.usagi-theme .ll-tabs{background:transparent;border:0;border-radius:0;padding:0;margin:12px 0 0;gap:8px}
.ll.usagi-theme .ll-tabs .ll-pickbtn,.ll.usagi-theme .ll-tab.ll-input{border:2px solid #594136;border-radius:30px;min-height:42px;color:#38251f;font-size:20px;padding:7px 12px;box-shadow:none;background:#fff9e9}
.ll.usagi-theme .ll-tabs .ll-pickbtn.on{background:#cff0dd}.ll.usagi-theme .ll-tab.ll-input.on{background:#f7b4cb;outline:0}
.ll.usagi-theme .ll-sub-head{border:0;background:transparent;padding:0;gap:8px}.ll.usagi-theme .ll-line{font-size:12px;flex-basis:100%}
.ll.usagi-theme :is(select,.ll-pickbtn){background:#fff9e9;border:1.5px solid #594136;padding:6px 12px}.ll.usagi-theme .ll-go{background:#f7b4cb;color:#38251f;border:1.5px solid #594136;box-shadow:none}
.ll.usagi-theme .ll-hero,.ll.usagi-theme .ll-page>.ll-sec:not(#workout){border:2px solid #594136;border-radius:22px;background:#fff9e9;padding:16px}
.ll.usagi-theme .ll-hero-top>.ll-h2,.ll.usagi-theme .ll-page>.ll-sec>.ll-h2{align-self:center;background:#f8bfd0;border:1.5px solid #594136;border-radius:30px;padding:3px 20px;font-size:22px}
.ll.usagi-theme .ll-grade b{color:#38251f;font-size:23px}.ll.usagi-theme .ll-stat{border:1.5px solid #594136;background:#d9f2df;border-radius:30px}.ll.usagi-theme .ll-body{max-width:350px;margin:auto}
.ll.usagi-theme .ll-ppl{background:transparent;border:1px solid #b9a895}.ll.usagi-theme .ll-points li{border-radius:20px;border:1px solid #b9a895;background:#fff9e9;padding:8px}.ll.usagi-theme .ll-mbar,.ll.usagi-theme .ll-hbar{background:#fffdf5;border:1px solid #594136}.ll.usagi-theme .ll-card{border:1.5px solid #594136;background:#fff9e9}.ll.usagi-theme .ll-focus{background:#e7f2e6;border:1px solid #b9a895}.ll.usagi-theme .ll-banner{border:1px solid #b9a895}
@media(max-width:420px){.ll.usagi-theme .ll-headrow{min-height:120px}.ll.usagi-theme .ll-headrow>.ll-pickwrap{top:9px;right:3px}.ll.usagi-theme .ll-title{font-size:27px}.ll.usagi-theme .ll-tabs{margin-top:8px}.ll.usagi-theme .ll-tabs .ll-pickbtn,.ll.usagi-theme .ll-tab.ll-input{font-size:17px}.ll.usagi-theme .ll-hero,.ll.usagi-theme .ll-page>.ll-sec:not(#workout){padding:12px}}
`;
const USAGI_WORKOUT = `
.wk.usagi-theme .village-topbar{flex-wrap:wrap}.wk.usagi-theme .usagi-shop-link{display:flex;justify-content:center;align-items:center;width:100%;aspect-ratio:3;padding:0 20% 6%;background:url("${USAGI_ASSETS.shop}") center top/100% auto no-repeat;border-radius:0;font-size:32px}.wk.usagi-theme #wk-runner{font-size:0;width:150px;height:150px;margin:8px auto;background:url("${USAGI_ASSETS.cardio}") right top/300% 200% no-repeat}.wk.usagi-theme{font-family:LifelogJua,Jua,sans-serif;color:#38251f}.wk.usagi-theme .village-place{padding:0;background:transparent}.wk.usagi-theme .village-place .ll-pickbtn{background:#fff9e9;border:1.5px solid #594136}.wk.usagi-theme .village-topbar{justify-content:flex-start}
.wk.usagi-theme .village-title{background:transparent;font-size:28px;margin:12px 0;padding:4px}.wk.usagi-theme #wk-q{border:2px solid #594136;border-radius:30px;background:#fffdf7;font-size:17px;padding:10px 16px;margin-bottom:12px}
.wk.usagi-theme .village-picker{border:2px solid #594136;border-radius:18px;padding:14px 10px;gap:10px;grid-template-columns:1fr 1fr}.wk.usagi-theme .village-muscles h2{display:none}.wk.usagi-theme .village-muscle-list button{border:1.5px solid #594136;background:#fff9e9;font-size:14px;padding:4px 2px;min-height:44px}.wk.usagi-theme .village-muscle-list button.on{background:#f7b4cb}
.wk.usagi-theme .btns{background:transparent;padding:0;gap:8px}.wk.usagi-theme .btns button{border:2px solid #594136;border-radius:14px;background:#cff0dd;padding:7px;font-size:19px}
.wk.usagi-theme .village-catalog-title{display:block;text-align:center;margin:12px 0 5px;background:transparent;font-size:23px}.wk.usagi-theme ul.drop{background:transparent;padding:0;gap:8px}.wk.usagi-theme ul.drop li{border:1.5px solid #594136;background:#fff9e9;border-radius:14px;padding:6px}.wk.usagi-theme ul.drop li:hover{background:#fce4eb;box-shadow:none}.wk.usagi-theme ul.drop li button{font-size:15px}.wk.usagi-theme ul.drop li .village-exart{max-height:140px}
.wk.usagi-theme #wk-back,.wk.usagi-theme #wk-cBack{border:1.5px solid #594136;margin-top:8px}.wk.usagi-theme #wk-setTitle{background:transparent;font-size:29px;margin:0;padding:8px}.wk.usagi-theme #wk-setMuscles{border:1px solid #7d9da5;background:#d6eaf3;padding:3px 16px;margin-bottom:12px}
.wk.usagi-theme #wk-stage{border:2px solid #594136;border-radius:20px;padding:6px 20px 12px}.wk.usagi-theme #wk-stage .village-body{max-width:300px}.wk.usagi-theme .village-entry{border:2px solid #594136;border-radius:20px;padding:16px}.wk.usagi-theme #wk-setNo{background:#f8bfd0;border:1.5px solid #594136;font-size:24px;margin-bottom:12px;padding:2px 24px}
.wk.usagi-theme .row{background:transparent;padding:3px 0;gap:8px}.wk.usagi-theme .row .village-step{color:#38251f;background:#cff0dd;border:1.5px solid #594136}.wk.usagi-theme .row .ll-pickbtn{border:1.5px solid #594136;background:#fffdf7;font-size:25px;min-height:44px;padding:2px 12px;justify-content:center}.wk.usagi-theme #wk-done,.wk.usagi-theme #wk-cDone{color:#38251f;background:#f6a7c2;border:2px solid #594136;border-radius:18px;box-shadow:none;padding:10px;font-size:25px}
.wk.usagi-theme .village-records{border:2px solid #594136;border-radius:20px;padding:15px}.wk.usagi-theme .village-records h3{text-align:center;background:#f8bfd0;border:1.5px solid #594136;border-radius:30px;margin:0 auto 12px;width:fit-content;padding:2px 24px}.wk.usagi-theme #wk-today li{border:1px solid #b9a895;background:#fffdf7}
.wk.usagi-theme #wk-fx{border:1.5px solid #594136;border-radius:14px;padding:10px 14px;margin-top:12px;background:#fff9e9}.wk.usagi-theme .village-foot{border:0;background:transparent;padding:0;gap:6px;margin-top:12px}.wk.usagi-theme .village-foot a{flex:1;text-align:center;border:1.5px solid #594136;border-radius:14px;background:#cff0dd;padding:10px 0}.wk.usagi-theme .village-foot a.current{background:#f7b4cb}
@media(max-width:420px){.wk.usagi-theme .village-muscle-list button{font-size:13px;min-height:44px}.wk.usagi-theme .village-picker{padding:10px 7px;gap:5px}.wk.usagi-theme ul.drop li button{font-size:12px}.wk.usagi-theme .village-title{font-size:24px}.wk.usagi-theme .village-entry{padding:12px}.wk.usagi-theme #wk-stage .village-body{max-width:260px}}
`;
const USAGI = {
  id:'usagi',name:'우사기 상점',swatch:'#f5a6bd',font:VILLAGE.font,
  classes:{dash:'usagi-theme usagi-world',workout:'usagi-theme'},
  css:{base:usagiScope(VILLAGE.css.base)+USAGI_BASE,dash:usagiScope(VILLAGE.css.dash)+USAGI_DASH,workout:usagiScope(VILLAGE.css.workout)+USAGI_WORKOUT},
  assets:USAGI_ASSETS,haptic:VILLAGE.haptic,body:usagiBody,exerciseArt:usagiExerciseArt,
  awake:{char:USAGI_ASSETS.awake,fire:USAGI_ASSETS.fire}, // 오운완(큰 부위 6/6) 각성: 앞뒤 캐릭터(누끼) + 불꽃 6프레임 띠. 없는 테마는 오운완 버튼 숨김
  pop:USAGI_POP, // 터치 팝콘: 누른 자리에서 6마리 튀어오름(ui.js touchPop). 없는 테마는 효과 없음
  slots:{top:()=>`<header class="village-topbar"><a class="village-brand usagi-shop-link" data-action="nav" data-nav="day" href="../dashboard/local.html#day">득근득근</a><label class="village-place">장소 <select id="wk-place"></select></label></header><p id="wk-notice"></p>`},
};

// ---- app/theme.js ----
// F19 테마 층: 테마 = 겉모습 묶음(글꼴·그림·CSS·진동 세기·화면 조각). 기능(저장·계산·연출 시점)은 core.js 하나
// 새 테마: 파일 하나 만들고 아래 THEMES에 등록하면 🎨 목록에 나온다

const THEMES = { village: { ...VILLAGE, pop: USAGI_POP } };
const DEFAULT_THEME = "village";
const THEME_FIELDS = ["id", "name", "swatch", "font", "classes", "css", "assets", "haptic", "body", "exerciseArt", "slots"];
const HAPTIC_FIELDS = ["tap", "nav", "pick", "touch", "rest", "hit", "finish"];

// 빠진 필드 이름 목록 (비면 쓸 수 있는 테마)
const themeProblems = (t) => [...THEME_FIELDS.filter((k) => t?.[k] == null), ...HAPTIC_FIELDS.filter((k) => t?.haptic && t.haptic[k] == null).map((k) => "haptic." + k)];
// 모르는 id·빠진 필드면 기본(우사기)
const pickTheme = (id, themes = THEMES) => (themes[id] && !themeProblems(themes[id]).length ? themes[id] : themes[DEFAULT_THEME]);
const themeList = (themes = THEMES) => Object.values(themes).filter((t) => !themeProblems(t).length).map(({ id, name, swatch }) => ({ id, name, swatch }));

let current = THEMES[DEFAULT_THEME];
const listeners = new Set();
const theme = () => current;
function setTheme(id) {
  const next = pickTheme(id);
  if (next !== current) { current = next; listeners.forEach((f) => f(current)); }
  return current;
}
const onTheme = (f) => { listeners.add(f); return () => listeners.delete(f); };

// ---- app/ui.js ----
// 운동 화면 UI: root 안에만 그린다 (대시보드 '운동' 탭과 app/index.html이 같이 씀, F14)
// id는 wk- 접두, CSS는 .wk 안 — 대시보드 문서의 다른 부분을 건드리지 않게

const CSS = `
.wk { --bg: #fff8f2; --fg: #2b2118; --muted: #8a7a6c; --accent: #ff7a59; --card: #ffffff; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; padding: 16px; border-radius: 16px; }
@media (prefers-color-scheme: dark) { .wk { --bg: #1d1712; --fg: #f5ece4; --muted: #a8988a; --card: #2a221b; } }
.wk select, .wk input, .wk button { font: inherit; }
.wk select, .wk .ll-pickbtn { font-size: 18px; padding: 8px 12px; border-radius: 12px; }
.wk #wk-notice { color: var(--accent); min-height: 1.5em; margin: 8px 0; }
.wk ul.drop { list-style: none; padding: 0; margin: 0; background: var(--card); border-radius: 12px; }
.wk ul.drop li { padding: 12px; border-bottom: 1px solid color-mix(in srgb, var(--muted) 25%, transparent); cursor: pointer; }
.wk ul.drop li.none { color: var(--muted); cursor: default; }
.wk ul.drop li small { color: var(--muted); }
.wk #wk-q { width: 100%; box-sizing: border-box; font-size: 18px; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--muted); }
.wk #wk-body { position: relative; max-width: 340px; margin: 16px auto 8px; touch-action: manipulation; }
.wk #wk-body svg { display: block; width: 100%; height: auto; }
.wk #wk-body text { fill: var(--muted); font-size: 9px; }
.wk #wk-body .nt { fill: color-mix(in srgb, var(--muted) 30%, transparent); }
.wk #wk-body .rg { fill: color-mix(in srgb, var(--accent) 55%, var(--card)); stroke: var(--bg); stroke-width: 1.5; cursor: pointer; }
.wk #wk-body .rg.on { fill: var(--accent); }
.wk #wk-body .rg:focus-visible { outline: none; stroke: var(--fg); }
.wk [data-m].squish { animation: wk-squish .18s ease-out; }
.wk .squish img, .wk .btns .squish span { animation: wk-squish .18s ease-out; }
.wk .btns { display: flex; gap: 8px; max-width: 340px; margin: 0 auto 8px; }
.wk .btns button { flex: 1; font-size: 18px; padding: 12px; border: 0; border-radius: 14px; background: var(--card); color: var(--fg); cursor: pointer; }
.wk .btns span { display: inline-block; }
@keyframes wk-squish { 40% { transform: scale(1.15, .8); } 100% { transform: none; } }
.wk .hide { display: none; }
.wk #wk-set h2, .wk #wk-cardio h2 { margin: 8px 0 0; }
.wk #wk-setNo { color: var(--muted); margin: 0 0 12px; }
.wk .row { display: flex; gap: 12px; align-items: center; margin: 8px 0; }
.wk .row select, .wk .row .ll-pickwrap { flex: 1; font-size: 22px; padding: 12px; }
.wk .err { color: #e5484d; font-size: 14px; min-width: 7em; }
.wk #wk-runner { font-size: 64px; text-align: center; margin: 8px 0; }
.wk #wk-runner.go { animation: wk-run .6s ease-out; }
@keyframes wk-run { 30% { transform: translateX(24px) scale(1.3, .85); } 60% { transform: translateX(-8px) scale(.95, 1.1); } 100% { transform: none; } }
.wk #wk-cDone, .wk #wk-done { width: 100%; font-size: 22px; padding: 18px; border: 0; border-radius: 16px; background: var(--accent); color: #fff; margin: 12px 0; }
.wk #wk-rest { font-size: 32px; font-variant-numeric: tabular-nums; text-align: center; margin: 4px 0; min-height: 1.2em; }
.wk #wk-rest.ready { color: var(--accent); }
.wk #wk-stage .p img, .wk #wk-stage .s img { --r: 1; transform: scale(calc(1 + (1 - var(--r)) * .25), calc(1 - (1 - var(--r)) * .25)); transition: transform .9s linear; }
.wk #wk-today, .wk #wk-cToday { list-style: none; padding: 0; margin: 8px 0; display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: 14px; }
.wk #wk-today li, .wk #wk-cToday li { display: flex; align-items: center; gap: 2px; background: var(--card); border-radius: 999px; padding: 2px 2px 2px 12px; color: var(--fg); }
.wk #wk-today button, .wk #wk-cToday button { border: 0; background: none; color: var(--muted); font-size: 18px; min-width: 44px; min-height: 44px; border-radius: 50%; cursor: pointer; }
.wk #wk-saveNote, .wk #wk-cWarn { color: var(--muted); font-size: 13px; }
.wk #wk-toast { position: fixed; left: 50%; bottom: 24px; z-index: 50; margin: 0; max-width: calc(100% - 32px); padding: 10px 16px; border-radius: 999px; background: rgba(30,30,28,.92); color: #fff; font-size: 14px; pointer-events: none; opacity: 0; translate: -50% 12px; transition: opacity .2s, translate .2s; }
.wk #wk-toast.on { opacity: 1; translate: -50% 0; }
@media (prefers-reduced-motion: reduce) { .wk #wk-toast { transition: none; } }
.wk #wk-stage { display: flex; justify-content: center; align-items: flex-end; gap: 8px; min-height: 140px; margin: 8px 0; }
.wk #wk-stage img { display: block; transform-origin: 50% 90%; }
.wk #wk-stage .p img { width: 120px; }
.wk #wk-stage .s img { width: 56px; }
.wk .hit img { animation: wk-hit .45s ease-out; }
.wk .hit-sm img { animation: wk-hitsm .45s ease-out; }
@keyframes wk-hit { 15% { transform: scale(calc(1.3 * var(--k, 1)), .65); filter: brightness(1.8); } 45% { transform: scale(.92, 1.1); filter: none; } 100% { transform: none; } }
.wk #wk-fx { margin-top: 24px; color: var(--muted); }
.wk #wk-fx label { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; min-height: 44px; color: var(--fg); }
.wk #wk-fx input[type=checkbox] { width: 22px; height: 22px; }
.wk.shake { animation: wk-shake .4s; }
@keyframes wk-shake { 20%, 60% { transform: translateX(-8px); } 40%, 80% { transform: translateX(8px); } }
.wk #wk-stage .p { position: relative; }
.wk .burst::after { content: ""; position: absolute; inset: -40%; border-radius: 50%; pointer-events: none; background: radial-gradient(circle, #fff6 0, var(--accent) 35%, transparent 70%); animation: wk-burst .9s ease-out .35s both; }
@keyframes wk-burst { from { transform: scale(.2); opacity: 1; } to { transform: scale(1.6); opacity: 0; } }
@keyframes wk-hitsm { 20% { transform: scale(1.1, .85); filter: brightness(1.4); } 100% { transform: none; } }
`;

// F19 화면 조각(기본). 테마가 slots에 같은 이름의 함수를 주면 그 조각으로 바꿔 낀다
// 약속: 버튼은 data-action(+data-*)으로 동작을 찾고, 값·출력 칸은 아래 wk- id를 그대로 쓴다. 화면 3개는 #wk-home·#wk-set·#wk-cardio
const SLOTS = {
  top: () => `<header class="village-topbar"><a class="village-brand" data-action="nav" data-nav="day" href="../dashboard/local.html#day"><i class="village-leaf" aria-hidden="true"></i>득근득근</a><label class="village-place">장소 <select id="wk-place"></select></label></header>
<p id="wk-notice"></p>`,
  home: () => `<section id="wk-home">
  <h1 class="village-title">어떤 운동을 할까요?</h1>
  <input id="wk-q" type="search" placeholder="운동 검색" autocomplete="off" aria-label="운동 검색">
  <ul id="wk-drop" class="drop"></ul>
  <div class="village-picker">
  <div id="wk-body"></div>
  <div class="village-muscles"><h2>부위를 골라요</h2><div class="village-muscle-list">${['가슴','등','어깨','코어','이두','삼두','대퇴사두','햄스트링','둔근','종아리'].map(m=>`<button type="button" data-action="muscle" data-muscle="${m}">${m}</button>`).join('')}</div></div>
  </div>
  <div class="btns"><button id="wk-bwBtn" type="button" data-action="bodyweight"><span>맨몸</span></button><button id="wk-cdBtn" type="button" data-action="cardioList"><span>유산소</span></button></div>
  <ul id="wk-cdrop" class="drop"></ul>
  <ul id="wk-mdrop" class="drop"></ul>
  <div id="wk-catalog"><h2 class="village-catalog-title">자주 하는 운동</h2><ul id="wk-catalogList" class="drop"></ul></div>
</section>`,
  set: () => `<section id="wk-set" class="hide">
  <button id="wk-back" type="button" data-action="home">← 뒤로</button>
  <h2 id="wk-setTitle"></h2>
  <p id="wk-setMuscles"></p>
  <div id="wk-stage"></div>
  <div class="village-entry"><p id="wk-setNo"></p>
  <div class="row"><label for="wk-kg">무게</label><button type="button" class="village-step" data-action="step" data-step="-1" data-for="kg" aria-label="무게 줄이기">−</button><select id="wk-kg" aria-label="무게"></select><span>kg</span><button type="button" class="village-step" data-action="step" data-step="1" data-for="kg" aria-label="무게 늘리기">+</button><span class="err" id="wk-kgErr"></span></div>
  <div class="row"><label for="wk-rep" id="wk-repLabel">횟수</label><button type="button" class="village-step" data-action="step" data-step="-1" data-for="rep" aria-label="횟수 또는 시간 줄이기">−</button><select id="wk-rep" aria-label="횟수"></select><span id="wk-repUnit">회</span><button type="button" class="village-step" data-action="step" data-step="1" data-for="rep" aria-label="횟수 또는 시간 늘리기">+</button><span class="err" id="wk-repErr"></span></div>
  <p id="wk-previous"></p>
  <p id="wk-rest"></p>
  <button id="wk-done" type="button" data-action="done">✓ 세트 완료</button></div>
  <section class="village-records"><h3>오늘 한 세트</h3>
  <ul id="wk-today" aria-label="오늘 기록"></ul>
  <p id="wk-saveNote"></p></section>
</section>`,
  cardio: () => `<section id="wk-cardio" class="hide">
  <button id="wk-cBack" type="button" data-action="home">← 뒤로</button>
  <h2 id="wk-cTitle"></h2>
  <div id="wk-runner" aria-hidden="true">🏃</div>
  <div class="row"><select id="wk-cMin" aria-label="시간"></select><span>분</span><span class="err" id="wk-cMinErr"></span></div>
  <div class="row"><select id="wk-cKmh" aria-label="속도 (선택)"></select><span>km/h</span></div>
  <div class="row"><select id="wk-cDeg" aria-label="경사 (선택)"></select><span>도</span></div>
  <button id="wk-cDone" type="button" data-action="cardioDone">완료</button>
  <ul id="wk-cToday" aria-label="오늘 유산소 기록"></ul>
  <p id="wk-cWarn"></p>
  <p id="wk-cNote"></p>
</section>`,
  settings: () => `<details id="wk-fx"><summary>휴식 · 연출 설정</summary>
  <label>진동 <input type="checkbox" id="wk-fxVib"></label>
  <label>소리 <input type="checkbox" id="wk-fxSnd"></label>
  <label>연출 강도 <select id="wk-fxInt"><option value="off">끔</option><option value="weak">약</option><option value="strong">강</option></select></label>
  <label>휴식 시간 <select id="wk-fxRest"></select></label>
</details>`,
  foot: () => `<nav class="village-foot" aria-label="화면"><a href="../dashboard/local.html#day" data-action="nav" data-nav="day">내 몸</a><a href="#input" class="current" data-action="nav" data-nav="input">운동</a><a href="../dashboard/local.html#week" data-action="nav" data-nav="week">기록</a></nav>`,
};
const SLOT_ORDER = ["top", "home", "set", "cardio", "settings", "foot"];
const composeWorkout = (t) => SLOT_ORDER.map((n) => (t.slots?.[n] ?? SLOTS[n])()).join("\n") + `<p id="wk-toast" role="status" aria-live="polite"></p>`;

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// F16 테마 드롭다운: select는 숨겨 값만 보관(기존 코드 그대로), 버튼+목록(listbox)으로 고른다. 대시보드도 LLW.pickMenu로 씀
function pickMenu(sel) {
  const wrap = sel.ownerDocument.createElement("span"); wrap.className = "ll-pickwrap";
  const mk = (tag) => sel.ownerDocument.createElement(tag);
  const btn = mk("button"); btn.type = "button"; btn.className = (sel.className + " ll-pickbtn").trim();
  btn.setAttribute("aria-haspopup", "listbox"); btn.setAttribute("aria-expanded", "false"); btn.setAttribute("aria-label", sel.getAttribute("aria-label") || "");
  const lab = mk("span"); btn.append(lab);
  const menu = mk("ul"); menu.setAttribute("role", "listbox"); menu.className = "ll-menu"; menu.hidden = true; menu.id = sel.id + "-menu";
  btn.setAttribute("aria-controls", menu.id);
  sel.before(wrap); wrap.append(sel, btn, menu); sel.classList.add("ll-native");
  const sync = () => { lab.textContent = sel.dataset.icon || sel.selectedOptions[0]?.textContent || "—"; btn.disabled = !sel.options.length; }; // data-icon: 글 대신 아이콘(🎨)
  // 코드가 value·selectedIndex를 바로 바꿔도 이름표가 따라가게
  for (const k of ["value", "selectedIndex"]) {
    const d = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(sel), k) ?? Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, k);
    Object.defineProperty(sel, k, { configurable: true, get() { return d.get.call(this); }, set(v) { d.set.call(this, v); sync(); } });
  }
  const items = () => [...menu.children];
  const close = (focus) => { if (menu.hidden) return; menu.hidden = true; btn.setAttribute("aria-expanded", "false"); if (focus) btn.focus(); };
  const choose = (v) => { try { navigator.vibrate?.(theme().haptic.pick); } catch {} if (sel.value !== v) { sel.value = v; sel.dispatchEvent(new Event("change", { bubbles: true })); } sync(); close(true); };
  const open = () => {
    menu.replaceChildren(...[...sel.options].filter((o) => !o.hidden).map((o) => {
      const li = mk("li"); li.setAttribute("role", "option"); li.tabIndex = -1; li.textContent = o.textContent; li.dataset.v = o.value; if (o.dataset?.swatch) { li.classList.add("ll-sw"); li.style.setProperty("--sw", o.dataset.swatch); }
      li.setAttribute("aria-selected", String(o.value === sel.value)); li.onclick = () => choose(o.value); return li;
    }));
    menu.hidden = false; btn.setAttribute("aria-expanded", "true");
    const cur = items().find((li) => li.getAttribute("aria-selected") === "true") || items()[0];
    cur?.focus(); cur?.scrollIntoView?.({ block: "nearest" });
  };
  btn.onclick = () => (menu.hidden ? open() : close(true));
  btn.addEventListener("keydown", (e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); open(); } });
  menu.addEventListener("keydown", (e) => {
    const list = items(), i = list.indexOf(sel.ownerDocument.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); list[Math.max(0, Math.min(list.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))]?.focus(); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (i >= 0) choose(list[i].dataset.v); }
    else if (e.key === "Escape" || e.key === "Tab") close(e.key === "Escape");
  });
  sel.ownerDocument.addEventListener("pointerdown", (e) => { if (!wrap.contains(e.target)) close(false); });
  sel.addEventListener("change", sync);
  new MutationObserver(sync).observe(sel, { childList: true, subtree: true, characterData: true }); // 목록을 다시 채우면 따라감
  sync();
}

// root: 그릴 요소. opts.ls → 설정 저장소(없으면 기본값)
// 돌려주는 api로 데이터·저장소를 넣는다: setData, setSets, setCardio, setStore, setCStore
function mountWorkout(root, opts = {}) {
  root.classList.add("wk");
  const $ = (id) => root.querySelector(`#wk-${id}`);
  const note = (id, m) => { $(id).textContent = m; toast($("toast"), m); }; // F16 안내를 토스트로도
  const vibrate = (p) => { try { navigator.vibrate?.(p); } catch {} };
  let state = { screen: "home" }, shown = "home", prevText = "";
  let catalog = buildCatalog("place,equipment,exercise\n", "exercise,muscle,share\n"), e = "date,time,kind,item,value,unit,source\n";

  // F04 화면 저장소. 연결 전·실패면 이 화면에서만 기억 (F13 안내)
  let sets = [], form = null;
  const memory = { add: async (r) => { sets.push(r); }, remove: async (r) => { sets = sets.filter((x) => x !== r); } };
  let store = memory, sWarn = NOT_CONNECTED;
  let cardio = [], cform = null, cPersist = false, cWarn = NOT_CONNECTED;
  const cmemory = { add: async (r) => { cardio.push(r); }, remove: async (r) => { cardio = cardio.filter((x) => x !== r); } };
  let cstore = cmemory;

  const place = () => $("place");
  const list = () => placeList(catalog, place().value);
  const items = (xs, sub = () => "", action = "pick") => xs.map((x) => `<li data-ex="${esc(x)}" data-action="${action}"><button type="button">${theme().exerciseArt(x)}<span>${esc(x)}</span>${sub(x)}</button></li>`).join("");
  const muscleButtons = () => root.querySelectorAll('[data-action="muscle"]');
  const highlight = (mu) => muscleButtons().forEach(b => { b.classList.toggle('on', b.dataset.muscle === mu); b.setAttribute('aria-pressed', String(b.dataset.muscle === mu)); });
  const renderCatalog = () => { $("catalogList").innerHTML = items(search(list(), "", workoutHistory(e, sets)).slice(0,6)); };

  const render = () => {
    $("notice").textContent = candidates(catalog, place().value).notice ?? "";
    $("home").classList.toggle("hide", state.screen !== "home");
    $("set").classList.toggle("hide", state.screen !== "set");
    $("cardio").classList.toggle("hide", state.screen !== "cardio");
    const dir = slideDir(SCREENS, shown, state.screen); shown = state.screen; // F17
    if (dir) { slideIn($(state.screen), dir); if (settings.vibrate) vibrate(theme().haptic.nav); }
    $("setTitle").textContent = state.exercise ?? "";
    if (state.screen === 'home') renderCatalog();
    renderSet();
  };
  const opts2 = (vals, v) => `<option value="">고르기</option>` + vals.map((x) => `<option${x === v ? " selected" : ""}>${x}</option>`).join("");
  const ck = () => (isHold(state.exercise) ? "sec" : "rep"); // 버티는 운동은 횟수 대신 초
  function renderSet() {
    if (state.screen !== "set" || !form) return;
    $("setNo").textContent = `${form.setNo}세트째`;
    const c = ck();
    $("kg").innerHTML = opts2(withValue(KG, form.kg), form.kg);
    $("rep").innerHTML = opts2(withValue(c === "sec" ? SEC : REP, form[c]), form[c]);
    $("rep").setAttribute("aria-label", c === "sec" ? "초" : "횟수");
    $("repUnit").textContent = c === "sec" ? "초" : "회";
    $("repLabel").textContent = c === "sec" ? "시간" : "횟수";
    $("setMuscles").textContent = (catalog.muscles[state.exercise] ?? []).map(x=>x.muscle).join(' · ');
    $("today").innerHTML = todaySets(sets, state.exercise).map((r) => `<li>${esc(r.label)}<button type="button" data-action="delSet" data-key="${esc(r.key)}" aria-label="${esc(r.label)} 지우기">×</button></li>`).join("");
  }
  // F05 연출 재생 (소리는 파일 없이 합성)
  const player = makePlayer();
  let ac = null;
  function sound(kind) {
    try {
      ac ??= new AudioContext();
      const t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain();
      o.type = "sine"; o.frequency.setValueAtTime(kind === "best" ? 220 : 160, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.18);
      g.gain.setValueAtTime(kind === "best" ? 0.9 : 0.7, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
      o.connect(g).connect(ac.destination); o.start(t); o.stop(t + 0.26);
    } catch {}
  }
  const replay = (el, cls) => { el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); };
  function renderStage() {
    const p = hitPlan(catalog, state.exercise ?? "", "normal", {});
    $("stage").innerHTML = theme().body(false);
    for (const region of $("stage").querySelectorAll('[data-m]')) {
      region.classList.toggle('active', p.primary.includes(region.dataset.m) || p.secondary.includes(region.dataset.m));
      region.classList.toggle('p', p.primary.includes(region.dataset.m));
      region.classList.toggle('s', p.secondary.includes(region.dataset.m));
      region.classList.toggle('secondary', p.secondary.includes(region.dataset.m));
    }
  }
  function play(plan) {
    if (plan.vibrate) vibrate(plan.vibrate);
    if (plan.sound) sound(plan.tier);
    for (const el of $("stage").querySelectorAll('[data-m].active')) {
      el.style.setProperty("--k", plan.primaryScale);
      replay(el, el.classList.contains("p") ? "hit" : "hit-sm");
      if (plan.burst && el.classList.contains("p")) replay(el, "burst");
    }
    if (plan.shake) setTimeout(() => replay(root, "shake"), plan.pauseMs);
  }
  // F07 휴식 타이머 · F08 설정 (이 폰 브라우저에 저장, 막혀 있으면 기본값)
  const ls = opts.ls ?? null;
  let settings = loadSettings(ls);
  const timer = makeRestTimer(settings.restSec);
  const fillFx = () => {
    $("fxRest").innerHTML = Array.from({ length: 19 }, (_, i) => 30 + i * 15).map((x) => `<option value="${x}">${Math.floor(x / 60)}분 ${x % 60 ? (x % 60) + "초" : ""}</option>`).join("");
    $("fxVib").checked = settings.vibrate; $("fxSnd").checked = settings.sound; $("fxInt").value = settings.intensity; $("fxRest").value = settings.restSec;
  };
  const saveFx = () => {
    settings = { vibrate: $("fxVib").checked, sound: $("fxSnd").checked, intensity: $("fxInt").value, restSec: Number($("fxRest").value) };
    saveSettings(ls, settings); timer.setRest(settings.restSec);
  };
  function ding() {
    try {
      ac ??= new AudioContext();
      const t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain();
      o.frequency.value = 880; g.gain.setValueAtTime(0.4, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.5);
      o.connect(g).connect(ac.destination); o.start(t); o.stop(t + 0.5);
    } catch {}
  }
  function tickRest() {
    if (!root.isConnected) return;
    const r = timer.tick(Date.now());
    const el = $("rest");
    el.textContent = r.running ? `${Math.floor(r.remainingSec / 60)}:${String(r.remainingSec % 60).padStart(2, "0")}` : r.done ? "다음 세트!" : "";
    el.classList.toggle("ready", r.done);
    $("stage").style.setProperty("--r", restRecovery(r, settings)); // 테마 그림이 var(--r)로 회복 모양
    if (r.alert) { if (settings.vibrate) vibrate(theme().haptic.rest); if (settings.sound) ding(); }
  }
  const iv = setInterval(tickRest, 1000);
  const onVis = () => { if (!document.hidden) tickRest(); };
  document.addEventListener("visibilitychange", onVis);
  const num = (id) => ($(id).value === "" ? null : Number($(id).value));
  const env = () => ({ canVibrate: "vibrate" in navigator, haptic: theme().haptic }); // F19 진동 세기는 테마
  // F19 버튼 동작은 data-action 이름표로 찾는다 (테마가 버튼 위치·개수를 바꿔도 같은 기능)
  const actions = {};
  actions.step = (button) => {
    const control = $(button.dataset.for);
    const next = Math.max(1, Math.min(control.options.length - 1, control.selectedIndex + Number(button.dataset.step)));
    control.selectedIndex = next; control.dispatchEvent(new Event('change', {bubbles:true}));
  };
  actions.done = async () => {
    const ctx = { catalog, sets, store, player, play, settings, env: env(),
      tierOf: (ex, f) => tierOf(e, sets, ex, f) };
    const r = await handleDone(ctx, state.exercise, form);
    if (r.busy) return;
    note("saveNote", r.message ?? sWarn);
    if (r.ok) { timer.start(Date.now()); setTimeout(tickRest, r.plan.durationMs); }
    $("kgErr").textContent = r.errors?.kg ?? "";
    $("repErr").textContent = r.errors?.[ck()] ?? "";
    if (!r.ok) return;
    if (store !== memory) sets = addSaved(sets, r.rec); // 바로 보이게. 새 목록이 먼저 왔으면 이미 있음 (F13)
    form = r.form;
    renderSet();
  };
  // F10 세트 삭제: × → 확인 없이 그 세트만 지우고 남은 세트로 번호·기본값 다시 계산
  actions.delSet = async (b) => {
    const key = b.dataset.key;
    if (!key) return;
    try {
      sets = await deleteSet(store, sets, key);
      form = setForm(e, sets, state.exercise);
      $("kgErr").textContent = $("repErr").textContent = "";
    } catch { note("saveNote", "삭제 실패 — 다시 눌러 주세요"); }
    renderSet();
  };
  // F12 목록은 하나만: open 말고 다 비움. 부위 목록(mdrop)을 안 남기면 부위 표시·팝업도 끔
  const closeLists = (open = null) => {
    for (const id of listsToClear(open)) $(id).innerHTML = "";
    $("catalog").classList.toggle('hide', open !== null);
    if (open !== 'mdrop') highlight(null);
    if (open !== "mdrop") { for (const x of $("body").querySelectorAll("[data-m]")) x.classList.remove("on"); }
  };
  const go = (ex) => {
    state = pick(state, ex); form = setForm(e, sets, ex);
    closeLists(); $("q").value = ""; $("kgErr").textContent = $("repErr").textContent = "";
    $("saveNote").textContent = sWarn;
    prevText = form.kg != null && (form.rep != null || form.sec != null) ? `직전 ${form.kg} kg × ${form.sec ?? form.rep}${form.sec != null ? '초' : '회'}` : '무게와 횟수를 골라 주세요';
    $("previous").textContent = prevText;
    renderStage(); render();
  };
  // F02 검색
  const openDrop = () => {
    closeLists("drop");
    const r = search(list(), $("q").value, workoutHistory(e, sets));
    $("drop").innerHTML = r.length ? items(r) : `<li class="none">${NO_MATCH}</li>`;
  };
  // F03 부위 탭: 몸 앞·뒤 그림(테마), 누른 부위 켜짐·찌그러짐·진동
  const tapRegion = (g) => {
    closeLists("mdrop");
    const mu = g.dataset.m;
    highlight(mu);
    vibrate(theme().haptic.touch);
    for (const x of $("body").querySelectorAll("[data-m]")) x.classList.toggle("on", x.dataset.m === mu);
    g.classList.remove("squish"); void g.offsetWidth; g.classList.add("squish");
    const r = exercisesFor(catalog, mu, list(), workoutHistory(e, sets));
    const share = (x) => catalog.muscles[x].find((y) => y.muscle === mu).share;
    $("mdrop").innerHTML = r.length ? items(r, (x) => share(x) < 1 ? "<small>보조</small>" : "") : `<li class="none">${NO_MATCH}</li>`;
  };
  actions.muscle = (button) => {
    const region = [...$("body").querySelectorAll('[data-m]')].find(r=>r.dataset.m === button.dataset.muscle);
    if (region) tapRegion(region);
  };
  actions.region = (g) => { if ($("body").contains(g)) tapRegion(g); };
  // F11 맨몸 버튼: 찌그러짐·진동 → 이 장소 맨몸 운동 (자주 한 순)
  actions.bodyweight = (b) => {
    closeLists("mdrop");
    tapButton();
    vibrate(theme().haptic.touch);
    b.classList.remove("squish"); void b.offsetWidth; b.classList.add("squish");
    for (const x of $("body").querySelectorAll("[data-m]")) x.classList.remove("on");
    $("mdrop").innerHTML = items(bodyweightFor(catalog, place().value, workoutHistory(e, sets)));
  };
  // F12 유산소 버튼 → 종목 목록 → 시간·속도·경사 → 완료(완주 연출)
  actions.cardioList = (b) => {
    closeLists("cdrop");
    tapButton();
    vibrate(theme().haptic.touch);
    b.classList.remove("squish"); void b.offsetWidth; b.classList.add("squish");
    $("cdrop").innerHTML = items(cardioFor(catalog, place().value, cardioHistory(e, cardio)), undefined, "cardioPick");
  };
  const renderCardio = () => {
    $("cTitle").textContent = state.exercise ?? "";
    $("cMin").innerHTML = opts2(withValue(MIN, cform.min), cform.min);
    $("cKmh").innerHTML = opts2(withValue(KMH, cform.kmh), cform.kmh).replace("고르기", "없음");
    $("cDeg").innerHTML = opts2(withValue(DEG, cform.deg), cform.deg).replace("고르기", "없음");
    renderCToday();
  };
  // F12 오늘 유산소 칸, × → 확인 없이 그 칸만 지움
  const renderCToday = () => {
    if (state.screen !== "cardio") return;
    $("cToday").innerHTML = todayCardio(cardio, state.exercise).map((r) => `<li>${esc(r.label)}<button type="button" data-action="delCardio" data-key="${esc(r.key)}" aria-label="${esc(r.label)} 지우기">×</button></li>`).join("");
  };
  actions.delCardio = async (b) => {
    const key = b.dataset.key;
    if (!key) return;
    try { cardio = await deleteCardio(cstore, cardio, key); } catch { note("cNote", "삭제 실패 — 다시 눌러 주세요"); }
    renderCToday();
  };
  actions.cardioPick = (li) => {
    const ex = li.dataset.ex;
    if (!ex) return;
    state = { screen: "cardio", exercise: ex }; cform = cardioForm(e, cardio, ex);
    closeLists(); $("cMinErr").textContent = $("cNote").textContent = ""; $("cWarn").textContent = cWarn;
    renderCardio(); render();
  };
  actions.cardioDone = async () => {
    const ctx = { store: cstore, player, settings, env: env(),
      play: (p) => { if (p.vibrate) vibrate(p.vibrate); if (p.sound) sound("best"); replay($("runner"), "go"); } };
    try {
      const r = await handleCardio(ctx, state.exercise, cform);
      if (r.busy) return;
      $("cMinErr").textContent = r.errors?.min ?? "";
      if (r.ok) { note("cNote", cardioDoneText(r.rec, cPersist)); if (cPersist) cardio = addSaved(cardio, r.rec); renderCToday(); }
      else if (r.message) note("cNote", r.message);
    } catch { note("cNote", SAVE_FAIL); }
  };
  actions.home = () => { closeLists(); state = { screen: "home" }; render(); };
  actions.pick = (li) => go(li.dataset.ex);
  actions.nav = (a, event) => {
    if (opts.onNavigate) { event.preventDefault(); opts.onNavigate(a.dataset.nav); }
    else if (a.dataset.nav === 'input') { event.preventDefault(); closeLists(); state = {screen:'home'}; render(); }
  };
  root.addEventListener("click", (ev) => { const a = ev.target.closest("[data-action]"); if (a && root.contains(a)) actions[a.dataset.action]?.(a, ev); });
  root.addEventListener("keydown", (ev) => { const g = ev.target.closest("#wk-body [data-m]"); if (g && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); tapRegion(g); } });
  // 값 칸은 id로 (테마 조각도 같은 id를 씀)
  const changes = {
    kg: () => { form.kg = num("kg"); $("kgErr").textContent = ""; },
    rep: () => { form[ck()] = num("rep"); $("repErr").textContent = ""; },
    cMin: () => { cform.min = num("cMin"); $("cMinErr").textContent = ""; },
    cKmh: () => { cform.kmh = num("cKmh"); $("cMinErr").textContent = ""; },
    cDeg: () => { cform.deg = num("cDeg"); $("cMinErr").textContent = ""; },
    place: () => { closeLists(); render(); },
  };
  root.addEventListener("change", (ev) => { const id = ev.target.id?.replace(/^wk-/, ""); if (changes[id]) changes[id](); else if (ev.target.closest("#wk-fx")) saveFx(); });
  for (const type of ["input", "focusin"]) root.addEventListener(type, (ev) => { if (ev.target.id === "wk-q") openDrop(); });

  // F19 테마 조각으로 화면을 (다시) 그린다. 상태·데이터는 그대로, 바뀐 테마면 새로고침 없이 바로
  let painted = null;
  function paint() {
    const t = theme(), keep = place()?.value;
    if (painted) root.classList.remove(...painted.classes.workout.split(" "));
    root.classList.add(...t.classes.workout.split(" ")); painted = t;
    root.innerHTML = `<style>${CSS}\n${t.css.base}\n${t.css.workout}</style>${composeWorkout(t)}`;
    root.querySelectorAll("select").forEach(pickMenu); // F16 운동 탭 선택칸도 테마 목록
    $("body").insertAdjacentHTML("afterbegin", t.body(true));
    fillFx();
    if (catalog.places.length) { place().innerHTML = catalog.places.map((p) => `<option>${esc(p)}</option>`).join(""); if (keep && catalog.places.includes(keep)) place().value = keep; }
    $("saveNote").textContent = sWarn; $("cWarn").textContent = cWarn; $("previous").textContent = prevText;
    if (state.screen === "set") renderStage();
    if (state.screen === "cardio") renderCardio();
    render();
  }
  const offTheme = onTheme(paint);

  const api = {
    // gyms·muscles·entries CSV 글. 장소 고른 것은 유지
    setData({ gymsText, musclesText, entriesText }) {
      if (gymsText != null && musclesText != null) {
        catalog = buildCatalog(gymsText, musclesText);
        const cur = place().value;
        place().innerHTML = catalog.places.map((p) => `<option>${esc(p)}</option>`).join("");
        if (catalog.places.includes(cur)) place().value = cur;
      }
      if (entriesText != null) e = entriesText;
      render();
    },
    setSets(arr) { sets = arr; renderSet(); },
    setCardio(arr) { cardio = [...arr].sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`)); renderCToday(); },
    // 저장소가 연결되면 넣는다 (warn: 화면 안내, 빈 글이면 안내 없음)
    setStore(s, warn = "") { store = s; sWarn = warn; $("saveNote").textContent = warn; },
    setCStore(s) { cstore = s; api.cardioRead(true); },
    // 유산소 기록 읽기 성공/실패 (실패면 안내 + 완료 문구 '이 화면에만 저장')
    cardioRead(ok) { ({ persisted: cPersist, warn: cWarn } = cardioState(cstore !== cmemory, ok)); $("cWarn").textContent = cWarn; },
    get sets() { return sets; },
    get memory() { return store === memory; },
    destroy() { clearInterval(iv); document.removeEventListener("visibilitychange", onVis); offTheme(); },
  };
  paint();
  return api;
}

// 터치 팝콘(우사기): 화면 어디를 눌러도 누른 자리에서 테마 pop 그림 3~6장(랜덤)이 솟았다 떨어지며 사라짐 (mockup/touch-popcorn-v2 시안 k=2)
// 누를 때마다 그 자리에 작은 캔버스(pointer-events:none)를 붙임 → 스크롤·긴 페이지 어디서나 같은 위치, 버튼 클릭은 안 막음. 돌려주는 함수로 정리
const POP = { ms: 1000, min: 3, max: 6, bursts: 12, ring: 44, colors: ["#ef8faf", "#f3b854", "#7ebda3"], box: [90, 130, 70] }; // box = 캔버스 좌우 반폭·위·아래(px)
function popAt(i, p, n = 6) { // n장 중 i번째 그림의 진행률 p(0~1) 위치 [x, y, 크기, 투명도, 회전]
  const e = 1 - (1 - p) ** 3;
  return [(i - (n - 1) / 2) * 28 * e, -(85 + 13 * (i % 3)) * Math.sin(p * Math.PI * 0.87) + 45 * p * p, 35 * Math.min(1, p / 0.12) * (1 - 0.3 * p), Math.min(1, (1 - p) / 0.28), Math.sin(i * 2 + p * 5) * 0.5];
}
const popCount = (r = Math.random()) => POP.min + Math.floor(r * (POP.max - POP.min + 1));
function touchPop(host) { // host = 대시보드 최상위(.ll). 캔버스도 그 안에
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches, ms = reduced ? 220 : POP.ms, [hw, up, down] = POP.box;
  if (getComputedStyle(host).position === "static") host.style.position = "relative";
  const layer = document.createElement("div"); // host 크기 투명 층: 가장자리에서 눌러도 가로 스크롤 안 생기게 잘라냄
  layer.setAttribute("aria-hidden", "true");
  layer.style.cssText = "position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:2147483000";
  host.append(layer);
  const cache = new Map(), img = (src) => { if (!cache.has(src)) { const im = new Image(); im.src = src; cache.set(src, im); } return cache.get(src); };
  let bursts = [], raf = 0;
  const frame = (now) => {
    for (const b of bursts) if (now - b.t >= ms) b.c.remove();
    bursts = bursts.filter((b) => now - b.t < ms);
    for (const b of bursts) {
      const p = reduced ? 0.25 : (now - b.t) / ms, e = 1 - (1 - p) ** 3, ctx = b.c.getContext("2d");
      ctx.setTransform(b.d, 0, 0, b.d, 0, 0); ctx.clearRect(0, 0, hw * 2, up + down); ctx.translate(hw, up);
      ctx.globalAlpha = 0.86 * (1 - p); ctx.lineWidth = 2;
      ctx.strokeStyle = POP.colors[2]; ctx.beginPath(); ctx.arc(0, 0, 4 + POP.ring * e, 0, Math.PI * 2); ctx.stroke(); // 물결 링
      for (let j = 0; j < 6; j++) { // 반짝이 십자
        const a = j * Math.PI / 3 + 0.2, r = 12 + (POP.ring + 6) * e, x = Math.cos(a) * r, y = Math.sin(a) * r, s = Math.max(1, 4 * (1 - p));
        ctx.globalAlpha = 0.9 * (1 - p); ctx.strokeStyle = POP.colors[j % 3];
        ctx.beginPath(); ctx.moveTo(x - s, y); ctx.lineTo(x + s, y); ctx.moveTo(x, y - s); ctx.lineTo(x, y + s); ctx.stroke();
      }
      b.imgs.forEach((im, i) => {
        if (!im.complete || !im.naturalWidth) return;
        const [x, y, s, alpha, rot] = popAt(i, p, b.imgs.length), wd = s * im.naturalWidth / im.naturalHeight;
        ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.globalAlpha = alpha; ctx.drawImage(im, -wd / 2, -s / 2, wd, s); ctx.restore();
      });
    }
    raf = bursts.length ? requestAnimationFrame(frame) : 0;
  };
  const press = (ev) => {
    const art = theme().pop;
    if (!art?.length) return; // 팝콘 그림 없는 테마(마을)는 효과 없음
    const r = host.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2), c = document.createElement("canvas");
    c.width = hw * 2 * d; c.height = (up + down) * d;
    c.style.cssText = `position:absolute;left:${ev.clientX - r.left - hw}px;top:${ev.clientY - r.top - up}px;width:${hw * 2}px;height:${up + down}px;pointer-events:none`;
    layer.append(c);
    const pool = [...art].sort(() => Math.random() - 0.5); // 겹치지 않게 섞어서 앞에서부터
    bursts.push({ c, d, t: performance.now(), imgs: pool.slice(0, popCount()).map(img) });
    if (bursts.length > POP.bursts) bursts.shift().c.remove(); // 연타 제한
    if (!raf) raf = requestAnimationFrame(frame);
  };
  host.addEventListener("pointerdown", press, { passive: true });
  return () => { host.removeEventListener("pointerdown", press); cancelAnimationFrame(raf); layer.remove(); bursts = []; };
}

const CHARS = {"가슴": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EA%B0%80%EC%8A%B4%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23ff8a7a%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "대퇴사두": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EB%8C%80%ED%87%B4%EC%82%AC%EB%91%90%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23ff9fc8%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "둔근": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EB%91%94%EA%B7%BC%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23ffa86b%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "등": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EB%93%B1%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%237ab8ff%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "삼두": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EC%82%BC%EB%91%90%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%238fd6a8%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "어깨": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EC%96%B4%EA%B9%A8%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23ffc46b%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "이두": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EC%9D%B4%EB%91%90%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23b48cff%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "종아리": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EC%A2%85%EC%95%84%EB%A6%AC%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23a8c86b%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "코어": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%EC%BD%94%EC%96%B4%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%23ffd84d%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E", "햄스트링": "data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%20100%20100%22%20role%3D%22img%22%20aria-label%3D%22%ED%96%84%EC%8A%A4%ED%8A%B8%EB%A7%81%22%3E%0A%3C%21--%20%EC%9E%84%EC%8B%9C%20%EB%A7%90%EB%9E%91%20%EB%A7%88%EC%8A%A4%EC%BD%94%ED%8A%B8.%20%EC%B5%9C%EC%A2%85%20%EA%B7%B8%EB%A6%BC%EC%9C%BC%EB%A1%9C%20%EB%B0%94%EA%BF%80%20%EB%95%90%20%EC%9D%B4%20%ED%8C%8C%EC%9D%BC%EB%A7%8C%20%EA%B5%90%EC%B2%B4%20--%3E%0A%3Cpath%20d%3D%22M50%2010C76%2010%2090%2030%2090%2055S74%2092%2050%2092%2010%2080%2010%2055%2024%2010%2050%2010Z%22%20fill%3D%22%236fd0d0%22%2F%3E%0A%3Cellipse%20cx%3D%2238%22%20cy%3D%2230%22%20rx%3D%2210%22%20ry%3D%226%22%20fill%3D%22%23fff%22%20opacity%3D%22.35%22%2F%3E%0A%3Ccircle%20cx%3D%2238%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%3Ccircle%20cx%3D%2262%22%20cy%3D%2252%22%20r%3D%225%22%20fill%3D%22%232b2118%22%2F%3E%0A%3Ccircle%20cx%3D%2230%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%3Ccircle%20cx%3D%2270%22%20cy%3D%2264%22%20r%3D%225%22%20fill%3D%22%23ff5e7e%22%20opacity%3D%22.35%22%2F%3E%0A%3Cpath%20d%3D%22M44%2064Q50%2070%2056%2064%22%20stroke%3D%22%232b2118%22%20stroke-width%3D%223%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%2F%3E%0A%3C%2Fsvg%3E"};
window.LLW = { parseCSV, buildCatalog, candidates, NO_MATCH, workoutHistory, search, pick, MUSCLES, exercisesFor, tapMuscle, bodySvg, KG, REP, SEC, withValue, isHold, kstNow, setForm, BODYWEIGHT, isBodyweight, bodyweightFor, placeList, tapButton, HAPTIC, TABS, SCREENS, slideDir, slideIn, toast, validateSet, completeSet, saveSet, todaySets, deleteSet, hitPlan, makePlayer, handleDone, SAVE_FAIL, NOT_CONNECTED, addSaved, CARDIO_READ_FAIL, cardioState, cardioDoneText, tierOf, REST_DEFAULT_SEC, makeRestTimer, DEFAULT_SETTINGS, loadSettings, saveSettings, applySettings, restRecovery, CARDIO, MIN, KMH, DEG, cardioHistory, cardioFor, cardioForm, validateCardio, saveCardio, todayCardio, deleteCardio, LISTS, listsToClear, handleCardio, appRows, toCSV, VILLAGE_ASSETS, VILLAGE_REGIONS, villageBody, villageExerciseArt, VILLAGE_CSS, VILLAGE_WORKOUT_CSS, VILLAGE_DASH_CSS, VILLAGE, USAGI_ASSETS, USAGI_POP, usagiExerciseArt, USAGI_REGIONS, usagiBody, USAGI, THEMES, DEFAULT_THEME, THEME_FIELDS, HAPTIC_FIELDS, themeProblems, pickTheme, themeList, theme, setTheme, onTheme, SLOTS, SLOT_ORDER, composeWorkout, pickMenu, mountWorkout, POP, popAt, popCount, touchPop, CHARS };
})();
