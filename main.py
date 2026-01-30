from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api import simulator, audit
from pathlib import Path
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root directory for path resolution
ROOT_DIR = Path(__file__).parent

# Mount static files
app.mount("/static", StaticFiles(directory=ROOT_DIR / "app" / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=ROOT_DIR / "app" / "templates")

app.include_router(simulator.router)
app.include_router(audit.router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/audit", response_class=HTMLResponse)
async def read_audit(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)