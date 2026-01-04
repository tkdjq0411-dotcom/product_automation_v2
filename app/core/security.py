import hashlib

def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
