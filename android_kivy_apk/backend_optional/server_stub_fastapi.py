"""
Backend opcional para a próxima etapa de nuvem real.
Execute fora do APK, em servidor: pip install fastapi uvicorn
uvicorn server_stub_fastapi:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI(title="Treino Pro Max Cloud API")
FAKE_DB = {}

class SyncPayload(BaseModel):
    email: str
    data: Dict[str, Any]

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/sync/upload")
def upload(payload: SyncPayload):
    FAKE_DB[payload.email] = payload.data
    return {"ok": True, "message": "Backup recebido"}

@app.get("/sync/download/{email}")
def download(email: str):
    return {"ok": True, "data": FAKE_DB.get(email, {})}

@app.post("/payments/pix")
def create_pix(payload: Dict[str, Any]):
    return {"ok": True, "status": "simulado", "pix_copia_cola": "000201...PIX_SIMULADO"}
