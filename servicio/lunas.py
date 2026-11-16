# -*- coding: utf-8 -*-
"""
lunas.py · «Las lunas de tu mes» · v0.1 (16/11/2026)

Lo que el servicio le da a n8n para la pestaña «Lunas» de Clientes (Fase 1 del flujo de las lunas;
ficha IA\\PROPUESTA_n8n_flujo-lunas_2026-11-16.md). El servicio NO escribe en el Sheets ni guarda el email:
- calcula la huella del email con la MISMA sal y el mismo método que Visitantes (limites.huella), para
  que una persona dé la misma huella en las dos pestañas;
- genera un token de baja al azar (n8n lo usa solo si la fila es nueva: una fila que ya existe conserva el suyo).
La sal nunca sale del servicio.
"""
from __future__ import annotations
import re, secrets

import limites

PATRON_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
TEXTOS = {
    "dato": "Revisá el mail: así no me llega.",
    "turnstile": "No pude comprobar que seas una persona. Recargá la página y probá de nuevo.",
}


def email_valido(email: str) -> bool:
    return bool(PATRON_EMAIL.fullmatch((email or "").strip())) and len(email.strip()) <= 200


def token_baja() -> str:
    # 32 caracteres seguros para una URL: imposible de adivinar, no dice nada de la persona.
    return secrets.token_urlsafe(24)


def alta(email: str) -> dict:
    """Huella y token para un email ya validado (y con Turnstile ya comprobado por quien llama)."""
    limpio = email.strip()
    return {"estado": "ok", "huella": limites.huella(limites.normalizar_email(limpio)),
            "email": limpio, "token": token_baja()}
