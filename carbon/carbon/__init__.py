"""탄소정책 모니터링 패키지.

의존 방향 (한 방향만 허용):
  수집  main → pipeline → sources, db, tagging
  분석  main → analysis → db
  출력  main → render   (render 는 db·analysis 를 import 하지 않는다)
"""
