# -*- coding: utf-8 -*-
"""Control dentro del contenedor del VPS: docker exec elbrujo-pregunta python /codigo/servicio/pruebas/salud_vps.py
No llama a Claude: con PREGUNTA_ABIERTA=no el servicio contesta «cerrada» antes de calcular."""
import json, os, urllib.request

B = "http://127.0.0.1:8000"
salud = json.loads(urllib.request.urlopen(B + "/salud", timeout=30).read().decode())
print("salud:", json.dumps(salud))
if salud.get("abierta"):
    # Con el servicio abierto, el control NO pregunta: sería una pregunta real (cuesta y gasta cupo).
    print("servicio ABIERTO: no se manda la pregunta de control")
else:
    datos = {"email": "control@ejemplo.com", "fecha": "1990-01-01", "lugar": "Rosario, Argentina",
             "pregunta": "control de cierre"}
    req = urllib.request.Request(B + "/pregunta", data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"})
    print("pregunta con el servicio cerrado:", json.loads(urllib.request.urlopen(req, timeout=30).read())["estado"])
print("sal creada:", os.path.getsize("/datos/sal") == 64 if os.path.exists("/datos/sal") else False)
print("clave de la API presente:", bool(os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-")))
