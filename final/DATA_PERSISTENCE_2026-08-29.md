# 2026-08-29 사용자 데이터 영구 보존 보정

- 프로젝트 ZIP 교체 시 `final/data/b2b_v1.sqlite3`가 함께 바뀌어 계정이 사라지는 문제를 수정했습니다.
- Windows 기본 DB 위치: `%LOCALAPPDATA%\\B2B_SaaS\\data\\b2b_v1.sqlite3`
- 영구 DB가 아직 없고 기존 프로젝트 DB가 있으면 최초 실행 때 한 번만 복사합니다.
- 영구 DB가 이미 있으면 새 ZIP의 DB로 절대 덮어쓰지 않습니다.
- 이후 프로젝트 폴더를 교체해도 사용자/상품/공급처/재고 등 SQLite 데이터는 유지됩니다.
