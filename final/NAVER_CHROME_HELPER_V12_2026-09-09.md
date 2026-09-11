# NAVER Chrome Helper V12

- 네이버 SmartStore/BrandStore는 서버 자동수집을 먼저 시도합니다.
- 서버 결과가 미완료이면 B2B 화면이 네이버 상품 페이지를 새 탭으로 열고 Chrome 도우미가 실제 렌더링 페이지를 자동 수집합니다.
- 확장프로그램에서 버튼을 누르거나 값을 복사할 필요가 없습니다.
- 수집 데이터는 로컬 B2B 서버(127.0.0.1:8000)에만 전달됩니다.
- 상품명/실제 상점명/최종가/배송비/갤러리/옵션/판매상태를 직접수집 값으로 우선 적용합니다.
- 서버 Collector V11은 삭제하지 않고 fallback/향후 무설치 전환용으로 유지합니다.

## 설치
1. Chrome -> chrome://extensions
2. 개발자 모드 켜기
3. `chrome_extension/naver_source_helper` 폴더를 `압축해제된 확장 프로그램을 로드합니다`로 설치
4. B2B 서버 실행
5. 상품소싱에서 네이버 URL 입력 후 `실제 URL 가져오기`
