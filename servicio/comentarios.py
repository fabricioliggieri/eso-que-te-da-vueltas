# -*- coding: utf-8 -*-
"""
comentarios.py · respuestas a comentarios de Instagram, en borrador · v0.1 (26/11/2026)

Ficha aprobada por Fabricio el 26/11/2026 («OK a la ficha»): IA/PROPUESTA_n8n_comentarios-instagram_2026-11-26.md.
Regla de tono: Identidad, fila «Sombra y empatía en las respuestas a comentarios» («Sí, va»).

NADA de lo que sale de acá se publica solo: n8n lo deja en borrador y lo publica recién con el OK de Fabricio.

Recorrido: filtro fijo de crisis (sin modelo) → Sonnet escribe → controles por código → Haiku revisa →
si no pasa, un segundo intento con el motivo → si tampoco, «frenado» (le llega a Fabricio sin aprobación rápida).

Estados:
  borrador      listo para aprobar
  delicado      duelo, salud, crisis: borrador de presencia, sin aprobación rápida
  sin_respuesta insulto o spam: se sugiere no responder
  frenado       el revisor no lo pasó dos veces: Fabricio escribe o descarta
  error         algo falló; n8n reintenta en la vuelta siguiente
"""
from __future__ import annotations
import json, os, re
from datetime import datetime
import pytz

import filtros, modelo

AQUI = os.path.dirname(os.path.abspath(__file__))
PROMPT_ESCRIBE = open(os.path.join(AQUI, "prompts", "comentario_v0.1.md"), encoding="utf-8").read()
PROMPT_REVISA = open(os.path.join(AQUI, "prompts", "revisor_comentario_v0.1.md"), encoding="utf-8").read()
TZ_AR = pytz.timezone("America/Argentina/Buenos_Aires")
VERSION = "comentarios v0.1"

TIPOS = ["elogio", "pregunta_dato", "pide_lectura", "sombra_propia", "esceptico", "delicado",
         "conversacion", "insulto", "spam"]
REGLAS = ["R1", "SIGNO", "DELICADO", "SOMBRA", "R11", "DATO", "VENTA", "GENERO", "INSTR", "FORMA"]
ESQ_ESCRIBE = {"type": "object", "additionalProperties": False, "required": ["respuesta", "tipo", "responder"],
               "properties": {"respuesta": {"type": "string"}, "tipo": {"type": "string", "enum": TIPOS},
                              "responder": {"type": "boolean"}}}
ESQ_REVISA = {"type": "object", "additionalProperties": False, "required": ["pasa", "reglas", "motivo"],
              "properties": {"pasa": {"type": "boolean"},
                             "reglas": {"type": "array", "items": {"type": "string", "enum": REGLAS}},
                             "motivo": {"type": "string"}}}

# Respuesta pública para comentarios con señales de crisis (filtro fijo). Corta, porque es un comentario
# público; las líneas completas van por mensaje. La decide Fabricio en cada caso: nunca sale sola.
CRISIS_PUBLICA = ("Lo que escribís me importa más que cualquier lectura. Si estás pasando algo muy difícil, "
                  "hablá ahora con alguien: en findahelpline.com están las líneas gratis de tu país. "
                  "Y si querés, escribime por mensaje.")

EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
FUTURO = re.compile(r"\b(vas a (tener|encontrar|conseguir|lograr|recibir)|te va a (ir|llegar|pasar)|va a (pasar|llegar|volver))\b", re.I)
PRECIO = re.compile(r"(\$\s?\d|usd|d[oó]lares|pesos)", re.I)


def _plano(t: str) -> str:
    return filtros._plano(t)


def controles_codigo(salida: dict) -> list[str]:
    txt = (salida.get("respuesta") or "").strip()
    fallas = []
    if salida.get("responder") and not txt:
        fallas.append("FORMA:vacía")
    if len(txt.split()) > 35:
        fallas.append(f"FORMA:largo={len(txt.split())}")
    if len(EMOJI.findall(txt)) > (0 if salida.get("tipo") == "delicado" else 1):
        fallas.append("FORMA:emojis")
    if FUTURO.search(txt):
        fallas.append("R1:futuro")
    if PRECIO.search(txt):
        fallas.append("VENTA:precio")
    return fallas


def armar_mensaje(comentario: str, pieza: str, cielo: dict) -> str:
    c = {k: v for k, v in cielo.items() if k not in ("efemerides", "motor")}
    return (f"<pieza>\n{json.dumps((pieza or '')[:1500], ensure_ascii=False)}\n</pieza>\n"
            f"<cielo_de_hoy>\n{json.dumps(c, ensure_ascii=False, default=str)}\n</cielo_de_hoy>\n"
            f"<comentario>\n{json.dumps(comentario, ensure_ascii=False)}\n</comentario>")


def _llamar(mod: str, system: str, mensaje: str, esquema: dict) -> tuple[dict | None, dict]:
    return modelo.leer(modelo.cliente().messages.create(**modelo.parametros(mod, system, mensaje, esquema)))


def _cielo_hoy() -> dict:
    import cielo_hoy
    return cielo_hoy.cielo_hoy(datetime.now(TZ_AR).date().isoformat())


def borrador(comentario: str, pieza: str = "", cielo: dict | None = None,
             escribir=None, revisar=None) -> dict:
    """Devuelve {estado, tipo, borrador, reglas, motivo, intentos, uso, version}.
    escribir/revisar(system, mensaje) -> (datos, uso): se pueden cambiar en las pruebas."""
    escribir = escribir or (lambda s, m: _llamar(modelo.MODELO_SONNET, s, m, ESQ_ESCRIBE))
    revisar = revisar or (lambda s, m: _llamar(modelo.MODELO_REVISOR, s, m, ESQ_REVISA))
    base = {"version": VERSION, "reglas": [], "motivo": "", "intentos": 0, "uso": []}
    texto = (comentario or "").strip()
    if not texto:
        return {**base, "estado": "sin_respuesta", "tipo": "spam", "borrador": ""}
    if any(re.search(x, _plano(texto)) for x in filtros.CRISIS):
        return {**base, "estado": "delicado", "tipo": "crisis", "borrador": CRISIS_PUBLICA, "reglas": ["R6"]}
    try:
        cielo = cielo if cielo is not None else _cielo_hoy()
        msg = armar_mensaje(texto, pieza, cielo)
        nota = ""
        ultimo = None
        for intento in (1, 2):
            base["intentos"] = intento
            salida, uso = escribir(PROMPT_ESCRIBE, msg + nota)
            base["uso"].append(uso)
            if salida is None:
                ultimo = {"reglas": ["INSTR"], "motivo": f"el modelo no respondió ({uso.get('stop')})", "salida": None}
                continue
            if not salida["responder"] or salida["tipo"] in ("insulto", "spam"):
                return {**base, "estado": "sin_respuesta", "tipo": salida["tipo"], "borrador": ""}
            fallas = controles_codigo(salida)
            veredicto = {"pasa": True, "reglas": [], "motivo": ""}
            if not fallas:
                v, uso2 = revisar(PROMPT_REVISA, msg + f"\n<borrador>\n{salida['respuesta']}\n</borrador>")
                base["uso"].append(uso2)
                veredicto = v or {"pasa": False, "reglas": ["INSTR"], "motivo": "revisor sin veredicto"}
            reglas = fallas + list(veredicto.get("reglas", []))
            if not reglas and veredicto.get("pasa"):
                estado = "delicado" if salida["tipo"] == "delicado" else "borrador"
                return {**base, "estado": estado, "tipo": salida["tipo"], "borrador": salida["respuesta"].strip()}
            ultimo = {"reglas": reglas, "motivo": veredicto.get("motivo", ""), "salida": salida}
            nota = (f"\n<correccion>\nUn borrador anterior no pasó la revisión: {', '.join(reglas)}. "
                    f"{veredicto.get('motivo', '')} Escribí uno nuevo que no tenga ese problema.\n</correccion>")
        s = (ultimo or {}).get("salida") or {}
        return {**base, "estado": "frenado", "tipo": s.get("tipo", "conversacion"),
                "borrador": (s.get("respuesta") or "").strip(),
                "reglas": (ultimo or {}).get("reglas", []), "motivo": (ultimo or {}).get("motivo", "")}
    except Exception as e:
        return {**base, "estado": "error", "tipo": None, "borrador": "", "motivo": repr(e)[:300]}
