from fastapi import FastAPI
from monitor_api import router as monitor_router

app = FastAPI()
app.include_router(monitor_router, prefix="/api")

# Serve the static assets (JS, CSS, etc.)
app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

# Serve index.html for root path
@app.get("/")
def root():
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info", root_path="/")
