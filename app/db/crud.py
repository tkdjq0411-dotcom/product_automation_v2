from sqlalchemy.orm import Session
from .models import Item

def create_item(db: Session, data: dict):
    item = Item(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def get_items(db: Session):
    return db.query(Item).all()

def delete_item(db: Session, item_id: int):
    item = db.query(Item).get(item_id)
    if item:
        db.delete(item)
        db.commit()
