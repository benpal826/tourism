# 배출권 가격(KAU, EUA) 자동 수집 가능성 조사 (F8)

조사일: 2026-11-11 · 범위: 조사만 (코드 없음). 구현 여부는 사용자가 결정한다.

## 조사 방법과 한계 (먼저 읽기)

- 이번 조사 환경(클라우드 세션)은 네트워크 정책 때문에 `krx.co.kr`, `eex.com`, `europa.eu`, `icapcarbonaction.com` 페이지를 **직접 열지 못했다** (DNS 차단). `robots.txt` 도 하나도 읽지 못했다.
- 그래서 아래 내용은 **웹 검색 결과의 요약**과 제3자 오픈소스 코드(GitHub)에 근거한다. 공식 페이지 원문으로 확인하지 못한 항목은 "미확인", 제3자 자료로만 확인한 항목은 "(제3자 자료)"로 표시했다.
- 이용약관 판단은 법률 검토가 아니다. 구현 전에 사용자가 아래 "구현 전 확인할 것"의 원문을 직접 읽어야 한다.

## 가격 종류 구분

같은 "배출권 가격"이라도 출처마다 가리키는 값이 다르다. 리포트에 쓸 때 섞으면 안 된다.

| 구분 | 뜻 | 예 |
| --- | --- | --- |
| 장내 거래 종가 | 거래소 2차 시장의 하루 종가 | KRX 배출권시장 KAU26 종가 |
| 경매 낙찰가 | 정부가 유상할당분을 경매로 팔 때의 낙찰가 (1차 시장, 경매일에만 존재) | KRX KAU 경매, EEX EUA 경매 |
| 선물 가격 | 선물 계약 가격. 언론에 흔히 나오는 EUA 가격은 ICE 12월물 선물 | ICE EUA Dec 선물, Investing.com 시세 |
| 기간 평균 | 주·연 평균 | ICAP 주간 평균, 한국가스공사 연평균 |

## KAU (한국 배출권)

| 출처 | 제공 데이터 | 갱신 주기 | 자동 수집 | 형식 | 비용·약관 | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
| **KRX OPEN API** – "배출권 시장 일별매매정보" (openapi.krx.co.kr) | 종목별(KAU·KCU·KOC 등) 일별 종가·시가·고가·저가·대비·등락률·거래량·거래대금. 2015-01-12부터 | 매 거래일 | **가능** (인증키 + 서비스별 이용 신청·승인 필요). 인증키당 하루 10,000회 | JSON / XML | 인증키 발급 무료 (제3자 자료). 저작권은 KRX (약관 제10조, 검색 요약). **비상업적 이용만 허용, 원자료 제3자 재배포 금지, 출처 "한국거래소 통계정보" 표기** — 제3자 README 의 요약이며 약관 원문 미확인. 배출권 서비스가 무료 대상인지 미확인 | **가장 유력.** 개인 모니터링 용도라면 약관상 가능할 가능성이 높으나 원문 확인 필요 |
| KRX 배출권시장 정보플랫폼 (ets.krx.co.kr) | KAU 종가·대비·등락률·거래량 표, 경매 결과 | 매 거래일 | 미확인 (내려받기 기능 미확인, robots.txt 미확인) | HTML | 미확인 | 화면 긁기(스크래핑)는 API 가 있으므로 권하지 않음 |
| KRX 정보데이터시스템 (data.krx.co.kr) | 배출권 일별 시세 화면 (CSV 내려받기 버튼 존재 여부 미확인) | 매 거래일 | 미확인. 사람이 내려받는 화면이며 자동화 허용 여부 미확인 | 미확인 | 미확인 | 수동 보조용 후보 |
| KRX 데이터 분배상품 | 배출권 실시간·종가 | 실시간/일 | 가능 | 미확인 | **유료** | 범위 밖 (무료 아님) |
| ICAP Allowance Price Explorer | 여러 배출권거래제 가격 비교 (K-ETS 포함 여부·출처 미확인) | 분기별 수동 갱신 | 내려받기 범위 미확인 | 미확인 | 재생산·재배포는 비상업 목적이라도 **ICAP 사전 서면 허락** 필요, 도구와 원출처 표기 | 자동 수집 부적합 |

## EUA (EU 배출권)

| 출처 | 제공 데이터 | 갱신 주기 | 자동 수집 | 형식 | 비용·약관 | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
| **EEX EU ETS 경매 결과 페이지** (eex.com) | EUA 1차 시장 **경매 낙찰가**·물량. 최근 45일 표 + 이력 내려받기 | 경매일마다 (주 여러 회) | 미확인 (robots.txt·자동 조회 허용 조항 미확인) | 미확인 (이력 파일 형식 미확인) | 소량·비상업적 공유는 허용, **체계적 재게시·대량 배포는 EEX 명시적 허락 필요** (검색 요약) | 후보. 단 2차 시장 시세가 아니라 경매가 |
| EEX 경매 보고서 내려받기 | 경매 결과 파일, 2012–2025 이력 보고서 zip | 미확인 | 사람이 내려받는 파일 | 미확인 | 위와 같음 | 과거 이력 1회성 확보용 후보 |
| EEX Webshop (Environmentals EoD 등) | 경매·현물·파생 집계 결과 | 매일 장 마감 후 | 가능 (File Cloud / API) | CSV, XLSX | **유료** (월 €75~) | 범위 밖 (무료 아님) |
| EU 집행위 경매 안내 (climate.ec.europa.eu) | 경매 결과는 경매 플랫폼(EEX) 페이지에 매일 게시, 상세 보고서는 분기별 | 일 / 분기 | 원자료는 EEX 로 연결 | — | — | 독립 출처 아님 (EEX 와 같음) |
| **공공데이터포털 – 한국가스공사 EU-ETS 가격** (data.go.kr 15102705) | **연도별** 최저가·최고가·연평균(유로) | 수시 | 가능 (파일 + 오픈API) | 파일, 오픈API (세부 형식 미확인) | 무료. 이용허락범위 미확인 | 합법·무료가 가장 분명하나 **연 단위**라 일일 모니터링에는 부족 |
| ICAP Allowance Price Explorer – EU ETS | 2019년 이후 **주간 평균**(ICE) 내려받기, 6개월 지연. 일별 종가는 그래프로만 | 분기별 수동 | 내려받기만 (자동화 허용 미확인) | 미확인 | 재배포는 **사전 서면 허락** 필요 | 부적합 (지연·약관) |
| Investing.com EUA 선물 이력 | 일별 선물 가격 (기간 지정 내려받기) | 매일 | 미확인. 사이트 이용약관상 자동 수집 금지 여부 **미확인** | CSV (화면 내려받기) | 미확인 | 약관 확인 전에는 권하지 않음 |
| Ember Carbon Price Viewer | EUA 일별 가격 | **갱신 중단** | — | 과거 CSV 링크는 바뀌어 불확실 | — | 제외 |
| Sandbag Carbon Price Viewer | EUA 가격 (2026년 4월까지 표시) | 미확인 | 내려받기 미확인 | 미확인 | 미확인 | 미확인 |
| Carbon Pulse EU ETS 포털 | 기준 EUA 가격 등 (무료 접근이라고 발표) | 미확인 | 미확인 | 미확인 | 미확인 | 미확인 |
| OilPriceAPI (상용 API) | EUA 일 1회 현물 판독값 (집계 사이트 경유) | 일 | 가능 | JSON | 무료 범위 미확인. 업체 스스로 정산가는 ICE/EEX 를 쓰라고 안내 | 2차 집계라 근거로 쓰기 약함 |

## 정리

- **KAU:** 무료·합법·자동으로 일별 종가를 받을 수 있는 유력 후보는 **KRX OPEN API "배출권 시장 일별매매정보" 하나**다. 다만 이용약관 원문(비상업 조건, 재배포, 배출권 서비스 무료 여부)을 확인하지 못했다.
- **EUA:** 무료로 **일별 2차 시장 시세**를 자동 수집할 수 있는 공식 출처는 **찾지 못했다**. 무료로 확인된 것은 ① EEX 경매 낙찰가(경매일만, 자동 조회 허용 여부 미확인)와 ② 한국가스공사의 연 단위 가격뿐이다. 일별 종가가 필요하면 유료(EEX Webshop 등)이거나 약관이 불분명한 사이트다.
- 두 값을 나란히 보여줄 경우 **KAU 는 장내 종가, EUA 는 경매 낙찰가**처럼 종류가 달라질 수 있으므로 리포트에 종류를 반드시 표시해야 한다.

## 구현 전 확인할 것 (사용자 직접)

1. KRX OPEN API 이용약관 전문 (openapi.krx.co.kr 의 약관 페이지): 비상업 이용 범위, 출처 표기, 재배포 금지 조항, 배출권 서비스의 유료 여부.
2. KRX OPEN API 서비스 목록에서 "배출권 시장 일별매매정보" 의 개발 명세서: 정확한 요청 주소·변수 이름·응답 필드. (제3자 코드상 API ID 는 `ets_bydd_trd`, 응답 필드는 `BAS_DD, ISU_CD, ISU_NM, TDD_CLSPRC, CMPPREVDD_PRC, FLUC_RT, TDD_OPNPRC, TDD_HGPRC, TDD_LWPRC, ACC_TRDVOL, ACC_TRDVAL` — 공식 명세로 확인 필요)
3. EEX 경매 결과 페이지의 이용약관과 `https://www.eex.com/robots.txt`: 자동 조회 허용 여부, 이력 파일 형식.
4. 공공데이터포털 15102705 의 이용허락범위와 오픈API 명세.

## 구현한다면 (참고용, 결정은 사용자)

- `carbon/sources/` 가 아니라 별도 가격 수집기(기사가 아니므로)와 별도 테이블이 필요하다. 마이그레이션 추가.
- 인증키는 환경변수(예: `KRX_API_KEY`)로만 읽는다. 하루 1회 호출이면 호출 상한(10,000회)에 비해 충분히 적다.
- 이 클라우드 환경에서 실행하려면 네트워크 허용 목록에 해당 호스트를 추가해야 한다. Windows PC 에서 실행하면 해당 없음.

## 출처 (검색으로 확인, 원문 미열람)

- KRX OPEN API 서비스 목록: https://openapi.krx.co.kr/contents/OPP/INFO/service/OPPINFO004.cmd
- KRX OPEN API 이용약관: https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO005.jsp
- KRX 데이터 구입안내 / 분배상품: https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA001.jsp , https://openapi.krx.co.kr/contents/OPP/DATA/OPPDATA002.jsp
- KRX 배출권시장 정보플랫폼: https://ets.krx.co.kr/main/main.jsp
- 제3자 코드 krx-openapi (엔드포인트·필드, 약관 요약): https://github.com/seokhoonj/krx-openapi
- EEX EU ETS 경매 시장 데이터: https://www.eex.com/en/market-data/environmentals/eu-ets-auctions
- EEX 내려받기: https://www.eex.com/en/downloads-3
- EEX Webshop Environmentals (EoD): https://webshop.eex-group.com/data-type/eex-environmentals-eod
- EU 집행위 배출권 경매: https://climate.ec.europa.eu/areas-action/carbon-markets/eu-emissions-trading-system-eu-ets/auctioning-allowances_en
- 공공데이터포털 한국가스공사 EU-ETS 가격: https://www.data.go.kr/data/15102705/fileData.do
- ICAP Allowance Price Explorer 이용약관·문서: https://icapcarbonaction.com/en/documentation-allowance-price-explorer
- Ember Carbon Price Viewer (갱신 중단): https://ember-climate.org/data/data-tools/carbon-price-viewer/
- Sandbag Carbon Price Viewer: https://sandbag.be/?p=209078
- Carbon Pulse EU ETS 포털 발표: https://carbon-pulse.com/528703/
- Investing.com EUA 선물 이력: https://www.investing.com/commodities/european-union-allowance-eua-year-futures-historical-data
- OilPriceAPI EUA: https://www.oilpriceapi.com/live/eu-carbon-price
