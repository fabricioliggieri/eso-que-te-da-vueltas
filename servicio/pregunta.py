# -*- coding: utf-8 -*-
"""
pregunta.py · «Eso que te da vueltas» · v0.1 (15/11/2026)

El recorrido entero, en el orden del brief v1.3 (§8.1):
filtros fijos → límites → cálculo → modelo (escribe) → controles por código → revisor → respuesta.
El modelo y el revisor se pasan como funciones: en la etapa B son de prueba (sin API);
en la etapa C se enchufa la API de Claude. Nunca se muestra algo que el revisor no pasó.
"""
from __future__ import annotations
import json, os, re
from datetime import datetime
import pytz

import filtros, limites, calculo_pregunta

AQUI = os.path.dirname(os.path.abspath(__file__))
TZ_AR = pytz.timezone("America/Argentina/Buenos_Aires")
SIN_PUERTA = {"salud", "embarazo", "duelo", "crisis"}
PROMPT_BRUJO = open(os.path.join(AQUI, "prompts", "brujo_v0.5.md"), encoding="utf-8").read()
PROMPT_REVISOR = open(os.path.join(AQUI, "prompts", "revisor_v0.3.md"), encoding="utf-8").read()

# «vas a…» es promesa salvo cuando repite la pregunta o la niega
# («Preguntás si te vas a…», «no digo qué va a pasar», «ni cuándo vas a…»). El juicio fino es del revisor.
FUTURO = re.compile(r"\b(vas a|va a (llegar|volver|pasar|salir)|te va a ir|"
                    r"el (proximo|próximo) (mes|año) (vas|va))\b", re.I)
_EXCUSA = re.compile(r"\b(si|cu[aá]ndo|qu[eé]|c[oó]mo|no|ni|pregunt[aá]s|ped[ií]s)\b", re.I)


def promete_futuro(txt: str) -> bool:
    for m in FUTURO.finditer(txt):
        antes = txt[max(0, m.start() - 30):m.start()]
        if not _EXCUSA.search(antes):
            return True
    return False
SI_NO = re.compile(r"^\s*(s[ií]|no)[\s,.!:]", re.I)


def controles_codigo(salida: dict, hechos: dict) -> list[str]:
    """Lo que se puede chequear sin modelo, antes del revisor."""
    fallas = []
    txt = (salida.get("respuesta") or "").strip()
    n = len(txt.split())
    if not txt or n > 130:
        fallas.append(f"FORMA:largo={n}")
    if SI_NO.search(txt):
        fallas.append("R1:empieza con sí/no")
    if promete_futuro(txt):
        fallas.append("R1:futuro")
    if salida.get("tipo") in SIN_PUERTA and salida.get("puerta"):
        fallas.append("R2:puerta en tema sin puerta")
    if hechos.get("sin_hora") and re.search(r"\b(Luna natal|Ascendente|casa \d|pilar de hora)\b", txt, re.I):
        fallas.append("R8")
    return fallas


def armar_mensaje(hechos: dict, pregunta: str) -> str:
    h = {k: v for k, v in hechos.items() if k not in ("motor", "efemerides")}
    return (f"<hechos>\n{json.dumps(h, ensure_ascii=False, default=str)}\n</hechos>\n"
            f"<pregunta>\n{json.dumps(pregunta, ensure_ascii=False)}\n</pregunta>")


def responder(datos: dict, escribir, revisar, con, ahora: datetime | None = None,
              detectar_crisis=None) -> dict:
    """datos: email, ip, fecha (AAAA-MM-DD), hora (HH:MM o None), lat, lon, tz, pregunta.
    escribir(system, mensaje) -> dict ; revisar(system, mensaje) -> dict.
    Devuelve lo que ve la persona y lo que se registra (sin email ni datos de nacimiento)."""
    ahora = ahora or datetime.now(TZ_AR).replace(tzinfo=None)
    registro = {"fecha": ahora.date().isoformat(), "pregunta": datos["pregunta"], "respuesta_mostrada": None,
                "respuesta_generada": None, "tipo": None, "puerta": None, "regla": "", "alerta": False}

    fijo = filtros.revisar(datos["pregunta"], datos["fecha"], ahora.date())
    if fijo:
        if not fijo["guardar_texto"]:
            registro["pregunta"] = f"[{fijo['tipo']}: texto no guardado]"
        registro.update(respuesta_mostrada=fijo["texto"], tipo=fijo["tipo"], regla=fijo["regla"],
                        alerta=fijo["tipo"] == "crisis")
        return {"texto": fijo["texto"], "estado": "fijo", "registro": registro}

    res = limites.reservar(con, datos["email"], datos.get("ip", ""), ahora)
    if not res["ok"] and detectar_crisis is not None:
        # Nadie en riesgo recibe «volvé mañana»: si la pregunta muestra riesgo, va la respuesta de cuidado
        # aunque haya tope (una clasificación chica con Haiku; si falla, se asume que sí hay riesgo).
        try:
            riesgo = detectar_crisis(datos["pregunta"])
        except Exception:
            riesgo = True
        if riesgo:
            registro.update(pregunta="[crisis con tope alcanzado: texto no guardado]",
                            respuesta_mostrada=filtros.RESPUESTAS["crisis"], tipo="crisis", regla="R6", alerta=True)
            return {"texto": filtros.RESPUESTAS["crisis"], "estado": "crisis", "registro": registro}
    if not res["ok"]:
        # Desde el 15/11/2026, el tope por hora tiene su propio aviso («volvé en un rato»); IP y día siguen con «tope».
        clave = res["motivo"] if res["motivo"] in ("email_10_dias", "tope_hora") else "tope"
        prox = res.get("proxima", "")
        prox = f"{prox[8:10]}/{prox[5:7]}" if len(prox) == 10 else prox  # «25/11»
        texto = filtros.RESPUESTAS[clave].format(proxima=prox)
        return {"texto": texto, "estado": "limite", "motivo": res["motivo"], "registro": None}

    try:
        hechos = calculo_pregunta.hechos(datos["fecha"], datos.get("hora"), datos["lat"], datos["lon"],
                                         datos["tz"], ahora.date().isoformat())
        msg = armar_mensaje(hechos, datos["pregunta"])
        salida = escribir(PROMPT_BRUJO, msg)
        registro.update(respuesta_generada=salida.get("respuesta"), tipo=salida.get("tipo"),
                        puerta=salida.get("puerta"))
        fallas = controles_codigo(salida, hechos)
        veredicto = {"pasa": True, "reglas": []}
        if not fallas:
            veredicto = revisar(PROMPT_REVISOR, msg + f"\n<respuesta>\n{salida.get('respuesta')}\n</respuesta>")
        reglas = fallas + list(veredicto.get("reglas", []))
        if salida.get("tipo") == "crisis" or "R6" in reglas:
            # Riesgo que el filtro fijo no vio: va la respuesta de cuidado, nunca la neutra.
            texto = filtros.RESPUESTAS["crisis"]
            registro.update(pregunta="[crisis detectada por el modelo: texto no guardado]",
                            respuesta_mostrada=texto, respuesta_generada=None, tipo="crisis",
                            puerta=None, regla=",".join(reglas) or "R6", alerta=True)
            limites.cerrar(con, res["id"], "fijo")
            return {"texto": texto, "estado": "crisis", "registro": registro}
        if fallas or not veredicto.get("pasa", False):
            texto = filtros.RESPUESTAS["revisor"]
            registro.update(respuesta_mostrada=texto, regla=",".join(reglas), alerta=True)
            limites.cerrar(con, res["id"], "fijo")
            return {"texto": texto, "estado": "frenada", "registro": registro}
        registro.update(respuesta_mostrada=salida["respuesta"])
        limites.cerrar(con, res["id"], "respondido")
        return {"texto": salida["respuesta"], "puerta": salida.get("puerta"), "estado": "respondida",
                "registro": registro}
    except Exception as e:  # el cupo se devuelve
        limites.cerrar(con, res["id"], "fallido")
        return {"texto": filtros.RESPUESTAS["error"], "estado": "error", "error": repr(e), "registro": None}
