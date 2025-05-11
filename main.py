from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
from pathlib import Path

app = FastAPI()
config_path = Path("config.json")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/config")
async def get_config():
    with config_path.open() as f:
        return json.load(f)


@app.post("/api/config")
async def save_config(request: Request):
    data = await request.json()
    with config_path.open("w") as f:
        json.dump(data, f, indent=2)
    return {"status": "ok"}
