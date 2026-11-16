"""탄소정책 모니터링 실행 진입점.

  python main.py collect   기사 수집·저장
  python main.py report    리포트 HTML 생성
  python main.py tiers     기사에 출처 신뢰도 등급(공식/일반/단체·업계 주장/미분류)을 부여 (collect, run 에 포함)
  python main.py enrich    LLM 으로 기사·공식 문서를 분류·요약하고 오늘의 브리핑 생성 (--limit N. 인증 정보 없으면 건너뜀)
  python main.py coverage  새 공식 문서의 제목으로 뉴스를 검색해 후속 보도를 모음
  python main.py link      최근 뉴스를 공식 문서와 연결 (--relink: 기간 내 연결을 지우고 다시 계산)
  python main.py refilter  저장된 기사의 태그와 관련성(무관 기사 필터)을 현재 규칙으로 다시 판정 (config 규칙을 고친 뒤)
  python main.py rank-agencies  공식 기관 중요도를 누적 데이터로 계산 (DB 14일 이상 누적 후. run 에 포함)
  python main.py run       collect + tiers + enrich + coverage + link + rank-agencies + report (매일 실행용)
  python main.py notify    리포트를 만들고 알림 조건(config.NOTIFY_RULES)에 해당하는 항목이 있으면 메일 발송 (--dry-run: 콘솔에만 출력)
                           run 에서는 --notify 를 줄 때만 발송한다 (run --dry-run 은 내용만 출력)
  python main.py search "키워드"   제목·요약에서 검색해 최근 20건 표시 (--from/--to/--topic/--region 과 함께 쓸 수 있음)
  python main.py export    조건에 맞는 기사를 CSV(utf-8-sig)로 저장: --from YYYY-MM-DD --to YYYY-MM-DD --topic ... --region ... --out out.csv
  python main.py reweight  영향도 키워드 가중치를 누적 데이터로 갱신하고 공식 문서 재판정 (주 1회 권장)
  python main.py classify  저장된 공식 문서를 현재 규칙으로 재판정 (config 규칙을 고친 뒤)
  python main.py ai-export classify|summary   Claude 앱 예약 작업 세션이 분류·요약할 재료를 work/ 에 JSON 으로 내보냄 (--out)
  python main.py ai-import classify|summary   세션이 쓴 결과(work/ai_종류_날짜.out.json)를 검증해 저장 (--in). 오류면 2
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from carbon import agencies, analysis, db, handoff, llm, notify, pipeline, query, render, weights
from carbon.sources.registry import build_sources

log = logging.getLogger("main")


def setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Windows 콘솔(cp949)에서 표현 못 하는 문자 때문에 로깅이 죽지 않게 한다.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers = [
        logging.FileHandler(config.LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)


def cmd_collect(only: list[str] | None = None) -> None:
    pipeline.collect(build_sources(only) if only else None)


def cmd_enrich(limit: int | None = None, force_briefing: bool = False) -> None:
    """LLM 으로 기사·공식 문서를 분류·요약하고 오늘의 브리핑을 만든다. 인증 정보가 없으면 건너뛴다 (나머지 단계는 그대로 동작)."""
    conn = db.connect()
    try:
        llm.enrich(conn, limit=limit, force_briefing=force_briefing)
    finally:
        conn.close()


def cmd_refilter() -> None:
    """저장된 기사에 현재 규칙으로 태그와 관련성(무관 기사 필터)을 다시 판정한다. config 의 TOPICS·RELEVANCE_RULES 를 고친 뒤 사용."""
    conn = db.connect()
    try:
        pipeline.refilter(conn)
    finally:
        conn.close()


def cmd_rank_agencies() -> None:
    """공식 기관 중요도를 누적 데이터로 다시 계산한다 (DB 에 14일 이상 쌓인 뒤부터). 환경부는 항상 1순위로 고정."""
    conn = db.connect()
    try:
        agencies.rank_agencies(conn, csv_path=config.REPORT_DIR / "agency_ranking.csv")
    finally:
        conn.close()


def cmd_tiers() -> None:
    """기사에 출처 신뢰도 등급을 (다시) 부여한다. config 의 등급 규칙이나 보정 목록을 고친 뒤 사용."""
    conn = db.connect()
    try:
        pipeline.assign_tiers(conn)
    finally:
        conn.close()


def cmd_coverage() -> None:
    """새 공식 문서의 제목으로 뉴스를 검색해 후속 보도를 모은다."""
    conn = db.connect()
    try:
        pipeline.search_coverage(conn)
    finally:
        conn.close()


def cmd_link(relink: bool = False) -> None:
    """최근 뉴스를 공식 문서와 연결한다. --relink 는 기간 내 연결을 모두 지우고 다시 계산한다."""
    conn = db.connect()
    try:
        pipeline.link_news(conn, relink=relink)
    finally:
        conn.close()


def cmd_reweight() -> None:
    """키워드 가중치를 누적 데이터로 다시 계산하고, 저장된 공식 문서를 재판정한다."""
    conn = db.connect()
    try:
        weights.reweight(conn, csv_path=config.REPORT_DIR / "weight_changes.csv")
        pipeline.reclassify_official(conn)
    finally:
        conn.close()


def cmd_classify() -> None:
    """가중치는 그대로 두고 저장된 공식 문서를 현재 규칙으로 재판정한다 (config 의 규칙·seed 를 고친 뒤 사용)."""
    conn = db.connect()
    try:
        weights.ensure_seeds(conn)
        pipeline.reclassify_official(conn)
    finally:
        conn.close()


def cmd_report():
    data = analysis.build_report_data(days=7)
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.REPORT_DIR / f"report_{data['generated_at'][:10]}.html"
    path.write_text(render.render_report(data), encoding="utf-8")
    log.info("리포트 생성: %s", path)
    return data, path


def cmd_notify(data: dict, path, dry_run: bool = False) -> None:
    """알림 조건에 해당하는 항목이 있을 때만 리포트를 메일로 보낸다. dry_run 이면 콘솔에만 출력하고 발송 기록을 남기지 않는다."""
    conn = db.connect()
    try:
        notify.notify(conn, data, path, dry_run=dry_run)
    finally:
        conn.close()


def cmd_search(term: str | None, f_args: dict) -> None:
    if not term:
        raise query.QueryError('검색어가 필요합니다: python main.py search "키워드"')
    f = query.make_filters(keyword=term, **f_args)
    conn = db.connect()
    try:
        items = query.find(conn, f, limit=query.SEARCH_LIMIT)
    finally:
        conn.close()
    print(f"'{term}' 검색 결과 (최근 {query.SEARCH_LIMIT}건까지): {len(items)}건")
    print(query.format_table(items))


def cmd_export(f_args: dict, out: str | None) -> None:
    f = query.make_filters(**f_args)
    path = Path(out) if out else config.REPORT_DIR / f"export_{datetime.now(config.KST):%Y%m%d_%H%M}.csv"
    conn = db.connect()
    try:
        items = query.find(conn, f)
    finally:
        conn.close()
    query.export_csv(items, path)
    log.info("내보내기: %d건 → %s", len(items), path)


AI_KINDS = ("classify", "summary")


def _ai_paths(kind: str, day: str, in_path: str | None) -> tuple[Path, Path]:
    """(내보낸 파일, 결과 파일). --in 이 *.out.json 이면 내보낸 파일은 같은 폴더의 *.json 으로 본다."""
    if in_path:
        out = Path(in_path)
        exported = out.with_name(out.name.replace(".out.json", ".json")) if out.name.endswith(".out.json") \
            else config.AI_WORK_DIR / f"ai_{kind}_{day}.json"
        return exported, out
    return config.AI_WORK_DIR / f"ai_{kind}_{day}.json", config.AI_WORK_DIR / f"ai_{kind}_{day}.out.json"


def cmd_ai(command: str, kind: str | None, out_path: str | None, in_path: str | None) -> int:
    """세션 AI 파일 내보내기·가져오기. 성공 0, 사용법·파일·형식 오류 2 (DB 는 바뀌지 않음)."""
    if kind not in AI_KINDS:
        log.error("%s 다음에 종류를 쓰세요: %s", command, " | ".join(AI_KINDS))
        return 2
    now = datetime.now(timezone.utc)
    day = handoff.day_kst(now)
    conn = db.connect()
    try:
        if command == "ai-export":
            data = handoff.export_classify(conn, now) if kind == "classify" else handoff.export_summary(conn, now)
            path = Path(out_path) if out_path else config.AI_WORK_DIR / f"ai_{kind}_{day}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            n = len(data["items"]) if kind == "classify" else len(data["materials"])
            log.info("내보냄: %s (%d건) → 결과는 %s 에 쓰세요", path, n, path.with_name(path.name.replace(".json", ".out.json")))
            return 0
        exported_path, result_path = _ai_paths(kind, day, in_path)
        try:
            exported = json.loads(exported_path.read_text(encoding="utf-8-sig"))
            out = json.loads(result_path.read_text(encoding="utf-8-sig"))     # PowerShell 이 붙이는 BOM 허용
        except FileNotFoundError as e:
            log.error("파일 없음: %s", e.filename)
            return 2
        except ValueError as e:
            log.error("JSON 형식 오류: %s", e)
            return 2
        try:
            res = handoff.import_classify(conn, out, exported, now) if kind == "classify" \
                else handoff.import_summary(conn, out, exported, now)
        except handoff.HandoffError as e:
            log.error("%s", e)
            return 2
        log.info("가져옴 (%s): %s", kind, res)
        return 0
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="탄소정책 기사 수집·분석")
    parser.add_argument("command", choices=["collect", "tiers", "enrich", "coverage", "link", "rank-agencies", "refilter", "report",
                                            "run", "notify", "search", "export", "reweight", "classify", "ai-export", "ai-import"],
                        nargs="?", default="run")
    parser.add_argument("term", nargs="?", help="search 명령의 검색어 / ai-export·ai-import 의 종류 (classify | summary)")
    parser.add_argument("--in", dest="in_path", help="ai-import: 세션이 쓴 결과 파일 (기본 work/ai_종류_날짜.out.json)")
    parser.add_argument("--from", dest="date_from", help="search/export: 시작일 YYYY-MM-DD (KST, 포함)")
    parser.add_argument("--to", dest="date_to", help="search/export: 종료일 YYYY-MM-DD (KST, 포함)")
    parser.add_argument("--topic", help="search/export: 주제 (config.TOPICS 의 이름, 일부만 써도 됨. 예: CBAM)")
    parser.add_argument("--region", help="search/export: 지역 (config.REGIONS 의 이름. 예: EU)")
    parser.add_argument("--out", help="export: 저장할 CSV 경로 (기본 reports/export_날짜_시각.csv) / ai-export: 내보낼 JSON 경로")
    parser.add_argument("--limit", type=int, help="enrich 에서 이번에 처리할 최대 건수 (처음에는 --limit 3 으로 시험해 보세요)")
    parser.add_argument("--force-briefing", action="store_true", help="enrich 에서 오늘 브리핑이 이미 있어도 다시 만듦")
    parser.add_argument("--relink", action="store_true", help="link 명령에서 기간 내 연결을 모두 지우고 다시 계산")
    parser.add_argument("--only", help="수집할 출처만 쉼표로 지정 (예: official_boards,eu_presscorner). 기본은 config.SOURCES 전체")
    parser.add_argument("--notify", action="store_true", help="run 에서 알림 조건에 해당하는 항목이 있으면 메일 발송 (SMTP 환경변수 필요)")
    parser.add_argument("--dry-run", action="store_true", help="run/notify 에서 메일을 보내지 않고 내용만 콘솔에 출력")
    args = parser.parse_args(argv)
    setup_logging()
    if args.command in ("ai-export", "ai-import"):
        return cmd_ai(args.command, args.term, args.out, args.in_path)
    f_args = {"date_from": args.date_from, "date_to": args.date_to, "topic": args.topic, "region": args.region}
    if args.command in ("search", "export"):
        try:
            if args.command == "search":
                cmd_search(args.term, f_args)
            else:
                cmd_export(f_args, args.out)
        except query.QueryError as e:
            log.error("%s", e)
            return 2
        return 0
    started = datetime.now()
    try:
        if args.command in ("collect", "run"):
            cmd_collect(args.only.split(",") if args.only else None)
        if args.command in ("tiers", "collect", "run"):
            cmd_tiers()
        if args.command in ("enrich", "run"):
            cmd_enrich(args.limit, args.force_briefing)
        if args.command in ("coverage", "run"):
            cmd_coverage()
        if args.command in ("link", "run"):
            cmd_link(args.relink)
        if args.command in ("rank-agencies", "run"):
            cmd_rank_agencies()
        if args.command == "refilter":
            cmd_refilter()
        if args.command == "reweight":
            cmd_reweight()
        if args.command == "classify":
            cmd_classify()
        if args.command in ("report", "run", "notify"):
            data, path = cmd_report()
            if args.command == "notify" or (args.command == "run" and (args.notify or args.dry_run)):
                cmd_notify(data, path, dry_run=args.dry_run)
    except Exception:
        log.exception("실행 실패")
        return 1
    log.info("완료 (%.1f초)", (datetime.now() - started).total_seconds())
    return 0


if __name__ == "__main__":
    sys.exit(main())
