"""e2e 용 고정 DB(tests/fixtures/sample.db)를 만든다.

바탕은 실제 수집 결과(sample_items.json: 공식 문서 11건 + 뉴스 60건)이고, 화면 점검에 필요한 경우를 몇 건 더한다.
  - 확정·직접 규제 공식 문서 1건과, 그 문서에 연결된(공식 확인됨) 뉴스 1건
  - 단체·업계 주장(3등급) 단일 출처 + 자극적 표현 뉴스 1건
  - 제목에 <script> 가 든 뉴스 1건 (XSS 점검)
  - 2·5일 전 뉴스 (기간 필터 점검), 무관 기사 1건 (집계 제외 점검)
  - LLM 결과(중요도 high/medium/low, 요약) 몇 건과 오늘의 브리핑

    python tests/fixtures/make_sample_db.py        # 다시 만들 때

기준 시각은 NOW(2026-11-03 12:00 UTC = 21:00 KST)로 고정한다. 리포트도 같은 시각으로 만들어야 결과가 바뀌지 않는다.
"""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from carbon import db  # noqa: E402

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
DB_PATH = HERE / "sample.db"
XSS_TITLE = "<script>alert(1)</script> 배출권 시험 기사"
HOT_TITLE = "제4차 계획기간 배출권 할당계획 확정 고시"
LINKED_NEWS_TITLE = "정부, 4차 배출권 할당계획 확정…업계 부담 커진다 - 연합뉴스"
CLAIM_TITLE = "충격! 탄소세 도입하면 일자리 절반 사라져 - ○○산업협회"


def _id(title: str) -> str:
    return hashlib.sha1(title.encode("utf-8")).hexdigest()


def _utc(kst_iso: str) -> str:
    return datetime.fromisoformat(kst_iso).astimezone(timezone.utc).isoformat()


def build(path: Path = DB_PATH) -> Path:
    path.unlink(missing_ok=True)
    conn = db.connect(path)
    items = json.loads((HERE / "sample_items.json").read_text(encoding="utf-8"))
    col = NOW.isoformat()
    rows = []
    for o in items["official"]:
        rows.append(dict(id=_id(o["title"]), title=o["title"], url=o["url"], source=o["agency"], lang="ko", query=o["board"],
                         published=_utc(o["published"]), source_type="official", agency=o["agency"], official_status="n/a",
                         policy_stage=o["stage"], domestic_impact=o["impact"], impact_keyword=o["impact_keyword"],
                         impact_score=o["impact_score"], source_tier=1, relevant=1, topics="", regions=""))
    for a in items["news"][:50]:   # 리포트 뉴스 목록(최근 60건)에 아래 추가 기사가 모두 들어가도록 50건만
        rows.append(dict(id=_id(a["title"]), title=a["title"], url=a["url"], source=a["source"], lang=a["lang"], query="q",
                         published=_utc(a["published"]), source_type="news", official_status="unconfirmed",
                         source_tier=a["source_tier"], topics=",".join(a["topics"]), regions=",".join(a["regions"])))
    pub = lambda h: (NOW - timedelta(hours=h)).isoformat()
    rows += [
        dict(id=_id(HOT_TITLE), title=HOT_TITLE, url="https://mcee.go.kr/sample/hot", source="기후에너지환경부", lang="ko",
             query="공지·공고", published=pub(30), source_type="official", agency="기후에너지환경부", official_status="n/a",
             policy_stage="decided", domestic_impact="direct", impact_keyword="배출권거래제", impact_score=95.0, source_tier=1,
             relevant=1, topics="배출권거래제(ETS)", regions="한국"),
        dict(id=_id(LINKED_NEWS_TITLE), title=LINKED_NEWS_TITLE, url="https://example.com/news/linked", source="연합뉴스", lang="ko",
             query="q", published=pub(5), source_type="news", official_status="confirmed", source_tier=2, relevant=1,
             topics="배출권거래제(ETS)", regions="한국", llm_done_at=col, llm_topics="배출권거래제(ETS)", llm_regions="한국",
             llm_impact="high", llm_summary="4차 배출권 할당계획이 확정돼 업계 비용 부담이 늘어난다는 보도"),
        dict(id=_id(CLAIM_TITLE), title=CLAIM_TITLE, url="https://example.com/news/claim", source="○○산업협회", lang="ko", query="q",
             published=pub(4), source_type="news", source_tier=3, sensational="충격", relevant=1, topics="탄소가격/탄소세",
             regions="한국"),
        dict(id=_id(XSS_TITLE), title=XSS_TITLE, url="https://example.com/news/xss", source="시험언론", lang="ko", query="q",
             published=pub(6), source_type="news", source_tier=2, relevant=1, topics="배출권거래제(ETS)", regions=""),
        dict(id=_id("이틀 전 CBAM 철강 기사"), title="이틀 전 CBAM 철강 기사 - 매일경제", url="https://example.com/news/2d",
             source="매일경제", lang="ko", query="q", published=pub(50), source_type="news", source_tier=2, relevant=1,
             topics="CBAM/탄소국경,산업·기업 영향", regions="EU"),
        dict(id=_id("닷새 전 영국 ETS 기사"), title="UK ETS expansion consultation opens - Reuters", url="https://example.com/news/5d",
             source="Reuters", lang="en", query="q", published=pub(120), source_type="news", source_tier=2, relevant=1,
             topics="배출권거래제(ETS)", regions="영국"),
        dict(id=_id("무관 기사"), title="Carbon fiber bicycle market report 2026-2033", url="https://example.com/news/irrelevant",
             source="openPR", lang="en", query="q", published=pub(3), source_type="news", source_tier=3, relevant=0,
             relevance_reason="rule:exclude_hard 시장조사 스팸", topics="", regions=""),
    ]
    for r in rows:
        r.setdefault("official_status", "unconfirmed")
    cols = sorted({k for r in rows for k in r})
    conn.executemany(f"INSERT INTO articles ({','.join(cols)}, collected) VALUES ({','.join('?' * len(cols))}, ?)",
                     [[r.get(c) for c in cols] + [col] for r in rows])
    conn.execute("INSERT INTO article_links (news_id, official_id, score, method, created_at) VALUES (?,?,?,?,?)",
                 (_id(LINKED_NEWS_TITLE), _id(HOT_TITLE), 78.0, '{"entity": ["배출권"], "number": ["4"]}', col))
    # LLM 중요도 medium/low 를 실제 뉴스 두 건에
    first_two = [_id(a["title"]) for a in items["news"][:2]]
    conn.execute("UPDATE articles SET llm_done_at=?, llm_topics=topics, llm_regions=regions, llm_impact='medium', "
                 "llm_summary='EU CBAM 대응 협력 소식' WHERE id=?", (col, first_two[0]))
    conn.execute("UPDATE articles SET llm_done_at=?, llm_topics=topics, llm_regions=regions, llm_impact='low' WHERE id=?",
                 (col, first_two[1]))
    conn.execute("INSERT INTO briefings (day, text, model, created_at, source_ids) VALUES (?,?,?,?,?)",
                 ("2026-11-03", "정부가 제4차 배출권 할당계획을 확정 고시했습니다. EU CBAM 대응 협력과 지자체 탄소중립 정책 소식이 이어졌습니다.",
                  "fixture", col, "[]"))
    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    print(build())
