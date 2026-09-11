from __future__ import annotations

from pathlib import Path
from getpass import getpass

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def read_lines():
    if ENV_PATH.exists():
        return ENV_PATH.read_text(encoding="utf-8").splitlines()
    return ["SECRET_KEY=b2b-v1-local-secret-key"]


def set_value(lines, key, value):
    prefix = key + "="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = prefix + value
            return
    lines.append(prefix + value)


def main():
    print("\n=== NAVER Commerce API local setup ===")
    print("네이버 커머스API센터 > 내 스토어 애플리케이션의 값을 입력하세요.")
    print("이 값은 이 PC의 .env에만 저장되며 브라우저/SQLite에는 저장하지 않습니다.\n")
    client_id = input("Application ID: ").strip()
    secret = getpass("Application Secret (입력 내용 숨김): ").strip()
    if not client_id or not secret:
        print("\n[실패] ID와 Secret은 필수입니다.")
        raise SystemExit(1)
    lines = read_lines()
    set_value(lines, "NAVER_COMMERCE_CLIENT_ID", client_id)
    set_value(lines, "NAVER_COMMERCE_CLIENT_SECRET", secret)
    set_value(lines, "NAVER_COMMERCE_TOKEN_TYPE", "SELF")
    # Own-store applications must use SELF and must not send account_id.
    set_value(lines, "NAVER_COMMERCE_ACCOUNT_ID", "")
    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print("\n[완료] .env에 네이버 내 스토어 API 설정을 저장했습니다.")
    print("B2B 서버가 실행 중이면 종료 후 다시 실행하세요.")
    print("설정 > 판매채널 연동 > NAVER > API 연결 테스트를 누르세요.\n")


if __name__ == "__main__":
    main()
