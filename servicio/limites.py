# -*- coding: utf-8 -*-
"""
limites.py · «Eso que te da vueltas» · v0.1 (15/11/2026)

La base de límites (SQLite). Es la fuente de verdad del cupo: el Sheets es solo vista.
- Una pregunta cada 10 días por email (se guarda la HUELLA del email, nunca el email).
- Hasta 3 por día por IP (también como huella).
- Tope global: por día y por hora (brief v1.3: 10/día en producción oculta, 40 al abrir, 15 por hora).
La reserva es atómica (BEGIN IMMEDIATE): dos pedidos simultáneos no pasan el límite.
"""
from __future__ import annotations
import hashlib, hmac, os, sqlite3, unicodedata
from datetime import datetime, timedelta

DIAS_ENTRE_PREGUNTAS = 10
POR_IP_POR_DIA = 3
TOPE_DIA = int(os.environ.get("PREGUNTA_TOPE_DIA", "10"))
TOPE_HORA = int(os.environ.get("PREGUNTA_TOPE_HORA", "15"))
def _sal() -> bytes:
    """La sal de las huellas. Orden: variable PREGUNTA_SAL; si no, el archivo «sal» del disco de datos
    (se crea al azar la primera vez y queda ahí, sin que nadie la escriba a mano); si no hay carpeta
    de datos, una fija solo para pruebas en la PC."""
    if os.environ.get("PREGUNTA_SAL"):
        return os.environ["PREGUNTA_SAL"].encode()
    carpeta = os.environ.get("PREGUNTA_DATOS")
    if not carpeta:
        return b"solo-para-pruebas-en-la-pc"
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "sal")
    if not os.path.exists(ruta):
        import secrets
        with open(ruta, "w", encoding="ascii") as f:
            f.write(secrets.token_hex(32))
        os.chmod(ruta, 0o600)
    with open(ruta, encoding="ascii") as f:
        return f.read().strip().encode()


SAL = _sal()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
  id INTEGER PRIMARY KEY,
  momento TEXT NOT NULL,          -- ISO, hora argentina
  huella_email TEXT NOT NULL,
  huella_ip TEXT NOT NULL,
  estado TEXT NOT NULL            -- reservado | respondido | fijo | fallido
);
CREATE INDEX IF NOT EXISTS i_email ON pedidos(huella_email, momento);
CREATE INDEX IF NOT EXISTS i_ip ON pedidos(huella_ip, momento);
CREATE INDEX IF NOT EXISTS i_momento ON pedidos(momento);
"""


def normalizar_email(email: str) -> str:
    e = unicodedata.normalize("NFKC", (email or "").strip().lower())
    usuario, _, dominio = e.partition("@")
    usuario = usuario.split("+", 1)[0]
    if dominio in ("gmail.com", "googlemail.com"):
        usuario, dominio = usuario.replace(".", ""), "gmail.com"
    return f"{usuario}@{dominio}"


def huella(valor: str) -> str:
    return hmac.new(SAL, valor.encode(), hashlib.sha256).hexdigest()


def abrir(ruta: str) -> sqlite3.Connection:
    # El servicio atiende en varios hilos: la conexión se comparte y BEGIN IMMEDIATE ordena las reservas.
    con = sqlite3.connect(ruta, timeout=10, isolation_level=None, check_same_thread=False)
    con.executescript(ESQUEMA)
    return con


import threading
_CANDADO = threading.Lock()


def reservar(con: sqlite3.Connection, email: str, ip: str, ahora: datetime) -> dict:
    """Reserva un lugar o dice por qué no. Devuelve {ok, motivo, id, proxima}."""
    with _CANDADO:
        return _reservar(con, email, ip, ahora)


def _reservar(con: sqlite3.Connection, email: str, ip: str, ahora: datetime) -> dict:
    he, hi = huella(normalizar_email(email)), huella(ip or "")
    iso = ahora.isoformat(timespec="seconds")
    con.execute("BEGIN IMMEDIATE")
    try:
        ult = con.execute("SELECT momento FROM pedidos WHERE huella_email=? AND estado IN "
                          "('reservado','respondido') ORDER BY momento DESC LIMIT 1", (he,)).fetchone()
        if ult:
            prox = datetime.fromisoformat(ult[0]) + timedelta(days=DIAS_ENTRE_PREGUNTAS)
            if ahora < prox:
                con.execute("ROLLBACK")
                return {"ok": False, "motivo": "email_10_dias", "proxima": prox.date().isoformat()}
        dia = ahora.date().isoformat()
        n_ip = con.execute("SELECT COUNT(*) FROM pedidos WHERE huella_ip=? AND momento>=?",
                           (hi, dia)).fetchone()[0]
        if n_ip >= POR_IP_POR_DIA:
            con.execute("ROLLBACK"); return {"ok": False, "motivo": "ip_dia"}
        n_dia = con.execute("SELECT COUNT(*) FROM pedidos WHERE momento>=? AND estado!='fallido'",
                            (dia,)).fetchone()[0]
        if n_dia >= TOPE_DIA:
            con.execute("ROLLBACK"); return {"ok": False, "motivo": "tope_dia"}
        hora = (ahora - timedelta(hours=1)).isoformat(timespec="seconds")
        n_hora = con.execute("SELECT COUNT(*) FROM pedidos WHERE momento>=? AND estado!='fallido'",
                             (hora,)).fetchone()[0]
        if n_hora >= TOPE_HORA:
            con.execute("ROLLBACK"); return {"ok": False, "motivo": "tope_hora"}
        cur = con.execute("INSERT INTO pedidos(momento,huella_email,huella_ip,estado) VALUES(?,?,?, 'reservado')",
                          (iso, he, hi))
        con.execute("COMMIT")
        return {"ok": True, "id": cur.lastrowid}
    except Exception:
        con.execute("ROLLBACK"); raise


def contar(con: sqlite3.Connection, email: str) -> int:
    """Cuántas preguntas respondidas (o con respuesta fija de crisis/revisor) lleva ese email."""
    he = huella(normalizar_email(email))
    with _CANDADO:
        return con.execute("SELECT COUNT(*) FROM pedidos WHERE huella_email=? AND estado IN ('respondido','fijo')",
                           (he,)).fetchone()[0]


def cerrar(con: sqlite3.Connection, id_: int, estado: str) -> None:
    """estado: respondido | fijo (respuesta fija, no cuenta para los 10 días) | fallido (devuelve el cupo)."""
    with _CANDADO:
        con.execute("UPDATE pedidos SET estado=? WHERE id=?", (estado, id_))
