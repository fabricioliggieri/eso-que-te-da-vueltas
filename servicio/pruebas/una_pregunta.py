# -*- coding: utf-8 -*-
"""Una sola pregunta contra la API, de punta a punta. Uso: python una_pregunta.py [sonnet|opus] "pregunta" """
import os, sys, tempfile
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pregunta, limites, modelo

clave = sys.argv[1] if len(sys.argv) > 1 else "sonnet"
texto = sys.argv[2] if len(sys.argv) > 2 else "¿Vuelve mi ex?"
mod = modelo.MODELO_OPUS if clave == "opus" else modelo.MODELO_SONNET
con = limites.abrir(os.path.join(tempfile.mkdtemp(), "l.sqlite"))
d = dict(fecha="1991-03-14", hora="08:20", lat=-32.9468, lon=-60.6393, tz="America/Argentina/Cordoba",
         email="prueba@ejemplo.com", ip="127.0.0.1", pregunta=texto)
r = pregunta.responder(d, modelo.escritor(mod), modelo.revisor(), con, datetime(2026, 11, 15, 12, 0))
print("MODELO:", mod, "· ESTADO:", r["estado"], "· PUERTA:", r.get("puerta"))
print(r["texto"])
reg = r.get("registro") or {}
print("REGLAS:", reg.get("regla") or "—")
if r["estado"] == "error":
    print("ERROR:", r.get("error"))
