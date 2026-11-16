from datetime import timedelta

import config
from carbon import pipeline, policy, weights
from tests.conftest import NOW, FakeSource, make_article


def official(title, url, days_ago=1.0, stage=None):
    a = make_article(title, days_ago=days_ago, url=url, source="기후에너지환경부")
    a.source_type, a.agency = "official", "기후에너지환경부"
    from carbon.sources.base import official_id
    a.id = official_id(url)
    return a


def set_collected(conn, days_back):
    """DB 에 쌓인 기간이 days_back 일인 것처럼 수집 시각을 벌려 놓는다."""
    rows = conn.execute("SELECT id FROM articles ORDER BY id").fetchall()
    for i, r in enumerate(rows):
        day = NOW - timedelta(days=days_back * i / max(len(rows) - 1, 1))
        conn.execute("UPDATE articles SET collected=? WHERE id=?", (day.isoformat(), r["id"]))
    conn.commit()


def seed_corpus(conn):
    """배출권거래제는 자주·공식 문서에 많이 나오고 확정이 많다. 자발적 탄소시장은 거의 안 나온다."""
    arts = []
    for i in range(8):
        arts.append(official(f"배출권거래제 할당 기준 고시 {i}", f"https://x.test/ets{i}", days_ago=i * 0.5))
    for i in range(4):
        arts.append(make_article(f"배출권거래제 뉴스 {i}", days_ago=i))
    for i in range(3):
        arts.append(make_article(f"자발적 탄소시장 논의 {i}", days_ago=i))
    pipeline.collect([FakeSource(arts)], conn=conn)


def test_load_weights_defaults_to_seeds_and_does_not_write(conn):
    w = weights.load_weights(conn)
    assert w == policy.seed_weights()
    assert conn.execute("SELECT COUNT(*) FROM keyword_weights").fetchone()[0] == 0


def test_ensure_seeds_is_idempotent_and_adds_new_keywords(conn):
    weights.ensure_seeds(conn)
    n = conn.execute("SELECT COUNT(*) FROM keyword_weights").fetchone()[0]
    assert n == len(config.IMPACT_SEEDS)
    weights.ensure_seeds(conn)
    assert conn.execute("SELECT COUNT(*) FROM keyword_weights").fetchone()[0] == n


def test_short_history_keeps_seed_only(conn):
    """DB 에 쌓인 기간이 14일 미만이면 학습하지 않고 seed 만 쓴다."""
    seed_corpus(conn)
    set_collected(conn, days_back=3)
    changes = weights.reweight(conn, now=NOW)
    assert not any(c["changed"] for c in changes)
    assert weights.load_weights(conn) == policy.seed_weights()
    assert all(c["learned_new"] is None for c in changes)


def test_enough_history_learns_and_blends_with_seed(conn):
    seed_corpus(conn)
    set_collected(conn, days_back=20)
    pipeline.reclassify_official(conn)
    changes = {c["keyword"]: c for c in weights.reweight(conn, now=NOW)}
    ets, volun = changes["배출권거래제"], changes["자발적 탄소시장"]
    assert ets["learned_new"] is not None and volun["learned_new"] is not None
    assert ets["learned_new"] > volun["learned_new"]                  # 자주·공식·확정으로 나오는 쪽이 더 높다
    # 최종 = seed*(1-α) + 학습값*α  (α = config.IMPACT_LEARN_RATE)
    a = config.IMPACT_LEARN_RATE
    expected = round(volun["seed"] * (1 - a) + volun["learned_new"] * a, 1)
    assert volun["final_new"] == expected
    assert '"official"' in ets["evidence"]                             # 근거가 JSON 으로 남는다


def test_top_keywords_never_fall_below_floor(conn):
    seed_corpus(conn)
    # 최상위 seed(배출권거래제 95)를 가진 키워드가 학습값 0점이어도 하한 아래로 내려가지 않는다
    assert weights._final(95, 0.0) >= config.IMPACT_FLOOR
    assert weights._final(95, 0.0) == config.IMPACT_FLOOR
    assert weights._final(30, 0.0) == round(30 * (1 - config.IMPACT_LEARN_RATE), 1)   # 낮은 seed 는 하한 없음


def test_keywords_with_too_little_evidence_keep_seed(conn):
    seed_corpus(conn)
    set_collected(conn, days_back=20)
    changes = {c["keyword"]: c for c in weights.reweight(conn, now=NOW)}
    rare = changes["원전"]                                             # 코퍼스에 거의 안 나옴
    assert rare["learned_new"] is None and rare["final_new"] == rare["seed"]
    assert "reason" in rare["evidence"]


def test_reweight_changes_future_classification_and_writes_csv(conn, tmp_path):
    seed_corpus(conn)
    set_collected(conn, days_back=20)
    csv_path = tmp_path / "weight_changes.csv"
    weights.reweight(conn, now=NOW, csv_path=csv_path)
    text = csv_path.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].startswith("keyword,seed,learned_prev,learned_new,final_prev,final_new,changed")
    assert "배출권거래제" in text
    # 갱신된 가중치가 새 문서의 판정에 쓰인다
    w = weights.load_weights(conn)
    assert w["자발적 탄소시장"] != policy.seed_weights()["자발적 탄소시장"]


def test_removed_seed_keywords_in_table_are_ignored(conn):
    weights.ensure_seeds(conn)
    conn.execute("INSERT INTO keyword_weights (keyword,seed_weight,final_weight) VALUES ('삭제된키워드', 10, 99)")
    assert "삭제된키워드" not in weights.load_weights(conn)
