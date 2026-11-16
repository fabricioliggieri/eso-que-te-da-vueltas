# -*- coding: utf-8 -*-
"""
app.py · «Eso que te da vueltas» · servicio HTTP · v0.2 (16/11/2026: suma /lunas)

Lo llama SOLO n8n, por la red interna de Docker (no tiene puerto afuera ni dirección en Traefik).
- GET  /salud     → {ok, motor, efemerides}
- POST /pregunta  → lo que ve la persona + lo que se registra (sin email ni datos de nacimiento)
- POST /lunas     → alta a «Las lunas de tu mes»: valida email y Turnstile, devuelve huella y token de baja

Variables de entorno (las secretas las escribe Fabricio en el Entorno del proyecto en Hostinger):
  ANTHROPIC_API_KEY      clave de la API (secreta)
  PREGUNTA_TOKEN         token compartido con n8n (secreto): va en la cabecera X-Pregunta-Token
  TURNSTILE_SECRET       clave secreta de Cloudflare Turnstile (secreta); sin ella no se valida
  PREGUNTA_SAL           sal de las huellas de email e IP (secreta)
  PREGUNTA_TOPE_DIA      10 en producción oculta, 40 al abrir · PREGUNTA_TOPE_HORA 15
  PREGUNTA_ABIERTA       «si» o «no»: el interruptor del servicio
  PREGUNTA_DATOS         carpeta de las bases SQLite (volumen)
"""
from __future__ import annotations
import hmac, json, os, re, urllib.parse, urllib.request
from datetime import datetime, date

import pytz
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import calculo_pregunta, filtros, limites, lugares, lunas, modelo, pregunta

DATOS = os.environ.get("PREGUNTA_DATOS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos"))
os.makedirs(DATOS, exist_ok=True)
TOKEN = os.environ.get("PREGUNTA_TOKEN", "")
TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET", "")
TZ_AR = pytz.timezone("America/Argentina/Buenos_Aires")

app = FastAPI(title="El Brujo · Eso que te da vueltas", docs_url=None, redoc_url=None, openapi_url=None)
CON_LIM = limites.abrir(os.path.join(DATOS, "limites.sqlite"))
CON_LUG = lugares.abrir(os.path.join(DATOS, "lugares.sqlite"))
ESCRIBIR = modelo.escritor(modelo.MODELO_SONNET)
REVISAR = modelo.revisor()
DETECTAR_CRISIS = modelo.detector_crisis()


class Pedido(BaseModel):
    email: str = Field(max_length=200)
    fecha: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    hora: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    lugar: str = Field(max_length=200)
    pregunta: str = Field(max_length=1000)
    ip: str = Field(default="", max_length=64)
    turnstile: str = Field(default="", max_length=2048)


def _turnstile_ok(token: str, ip: str) -> bool:
    if not TURNSTILE_SECRET:  # sin clave configurada (pruebas en la PC) no se valida
        return True
    datos = urllib.parse.urlencode({"secret": TURNSTILE_SECRET, "response": token, "remoteip": ip}).encode()
    req = urllib.request.Request("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=datos)
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return bool(json.loads(r.read().decode()).get("success"))
    except Exception:
        return False


def _autorizado(token: str | None) -> None:
    """Sin PREGUNTA_TOKEN configurado, el servicio confía en la red interna (sin puertos afuera: solo
    n8n llega). Con token configurado, n8n tiene que mandarlo en X-Pregunta-Token."""
    if not TOKEN:
        return
    if not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401)


@app.get("/salud")
def salud():
    c = calculo_pregunta.cielo_del_dia(datetime.now(TZ_AR).date().isoformat())
    return {"ok": True, "motor": calculo_pregunta.m.VERSION, "efemerides": c["efemerides"],
            "abierta": os.environ.get("PREGUNTA_ABIERTA", "no") == "si"}


@app.post("/pregunta")
def preguntar(p: Pedido, x_pregunta_token: str | None = Header(default=None)):
    _autorizado(x_pregunta_token)
    if os.environ.get("PREGUNTA_ABIERTA", "no") != "si":
        return {"texto": filtros.RESPUESTAS["cerrada"], "estado": "cerrada", "registro": None}
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", p.email.strip()):
        return {"texto": "Revisá el mail: así no me llega.", "estado": "dato", "registro": None}
    try:
        date.fromisoformat(p.fecha)
    except ValueError:
        return {"texto": "Revisá la fecha de nacimiento.", "estado": "dato", "registro": None}
    if not _turnstile_ok(p.turnstile, p.ip):
        return {"texto": "No pude comprobar que seas una persona. Recargá la página y probá de nuevo.",
                "estado": "turnstile", "registro": None}
    lug = lugares.resolver(CON_LUG, p.lugar)
    if not lug:
        return {"texto": "No encuentro ese lugar. Escribilo como «Ciudad, Provincia, País».",
                "estado": "dato", "registro": None}
    datos = {"email": p.email, "ip": p.ip, "fecha": p.fecha, "hora": p.hora, "pregunta": p.pregunta,
             "lat": lug["lat"], "lon": lug["lon"], "tz": lug["tz"]}
    r = pregunta.responder(datos, ESCRIBIR, REVISAR, CON_LIM, detectar_crisis=DETECTAR_CRISIS)
    r.pop("error", None)  # el detalle técnico no sale del servicio
    if r.get("registro"):
        r["registro"]["estado"] = r["estado"]
    if r["estado"] in ("respondida", "frenada", "crisis"):
        # Para la pestaña Visitantes. n8n suma el email en claro solo si la persona marcó las lunas.
        r["visitante"] = {"huella": limites.huella(limites.normalizar_email(p.email)),
                          "fecha": p.fecha, "hora": p.hora or "", "lugar": p.lugar.strip(),
                          "ultima": datetime.now(TZ_AR).date().isoformat(),
                          "cantidad": limites.contar(CON_LIM, p.email),
                          # Para la pestaña Lunas (v0.2): n8n lo usa solo si la persona marcó las lunas
                          # y su fila es nueva. La huella de Lunas es la misma que la de Visitantes.
                          "token_lunas": lunas.token_baja()}
    return r


class AltaLunas(BaseModel):
    email: str = Field(max_length=200)
    ip: str = Field(default="", max_length=64)
    turnstile: str = Field(default="", max_length=2048)


@app.post("/lunas")
def alta_lunas(p: AltaLunas, x_pregunta_token: str | None = Header(default=None)):
    """Alta a «Las lunas de tu mes» desde la placa VI de la web (flujo «Lunas · alta»).
    Valida el email y Turnstile; devuelve la huella y un token de baja. No guarda nada.
    No depende de PREGUNTA_ABIERTA: las lunas siguen aunque la pregunta esté cerrada."""
    _autorizado(x_pregunta_token)
    if not lunas.email_valido(p.email):
        return {"estado": "dato", "texto": lunas.TEXTOS["dato"]}
    if not _turnstile_ok(p.turnstile, p.ip):
        return {"estado": "turnstile", "texto": lunas.TEXTOS["turnstile"]}
    return lunas.alta(p.email)
