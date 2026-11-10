#!/usr/bin/env bash
# 주 1회 갱신 단일 스크립트. 키가 없으면 샘플 데이터로 동작.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
python3 -m src.run "$@"
