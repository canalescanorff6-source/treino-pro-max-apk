# -*- coding: utf-8 -*-
"""
Treino Pro Max v4.1
Aplicativo Android em Python/Kivy com recursos estilo app pago: login local,
perfil, gerador de treino, timer, histórico, gráficos, alimentação, fotos,
modo personal trainer, exportação, nuvem pessoal opcional, mídia de exercícios
e notificações avançadas. Sem pagamento/assinatura.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import random
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle, Rectangle
from kivy.metrics import dp
from kivy.properties import DictProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

try:
    from plyer import notification, vibrator, camera, filechooser
except Exception:  # desktop fallback
    notification = None
    vibrator = None
    camera = None
    filechooser = None

Window.clearcolor = (0.035, 0.055, 0.085, 1)
APP_NAME = "Treino Pro Max"
DB_NAME = "treino_pro_max_v4_1.db"
VERSION = "4.1.0"


# -----------------------------------------------------------------------------
# Helpers visuais
# -----------------------------------------------------------------------------

class Theme:
    bg = (0.035, 0.055, 0.085, 1)
    panel = (0.055, 0.085, 0.13, 1)
    panel2 = (0.075, 0.115, 0.17, 1)
    accent = (0.0, 0.82, 0.74, 1)
    accent2 = (0.15, 0.52, 1.0, 1)
    warn = (1.0, 0.74, 0.20, 1)
    danger = (1.0, 0.25, 0.28, 1)
    ok = (0.25, 0.90, 0.45, 1)
    text = (0.94, 0.97, 1.0, 1)
    muted = (0.63, 0.72, 0.78, 1)


class Card(BoxLayout):
    def __init__(self, radius=18, bg=None, pad=12, **kwargs):
        super().__init__(**kwargs)
        self.padding = dp(pad)
        self.spacing = dp(8)
        self.bg = bg or Theme.panel
        self.radius = radius
        with self.canvas.before:
            Color(*self.bg)
            self.rect = RoundedRectangle(radius=[dp(self.radius)], pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *_):
        self.rect.pos = self.pos
        self.rect.size = self.size


class Title(Label):
    def __init__(self, text="", size=22, **kwargs):
        super().__init__(text=text, color=Theme.text, bold=True, font_size=dp(size), **kwargs)
        self.halign = "left"
        self.valign = "middle"
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))


class Muted(Label):
    def __init__(self, text="", size=14, **kwargs):
        super().__init__(text=text, color=Theme.muted, font_size=dp(size), **kwargs)
        self.halign = "left"
        self.valign = "middle"
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))


class Body(Label):
    def __init__(self, text="", size=15, **kwargs):
        super().__init__(text=text, color=Theme.text, font_size=dp(size), **kwargs)
        self.halign = "left"
        self.valign = "middle"
        self.bind(size=lambda *_: setattr(self, "text_size", self.size))


class Pill(Button):
    def __init__(self, text="", bg=None, **kwargs):
        super().__init__(text=text, **kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = bg or Theme.accent
        self.color = (0.02, 0.04, 0.06, 1)
        self.bold = True
        self.font_size = dp(14)
        self.size_hint_y = None
        self.height = dp(44)


class GhostButton(Button):
    def __init__(self, text="", **kwargs):
        super().__init__(text=text, **kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = Theme.panel2
        self.color = Theme.text
        self.bold = True
        self.font_size = dp(14)
        self.size_hint_y = None
        self.height = dp(44)


class Input(TextInput):
    def __init__(self, hint_text="", **kwargs):
        super().__init__(hint_text=hint_text, **kwargs)
        self.background_normal = ""
        self.background_active = ""
        self.background_color = Theme.panel2
        self.foreground_color = Theme.text
        self.hint_text_color = Theme.muted
        self.cursor_color = Theme.accent
        self.multiline = False
        self.padding = [dp(12), dp(11)]
        self.size_hint_y = None
        self.height = dp(46)
        self.font_size = dp(15)


def toast(msg: str, title="Aviso"):
    box = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
    box.add_widget(Body(msg))
    btn = Pill("OK")
    box.add_widget(btn)
    pop = Popup(title=title, content=box, size_hint=(0.88, None), height=dp(230), auto_dismiss=True)
    btn.bind(on_release=pop.dismiss)
    pop.open()


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_iso():
    return date.today().isoformat()


def safe_float(v, default=0.0):
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        return int(float(str(v).replace(",", ".")))
    except Exception:
        return default


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# Banco local + estrutura para nuvem/API
# -----------------------------------------------------------------------------

class Store:
    def __init__(self, root: Path):
        self.root = root
        self.data_dir = root / "data"
        self.exports_dir = root / "exports"
        self.photos_dir = root / "photos"
        self.assets_dir = root / "assets"
        for p in [self.data_dir, self.exports_dir, self.photos_dir, self.assets_dir]:
            p.mkdir(exist_ok=True, parents=True)
        self.db_path = self.data_dir / DB_NAME
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.init_db()
        self.seed_defaults()

    def init_db(self):
        c = self.conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT UNIQUE, password_hash TEXT,
                security_answer_hash TEXT, created_at TEXT, is_pro INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS profile(
                user_id INTEGER PRIMARY KEY, age INTEGER, height_cm REAL, weight_kg REAL,
                objective TEXT, level TEXT, body_type TEXT, days_per_week INTEGER,
                max_minutes INTEGER, equipment TEXT, injuries TEXT, priority_muscle TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS workouts(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT, day_name TEXT,
                focus TEXT, max_minutes INTEGER, created_at TEXT, is_template INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS workout_exercises(
                id INTEGER PRIMARY KEY AUTOINCREMENT, workout_id INTEGER, exercise_id TEXT,
                name TEXT, muscle TEXT, sets INTEGER, reps TEXT, rest_seconds INTEGER,
                suggested_weight REAL, set_type TEXT, order_index INTEGER
            );
            CREATE TABLE IF NOT EXISTS workout_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, workout_id INTEGER,
                exercise_id TEXT, exercise_name TEXT, log_date TEXT, set_number INTEGER,
                weight REAL, reps INTEGER, rpe REAL, set_type TEXT, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS body_measurements(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, measure_date TEXT,
                weight_kg REAL, chest_cm REAL, waist_cm REAL, arm_cm REAL,
                thigh_cm REAL, bodyfat_percent REAL, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS meals(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, meal_date TEXT,
                name TEXT, calories REAL, protein REAL, carbs REAL, fat REAL, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS progress_photos(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, photo_date TEXT,
                angle TEXT, path TEXT, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS reminders(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT,
                kind TEXT, hour TEXT, weekdays TEXT, active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS students(
                id INTEGER PRIMARY KEY AUTOINCREMENT, trainer_user_id INTEGER, name TEXT,
                phone TEXT, objective TEXT, level TEXT, notes TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS student_workouts(
                id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, workout_text TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS cloud_settings(
                user_id INTEGER PRIMARY KEY, api_url TEXT, access_token TEXT, auto_sync INTEGER DEFAULT 0, last_sync TEXT
            );
            CREATE TABLE IF NOT EXISTS exercise_media(
                id INTEGER PRIMARY KEY AUTOINCREMENT, exercise_id TEXT, title TEXT, local_path TEXT, video_url TEXT, notes TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS health_records(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, record_date TEXT, steps INTEGER, sleep_hours REAL, resting_hr INTEGER, calories_burned REAL, source TEXT, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS app_settings(
                key TEXT PRIMARY KEY, value TEXT
            );
            CREATE TABLE IF NOT EXISTS remote_content_cache(
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_url TEXT, content_type TEXT,
                json_text TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS session_feedback(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, feedback_date TEXT,
                workout_id INTEGER, rating TEXT, energy INTEGER, pain_area TEXT, pain_level INTEGER,
                duration_minutes INTEGER, notes TEXT
            );
            CREATE TABLE IF NOT EXISTS smart_alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, alert_date TEXT,
                kind TEXT, message TEXT, severity TEXT, done INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS remote_workout_versions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, version_name TEXT,
                json_text TEXT, applied_at TEXT
            );
            """
        )
        self.conn.commit()

    def seed_defaults(self):
        cur = self.conn.execute("SELECT COUNT(*) as n FROM users")
        if cur.fetchone()["n"] == 0:
            self.create_user("Luis", "luis@app.local", "123456", "academia")
        user = self.get_user_by_email("luis@app.local")
        if user and not self.get_profile(user["id"]):
            self.save_profile(user["id"], {
                "age": 25, "height_cm": 170, "weight_kg": 65, "objective": "Hipertrofia e ganho de massa",
                "level": "Voltando após pausa", "body_type": "Ectomorfo", "days_per_week": 3,
                "max_minutes": 90, "equipment": "Academia completa", "injuries": "Nenhuma informada",
                "priority_muscle": "Geral"
            })
        if user and self.conn.execute("SELECT COUNT(*) as n FROM workouts WHERE user_id=?", (user["id"],)).fetchone()["n"] == 0:
            self.create_default_workouts(user["id"])

    def create_user(self, name, email, password, answer) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO users(name,email,password_hash,security_answer_hash,created_at,is_pro) VALUES(?,?,?,?,?,1)",
                (name.strip(), email.strip().lower(), sha(password), sha(answer.strip().lower()), now_iso()),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user_by_email(self, email):
        return self.conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()

    def login(self, email, password):
        user = self.get_user_by_email(email)
        if user and user["password_hash"] == sha(password):
            return user
        return None

    def reset_password(self, email, answer, new_password):
        user = self.get_user_by_email(email)
        if user and user["security_answer_hash"] == sha(answer.strip().lower()):
            self.conn.execute("UPDATE users SET password_hash=? WHERE id=?", (sha(new_password), user["id"]))
            self.conn.commit()
            return True
        return False

    def save_profile(self, user_id: int, d: Dict[str, Any]):
        self.conn.execute(
            """INSERT OR REPLACE INTO profile(user_id,age,height_cm,weight_kg,objective,level,body_type,days_per_week,
            max_minutes,equipment,injuries,priority_muscle,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, safe_int(d.get("age")), safe_float(d.get("height_cm")), safe_float(d.get("weight_kg")),
             d.get("objective", ""), d.get("level", ""), d.get("body_type", ""), safe_int(d.get("days_per_week",3)),
             safe_int(d.get("max_minutes",90)), d.get("equipment", ""), d.get("injuries", ""), d.get("priority_muscle", ""), now_iso())
        )
        self.conn.commit()

    def get_profile(self, user_id):
        return self.conn.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()

    def create_default_workouts(self, user_id: int):
        templates = [
            ("Segunda - Peito, Ombro e Tríceps", "Segunda", "Peito/Ombro/Tríceps", [
                ("EX0001", "Supino reto com barra", "Peito", 4, "8-12", 90, 12, "normal"),
                ("EX0002", "Supino inclinado com halteres", "Peito", 3, "8-12", 90, 14, "normal"),
                ("EX0003", "Crucifixo no peck deck", "Peito", 3, "10-12", 60, 25, "normal"),
                ("EX0004", "Desenvolvimento com halteres", "Ombros", 3, "8-12", 90, 12, "normal"),
                ("EX0005", "Elevação lateral", "Ombros", 3, "12-15", 60, 6, "normal"),
                ("EX0006", "Tríceps na polia", "Tríceps", 3, "10-12", 60, 25, "normal"),
                ("EX0007", "Tríceps francês", "Tríceps", 2, "10-12", 60, 16, "normal"),
            ]),
            ("Quarta - Costas e Bíceps", "Quarta", "Costas/Bíceps", [
                ("EX0008", "Puxada alta frente", "Costas", 4, "8-12", 90, 40, "normal"),
                ("EX0009", "Remada baixa", "Costas", 4, "8-12", 90, 40, "normal"),
                ("EX0010", "Remada unilateral com halter", "Costas", 3, "10-12", 75, 20, "unilateral"),
                ("EX0011", "Pulldown braço reto", "Costas", 3, "10-12", 60, 25, "normal"),
                ("EX0012", "Rosca direta", "Bíceps", 3, "8-12", 75, 10, "normal"),
                ("EX0013", "Rosca alternada", "Bíceps", 3, "10-12", 60, 10, "unilateral"),
                ("EX0014", "Rosca martelo", "Bíceps", 2, "10-12", 60, 10, "normal"),
            ]),
            ("Sexta - Pernas e Abdômen", "Sexta", "Pernas/Abdômen", [
                ("EX0015", "Agachamento livre", "Pernas", 4, "8-12", 120, 15, "normal"),
                ("EX0016", "Leg press", "Pernas", 4, "10-12", 90, 100, "normal"),
                ("EX0017", "Cadeira extensora", "Pernas", 3, "10-12", 60, 35, "normal"),
                ("EX0018", "Mesa flexora", "Posterior", 3, "10-12", 60, 30, "normal"),
                ("EX0019", "Stiff", "Posterior", 3, "8-12", 90, 20, "normal"),
                ("EX0020", "Panturrilha em pé", "Panturrilha", 4, "12-20", 60, 40, "normal"),
                ("EX0021", "Prancha", "Abdômen", 3, "30-60s", 45, 0, "tempo"),
            ]),
        ]
        for name, day, focus, items in templates:
            wid = self.add_workout(user_id, name, day, focus, 90)
            for order, it in enumerate(items, 1):
                self.conn.execute(
                    """INSERT INTO workout_exercises(workout_id,exercise_id,name,muscle,sets,reps,rest_seconds,suggested_weight,set_type,order_index)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""", (wid, *it, order)
                )
        self.conn.commit()

    def add_workout(self, user_id, name, day_name, focus, max_minutes=90):
        cur = self.conn.execute(
            "INSERT INTO workouts(user_id,name,day_name,focus,max_minutes,created_at) VALUES(?,?,?,?,?,?)",
            (user_id, name, day_name, focus, max_minutes, now_iso())
        )
        self.conn.commit()
        return cur.lastrowid

    def get_workouts(self, user_id):
        return self.conn.execute("SELECT * FROM workouts WHERE user_id=? ORDER BY id", (user_id,)).fetchall()

    def get_workout_exercises(self, workout_id):
        return self.conn.execute("SELECT * FROM workout_exercises WHERE workout_id=? ORDER BY order_index", (workout_id,)).fetchall()

    def log_set(self, user_id, workout_id, ex, set_no, weight, reps, rpe, set_type, notes=""):
        self.conn.execute(
            """INSERT INTO workout_logs(user_id,workout_id,exercise_id,exercise_name,log_date,set_number,weight,reps,rpe,set_type,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, workout_id, ex["exercise_id"], ex["name"], now_iso(), set_no, weight, reps, rpe, set_type, notes)
        )
        self.conn.commit()

    def recent_logs(self, user_id, limit=100):
        return self.conn.execute("SELECT * FROM workout_logs WHERE user_id=? ORDER BY log_date DESC LIMIT ?", (user_id, limit)).fetchall()

    def best_weight(self, user_id, exercise_name):
        row = self.conn.execute("SELECT MAX(weight) as m FROM workout_logs WHERE user_id=? AND exercise_name=?", (user_id, exercise_name)).fetchone()
        return row["m"] or 0

    def suggest_next_weight(self, user_id, exercise_name, current_weight):
        rows = self.conn.execute(
            "SELECT weight,reps,rpe FROM workout_logs WHERE user_id=? AND exercise_name=? ORDER BY log_date DESC LIMIT 6",
            (user_id, exercise_name)
        ).fetchall()
        if len(rows) < 3:
            return current_weight, "Pouco histórico. Mantenha e foque na execução."
        avg_reps = sum(r["reps"] for r in rows) / len(rows)
        avg_rpe = sum(r["rpe"] for r in rows if r["rpe"] is not None) / max(1, len(rows))
        if avg_reps >= 11.5 and avg_rpe <= 8.5:
            inc = 2 if current_weight < 30 else 5
            return current_weight + inc, f"Aumentar {inc} kg: reps altas e RPE controlado."
        if avg_reps < 8 or avg_rpe >= 9.5:
            dec = 2 if current_weight < 30 else 5
            return max(0, current_weight - dec), f"Reduzir {dec} kg: esforço alto ou reps baixas."
        return current_weight, "Manter: zona ideal de hipertrofia."

    def export_backup(self, user_id):
        tables = ["users","profile","workouts","workout_exercises","workout_logs","body_measurements","meals","progress_photos","reminders","students","student_workouts","app_settings","remote_content_cache","session_feedback","smart_alerts","remote_workout_versions","exercise_media","health_records","cloud_settings"]
        data = {"version": VERSION, "exported_at": now_iso(), "tables": {}}
        for t in tables:
            rows = [dict(r) for r in self.conn.execute(f"SELECT * FROM {t}").fetchall()]
            data["tables"][t] = rows
        path = self.exports_dir / f"backup_treino_pro_{date.today().isoformat()}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def export_csv(self, user_id):
        path = self.exports_dir / f"historico_treino_{date.today().isoformat()}.csv"
        rows = self.recent_logs(user_id, 10000)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["data","exercicio","serie","peso","reps","rpe","tipo","obs"])
            for r in rows:
                w.writerow([r["log_date"], r["exercise_name"], r["set_number"], r["weight"], r["reps"], r["rpe"], r["set_type"], r["notes"]])
        return path

    def add_measurement(self, user_id, d):
        self.conn.execute(
            """INSERT INTO body_measurements(user_id,measure_date,weight_kg,chest_cm,waist_cm,arm_cm,thigh_cm,bodyfat_percent,notes)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (user_id, today_iso(), safe_float(d.get("weight")), safe_float(d.get("chest")), safe_float(d.get("waist")), safe_float(d.get("arm")), safe_float(d.get("thigh")), safe_float(d.get("bf")), d.get("notes",""))
        )
        self.conn.commit()

    def measurements(self, user_id):
        return self.conn.execute("SELECT * FROM body_measurements WHERE user_id=? ORDER BY measure_date", (user_id,)).fetchall()

    def add_meal(self, user_id, d):
        self.conn.execute(
            "INSERT INTO meals(user_id,meal_date,name,calories,protein,carbs,fat,notes) VALUES(?,?,?,?,?,?,?,?)",
            (user_id, today_iso(), d.get("name","Refeição"), safe_float(d.get("cal")), safe_float(d.get("prot")), safe_float(d.get("carb")), safe_float(d.get("fat")), d.get("notes",""))
        )
        self.conn.commit()

    def meals_today(self, user_id):
        return self.conn.execute("SELECT * FROM meals WHERE user_id=? AND meal_date=? ORDER BY id DESC", (user_id, today_iso())).fetchall()

    def add_photo(self, user_id, angle, src_path, notes=""):
        src = Path(src_path)
        dst = self.photos_dir / f"foto_{user_id}_{int(time.time())}_{src.name}"
        try:
            shutil.copy(str(src), str(dst))
        except Exception:
            dst.write_text("Arquivo de foto não copiado no ambiente atual.", encoding="utf-8")
        self.conn.execute("INSERT INTO progress_photos(user_id,photo_date,angle,path,notes) VALUES(?,?,?,?,?)", (user_id, today_iso(), angle, str(dst), notes))
        self.conn.commit()
        return dst

    def photos(self, user_id):
        return self.conn.execute("SELECT * FROM progress_photos WHERE user_id=? ORDER BY photo_date DESC", (user_id,)).fetchall()

    def add_student(self, trainer_user_id, d):
        self.conn.execute("INSERT INTO students(trainer_user_id,name,phone,objective,level,notes,created_at) VALUES(?,?,?,?,?,?,?)",
                          (trainer_user_id, d.get("name",""), d.get("phone",""), d.get("objective",""), d.get("level",""), d.get("notes",""), now_iso()))
        self.conn.commit()

    def students(self, trainer_user_id):
        return self.conn.execute("SELECT * FROM students WHERE trainer_user_id=? ORDER BY id DESC", (trainer_user_id,)).fetchall()



    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO app_settings(key,value) VALUES(?,?)", (key, str(value)))
        self.conn.commit()

    def get_setting(self, key, default=""):
        row = self.conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def add_feedback(self, user_id, d):
        self.conn.execute(
            """INSERT INTO session_feedback(user_id,feedback_date,workout_id,rating,energy,pain_area,pain_level,duration_minutes,notes)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (user_id, now_iso(), safe_int(d.get("workout_id")), d.get("rating","Bom"), safe_int(d.get("energy"),5),
             d.get("pain_area","Nenhuma"), safe_int(d.get("pain_level"),0), safe_int(d.get("duration"),0), d.get("notes",""))
        )
        self.conn.commit()

    def recent_feedback(self, user_id, limit=10):
        return self.conn.execute("SELECT * FROM session_feedback WHERE user_id=? ORDER BY feedback_date DESC LIMIT ?", (user_id, limit)).fetchall()

    def save_remote_cache(self, source_url, content_type, data):
        txt = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
        self.conn.execute("INSERT INTO remote_content_cache(source_url,content_type,json_text,created_at) VALUES(?,?,?,?)", (source_url, content_type, txt, now_iso()))
        self.conn.commit()
        return txt

    def add_smart_alert(self, user_id, kind, message, severity="info"):
        self.conn.execute("INSERT INTO smart_alerts(user_id,alert_date,kind,message,severity,done) VALUES(?,?,?,?,?,0)", (user_id, now_iso(), kind, message, severity))
        self.conn.commit()

    def smart_alerts(self, user_id, limit=30):
        return self.conn.execute("SELECT * FROM smart_alerts WHERE user_id=? ORDER BY alert_date DESC LIMIT ?", (user_id, limit)).fetchall()

    def apply_remote_plan(self, user_id, payload):
        """Aplica treinos/configurações vindos do RunSite sem reinstalar APK."""
        if isinstance(payload, str):
            payload = json.loads(payload)
        applied = []
        settings = payload.get("settings", {}) or {}
        for k, v in settings.items():
            self.set_setting(k, v)
            applied.append(f"setting:{k}")
        workouts = payload.get("workouts", []) or []
        for w in workouts:
            wid = self.add_workout(user_id, w.get("name", "Treino remoto"), w.get("day", "Remoto"), w.get("focus", "Personalizado"), safe_int(w.get("max_minutes", 90)))
            for order, e in enumerate(w.get("exercises", []), 1):
                self.conn.execute("""INSERT INTO workout_exercises(workout_id,exercise_id,name,muscle,sets,reps,rest_seconds,suggested_weight,set_type,order_index)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (
                    wid, e.get("exercise_id", f"REMOTE{order}"), e.get("name", "Exercício remoto"), e.get("muscle", "Geral"),
                    safe_int(e.get("sets", 3)), str(e.get("reps", "8-12")), safe_int(e.get("rest", e.get("rest_seconds", 60))),
                    safe_float(e.get("weight", e.get("suggested_weight", 0))), e.get("set_type", "normal"), order
                ))
            applied.append(f"workout:{w.get('name','Treino remoto')}")
        self.conn.execute("INSERT INTO remote_workout_versions(user_id,version_name,json_text,applied_at) VALUES(?,?,?,?)", (user_id, payload.get("version", "remoto"), json.dumps(payload, ensure_ascii=False), now_iso()))
        self.conn.commit()
        return applied

    def add_custom_exercise_to_workout(self, workout_id, name, muscle, sets, reps, rest, weight, set_type="normal"):
        row = self.conn.execute("SELECT COALESCE(MAX(order_index),0)+1 as n FROM workout_exercises WHERE workout_id=?", (workout_id,)).fetchone()
        order = row["n"] or 1
        exid = "CUSTOM" + str(int(time.time()))
        self.conn.execute("""INSERT INTO workout_exercises(workout_id,exercise_id,name,muscle,sets,reps,rest_seconds,suggested_weight,set_type,order_index)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", (workout_id, exid, name, muscle, safe_int(sets,3), str(reps or "8-12"), safe_int(rest,60), safe_float(weight), set_type or "normal", order))
        self.conn.commit()

    def replace_exercise(self, workout_exercise_id, exercise):
        self.conn.execute("UPDATE workout_exercises SET exercise_id=?, name=?, muscle=? WHERE id=?", (exercise.get("id","REPL"), exercise.get("name","Substituto"), exercise.get("muscle","Geral"), workout_exercise_id))
        self.conn.commit()

    def weekly_report_text(self, user_id):
        since = (date.today() - timedelta(days=7)).isoformat()
        logs = self.conn.execute("SELECT * FROM workout_logs WHERE user_id=? AND substr(log_date,1,10)>=? ORDER BY log_date", (user_id, since)).fetchall()
        meals = self.conn.execute("SELECT * FROM meals WHERE user_id=? AND meal_date>=? ORDER BY meal_date", (user_id, since)).fetchall()
        feedback = self.recent_feedback(user_id, 10)
        days = sorted(set(str(r["log_date"])[:10] for r in logs))
        volume = sum((r["weight"] or 0)*(r["reps"] or 0) for r in logs)
        lines = ["RELATÓRIO SEMANAL - TREINO PRO MAX v4.1", f"Período desde {since}", f"Dias treinados: {len(days)}", f"Séries: {len(logs)}", f"Volume: {round(volume)} kg"]
        if meals:
            avg_cal = sum(r["calories"] or 0 for r in meals) / max(1, len(set(r["meal_date"] for r in meals)))
            lines.append(f"Calorias médias registradas/dia: {round(avg_cal)} kcal")
        if feedback:
            last = feedback[0]
            lines.append(f"Última avaliação: {last['rating']} • dor: {last['pain_area']} nível {last['pain_level']} • energia {last['energy']}/10")
        lines.append("\nAnálise inteligente:")
        lines.extend(smart_coach_lines(self, user_id))
        path = self.exports_dir / f"relatorio_semanal_v41_{today_iso()}.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path, "\n".join(lines)


# -----------------------------------------------------------------------------
# Dados de exercícios, gerador e calculadoras
# -----------------------------------------------------------------------------

class ExerciseRepo:
    def __init__(self, path: Path):
        self.path = path
        self.items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def search(self, term="", muscle="Todos", equipment="Todos", level="Todos"):
        term = term.lower().strip()
        out = []
        for e in self.items:
            if term and term not in e["name"].lower() and term not in e["muscle"].lower():
                continue
            if muscle != "Todos" and e["muscle"] != muscle:
                continue
            if equipment != "Todos" and e["equipment"] != equipment:
                continue
            if level != "Todos" and e["level"] != level:
                continue
            out.append(e)
        return out

    def by_muscle(self, muscle, n=4):
        arr = [e for e in self.items if e["muscle"] == muscle]
        return arr[:n] if len(arr) >= n else arr

    def get(self, ex_id):
        for e in self.items:
            if e["id"] == ex_id:
                return e
        return None


class WorkoutGenerator:
    splits = {
        2: [("Treino A - Superior", ["Peito","Costas","Ombros","Bíceps","Tríceps"]), ("Treino B - Inferior", ["Pernas","Posterior","Glúteos","Panturrilha","Abdômen"])],
        3: [("Push - Peito/Ombro/Tríceps", ["Peito","Ombros","Tríceps"]), ("Pull - Costas/Bíceps", ["Costas","Bíceps"]), ("Legs - Pernas/Abdômen", ["Pernas","Posterior","Glúteos","Panturrilha","Abdômen"])],
        4: [("Superior 1", ["Peito","Costas","Ombros"]), ("Inferior 1", ["Pernas","Posterior","Panturrilha"]), ("Superior 2", ["Costas","Peito","Bíceps","Tríceps"]), ("Inferior 2", ["Glúteos","Posterior","Pernas","Abdômen"])],
        5: [("Peito", ["Peito","Tríceps"]), ("Costas", ["Costas","Bíceps"]), ("Pernas", ["Pernas","Posterior"]), ("Ombros/Braços", ["Ombros","Bíceps","Tríceps"]), ("Glúteos/Abdômen", ["Glúteos","Panturrilha","Abdômen"])],
        6: [("Push A", ["Peito","Ombros","Tríceps"]), ("Pull A", ["Costas","Bíceps"]), ("Legs A", ["Pernas","Posterior"]), ("Push B", ["Peito","Ombros","Tríceps"]), ("Pull B", ["Costas","Bíceps"]), ("Legs B", ["Glúteos","Panturrilha","Abdômen"])]
    }

    @staticmethod
    def generate(repo: ExerciseRepo, profile: sqlite3.Row | Dict[str, Any]) -> List[Dict[str, Any]]:
        days = safe_int(profile["days_per_week"] if isinstance(profile, sqlite3.Row) else profile.get("days_per_week"), 3)
        days = max(2, min(6, days))
        max_minutes = safe_int(profile["max_minutes"] if isinstance(profile, sqlite3.Row) else profile.get("max_minutes"), 90)
        level = (profile["level"] if isinstance(profile, sqlite3.Row) else profile.get("level", "Intermediário")) or "Intermediário"
        body_type = (profile["body_type"] if isinstance(profile, sqlite3.Row) else profile.get("body_type", "")) or ""
        priority = (profile["priority_muscle"] if isinstance(profile, sqlite3.Row) else profile.get("priority_muscle", "")) or "Geral"
        result = []
        for day_idx, (name, muscles) in enumerate(WorkoutGenerator.splits[days], 1):
            if priority in muscles and priority != "Geral":
                muscles = [priority] + muscles
            exercises = []
            budget = max_minutes - 8
            total_sets = 0
            for muscle in muscles:
                per = 2 if len(muscles) <= 3 else 1
                if muscle in ["Abdômen","Panturrilha"]: per = 1
                for e in repo.by_muscle(muscle, per):
                    sets = 4 if muscle in ["Peito","Costas","Pernas"] and "Iniciante" not in level else 3
                    if "Ectomorfo" in body_type and total_sets > 18:
                        continue
                    rest = 90 if muscle in ["Peito","Costas","Pernas","Posterior"] else 60
                    est = sets * (rest + 45) / 60
                    if est <= budget:
                        exercises.append({"exercise_id": e["id"], "name": e["name"], "muscle": e["muscle"], "sets": sets, "reps": e["default_reps"], "rest": rest, "weight": 0, "set_type": "normal"})
                        budget -= est
                        total_sets += sets
            result.append({"name": name, "focus": "/".join(muscles), "day": f"Dia {day_idx}", "max_minutes": max_minutes, "exercises": exercises})
        return result


def calc_1rm(weight, reps):
    weight = safe_float(weight); reps = safe_int(reps)
    if reps <= 1:
        return weight
    return round(weight * (1 + reps / 30), 1)


def calc_bmi(weight, height_cm):
    h = safe_float(height_cm) / 100
    return round(safe_float(weight) / (h*h), 1) if h > 0 else 0


def calc_calories(weight, height_cm, age, objective="Hipertrofia"):
    # Mifflin-St Jeor masculino aproximado + atividade moderada
    bmr = 10*safe_float(weight) + 6.25*safe_float(height_cm) - 5*safe_int(age) + 5
    maintenance = bmr * 1.55
    surplus = 350 if "Hipertrofia" in objective or "massa" in objective.lower() else -350
    return round(maintenance + surplus)


def macro_targets(weight, calories):
    w = safe_float(weight)
    protein = round(w * 2.0)
    fat = round(w * 0.9)
    carbs = round((safe_float(calories) - protein*4 - fat*9) / 4)
    water = round(w * 40)
    return protein, max(carbs, 0), fat, water


def plate_calculator(total_weight, bar_weight=20):
    total_weight = safe_float(total_weight); bar_weight = safe_float(bar_weight)
    side = max(0, (total_weight - bar_weight) / 2)
    plates = [25,20,15,10,5,2,1,0.5]
    out = []
    for p in plates:
        n = int(side // p)
        if n:
            out.append((p,n))
            side -= p*n
    return out


def warmup_sets(target):
    target = safe_float(target)
    return [("Aquecimento 1", round(target*0.40,1), 10), ("Aquecimento 2", round(target*0.60,1), 6), ("Aquecimento 3", round(target*0.80,1), 3)]


def smart_coach_lines(store, user_id):
    lines = []
    profile = store.get_profile(user_id)
    logs = store.recent_logs(user_id, 500)
    feedback = store.recent_feedback(user_id, 5)
    health = store.conn.execute("SELECT * FROM health_records WHERE user_id=? ORDER BY record_date DESC LIMIT 5", (user_id,)).fetchall()
    measurements = store.measurements(user_id)
    today = date.today()
    recent_days = sorted(set(str(r["log_date"])[:10] for r in logs if (today - datetime.strptime(str(r["log_date"])[:10], "%Y-%m-%d").date()).days <= 7)) if logs else []
    volume7 = sum((r["weight"] or 0)*(r["reps"] or 0) for r in logs if (today - datetime.strptime(str(r["log_date"])[:10], "%Y-%m-%d").date()).days <= 7) if logs else 0
    readiness = 75
    if health:
        last = health[0]
        sleep = safe_float(last["sleep_hours"], 0)
        if sleep and sleep < 6: readiness -= 15
        if sleep >= 7: readiness += 8
        if safe_int(last["resting_hr"], 0) > 85: readiness -= 10
    if feedback:
        f = feedback[0]
        if safe_int(f["pain_level"], 0) >= 5: readiness -= 25
        if safe_int(f["energy"], 5) <= 4: readiness -= 12
    readiness = max(20, min(100, readiness))
    lines.append(f"Prontidão estimada hoje: {readiness}/100.")
    if profile and "Ectomorfo" in (profile["body_type"] or ""):
        lines.append("Modo ectomorfo: treino curto, pesado e controlado; descanso e superávit calórico são prioridade.")
        if len(recent_days) >= 4:
            lines.append("Você treinou 4+ dias na semana. Para ganhar massa, não exagere no volume se o peso não estiver subindo.")
    if len(recent_days) < 2:
        lines.append("Frequência baixa nos últimos 7 dias. Faça o próximo treino planejado e não tente compensar tudo em um único dia.")
    elif len(recent_days) >= 3:
        lines.append("Frequência boa. Mantenha progressão pequena de carga ou repetições.")
    if feedback:
        f = feedback[0]
        if safe_int(f["pain_level"],0) >= 4:
            lines.append(f"Atenção à dor em {f['pain_area']}: reduza carga, evite falha e priorize execução.")
        if safe_int(f["duration_minutes"],0) > 90:
            lines.append("O treino passou de 90 minutos. Corte isoladores extras ou reduza conversas/descanso.")
    if measurements and len(measurements) >= 2:
        delta = (measurements[-1]["weight_kg"] or 0) - (measurements[0]["weight_kg"] or 0)
        if delta <= 0 and profile and "massa" in (profile["objective"] or "").lower():
            lines.append("Peso não subiu nas medidas: aumente 250 a 400 kcal por dia por 7 dias e acompanhe.")
        elif delta > 0:
            lines.append(f"Peso evoluiu {round(delta,1)} kg no histórico: bom sinal para bulking.")
    lines.append(f"Volume recente estimado: {round(volume7)} kg nos últimos 7 dias.")
    return lines


# -----------------------------------------------------------------------------
# Widget de gráfico simples sem dependências pesadas
# -----------------------------------------------------------------------------

class LineChart(Widget):
    values = ListProperty([])
    title = StringProperty("Gráfico")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw, values=self.draw)

    def draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(*Theme.panel2)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(16)])
            Color(*Theme.accent)
            x0, y0 = self.x + dp(18), self.y + dp(28)
            w, h = max(1, self.width - dp(36)), max(1, self.height - dp(60))
            Color(0.25,0.35,0.45,1)
            Line(points=[x0,y0,x0+w,y0], width=1)
            Line(points=[x0,y0,x0,y0+h], width=1)
            vals = [safe_float(v) for v in self.values if v is not None]
            if len(vals) < 2:
                Color(*Theme.muted)
                Line(points=[x0,y0+h/2,x0+w,y0+h/2], width=1)
                return
            mn, mx = min(vals), max(vals)
            if mx == mn: mx += 1
            pts=[]
            for i,v in enumerate(vals):
                x = x0 + (w * i / (len(vals)-1))
                y = y0 + ((v-mn)/(mx-mn))*h
                pts += [x,y]
            Color(*Theme.accent)
            Line(points=pts, width=2.2)
            for i in range(0, len(pts), 2):
                Rectangle(pos=(pts[i]-dp(2), pts[i+1]-dp(2)), size=(dp(4), dp(4)))


# -----------------------------------------------------------------------------
# Base screen
# -----------------------------------------------------------------------------

class BaseScreen(Screen):
    def app(self):
        return App.get_running_app()

    def root_box(self, title: str, subtitle: str = ""):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        header = BoxLayout(size_hint_y=None, height=dp(64), spacing=dp(8))
        back = GhostButton("‹")
        back.size_hint_x = None; back.width = dp(46)
        back.bind(on_release=lambda *_: self.app().go_home())
        header.add_widget(back)
        titles = BoxLayout(orientation="vertical")
        titles.add_widget(Title(title, 21))
        if subtitle:
            titles.add_widget(Muted(subtitle, 12))
        header.add_widget(titles)
        box.add_widget(header)
        return box

    def scroller(self):
        sv = ScrollView(do_scroll_x=False)
        content = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        sv.add_widget(content)
        return sv, content

    def nav_button(self, text, target, bg=None):
        b = Pill(text, bg=bg or Theme.panel2)
        b.color = Theme.text
        b.bind(on_release=lambda *_: self.app().nav(target))
        return b


class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        box.add_widget(Image(source="assets/icon.png", size_hint_y=None, height=dp(110)))
        box.add_widget(Title("Treino Pro Max", 28, size_hint_y=None, height=dp(42)))
        box.add_widget(Muted("Login local com estrutura pronta para nuvem/API", 14, size_hint_y=None, height=dp(28)))
        self.email = Input("E-mail")
        self.passw = Input("Senha"); self.passw.password = True
        box.add_widget(self.email); box.add_widget(self.passw)
        entrar = Pill("Entrar")
        entrar.bind(on_release=self.do_login)
        box.add_widget(entrar)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        criar = GhostButton("Criar conta")
        criar.bind(on_release=lambda *_: self.create_popup())
        reset = GhostButton("Recuperar senha")
        reset.bind(on_release=lambda *_: self.reset_popup())
        row.add_widget(criar); row.add_widget(reset)
        box.add_widget(row)
        demo = Muted("Conta demo: luis@app.local / 123456", 13, size_hint_y=None, height=dp(26))
        box.add_widget(demo)
        self.add_widget(box)

    def do_login(self, *_):
        app = App.get_running_app()
        user = app.store.login(self.email.text or "luis@app.local", self.passw.text or "123456")
        if user:
            app.user = dict(user)
            app.nav("home")
        else:
            toast("E-mail ou senha incorretos.")

    def create_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        name, email, pwd, ans = Input("Nome"), Input("E-mail"), Input("Senha"), Input("Resposta de segurança: sua palavra-chave")
        pwd.password=True
        for w in [name,email,pwd,ans]: box.add_widget(w)
        btn = Pill("Criar")
        box.add_widget(btn)
        pop = Popup(title="Criar conta local", content=box, size_hint=(0.9,None), height=dp(360))
        def go(*_):
            ok = App.get_running_app().store.create_user(name.text, email.text, pwd.text, ans.text)
            toast("Conta criada. Agora entre com e-mail e senha." if ok else "Esse e-mail já existe.")
            pop.dismiss()
        btn.bind(on_release=go)
        pop.open()

    def reset_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        email, ans, pwd = Input("E-mail"), Input("Resposta de segurança"), Input("Nova senha")
        pwd.password=True
        for w in [email,ans,pwd]: box.add_widget(w)
        btn = Pill("Alterar senha")
        box.add_widget(btn)
        pop = Popup(title="Recuperar senha", content=box, size_hint=(0.9,None), height=dp(320))
        def go(*_):
            ok = App.get_running_app().store.reset_password(email.text, ans.text, pwd.text)
            toast("Senha alterada." if ok else "Não conferiu. Verifique e-mail e resposta.")
            pop.dismiss()
        btn.bind(on_release=go)
        pop.open()


class HomeScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        app = self.app()
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        hero = Card(orientation="vertical", size_hint_y=None, height=dp(140), bg=(0.04,0.11,0.14,1))
        hero.add_widget(Title(f"Olá, {app.user.get('name','Atleta')}", 25))
        hero.add_widget(Muted("Versão pessoal premium: treino, evolução, mídia, nuvem opcional e lembretes.", 14))
        stats = self.today_summary()
        hero.add_widget(Body(stats, 15, size_hint_y=None, height=dp(35)))
        box.add_widget(hero)
        sv, content = self.scroller()
        groups = [
            ("Treino", [("Treino de hoje + timer", "workout_today"), ("Editor de treinos", "workout_editor"), ("Gerador inteligente de treino", "generator"), ("Biblioteca de exercícios", "library"), ("Mídias dos exercícios", "media")]),
            ("Inteligente v4.1", [("Treinador inteligente", "smart_coach"), ("Avaliação do treino", "feedback"), ("Conteúdo remoto RunSite", "remote_content"), ("Relatório semanal", "weekly_report")]),
            ("Evolução", [("Dashboard e gráficos", "dashboard"), ("Progresso e gráficos", "progress"), ("Medidas corporais", "measurements"), ("Fotos de progresso", "photos")]),
            ("Ferramentas", [("Calculadoras fitness", "calculators"), ("Alimentação e macros", "nutrition"), ("Integração saúde/relógio", "health"), ("Lembretes e notificações", "notifications")]),
            ("Profissional", [("Modo personal trainer", "trainer"), ("Compartilhar / exportar", "share"), ("Nuvem pessoal / integração", "cloud_sync")]),
            ("Conta", [("Perfil e objetivo", "profile"), ("Backup e importação", "backup"), ("Configurações", "settings")]),
        ]
        for title, buttons in groups:
            card = Card(orientation="vertical", size_hint_y=None, height=dp(72+len(buttons)*50))
            card.add_widget(Title(title, 18, size_hint_y=None, height=dp(34)))
            for text, target in buttons:
                card.add_widget(self.nav_button(text, target))
            content.add_widget(card)
        box.add_widget(sv)
        self.add_widget(box)

    def today_summary(self):
        app = self.app()
        logs = app.store.recent_logs(app.user["id"], 500)
        today_logs = [r for r in logs if str(r["log_date"]).startswith(today_iso())]
        volume = sum((r["weight"] or 0) * (r["reps"] or 0) for r in today_logs)
        return f"Hoje: {len(today_logs)} séries registradas • Volume: {round(volume)} kg • Meta: até 90 min • v4.1 inteligente"


class ProfileScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box = self.root_box("Perfil", "Dados usados pelo gerador de treino e alimentação")
        sv, c = self.scroller()
        p = self.app().store.get_profile(self.app().user["id"])
        self.fields = {}
        entries = [
            ("age","Idade", p["age"] if p else ""), ("height_cm","Altura cm", p["height_cm"] if p else ""),
            ("weight_kg","Peso kg", p["weight_kg"] if p else ""), ("objective","Objetivo", p["objective"] if p else "Hipertrofia"),
            ("level","Nível", p["level"] if p else "Voltando após pausa"), ("body_type","Biotipo", p["body_type"] if p else "Ectomorfo"),
            ("days_per_week","Dias por semana", p["days_per_week"] if p else 3), ("max_minutes","Tempo máximo por treino", p["max_minutes"] if p else 90),
            ("equipment","Equipamentos", p["equipment"] if p else "Academia completa"), ("injuries","Lesões/limitações", p["injuries"] if p else "Nenhuma"),
            ("priority_muscle","Músculo prioridade", p["priority_muscle"] if p else "Geral")]
        card = Card(orientation="vertical", size_hint_y=None, height=dp(620))
        for key,label,value in entries:
            card.add_widget(Muted(label, 12, size_hint_y=None, height=dp(20)))
            inp = Input(str(value or ""))
            inp.text = str(value or "")
            self.fields[key] = inp
            card.add_widget(inp)
        btn = Pill("Salvar perfil")
        btn.bind(on_release=self.save)
        card.add_widget(btn)
        c.add_widget(card)
        box.add_widget(sv)
        self.add_widget(box)

    def save(self, *_):
        d = {k:v.text for k,v in self.fields.items()}
        self.app().store.save_profile(self.app().user["id"], d)
        toast("Perfil salvo. O gerador de treino já vai usar esses dados.")


class WorkoutTodayScreen(BaseScreen):
    workout_id = NumericProperty(0)
    elapsed = NumericProperty(0)
    rest_left = NumericProperty(0)
    current_ex = DictProperty({})

    def on_pre_enter(self):
        self.elapsed = 0
        self.rest_left = 0
        Clock.unschedule(self.tick)
        Clock.schedule_interval(self.tick, 1)
        self.build()

    def on_leave(self):
        Clock.unschedule(self.tick)

    def tick(self, *_):
        self.elapsed += 1
        if self.rest_left > 0:
            self.rest_left -= 1
            if self.rest_left == 0:
                self.notify("Descanso finalizado", "Pode iniciar a próxima série.")
        if hasattr(self, "timer_label"):
            self.timer_label.text = f"Treino: {self.elapsed//60:02d}:{self.elapsed%60:02d} • Descanso: {self.rest_left//60:02d}:{self.rest_left%60:02d}"

    def notify(self, title, msg):
        if vibrator:
            try: vibrator.vibrate(0.35)
            except Exception: pass
        if notification:
            try: notification.notify(title=title, message=msg, timeout=3, app_name=APP_NAME)
            except Exception: pass

    def build(self):
        self.clear_widgets()
        app = self.app(); uid = app.user["id"]
        box = self.root_box("Treino de hoje", "Timer, séries, carga, RPE e progressão")
        workouts = app.store.get_workouts(uid)
        if not workouts:
            box.add_widget(Body("Nenhum treino criado. Use o Gerador Inteligente."))
            self.add_widget(box); return
        if self.workout_id == 0:
            weekday = datetime.now().weekday()
            idx = {0:0,2:1,4:2}.get(weekday,0)
            idx = min(idx, len(workouts)-1)
            self.workout_id = workouts[idx]["id"]
        choose = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
        for w in workouts[:4]:
            b = GhostButton(w["day_name"][:10])
            b.bind(on_release=lambda _, wid=w["id"]: self.set_workout(wid))
            choose.add_widget(b)
        box.add_widget(choose)
        self.timer_label = Title("Treino: 00:00 • Descanso: 00:00", 18, size_hint_y=None, height=dp(42))
        box.add_widget(self.timer_label)
        sv, c = self.scroller()
        for ex in app.store.get_workout_exercises(self.workout_id):
            card = Card(orientation="vertical", size_hint_y=None, height=dp(260))
            best = app.store.best_weight(uid, ex["name"])
            sug, reason = app.store.suggest_next_weight(uid, ex["name"], ex["suggested_weight"] or best)
            card.add_widget(Title(ex["name"], 17, size_hint_y=None, height=dp(30)))
            card.add_widget(Muted(f"{ex['muscle']} • {ex['sets']}x{ex['reps']} • Descanso {ex['rest_seconds']}s • Tipo: {ex['set_type']}", 12, size_hint_y=None, height=dp(24)))
            card.add_widget(Muted(f"Carga sugerida: {sug} kg • {reason}", 12, size_hint_y=None, height=dp(38)))
            row = GridLayout(cols=4, spacing=dp(6), size_hint_y=None, height=dp(50))
            w_in = Input("Peso"); w_in.text = str(sug)
            r_in = Input("Reps"); r_in.text = "10"
            rpe_in = Input("RPE"); rpe_in.text = "8"
            set_in = Input("Série"); set_in.text = "1"
            for i in [w_in,r_in,rpe_in,set_in]: row.add_widget(i)
            card.add_widget(row)
            row2 = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
            log_btn = Pill("Salvar série")
            log_btn.bind(on_release=lambda _, ex=dict(ex), wi=w_in, ri=r_in, rpei=rpe_in, si=set_in: self.log(ex, wi.text, ri.text, rpei.text, si.text))
            rest_btn = GhostButton("Iniciar descanso")
            rest_btn.bind(on_release=lambda _, rest=ex["rest_seconds"]: self.start_rest(rest))
            row2.add_widget(log_btn); row2.add_widget(rest_btn)
            card.add_widget(row2)
            c.add_widget(card)
        box.add_widget(sv)
        self.add_widget(box)

    def set_workout(self, wid):
        self.workout_id = wid
        self.build()

    def start_rest(self, sec):
        self.rest_left = safe_int(sec,60)

    def log(self, ex, weight, reps, rpe, set_no):
        self.app().store.log_set(self.app().user["id"], self.workout_id, ex, safe_int(set_no,1), safe_float(weight), safe_int(reps), safe_float(rpe), ex.get("set_type","normal"))
        self.start_rest(ex.get("rest_seconds",60))
        toast("Série salva e descanso iniciado.")


class GeneratorScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box = self.root_box("Gerador inteligente", "Cria treino por objetivo, tempo, nível, equipamento e biotipo")
        p = self.app().store.get_profile(self.app().user["id"])
        if not p:
            box.add_widget(Body("Preencha o perfil primeiro.")); self.add_widget(box); return
        btn = Pill("Gerar novo treino personalizado")
        btn.bind(on_release=self.generate)
        box.add_widget(btn)
        self.result = ScrollView(do_scroll_x=False)
        self.content = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.content.bind(minimum_height=self.content.setter("height"))
        self.result.add_widget(self.content)
        box.add_widget(self.result)
        self.add_widget(box)

    def generate(self, *_):
        app = self.app(); uid=app.user["id"]
        plan = WorkoutGenerator.generate(app.exercises, app.store.get_profile(uid))
        self.content.clear_widgets()
        for day in plan:
            card = Card(orientation="vertical", size_hint_y=None, height=dp(90+len(day["exercises"])*32))
            card.add_widget(Title(day["name"], 18, size_hint_y=None, height=dp(32)))
            card.add_widget(Muted(f"Foco: {day['focus']} • Meta até {day['max_minutes']} min", 12, size_hint_y=None, height=dp(24)))
            for e in day["exercises"]:
                card.add_widget(Body(f"• {e['name']} — {e['sets']}x{e['reps']} • {e['rest']}s", 13, size_hint_y=None, height=dp(28)))
            save = GhostButton("Salvar este treino")
            save.bind(on_release=lambda _, d=day: self.save_day(d))
            card.add_widget(save)
            self.content.add_widget(card)

    def save_day(self, d):
        app = self.app(); uid=app.user["id"]
        wid = app.store.add_workout(uid, d["name"], d["day"], d["focus"], d["max_minutes"])
        for order,e in enumerate(d["exercises"],1):
            app.store.conn.execute("""INSERT INTO workout_exercises(workout_id,exercise_id,name,muscle,sets,reps,rest_seconds,suggested_weight,set_type,order_index)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (wid,e["exercise_id"],e["name"],e["muscle"],e["sets"],e["reps"],e["rest"],e["weight"],e["set_type"],order))
        app.store.conn.commit()
        toast("Treino salvo na sua lista.")


class LibraryScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box = self.root_box("Biblioteca de exercícios", "320 exercícios com técnica, erros, substitutos e filtros")
        filters = GridLayout(cols=2, size_hint_y=None, height=dp(104), spacing=dp(8))
        self.term = Input("Buscar exercício")
        self.muscle = Input("Músculo: Todos")
        self.equip = Input("Equipamento: Todos")
        btn = Pill("Filtrar")
        btn.bind(on_release=lambda *_: self.load_results())
        for w in [self.term,self.muscle,self.equip,btn]: filters.add_widget(w)
        box.add_widget(filters)
        sv, self.content = self.scroller()
        box.add_widget(sv)
        self.add_widget(box)
        self.load_results()

    def load_results(self):
        self.content.clear_widgets()
        muscle = self.muscle.text.replace("Músculo:","").strip() or "Todos"
        equip = self.equip.text.replace("Equipamento:","").strip() or "Todos"
        res = self.app().exercises.search(self.term.text, muscle if muscle != "" else "Todos", equip if equip != "" else "Todos")[:80]
        for e in res:
            card = Card(orientation="vertical", size_hint_y=None, height=dp(160))
            card.add_widget(Title(e["name"], 16, size_hint_y=None, height=dp(28)))
            card.add_widget(Muted(f"{e['muscle']} • {e['equipment']} • {e['level']}", 12, size_hint_y=None, height=dp(24)))
            card.add_widget(Body(e["technique"], 13, size_hint_y=None, height=dp(42)))
            b = GhostButton("Ver detalhes")
            b.bind(on_release=lambda _, ex=e: self.detail(ex))
            card.add_widget(b)
            self.content.add_widget(card)

    def detail(self, e):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        box.add_widget(Image(source=f"assets/{e['image']}", size_hint_y=None, height=dp(150)))
        box.add_widget(Title(e["name"], 18, size_hint_y=None, height=dp(32)))
        box.add_widget(Body(f"Execução: {e['technique']}\n\nErros comuns: {e['common_errors']}\n\nSubstitutos: {e['substitutes']}\n\nTipos de série: {', '.join(e['set_types'])}", 14))
        btn = Pill("Fechar")
        box.add_widget(btn)
        pop = Popup(title="Detalhes", content=box, size_hint=(0.94,0.86))
        btn.bind(on_release=pop.dismiss)
        pop.open()


class ProgressScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        app=self.app(); uid=app.user["id"]
        box=self.root_box("Progresso e gráficos", "Carga, volume, frequência, recordes e 1RM estimado")
        logs=app.store.recent_logs(uid, 500)
        by_day={}
        for r in logs:
            d=str(r["log_date"])[:10]
            by_day[d]=by_day.get(d,0)+(r["weight"] or 0)*(r["reps"] or 0)
        vals=[by_day[k] for k in sorted(by_day.keys())][-12:]
        chart=LineChart(values=vals, size_hint_y=None, height=dp(220))
        box.add_widget(chart)
        sv,c=self.scroller()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(420))
        total_sets=len(logs)
        volume=sum((r["weight"] or 0)*(r["reps"] or 0) for r in logs)
        card.add_widget(Title("Resumo", 19, size_hint_y=None, height=dp(34)))
        card.add_widget(Body(f"Séries registradas: {total_sets}\nVolume total recente: {round(volume)} kg\nDias treinados: {len(by_day)}", 15, size_hint_y=None, height=dp(90)))
        names=sorted(set(r["exercise_name"] for r in logs))[:8]
        for n in names:
            best=app.store.best_weight(uid,n)
            one=calc_1rm(best,10) if best else 0
            card.add_widget(Muted(f"{n}: recorde {best} kg • 1RM estimado {one} kg", 12, size_hint_y=None, height=dp(26)))
        c.add_widget(card)
        box.add_widget(sv)
        self.add_widget(box)


class MeasurementsScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Medidas corporais", "Peso, cintura, braço, coxa, peito e percentual")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(390))
        self.inputs={}
        for k,h in [("weight","Peso kg"),("chest","Peito cm"),("waist","Cintura cm"),("arm","Braço cm"),("thigh","Coxa cm"),("bf","% gordura"),("notes","Observações")]:
            inp=Input(h); self.inputs[k]=inp; card.add_widget(inp)
        btn=Pill("Salvar medidas de hoje")
        btn.bind(on_release=self.save)
        card.add_widget(btn)
        box.add_widget(card)
        vals=[r["weight_kg"] for r in app.store.measurements(uid)]
        box.add_widget(LineChart(values=vals[-12:], size_hint_y=None, height=dp(210)))
        self.add_widget(box)

    def save(self,*_):
        self.app().store.add_measurement(self.app().user["id"], {k:v.text for k,v in self.inputs.items()})
        toast("Medidas salvas.")


class CalculatorsScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box=self.root_box("Calculadoras fitness", "1RM, anilhas, aquecimento, IMC, calorias, proteína e água")
        sv,c=self.scroller()
        self.inputs={}
        fields=[("weight","Peso/carga"),("reps","Repetições"),("bar","Peso da barra"),("height","Altura cm"),("age","Idade")]
        card=Card(orientation="vertical", size_hint_y=None, height=dp(410))
        for k,h in fields:
            inp=Input(h); self.inputs[k]=inp; card.add_widget(inp)
        btn=Pill("Calcular tudo")
        btn.bind(on_release=self.calc)
        card.add_widget(btn)
        self.output=Body("Resultado aparece aqui.",14)
        card.add_widget(self.output)
        c.add_widget(card)
        box.add_widget(sv); self.add_widget(box)

    def calc(self,*_):
        w=self.inputs["weight"].text; reps=self.inputs["reps"].text; bar=self.inputs["bar"].text or 20
        h=self.inputs["height"].text; age=self.inputs["age"].text or 25
        calories=calc_calories(w,h,age,"Hipertrofia")
        prot,carb,fat,water=macro_targets(w,calories)
        plates=plate_calculator(w,bar)
        warm=warmup_sets(w)
        self.output.text=(f"1RM estimado: {calc_1rm(w,reps)} kg\nIMC: {calc_bmi(w,h)}\nCalorias para massa: {calories} kcal\n"
                          f"Proteína: {prot}g • Carbo: {carb}g • Gordura: {fat}g • Água: {water} ml\n"
                          f"Anilhas por lado: {plates}\nAquecimento: {warm}")


class NutritionScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        p=app.store.get_profile(uid)
        box=self.root_box("Alimentação", "Macros, refeições, bulking e lista de compras")
        if p:
            cal=calc_calories(p["weight_kg"],p["height_cm"],p["age"],p["objective"])
            prot,carb,fat,water=macro_targets(p["weight_kg"],cal)
            box.add_widget(Card(orientation="vertical", size_hint_y=None, height=dp(120)))
            box.children[0].add_widget(Title("Meta diária",18))
            box.children[0].add_widget(Body(f"{cal} kcal • Proteína {prot}g • Carbo {carb}g • Gordura {fat}g • Água {water} ml",14))
        card=Card(orientation="vertical", size_hint_y=None, height=dp(330))
        self.m={}
        for k,h in [("name","Refeição"),("cal","Calorias"),("prot","Proteína g"),("carb","Carbo g"),("fat","Gordura g"),("notes","Obs")]:
            inp=Input(h); self.m[k]=inp; card.add_widget(inp)
        btn=Pill("Salvar refeição")
        btn.bind(on_release=self.save)
        card.add_widget(btn)
        box.add_widget(card)
        sv,c=self.scroller()
        meals=app.store.meals_today(uid)
        total=sum(r["calories"] for r in meals)
        c.add_widget(Title(f"Hoje: {round(total)} kcal registradas",18,size_hint_y=None,height=dp(35)))
        for r in meals:
            c.add_widget(Muted(f"{r['name']}: {r['calories']} kcal • P {r['protein']} C {r['carbs']} G {r['fat']}",13,size_hint_y=None,height=dp(28)))
        c.add_widget(Body("Lista de compras sugerida: arroz, feijão, ovos, frango, carne, leite, aveia, banana, batata, macarrão, azeite, pasta de amendoim.",14,size_hint_y=None,height=dp(80)))
        box.add_widget(sv); self.add_widget(box)

    def save(self,*_):
        self.app().store.add_meal(self.app().user["id"],{k:v.text for k,v in self.m.items()})
        toast("Refeição salva.")
        self.on_pre_enter()


class NotificationsScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box=self.root_box("Lembretes e notificações", "Treino, água, refeição, descanso e ausência")
        sv,c=self.scroller()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(370))
        card.add_widget(Title("Notificações configuradas",18,size_hint_y=None,height=dp(35)))
        for text in ["Segunda/Quarta/Sexta: aviso de treino", "Água a cada 2 horas", "Refeição a cada 3 horas", "Aviso se ficar 3 dias sem treino", "Alerta/vibração ao terminar descanso"]:
            card.add_widget(Body("• "+text,14,size_hint_y=None,height=dp(35)))
        test=Pill("Testar notificação agora")
        test.bind(on_release=self.test)
        card.add_widget(test)
        c.add_widget(card)
        info=Card(orientation="vertical", size_hint_y=None, height=dp(150))
        info.add_widget(Muted("Observação técnica",13,size_hint_y=None,height=dp(24)))
        info.add_widget(Body("No app aberto, o timer e alertas funcionam. Para notificação garantida com app fechado, conecte o serviço nativo Android/AlarmManager ou Firebase nas próximas builds.",14))
        c.add_widget(info)
        box.add_widget(sv); self.add_widget(box)

    def test(self,*_):
        if notification:
            try: notification.notify(title="Treino Pro Max", message="Notificação funcionando.", timeout=4)
            except Exception: pass
        if vibrator:
            try: vibrator.vibrate(0.4)
            except Exception: pass
        toast("Teste enviado. No PC pode aparecer só esta mensagem; no Android aparece notificação se permitido.")


class PhotosScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Fotos de progresso", "Frente, lado, costas e comparação antes/depois")
        row=BoxLayout(size_hint_y=None,height=dp(50),spacing=dp(8))
        add=GhostButton("Selecionar foto")
        add.bind(on_release=self.pick)
        cam=GhostButton("Abrir câmera")
        cam.bind(on_release=self.take_photo)
        row.add_widget(add); row.add_widget(cam); box.add_widget(row)
        sv,c=self.scroller()
        photos=app.store.photos(uid)
        for p in photos:
            card=Card(orientation="horizontal", size_hint_y=None, height=dp(120))
            if os.path.exists(p["path"]): card.add_widget(Image(source=p["path"], size_hint_x=None, width=dp(110)))
            card.add_widget(Body(f"{p['photo_date']} • {p['angle']}\n{p['notes']}\n{p['path']}",13))
            c.add_widget(card)
        if not photos:
            c.add_widget(Body("Nenhuma foto ainda. Adicione frente, lado e costas a cada 15 ou 30 dias.",14,size_hint_y=None,height=dp(80)))
        box.add_widget(sv); self.add_widget(box)

    def pick(self,*_):
        if filechooser:
            try:
                filechooser.open_file(on_selection=self._picked)
                return
            except Exception:
                pass
        toast("No Android, o seletor abre pelos arquivos. No PC, copie uma imagem para a pasta photos e registre manualmente.")

    def _picked(self, selection):
        if selection:
            self.app().store.add_photo(self.app().user["id"], "Frente/Lado/Costas", selection[0], "Foto importada")
            toast("Foto salva.")
            self.on_pre_enter()

    def take_photo(self,*_):
        if camera:
            try:
                path=str(self.app().store.photos_dir / f"camera_{int(time.time())}.jpg")
                camera.take_picture(filename=path, on_complete=lambda p: self._picked([p] if p else []))
                return
            except Exception:
                pass
        toast("Câmera disponível apenas no Android com permissões ativas.")


class ShareScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Compartilhar e exportar", "CSV, backup, texto para WhatsApp e estrutura social")
        sv,c=self.scroller()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(300))
        for text,fn in [("Exportar histórico CSV",self.csv),("Gerar backup JSON",self.backup),("Criar resumo para WhatsApp",self.whatsapp),("Exportar treino em texto",self.text_export)]:
            b=Pill(text); b.bind(on_release=lambda _, f=fn: f()); card.add_widget(b)
        c.add_widget(card)
        info=Card(orientation="vertical", size_hint_y=None, height=dp(145))
        info.add_widget(Body("Área social preparada: exportação de treino, resumo de evolução e envio por WhatsApp. Recursos de amigos, curtidas e ranking precisam de servidor para funcionar de verdade.",14))
        c.add_widget(info)
        box.add_widget(sv); self.add_widget(box)

    def csv(self):
        path=self.app().store.export_csv(self.app().user["id"]); toast(f"CSV criado em:\n{path}")
    def backup(self):
        path=self.app().store.export_backup(self.app().user["id"]); toast(f"Backup criado em:\n{path}")
    def whatsapp(self):
        path=self.text_export()
        toast(f"Resumo pronto para compartilhar pelo WhatsApp:\n{path}")
    def text_export(self):
        app=self.app(); uid=app.user["id"]
        workouts=app.store.get_workouts(uid)
        lines=["TREINO PRO MAX - RESUMO"]
        for w in workouts:
            lines.append(f"\n{w['name']} ({w['focus']})")
            for e in app.store.get_workout_exercises(w["id"]):
                lines.append(f"- {e['name']}: {e['sets']}x{e['reps']} • descanso {e['rest_seconds']}s")
        path=app.store.exports_dir / f"treino_para_whatsapp_{today_iso()}.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path


class TrainerScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Modo personal trainer", "Cadastre alunos, objetivos e envie treinos")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(330))
        self.s={}
        for k,h in [("name","Nome do aluno"),("phone","WhatsApp"),("objective","Objetivo"),("level","Nível"),("notes","Observações")]:
            inp=Input(h); self.s[k]=inp; card.add_widget(inp)
        b=Pill("Salvar aluno")
        b.bind(on_release=self.save)
        card.add_widget(b); box.add_widget(card)
        sv,c=self.scroller()
        for st in app.store.students(uid):
            sc=Card(orientation="vertical", size_hint_y=None, height=dp(135))
            sc.add_widget(Title(st["name"],16,size_hint_y=None,height=dp(28)))
            sc.add_widget(Muted(f"{st['phone']} • {st['objective']} • {st['level']}",12,size_hint_y=None,height=dp(24)))
            sc.add_widget(Body(st["notes"],13))
            c.add_widget(sc)
        box.add_widget(sv); self.add_widget(box)

    def save(self,*_):
        self.app().store.add_student(self.app().user["id"],{k:v.text for k,v in self.s.items()})
        toast("Aluno salvo no modo personal trainer.")
        self.on_pre_enter()


class PremiumScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box=self.root_box("Plano Pro e monetização", "Tela pronta para plano grátis/pro, PIX e gateway")
        sv,c=self.scroller()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(520), bg=(0.05,0.10,0.16,1))
        card.add_widget(Title("Treino Pro Max PRO",24,size_hint_y=None,height=dp(45)))
        benefits=["Treinos ilimitados", "Histórico e gráficos ilimitados", "Gerador avançado", "Fotos de progresso", "Modo personal trainer", "Exportação CSV/backup", "Biblioteca completa", "Calculadoras premium"]
        for b in benefits: card.add_widget(Body("✓ "+b,15,size_hint_y=None,height=dp(32)))
        card.add_widget(Muted("Status atual: PRO liberado localmente para testes.",13,size_hint_y=None,height=dp(28)))
        pix=Pill("Simular pagamento PIX / ativar PRO")
        pix.bind(on_release=lambda *_: toast("PRO ativado no modo local. Para venda real, conecte ASAAS/Mercado Pago/Google Play Billing."))
        card.add_widget(pix)
        terms=GhostButton("Ver termos e privacidade")
        terms.bind(on_release=self.terms)
        card.add_widget(terms)
        c.add_widget(card); box.add_widget(sv); self.add_widget(box)

    def terms(self,*_):
        app=self.app()
        text=(app.store.assets_dir/"terms.txt").read_text(encoding="utf-8")+"\n\n"+(app.store.assets_dir/"privacy.txt").read_text(encoding="utf-8")
        box=BoxLayout(orientation="vertical",padding=dp(12),spacing=dp(8)); box.add_widget(Body(text,13)); btn=Pill("Fechar"); box.add_widget(btn)
        pop=Popup(title="Termos e privacidade", content=box, size_hint=(0.94,0.9)); btn.bind(on_release=pop.dismiss); pop.open()


class BackupScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box=self.root_box("Backup local/nuvem", "Exportar, importar e estrutura de sincronização")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(330))
        for text,fn in [("Exportar backup JSON", self.backup), ("Exportar histórico CSV", self.csv), ("Simular sincronização com nuvem", self.cloud)]:
            b=Pill(text); b.bind(on_release=lambda _, f=fn: f()); card.add_widget(b)
        card.add_widget(Body("Integração real de nuvem exige backend com login, API, banco online e endpoint de sync. A estrutura local já gera backup pronto para envio.",14))
        box.add_widget(card); self.add_widget(box)
    def backup(self): toast(f"Backup criado:\n{self.app().store.export_backup(self.app().user['id'])}")
    def csv(self): toast(f"CSV criado:\n{self.app().store.export_csv(self.app().user['id'])}")
    def cloud(self): toast("Sincronização simulada OK. Configure API_URL no backend para nuvem real.")



class DashboardScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Dashboard premium", "Visão rápida igual app pago: frequência, volume, peso, recordes e alertas")
        logs=app.store.recent_logs(uid, 1000)
        meas=app.store.measurements(uid)
        by_day={}
        by_ex={}
        for r in logs:
            d=str(r["log_date"])[:10]
            vol=(r["weight"] or 0)*(r["reps"] or 0)
            by_day[d]=by_day.get(d,0)+vol
            by_ex.setdefault(r["exercise_name"],[]).append(r)
        sv,c=self.scroller()
        top=GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(260))
        stats=[
            ("Séries recentes", str(len(logs))),
            ("Dias treinados", str(len(by_day))),
            ("Volume recente", f"{round(sum(by_day.values()))} kg"),
            ("Peso atual", f"{meas[0]['weight_kg']} kg" if meas else "Sem registro"),
        ]
        for title,val in stats:
            card=Card(orientation="vertical")
            card.add_widget(Muted(title,12,size_hint_y=None,height=dp(28)))
            card.add_widget(Title(val,22))
            top.add_widget(card)
        c.add_widget(top)
        c.add_widget(LineChart(values=[by_day[k] for k in sorted(by_day.keys())][-16:], size_hint_y=None, height=dp(230)))
        insight=Card(orientation="vertical", size_hint_y=None, height=dp(260))
        insight.add_widget(Title("Análise automática",18,size_hint_y=None,height=dp(34)))
        if not logs:
            msg="Ainda não há histórico. Faça 2 ou 3 treinos registrando carga, reps e RPE para o app sugerir progressão com mais precisão."
        else:
            avg_rpe=sum((r["rpe"] or 0) for r in logs)/max(1,len(logs))
            last_days=len([d for d in by_day if (date.today()-datetime.strptime(d,'%Y-%m-%d').date()).days <= 7])
            msg=f"RPE médio recente: {avg_rpe:.1f}. Frequência dos últimos 7 dias: {last_days} dia(s). "
            msg += "Boa recuperação para ectomorfo: mantenha 3 treinos fortes e coma em superávit." if last_days<=3 else "Atenção: frequência alta. Priorize sono, alimentação e descanso."
        insight.add_widget(Body(msg,14))
        c.add_widget(insight)
        box.add_widget(sv); self.add_widget(box)


class MediaScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app()
        box=self.root_box("Mídias dos exercícios", "Anexe imagem, GIF, vídeo local ou link para cada exercício")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(260))
        self.exid=Input("ID do exercício, exemplo EX0001")
        self.title=Input("Título da mídia")
        self.path=Input("Caminho local da imagem/GIF/vídeo")
        self.url=Input("Link de vídeo opcional")
        for w in [self.exid,self.title,self.path,self.url]: card.add_widget(w)
        row=BoxLayout(size_hint_y=None,height=dp(46),spacing=dp(8))
        pick=GhostButton("Escolher arquivo")
        pick.bind(on_release=self.pick)
        save=Pill("Salvar mídia")
        save.bind(on_release=self.save)
        row.add_widget(pick); row.add_widget(save); card.add_widget(row)
        box.add_widget(card)
        sv,self.content=self.scroller(); box.add_widget(sv); self.add_widget(box); self.load()

    def pick(self,*_):
        if filechooser:
            try:
                filechooser.open_file(on_selection=lambda s: setattr(self.path,'text',s[0] if s else self.path.text))
                return
            except Exception: pass
        toast("No PC, copie o caminho do arquivo. No Android, o seletor abre quando as permissões estiverem ativas.")

    def save(self,*_):
        app=self.app()
        app.store.conn.execute("INSERT INTO exercise_media(exercise_id,title,local_path,video_url,notes,created_at) VALUES(?,?,?,?,?,?)",
            (self.exid.text.strip(), self.title.text.strip() or "Mídia do exercício", self.path.text.strip(), self.url.text.strip(), "Adicionada pelo usuário", now_iso()))
        app.store.conn.commit(); toast("Mídia salva para o exercício."); self.load()

    def load(self):
        self.content.clear_widgets(); app=self.app()
        rows=app.store.conn.execute("SELECT * FROM exercise_media ORDER BY created_at DESC LIMIT 80").fetchall()
        if not rows:
            self.content.add_widget(Body("Nenhuma mídia anexada ainda. Você pode adicionar GIFs, imagens ou links dos exercícios que usa.",14,size_hint_y=None,height=dp(90)))
            return
        for r in rows:
            card=Card(orientation="horizontal", size_hint_y=None, height=dp(120))
            if r["local_path"] and os.path.exists(r["local_path"]):
                card.add_widget(Image(source=r["local_path"], size_hint_x=None, width=dp(115)))
            card.add_widget(Body(f"{r['exercise_id']} • {r['title']}\nArquivo: {r['local_path']}\nLink: {r['video_url']}",13))
            self.content.add_widget(card)


class CloudSyncScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Nuvem pessoal", "Sem pagamento: backup local, API própria e sincronização opcional")
        row=app.store.conn.execute("SELECT * FROM cloud_settings WHERE user_id=?",(uid,)).fetchone()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(430))
        self.api=Input("API URL, exemplo http://192.168.0.10:8000")
        self.token=Input("Token pessoal")
        self.auto=Input("Auto sync 0 ou 1")
        if row:
            self.api.text=row["api_url"] or ""; self.token.text=row["access_token"] or ""; self.auto.text=str(row["auto_sync"] or 0)
        else:
            self.api.text="https://treino-cloud-runsite.onrender.com"
            self.token.text="treino-pro-max-online-2026"
            self.auto.text="1"
        for w in [self.api,self.token,self.auto]: card.add_widget(w)
        for text,fn in [("Salvar configuração",self.save),("Enviar backup para nuvem",self.upload),("Baixar backup da nuvem",self.download),("Gerar pacote local de sync",self.package),("Importar backup JSON",self.import_backup),("Teste de conexão / instruções",self.test)]:
            b=Pill(text); b.bind(on_release=lambda _,f=fn: f()); card.add_widget(b)
        box.add_widget(card)
        info=Card(orientation="vertical", size_hint_y=None, height=dp(210))
        info.add_widget(Body("Nuvem real precisa de um servidor rodando. Incluí a pasta backend_personal_cloud com FastAPI: você pode rodar em PC, VPS ou RunSite. Para uso pessoal, também dá para usar só backup JSON e Google Drive manual.",14))
        box.add_widget(info); self.add_widget(box)

    def save(self,*_):
        app=self.app(); uid=app.user["id"]
        app.store.conn.execute("INSERT OR REPLACE INTO cloud_settings(user_id,api_url,access_token,auto_sync,last_sync) VALUES(?,?,?,?,?)",(uid,self.api.text,self.token.text,safe_int(self.auto.text),now_iso()))
        app.store.conn.commit(); toast("Configuração de nuvem pessoal salva.")

    def package(self,*_):
        path=self.app().store.export_backup(self.app().user["id"])
        toast(f"Pacote gerado para sincronizar/enviar:\n{path}")

    def upload(self,*_):
        app=self.app(); uid=app.user["id"]
        try:
            import urllib.request, json as _json
            path=app.store.export_backup(uid)
            backup=_json.loads(Path(path).read_text(encoding="utf-8"))
            base=self.api.text.rstrip("/")
            token=self.token.text.strip()
            payload=_json.dumps({"user_email": app.user.get("email","local@app"), "backup": backup}).encode("utf-8")
            try:
                req=urllib.request.Request(base+"/sync/upload", data=payload, method="POST", headers={"Content-Type":"application/json", "Authorization":"Bearer "+token})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    out=resp.read().decode("utf-8")
            except Exception:
                device=str(uid)
                req=urllib.request.Request(base+"/api/backup/"+device, data=_json.dumps(backup).encode("utf-8"), method="POST", headers={"Content-Type":"application/json", "X-API-Token":token})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    out=resp.read().decode("utf-8")
            toast("Backup enviado para a nuvem pessoal.\n"+out[:350])
        except Exception as e:
            toast("Não consegui enviar para a nuvem. Verifique API URL, token, internet e se o servidor está rodando.\n\nErro: "+str(e)[:250])

    def download(self,*_):
        app=self.app()
        try:
            import urllib.request
            base=self.api.text.rstrip("/")
            token=self.token.text.strip()
            email=app.user.get("email","local@app")
            try:
                req=urllib.request.Request(base+"/sync/download/"+email, headers={"Authorization":"Bearer "+token})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    out=resp.read().decode("utf-8")
            except Exception:
                device=str(app.user.get("id",1))
                req=urllib.request.Request(base+"/api/backup/"+device, headers={"X-API-Token":token})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    out=resp.read().decode("utf-8")
            path=app.store.exports_dir / f"backup_nuvem_baixado_{today_iso()}.json"
            Path(path).write_text(out, encoding="utf-8")
            toast(f"Backup baixado da nuvem e salvo em:\n{path}\n\nRestauração automática fica bloqueada por segurança.")
        except Exception as e:
            toast("Não consegui baixar da nuvem. Verifique API URL, token, internet e se o servidor está rodando.\n\nErro: "+str(e)[:250])

    def import_backup(self,*_):
        toast("Importação segura: use a tela Backup e copie o JSON para a pasta exports. A restauração automática deve ser feita com cuidado para não sobrescrever seus dados.")

    def test(self,*_):
        toast("Para testar nuvem: rode backend_personal_cloud/server.py, copie a URL no campo API URL e use o token pessoal definido no servidor.")


class HealthScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Saúde e relógio", "Registro manual + importação CSV para passos, sono e batimentos")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(360))
        self.steps=Input("Passos do dia")
        self.sleep=Input("Sono em horas")
        self.hr=Input("Batimento em repouso")
        self.cal=Input("Calorias gastas")
        self.notes=Input("Observações")
        for w in [self.steps,self.sleep,self.hr,self.cal,self.notes]: card.add_widget(w)
        row=BoxLayout(size_hint_y=None,height=dp(46),spacing=dp(8))
        save=Pill("Salvar saúde")
        save.bind(on_release=self.save)
        exp=GhostButton("Exportar CSV saúde")
        exp.bind(on_release=self.export)
        row.add_widget(save); row.add_widget(exp); card.add_widget(row)
        box.add_widget(card)
        sv,c=self.scroller()
        rows=app.store.conn.execute("SELECT * FROM health_records WHERE user_id=? ORDER BY record_date DESC LIMIT 30",(uid,)).fetchall()
        if not rows:
            c.add_widget(Body("Sem dados ainda. Registre manualmente ou exporte do relógio/Google Fit e adapte para CSV.",14,size_hint_y=None,height=dp(90)))
        for r in rows:
            c.add_widget(Body(f"{r['record_date']}: {r['steps']} passos • sono {r['sleep_hours']}h • HR {r['resting_hr']} • kcal {r['calories_burned']}",13,size_hint_y=None,height=dp(34)))
        box.add_widget(sv); self.add_widget(box)

    def save(self,*_):
        app=self.app(); uid=app.user["id"]
        app.store.conn.execute("INSERT INTO health_records(user_id,record_date,steps,sleep_hours,resting_hr,calories_burned,source,notes) VALUES(?,?,?,?,?,?,?,?)",
            (uid,today_iso(),safe_int(self.steps.text),safe_float(self.sleep.text),safe_int(self.hr.text),safe_float(self.cal.text),"manual",self.notes.text))
        app.store.conn.commit(); toast("Dados de saúde salvos."); self.on_pre_enter()

    def export(self,*_):
        app=self.app(); uid=app.user["id"]
        rows=app.store.conn.execute("SELECT * FROM health_records WHERE user_id=? ORDER BY record_date",(uid,)).fetchall()
        path=app.store.exports_dir / f"saude_{today_iso()}.csv"
        with open(path,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["data","passos","sono_horas","batimento_repouso","calorias","fonte","obs"])
            for r in rows: w.writerow([r['record_date'],r['steps'],r['sleep_hours'],r['resting_hr'],r['calories_burned'],r['source'],r['notes']])
        toast(f"CSV de saúde criado:\n{path}")



class RemoteContentScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Conteúdo remoto Render", "Atualize treinos, dicas, vídeos e configurações sem gerar APK novo")
        row=app.store.conn.execute("SELECT * FROM cloud_settings WHERE user_id=?", (uid,)).fetchone()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(520))
        self.api=Input("URL do Render, ex: https://treino-cloud-runsite.onrender.com")
        self.token=Input("Token do Render")
        if row:
            self.api.text=row["api_url"] or ""; self.token.text=row["access_token"] or ""
        else:
            self.api.text="https://treino-cloud-runsite.onrender.com"
            self.token.text="treino-pro-max-online-2026"
        self.manual=TextInput(hint_text="Ou cole aqui um JSON de configuração remota", background_color=Theme.panel2, foreground_color=Theme.text, hint_text_color=Theme.muted, size_hint_y=None, height=dp(130))
        for w in [self.api,self.token,self.manual]: card.add_widget(w)
        buttons=[("Salvar URL/token",self.save), ("Baixar conteúdo do Render", self.download), ("Aplicar JSON colado", self.apply_manual), ("Criar modelo de JSON remoto", self.make_template), ("Ver últimas atualizações", self.show_cache)]
        for text,fn in buttons:
            b=Pill(text); b.bind(on_release=lambda _,f=fn: f()); card.add_widget(b)
        box.add_widget(card)
        info=Card(orientation="vertical", size_hint_y=None, height=dp(190))
        info.add_widget(Body("Essa tela resolve o problema de mudar treino depois do APK pronto. Você altera o conteúdo no Render e o app baixa/aplica. Dá para mudar exercícios, descanso, séries, dicas, alimentação e links de vídeo sem reinstalar o app.",14))
        box.add_widget(info); self.add_widget(box)

    def save(self,*_):
        app=self.app(); uid=app.user["id"]
        app.store.conn.execute("INSERT OR REPLACE INTO cloud_settings(user_id,api_url,access_token,auto_sync,last_sync) VALUES(?,?,?,?,?)", (uid,self.api.text.strip(),self.token.text.strip(),1,now_iso()))
        app.store.conn.commit(); toast("URL/token salvos. Agora você pode baixar conteúdo remoto.")

    def normalize_render_content(self, data):
        # Aceita tanto o formato antigo v4.1 (workouts) quanto o formato novo do Render (weekly_plan).
        if isinstance(data, dict) and data.get("workouts"):
            return data
        if not isinstance(data, dict):
            return {"version":"remoto-invalido", "workouts":[]}
        weekly = data.get("weekly_plan", []) or []
        workouts = []
        for i, day in enumerate(weekly, 1):
            exercises = []
            for j, e in enumerate(day.get("exercises", []) or [], 1):
                exercises.append({
                    "exercise_id": e.get("exercise_id") or f"RD{i:02d}{j:02d}",
                    "name": e.get("name", "Exercício remoto"),
                    "muscle": e.get("muscle") or e.get("target") or day.get("focus", "Geral"),
                    "sets": e.get("sets", 3),
                    "reps": e.get("reps", "8-12"),
                    "rest": e.get("rest", e.get("rest_seconds", 90)),
                    "weight": e.get("weight", e.get("suggested_weight", 0)),
                    "set_type": e.get("set_type", "normal")
                })
            workouts.append({
                "name": day.get("title") or day.get("name") or f"Treino remoto {i}",
                "day": day.get("day", "Remoto"),
                "focus": day.get("focus", "Personalizado"),
                "max_minutes": data.get("settings", {}).get("max_workout_minutes", 90),
                "exercises": exercises
            })
        return {
            "version": data.get("version", "render-online"),
            "settings": data.get("settings", {}),
            "workouts": workouts,
            "nutrition": data.get("nutrition", data.get("meal_plan", {})),
            "videos": data.get("videos", {})
        }

    def download(self,*_):
        app=self.app(); uid=app.user["id"]
        try:
            import urllib.request, urllib.parse
            base=self.api.text.strip().rstrip("/")
            token=self.token.text.strip()
            errors=[]
            data=None
            # 1) Tenta backend v4.1 antigo: /content/config com Authorization Bearer
            try:
                req=urllib.request.Request(base+"/content/config", headers={"Authorization":"Bearer "+token})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data=json.loads(resp.read().decode("utf-8"))
            except Exception as e1:
                errors.append(str(e1)[:120])
            # 2) Tenta backend Render novo: /api/content?token=...
            if data is None:
                url=base+"/api/content?token="+urllib.parse.quote(token)
                try:
                    req=urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data=json.loads(resp.read().decode("utf-8"))
                except Exception as e2:
                    errors.append(str(e2)[:120])
                    raise Exception(" | ".join(errors))
            normalized=self.normalize_render_content(data)
            app.store.save_remote_cache(base, "config", normalized)
            applied=app.store.apply_remote_plan(uid, normalized)
            toast("Conteúdo remoto baixado do Render e aplicado:\n"+"\n".join(applied[:12]))
        except Exception as e:
            toast("Erro ao baixar/aplicar conteúdo remoto. Confira o link do Render, token e internet.\n\n"+str(e)[:300])

    def apply_manual(self,*_):
        try:
            data=json.loads(self.manual.text)
            applied=self.app().store.apply_remote_plan(self.app().user["id"], data)
            self.app().store.save_remote_cache("manual", "config", data)
            toast("JSON aplicado:\n"+"\n".join(applied[:12]))
        except Exception as e:
            toast("JSON inválido ou erro ao aplicar:\n"+str(e)[:300])

    def make_template(self,*_):
        template={
            "version":"v4.1-modelo",
            "settings":{"modo_ectomorfo":"1","limite_treino_min":"90","frase":"Treine forte, coma bem e descanse."},
            "workouts":[{"name":"Treino remoto exemplo","day":"Segunda","focus":"Peito/Ombro/Tríceps","max_minutes":90,"exercises":[
                {"exercise_id":"R001","name":"Supino reto remoto","muscle":"Peito","sets":4,"reps":"8-12","rest":90,"weight":12,"set_type":"normal"},
                {"exercise_id":"R002","name":"Elevação lateral remota","muscle":"Ombros","sets":3,"reps":"12-15","rest":60,"weight":6,"set_type":"normal"}
            ]}],
            "nutrition":{"bulking_tip":"Adicione uma vitamina hipercalórica caseira se o peso não subir."},
            "videos":{"Supino reto remoto":"https://youtube.com/"}
        }
        path=self.app().store.exports_dir / "modelo_conteudo_remoto_v41.json"
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        self.manual.text=json.dumps(template, ensure_ascii=False, indent=2)
        toast(f"Modelo criado em:\n{path}")

    def show_cache(self,*_):
        rows=self.app().store.conn.execute("SELECT * FROM remote_content_cache ORDER BY created_at DESC LIMIT 5").fetchall()
        msg="\n\n".join([f"{r['created_at']} • {r['source_url']} • {r['content_type']}" for r in rows]) or "Nenhum conteúdo remoto baixado ainda."
        toast(msg, "Últimas atualizações")


class SmartCoachScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Treinador inteligente", "Modo ectomorfo, prontidão, progressão, deload, alertas e alimentação")
        sv,c=self.scroller()
        lines=smart_coach_lines(app.store, uid)
        card=Card(orientation="vertical", size_hint_y=None, height=dp(170+len(lines)*30), bg=(0.04,0.10,0.14,1))
        card.add_widget(Title("Análise de hoje",21,size_hint_y=None,height=dp(38)))
        for line in lines:
            card.add_widget(Body("• "+line,14,size_hint_y=None,height=dp(30)))
        b=Pill("Gerar alertas inteligentes")
        b.bind(on_release=self.make_alerts)
        card.add_widget(b)
        c.add_widget(card)
        logs=app.store.recent_logs(uid, 200)
        names=sorted(set(r["exercise_name"] for r in logs))[:10]
        prog=Card(orientation="vertical", size_hint_y=None, height=dp(80+len(names)*34))
        prog.add_widget(Title("Próximas cargas sugeridas",18,size_hint_y=None,height=dp(35)))
        for n in names:
            best=app.store.best_weight(uid,n)
            sug, reason=app.store.suggest_next_weight(uid,n,best)
            prog.add_widget(Muted(f"{n}: {best} kg → {sug} kg • {reason}",12,size_hint_y=None,height=dp(32)))
        c.add_widget(prog)
        box.add_widget(sv); self.add_widget(box)

    def make_alerts(self,*_):
        app=self.app(); uid=app.user["id"]
        for line in smart_coach_lines(app.store, uid):
            sev="warning" if any(x in line.lower() for x in ["dor","não subiu","baixa","passou"]) else "info"
            app.store.add_smart_alert(uid,"coach",line,sev)
        toast("Alertas inteligentes criados. Veja em Lembretes/Notificações ou Dashboard.")


class WorkoutEditorScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Editor de treinos", "Mude exercícios, séries, descanso e cargas sem mexer no código")
        sv,c=self.scroller()
        self.workouts=app.store.get_workouts(uid)
        form=Card(orientation="vertical", size_hint_y=None, height=dp(440))
        form.add_widget(Title("Adicionar exercício ao treino",18,size_hint_y=None,height=dp(35)))
        self.wid=Input("ID do treino")
        self.name=Input("Nome do exercício")
        self.muscle=Input("Músculo")
        self.sets=Input("Séries")
        self.reps=Input("Reps ex: 8-12")
        self.rest=Input("Descanso segundos")
        self.weight=Input("Carga sugerida")
        self.typ=Input("Tipo: normal, aquecimento, drop-set, bi-set, rest-pause, falha")
        for w in [self.wid,self.name,self.muscle,self.sets,self.reps,self.rest,self.weight,self.typ]: form.add_widget(w)
        add=Pill("Adicionar exercício")
        add.bind(on_release=self.add_exercise)
        form.add_widget(add); c.add_widget(form)
        for w in self.workouts:
            exs=app.store.get_workout_exercises(w["id"])
            card=Card(orientation="vertical", size_hint_y=None, height=dp(90+len(exs)*30))
            card.add_widget(Title(f"ID {w['id']} • {w['name']}",16,size_hint_y=None,height=dp(30)))
            card.add_widget(Muted(f"{w['day_name']} • {w['focus']} • meta {w['max_minutes']} min",12,size_hint_y=None,height=dp(24)))
            for e in exs:
                card.add_widget(Body(f"#{e['id']} {e['name']} — {e['sets']}x{e['reps']} • {e['rest_seconds']}s • {e['set_type']}",12,size_hint_y=None,height=dp(28)))
            c.add_widget(card)
        box.add_widget(sv); self.add_widget(box)

    def add_exercise(self,*_):
        if not self.wid.text.strip():
            toast("Informe o ID do treino. Ele aparece na lista abaixo."); return
        self.app().store.add_custom_exercise_to_workout(safe_int(self.wid.text), self.name.text, self.muscle.text, self.sets.text, self.reps.text, self.rest.text, self.weight.text, self.typ.text or "normal")
        toast("Exercício adicionado ao treino."); self.on_pre_enter()


class FeedbackScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Avaliação do treino", "O app usa isso para ajustar carga, descanso e recuperação")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(430))
        self.workout_id=Input("ID do treino feito (opcional)")
        self.rating=Input("Como foi? Leve, Bom, Pesado, Pesado demais")
        self.energy=Input("Energia 1 a 10")
        self.pain=Input("Dor onde? Nenhuma, ombro, lombar, joelho...")
        self.pain_level=Input("Nível da dor 0 a 10")
        self.duration=Input("Duração em minutos")
        self.notes=Input("Observações")
        for w in [self.workout_id,self.rating,self.energy,self.pain,self.pain_level,self.duration,self.notes]: card.add_widget(w)
        b=Pill("Salvar avaliação inteligente")
        b.bind(on_release=self.save)
        card.add_widget(b); box.add_widget(card)
        sv,c=self.scroller()
        for f in app.store.recent_feedback(uid, 8):
            c.add_widget(Body(f"{f['feedback_date']} • {f['rating']} • energia {f['energy']}/10 • dor {f['pain_area']} {f['pain_level']}/10 • {f['duration_minutes']}min",13,size_hint_y=None,height=dp(38)))
        box.add_widget(sv); self.add_widget(box)

    def save(self,*_):
        d={"workout_id":self.workout_id.text,"rating":self.rating.text or "Bom","energy":self.energy.text or 7,"pain_area":self.pain.text or "Nenhuma","pain_level":self.pain_level.text or 0,"duration":self.duration.text or 0,"notes":self.notes.text}
        self.app().store.add_feedback(self.app().user["id"], d)
        toast("Avaliação salva. O Treinador Inteligente já vai usar esses dados."); self.on_pre_enter()


class WeeklyReportScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets(); app=self.app(); uid=app.user["id"]
        box=self.root_box("Relatório semanal", "Resumo automático para acompanhar evolução e corrigir falhas")
        path, txt=app.store.weekly_report_text(uid)
        sv,c=self.scroller()
        card=Card(orientation="vertical", size_hint_y=None, height=dp(620))
        card.add_widget(Title("Relatório gerado",18,size_hint_y=None,height=dp(35)))
        card.add_widget(Body(txt,13))
        b=Pill("Gerar/atualizar relatório TXT")
        b.bind(on_release=lambda *_: toast(f"Relatório salvo em:\n{path}"))
        card.add_widget(b)
        c.add_widget(card); box.add_widget(sv); self.add_widget(box)


class SettingsScreen(BaseScreen):
    def on_pre_enter(self):
        self.clear_widgets()
        box=self.root_box("Configurações", "Tema, dados, permissões e informações")
        card=Card(orientation="vertical", size_hint_y=None, height=dp(350))
        card.add_widget(Title(f"{APP_NAME} v{VERSION}",20,size_hint_y=None,height=dp(42)))
        card.add_widget(Body("Tema escuro premium ativo.\nBanco local SQLite ativo.\nSem pagamento/assinatura.\nPermissões Android: internet, vibração, câmera, armazenamento, notificações e serviço de lembretes.\nBuild preparado para Kivy/Buildozer.",14))
        b=GhostButton("Sair da conta")
        b.bind(on_release=lambda *_: self.app().logout())
        card.add_widget(b)
        box.add_widget(card); self.add_widget(box)


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------

class TreinoProMaxApp(App):
    user: Dict[str, Any] = {}

    def build(self):
        self.title = APP_NAME
        root = Path(os.path.dirname(os.path.abspath(__file__)))
        self.store = Store(root)
        self.exercises = ExerciseRepo(root / "assets" / "exercises.json")
        self.sm = ScreenManager(transition=SlideTransition(duration=0.18))
        screens = [
            ("login", LoginScreen), ("home", HomeScreen), ("profile", ProfileScreen), ("workout_today", WorkoutTodayScreen),
            ("workout_editor", WorkoutEditorScreen), ("smart_coach", SmartCoachScreen), ("feedback", FeedbackScreen), ("remote_content", RemoteContentScreen), ("weekly_report", WeeklyReportScreen),
            ("generator", GeneratorScreen), ("library", LibraryScreen), ("media", MediaScreen), ("dashboard", DashboardScreen), ("progress", ProgressScreen), ("measurements", MeasurementsScreen),
            ("calculators", CalculatorsScreen), ("nutrition", NutritionScreen), ("health", HealthScreen), ("notifications", NotificationsScreen), ("photos", PhotosScreen),
            ("share", ShareScreen), ("trainer", TrainerScreen), ("cloud_sync", CloudSyncScreen), ("backup", BackupScreen), ("settings", SettingsScreen)
        ]
        for name, cls in screens:
            self.sm.add_widget(cls(name=name))
        self.sm.current = "login"
        return self.sm

    def nav(self, name):
        self.sm.current = name

    def go_home(self):
        self.sm.current = "home" if self.user else "login"

    def logout(self):
        self.user = {}
        self.sm.current = "login"


if __name__ == "__main__":
    TreinoProMaxApp().run()
