# -*- coding: utf-8 -*-
"""Prueba de lunas.py (16/11/2026), sin red ni API. Uso: python pruebas/probar_lunas.py (desde servicio/)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import limites, lunas

ok = fallas = 0
def caso(nombre, cond):
    global ok, fallas
    print(("  [PASA] " if cond else "  [FALLA] ") + nombre); ok += cond; fallas += (not cond)

a = lunas.alta("Ana.Perez+lunas@Gmail.com ")
b = lunas.alta("anaperez@gmail.com")
caso("misma persona, misma huella (normaliza como Visitantes)", a["huella"] == b["huella"])
caso("la huella es la de Visitantes", a["huella"] == limites.huella(limites.normalizar_email("anaperez@gmail.com")))
caso("otra persona, otra huella", a["huella"] != lunas.alta("otra@gmail.com")["huella"])
caso("el token cambia en cada alta", a["token"] != b["token"])
caso("token de 32 caracteres seguros para URL",
     len(a["token"]) == 32 and all(c.isalnum() or c in "-_" for c in a["token"]))
caso("la huella no contiene el email", "anaperez" not in a["huella"])
caso("email que guarda: el escrito, sin espacios", a["email"] == "Ana.Perez+lunas@Gmail.com")
for malo in ["", "sinarroba.com", "a@b", "a @b.com", "x" * 195 + "@b.com"]:
    caso(f"email inválido rechazado: «{malo[:20]}»", not lunas.email_valido(malo))
caso("email válido aceptado", lunas.email_valido("alguien@dominio.com.ar"))
print(f"\n{ok} pasan, {fallas} fallan")
sys.exit(1 if fallas else 0)
