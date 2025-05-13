from fastapi import FastAPI
from monitor_api import router as monitor_router

app = FastAPI()
app.include_router(monitor_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info", root_path="/")
