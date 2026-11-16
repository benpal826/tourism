"""이메일 알림 (F9): 알림 조건에 해당하는 항목이 있을 때만 SMTP 로 리포트를 보낸다.

설계 원칙
- 알림 조건은 config.NOTIFY_RULES 에서만 조정한다. 기본값: CBAM·ETS 신규 기사, LLM 중요도 high 신규 기사, 급증 배율 3배 이상 키워드.
- '신규' 는 마지막 발송(notify_log) 이후에 수집된 것이다. 발송 기록이 없으면 최근 first_run_hours 시간 안에 수집된 것.
  발송에 실패하거나 --dry-run 이면 기록을 남기지 않으므로 다음 실행에서 같은 항목이 다시 대상이 된다.
- 무관 기사(relevant=0)는 알리지 않는다. 단체·업계 주장(3등급)은 exclude_tier3 이면 조건에 쓰지 않는다 (집계와 같은 기준).
- SMTP 서버·계정·비밀번호·수신자는 환경변수로만 읽고, 로그·DB 에는 수신자 수만 남긴다.
- 조건 판정(select_alerts)·메일 구성(build_message)·발송(send)을 나눠, 발송 없이 모든 로직을 테스트한다.
"""
import html
import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import config
from . import db

log = logging.getLogger(__name__)

ENV_REQUIRED = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_TO")
IMPACT_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}


class NotifyConfigError(Exception):
    """SMTP 설정 환경변수가 빠졌다. 메시지에는 변수 이름만 담고 값은 담지 않는다."""


@dataclass
class SmtpSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipients: list[str]

    def __repr__(self) -> str:  # 로그·예외에 비밀번호가 찍히지 않게
        return f"SmtpSettings(host={self.host!r}, port={self.port}, recipients={len(self.recipients)})"


def settings_from_env(env=None) -> SmtpSettings:
    env = os.environ if env is None else env
    missing = [k for k in ENV_REQUIRED if not env.get(k, "").strip()]
    if missing:
        raise NotifyConfigError("이메일 알림에 필요한 환경변수가 없습니다: " + ", ".join(missing))
    recipients = [a.strip() for a in env["NOTIFY_TO"].split(",") if a.strip()]
    if not recipients:
        raise NotifyConfigError("NOTIFY_TO 에 수신자 주소가 없습니다")
    try:
        port = int(env.get("SMTP_PORT", "").strip() or 587)
    except ValueError:
        raise NotifyConfigError("SMTP_PORT 가 숫자가 아닙니다") from None
    user = env["SMTP_USER"].strip()
    return SmtpSettings(host=env["SMTP_HOST"].strip(), port=port, user=user, password=env["SMTP_PASSWORD"],
                        sender=env.get("NOTIFY_FROM", "").strip() or user, recipients=recipients)


# ----------------------------------------------------------------------------- 조건 판정
def _split(tags: str | None) -> list[str]:
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def _kst(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(config.KST).strftime("%Y-%m-%d %H:%M")


def last_sent(conn) -> str | None:
    row = conn.execute("SELECT MAX(sent_at) FROM notify_log").fetchone()
    return row[0] if row else None


def _recent_terms(conn, now: datetime, days: float) -> set[str]:
    since = (now - timedelta(days=days)).isoformat()
    out: set[str] = set()
    for r in conn.execute("SELECT terms FROM notify_log WHERE sent_at >= ?", (since,)):
        out.update(json.loads(r[0] or "[]"))
    return out


def select_alerts(conn, report_data: dict, now: datetime | None = None, rules: dict | None = None) -> dict:
    """알림 조건별 대상 목록. 한 기사가 여러 조건에 해당하면 각 목록에 모두 들어간다 (조건별로 정확히 보이도록)."""
    rules = {**config.NOTIFY_RULES, **(rules or {})}
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    unknown = [t for t in rules["new_topics"] if t not in config.TOPICS]
    if unknown:
        log.warning("NOTIFY_RULES.new_topics 에 config.TOPICS 에 없는 주제가 있습니다 (알림이 걸리지 않음): %s", unknown)

    prev = last_sent(conn)
    since = prev or (now - timedelta(hours=rules["first_run_hours"])).isoformat()
    min_pub = (now - timedelta(days=rules["max_age_days"])).isoformat()
    rows = conn.execute(
        f"SELECT id,title,url,source,source_type,agency,published,collected,{db.EFFECTIVE_TOPICS} AS topics,"
        "source_tier,llm_impact,llm_summary FROM articles "
        "WHERE collected > ? AND published >= ? AND relevant IS NOT 0 ORDER BY published DESC",
        (since, min_pub),
    ).fetchall()
    if rules["exclude_tier3"]:
        rows = [r for r in rows if r["source_tier"] != 3]

    want_topics = set(rules["new_topics"])
    want_impact = set(rules["impact_levels"])
    new_topic, high_impact = [], []
    for r in rows:
        topics = _split(r["topics"])
        item = {
            "id": r["id"], "title": r["title"], "url": r["url"] or "",
            "kind": "official" if r["source_type"] == "official" else "news",
            "source": (r["agency"] or r["source"] or "") if r["source_type"] == "official" else (r["source"] or ""),
            "published": _kst(r["published"]), "topics": topics,
            "ai_impact": r["llm_impact"] or "", "summary": r["llm_summary"] or "",
        }
        matched = [t for t in topics if t in want_topics]
        if matched:
            new_topic.append({**item, "matched": matched})
        if r["llm_impact"] in want_impact:
            high_impact.append(item)

    already = _recent_terms(conn, now, rules["rising_repeat_days"])
    rising = [t for t in report_data.get("rising_terms", [])
              if t["ratio"] >= rules["rising_min_ratio"] and t["term"] not in already]
    skipped_terms = [t["term"] for t in report_data.get("rising_terms", [])
                     if t["ratio"] >= rules["rising_min_ratio"] and t["term"] in already]

    ids = list(dict.fromkeys([a["id"] for a in new_topic] + [a["id"] for a in high_impact]))
    return {
        "since": since, "first_run": prev is None,
        "new_topic": new_topic, "high_impact": high_impact, "rising": rising,
        "skipped_terms": skipped_terms, "article_ids": ids, "rules": rules,
    }


def has_alerts(alerts: dict) -> bool:
    return bool(alerts["new_topic"] or alerts["high_impact"] or alerts["rising"])


# ----------------------------------------------------------------------------- 메일 구성
def subject_for(alerts: dict, report_data: dict) -> str:
    parts = []
    if alerts["new_topic"]:
        parts.append(f"신규 {len(alerts['new_topic'])}건")
    if alerts["high_impact"]:
        parts.append(f"중요도 높음 {len(alerts['high_impact'])}건")
    if alerts["rising"]:
        parts.append(f"급증 키워드 {len(alerts['rising'])}개")
    day = report_data.get("generated_at", "")[:10]
    return f"{config.NOTIFY_SUBJECT_PREFIX} {day} " + ", ".join(parts)


def _sections(alerts: dict) -> list[tuple[str, list[dict], str]]:
    rules = alerts["rules"]
    return [
        (f"주제 신규 ({', '.join(rules['new_topics'])})", alerts["new_topic"], "article"),
        (f"AI 중요도 {'/'.join(IMPACT_LABELS.get(x, x) for x in rules['impact_levels'])}", alerts["high_impact"], "article"),
        (f"급증 키워드 (평소 대비 {rules['rising_min_ratio']:g}배 이상)", alerts["rising"], "term"),
    ]


def _article_line(a: dict) -> str:
    kind = "공식" if a["kind"] == "official" else "뉴스"
    extra = f" — {a['summary']}" if a["summary"] else ""
    tags = f" [{', '.join(a.get('matched') or a['topics'])}]" if (a.get("matched") or a["topics"]) else ""
    return f"[{kind}] {a['title']} ({a['source']}, {a['published']}){tags}{extra}\n  {a['url']}"


def _term_line(t: dict) -> str:
    return f"{t['term']} — 최근 {t['recent']}건, 평소 기대 {t['baseline']}건, {t['ratio']:g}배"


def text_body(alerts: dict, report_data: dict, report_name: str | None, attach: bool) -> str:
    max_items = alerts["rules"]["max_items"]
    since = "첫 발송: 최근 수집분" if alerts["first_run"] else f"마지막 발송({_kst(alerts['since'])} KST) 이후 수집분"
    lines = [f"탄소정책 모니터링 알림 — {report_data.get('generated_at', '')[:16].replace('T', ' ')} KST", f"기준: {since}", ""]
    if report_data.get("briefing"):
        lines += ["오늘의 브리핑", report_data["briefing"], ""]
    for title, items, kind in _sections(alerts):
        if not items:
            continue
        unit = "개" if kind == "term" else "건"
        lines.append(f"■ {title}: {len(items)}{unit}")
        for x in items[:max_items]:
            lines.append("- " + (_article_line(x) if kind == "article" else _term_line(x)))
        if len(items) > max_items:
            lines.append(f"  … 외 {len(items) - max_items}건은 리포트에서 확인하세요")
        lines.append("")
    if report_name:
        lines.append(f"전체 리포트: 첨부 파일 {report_name}" if attach else "전체 리포트는 아래에 이어집니다.")
    return "\n".join(lines)


def html_summary(alerts: dict, report_data: dict, report_name: str | None, attach: bool) -> str:
    esc = html.escape
    max_items = alerts["rules"]["max_items"]
    since = "첫 발송: 최근 수집분" if alerts["first_run"] else f"마지막 발송({_kst(alerts['since'])} KST) 이후 수집분"
    out = [f"<h2>탄소정책 모니터링 알림</h2><p>{esc(report_data.get('generated_at', '')[:16].replace('T', ' '))} KST · {esc(since)}</p>"]
    if report_data.get("briefing"):
        out.append(f"<h3>오늘의 브리핑</h3><p>{esc(report_data['briefing'])}</p>")
    for title, items, kind in _sections(alerts):
        if not items:
            continue
        out.append(f"<h3>{esc(title)}: {len(items)}{'개' if kind == 'term' else '건'}</h3><ul>")
        for x in items[:max_items]:
            if kind == "term":
                out.append(f"<li>{esc(_term_line(x))}</li>")
                continue
            kind_label = "공식" if x["kind"] == "official" else "뉴스"
            tags = x.get("matched") or x["topics"]
            out.append(
                f"<li>[{kind_label}] <a href=\"{esc(x['url'], quote=True)}\">{esc(x['title'])}</a> "
                f"<small>({esc(x['source'])}, {esc(x['published'])}){' · ' + esc(', '.join(tags)) if tags else ''}</small>"
                + (f"<br><small>{esc(x['summary'])}</small>" if x["summary"] else "") + "</li>")
        if len(items) > max_items:
            out.append(f"<li>… 외 {len(items) - max_items}건은 리포트에서 확인하세요</li>")
        out.append("</ul>")
    if report_name and attach:
        out.append(f"<p>전체 리포트: 첨부 파일 {esc(report_name)}</p>")
    return "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>" + "".join(out) + "</body></html>"


def build_message(alerts: dict, report_data: dict, report_path: Path | None, sender: str, recipients: list[str],
                  attach: bool | None = None) -> EmailMessage:
    attach = config.NOTIFY_ATTACH if attach is None else attach
    report_name = report_path.name if report_path else None
    msg = EmailMessage()
    msg["Subject"] = subject_for(alerts, report_data)
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body(alerts, report_data, report_name, attach))
    if attach or not report_path:
        msg.add_alternative(html_summary(alerts, report_data, report_name, attach), subtype="html")
        if report_path:
            # 문자열로 넣어야 charset=utf-8 이 붙는다 (bytes 로 넣으면 charset 이 없어 메일 앱에서 한글이 깨질 수 있다)
            msg.add_attachment(report_path.read_text(encoding="utf-8"), subtype="html", charset="utf-8",
                               disposition="attachment", filename=report_name)
    else:
        # 본문 모드: 리포트 HTML 자체를 본문으로 보낸다 (텍스트 파트에는 알림 요약)
        msg.add_alternative(report_path.read_text(encoding="utf-8"), subtype="html")
    return msg


# ----------------------------------------------------------------------------- 발송
def send(msg: EmailMessage, settings: SmtpSettings, smtp_factory=None) -> None:
    """465 는 SSL, 그 외는 STARTTLS. smtp_factory 는 테스트용 (smtplib.SMTP 와 같은 인터페이스)."""
    if smtp_factory is None:
        smtp_factory = smtplib.SMTP_SSL if settings.port == 465 else smtplib.SMTP
    with smtp_factory(settings.host, settings.port, timeout=config.SMTP_TIMEOUT) as smtp:
        if settings.port != 465:
            smtp.starttls()
        smtp.login(settings.user, settings.password)
        smtp.send_message(msg, from_addr=settings.sender, to_addrs=settings.recipients)


def record(conn, alerts: dict, subject: str, recipients: int, now: datetime | None = None) -> None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    conn.execute("INSERT INTO notify_log (sent_at, subject, article_ids, terms, recipients) VALUES (?,?,?,?,?)",
                 (now.isoformat(), subject, json.dumps(alerts["article_ids"], ensure_ascii=False),
                  json.dumps([t["term"] for t in alerts["rising"]], ensure_ascii=False), recipients))
    conn.commit()


def notify(conn, report_data: dict, report_path: Path | None, dry_run: bool = False, env=None, smtp_factory=None,
           now: datetime | None = None, out=print) -> str:
    """알림 조건을 확인하고 해당 항목이 있으면 보낸다. 반환: 'no_alerts' | 'dry_run' | 'sent'."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    alerts = select_alerts(conn, report_data, now)
    counts = (len(alerts["new_topic"]), len(alerts["high_impact"]), len(alerts["rising"]))
    log.info("알림 대상: 주제 신규 %d건, 중요도 %d건, 급증 키워드 %d개 (기준 %s 이후 수집)", *counts, alerts["since"])
    if alerts["skipped_terms"]:
        log.info("최근 %s일 안에 이미 알린 급증 키워드는 제외: %s", alerts["rules"]["rising_repeat_days"], alerts["skipped_terms"])
    if not has_alerts(alerts):
        log.info("알림 조건에 해당하는 항목이 없어 메일을 보내지 않습니다")
        return "no_alerts"

    if dry_run:
        try:
            settings = settings_from_env(env)
            sender, recipients, note = settings.sender, settings.recipients, f"수신자 {len(settings.recipients)}명"
        except NotifyConfigError as e:
            sender, recipients, note = "(미설정)", ["(미설정)"], f"실제 발송 불가 — {e}"
        msg = build_message(alerts, report_data, report_path, sender, recipients)
        out("=" * 70)
        out(f"[dry-run] 메일을 보내지 않고 내용만 출력합니다 ({note})")
        out(f"제목: {msg['Subject']}")
        att = [p.get_filename() for p in msg.iter_attachments()]
        out(f"첨부: {', '.join(att) if att else '없음'}")
        out("-" * 70)
        out(msg.get_body(preferencelist=("plain",)).get_content())
        out("=" * 70)
        return "dry_run"

    settings = settings_from_env(env)
    msg = build_message(alerts, report_data, report_path, settings.sender, settings.recipients)
    send(msg, settings, smtp_factory)
    record(conn, alerts, msg["Subject"], len(settings.recipients), now)
    log.info("알림 메일 발송: %s (수신자 %d명)", msg["Subject"], len(settings.recipients))
    return "sent"
