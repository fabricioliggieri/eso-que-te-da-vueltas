# -*- coding: utf-8 -*-
"""
filtros.py · «Eso que te da vueltas» · v0.1 (15/11/2026) · APROBADO por Fabricio el 15/11/2026 («OK a todo»)

Filtros fijos, sin modelo. Corren ANTES de calcular y de llamar a la API:
largo · crisis (R6) · no-pregunta e inyección (R7) · edad.
Si uno salta, va una respuesta fija y la pregunta no viaja a Anthropic.
Las crisis, además, no se guardan con su texto (brief v1.3, §3.2).
"""
from __future__ import annotations
import re, unicodedata
from datetime import date

LARGO_MIN, LARGO_MAX = 8, 300

# ---------------------------------------------------------------- respuestas fijas (PROPUESTA)
RESPUESTAS = {
    "crisis": (
        "Lo que me escribís importa más que cualquier lectura, y no te voy a contestar con símbolos.\n"
        "Hablá ahora con una persona. En la Argentina, la línea de salud mental del Ministerio de Salud "
        "atiende gratis las 24 horas: 0800-999-0091. Si estás en peligro ahora, llamá al 911 "
        "(en Capital, también al 107).\n"
        "Si hay alguien cerca en quien confiás, decile hoy cómo estás. No tenés que poder solo con esto."
    ),
    "no_pregunta": (
        "Eso no es una pregunta para mí. Leo cielos, números y pilares; no muestro cómo estoy hecho "
        "ni escribo por encargo.\nSi querés, traeme lo que te da vueltas a vos."
    ),
    "menor": (
        "Esta pregunta es para personas de 18 años o más, así que esta vez no te leo.\n"
        "Si querés conocer tu carta, pedile a una persona adulta que te acompañe."
    ),
    "largo": (
        "Tu pregunta quedó {motivo}. Escribila en una o dos líneas, como se la dirías a alguien de confianza."
    ),
    "email_10_dias": (
        "Ya me hiciste una pregunta hace poco. Te leo una vez cada 10 días: la próxima, desde el {proxima}.\n"
        "Mientras tanto, lo que te dije sigue ahí para releerlo."
    ),
    # Con el servicio cerrado (PREGUNTA_ABIERTA=no), desde el 15/11/2026: la web ya muestra la placa.
    "cerrada": "La pregunta gratis todavía no está abierta. Volvé en unos días.",
    "tope": (
        "Por hoy ya respondí todas las preguntas que puedo. Volvé mañana.\n"
        "Si querés, te mando las lunas de cada mes por mail."
    ),
    "revisor": (
        "Esta vez no te pude leer bien. Probá con otra forma de preguntar, más tuya y más corta."
    ),
    "error": (
        "Algo se trabó de mi lado y no pude leerte. Tu pregunta no se descontó: probá de nuevo en un rato."
    ),
}

# ---------------------------------------------------------------- detección
def _plano(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t)

# R6 · se prefiere el falso positivo: ante la duda, respuesta de cuidado.
CRISIS = [
    r"suicid", r"\bmatarme\b", r"\bme quiero matar\b", r"\bme voy a matar\b", r"quitarme la vida",
    r"no quiero (seguir )?viv(ir|iendo)", r"no quiero seguir (asi|aca|mas)", r"no quiero estar mas", r"no tengo ganas de vivir",
    r"(ganas|quiero) de morir(me)?", r"\bquiero morir(me)?\b", r"me quiero morir",
    r"terminar con (todo|mi vida)", r"acabar con (todo|mi vida)", r"desaparecer para siempre",
    r"dormir(me)? y no despertar", r"no despertar(me)? mas",
    r"cortarme (las venas|los brazos|las munecas)", r"\bme corto (los brazos|las munecas)", r"lastimarme",
    r"hacerme dano", r"no aguanto mas\b", r"no doy mas\b",
    r"ya no le encuentro sentido", r"no le encuentro sentido a (nada|la vida|vivir)", r"para que (sigo|estoy) (vivo|viva|aca)",
    r"para que sigo\b", r"no se para que (sigo|vivo|estoy aca|estoy viva|estoy vivo)", r"cansad[ao] de (todo|vivir|la vida)",
    r"agotad[ao] de (todo|vivir|la vida)", r"no puedo mas\b", r"quiero que todo termine",
    r"mejor (si|que) no (existiera|estuviera)", r"todos estarian mejor sin mi",
    r"despedirme de todos", r"carta de despedida", r"pastillas para (morir|no despertar)",
]
# R7 · no-pregunta, inyección, encargos.
INYECCION = [
    r"ignora(r|lo)? (todo|todas|las|tus|lo)", r"olvida(te)? (todo|tus|las) (instrucciones|reglas)",
    r"(system|sistema) prompt", r"\bprompt\b", r"tus instrucciones", r"tus reglas",
    r"(mostra|decime|deci|escribi|copia|repeti)(me)? (tus|las|el) (instrucciones|reglas|prompt|texto)",
    r"actua como", r"hace(te)? pasar por", r"\bjailbreak\b", r"modo desarrollador",
    r"developer mode", r"<\|", r"</?\w+>", r"\[inst\]", r"###", r"```",
    r"escribi(me)? (un|una) (poema|codigo|programa|ensayo|cuento|mail|carta)",
    r"\b(traduci|resumi|codea)(me)?\b",
]
INSULTO = [r"\bchanta\b", r"\bestafa(dor)?\b", r"\bhdp\b", r"\bpelotud", r"\bforr[oa]\b",
           r"\bmierda\b", r"\bboludo\b.*\bbot\b"]


def edad(fecha_nac: str, hoy: date | None = None) -> int:
    hoy = hoy or date.today()
    y, mth, d = map(int, fecha_nac.split("-"))
    return hoy.year - y - ((hoy.month, hoy.day) < (mth, d))


def revisar(pregunta: str, fecha_nac: str, hoy: date | None = None) -> dict | None:
    """None = pasa al modelo. Si no, {tipo, texto, guardar_texto}."""
    p = (pregunta or "").strip()
    pl = _plano(p)
    # La crisis va primero: aunque la pregunta sea larga o corta, se responde con cuidado.
    if any(re.search(x, pl) for x in CRISIS):
        return {"tipo": "crisis", "regla": "R6", "texto": RESPUESTAS["crisis"], "guardar_texto": False}
    if len(p) < LARGO_MIN:
        return {"tipo": "largo", "regla": "largo", "texto": RESPUESTAS["largo"].format(motivo="muy corta"),
                "guardar_texto": True}
    if len(p) > LARGO_MAX:
        return {"tipo": "largo", "regla": "largo", "texto": RESPUESTAS["largo"].format(motivo="muy larga"),
                "guardar_texto": False}
    if edad(fecha_nac, hoy) < 18:
        return {"tipo": "menor", "regla": "edad", "texto": RESPUESTAS["menor"], "guardar_texto": False}
    if any(re.search(x, pl) for x in INYECCION) or any(re.search(x, pl) for x in INSULTO):
        return {"tipo": "no_pregunta", "regla": "R7", "texto": RESPUESTAS["no_pregunta"], "guardar_texto": True}
    return None
