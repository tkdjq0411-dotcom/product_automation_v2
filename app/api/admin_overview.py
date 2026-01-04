from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Item

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/admin/overview")
def overview(request: Request, db: Session = Depends(get_db)):
    items = db.query(Item).all()
    return {
        "total": len(items),
        "sell": len([i for i in items if i.decision == "SELL"]),
        "stop": len([i for i in items if i.decision == "STOP"]),
    }
