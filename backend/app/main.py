from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.routers.api import router

app = FastAPI(title="综测星轨 Zongce Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    init_db()


upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)

app.include_router(router)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")
