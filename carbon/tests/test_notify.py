from datetime import timedelta
from email import message_from_bytes
from email.policy import default as default_policy

import pytest

import config
from carbon import notify
from tests.conftest import NOW

ENV = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "587", "SMTP_USER": "bot@example.com",
       "SMTP_PASSWORD": "pw-should-not-leak", "NOTIFY_TO": "a@example.com, b@example.com"}


def add(conn, aid, title, topics="", hours_ago=1.0, collected_hours_ago=None, source_type="news", tier=2,
        relevant=None, llm_impact=None, llm_topics=None, agency=None, published_days_ago=None):
    pub = NOW - (timedelta(days=published_days_ago) if published_days_ago is not None else timedelta(hours=hours_ago))
    col = NOW - timedelta(hours=hours_ago if collected_hours_ago is None else collected_hours_ago)
    conn.execute(
        "INSERT INTO articles (id,title,url,source,lang,published,collected,topics,source_type,agency,source_tier,relevant,"
        "llm_impact,llm_topics,llm_done_at,llm_summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (aid, title, f"https://example.com/{aid}", "언론사", "ko", pub.isoformat(), col.isoformat(), topics, source_type,
         agency, tier, relevant, llm_impact, llm_topics, NOW.isoformat() if llm_topics is not None else None,
         "요약" if llm_impact else None))
    conn.commit()


def report(rising=None):
    return {"generated_at": NOW.astimezone(config.KST).isoformat(), "rising_terms": rising or [], "briefing": ""}


def term(t, ratio, recent=5):
    return {"term": t, "recent": recent, "baseline": 1.0, "ratio": ratio}


def ids(items):
    return sorted(x["id"] for x in items)


def test_default_rule_topics_exist_in_config():
    assert set(config.NOTIFY_RULES["new_topics"]) <= set(config.TOPICS)


def test_topic_condition_selects_only_cbam_and_ets(conn):
    add(conn, "cbam", "EU CBAM 확정", topics="CBAM/탄소국경")
    add(conn, "ets", "배출권 할당", topics="배출권거래제(ETS),감축목표/NDC")
    add(conn, "ndc", "NDC 발표", topics="감축목표/NDC")
    add(conn, "none", "태그 없음", topics="")
    a = notify.select_alerts(conn, report(), NOW)
    assert ids(a["new_topic"]) == ["cbam", "ets"]
    ets = next(x for x in a["new_topic"] if x["id"] == "ets")
    assert ets["matched"] == ["배출권거래제(ETS)"]
    assert a["high_impact"] == [] and a["rising"] == []
    assert notify.has_alerts(a)


def test_llm_topics_override_keyword_topics(conn):
    # LLM 이 처리한 기사는 LLM 의 최종 주제를 따른다 (리포트와 같은 기준)
    add(conn, "x", "키워드는 CBAM", topics="CBAM/탄소국경", llm_topics="에너지 전환·재생에너지")
    add(conn, "y", "키워드 없음", topics="", llm_topics="배출권거래제(ETS)")
    assert ids(notify.select_alerts(conn, report(), NOW)["new_topic"]) == ["y"]


def test_high_impact_condition(conn):
    add(conn, "h", "중요한 기사", llm_impact="high")
    add(conn, "m", "보통 기사", llm_impact="medium")
    add(conn, "n", "LLM 미처리")
    a = notify.select_alerts(conn, report(), NOW)
    assert ids(a["high_impact"]) == ["h"] and a["new_topic"] == []


def test_article_matching_two_conditions_appears_in_both(conn):
    add(conn, "both", "CBAM 중요", topics="CBAM/탄소국경", llm_impact="high")
    a = notify.select_alerts(conn, report(), NOW)
    assert ids(a["new_topic"]) == ["both"] and ids(a["high_impact"]) == ["both"]
    assert a["article_ids"] == ["both"]


def test_irrelevant_tier3_and_old_articles_excluded(conn):
    add(conn, "irr", "무관 CBAM", topics="CBAM/탄소국경", relevant=0)
    add(conn, "t3", "단체 주장 CBAM", topics="CBAM/탄소국경", tier=3)
    add(conn, "old", "옛 기사 CBAM", topics="CBAM/탄소국경", published_days_ago=30, collected_hours_ago=1)
    add(conn, "undecided", "미판정 CBAM", topics="CBAM/탄소국경", relevant=None)
    assert ids(notify.select_alerts(conn, report(), NOW)["new_topic"]) == ["undecided"]
    # exclude_tier3 를 끄면 3등급도 대상
    assert "t3" in ids(notify.select_alerts(conn, report(), NOW, rules={"exclude_tier3": False})["new_topic"])


def test_official_document_uses_agency_as_source(conn):
    add(conn, "o", "배출권 할당계획 고시", topics="배출권거래제(ETS)", source_type="official", tier=1, agency="기후에너지환경부")
    item = notify.select_alerts(conn, report(), NOW)["new_topic"][0]
    assert item["kind"] == "official" and item["source"] == "기후에너지환경부"


def test_first_run_uses_window_then_last_sent(conn):
    add(conn, "recent", "CBAM 최근", topics="CBAM/탄소국경", hours_ago=2)
    add(conn, "before", "CBAM 어제 전", topics="CBAM/탄소국경", hours_ago=30)
    a = notify.select_alerts(conn, report(), NOW)
    assert a["first_run"] and ids(a["new_topic"]) == ["recent"]       # 기본 24시간
    notify.record(conn, a, "제목", 2, now=NOW - timedelta(hours=1))
    add(conn, "after", "CBAM 발송 후", topics="CBAM/탄소국경", hours_ago=0.5)
    a2 = notify.select_alerts(conn, report(), NOW)
    assert not a2["first_run"] and ids(a2["new_topic"]) == ["after"]   # 발송 이후 수집분만


def test_rising_ratio_threshold_and_repeat_suppression(conn):
    r = report([term("유예", 3.0), term("할당", 2.9), term("무상할당", 5.2)])
    a = notify.select_alerts(conn, r, NOW)
    assert [t["term"] for t in a["rising"]] == ["유예", "무상할당"]       # 3배 이상만 (경계 포함)
    notify.record(conn, a, "제목", 1, now=NOW - timedelta(days=1))
    a2 = notify.select_alerts(conn, r, NOW)
    assert a2["rising"] == [] and sorted(a2["skipped_terms"]) == ["무상할당", "유예"]
    # rising_repeat_days(2일) 가 지나면 다시 알린다
    a3 = notify.select_alerts(conn, r, NOW + timedelta(days=2))
    assert [t["term"] for t in a3["rising"]] == ["유예", "무상할당"]


def test_no_alerts_sends_nothing(conn):
    add(conn, "ndc", "NDC 발표", topics="감축목표/NDC")
    calls = []
    status = notify.notify(conn, report([term("x", 2.0)]), None, env=ENV, now=NOW,
                           smtp_factory=lambda *a, **k: calls.append(1))
    assert status == "no_alerts" and calls == []
    assert conn.execute("SELECT COUNT(*) FROM notify_log").fetchone()[0] == 0


def test_settings_require_env_and_hide_values():
    with pytest.raises(notify.NotifyConfigError) as e:
        notify.settings_from_env({"SMTP_HOST": "h", "SMTP_PASSWORD": "secret-value"})
    assert "SMTP_USER" in str(e.value) and "NOTIFY_TO" in str(e.value) and "secret-value" not in str(e.value)
    s = notify.settings_from_env(ENV)
    assert s.recipients == ["a@example.com", "b@example.com"] and s.sender == "bot@example.com" and s.port == 587
    assert "pw-should-not-leak" not in repr(s)
    with pytest.raises(notify.NotifyConfigError):
        notify.settings_from_env({**ENV, "SMTP_PORT": "abc"})


def test_dry_run_prints_without_sending_or_recording(conn, tmp_path):
    add(conn, "cbam", "EU CBAM <확정>", topics="CBAM/탄소국경")
    path = tmp_path / "report_2026-11-03.html"
    path.write_text("<html>리포트</html>", encoding="utf-8")
    printed, calls = [], []
    status = notify.notify(conn, report(), path, dry_run=True, env={}, now=NOW, out=printed.append,
                           smtp_factory=lambda *a, **k: calls.append(1))
    text = "\n".join(printed)
    assert status == "dry_run" and calls == []
    assert "EU CBAM <확정>" in text and "실제 발송 불가" in text and "report_2026-11-03.html" in text
    assert conn.execute("SELECT COUNT(*) FROM notify_log").fetchone()[0] == 0


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.log = host, port, []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.log.append("starttls")

    def login(self, user, password):
        self.log.append(("login", user))

    def send_message(self, msg, from_addr=None, to_addrs=None):
        self.sent = (msg, from_addr, to_addrs)


def test_send_attaches_report_and_records(conn, tmp_path):
    FakeSMTP.instances = []
    add(conn, "cbam", "EU CBAM 확정", topics="CBAM/탄소국경")
    path = tmp_path / "report_2026-11-03.html"
    path.write_text("<html>리포트 본문</html>", encoding="utf-8")
    status = notify.notify(conn, report([term("유예", 4.0)]), path, env=ENV, now=NOW, smtp_factory=FakeSMTP)
    assert status == "sent"
    smtp = FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.example.com", 587) and smtp.log == ["starttls", ("login", "bot@example.com")]
    msg, sender, to = smtp.sent
    assert to == ["a@example.com", "b@example.com"] and sender == "bot@example.com"
    parsed = message_from_bytes(msg.as_bytes(), policy=default_policy)
    assert "신규 1건" in parsed["Subject"] and "급증 키워드 1개" in parsed["Subject"]
    att = list(parsed.iter_attachments())
    assert [a.get_filename() for a in att] == ["report_2026-11-03.html"]
    assert "리포트 본문" in att[0].get_content()
    assert "pw-should-not-leak" not in msg.as_string()
    row = conn.execute("SELECT article_ids, terms, recipients FROM notify_log").fetchone()
    assert row["article_ids"] == '["cbam"]' and row["terms"] == '["유예"]' and row["recipients"] == 2
    # 같은 항목은 다음 실행에서 다시 알리지 않는다
    assert notify.notify(conn, report([term("유예", 4.0)]), path, env=ENV, now=NOW + timedelta(minutes=5),
                         smtp_factory=FakeSMTP) == "no_alerts"


def test_inline_mode_uses_report_as_html_body(conn, tmp_path):
    add(conn, "cbam", "EU CBAM 확정", topics="CBAM/탄소국경")
    path = tmp_path / "r.html"
    path.write_text("<html>인라인 리포트</html>", encoding="utf-8")
    a = notify.select_alerts(conn, report(), NOW)
    msg = notify.build_message(a, report(), path, "s@example.com", ["t@example.com"], attach=False)
    assert list(msg.iter_attachments()) == []
    assert "인라인 리포트" in msg.get_body(preferencelist=("html",)).get_content()
    assert "EU CBAM 확정" in msg.get_body(preferencelist=("plain",)).get_content()


def test_failed_send_is_not_recorded(conn):
    add(conn, "cbam", "EU CBAM 확정", topics="CBAM/탄소국경")

    class Boom(FakeSMTP):
        def login(self, user, password):
            raise OSError("auth failed")

    with pytest.raises(OSError):
        notify.notify(conn, report(), None, env=ENV, now=NOW, smtp_factory=Boom)
    assert conn.execute("SELECT COUNT(*) FROM notify_log").fetchone()[0] == 0


def test_html_escapes_titles(conn):
    add(conn, "x", "<script>alert(1)</script> CBAM", topics="CBAM/탄소국경")
    a = notify.select_alerts(conn, report(), NOW)
    body = notify.html_summary(a, report(), None, True)
    assert "<script>" not in body and "&lt;script&gt;" in body
