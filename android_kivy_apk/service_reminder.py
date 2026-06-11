# -*- coding: utf-8 -*-
"""Serviço Android opcional para lembretes.
Funciona como base para notificações com app fechado. Em alguns aparelhos Android,
o sistema pode limitar serviços em segundo plano; use também as permissões de bateria.
"""
import os, sqlite3, time
from datetime import datetime
try:
    from plyer import notification
except Exception:
    notification = None

APP = "Treino Pro Max"
DB = "treino_pro_max_v4.db"


def notify(title, message):
    if notification:
        try:
            notification.notify(title=title, message=message, app_name=APP, timeout=5)
        except Exception:
            pass


def find_db():
    bases = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    for b in bases:
        p = os.path.join(b, "data", DB)
        if os.path.exists(p):
            return p
    return None

last_sent = {}
while True:
    try:
        db = find_db()
        now = datetime.now()
        if db:
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM reminders WHERE active=1").fetchall()
            conn.close()
            for r in rows:
                hour = (r["hour"] or "").strip()
                key = f"{r['id']}-{now.strftime('%Y-%m-%d')}"
                if hour == now.strftime("%H:%M") and last_sent.get(key) != hour:
                    notify(r["title"] or "Lembrete de treino", "Hora de cuidar do treino, alimentação ou descanso.")
                    last_sent[key] = hour
        # lembrete leve padrão a cada 4h, só se nenhum lembrete bater
        if now.minute == 0 and now.hour in (8, 12, 16, 20):
            k = f"padrao-{now.strftime('%Y-%m-%d-%H')}"
            if k not in last_sent:
                notify(APP, "Confira seu treino, água e alimentação de hoje.")
                last_sent[k] = "ok"
    except Exception:
        pass
    time.sleep(60)
