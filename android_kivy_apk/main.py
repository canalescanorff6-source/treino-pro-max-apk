import json
import os
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput

Window.clearcolor = (0.03, 0.05, 0.10, 1)
APP_TITLE = "Treino Pro Max Online"
CONFIG_FILE = "treino_config.json"
CACHE_FILE = "treino_content_cache.json"
PENDING_FILE = "treino_pending_logs.json"
DEFAULT_API_URL = "https://SEU-APP.onrender.com"
DEFAULT_TOKEN = "treino-pro-max-online-2026"

def app_path(filename):
    app = App.get_running_app()
    return os.path.join(app.user_data_dir, filename) if app else filename

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception:
        pass
    return default

def save_json(path, data):
    folder = os.path.dirname(path)
    if folder: os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def http_json(method, url, token, payload=None, timeout=20):
    data = None
    headers = {"X-Api-Token": token, "Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(12), spacing=dp(6), size_hint_y=None, **kwargs)
        self.bind(minimum_height=self.setter("height"))

class BaseScreen(Screen):
    def app(self): return App.get_running_app()
    def btn(self, text, cb, h=50):
        b = Button(text=text, size_hint_y=None, height=dp(h), background_normal='', background_color=(0.08,0.22,0.36,1), color=(1,1,1,1), font_size=dp(15))
        b.bind(on_release=lambda *_: cb())
        return b
    def title(self, text):
        return Label(text=text, font_size=dp(22), bold=True, size_hint_y=None, height=dp(45), color=(1,1,1,1))

class HomeScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(Label(text="Treino Pro Max Online", font_size=dp(24), bold=True, size_hint_y=None, height=dp(48), color=(0.8,0.95,1,1)))
        status = f"Servidor: {self.app().api_url()}\nToken: {'configurado' if self.app().token() and 'COLE' not in self.app().token() else 'precisa configurar'}"
        root.add_widget(Label(text=status, size_hint_y=None, height=dp(58), color=(0.85,0.9,1,1)))
        grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        items = [("Configurar Render", "config"), ("Sincronizar", "sync"), ("Treino", "workout"), ("Timer", "timer"), ("Registrar", "log"), ("Histórico", "history"), ("Perfil", "profile"), ("Progresso", "progress"), ("Medidas", "measure")]
        for text, screen in items:
            grid.add_widget(self.btn(text, lambda s=screen: setattr(self.manager, "current", s)))
        scroll = ScrollView(); scroll.add_widget(grid); root.add_widget(scroll)
        root.add_widget(Label(text="Online pelo Render. Se falhar internet, registre pendente e sincronize depois.", size_hint_y=None, height=dp(42), color=(0.7,0.85,1,1)))
        self.add_widget(root)

class ConfigScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(self.title("Configurar Render"))
        self.url = TextInput(text=self.app().api_url(), hint_text="https://seu-app.onrender.com", multiline=False, size_hint_y=None, height=dp(48))
        self.token = TextInput(text=self.app().token(), hint_text="TREINO_API_TOKEN", multiline=False, size_hint_y=None, height=dp(48))
        root.add_widget(self.url); root.add_widget(self.token)
        root.add_widget(self.btn("Salvar configuração", self.save))
        root.add_widget(self.btn("Testar conexão", self.test))
        root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.out = Label(text="", color=(0.8,1,0.8,1), halign="left")
        root.add_widget(self.out)
        self.add_widget(root)
    def save(self):
        self.app().config_data["api_url"] = self.url.text.strip().rstrip("/")
        self.app().config_data["token"] = self.token.text.strip()
        save_json(app_path(CONFIG_FILE), self.app().config_data)
        self.out.text = "Configuração salva."
    def test(self):
        self.save()
        try:
            r = http_json("GET", self.app().api_url()+"/api/content", self.app().token())
            self.out.text = "Conectou. Versão: " + str(r.get("version", "sem versão"))
        except Exception as e:
            self.out.text = "Erro de conexão: " + str(e)

class SyncScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(self.title("Sincronizar"))
        root.add_widget(self.btn("Baixar treinos do Render", self.download))
        root.add_widget(self.btn("Enviar registros pendentes", self.send_pending))
        root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.out=Label(text="", color=(0.85,1,0.85,1), halign="left", valign="top")
        root.add_widget(self.out); self.add_widget(root)
    def download(self):
        try:
            c=http_json("GET", self.app().api_url()+"/api/content", self.app().token())
            self.app().content=c; save_json(app_path(CACHE_FILE), c)
            self.out.text="Conteúdo baixado. Versão: "+str(c.get("version"))
        except Exception as e: self.out.text="Erro ao baixar: "+str(e)
    def send_pending(self):
        pending=load_json(app_path(PENDING_FILE), [])
        sent=0; rest=[]; err=""
        for p in pending:
            try:
                http_json("POST", self.app().api_url()+"/api/workout-log", self.app().token(), p); sent+=1
            except Exception as e:
                rest.append(p); err=str(e)
        save_json(app_path(PENDING_FILE), rest)
        self.out.text=f"Enviados: {sent}. Pendentes: {len(rest)}. {err}"

class WorkoutScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(self.title("Plano semanal"))
        scroll=ScrollView(); box=BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None); box.bind(minimum_height=box.setter("height"))
        for day in self.app().content.get("weekly_plan", []):
            c=Card(); c.add_widget(Label(text=f"{day.get('day')} — {day.get('title')}", bold=True, font_size=dp(17), size_hint_y=None, height=dp(32), color=(1,1,1,1)))
            exs=day.get("exercises", [])
            if not exs: c.add_widget(Label(text="Descanso, sono bom e alimentação forte.", size_hint_y=None, height=dp(32), color=(0.78,0.86,1,1)))
            for e in exs:
                txt=f"{e.get('name')} | {e.get('sets')}x {e.get('reps')} | {e.get('rest')}s\n{e.get('tips','')}"
                c.add_widget(Label(text=txt, size_hint_y=None, height=dp(64), color=(0.86,0.92,1,1), halign="left"))
            box.add_widget(c)
        scroll.add_widget(box); root.add_widget(scroll); root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.add_widget(root)

class TimerScreen(BaseScreen):
    seconds=NumericProperty(90); running=False
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
        root.add_widget(self.title("Timer de descanso")); self.display=Label(text=self.format_time(), font_size=dp(54), bold=True, color=(0.7,0.95,1,1)); root.add_widget(self.display)
        grid=GridLayout(cols=3, spacing=dp(8), size_hint_y=None, height=dp(54))
        for s in [60,90,120]: grid.add_widget(self.btn(f"{s}s", lambda x=s: self.set_seconds(x)))
        root.add_widget(grid); root.add_widget(self.btn("Iniciar/Pausar", self.toggle)); root.add_widget(self.btn("Resetar", self.reset)); root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.add_widget(root)
    def format_time(self):
        m,s=divmod(int(self.seconds),60); return f"{m:02d}:{s:02d}"
    def set_seconds(self,s): self.seconds=s; self.display.text=self.format_time()
    def toggle(self):
        self.running=not self.running
        if self.running: Clock.schedule_interval(self.tick,1)
    def tick(self,dt):
        if not self.running: return False
        if self.seconds>0: self.seconds-=1; self.display.text=self.format_time(); return True
        self.running=False; self.display.text="Fim!"; return False
    def reset(self): self.running=False; self.seconds=90; self.display.text=self.format_time()

class LogScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(self.title("Registrar treino"))
        self.day=TextInput(hint_text="Dia", multiline=False, size_hint_y=None, height=dp(44))
        self.exercise=TextInput(hint_text="Exercício", multiline=False, size_hint_y=None, height=dp(44))
        self.weight=TextInput(hint_text="Carga kg", multiline=False, input_filter="float", size_hint_y=None, height=dp(44))
        self.reps=TextInput(hint_text="Repetições", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        self.sets=TextInput(hint_text="Séries", text="1", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        self.rpe=TextInput(hint_text="RPE 1-10", text="8", multiline=False, input_filter="float", size_hint_y=None, height=dp(44))
        for w in [self.day,self.exercise,self.weight,self.reps,self.sets,self.rpe]: root.add_widget(w)
        root.add_widget(self.btn("Salvar online", self.save_online)); root.add_widget(self.btn("Salvar pendente", self.save_pending)); root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.out=Label(text="", color=(0.8,1,0.8,1)); root.add_widget(self.out); self.add_widget(root)
    def payload(self):
        return {"device_id":self.app().device_id(),"day":self.day.text.strip(),"exercise":self.exercise.text.strip(),"weight":float(self.weight.text or 0),"reps":int(self.reps.text or 0),"sets":int(self.sets.text or 1),"rpe":float(self.rpe.text or 8),"notes":""}
    def save_online(self):
        p=self.payload()
        try:
            r=http_json("POST", self.app().api_url()+"/api/workout-log", self.app().token(), p); self.out.text="Salvo online."
        except Exception as e:
            self.save_pending(); self.out.text="Sem conexão. Ficou pendente. " + str(e)
    def save_pending(self):
        pending=load_json(app_path(PENDING_FILE), []); pending.append(self.payload()); save_json(app_path(PENDING_FILE), pending); self.out.text="Salvo como pendente."

class HistoryScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        root.add_widget(self.title("Histórico online")); root.add_widget(self.btn("Atualizar histórico", self.load_history))
        self.scroll=ScrollView(); self.box=BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None); self.box.bind(minimum_height=self.box.setter("height")); self.scroll.add_widget(self.box); root.add_widget(self.scroll)
        root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home"))); self.add_widget(root)
    def load_history(self):
        self.box.clear_widgets()
        try:
            logs=http_json("GET", self.app().api_url()+"/api/workout-log/"+self.app().device_id(), self.app().token())
            for l in logs[:80]: self.box.add_widget(Label(text=f"{l.get('created_at')} | {l.get('exercise')} | {l.get('weight')}kg x {l.get('reps')} | {l.get('sets')} séries", size_hint_y=None, height=dp(44), color=(0.88,0.93,1,1), halign="left"))
        except Exception as e: self.box.add_widget(Label(text="Erro: "+str(e), size_hint_y=None, height=dp(80), color=(1,0.7,0.7,1)))

class ProfileScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        root.add_widget(self.title("Perfil"))
        self.name=TextInput(hint_text="Nome", multiline=False, size_hint_y=None, height=dp(44))
        self.age=TextInput(hint_text="Idade", multiline=False, input_filter="int", size_hint_y=None, height=dp(44))
        self.weight=TextInput(hint_text="Peso kg", multiline=False, input_filter="float", size_hint_y=None, height=dp(44))
        self.height=TextInput(hint_text="Altura cm", multiline=False, input_filter="float", size_hint_y=None, height=dp(44))
        self.goal=TextInput(text="Hipertrofia e ganho de massa", multiline=False, size_hint_y=None, height=dp(44))
        for w in [self.name,self.age,self.weight,self.height,self.goal]: root.add_widget(w)
        root.add_widget(self.btn("Salvar perfil online", self.save)); root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.out=Label(text="", color=(0.8,1,0.8,1)); root.add_widget(self.out); self.add_widget(root)
    def save(self):
        p={"device_id":self.app().device_id(),"name":self.name.text,"age":int(self.age.text or 0),"weight":float(self.weight.text or 0),"height":float(self.height.text or 0),"goal":self.goal.text,"level":"Voltando"}
        try: http_json("POST", self.app().api_url()+"/api/profile", self.app().token(), p); self.out.text="Perfil salvo online."
        except Exception as e: self.out.text="Erro: "+str(e)

class MeasureScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8)); root.add_widget(self.title("Medidas"))
        self.bw=TextInput(hint_text="Peso corporal", input_filter="float", multiline=False, size_hint_y=None, height=dp(44))
        self.chest=TextInput(hint_text="Peito cm", input_filter="float", multiline=False, size_hint_y=None, height=dp(44))
        self.arm=TextInput(hint_text="Braço cm", input_filter="float", multiline=False, size_hint_y=None, height=dp(44))
        self.waist=TextInput(hint_text="Cintura cm", input_filter="float", multiline=False, size_hint_y=None, height=dp(44))
        self.leg=TextInput(hint_text="Perna cm", input_filter="float", multiline=False, size_hint_y=None, height=dp(44))
        for w in [self.bw,self.chest,self.arm,self.waist,self.leg]: root.add_widget(w)
        root.add_widget(self.btn("Salvar medidas online", self.save)); root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home")))
        self.out=Label(text="", color=(0.8,1,0.8,1)); root.add_widget(self.out); self.add_widget(root)
    def save(self):
        p={"device_id":self.app().device_id(),"body_weight":float(self.bw.text or 0),"chest":float(self.chest.text or 0),"arm":float(self.arm.text or 0),"waist":float(self.waist.text or 0),"leg":float(self.leg.text or 0),"notes":""}
        try: http_json("POST", self.app().api_url()+"/api/measurement", self.app().token(), p); self.out.text="Medidas salvas."
        except Exception as e: self.out.text="Erro: "+str(e)

class ProgressScreen(BaseScreen):
    def on_pre_enter(self): self.build()
    def build(self):
        self.clear_widgets(); root=BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8)); root.add_widget(self.title("Progresso")); root.add_widget(self.btn("Carregar progresso", self.load))
        self.out=Label(text="Clique em carregar.", color=(0.86,0.94,1,1), halign="left", valign="top"); root.add_widget(self.out); root.add_widget(self.btn("Voltar", lambda: setattr(self.manager, "current", "home"))); self.add_widget(root)
    def load(self):
        try: self.out.text=json.dumps(http_json("GET", self.app().api_url()+"/api/progress/"+self.app().device_id(), self.app().token()), ensure_ascii=False, indent=2)
        except Exception as e: self.out.text="Erro: "+str(e)

class TreinoApp(App):
    def build(self):
        self.config_data=load_json(app_path(CONFIG_FILE), {"api_url":DEFAULT_API_URL,"token":DEFAULT_TOKEN,"device_id":str(uuid.uuid4())})
        if not self.config_data.get("device_id"): self.config_data["device_id"]=str(uuid.uuid4())
        save_json(app_path(CONFIG_FILE), self.config_data)
        default_content_path=os.path.join(os.path.dirname(__file__), "assets", "default_content.json")
        self.content=load_json(app_path(CACHE_FILE), load_json(default_content_path, {"weekly_plan":[]}))
        sm=ScreenManager()
        for cls, name in [(HomeScreen,"home"),(ConfigScreen,"config"),(SyncScreen,"sync"),(WorkoutScreen,"workout"),(TimerScreen,"timer"),(LogScreen,"log"),(HistoryScreen,"history"),(ProfileScreen,"profile"),(ProgressScreen,"progress"),(MeasureScreen,"measure")]: sm.add_widget(cls(name=name))
        return sm
    def api_url(self): return self.config_data.get("api_url", DEFAULT_API_URL).rstrip("/")
    def token(self): return self.config_data.get("token", DEFAULT_TOKEN)
    def device_id(self): return self.config_data.get("device_id") or str(uuid.uuid4())

if __name__ == "__main__": TreinoApp().run()
