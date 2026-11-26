# -*- coding: utf-8 -*-
"""
mensajes.py · respuestas a mensajes directos de Instagram, en borrador · v0.1 (26/11/2026)

Ficha aprobada por Fabricio el 26/11/2026 («OK a la ficha»): IA/PROPUESTA_n8n_mensajes-directos-IA_2026-11-26.md.
Mismo recorrido que comentarios.py (filtro fijo de crisis → Sonnet escribe → controles por código → Haiku revisa →
un segundo intento → «frenado»), con las reglas de lo privado y la conversación como contexto.
NADA de lo que sale de acá se manda solo: n8n lo deja en borrador y lo envía con el OK de Fabricio.

Estados: borrador · delicado · para_vos (pedido, pago o reclamo puntual: lo mira Fabricio) · sin_respuesta · frenado · error.

DATOS_VIGENTES sale del Catálogo del Sheets («Precio y cobro», «Flujo»). Si cambia el precio o la entrega, se cambia
acá el mismo día (y en las respuestas automáticas de Business Suite), con el OK de Fabricio.
"""
from __future__ import annotations
import json, os, re

import comentarios, filtros, modelo

AQUI = os.path.dirname(os.path.abspath(__file__))
PROMPT_ESCRIBE = open(os.path.join(AQUI, "prompts", "mensaje_v0.1.md"), encoding="utf-8").read()
PROMPT_REVISA = open(os.path.join(AQUI, "prompts", "revisor_mensaje_v0.1.md"), encoding="utf-8").read()
VERSION = "mensajes v0.1"

DATOS_VIGENTES = (
    "Precio: USD 10 por lectura para todo el mundo; en Argentina, $15.000 por lectura, por Mercado Pago. Desde otro país, "
    "USD 10 por PayPal. En un mismo pedido se pueden sumar hasta 14 lecturas.\n"
    "Cómo se pide: en elbrujolecturas.com, botón del pedido (elbrujolecturas.com/#pedido): se elige la lectura, se cargan "
    "los datos de nacimiento (fecha, hora, lugar y nombre completo como figura en el documento) y se paga ahí mismo.\n"
    "Entrega: la lectura llega siempre por mail, en PDF, con un link privado que vence a los 30 días. No se promete un plazo.\n"
    "Si no sabe la hora de nacimiento, igual se puede: la lectura dice hasta dónde llega sin ese dato.\n"
    "Pregunta gratis: en elbrujolecturas.com/?ir=pregunta, «Eso que te da vueltas»: una pregunta, con fecha, hora y lugar "
    "de nacimiento, una vez cada 10 días por mail. Responde leyendo el cielo de la carta, sin sí ni no.\n"
    "Las lunas de cada mes: gratis por mail, anotándose en la web.\n"
    "Las lecturas: Lectura Integral (las tres tradiciones juntas), Lectura natal, Tu nombre y tu fecha, Tus cuatro pilares, "
    "Tus décadas, Tu año personal, Sinastría, El año contado, Lectura del mes, Lunaciones, Retorno de Saturno o de Quirón, "
    "Tu próximo año, Progresiones y Lectura de un hijo o hija."
)

TIPOS = ["consulta", "precio_o_pedido", "pide_lectura", "sombra_propia", "esceptico", "para_vos", "delicado",
         "saludo", "insulto", "spam"]
REGLAS = ["R1", "LECTURA", "DATOS_PERSONA", "DATO", "DELICADO", "SOMBRA", "R11", "GENERO", "INSTR", "FORMA"]
ESQ_ESCRIBE = {"type": "object", "additionalProperties": False, "required": ["respuesta", "tipo", "responder"],
               "properties": {"respuesta": {"type": "string"}, "tipo": {"type": "string", "enum": TIPOS},
                              "responder": {"type": "boolean"}}}
ESQ_REVISA = comentarios.ESQ_REVISA | {"properties": {
    "pasa": {"type": "boolean"}, "reglas": {"type": "array", "items": {"type": "string", "enum": REGLAS}},
    "motivo": {"type": "string"}}}

FUTURO = comentarios.FUTURO
_EXCUSA = re.compile(r"\b(si|cu[aá]ndo|qu[eé]|c[oó]mo|no|ni|nadie|pregunt[aá]s|ped[ií]s|saber)\b", re.I)


def promete_futuro(txt: str) -> bool:
    """«va a volver» es promesa salvo cuando repite la pregunta o la niega («no puedo decirte si va a volver»)."""
    for mt in FUTURO.finditer(txt):
        if not _EXCUSA.search(txt[max(0, mt.start() - 30):mt.start()]):
            return True
    return False
PRECIO_RARO = re.compile(r"(\$\s?\d[\d.]*|usd\s?\d+|\d+\s?d[oó]lares)", re.I)
PRECIOS_OK = {"$15.000", "$ 15.000", "usd 10", "usd10", "10 dólares", "10 dolares"}


def controles_codigo(salida: dict) -> list[str]:
    txt = (salida.get("respuesta") or "").strip()
    fallas = []
    if salida.get("responder") and not txt:
        fallas.append("FORMA:vacía")
    if len(txt.split()) > 80:
        fallas.append(f"FORMA:largo={len(txt.split())}")
    if len(comentarios.EMOJI.findall(txt)) > (0 if salida.get("tipo") == "delicado" else 1):
        fallas.append("FORMA:emojis")
    if promete_futuro(txt):
        fallas.append("R1:futuro")
    for m in PRECIO_RARO.findall(txt):
        if m.strip().lower() not in PRECIOS_OK:
            fallas.append(f"DATO:precio «{m}»")
    return fallas


def armar_mensaje(conversacion: list[dict], cielo: dict) -> str:
    c = {k: v for k, v in cielo.items() if k not in ("efemerides", "motor")}
    conv = [{"de": m.get("de", "persona"), "texto": str(m.get("texto", ""))[:1500]} for m in conversacion[-8:]]
    return (f"<datos_vigentes>\n{DATOS_VIGENTES}\n</datos_vigentes>\n"
            f"<cielo_de_hoy>\n{json.dumps(c, ensure_ascii=False, default=str)}\n</cielo_de_hoy>\n"
            f"<conversacion>\n{json.dumps(conv, ensure_ascii=False)}\n</conversacion>")


def borrador(conversacion: list[dict], cielo: dict | None = None, escribir=None, revisar=None) -> dict:
    """conversacion: [{de: "persona"|"brujo", texto}], la última es de la persona.
    Devuelve {estado, tipo, borrador, reglas, motivo, intentos, uso, version}."""
    escribir = escribir or (lambda s, m: comentarios._llamar(modelo.MODELO_SONNET, s, m, ESQ_ESCRIBE))
    revisar = revisar or (lambda s, m: comentarios._llamar(modelo.MODELO_REVISOR, s, m, ESQ_REVISA))
    base = {"version": VERSION, "reglas": [], "motivo": "", "intentos": 0, "uso": []}
    de_persona = [m for m in conversacion if m.get("de") == "persona" and str(m.get("texto", "")).strip()]
    if not de_persona:
        return {**base, "estado": "sin_respuesta", "tipo": "spam", "borrador": ""}
    ultimos = " ".join(str(m["texto"]) for m in de_persona[-3:])
    if any(re.search(x, filtros._plano(ultimos)) for x in filtros.CRISIS):
        return {**base, "estado": "delicado", "tipo": "delicado", "borrador": filtros.RESPUESTAS["crisis"], "reglas": ["R6"]}
    try:
        cielo = cielo if cielo is not None else comentarios._cielo_hoy()
        msg = armar_mensaje(conversacion, cielo)
        nota, ultimo = "", None
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
                estado = {"delicado": "delicado", "para_vos": "para_vos"}.get(salida["tipo"], "borrador")
                return {**base, "estado": estado, "tipo": salida["tipo"], "borrador": salida["respuesta"].strip()}
            ultimo = {"reglas": reglas, "motivo": veredicto.get("motivo", ""), "salida": salida}
            nota = (f"\n<correccion>\nUn borrador anterior no pasó la revisión: {', '.join(reglas)}. "
                    f"{veredicto.get('motivo', '')} Escribí uno nuevo que no tenga ese problema.\n</correccion>")
        s = (ultimo or {}).get("salida") or {}
        return {**base, "estado": "frenado", "tipo": s.get("tipo", "consulta"), "borrador": (s.get("respuesta") or "").strip(),
                "reglas": (ultimo or {}).get("reglas", []), "motivo": (ultimo or {}).get("motivo", "")}
    except Exception as e:
        return {**base, "estado": "error", "tipo": None, "borrador": "", "motivo": repr(e)[:300]}
