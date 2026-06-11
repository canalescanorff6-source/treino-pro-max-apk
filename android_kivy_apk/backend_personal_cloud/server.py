# -*- coding: utf-8 -*-
"""Backend pessoal opcional do Treino Pro Max v4.
Rode em um PC/VPS/RunSite para guardar backups JSON do app.
Não tem pagamento, não tem assinatura. É só nuvem pessoal.
"""
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import json, os

TOKEN = os.getenv("TREINO_CLOUD_TOKEN", "troque-este-token")
DATA_DIR = Path(os.getenv("TREINO_CLOUD_DATA", "cloud_backups"))
DATA_DIR.mkdir(exist_ok=True)
app = FastAPI(title="Treino Pro Max Personal Cloud")

class BackupPayload(BaseModel):
    user_email: str
    backup: dict


def check(auth: str | None):
    if auth != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido")

@app.get("/health")
def health():
    return {"ok": True, "app": "Treino Pro Max Personal Cloud"}

@app.post("/sync/upload")
def upload(payload: BackupPayload, authorization: str | None = Header(default=None)):
    check(authorization)
    safe_email = payload.user_email.replace("@", "_at_").replace("/", "_")
    path = DATA_DIR / f"{safe_email}.json"
    content = {"updated_at": datetime.utcnow().isoformat(), "user_email": payload.user_email, "backup": payload.backup}
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "saved": str(path), "updated_at": content["updated_at"]}

@app.get("/sync/download/{user_email}")
def download(user_email: str, authorization: str | None = Header(default=None)):
    check(authorization)
    safe_email = user_email.replace("@", "_at_").replace("/", "_")
    path = DATA_DIR / f"{safe_email}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    return json.loads(path.read_text(encoding="utf-8"))
