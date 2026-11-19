# -*- coding: utf-8 -*-
"""
tips.py · «Web · al día» · tips de la semana · v0.2 (19/11/2026: se guarda y hasta dos intentos)

Decisiones de Fabricio (19/11/2026): un tips por semana (los lunes, con el cielo de lunes a domingo) y
«sale solo el tips a la web», sin OK de cada semana, si pasa la revisión.

- El cielo de la semana lo calcula el motor (cielo_hoy.semana). Nada inventado.
- Sonnet escribe SOLO el párrafo «Tips:» y dice qué hechos usó.
- La parte técnica (aspecto, grados, día y hora, qué quiere decir) la arma este código con los datos
  del motor: así no puede salir un grado o una hora mal escritos.
- Haiku revisa contra las reglas (R1, SIGNO, R11, R3, DATO, GENERO, FORMA, INSTR) y el código suma
  controles propios. Si no pasa, «publicar» es False y la web muestra solo la parte técnica.
"""
from __future__ import annotations
import json, os, re

import cielo_hoy
import modelo

AQUI = os.path.dirname(os.path.abspath(__file__))
PROMPT_TIPS = open(os.path.join(AQUI, "prompts", "tips_semana_v0.1.md"), encoding="utf-8").read()
PROMPT_REVISOR = open(os.path.join(AQUI, "prompts", "revisor_tips_v0.1.md"), encoding="utf-8").read()

REGLAS = ["R1", "SIGNO", "R11", "R3", "DATO", "GENERO", "FORMA", "INSTR"]
ESQ_TIPS = {"type": "object", "additionalProperties": False, "required": ["tips", "usados"],
            "properties": {"tips": {"type": "string"},
                           "usados": {"type": "array", "items": {"type": "integer"}}}}
ESQ_REV = {"type": "object", "additionalProperties": False, "required": ["pasa", "reglas", "motivo"],
           "properties": {"pasa": {"type": "boolean"},
                          "reglas": {"type": "array", "items": {"type": "string", "enum": REGLAS}},
                          "motivo": {"type": "string"}}}

QUE_ES = {  # el sentido llano de cada aspecto (el mismo que lee el prompt)
    "conjunción": "0°: dos fuerzas se juntan; lo que tocan se intensifica.",
    "sextil": "60°: se abre una puerta, pero hay que dar el paso.",
    "trígono": "120°: algo fluye con facilidad.",
    "cuadratura": "90°: fricción que empuja a mover algo que estaba quieto.",
    "oposición": "180°: dos fuerzas quedan enfrente y piden equilibrio.",
}
DIAS = cielo_hoy.DIAS
SIGNOS_GENTE = re.compile(r"\b(los|las|les|para|si sos)\s+(de\s+)?(aries|tauro|géminis|geminis|cáncer|cancer|leo|virgo|"
                          r"libra|escorpio|sagitario|capricornio|acuario|piscis)\b", re.I)
FUTURO = re.compile(r"\b(va a pasar|vas a|te va a ir|va a llegar|ocurrirá|sucederá)\b", re.I)


def _dia_hora(txt: str) -> str:
    from datetime import datetime
    t = datetime.strptime(txt, "%Y-%m-%d %H:%M")
    return f"{DIAS[t.weekday()]} {t.day}, {t:%H:%M}"


def hechos(sem: dict) -> list[dict]:
    """Los hechos de la semana, numerados, en el orden en que pesan. Es lo que lee Sonnet y lo que
    usa el código para la parte técnica."""
    out = []
    for l in sem["lunas"]:
        out.append({"tipo": "luna", "que": l["fase"], "cuando": l["cuando"], "posicion": l["posicion"]})
    for a in sem["aspectos"]:
        if a["exacto_en_la_semana"] or (a["peso"] in ("Alta", "Media") and a["orbe"] <= 2):
            out.append({"tipo": "aspecto", "que": f"{a['a']} {a['aspecto']} {a['b']}", "aspecto": a["aspecto"],
                        "a": a["a"], "b": a["b"], "peso": a["peso"],
                        "cuando": a["exacto"] if a["exacto_en_la_semana"] else None,
                        "posiciones": [a["posicion_a"], a["posicion_b"]],
                        "estado": "exacto esta semana" if a["exacto_en_la_semana"] else
                                  f"activo toda la semana (exacto el {a['exacto'][:10]})" if a["exacto"] else "activo toda la semana"})
    for i in sem["ingresos"]:
        out.append({"tipo": "ingreso", "que": f"{i['planeta']} entra en {i['entra_en']}", "cuando": i["cuando"]})
    for n, h in enumerate(out, 1):
        h["n"] = n
    return out


def tecnica(h: dict) -> dict:
    """Una línea técnica, corta, armada por código (fecha, hora, grados, qué es)."""
    if h["tipo"] == "luna":
        return {"titulo": h["que"].capitalize(), "cuando": _dia_hora(h["cuando"]) + " (hora argentina)",
                "grados": f"Luna a {h['posicion']}",
                "que_es": "La Luna queda frente al Sol (180°)." if h["que"] == "luna llena"
                          else "La Luna se junta con el Sol (0°): empieza el ciclo."}
    if h["tipo"] == "ingreso":
        return {"titulo": h["que"], "cuando": _dia_hora(h["cuando"]) + " (hora argentina)", "grados": "0°", "que_es": ""}
    return {"titulo": h["que"], "cuando": (_dia_hora(h["cuando"]) + " (hora argentina)") if h["cuando"] else h["estado"],
            "grados": " · ".join(h["posiciones"]), "que_es": f"{h['aspecto'].capitalize()}, {QUE_ES[h['aspecto']]}"}


def controles_codigo(texto: str) -> list[str]:
    malos = []
    if not texto.startswith("Tips: "):
        malos.append("FORMA")
    if len(texto.split()) > 120 or "\n" in texto.strip():
        malos.append("FORMA")
    if SIGNOS_GENTE.search(texto):
        malos.append("SIGNO")
    if FUTURO.search(texto):
        malos.append("R1")
    return sorted(set(malos))


def _llamar(system: str, mensaje: str, esquema: dict, modelo_id: str) -> tuple[dict | None, dict]:
    return modelo.leer(modelo.cliente().messages.create(**modelo.parametros(modelo_id, system, mensaje, esquema)))


ARCHIVO = os.path.join(os.environ.get("PREGUNTA_DATOS", os.path.join(AQUI, "datos")), "tips_semana.json")


def guardar(r: dict) -> None:
    """Guarda el tips de la semana en el volumen de datos (se pisa la semana anterior; la historia queda
    en la planilla que escribe n8n). Escritura atómica: nunca queda un archivo a medias."""
    sin_uso = {k: v for k, v in r.items() if k != "uso"}
    os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
    tmp = ARCHIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sin_uso, f, ensure_ascii=False)
    os.replace(tmp, ARCHIVO)


def guardado() -> dict | None:
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def tips_semana(fecha_lunes: str, intentos: int = 2) -> dict:
    """Hasta dos intentos: si el primero no pasa la revisión, se escribe otro (en las pruebas del 19/11,
    1 de 6 lo frenó el revisor). Si ninguno pasa, sale solo la parte técnica."""
    r = None
    for i in range(intentos):
        r = _un_intento(fecha_lunes)
        r["intento"] = i + 1
        if r["publicar"]:
            break
    return r


def _un_intento(fecha_lunes: str) -> dict:
    sem = cielo_hoy.semana(fecha_lunes)
    hs = hechos(sem)
    msg = "<cielo_semana>\n" + json.dumps({"semana": sem["semana"], "retrogrados": sem["retrogrados"],
                                            "hechos": hs}, ensure_ascii=False, indent=1) + "\n</cielo_semana>"
    salida, uso_t = _llamar(PROMPT_TIPS, msg, ESQ_TIPS, modelo.MODELO_SONNET)
    texto = (salida or {}).get("tips", "").strip()
    usados = [n for n in (salida or {}).get("usados", []) if 1 <= n <= len(hs)] or [h["n"] for h in hs[:2]]
    reglas, motivo, uso_r = controles_codigo(texto) if texto else ["FORMA"], "", None
    if texto:
        rev, uso_r = _llamar(PROMPT_REVISOR, msg + f"\n<tips>\n{texto}\n</tips>", ESQ_REV, modelo.MODELO_REVISOR)
        if rev is None:
            reglas, motivo = reglas + ["INSTR"], "revisor sin veredicto"
        else:
            reglas = sorted(set(reglas) | set(rev["reglas"]))
            motivo = rev["motivo"]
    return {
        "semana": sem["semana"],
        "publicar": bool(texto) and not reglas,
        "tips": texto if texto and not reglas else None,
        "borrador": texto,                       # se guarda siempre en la planilla, salga o no
        "reglas": reglas, "motivo": motivo,
        "tecnica": [tecnica(h) for h in hs if h["n"] in usados] + [tecnica(h) for h in hs if h["n"] not in usados],
        "usados": usados,
        "uso": {"tips": uso_t, "revisor": uso_r},
        "motor": sem["motor"], "efemerides": sem["efemerides"],
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(tips_semana(sys.argv[1] if len(sys.argv) > 1 else "2026-11-23"), ensure_ascii=False, indent=1))
