"""V1 로컬 DB 호환 레이어.

기존 서비스 코드가 import 경로를 유지할 수 있도록 함수명은 그대로 둡니다.
실제 저장소는 Supabase REST API가 아니라 SQLite입니다.
"""

from app.db.sqlite import delete, insert, select, update

__all__ = ["select", "insert", "update", "delete"]
