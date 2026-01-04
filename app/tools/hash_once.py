import hashlib

code = "K9FQ7M2XPA"
hashed = hashlib.sha256(code.encode("utf-8")).hexdigest()
print(hashed)
