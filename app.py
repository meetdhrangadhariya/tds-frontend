"""
TDS Challan Extractor — Frontend Proxy (Public HF Space)
Forwards all requests to the private backend, adding the secret token.

Routes
------
  GET  /                       — serve tds-challan-extractor.html
  GET  /health
  POST /api/parse              — PDF challan parse  → backend /api/parse
  POST /api/export             — PDF challan export → backend /api/export
  POST /api/simulate-interest  — interest calc      → backend /api/simulate-interest
  POST /api/tds/parse          — Dot TDS parse      → backend /api/tds/parse
  POST /api/tds/export         — Dot TDS export     → backend /api/tds/export
  POST /api/form16/extract     — Form 16A extract   → backend /api/form16/extract
  POST /api/form16/export      — Form 16A export    → backend /api/form16/export
"""

import os
import httpx
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List

app = FastAPI()

# ── CORS ─────────────────────────────────────────────────────────
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

# ── Config (set as HF Space Secrets) ─────────────────────────────
# BACKEND_URL  — private space URL e.g. https://meetsoni7-tds-backend.hf.space
# HF_TOKEN     — same bearer token used in backend
BACKEND = os.environ.get("BACKEND_URL", "").rstrip("/")
TOKEN   = os.environ.get("HF_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

async def _read_files(files: List[UploadFile], content_type: str = "application/octet-stream"):
    """Read uploaded files into (name, bytes, mime) tuples."""
    tuples = []
    for f in files:
        data = await f.read()
        tuples.append(("files", (f.filename, data, f.content_type or content_type)))
    return tuples


def _no_backend():
    return JSONResponse({"detail": "BACKEND_URL not configured"}, status_code=500)


# ─────────────────────────────────────────────────────────────────
# SERVE FRONTEND HTML
# ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    try:
        return open("tds-challan-extractor.html", encoding="utf-8").read()
    except FileNotFoundError:
        return HTMLResponse("<h2>Frontend HTML file not found.</h2>", status_code=500)


# ─────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "TDS Challan Extractor Frontend"}


# ─────────────────────────────────────────────────────────────────
# TOOL 1 — TDS CHALLAN EXTRACTOR (PDF)
# ─────────────────────────────────────────────────────────────────

@app.post("/api/parse")
async def parse(files: List[UploadFile] = File(...)):
    if not BACKEND:
        return _no_backend()
    tuples = await _read_files(files, "application/pdf")
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{BACKEND}/api/parse", files=tuples, headers=HEADERS)
    return JSONResponse(resp.json(), status_code=resp.status_code)


@app.post("/api/export")
async def export(files: List[UploadFile] = File(...)):
    if not BACKEND:
        return _no_backend()
    tuples = await _read_files(files, "application/pdf")
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{BACKEND}/api/export", files=tuples, headers=HEADERS)
    if resp.status_code != 200:
        return JSONResponse({"detail": "Export failed"}, status_code=resp.status_code)
    cd = resp.headers.get("Content-Disposition", 'attachment; filename="TDS_Output.xlsx"')
    return StreamingResponse(
        iter([resp.content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd},
    )


# ─────────────────────────────────────────────────────────────────
# TOOL 2 — DOT TDS EXTRACTOR (.tds files)
# ─────────────────────────────────────────────────────────────────

@app.post("/api/tds/parse")
async def tds_parse(files: List[UploadFile] = File(...)):
    """Proxy .tds file parse requests to the private backend."""
    if not BACKEND:
        return _no_backend()
    tuples = await _read_files(files, "application/octet-stream")
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{BACKEND}/api/tds/parse", files=tuples, headers=HEADERS)
    return JSONResponse(resp.json(), status_code=resp.status_code)


@app.post("/api/tds/export")
async def tds_export(files: List[UploadFile] = File(...)):
    """Proxy .tds file export requests to the private backend."""
    if not BACKEND:
        return _no_backend()
    tuples = await _read_files(files, "application/octet-stream")
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(f"{BACKEND}/api/tds/export", files=tuples, headers=HEADERS)
    if resp.status_code != 200:
        return JSONResponse({"detail": "TDS export failed"}, status_code=resp.status_code)
    cd = resp.headers.get("Content-Disposition", 'attachment; filename="DotTDS_Export.xlsx"')
    return StreamingResponse(
        iter([resp.content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd},
    )


# ─────────────────────────────────────────────────────────────────
# TOOL 3 — TDS INTEREST CALCULATOR
# ─────────────────────────────────────────────────────────────────

@app.post("/api/simulate-interest")
async def simulate(request: Request):
    if not BACKEND:
        return _no_backend()
    body = await request.json()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BACKEND}/api/simulate-interest", json=body, headers=HEADERS
        )
    return JSONResponse(resp.json(), status_code=resp.status_code)


# ─────────────────────────────────────────────────────────────────
# TOOL 2 — FORM 16A EXTRACTOR
# ─────────────────────────────────────────────────────────────────

@app.post("/api/form16/extract")
async def form16_extract(files: List[UploadFile] = File(...)):
    """Proxy Form 16A PDF extract requests to the private backend."""
    if not BACKEND:
        return _no_backend()
    tuples = await _read_files(files, "application/pdf")
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{BACKEND}/api/form16/extract", files=tuples, headers=HEADERS)
    return JSONResponse(resp.json(), status_code=resp.status_code)


@app.post("/api/form16/export")
async def form16_export(files: List[UploadFile] = File(...)):
    """Proxy Form 16A PDF export requests to the private backend."""
    if not BACKEND:
        return _no_backend()
    tuples = await _read_files(files, "application/pdf")
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{BACKEND}/api/form16/export", files=tuples, headers=HEADERS)
    if resp.status_code != 200:
        return JSONResponse({"detail": "Form 16A export failed"}, status_code=resp.status_code)
    cd = resp.headers.get("Content-Disposition", 'attachment; filename="Form16A_Export.xlsx"')
    return StreamingResponse(
        iter([resp.content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": cd},
    )
