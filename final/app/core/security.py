import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.core.config import SECRET_KEY

TOKEN_EXPIRE_SECONDS = 60 * 60 * 24
PASSWORD_ITERATIONS = 310_000


def hash_access_code(access_code: str) -> str:
    return hashlib.sha256(access_code.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 password hash.

    Format: pbkdf2_sha256$iterations$salt$hash
    """
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64_encode(salt)}${_b64_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_b64, digest_b64 = password_hash.split("$", 3)
            salt = _b64_decode(salt_b64)
            expected = _b64_decode(digest_b64)
            actual = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                int(iterations),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    # 8/28 기준본에서 사용하던 SHA-256 해시 호환.
    # 로그인 성공 시 service.py에서 새 PBKDF2 해시로 자동 교체합니다.
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy, password_hash)


def is_legacy_password_hash(password_hash: str | None) -> bool:
    return bool(password_hash) and not password_hash.startswith("pbkdf2_sha256$")


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: str) -> str:
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64_encode(signature)


def create_access_token(user: dict[str, Any]) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.get("id")),
        "email": user.get("email"),
        "role": user.get("role", "user"),
        "iat": now,
        "exp": now + TOKEN_EXPIRE_SECONDS,
        "jti": str(uuid4()),
    }

    encoded_header = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{encoded_header}.{encoded_payload}"
    signature = _sign(message)

    return f"{message}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("invalid token format")

        message = f"{parts[0]}.{parts[1]}"
        expected_signature = _sign(message)

        if not hmac.compare_digest(expected_signature, parts[2]):
            raise ValueError("invalid token signature")

        payload = json.loads(_b64_decode(parts[1]).decode("utf-8"))

        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired token")

        if not payload.get("sub"):
            raise ValueError("invalid token subject")

        return payload

    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired token")


def token_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
