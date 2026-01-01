# wd14-tagger-standalone WebUI (FastAPI)
# NOTE: You MUST edit WD14_TAGGER_CMD to point to your tagger entry.

import os
import json
import uuid
import shutil
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
WORK_DIR = APP_DIR / "_work"
WORK_DIR.mkdir(exist_ok=True)

app = FastAPI(title="wd14-tagger-standalone WebUI")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# ===== EDIT THIS =====
WD14_TAGGER_CMD = ["python3", "run.py"]

def safe_rm(p: Path):
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)

def run_tagger_on_folder(input_dir: Path, output_dir: Path, threshold: float = 0.35, append_tag: str = ""):
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = list(WD14_TAGGER_CMD)
    cli = [
        "--dir", str(input_dir),
        "--threshold", str(threshold),
        "--recursive",
        "--model", "wd-v1-4-convnext-tagger.v3",
        "--append_tag", str(append_tag),
    ]
    cmd += cli
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def collect_txt_results(output_dir: Path) -> Dict[str, str]:
    results = {}
    for p in output_dir.rglob("*.txt"):
        results[p.relative_to(output_dir).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
    return results

@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")

@app.post("/api/tag_upload")
async def tag_upload(files: List[UploadFile] = File(...), threshold: float = Form(0.35), append_tag: str = Form(...)):
    job_id = uuid.uuid4().hex
    job_dir = WORK_DIR / job_id
    in_dir = job_dir / "in"
    out_dir = job_dir / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in files:
        if Path(f.filename).suffix.lower() not in [".png",".jpg",".jpeg",".webp",".bmp"]:
            continue
        (in_dir / Path(f.filename).name).write_bytes(await f.read())
        saved += 1
    if saved == 0:
        safe_rm(job_dir)
        return JSONResponse({"ok": False, "error": "No valid images uploaded."}, status_code=400)
    proc = run_tagger_on_folder(in_dir, out_dir, threshold, append_tag )
    return {"ok": proc.returncode == 0, "job_id": job_id, "returncode": proc.returncode, "log": proc.stdout[-20000:], "captions": collect_txt_results(out_dir)}

@app.post("/api/tag_folder")
def tag_folder(folder_path: str = Form(...), threshold: float = Form(0.35), append_tag: str = Form(...)):
    folder = Path(folder_path).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        return JSONResponse({"ok": False, "error": f"Folder not found: {folder}"}, status_code=400)
    job_id = uuid.uuid4().hex
    job_dir = WORK_DIR / job_id
    out_dir = job_dir / "in"
    job_dir.mkdir(parents=True, exist_ok=True)
    proc = run_tagger_on_folder(folder, out_dir, threshold, append_tag)
    return {"ok": proc.returncode == 0, "job_id": job_id, "returncode": proc.returncode, "log": proc.stdout[-20000:], "captions": collect_txt_results(out_dir)}

@app.get("/api/download_zip/{job_id}")
def download_zip(job_id: str):
    out_dir = WORK_DIR / job_id / "in"
    if not out_dir.exists():
        return JSONResponse({"ok": False, "error": "job not found"}, status_code=404)
    zip_path = WORK_DIR / job_id / "result.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        print(out_dir)
        for p in out_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(out_dir).as_posix())
    return FileResponse(str(zip_path), filename=f"wd14_result_{job_id}.zip")
