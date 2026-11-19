# -*- coding: utf-8 -*-
"""
cielo_hoy.py · «Web · al día» · v0.2 (19/11/2026: suma semana(), para el tips semanal)

El cielo de hoy para la web, calculado con el motor de El Brujo (Swiss Ephemeris), igual para todos:
- los aspectos activos entre planetas (Sol a Plutón): cuál, a cuántos grados, si se está armando
  o deshaciendo, y el momento exacto en hora argentina;
- la Luna: signo, fase, iluminación y las próximas luna llena y luna nueva;
- los planetas que cambian de signo en los próximos 7 días y los retrógrados.

Solo datos calculados: no interpreta. La lectura del día la escribe tips.py.
Referencia del «hoy»: 12:00 hora argentina, como cielo_del_dia() de calculo_pregunta.
"""
from __future__ import annotations
import math
from datetime import datetime, timedelta
from functools import lru_cache

import pytz
import calculo_pregunta as cp      # fija las efemérides y trae el motor (cp.m) y swe
from calculo_pregunta import swe

TZ = pytz.timezone(cp.TZ_AR)
SIGNOS = ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", "Libra",
          "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"]
CUERPOS = [("Sol", swe.SUN), ("Mercurio", swe.MERCURY), ("Venus", swe.VENUS), ("Marte", swe.MARS),
           ("Júpiter", swe.JUPITER), ("Saturno", swe.SATURN), ("Urano", swe.URANUS),
           ("Neptuno", swe.NEPTUNE), ("Plutón", swe.PLUTO)]
LENTOS = {"Júpiter", "Saturno", "Urano", "Neptuno", "Plutón"}
ASPECTOS = [("conjunción", 0.0), ("sextil", 60.0), ("cuadratura", 90.0),
            ("trígono", 120.0), ("oposición", 180.0)]
NATURALEZA = {"conjunción": "fusión", "sextil": "armonía", "trígono": "armonía",
              "cuadratura": "tensión", "oposición": "tensión"}
ORBE_ACTIVO = 3.0      # grados: más abierto no se cuenta como «activo hoy»
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


def _pos(jd: float, cuerpo: int) -> tuple[float, float]:
    xx, _ = swe.calc_ut(jd, cuerpo, FLAGS)
    return xx[0], xx[3]


def _wrap(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0


def _fmt(lon: float) -> str:
    total = int(round(lon * 60)) % (360 * 60)
    return f"{(total // 60) % 30}°{total % 60:02d}' de {SIGNOS[total // 1800]}"


def _signo(lon: float) -> str:
    return SIGNOS[int(lon // 30) % 12]


def _jd(dt_local: datetime) -> float:
    u = dt_local.astimezone(pytz.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def _local(jd: float) -> datetime:
    y, mo, d, h = swe.revjul(jd, swe.GREG_CAL)
    return (pytz.utc.localize(datetime(y, mo, d)) + timedelta(hours=h)).astimezone(TZ)


def _hora_txt(jd: float) -> str:
    t = _local(jd)
    return t.strftime("%Y-%m-%d %H:%M")


def _raiz(f, a: float, b: float) -> float:
    fa = f(a)
    for _ in range(50):
        mid = (a + b) / 2
        fm = f(mid)
        if fa * fm <= 0:
            b = mid
        else:
            a, fa = mid, fm
    return (a + b) / 2


def _exacto(f, jd0: float, dias: float = 40, paso: float = 0.25) -> float | None:
    """El cruce por cero de f más cercano a jd0, buscando hacia atrás y hacia adelante."""
    mejor = None
    for sentido in (1, -1):
        t, ft = jd0, f(jd0)
        recorrido = 0.0
        while recorrido < dias:
            t2 = t + sentido * paso
            f2 = f(t2)
            if ft == 0 or (ft * f2 < 0 and abs(ft) < 20 and abs(f2) < 20):
                r = _raiz(f, min(t, t2), max(t, t2))
                if mejor is None or abs(r - jd0) < abs(mejor - jd0):
                    mejor = r
                break
            t, ft, recorrido = t2, f2, recorrido + paso
    return mejor


def _peso(a: str, b: str, asp: str) -> str:
    """El mismo criterio que la pestaña Aspectos (CIELO_aspectos_v1.py)."""
    la, lb = a in LENTOS, b in LENTOS
    duro = asp in ("conjunción", "cuadratura", "oposición")
    if la and lb:
        return "Alta" if duro else "Media"
    if (la or lb) and asp in ("conjunción", "oposición"):
        return "Media"
    if not la and not lb and asp == "conjunción":
        return "Media"
    return "Baja"


def aspectos_activos(jd: float) -> list[dict]:
    out = []
    for i, (na, ca) in enumerate(CUERPOS):
        for nb, cb in CUERPOS[i + 1:]:
            (la, va), (lb, vb) = _pos(jd, ca), _pos(jd, cb)
            sep = abs(_wrap(la - lb))
            for asp, ang in ASPECTOS:
                orbe = abs(sep - ang)
                if orbe > ORBE_ACTIVO:
                    continue
                # El ángulo con signo que tiene que llegar a ±ang (o a 0 / 180).
                objetivos = [ang] if ang in (0.0, 180.0) else [ang, -ang]
                obj = min(objetivos, key=lambda o: abs(_wrap(la - lb - o)))
                f = (lambda o: (lambda t: _wrap(_pos(t, ca)[0] - _pos(t, cb)[0] - o)))(obj)
                lentos = na in LENTOS and nb in LENTOS   # duran meses: se busca más lejos, a paso de un día
                jx = _exacto(f, jd, dias=420, paso=1.0) if lentos else _exacto(f, jd)
                out.append({
                    "a": na, "b": nb, "aspecto": asp, "angulo": int(ang),
                    "naturaleza": NATURALEZA[asp],
                    "orbe": round(orbe, 2),
                    "posicion_a": _fmt(la) + (" (retrógrado)" if va < 0 else ""),
                    "posicion_b": _fmt(lb) + (" (retrógrado)" if vb < 0 else ""),
                    "exacto": _hora_txt(jx) if jx else None,
                    "estado": (None if jx is None else ("se arma" if jx > jd else "se deshace")),
                    "peso": _peso(na, nb, asp),
                })
                break
    orden = {"Alta": 0, "Media": 1, "Baja": 2}
    return sorted(out, key=lambda x: (orden[x["peso"]], x["orbe"]))


def _proxima_fase(jd: float, objetivo: float) -> float | None:
    def f(t):
        return _wrap(_pos(t, swe.MOON)[0] - _pos(t, swe.SUN)[0] - objetivo)
    t, ft = jd, f(jd)
    for _ in range(int(32 / 0.25)):
        t2 = t + 0.25
        f2 = f(t2)
        if ft * f2 < 0 and abs(ft) < 30 and abs(f2) < 30:
            return _raiz(f, t, t2)
        t, ft = t2, f2
    return None


def luna(jd: float) -> dict:
    lon, _ = _pos(jd, swe.MOON)
    llena, nueva = _proxima_fase(jd, 180.0), _proxima_fase(jd, 0.0)
    d = {"signo": _signo(lon), "posicion": _fmt(lon), **cp._fase_luna(jd),
         "proxima_llena": None, "proxima_nueva": None}
    if llena:
        d["proxima_llena"] = {"cuando": _hora_txt(llena), "posicion": _fmt(_pos(llena, swe.MOON)[0])}
    if nueva:
        d["proxima_nueva"] = {"cuando": _hora_txt(nueva), "posicion": _fmt(_pos(nueva, swe.MOON)[0])}
    return d


def ingresos(jd: float, dias: int = 7) -> list[dict]:
    out = []
    for nombre, c in CUERPOS:
        t, s = jd, int(_pos(jd, c)[0] // 30)
        paso = 0.25
        while t < jd + dias:
            t2 = t + paso
            s2 = int(_pos(t2, c)[0] // 30)
            if s2 != s:
                def f(x, s2=s2):
                    return _wrap(_pos(x, c)[0] - s2 * 30.0) if s2 != (s + 1) % 12 else _wrap(_pos(x, c)[0] - s2 * 30.0)
                jx = _raiz(f, t, t2)
                out.append({"planeta": nombre, "entra_en": SIGNOS[s2], "cuando": _hora_txt(jx),
                            "retrogrado": _pos(jx, c)[1] < 0})
                s = s2
            t = t2
    return sorted(out, key=lambda x: x["cuando"])


@lru_cache(maxsize=8)
def cielo_hoy(fecha: str) -> dict:
    cp._efemerides_en_este_hilo()
    jd = _jd(TZ.localize(datetime.strptime(f"{fecha} 12:00", "%Y-%m-%d %H:%M")))
    base = cp.cielo_del_dia(fecha)
    return {
        "fecha": fecha,
        "referencia": "12:00 hora argentina",
        "posiciones": base["posiciones"],
        "retrogrados": base["retrogrados"],
        "luna": luna(jd),
        "aspectos": aspectos_activos(jd),
        "ingresos_7_dias": ingresos(jd),
        "efemerides": base["efemerides"],
        "motor": cp.m.VERSION,
    }


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


@lru_cache(maxsize=8)
def semana(fecha_lunes: str) -> dict:
    """El cielo de una semana (lunes a domingo), para el tips semanal (decisión de Fabricio, 19/11/2026:
    «en vez de un tips por día, uno por semana; los planetas no cambian todos los días»).
    Junta los aspectos activos algún día de la semana (el de menor orbe), marca los que se hacen exactos
    dentro de la semana, y suma las lunas y los cambios de signo de esos siete días."""
    cp._efemerides_en_este_hilo()
    lunes = datetime.strptime(fecha_lunes, "%Y-%m-%d")
    lunes = lunes - timedelta(days=lunes.weekday())          # por si llega otro día: se va al lunes
    jd0 = _jd(TZ.localize(lunes.replace(hour=0)))
    jd1 = jd0 + 7
    desde, hasta = _hora_txt(jd0), _hora_txt(jd1)
    juntos: dict[tuple, dict] = {}
    for d in range(7):
        jd = jd0 + d + 0.5
        for a in aspectos_activos(jd):
            k = (a["a"], a["b"], a["aspecto"])
            if k not in juntos or a["orbe"] < juntos[k]["orbe"]:
                juntos[k] = a
    aspectos = []
    for a in juntos.values():
        a = dict(a)
        a["exacto_en_la_semana"] = bool(a["exacto"] and desde <= a["exacto"] < hasta)
        if a["exacto_en_la_semana"]:
            t = datetime.strptime(a["exacto"], "%Y-%m-%d %H:%M")
            a["dia"] = f"{DIAS[t.weekday()]} {t.day}"
        aspectos.append(a)
    orden = {"Alta": 0, "Media": 1, "Baja": 2}
    aspectos.sort(key=lambda x: (not x["exacto_en_la_semana"], orden[x["peso"]], x["orbe"]))
    lunas = []
    for nombre, obj in (("luna llena", 180.0), ("luna nueva", 0.0)):
        t = _proxima_fase(jd0, obj)
        if t and t < jd1:
            lunas.append({"fase": nombre, "cuando": _hora_txt(t), "posicion": _fmt(_pos(t, swe.MOON)[0])})
    fin = lunes + timedelta(days=6)
    return {"semana": f"{lunes:%Y-%m-%d} al {fin:%Y-%m-%d}", "desde": desde, "hasta": hasta,
            "aspectos": aspectos, "lunas": lunas, "ingresos": ingresos(jd0, 7),
            "retrogrados": cp.cielo_del_dia(f"{lunes:%Y-%m-%d}")["retrogrados"],
            "efemerides": cp.cielo_del_dia(f"{lunes:%Y-%m-%d}")["efemerides"], "motor": cp.m.VERSION}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(cielo_hoy(sys.argv[1] if len(sys.argv) > 1 else datetime.now(TZ).date().isoformat()),
                     ensure_ascii=False, indent=1))
