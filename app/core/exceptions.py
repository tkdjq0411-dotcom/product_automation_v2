from fastapi import HTTPException

def bad_request(msg: str):
    raise HTTPException(status_code=400, detail=msg)
