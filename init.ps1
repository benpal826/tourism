# tourism 실행·검증 준비: 의존성 설치 후 샘플 모드(키 불필요)로 전체 파이프라인 실행. 실패하면 exit 1.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"  # Windows 콘솔(cp949)에서 출력의 특수문자로 죽는 것 방지
python -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit 1 }
python -m src.run --sample | Out-Null
if ($LASTEXITCODE -ne 0) { exit 1 }
# 샘플 산출물이 실제로 생겼는지 확인 (data/_sample, out/sample 은 gitignore)
python -c "import json,sys; c=json.load(open('out/sample/cards.json',encoding='utf-8')); sys.exit(0 if c else 1)"
if ($LASTEXITCODE -ne 0) { Write-Output "out/sample/cards.json 비어 있음"; exit 1 }
Write-Output "init OK"
