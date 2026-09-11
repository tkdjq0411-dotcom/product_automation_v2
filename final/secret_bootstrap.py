from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOOTSTRAP = ROOT / ".api_bootstrap.env"


def external_path() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "B2B_SaaS" / "secrets" / "credentials.env"
    return Path.home() / ".config" / "B2B_SaaS" / "secrets" / "credentials.env"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"{k}={v}" for k, v in sorted(values.items())) + "\n"
    path.write_text(content, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def restrict_windows_acl(path: Path) -> None:
    if os.name != "nt":
        return
    # Best-effort ACL hardening. Failure does not block local development.
    try:
        import subprocess
        username = os.getenv("USERNAME", "")
        if username:
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    except Exception:
        pass


def main() -> None:
    if not BOOTSTRAP.exists():
        return
    incoming = parse_env(BOOTSTRAP)
    allowed = {
        "NAVER_COMMERCE_CLIENT_ID",
        "NAVER_COMMERCE_CLIENT_SECRET",
        "NAVER_COMMERCE_TOKEN_TYPE",
        "NAVER_COMMERCE_ACCOUNT_ID",
        "COUPANG_ACCESS_KEY",
        "COUPANG_SECRET_KEY",
        "COUPANG_VENDOR_ID",
    }
    incoming = {k: v for k, v in incoming.items() if k in allowed and v != ""}
    if not incoming:
        BOOTSTRAP.unlink(missing_ok=True)
        return
    target = external_path()
    current = parse_env(target)
    current.update(incoming)
    current.setdefault("NAVER_COMMERCE_TOKEN_TYPE", "SELF")
    current.pop("NAVER_COMMERCE_ACCOUNT_ID", None) if current.get("NAVER_COMMERCE_TOKEN_TYPE", "SELF").upper() == "SELF" else None
    write_env(target, current)
    restrict_windows_acl(target)
    # Remove the plaintext bootstrap from the extracted project after first launch.
    try:
        BOOTSTRAP.write_text("", encoding="utf-8")
    finally:
        BOOTSTRAP.unlink(missing_ok=True)
    print("[API 설정] 네이버 API 자격증명을 프로젝트 밖의 로컬 보안 설정으로 이동했습니다.")


if __name__ == "__main__":
    main()
