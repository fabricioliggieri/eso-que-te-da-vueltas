# -*- coding: utf-8 -*-
"""
lugares.py · «Eso que te da vueltas» · v0.1 (15/11/2026)

«Ciudad, Provincia, País» → lat, lon y zona horaria.
Primero la caché (SQLite); si no está, Nominatim (OpenStreetMap) respetando su política:
un pedido por segundo como máximo, User-Agent propio y caché obligatoria. Atribución en la web:
«Datos de lugares © OpenStreetMap». La zona horaria sale de la coordenada (timezonefinder, sin red).
"""
from __future__ import annotations
import json, sqlite3, threading, time, unicodedata, urllib.parse, urllib.request
from timezonefinder import TimezoneFinder

USER_AGENT = "ElBrujo-Pregunta/0.1 (elbrujolecturas.com)"
_tf = TimezoneFinder()
_candado = threading.Lock()
_ultimo = [0.0]


def _clave(lugar: str) -> str:
    t = unicodedata.normalize("NFKD", lugar.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return ", ".join(p.strip() for p in t.split(",") if p.strip())


def abrir(ruta: str) -> sqlite3.Connection:
    con = sqlite3.connect(ruta, timeout=10, check_same_thread=False)
    con.execute("CREATE TABLE IF NOT EXISTS lugares (clave TEXT PRIMARY KEY, lat REAL, lon REAL, tz TEXT, nombre TEXT)")
    con.commit()
    return con


def resolver(con: sqlite3.Connection, lugar: str) -> dict | None:
    """Devuelve {lat, lon, tz, nombre} o None si no se encuentra. Exige al menos «Ciudad, País»."""
    k = _clave(lugar)
    if k.count(",") < 1:
        return None
    fila = con.execute("SELECT lat, lon, tz, nombre FROM lugares WHERE clave=?", (k,)).fetchone()
    if fila:
        return dict(zip(("lat", "lon", "tz", "nombre"), fila))
    with _candado:  # un pedido por segundo como máximo, para todo el servicio
        espera = 1.1 - (time.time() - _ultimo[0])
        if espera > 0:
            time.sleep(espera)
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": lugar, "format": "jsonv2", "limit": 1, "addressdetails": 0})
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                datos = json.loads(r.read().decode("utf-8"))
        finally:
            _ultimo[0] = time.time()
    if not datos:
        return None
    lat, lon = float(datos[0]["lat"]), float(datos[0]["lon"])
    tz = _tf.timezone_at(lat=lat, lng=lon)
    if not tz:
        return None
    nombre = datos[0].get("display_name", lugar)[:200]
    con.execute("INSERT OR REPLACE INTO lugares VALUES (?,?,?,?,?)", (k, lat, lon, tz, nombre))
    con.commit()
    return {"lat": lat, "lon": lon, "tz": tz, "nombre": nombre}
