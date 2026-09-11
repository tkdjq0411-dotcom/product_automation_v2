# NAVER SmartStore Hybrid V8

- V7의 상품번호 중심 네트워크 추출과 브랜드스토어에서 성공한 DOM/옵션 경로를 유지합니다.
- SmartStore는 구매영역 DOM 구조가 다른 경우가 있어 OG/meta + 화면 DOM을 병행합니다.
- URL slug를 공급처명으로 사용하지 않습니다. 실제 표시 상점명만 인정합니다.
- direct DOM 값이 비어 있다는 이유로 이미 확인된 OG/JSON-LD 가격/배송비를 지우지 않습니다.
- 상품명은 SmartStore에서 실제 product OG title을 우선 fallback으로 사용하고, 비밀번호/로그인/삭제 UI 문구는 계속 차단합니다.
- 대표이미지는 갤러리 DOM을 못 잡으면 실제 og:image를 fallback으로 사용합니다.
- SmartStore 옵션 탐색 범위를 페이지 전체의 실제 선택 컨트롤까지 확장했습니다.
- Brand Store에서 이미 성공한 PACIENCIA 옵션 수집 경로는 유지합니다.
