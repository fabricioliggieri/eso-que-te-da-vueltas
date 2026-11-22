# -*- coding: utf-8 -*-
"""
calculo_pregunta.py · «Eso que te da vueltas» · v0.1 (15/11/2026)

Envuelve al motor de El Brujo (elbrujo_calculo.py v8.9) SIN tocarlo y devuelve lo justo
para responder una pregunta: datos natales comprobables, el cielo del día (calculado una
vez por día y guardado) y los cruces más cerrados del cielo de hoy sobre la carta.

Regla R8: sin hora de nacimiento no se publican Luna, Ascendente, MC ni pilar de hora.
"""
from __future__ import annotations
import os, sys, json, math
from datetime import datetime, date
from functools import lru_cache

AQUI = os.path.dirname(os.path.abspath(__file__))
MOTOR = os.path.join(os.path.dirname(AQUI), "motor")
sys.path.insert(0, MOTOR)
os.environ.setdefault("ELBRUJO_EPHE", r"C:\ElBrujo\ephe")

import swisseph as swe          # noqa: E402
import pytz                     # noqa: E402
import elbrujo_calculo as m     # noqa: E402

# Las efemerides se fijan al importar: sin esto, el cielo del día calculado antes de la primera carta
# caía a Moshier (encontrado el 15/11 al probar el servicio). En el servidor van dentro de la imagen.
m.asegurar_efemerides(descargar=False)


def _efemerides_en_este_hilo() -> None:
    """pyswisseph guarda la carpeta de efemérides POR HILO: el servicio atiende cada pedido en otro hilo
    y, sin esto, el cálculo caía a Moshier sin avisar. Se fija antes de cada cálculo (no cuesta nada)."""
    swe.set_ephe_path(m.EPHE_DIR)

TZ_AR = "America/Argentina/Buenos_Aires"
# Punto de referencia del «cielo de hoy»: Buenos Aires, 12:00 hora argentina.
REF_LAT, REF_LON = -34.6037, -58.3816

DM_IMAGEN = {  # Identidad, fila «Día Maestro por imagen» (núcleo 3.ter.3)
    "Jia": "el roble", "Yi": "la enredadera", "Bing": "el sol", "Ding": "la vela",
    "Wu": "la montaña", "Ji": "el campo cultivado", "Geng": "el hierro",
    "Xin": "la joya", "Ren": "el río", "Gui": "la lluvia",
}
GLOSARIO = {  # Identidad, fila «Glosario llano» (núcleo 3.novena.5)
    "Sol": "lo que sos cuando estás en tu centro",
    "Luna": "cómo necesitás sentirte para estar bien",
    "Mercurio": "cómo pensás y hablás",
    "Venus": "cómo querés y qué te atrae",
    "Marte": "cómo actuás y cómo peleás",
    "Júpiter": "dónde crecés y confiás",
    "Saturno": "dónde te exigís y dónde construís",
    "Urano": "lo que te hace distinto",
    "Neptuno": "lo que te disuelve los bordes",
    "Plutón": "dónde te transformás",
    "Nodo N": "hacia dónde vas",
    "Ascendente": "cómo salís al mundo",
}
NATALES = ["Sol", "Luna", "Mercurio", "Venus", "Marte", "Júpiter", "Saturno"]
CIELO = ["Sol", "Luna", "Mercurio", "Venus", "Marte", "Júpiter", "Saturno",
         "Urano", "Neptuno", "Plutón"]
ASPECTO_LLANO = {"conjunción": "se junta con", "oposición": "queda enfrente de",
                 "trígono": "acompaña a", "cuadratura": "tensa a", "sextil": "le abre una puerta a"}


def _jd_local(fecha: str, hora: str, tz: str) -> float:
    dt = pytz.timezone(tz).localize(datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M"))
    u = dt.astimezone(pytz.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60)


def _fase_luna(jd: float) -> dict:
    # v0.2 (22/11/2026): la fase la da el motor 9.1 (m.fase_luna, mismo criterio). Pedido de Fabricio:
    # «todo se basa en el 9.0». Lo de abajo queda solo si el motor es anterior a la 9.1.
    if hasattr(m, "fase_luna"):
        return m.fase_luna(jd)
    sol = swe.calc_ut(jd, swe.SUN)[0][0]
    luna = swe.calc_ut(jd, swe.MOON)[0][0]
    elong = (luna - sol) % 360
    ilum = round((1 - math.cos(math.radians(elong))) / 2 * 100)
    if elong < 10 or elong > 350: nombre = "luna nueva"
    elif elong < 80: nombre = "creciente"
    elif elong < 100: nombre = "cuarto creciente"
    elif elong < 170: nombre = "gibosa creciente"
    elif elong < 190: nombre = "luna llena"
    elif elong < 260: nombre = "gibosa menguante"
    elif elong < 280: nombre = "cuarto menguante"
    else: nombre = "menguante"
    return {"fase": nombre, "iluminada_pct": ilum}


@lru_cache(maxsize=4)
def cielo_del_dia(fecha: str) -> dict:
    """El cielo de un día (12:00 hora argentina, Buenos Aires). Igual para todos: se calcula una vez."""
    _efemerides_en_este_hilo()
    jd = _jd_local(fecha, "12:00", TZ_AR)
    carta = m.astro_jd(jd, REF_LAT, REF_LON, sin_hora=True)
    pos = carta["pos"]
    B = m.bazi(fecha, "12:00", TZ_AR, REF_LON)
    return {
        "fecha": fecha,
        "posiciones": {k: pos[k]["fmt"] + (" (retrógrado)" if pos[k]["retro"] else "")
                       for k in CIELO if k in pos},
        "retrogrados": [k for k in CIELO if k in pos and pos[k]["retro"]],
        "luna": _fase_luna(jd),
        "pilar_dia_bazi": B.get("pilar_dia"),
        "efemerides": carta.get("efemerides"),
        "_pos": {k: v for k, v in pos.items()},
    }


def hechos(fecha_nac: str, hora_nac: str | None, lat: float, lon: float, tz: str,
           fecha_hoy: str | None = None) -> dict:
    """Todo lo que el Brujo puede usar para responder. Nada de esto viaja con email ni nombre."""
    fecha_hoy = fecha_hoy or date.today().isoformat()
    _efemerides_en_este_hilo()
    r = m.calcular({"fecha": fecha_nac, "hora": hora_nac, "lat": lat, "lon": lon,
                    "tz": tz, "fecha_consulta": fecha_hoy})
    A, N, B = r["astro"], r["num"], r["bazi"]
    sin_hora = bool(A.get("sin_hora"))
    natal = {}
    for k in NATALES:
        if k == "Luna" and sin_hora:
            continue
        natal[k] = {"posicion": A["pos"][k]["fmt"], "significa": GLOSARIO[k]}
    if not sin_hora:
        natal["Ascendente"] = {"posicion": A["asc"], "significa": GLOSARIO["Ascendente"]}
    dm = B["dia_maestro"]
    cielo = cielo_del_dia(fecha_hoy)
    if r["efemerides"] != "Swiss Ephemeris" or cielo["efemerides"] != "Swiss Ephemeris":
        raise RuntimeError(f"efemérides sin Swiss Ephemeris: carta={r['efemerides']} cielo={cielo['efemerides']}")

    # Cruces: el cielo de hoy (sin la Luna, que cambia en horas) sobre los puntos natales usables.
    hoy = {k: v for k, v in cielo["_pos"].items() if k in CIELO and k != "Luna"}
    nat = {k: v for k, v in A["pos"].items() if k in NATALES and not (k == "Luna" and sin_hora)}
    ejes = None if sin_hora else {"Ascendente": A["asc_deg"]}
    cruces = sorted(m.aspectos_cruzados(hoy, nat, ejes_b=ejes, orbe_max=2.0),
                    key=lambda c: c.get("orbe", 9))[:5]
    for c in cruces:  # «a» = cielo de hoy, «b» = punto natal
        c["en_llano"] = (f"{c['a']} de hoy {ASPECTO_LLANO.get(c['aspecto'].lower(), c['aspecto'].lower())} "
                         f"tu {c['b']} natal")

    return {
        "motor": r["version"], "efemerides": r["efemerides"],
        "sin_hora": sin_hora,
        "no_usar": (["Luna natal", "Ascendente", "casas", "pilar de hora"] if sin_hora else []),
        "natal": natal,
        "numerologia": {"camino_de_vida": N.get("camino"), "anio_personal": N.get("anio_personal")},
        "bazi": {"dia_maestro": f"{dm['tronco']} · {dm['descripcion']} · {DM_IMAGEN.get(dm['tronco'], '')}"},
        "cielo_de_hoy": {k: v for k, v in cielo.items() if not k.startswith("_")},
        "cruces_de_hoy": cruces,
    }


if __name__ == "__main__":
    h = hechos("1991-03-14", "08:20", -32.9468, -60.6393, "America/Argentina/Cordoba", "2026-11-15")
    print(json.dumps(h, ensure_ascii=False, indent=1, default=str))
