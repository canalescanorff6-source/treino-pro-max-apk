# Nuvem pessoal do Treino Pro Max v4

Servidor opcional para guardar backup do app sem pagamento/assinatura.

## Rodar no PC

```bash
cd backend_personal_cloud
pip install -r requirements.txt
set TREINO_CLOUD_TOKEN=meu-token-seguro
uvicorn server:app --host 0.0.0.0 --port 8000
```

No Linux/macOS:

```bash
export TREINO_CLOUD_TOKEN=meu-token-seguro
uvicorn server:app --host 0.0.0.0 --port 8000
```

No app, use:

- API URL: `http://IP_DO_PC:8000`
- Token: o mesmo token configurado no servidor

Para uso só pessoal, também pode usar apenas o backup JSON local e guardar no Google Drive manualmente.
