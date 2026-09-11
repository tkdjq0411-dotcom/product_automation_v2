# URL 자동 소싱 - 실전 모드

이 프로젝트는 무재고 B2B용이다. 자체 재고수량/입고/출고/창고 기능을 사용하지 않는다.

## 동작 방식
1. 사용자가 실제 상품 상세 URL을 입력한다.
2. 서버가 실제 원본 페이지를 HTTP로 조회한다.
3. JSON-LD, OpenGraph/meta, 페이지 내 실제 상품 상태 JSON을 분석한다.
4. 정보가 부족하면 설치된 Chromium으로 실제 페이지를 렌더링해 한 번 더 분석한다.
5. 상품명, 상품번호, 가격, 통화, 대표/상품 이미지, 옵션, 공급가능상태, 설명을 가능한 범위에서 가져온다.
6. 가져오지 못한 값은 임의의 테스트 값으로 채우지 않는다.
7. CAPTCHA/로그인/접근제한은 우회하지 않는다. 그런 사이트는 공식 API/제휴 권한 연결 대상으로 표시한다.

## 지원 전략
Alibaba, AliExpress, Taobao, Tmall, 1688, JD, DHgate, Made-in-China, GlobalSources,
네이버/스마트스토어, 쿠팡, 11번가, G마켓, 옥션, 롯데ON, SSG 등 국내몰,
Amazon, eBay, Etsy, Walmart, Temu, SHEIN, Rakuten, Qoo10, Shopee, Lazada 등을 인식한다.
목록에 없는 쇼핑몰도 표준 상품 메타데이터가 있으면 GENERIC_OPEN_MARKET 방식으로 수집한다.

## 최초 실행
`run.bat` 또는 `실행.bat`를 사용하면 Python 패키지와 Playwright Chromium 설치 후 서버를 실행한다.
직접 CMD에서 서버를 띄우는 경우 최초 1회:

    python -m pip install -r requirements.txt
    python -m playwright install chromium
    python -m uvicorn app.main:app --reload

## 원칙
모든 사이트를 100% 보장할 수는 없다. 로그인, CAPTCHA, 지역제한, 공개하지 않는 가격/옵션, 공식 API 권한이 필요한 데이터는 사이트 정책상 URL만으로 얻을 수 없다. 이 버전은 우회/가짜값 대신 실제로 얻은 데이터만 사용한다.
