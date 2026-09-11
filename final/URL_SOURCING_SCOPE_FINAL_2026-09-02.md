# 무재고 B2B URL 자동소싱 지원 범위

이 프로젝트는 자체 재고를 보유하지 않는 판매자 운영 자동화용이다. 입고/출고/창고 재고 기능을 URL 소싱 흐름에 추가하지 않는다.

## 지원 범위
- 국내: 네이버 스마트스토어/네이버쇼핑, 쿠팡, G마켓, 옥션, 11번가
- 중국: Alibaba.com, 1688, AliExpress, Taobao, Tmall
- 글로벌: Amazon, eBay, Temu

## 실제 수집 원칙
1. 입력 URL의 실제 상품 페이지에 HTTP로 접근한다.
2. JSON-LD/OpenGraph/페이지 내 상품 상태 데이터를 분석한다.
3. 정보가 부족하면 Playwright Chromium으로 실제 렌더링 후 다시 분석한다.
4. 로그인, CAPTCHA, 접근통제는 우회하지 않는다. 공식 API/제휴 권한이 필요한 경우 API_REQUIRED로 명시한다.
5. 수집되지 않은 가격/옵션/배송비를 임의 값으로 만들지 않는다.
6. 저장 전 사용자가 실제 원본과 결과를 확인한다.
7. 자체 재고 대신 공급처 AVAILABLE/OUT_OF_STOCK/UNKNOWN 상태를 관리한다.
