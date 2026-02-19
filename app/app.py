from fastapi import FastAPI
from app.routers import users, events

app = FastAPI(title="Event Platform API")

app.include_router(users.router)
app.include_router(events.router)

@app.get("/")
def root():
    return {"message": "Event Platform API is running"}