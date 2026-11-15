# -*- coding: utf-8 -*-
"""Prueba del servicio HTTP levantado en la PC (127.0.0.1:8790, token «prueba-local»)."""
import json, urllib.request

URL = "http://127.0.0.1:8790"

def post(datos, token="prueba-local"):
    req = urllib.request.Request(URL + "/pregunta", data=json.dumps(datos).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Pregunta-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None

base = {"email": "prueba@ejemplo.com", "fecha": "1991-03-14", "hora": "08:20",
        "lugar": "Rosario, Santa Fe, Argentina", "ip": "127.0.0.1"}
print("salud:", urllib.request.urlopen(URL + "/salud").read().decode())
for p, extra in [("¿Qué hago con mi trabajo?", {}),
                 ("¿Y con el amor?", {"email": "Prueba@Ejemplo.com"}),            # mismo email: límite
                 ("no aguanto más esta vida", {"email": "otra@ejemplo.com"}),      # crisis
                 ("¿Qué me trae este año?", {"email": "x@ejemplo.com", "lugar": "Lugarinexistente, Zzz"})]:
    st, d = post({**base, "pregunta": p, **extra})
    print(f"\n[{st}] «{p}» → {d and d['estado']} · puerta: {d and d.get('puerta')}")
    if d:
        print(d["texto"][:500])
        print("registro sin email:", "ejemplo" not in json.dumps(d.get("registro"), ensure_ascii=False).lower())
st, _ = post({**base, "pregunta": "hola"}, token="otro")
print("\ntoken malo →", st)
