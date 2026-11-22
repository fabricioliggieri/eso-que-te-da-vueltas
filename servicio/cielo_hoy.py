"""
cielo_hoy.py · «Web · al día» · v0.3 (22/11/2026: todo el cálculo lo hace el motor 9.1)
El cielo de hoy para la web, calculado con el motor de El Brujo, igual para todos:
- los aspectos activos entre planetas (Sol a Plutón): cuál, a cuántos grados, si se está armando
  o deshaciendo, y el momento exacto en hora argentina;
- la Luna: signo, fase, iluminación y las próximas luna llena y luna nueva;
- los planetas que cambian de signo en los próximos 7 días y los retrógrados.
Solo datos calculados: no interpreta. La lectura del día la escribe tips.py.
Referencia del «hoy»: 12:00 hora argentina, como cielo_del_dia() de calculo_pregunta.
v0.3: hasta la v0.2 los aspectos, las fases y los cambios de signo se calculaban acá con las
efemérides del motor; desde la v0.3 los da el motor (sección «El cielo de todos», v9.1). Pedido de
Fabricio (22/11): «todo se basa en el 9.0». Grados truncados al minuto; horas redondeadas al minuto.
La v0.2 queda en cielo_hoy_v0.2_respaldo.py.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from functools import lru_cache

import pytz

import calculo_pregunta as cp      # fija las efemérides y trae el motor (cp.m)

M = cp.m
TZ = pytz.timezone(cp.TZ_AR)
NATURALEZA = {"conjunción": "fusión", "sextil": "armonía", "trígono": "armonía",
              "cuadratura": "tensión", "oposición": "tensión"}
ORBE_ACTIVO = 3.0      # grados: más abierto no se cuenta como «activo hoy»


def _jd(dt_local: datetime) -> float:
    return M.jd_desde_local(dt_local.replace(tzinfo=None) if dt_local.tzinfo else dt_local, cp.TZ_AR)


def _hora_txt(jd: float) -> str:
    return M.hora_minuto(jd, cp.TZ_AR).strftime("%Y-%m-%d %H:%M")


def _fmt(lon: float) -> str:
    return M.fmt_de(lon)


def aspectos_activos(jd: float) -> list[dict]:
    out = []
    for a in M.aspectos_activos(jd, ORBE_ACTIVO):
        asp = a["aspecto"].lower()
        jx = a["jd_exacto"]
        out.append({
            "a": a["a"], "b": a["b"], "aspecto": asp, "angulo": a["angulo"],
            "naturaleza": NATURALEZA[asp],
            "orbe": a["orbe"],
            "posicion_a": _fmt(a["lon_a"]) + (" (retrógrado)" if a["retro_a"] else ""),
            "posicion_b": _fmt(a["lon_b"]) + (" (retrógrado)" if a["retro_b"] else ""),
            "exacto": _hora_txt(jx) if jx else None,
            "estado": (None if jx is None else ("se arma" if jx > jd else "se deshace")),
            "peso": a["peso"],
        })
    return out


def luna(jd: float) -> dict:
    lon = M.cielo_pos(jd, "Luna")[0]
    llena, nueva = M.proxima_fase(jd, 180.0), M.proxima_fase(jd, 0.0)
    d = {"signo": M.signo_de(lon), "posicion": _fmt(lon), **M.fase_luna(jd),
         "proxima_llena": None, "proxima_nueva": None}
    if llena:
        d["proxima_llena"] = {"cuando": _hora_txt(llena), "posicion": _fmt(M.cielo_pos(llena, "Luna")[0])}
    if nueva:
        d["proxima_nueva"] = {"cuando": _hora_txt(nueva), "posicion": _fmt(M.cielo_pos(nueva, "Luna")[0])}
    return d


def ingresos(jd: float, dias: int = 7) -> list[dict]:
    return sorted(({"planeta": x["planeta"], "entra_en": x["entra_en"], "cuando": _hora_txt(x["jd"]),
                    "retrogrado": x["retrogrado"]} for x in M.ingresos_proximos(jd, dias)),
                  key=lambda x: x["cuando"])


@lru_cache(maxsize=8)
def cielo_hoy(fecha: str) -> dict:
    cp._efemerides_en_este_hilo()
    jd = _jd(datetime.strptime(f"{fecha} 12:00", "%Y-%m-%d %H:%M"))
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
        "motor": M.VERSION,
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
    jd0 = _jd(lunes.replace(hour=0))
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
        t = M.proxima_fase(jd0, obj)
        if t and t < jd1:
            lunas.append({"fase": nombre, "cuando": _hora_txt(t), "posicion": _fmt(M.cielo_pos(t, "Luna")[0])})
    fin = lunes + timedelta(days=6)
    return {"semana": f"{lunes:%Y-%m-%d} al {fin:%Y-%m-%d}", "desde": desde, "hasta": hasta,
            "aspectos": aspectos, "lunas": lunas, "ingresos": ingresos(jd0, 7),
            "retrogrados": cp.cielo_del_dia(f"{lunes:%Y-%m-%d}")["retrogrados"],
            "efemerides": cp.cielo_del_dia(f"{lunes:%Y-%m-%d}")["efemerides"], "motor": M.VERSION}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(cielo_hoy(sys.argv[1] if len(sys.argv) > 1 else datetime.now(TZ).date().isoformat()),
                     ensure_ascii=False, indent=1))
