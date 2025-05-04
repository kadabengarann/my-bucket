from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import uuid
from pathlib import Path

UPLOAD_DIR = Path("storage")
MAPPING_FILE = Path("file_map.json")
UPLOAD_DIR.mkdir(exist_ok=True)

API_TOKEN = os.getenv("API_TOKEN")

app = FastAPI()

app.get("/")(lambda: {"message": "Success"})

app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

if MAPPING_FILE.exists():
    with open(MAPPING_FILE, "r") as f:
        file_map = json.load(f)
else:
    file_map = {}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    alias: str = Form(None),
    x_token: str = Header(...)
):
    if x_token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")

    if not alias:
        alias = uuid.uuid4().hex[:8]
    ext = os.path.splitext(file.filename)[1]
    filename = f"{alias}{ext}"
    file_path = UPLOAD_DIR / filename

    try:
        if alias in file_map:
            old_filename = file_map[alias]
            old_path = UPLOAD_DIR / old_filename
            if old_path.exists() and old_filename != filename:
                old_path.unlink()

        with open(file_path, "wb") as f:
            f.write(await file.read())

        file_map[alias] = filename
        with open(MAPPING_FILE, "w") as f:
            json.dump(file_map, f, indent=2)

        return {
            "status": "uploaded",
            "alias": alias,
            "url": f"/f/{alias}",
            "original_name": file.filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/f/{alias}")
def get_file_by_alias(alias: str):
    filename = file_map.get(alias)
    if not filename:
        raise HTTPException(status_code=404, detail="Alias not found")
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get("/list")
def list_files():
    files = []
    total_size = 0
    for alias, name in file_map.items():
        path = UPLOAD_DIR / name
        size = path.stat().st_size if path.exists() else 0
        total_size += size
        files.append({
            "alias": alias,
            "filename": name,
            "url": f"/f/{alias}",
            "size_bytes": size
        })
    total_size_mb = round(total_size / (1024 * 1024), 2)
    return JSONResponse({
        "total_size_bytes": total_size,
        "total_size_mb": total_size_mb,
        "files": files
    })

@app.delete("/delete/{alias}")
def delete_file(alias: str, x_token: str = Header(...)):
    if x_token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")

    filename = file_map.get(alias)
    if not filename:
        raise HTTPException(status_code=404, detail="Alias not found")
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
    file_map.pop(alias, None)
    with open(MAPPING_FILE, "w") as f:
        json.dump(file_map, f, indent=2)
    return {"status": "deleted", "alias": alias, "filename": filename}
