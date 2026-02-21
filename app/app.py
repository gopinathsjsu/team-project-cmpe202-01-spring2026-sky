from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.routers import users, events
from . import models  # noqa: F401
from .database import engine, Base

app = FastAPI(title="Event Platform API")
Base.metadata.create_all(bind=engine)
print(Base.metadata.tables.keys())
app.include_router(users.router)
app.include_router(events.router)

@app.get("/")
def root():
    return {"message": "Event Platform API is running"}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).fetchone()
    return {"database_response": result[0]}
