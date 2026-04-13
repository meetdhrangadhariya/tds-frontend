"""
TDS Challan Extractor — Frontend Proxy
Public Hugging Face Space
Forwards all requests to the private backend, adding the secret token.
"""

import os
import httpx
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List

app = FastAPI()

# ── CORS (allow tsblack.in to call this proxy) ────────────────
ALLOWED_ORIGINS = [
    "https://tsblack.in",
    "https://www.tsblack.in",
    "http://localhost:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ────────────────────────────────────────────────────
# Set these as Secrets in your HF Space settings:
#   HF_TOKEN  — same token used in backend
#   BACKEND_URL — your private space URL e.g. https://meetsoni7-tds-backend.hf.space
BACKEND = os.environ.get("BACKEND_URL", "").rstrip("/")
TOKEN   = os.environ.get("HF_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ── Serve frontend HTML ───────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    try:
        return open("tds-challan-extractor.html", encoding="utf-8").read()
    except FileNotFoundError:
        return HTMLResponse("<h2>Frontend HTML file not found.</h2>", status_code=500)

# ── Health check ─────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}

# ── Proxy: parse PDFs ─────────────────────────────────────────
@app.post("/api/parse")
async def parse(files: List[UploadFile] = File(...)):
    if not BACKEND:
        return JSONResponse({"detail": "BACKEND_URL not configured"}, status_code=500)
    file_tuples = []
    for f in files:
        data = await f.read()
        file_tuples.append(("files", (f.filename, data, f.content_type or "application/pdf")))
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{BACKEND}/api/parse", files=file_tuples, headers=HEADERS)
    return JSONResponse(resp.json(), status_code=resp.status_code)

# ── Proxy: export Excel ───────────────────────────────────────
@app.post("/api/export")
async def export(files: List[UploadFile] = File(...)):
    if not BACKEND:
        return JSONResponse({"detail": "BACKEND_URL not configured"}, status_code=500)
    file_tuples = []
    for f in files:
        data = await f.read()
        file_tuples.append(("files", (f.filename, data, f.content_type or "application/pdf")))
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{BACKEND}/api/export", files=file_tuples, headers=HEADERS)
    if resp.status_code != 200:
        return JSONResponse({"detail": "Export failed"}, status_code=resp.status_code)
    cd = resp.headers.get("Content-Disposition", 'attachment; filename="TDS_Output.xlsx"')
    return StreamingResponse(
        iter([resp.content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd}
    )

# ── Proxy: interest simulator ─────────────────────────────────
@app.post("/api/simulate-interest")
async def simulate(request: Request):
    if not BACKEND:
        return JSONResponse({"detail": "BACKEND_URL not configured"}, status_code=500)
    body = await request.json()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BACKEND}/api/simulate-interest", json=body, headers=HEADERS)
    return JSONResponse(resp.json(), status_code=resp.status_code)
