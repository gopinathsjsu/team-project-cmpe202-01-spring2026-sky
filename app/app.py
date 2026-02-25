from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.routers import users, events, authentication, RSVP, admin
from . import models  # noqa: F401
from .database import engine, Base
from mangum import Mangum

load_dotenv()

app = FastAPI(title="Event Platform API")
handler = Mangum(app)
Base.metadata.create_all(bind=engine)

app.include_router(users.router)
app.include_router(events.router)
app.include_router(authentication.router)
app.include_router(RSVP.router)
app.include_router(admin.router)


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
    result = db.execute(text("SELECT 1")).scalar_one_or_none()
    return {"database_response": result}
