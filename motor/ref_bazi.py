# -*- coding: utf-8 -*-
"""Referencia INDEPENDIENTE del ganzhi de año y mes.

No usa `getYearGZ()` ni `getMonthGZ()`. Determina el año y el mes Bazi
comparando el INSTANTE UTC del nacimiento contra el INSTANTE UTC del término
solar, y deriva los troncos por las reglas canónicas (ciclo sexagesimal para
el año, Wu Hu Dun para el mes). Sirve para auditar al motor sin heredar sus
supuestos.
"""
import sxtwl, pytz
from datetime import datetime, timedelta

TRONCOS = ["Jia","Yi","Bing","Ding","Wu","Ji","Geng","Xin","Ren","Gui"]
RAMAS = ["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"]

_cache = {}

def jieqi_utc(anios):
    key = tuple(sorted(anios))
    if key in _cache:
        return _cache[key]
    out = []
    for a in key:
        for jq in sxtwl.getJieQiByYear(a):
            t = sxtwl.JD2DD(jq.jd)
            cst = datetime(int(t.Y), int(t.M), int(t.D), int(t.h), int(t.m)) + timedelta(seconds=float(t.s))  # v9.0: con segundos; el motor usa Swiss Ephemeris, así la referencia es independiente
            out.append((cst - timedelta(hours=8), jq.jqIndex))
    out.sort()
    _cache[key] = out
    return out

def referencia(fecha, hora, tz):
    """Devuelve (ganzhi_anio, ganzhi_mes) por instantes UTC puros."""
    y = int(fecha[:4])
    naive = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    utc = pytz.timezone(tz).localize(naive).astimezone(pytz.UTC).replace(tzinfo=None)
    jq = jieqi_utc([y-1, y, y+1])

    # --- Año: último Lichun (jqIndex 3) anterior o igual al nacimiento ---
    lich = [t for t, i in jq if i == 3 and t <= utc]
    anio = max(lich).year
    idx = (anio - 4) % 60
    ys = idx % 10
    gz_anio = f"{TRONCOS[ys]} {RAMAS[idx % 12]}"

    # --- Mes: último jie (índice impar) anterior o igual. Lichun abre el mes Yin ---
    jies = [(t, i) for t, i in jq if i % 2 == 1 and t <= utc]
    t_ult, i_ult = max(jies)
    rama = (2 + ((i_ult - 3) // 2)) % 12
    # Wu Hu Dun: tronco del mes Yin = (tronco_año*2 + 2) % 10; luego avanza un tronco
    # por mes CONTANDO DESDE YIN. Zi y Chou cierran el año Bazi, así que su
    # desplazamiento desde Yin es 10 y 11 — no 0 y 1.
    paso = (rama - 2) % 12
    tronco = (ys * 2 + 2 + paso) % 10
    gz_mes = f"{TRONCOS[tronco]} {RAMAS[rama]}"
    return gz_anio, gz_mes
