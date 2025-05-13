from fastapi import FastAPI
from monitor_api import router as monitor_router

app = FastAPI()
app.include_router(monitor_router, prefix="/api")
