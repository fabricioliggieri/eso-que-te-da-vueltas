# -*- coding: utf-8 -*-
"""
elbrujo_calculo.py  ·  El Brujo v8.9
=====================================

v8.9 (28/10/2026) — HORA SOLAR LOCAL (3.ter). Decisión de Fabricio: el pilar de hora y
el giro de día (early-zi) se calculan sobre la hora solar local aparente del lugar de
nacimiento, no sobre la hora de reloj. bazi() recibe `lon`; sin longitud cae a reloj y lo
declara. `hora_pilar` publica la corrección (longitud, ecuación del tiempo, DST) y qué
habría dado el reloj. Consecuencia medida: en Argentina mueve el pilar de hora en la
mayoría de las cartas, y un nacimiento de 23:xx de reloj suele dejar de ser hora Zi.
La carta de demostración (2.4) cambia su pilar de hora: ver suite, sección 19.

MOTOR ÚNICO de cálculo: astrología + numerología + Bazi + tiempo.

v8.8.1 (28/10/2026) — correcciones de la auditoría del motor
(claude/auditoria-motor-astro-2026-10-28.md). No cambia ningún resultado que
el PDF publique en minutos de arco; cambia lo que el motor declara y cierra
tres huecos:
  · P1  Efemérides reales. Se descargan también sepl_18.se1 y semo_18.se1
        (planetas y Luna). Hasta hoy el motor pedía FLG_SWIEPH y, al faltar
        esos archivos, Swiss Ephemeris caía a Moshier en silencio. El motor
        ahora lee el flag que devuelve calc_ut() y declara en `efemerides`
        qué backend usó de verdad; si es Moshier, lo avisa.
  · P2  fmt(): 29°59.6' ya no se imprime «30°00' Aries»; arrastra al signo
        siguiente («0°00' Tauro»).
  · P3  Pilar de hora: se declara que se calcula sobre la hora de RELOJ
        (civil). Si en ese instante regía horario de verano, el motor lo dice,
        publica la hora estándar equivalente y el pilar de hora que daría. La
        convención sigue siendo la de reloj hasta que el núcleo decida otra
        (3.ter, pendiente); el motor no decide doctrina, la expone.
  · P4  _resolver_lugar(): sin lat/lon explícitas exige «Ciudad, País» (al
        menos dos partes separadas por coma) antes de geocodificar, para que
        «Córdoba» no caiga en España.

v8.7 (21/10/2026) — unificación. Incorpora al motor canónico lo que vivía en
scripts sueltos de dos entregas:
  · astro_jd()            carta para cualquier instante (base de natal y RS)
  · revolucion_solar()    instante exacto del retorno y carta del año
  · aspectos_cruzados()   planetas de una carta sobre puntos de otra
  · lunaciones()          lunas nuevas y llenas en un rango, con su grado
  · estaciones()          planetas que estacionan (R / D) en un rango
  · pasos_exactos()       fechas exactas de un tránsito sobre un punto natal
  · anio()                paquete completo de «El año contado»
  · mes()                 paquete completo de «Lectura del mes»
Nada de lo anterior cambia el resultado de calcular(): astro() devuelve lo
mismo que en v8.0, sólo que ahora pasa por astro_jd().
"""
from __future__ import annotations
import os, re, math, unicodedata, urllib.request, urllib.parse, json
from datetime import datetime, date, timedelta

import swisseph as swe
import pytz, sxtwl
from timezonefinder import TimezoneFinder

VERSION = "8.7"  # se reasigna a 8.8.1 al final del archivo

# ============================================================
# 0. EFEMÉRIDES
# ============================================================
EPHE_DIR = os.environ.get("ELBRUJO_EPHE", os.path.expanduser("~/.elbrujo/ephe"))
# Tres archivos (P1, v8.8.1): planetas, Luna y asteroides (Quirón). Cubren 1800–2400.
_EPHE_FILES = ["sepl_18.se1", "semo_18.se1", "seas_18.se1"]
_CHIRON_FILE = "seas_18.se1"
_EPHE_BASES = [
    "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/",
    "https://www.astro.com/ftp/swisseph/ephe/",
]

def asegurar_efemerides(descargar: bool = True) -> dict:
    """Descarga (una vez) los archivos Swiss Ephemeris que faltan y devuelve
    {archivo: bool}. Si falla la red, no inventa nada: el motor cae a Moshier y
    lo declara en cada carta."""
    os.makedirs(EPHE_DIR, exist_ok=True)
    presentes = {}
    for nombre in _EPHE_FILES:
        destino = os.path.join(EPHE_DIR, nombre)
        if not os.path.exists(destino) and descargar:
            for base in _EPHE_BASES:
                try:
                    req = urllib.request.Request(base + nombre, headers={"User-Agent": "ElBrujo/8.8"})
                    with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
                        f.write(r.read())
                    if os.path.getsize(destino) > 100_000:   # v9.0: un archivo real pesa más de 200 KB
                        break
                    os.remove(destino)
                except Exception:
                    if os.path.exists(destino):
                        os.remove(destino)
        presentes[nombre] = os.path.exists(destino)
    swe.set_ephe_path(EPHE_DIR)
    return presentes

EFEMERIDES = asegurar_efemerides()
QUIRON_DISPONIBLE = EFEMERIDES.get(_CHIRON_FILE, False)
PLANETAS_SWIEPH = EFEMERIDES.get("sepl_18.se1", False) and EFEMERIDES.get("semo_18.se1", False)

def _backend(iflag: int) -> str:
    """Nombre del backend que Swiss Ephemeris usó de verdad, leído del flag devuelto."""
    if iflag & swe.FLG_JPLEPH:  return "JPL"
    if iflag & swe.FLG_MOSEPH:  return "Moshier"
    if iflag & swe.FLG_SWIEPH:  return "Swiss Ephemeris"
    return "desconocido"

# ============================================================
# 1. CONSTANTES
# ============================================================
SIGNOS = ['Aries','Tauro','Géminis','Cáncer','Leo','Virgo','Libra','Escorpio',
          'Sagitario','Capricornio','Acuario','Piscis']
ROMANO = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']
PLANETAS = {'Sol':swe.SUN,'Luna':swe.MOON,'Mercurio':swe.MERCURY,'Venus':swe.VENUS,
            'Marte':swe.MARS,'Júpiter':swe.JUPITER,'Saturno':swe.SATURN,
            'Urano':swe.URANUS,'Neptuno':swe.NEPTUNE,'Plutón':swe.PLUTO,
            'Nodo N':swe.TRUE_NODE}
ASPECTOS = {'Conjunción':0,'Oposición':180,'Cuadratura':90,'Trígono':120,'Sextil':60}
ORBES = {'Sol':8,'Luna':8,'Mercurio':6,'Venus':6,'Marte':6,'Júpiter':6,'Saturno':6,
         'Urano':4,'Neptuno':4,'Plutón':4,'Nodo N':3,'Quirón':4,'Lilith':3}

LAT_LIMITE_TOPOCENTRICO = 66.0   # verificado empíricamente

# v9.0 (D3, D4, D5, D10): convenciones del cálculo, escritas en el núcleo (adenda 8.6.4) y
# publicadas con cada carta para que cualquiera pueda comparar con otro programa.
CONVENCIONES = {
    'zodiaco': 'tropical',
    'casas': 'Topocéntrico (Polich-Page); Whole Sign por encima de 66° de latitud',
    'nodo': 'Nodo verdadero',
    'lilith': 'Luna Negra media (otros programas usan la osculante, que puede diferir unos grados)',
    'orbes': 'el mayor de los dos cuerpos: Sol y Luna 8°; Mercurio a Saturno 6°; Urano, Neptuno, Plutón y Quirón 4°; Nodo y Lilith 3°',
    'transitos': 'lentos (Júpiter a Plutón, Nodo y Quirón) 3°; rápidos 2°; Luna 1°',
    'grados': 'truncados al minuto, como las efemérides impresas',
    'bazi': 'pilares por términos solares al segundo; día y hora por hora solar local; early-zi; '
            'escuela clásica, igual en los dos hemisferios',
}

DOMICILIO = {'Sol':['Leo'],'Luna':['Cáncer'],'Mercurio':['Géminis','Virgo'],
             'Venus':['Tauro','Libra'],'Marte':['Aries','Escorpio'],
             'Júpiter':['Sagitario','Piscis'],'Saturno':['Capricornio','Acuario']}
EXALTACION = {'Sol':'Aries','Luna':'Tauro','Mercurio':'Virgo','Venus':'Piscis',
              'Marte':'Capricornio','Júpiter':'Cáncer','Saturno':'Libra'}
CAIDA = {'Sol':'Libra','Luna':'Escorpio','Mercurio':'Piscis','Venus':'Virgo',
         'Marte':'Cáncer','Júpiter':'Capricornio','Saturno':'Aries'}
OPUESTO = {'Aries':'Libra','Tauro':'Escorpio','Géminis':'Sagitario','Cáncer':'Capricornio',
           'Leo':'Acuario','Virgo':'Piscis','Libra':'Aries','Escorpio':'Tauro',
           'Sagitario':'Géminis','Capricornio':'Cáncer','Acuario':'Leo','Piscis':'Virgo'}

# --- Bazi ---
TRONCOS = [("Jia","甲","Madera","Yang"),("Yi","乙","Madera","Yin"),
           ("Bing","丙","Fuego","Yang"),("Ding","丁","Fuego","Yin"),
           ("Wu","戊","Tierra","Yang"),("Ji","己","Tierra","Yin"),
           ("Geng","庚","Metal","Yang"),("Xin","辛","Metal","Yin"),
           ("Ren","壬","Agua","Yang"),("Gui","癸","Agua","Yin")]
RAMAS = [("Zi","子","Rata","Agua"),("Chou","丑","Buey","Tierra"),
         ("Yin","寅","Tigre","Madera"),("Mao","卯","Conejo","Madera"),
         ("Chen","辰","Dragón","Tierra"),("Si","巳","Serpiente","Fuego"),
         ("Wu","午","Caballo","Fuego"),("Wei","未","Cabra","Tierra"),
         ("Shen","申","Mono","Metal"),("You","酉","Gallo","Metal"),
         ("Xu","戌","Perro","Tierra"),("Hai","亥","Cerdo","Agua")]
OCULTOS = {0:[(9,1.0)], 1:[(5,.6),(9,.3),(7,.1)], 2:[(0,.6),(2,.3),(4,.1)],
           3:[(1,1.0)], 4:[(4,.6),(1,.3),(9,.1)], 5:[(2,.6),(4,.3),(6,.1)],
           6:[(3,.7),(5,.3)], 7:[(5,.6),(3,.3),(1,.1)], 8:[(6,.6),(8,.3),(4,.1)],
           9:[(7,1.0)], 10:[(4,.6),(7,.3),(3,.1)], 11:[(8,.7),(0,.3)]}
ELEMENTOS = ["Madera","Fuego","Tierra","Metal","Agua"]
NUTRE    = {"Madera":"Agua","Fuego":"Madera","Tierra":"Fuego","Metal":"Tierra","Agua":"Metal"}
CONTROLA = {"Madera":"Metal","Fuego":"Agua","Tierra":"Madera","Metal":"Fuego","Agua":"Tierra"}
DRENA    = {"Madera":"Fuego","Fuego":"Tierra","Tierra":"Metal","Metal":"Agua","Agua":"Madera"}
CHONG = [(0,6),(1,7),(2,8),(3,9),(4,10),(5,11)]
LIUHE = [(0,1),(2,11),(3,10),(4,9),(5,8),(6,7)]
SANHE = [([2,6,10],"Fuego"),([11,3,7],"Madera"),([8,0,4],"Agua"),([5,9,1],"Metal")]

# --- Numerología ---
TABLA = {}
for _blk in ("ABCDEFGHI","JKLMNOPQR","STUVWXYZ"):
    for _i, _c in enumerate(_blk):
        TABLA[_c] = _i + 1
TABLA['Ñ'] = 5
VOCALES = set("AEIOU")
MAESTROS = {11, 22, 33}
DEUDAS = {13, 14, 16, 19}
DEUDA_TXT = {13:"pereza pasada — trabajo paciente y constructivo",
             14:"exceso pasado — disciplina y moderación",
             16:"orgullo — caída del ego para reconstruir desde la humildad",
             19:"abuso de poder — dar sin esperar reconocimiento"}

# ============================================================
# 2. UTILIDADES
# ============================================================
def fmt(g: float) -> str:
    """Grado → «g°mm' Signo». v9.0 (E11): TRUNCA al minuto, como astro.com y las efemérides
    impresas. Así el signo mostrado es siempre el signo real del planeta (29°59.6' Aries se
    muestra «29°59' Aries», no «0°00' Tauro» mientras la dignidad usaba Aries)."""
    g %= 360
    total_min = int(math.floor(g * 60 + 1e-9)) % (360 * 60)
    i, resto = divmod(total_min, 30 * 60)
    gi, m = divmod(resto, 60)
    return f"{gi}°{m:02d}' {SIGNOS[i]}"

def casa_de(g: float, cusp) -> int:
    g %= 360
    for i in range(12):
        a, b = cusp[i] % 360, cusp[(i+1) % 12] % 360
        if a < b:
            if a <= g < b: return i+1
        else:
            if g >= a or g < b: return i+1
    return 1

_GEO_NOMBRE = {}   # v9.0 (E21): qué lugar encontró de verdad la búsqueda, para declararlo

def geocodificar(lugar: str):
    try:
        url = ("https://nominatim.openstreetmap.org/search?q="
               + urllib.parse.quote(lugar) + "&format=json&limit=1")
        req = urllib.request.Request(url, headers={"User-Agent": "ElBrujo/9.0", "Accept-Language": "es"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        if d:
            _GEO_NOMBRE[lugar] = d[0].get("display_name", lugar)
            return float(d[0]["lat"]), float(d[0]["lon"])
    except Exception:
        pass
    return None, None

def reducir(n: int, maestros=False, deudas=False):
    d = None
    while n > 9:
        if maestros and n in MAESTROS: break
        if deudas and n in DEUDAS: d = n
        n = sum(int(x) for x in str(n))
    return n, d

def traza_reduccion(n: int):
    """Todos los pasos de la reducción, para poder ver los maestros intermedios."""
    pasos = [n]
    while n > 9:
        n = sum(int(x) for x in str(n))
        pasos.append(n)
    return pasos

def _cumple_en(anio: int, m: int, dd: int) -> date:
    """Cumpleaños en un año dado. Nacidos el 29/2: en año no bisiesto, el 1/3 (v9.0)."""
    try:
        return date(anio, m, dd)
    except ValueError:
        return date(anio, 3, 1)

def _edad_cumplida(nac: date, hoy: date) -> int:
    """Años cumplidos (por cumpleaños, no por días/365,25) (v9.0, E3)."""
    return hoy.year - nac.year - (1 if hoy < _cumple_en(hoy.year, nac.month, nac.day) else 0)

# v9.0 (E15): letras latinas sin descomposición Unicode, pasadas a su equivalente declarado.
# Antes se borraban y partían la palabra («Søren» daba Alma 5 y «Soren» 11).
_TRANSLIT = {'Ø': 'O', 'Æ': 'AE', 'Œ': 'OE', 'Ł': 'L', 'Đ': 'D', 'Ð': 'D', 'Þ': 'TH',
             'ẞ': 'SS', 'Ĳ': 'IJ', 'İ': 'I', 'Ŋ': 'NG', 'Ħ': 'H', 'Ŧ': 'T'}

def _translit(s: str) -> str:
    s = s.upper()
    return "".join(_TRANSLIT.get(c, c) for c in s)

def letras_no_latinas(nombre: str) -> list[str]:
    """Letras del nombre que no tienen lectura en la tabla pitagórica (otro alfabeto)."""
    t = unicodedata.normalize("NFD", _translit(nombre).replace("Ñ", "N"))
    return sorted({c for c in t if unicodedata.category(c).startswith("L") and not ("A" <= c <= "Z")})

def _norm_nombre(s: str) -> str:
    s = _translit(s).replace("Ñ", "\x01")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z\x01]", "", s).replace("\x01", "Ñ")

def _norm_nombre_palabras(s: str) -> str:
    """Igual que _norm_nombre, pero CONSERVA los límites de palabra (criterio de la Y)."""
    s = _translit(s).replace("Ñ", "\x01")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z\x01]", " ", s)
    return re.sub(r"\s+", " ", s).strip().replace("\x01", "Ñ")

def _y_regla(nombre_norm: str, idx: int):
    """Decide si la Y de `idx` funciona como vocal, y devuelve la regla aplicada (3.bis.1)."""
    if idx < 0 or idx >= len(nombre_norm) or nombre_norm[idx] != 'Y':
        return False, 'no es Y'
    ini = idx == 0 or not nombre_norm[idx-1].isalpha()
    fin = idx == len(nombre_norm) - 1 or not nombre_norm[idx+1].isalpha()
    prev = None if ini else nombre_norm[idx-1]
    sig  = None if fin else nombre_norm[idx+1]
    if ini and fin: return True, 'conjunción'
    if ini and sig in VOCALES: return False, 'inicial+vocal'
    if prev in VOCALES and sig in VOCALES: return False, 'entre vocales'
    if fin and prev in VOCALES: return True, 'final tras vocal'
    if not ini and prev not in VOCALES: return True, 'tras consonante'
    return False, 'consonante por defecto'

def _y_es_vocal(nombre_norm: str, idx: int) -> bool:
    return _y_regla(nombre_norm, idx)[0]

def _jd(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                      dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600)

def _local_aware(fecha: str, hora: str | None, tz: str, lon: float | None = None,
                 dst: bool | None = None) -> datetime:
    """Hora civil → datetime con zona. v9.0:
    · E6: si la hora se repitió o no existió por un cambio de horario, se usa la lectura
      `dst` (por defecto False = hora estándar, como hasta v8.9); calcular() detecta el
      caso con _estado_hora() y publica las dos lecturas.
    · E10: antes de la hora oficial la base de zonas da la hora media de la CIUDAD
      cabecera (LMT); con la longitud del lugar se usa la hora media del lugar."""
    naive = datetime.strptime(f"{fecha} {hora or '12:00'}", "%Y-%m-%d %H:%M")
    z = pytz.timezone(tz)
    local = z.localize(naive, is_dst=bool(dst))
    if lon is not None and local.tzname() == 'LMT':
        from datetime import timezone as _tzc
        local = naive.replace(tzinfo=_tzc(timedelta(seconds=round(lon * 240.0)), 'LMT del lugar'))
    return local

def _estado_hora(fecha: str, hora: str | None, tz: str) -> str:
    """'normal' · 'repetida' (la hora pasó dos veces) · 'inexistente' (el reloj la salteó) ·
    'lmt' (anterior a la hora oficial). v9.0, E6/E10."""
    if not hora:
        return 'normal'
    naive = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    z = pytz.timezone(tz)
    try:
        loc = z.localize(naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        return 'repetida'
    except pytz.exceptions.NonExistentTimeError:
        return 'inexistente'
    return 'lmt' if loc.tzname() == 'LMT' else 'normal'

def _utc_desde_local(fecha: str, hora: str | None, tz: str, lon: float | None = None,
                     dst: bool | None = None) -> datetime:
    return _local_aware(fecha, hora, tz, lon, dst).astimezone(pytz.UTC)

def _jd_a_local(jd: float, tz: str):
    # v9.0 (E12): redondeo al minuto con timedelta (antes, entre 23:59:30 y 24:00 UTC,
    # el minuto 60 llevaba la hora a 24 y se caía).
    y, mo, d, h = swe.revjul(jd)
    utc = datetime(y, mo, d) + timedelta(minutes=round(h * 60.0))
    utc = pytz.UTC.localize(utc)
    return utc, utc.astimezone(pytz.timezone(tz))

# ---------- hora solar local (decisión del 28/10/2026, 3.ter) ----------
# El pilar de hora (y el giro de día early-zi) se calculan sobre la HORA SOLAR LOCAL
# APARENTE del lugar: hora de reloj → UTC → + longitud/15 → + ecuación del tiempo.
# Es la hora que las ramas horarias siempre quisieron medir (Caballo = mediodía solar).
# En Argentina la corrección es de 50 a 95 minutos, así que mueve el pilar de hora en la
# mayoría de las cartas respecto de un cálculo por reloj. Se declara en cada documento.
CONVENCION_HORA_PILAR = "solar"      # "solar" (canónica) · "reloj" (sólo para auditoría)

def hora_solar_local(fecha: str, hora: str, tz: str, lon: float, dst: bool | None = None):
    """Devuelve (datetime solar aparente naive, detalle) para una hora civil en `tz` y `lon`."""
    local = _local_aware(fecha, hora, tz, lon, dst)
    utc = local.astimezone(pytz.UTC)
    jd = _jd(utc)
    eot = swe.time_equ(jd)
    eot = eot[0] if isinstance(eot, (tuple, list)) else eot      # días, aparente − media
    corr_lon = timedelta(hours=lon / 15.0)
    corr_eot = timedelta(days=eot)
    solar = utc.replace(tzinfo=None) + corr_lon + corr_eot
    dst = local.dst() or timedelta(0)
    offset = local.utcoffset() or timedelta(0)
    return solar, {
        'hora_reloj': hora,
        'huso': round(offset.total_seconds() / 3600, 2),
        'dst_activo': dst != timedelta(0),
        'longitud': lon,
        'correccion_longitud_min': round((corr_lon - offset).total_seconds() / 60, 1),
        'ecuacion_tiempo_min': round(eot * 1440, 1),
        'correccion_total_min': round((solar - local.replace(tzinfo=None)).total_seconds() / 60, 1),
        'hora_solar': solar.strftime('%H:%M'),
        'fecha_solar': solar.strftime('%Y-%m-%d'),
    }

# ============================================================
# 3. ASTROLOGÍA
# ============================================================
def _dignidad(planeta: str, signo: str):
    if planeta in DOMICILIO and signo in DOMICILIO[planeta]:
        return "domicilio", "opera con fuerza propia"
    if EXALTACION.get(planeta) == signo:
        return "exaltación", "opera elevado"
    if planeta in DOMICILIO and signo in [OPUESTO[s] for s in DOMICILIO[planeta]]:
        return "detrimento", "opera sin fuerza propia"
    if CAIDA.get(planeta) == signo:
        return "caída", "opera distorsionado"
    return None, None

def _aspectos(pos):
    # El Nodo Sur es el Nodo Norte + 180° por construcción: el eje se computa una vez.
    out, nombres = [], [k for k in pos.keys() if k != 'Nodo S']
    for i, a in enumerate(nombres):
        for b in nombres[i+1:]:
            diff = abs(pos[a]['grados'] - pos[b]['grados']) % 360
            if diff > 180: diff = 360 - diff
            for nom, ang in ASPECTOS.items():
                orbe = max(ORBES.get(a, 4), ORBES.get(b, 4))
                if abs(diff - ang) <= orbe:
                    out.append({'a':a,'b':b,'aspecto':nom,'orbe':round(abs(diff-ang),2)})
                    break
    return sorted(out, key=lambda x: x['orbe'])

def astro_jd(jd: float, lat: float, lon: float, sin_hora: bool = False):
    """Carta para un instante JD (UT) en (lat, lon). Base común de natal, RS y tránsitos."""
    flag = swe.FLG_SWIEPH | swe.FLG_SPEED
    pos, avisos = {}, []
    backends = set()
    for nom, cod in PLANETAS.items():
        try:
            r = swe.calc_ut(jd, cod, flag)
        except Exception:
            r = swe.calc_ut(jd, cod, swe.FLG_MOSEPH | swe.FLG_SPEED)
        backends.add(_backend(r[1]))
        pos[nom] = {'grados': r[0][0] % 360, 'retro': r[0][3] < 0, 'fmt': fmt(r[0][0])}

    ns = (pos['Nodo N']['grados'] + 180) % 360
    pos['Nodo S'] = {'grados': ns, 'retro': False, 'fmt': fmt(ns)}
    # Luna Negra MEDIA — convención canónica (3.1.bis), mismo flag que el resto.
    gl = swe.calc_ut(jd, swe.MEAN_APOG, flag)[0][0]
    pos['Lilith'] = {'grados': gl % 360, 'retro': False, 'fmt': fmt(gl)}
    # v9.0 (D5): la osculante solo como referencia publicada (no entra a aspectos ni lectura)
    _lo = swe.calc_ut(jd, swe.OSCU_APOG, flag)[0][0] % 360

    if QUIRON_DISPONIBLE:
        try:
            q = swe.calc_ut(jd, swe.CHIRON, flag)
            pos['Quirón'] = {'grados': q[0][0] % 360, 'retro': q[0][3] < 0, 'fmt': fmt(q[0][0])}
        except Exception:
            avisos.append("Quirón no pudo calcularse con las efemérides disponibles.")
    else:
        avisos.append("Quirón no incluido: falta el archivo de efemérides del asteroide "
                      "(seas_18.se1). Aparece solo como definición en el glosario.")

    # P1 (v8.8.1): declarar el backend real. Precisión medida el 28/10/2026 contra
    # astro.com y JPL: Swiss Ephemeris ≤ 0,5″; Moshier ≤ 1,5″ en Luna y ≤ 17″ en el
    # Nodo verdadero. Ninguna afecta un PDF que publica minutos; se declara igual.
    efemerides = " + ".join(sorted(backends))
    if "Moshier" in backends:
        avisos.append("Posiciones calculadas con el modelo analítico Moshier porque faltan "
                      "los archivos sepl_18.se1 / semo_18.se1 de Swiss Ephemeris. "
                      "Diferencia respecto de las efemérides completas: menor a 2 segundos "
                      "de arco (17″ en el Nodo verdadero); no cambia ningún grado ni minuto "
                      "publicado.")

    asc = mc = cusps = None
    sistema = None
    diurna = fortuna = None
    if sin_hora:
        avisos.append("Sin hora de nacimiento: no hay casas, Ascendente, Medio Cielo, "
                      "Parte de la Fortuna ni rueda natal. Las posiciones se calcularon al "
                      "mediodía: los planetas no cambian de signo en el día salvo que se avise, "
                      "pero la Luna recorre unos 13° en el día, así que su grado y sus aspectos "
                      "son aproximados (v9.0: se publica su rango).")
    else:
        hsys, sistema = b'T', "Topocéntrico (Polich-Page)"
        if abs(lat) > LAT_LIMITE_TOPOCENTRICO:
            hsys, sistema = b'W', "Whole Sign"
            avisos.append(f"Latitud {lat:.1f}°: sobre los {LAT_LIMITE_TOPOCENTRICO:.0f}° el "
                          "sistema topocéntrico devuelve casas degeneradas. Se usa Whole Sign, "
                          "definido en toda latitud y de linaje helenístico.")
        cusps, ang = swe.houses(jd, lat, lon, hsys)
        cusps = [c % 360 for c in cusps]
        asc, mc = ang[0] % 360, ang[1] % 360
        for info in pos.values():
            info['casa'] = casa_de(info['grados'], cusps)
        diurna = pos['Sol']['casa'] in (7, 8, 9, 10, 11, 12)
        if hsys == b'W':
            # v9.0 (E13): en Whole Sign la casa del Sol no dice si está sobre el horizonte;
            # se usa la altura real del Sol (carta diurna = Sol arriba del horizonte).
            _sol = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0]
            _alt = swe.azalt(jd, swe.ECL2HOR, (lon, lat, 0.0), 0.0, 0.0, (_sol[0], _sol[1], _sol[2]))[1]
            diurna = _alt > 0
        pf = ((asc + pos['Luna']['grados'] - pos['Sol']['grados']) if diurna
              else (asc + pos['Sol']['grados'] - pos['Luna']['grados'])) % 360
        fortuna = {'grados': pf, 'fmt': fmt(pf), 'casa': casa_de(pf, cusps)}

    dign = {}
    for p in ('Sol','Luna','Mercurio','Venus','Marte','Júpiter','Saturno'):
        s = SIGNOS[int(pos[p]['grados'] // 30)]
        d, txt = _dignidad(p, s)
        if d: dign[p] = {'signo': s, 'dignidad': d, 'efecto': txt}

    secta = None
    if diurna is not None:
        secta = {'tipo': 'diurna' if diurna else 'nocturna',
                 'de_secta':    ['Sol','Júpiter','Saturno'] if diurna else ['Luna','Venus','Marte'],
                 'fuera_secta': ['Luna','Venus','Marte'] if diurna else ['Sol','Júpiter','Saturno']}

    for x in (asp := _aspectos(pos)):
        x['cerrado'] = x['orbe'] <= 4.0           # v9.0 (D4): el anexo publica todos, con su orbe
    return {'sin_hora': sin_hora, 'jd': jd,
            'convenciones': CONVENCIONES, 'lilith_osculante': fmt(_lo),
            'pos': pos, 'cusp_deg': cusps, 'sistema_casas': sistema,
            'asc_deg': asc, 'mc_deg': mc,
            'asc': fmt(asc) if asc is not None else None,
            'mc': fmt(mc) if mc is not None else None,
            'diurna': diurna, 'secta': secta, 'fortuna': fortuna,
            'dignidades': dign, 'aspectos': asp,
            'efemerides': efemerides, 'avisos': avisos}

def astro(fecha: str, hora, lat: float, lon: float, tz: str, dst: bool | None = None):
    """Carta natal (o carta de cualquier fecha local). Idéntica a v8.0 en su salida."""
    sin_hora = not hora
    utc = _utc_desde_local(fecha, hora, tz, lon if hora else None, dst)
    out = astro_jd(_jd(utc), lat, lon, sin_hora)
    out.update({'utc': utc, 'tz': tz})
    return out

def revolucion_solar(natal_astro: dict, anio: int, lat: float, lon: float, tz: str):
    """Instante exacto en que el Sol vuelve a su grado natal en `anio`, y la carta
    para ese instante levantada en (lat, lon) —el lugar donde la persona ESTÁ ese
    día, no donde nació—. Bisección sobre la longitud solar, residuo < 1e-6°."""
    sol_nat = natal_astro['pos']['Sol']['grados']
    utc_nat = natal_astro['utc']
    jd0 = swe.julday(anio, utc_nat.month, utc_nat.day, utc_nat.hour + utc_nat.minute/60) - 3
    jd1 = jd0 + 6
    def dsol(jd):
        s = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0]
        return (s - sol_nat + 180) % 360 - 180
    a, b = jd0, jd1
    for _ in range(60):
        m = (a + b) / 2
        if dsol(a) * dsol(m) <= 0: b = m
        else: a = m
    jd_rs = (a + b) / 2
    utc_rs, local_rs = _jd_a_local(jd_rs, tz)
    out = astro_jd(jd_rs, lat, lon, False)
    out.update({'utc': utc_rs, 'local': local_rs, 'tz': tz, 'anio': anio,
                'lat': lat, 'lon': lon,
                'sol_natal': sol_nat, 'residuo_deg': dsol(jd_rs)})
    return out

def aspectos_cruzados(pos_a: dict, pos_b: dict, ejes_a=None, ejes_b=None,
                      factor: float = 0.75, orbe_max: float | None = None):
    """Aspectos de los cuerpos de A sobre los de B (RS sobre natal, sinastría, etc.).
    `ejes_*` permite sumar Asc/MC como puntos. Orbe = orbe natal × factor, o fijo."""
    pa = {k: v['grados'] for k, v in pos_a.items() if k != 'Nodo S'}
    if ejes_a: pa.update(ejes_a)
    pb = {k: v['grados'] for k, v in pos_b.items() if k != 'Nodo S'}
    if ejes_b: pb.update(ejes_b)
    out = []
    for na, ga in pa.items():
        for nb, gb in pb.items():
            diff = abs(ga - gb) % 360
            if diff > 180: diff = 360 - diff
            for nom, ang in ASPECTOS.items():
                tope = orbe_max if orbe_max is not None else max(ORBES.get(na, 4), ORBES.get(nb, 4)) * factor
                if abs(diff - ang) <= tope:
                    out.append({'a': na, 'aspecto': nom, 'b': nb, 'orbe': round(abs(diff-ang), 2)})
                    break
    return sorted(out, key=lambda x: x['orbe'])

# ============================================================
# 4. NUMEROLOGÍA
# ============================================================
def validar_fecha(fecha: str, que: str = "fecha de nacimiento") -> date:
    """v9.0 (E14): la fecha tiene que existir y estar en el rango de las efemérides."""
    if not isinstance(fecha, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha.strip()):
        raise ValueError(f"La {que} «{fecha}» no tiene el formato AAAA-MM-DD (por ejemplo 1990-03-14).")
    try:
        f = date.fromisoformat(fecha.strip())
    except ValueError:
        raise ValueError(f"La {que} «{fecha}» no existe en el calendario (revisá día y mes).")
    if not (1800 <= f.year <= 2399):
        raise ValueError(f"La {que} «{fecha}» está fuera del rango que cubren las efemérides (1800–2399).")
    return f

def validar_hora(hora) -> None:
    if hora and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(hora).strip()):
        raise ValueError(f"La hora «{hora}» no tiene el formato HH:MM de 24 horas (por ejemplo 09:45).")

def numerologia(nombre, fecha: str, fecha_consulta: str | None = None):
    _nac = validar_fecha(fecha)
    y, m, dd = [int(x) for x in fecha.split("-")]
    hoy = validar_fecha(fecha_consulta, "fecha de consulta") if fecha_consulta else date.today()
    if hoy < _nac:
        raise ValueError(f"La fecha de consulta ({hoy.isoformat()}) es anterior al nacimiento ({fecha}).")
    if nombre and letras_no_latinas(nombre):
        raise ValueError("El nombre tiene letras fuera del alfabeto latino ("
                         + " ".join(letras_no_latinas(nombre)) + "): la tabla pitagórica no las lee. "
                         "Pasalo como figura en el documento, en letras latinas.")
    if nombre and nombre.strip() and not _norm_nombre(nombre):
        raise ValueError("El nombre no tiene letras: no se puede calcular Alma, Expresión ni Personalidad.")
    if nombre is not None and not nombre.strip():
        nombre = None
    avisos, deudas = [], set()
    # v9.0 (D2, E17): una deuda kármica cuenta solo si es INDIVIDUAL: el día de nacimiento
    # (13, 14, 16 o 19) y la suma de cada posición núcleo (Camino, Alma, Expresión,
    # Personalidad). El año solo NO cuenta: lo comparte toda una generación (todos los
    # nacidos en 1990 llevaban 19). Cada deuda se publica con su posición y su traza.
    deudas_pos = []
    def _anotar(deuda, posicion, traza):
        if deuda:
            deudas.add(deuda)
            deudas_pos.append({'deuda': deuda, 'posicion': posicion, 'traza': traza})

    dr, d1 = reducir(dd, True, True)
    mr, _ = reducir(m,  True, True)
    yr, _ = reducir(y,  True, True)
    _anotar(d1, 'día de nacimiento', traza_reduccion(dd))
    suma_camino = dr + mr + yr
    camino, d4 = reducir(suma_camino, True, True)
    _anotar(d4, 'Camino de Vida', [suma_camino] + traza_reduccion(suma_camino)[1:])

    # v9.0 (D1): la forma de la casa es la de arriba (día, mes y año reducidos por separado,
    # conservando 11 y 22, y sumados). Las otras dos formas de la tradición se calculan y,
    # si dan otro maestro u otra deuda, quedan como OBSERVACIÓN (anexo); al cuerpo entran
    # solo si las corrobora el Bazi (regla de la casa, 3.bis.12).
    def _forma(total):
        tr = traza_reduccion(total)
        mae = next((x for x in tr if x in MAESTROS), None)
        deu = next((x for x in tr if x in DEUDAS), None)
        return {'suma': total, 'traza': tr, 'maestro': mae, 'deuda': deu}
    f_dig = _forma(sum(int(c) for c in f"{dd}{m}{y}"))
    f_com = _forma(dd + m + y)
    camino_formas = {'casa': {'suma': suma_camino, 'traza': [suma_camino] + traza_reduccion(suma_camino)[1:],
                              'componentes': [dr, mr, yr], 'maestro': camino if camino in MAESTROS else None,
                              'deuda': d4},
                     'todos_los_digitos': f_dig, 'dia_mes_anio_completos': f_com}
    observaciones = []
    for nom, f in (('todos los dígitos', f_dig), ('día + mes + año completos', f_com)):
        if f['maestro'] and f['maestro'] != camino_formas['casa']['maestro']:
            observaciones.append({'tipo': 'maestro', 'valor': f['maestro'], 'forma': nom, 'traza': f['traza']})
        if f['deuda'] and f['deuda'] not in deudas:
            observaciones.append({'tipo': 'deuda', 'valor': f['deuda'], 'forma': nom, 'traza': f['traza']})

    nucleo = {'camino': camino}
    if nombre:
        nn = _norm_nombre_palabras(nombre)
        def suma(modo):
            t = 0
            for i, ch in enumerate(nn):
                if ch not in TABLA: continue
                voc = (ch in VOCALES) or (ch == 'Y' and _y_es_vocal(nn, i))
                if modo == 't' or (modo == 'v' and voc) or (modo == 'c' and not voc):
                    t += TABLA[ch]
            return t
        for clave, modo in (('alma','v'), ('expresion','t'), ('personalidad','c')):
            v, d = reducir(suma(modo), True, True)
            nucleo[clave] = v
            nucleo[clave + '_bruto'] = suma(modo)
            _anotar(d, {'alma': 'Alma', 'expresion': 'Expresión', 'personalidad': 'Personalidad'}[clave],
                    traza_reduccion(suma(modo)))
        presentes = {TABLA[c] for c in nn if c in TABLA}
        nucleo['lecciones'] = [k for k in range(1, 10) if k not in presentes]
        y_vocal = []
        for i, ch in enumerate(nn):
            if ch != 'Y': continue
            es_v, regla = _y_regla(nn, i)
            ini_p = nn.rfind(' ', 0, i) + 1
            fin_p = nn.find(' ', i); fin_p = len(nn) if fin_p == -1 else fin_p
            y_vocal.append({'posicion': i, 'palabra': nn[ini_p:fin_p], 'regla': regla,
                            'cuenta_como': 'vocal' if es_v else 'consonante'})
        nucleo['y_vocal'] = y_vocal
        # 3.bis.8: la Madurez reduce maestros, pero si 11/22/33 aparece en la traza se
        # nombra como ECO OCULTO (puede estar en cualquier paso: 38 → 11 → 2).
        _traza = traza_reduccion(camino + nucleo['expresion'])
        _ecos = [x for x in _traza[:-1] if x in MAESTROS]
        nucleo['madurez_eco'] = _ecos[0] if _ecos else None
        nucleo['madurez_traza'] = _traza
        nucleo['madurez'] = _traza[-1]
    else:
        for k in ('alma','expresion','personalidad','madurez','madurez_eco','madurez_traza'):
            nucleo[k] = None
        nucleo['lecciones'] = None
        nucleo['y_vocal'] = []
        avisos.append("Sin nombre completo de nacimiento: quedan fuera Alma, Expresión, "
                      "Personalidad, Madurez y Lecciones Kármicas. Camino de Vida y ciclos "
                      "personales sí se calculan.")

    # Pináculos y Desafíos sobre componentes reducidos a dígito (3.bis.2).
    dR, mR, yR = reducir(dd)[0], reducir(m)[0], reducir(y)[0]
    p1, _ = reducir(mR + dR); p2, _ = reducir(dR + yR)
    p3, _ = reducir(p1 + p2); p4, _ = reducir(mR + yR)
    # v9.0 (E16): eco oculto (3.bis.9) en toda posición no núcleo, no solo en la Madurez.
    ecos = {}
    for nom, tot in (('P1', mR + dR), ('P2', dR + yR), ('P3', p1 + p2), ('P4', mR + yR)):
        e = next((x for x in traza_reduccion(tot)[:-1] if x in MAESTROS), None)
        if e: ecos[nom] = {'eco': e, 'traza': traza_reduccion(tot)}
    fin1 = 36 - camino                      # la DURACIÓN sí usa el maestro (3.bis.5)
    # v9.0 (E3): tramos sin hueco. 'desde' es el cumpleaños en que empieza (incluido) y
    # 'hasta' el cumpleaños en que empieza el siguiente (excluido): P1 [0, 36−C),
    # P2 [36−C, 45−C), P3 [45−C, 54−C), P4 desde 54−C. Se comparan con años cumplidos.
    pinaculos = [
        {'n':1,'valor':p1,'desde':0,         'hasta':fin1},
        {'n':2,'valor':p2,'desde':fin1,      'hasta':fin1+9},
        {'n':3,'valor':p3,'desde':fin1+9,    'hasta':fin1+18},
        {'n':4,'valor':p4,'desde':fin1+18,   'hasta':None},
    ]
    if (m, dd) == (2, 29):
        avisos.append("Nacimiento el 29/2: en los años no bisiestos el cumpleaños numerológico "
                      "se toma el 1/3, y ahí cambian el Año Personal y los Pináculos.")
    des = [reducir(abs(mR-dR))[0], reducir(abs(dR-yR))[0]]
    des.append(reducir(abs(des[0]-des[1]))[0]); des.append(reducir(abs(mR-yR))[0])

    ap, _ = reducir(reducir(dd)[0] + reducir(m)[0] + reducir(hoy.year)[0])
    if (hoy.month, hoy.day) < (m, dd):
        ap, _ = reducir(reducir(dd)[0] + reducir(m)[0] + reducir(hoy.year - 1)[0])
        avisos.append(f"Año Personal calculado sobre el ciclo que comenzó en el cumpleaños "
                      f"de {hoy.year - 1}; cambia el {dd}/{m}.")
    mp, _ = reducir(ap + hoy.month)
    dp, _ = reducir(mp + hoy.day)
    _y_ciclo = hoy.year if (hoy.month, hoy.day) >= (m, dd) else hoy.year - 1
    _tot_ap = reducir(dd)[0] + reducir(m)[0] + reducir(_y_ciclo)[0]
    _e = next((x for x in traza_reduccion(_tot_ap)[:-1] if x in MAESTROS), None)
    if _e: ecos['Año Personal'] = {'eco': _e, 'traza': traza_reduccion(_tot_ap)}
    if nucleo.get('madurez_eco'):
        ecos['Madurez'] = {'eco': nucleo['madurez_eco'], 'traza': nucleo['madurez_traza']}

    return {**nucleo,
            'pinaculos': pinaculos, 'desafios': des,
            'anio_personal': ap, 'mes_personal': mp, 'dia_personal': dp,
            'deudas': sorted(deudas), 'deudas_txt': {d: DEUDA_TXT[d] for d in sorted(deudas)},
            'deudas_por_posicion': deudas_pos, 'ecos': ecos,
            'camino_formas': camino_formas, 'observaciones': observaciones,
            'avisos': avisos}

# ============================================================
# 5. BAZI
# ============================================================
_JQ_CACHE = {}

def _jieqi_utc(anios):
    """Términos solares (jieqi) en UTC, al segundo. v9.0 (E5): sxtwl solo da el índice y una
    primera aproximación; el instante exacto sale de Swiss Ephemeris (solcross_ut sobre la
    longitud del término: 270° + 15° × índice). Hasta v8.9 se truncaban los segundos y cada
    término quedaba hasta 59 s antes: en un nacimiento a menos de un minuto del cruce cambiaba
    el mes y, en el Lichun, el año."""
    out = []
    for a in anios:
        if a not in _JQ_CACHE:
            fila = []
            for jq in sxtwl.getJieQiByYear(a):
                lon_t = (270.0 + 15.0 * jq.jqIndex) % 360.0
                jd = swe.solcross_ut(lon_t, jq.jd - 8.0 / 24.0 - 1.0, swe.FLG_SWIEPH)
                y_, m_, d_, h_ = swe.revjul(jd)
                t = datetime(y_, m_, d_) + timedelta(seconds=round(h_ * 3600.0, 1))
                fila.append((t, jq.jqIndex))
            _JQ_CACHE[a] = fila
        out.extend(_JQ_CACHE[a])
    return sorted(out)

def _pilar_hora(tronco_dia: int, hh: int):
    hb = ((hh + 1) // 2) % 12
    return ((tronco_dia * 2 + hb) % 10, hb)

def bazi(fecha: str, hora, tz: str, lon: float | None = None,
         convencion: str | None = None, _alterna: bool = False, dst: bool | None = None):
    """Cuatro Pilares. Año y mes por el instante UTC contra los términos solares; día y hora
    por la HORA SOLAR LOCAL (3.ter, decisión 28/10/2026) cuando hay hora y longitud. Sin
    longitud cae a hora de reloj y lo declara."""
    convencion = convencion or CONVENCION_HORA_PILAR
    sin_hora = not hora
    y, m, dd = [int(x) for x in fecha.split("-")]
    local = _local_aware(fecha, hora, tz, lon if hora else None, dst)
    utc = local.astimezone(pytz.UTC).replace(tzinfo=None)
    avisos = []
    # Hora base para día y hora: solar si se puede, reloj si no.
    hora_pilar = None
    if not sin_hora:
        if convencion == "solar" and lon is not None:
            solar_dt, det = hora_solar_local(fecha, hora, tz, lon, dst)
            base_fecha, base_hh = solar_dt.date(), solar_dt.hour
            hora_pilar = {'convencion': 'hora solar local aparente', **det}
        else:
            base_fecha, base_hh = date(y, m, dd), int(hora.split(":")[0])
            hora_pilar = {'convencion': 'hora de reloj (civil)', 'hora_reloj': hora,
                          'dst_activo': (local.dst() or timedelta(0)) != timedelta(0),
                          'motivo': ('sin longitud: no se pudo pasar a hora solar' if lon is None
                                     else 'convención forzada a reloj')}
            if convencion == "solar" and lon is None:
                avisos.append("Pilar de hora calculado sobre la hora de reloj porque no se "
                              "recibió la longitud del lugar; la convención canónica es la hora "
                              "solar local.")

    jq = _jieqi_utc([y-1, y, y+1])

    lichun = [t for t, i in jq if i == 3 and t <= utc]
    anio_bazi = max(lichun).year
    idx_anio = (anio_bazi - 4) % 60
    ys = idx_anio % 10
    yG = (ys, idx_anio % 12)

    t_jie, i_jie = max((t, i) for t, i in jq if i % 2 == 1 and t <= utc)
    rama_mes = (2 + ((i_jie - 3) // 2)) % 12
    mG = ((ys * 2 + 2 + ((rama_mes - 2) % 12)) % 10, rama_mes)

    if not sin_hora:
        cercano = min((abs((utc-t).total_seconds()), t) for t, i in jq if i % 2 == 1)
        if cercano[0] < 12*3600:
            avisos.append("Nacimiento a menos de 12 horas de un término solar: el pilar de mes "
                          "se determinó por el instante real, no por la fecha calendaria. "
                          "Otros calculadores pueden diferir.")
    else:
        pass   # v9.0 (D6): calcular() revisa el día entero y avisa solo si algo cambia

    f_local = base_fecha if not sin_hora else date(y, m, dd)
    if not sin_hora and base_hh >= 23:
        f_local = f_local + timedelta(days=1)
        avisos.append("Naciste en la hora Zi (23:00–01:00 solar). Este sistema aplica EARLY-ZI: el "
                      "pilar de día corresponde al día siguiente. Otros calculadores pueden "
                      "mostrarte otro Día Maestro; la diferencia es de escuela, no de error.")
    dG = sxtwl.fromSolar(f_local.year, f_local.month, f_local.day).getDayGZ()

    pilares = [yG, mG, (dG.tg, dG.dz)]
    pilar_hora = None
    if not sin_hora:
        pilar_hora = _pilar_hora(dG.tg, base_hh)
        pilares.append(pilar_hora)
        # 2.3 / 8.5: hora en el borde de una franja (las franjas giran en las horas impares).
        base_min = base_hh * 60 + (solar_dt.minute if hora_pilar['convencion'].startswith('hora solar')
                                   else int(hora.split(":")[1]))
        dist = min(abs(base_min - b) for b in range(60, 24 * 60 + 60, 120))
        hora_pilar['minutos_al_borde_de_franja'] = int(dist)
        # v9.0 (E9): el borde está ADELANTE si los minutos dentro del bloque de 2 h (que
        # arranca en hora par) son < 60, y ATRÁS si son ≥ 60. Hasta v8.9 el signo estaba
        # invertido y el aviso nombraba el pilar que ya tenía. Ahora se recalcula la carta
        # entera del otro lado del borde (hora, día por early-zi y elemento útil, 2.3).
        cruce = None
        if dist <= 10 and not _alterna:
            cruce = (1 if (base_min % 120) < 60 else -1, int(dist))
        # Contraste declarado: qué habría dado la hora de reloj (para el anexo y el aviso).
        if hora_pilar['convencion'].startswith('hora solar'):
            f_rel = date(y, m, dd); hh_rel = int(hora.split(":")[0])
            if hh_rel >= 23: f_rel += timedelta(days=1)
            dR = sxtwl.fromSolar(f_rel.year, f_rel.month, f_rel.day).getDayGZ()
            alt = _pilar_hora(dR.tg, hh_rel)
            hora_pilar['pilar_hora_por_reloj'] = f"{TRONCOS[alt[0]][0]} {RAMAS[alt[1]][0]}"
            hora_pilar['pilar_dia_por_reloj'] = f"{TRONCOS[dR.tg][0]} {RAMAS[dR.dz][0]}"
            hora_pilar['cambia_hora'] = alt != pilar_hora
            hora_pilar['cambia_dia'] = (dR.tg, dR.dz) != (dG.tg, dG.dz)
            if hora_pilar['cambia_hora'] or hora_pilar['cambia_dia']:
                avisos.append(f"Pilar de hora calculado sobre la hora solar local de tu lugar de "
                              f"nacimiento ({hora_pilar['hora_solar']}), no sobre la hora de reloj "
                              f"({hora}): la diferencia es de {hora_pilar['correccion_total_min']:+.0f} "
                              f"minutos (longitud y ecuación del tiempo"
                              + (", incluido el horario de verano" if hora_pilar['dst_activo'] else "")
                              + "). Otros calculadores, que usan la hora de reloj, pueden mostrarte "
                              + ("otro animal de hora" if not hora_pilar['cambia_dia'] else
                                 "otro Día Maestro y otro animal de hora")
                              + "; la diferencia es de convención, no de error.")
    else:
        avisos.append("Sin hora de nacimiento: el pilar de hora Bazi no se calcula. "
                      "La lectura va sobre tres pilares.")

    bal = {e: 0.0 for e in ELEMENTOS}
    for tg, dz in pilares:
        bal[TRONCOS[tg][2]] += 1.0
        for tgo, peso in OCULTOS[dz]:
            bal[TRONCOS[tgo][2]] += peso
    bal = {k: round(v, 2) for k, v in bal.items()}

    PESO_PILAR = (0.8, 2.0, 1.2, 1.0)      # año · MES · día · hora
    balp = {e: 0.0 for e in ELEMENTOS}
    for (tg, dz), w in zip(pilares, PESO_PILAR):
        balp[TRONCOS[tg][2]] += 1.0 * w
        for tgo, peso in OCULTOS[dz]:
            balp[TRONCOS[tgo][2]] += peso * w
    balp = {k: round(v, 2) for k, v in balp.items()}

    dm = TRONCOS[dG.tg]
    el_dm = dm[2]
    rama_mes = pilares[1][1]
    el_mes = TRONCOS[max(OCULTOS[rama_mes], key=lambda t: t[1])[0]][2]
    en_estacion = el_mes in (el_dm, NUTRE[el_dm])

    totalp = sum(balp.values()) or 1
    fuerza = (balp[el_dm] + balp[NUTRE[el_dm]]) / totalp
    umbral = 0.45 if en_estacion else 0.55
    fuerte = fuerza > umbral

    candidatos_base = [CONTROLA[el_dm], DRENA[el_dm]] if fuerte else [NUTRE[el_dm], el_dm]
    UMBRAL_EXCEDENTE = 0.35
    _cand_exc = sorted(((v, e) for e, v in balp.items() if e != el_dm), reverse=True)
    excedente, part_exc = None, 0.0
    if _cand_exc:
        _v, _e = _cand_exc[0]
        _p = _v / totalp
        if _p > UMBRAL_EXCEDENTE:
            excedente, part_exc = _e, _p

    candidatos = list(candidatos_base)
    descartados = []
    vacio_por_descarte = False
    if excedente:
        descartados = [c for c in candidatos if NUTRE[excedente] == c]
        candidatos = [c for c in candidatos if c not in descartados]
        # v9.0 (D7): la regla de no nutrir al fuerte manda sobre la del excedente. Si el que
        # controla al excedente es el propio elemento del Día Maestro o su recurso, no se suma
        # (en 9 de 18.844 cartas le recetaba a un Día Maestro fuerte su propio sostén).
        _ctrl = CONTROLA[excedente]
        if fuerte and _ctrl not in candidatos and _ctrl not in (el_dm, NUTRE[el_dm]):
            candidatos.append(_ctrl)
        if not candidatos:
            candidatos = list(candidatos_base)
            vacio_por_descarte = True

    _ord = sorted(candidatos, key=lambda e: balp[e])
    util = _ord[0]
    margen = round(balp[_ord[1]] - balp[_ord[0]], 3) if len(_ord) > 1 else None
    margen_estrecho = margen is not None and margen < 0.15
    yong_shen_metodo = {
        'candidatos_base': candidatos_base,
        'excedente': excedente,
        'participacion_excedente': round(part_exc, 3) if excedente else 0.0,
        'umbral_excedente': UMBRAL_EXCEDENTE,
        'descartados_por_generar_exceso': descartados,
        'descarte_revertido_por_lista_vacia': vacio_por_descarte,
        'candidatos_finales': _ord,
        'pesos_candidatos': {e: balp[e] for e in _ord},
        'elegido': util,
        'margen': margen,
        'margen_estrecho': margen_estrecho,
    }
    ausentes = [e for e, v in bal.items() if v == 0]

    ramas = [dz for _, dz in pilares]
    rel = {'chong': [], 'liuhe': [], 'sanhe': []}
    for i in range(len(ramas)):
        for j in range(i+1, len(ramas)):
            par = tuple(sorted((ramas[i], ramas[j])))
            if par in [tuple(sorted(p)) for p in CHONG]:
                rel['chong'].append((RAMAS[ramas[i]][2], RAMAS[ramas[j]][2]))
            if par in [tuple(sorted(p)) for p in LIUHE]:
                rel['liuhe'].append((RAMAS[ramas[i]][2], RAMAS[ramas[j]][2]))
    for trio, el in SANHE:
        pres = [i for i in trio if i in ramas]
        if len(set(pres)) == 3:
            rel['sanhe'].append({'elemento': el, 'completa': True, 'tipo': 'Sanhé (trío)',
                                 'presentes': [RAMAS[i][2] for i in trio]})
        elif len(set(pres)) == 2:
            rel['sanhe'].append({'elemento': el, 'completa': False,
                                 'tipo': 'media combinación (Banhe)',
                                 'presentes': [RAMAS[i][2] for i in set(pres)]})

    def gz(t):
        return {'ganzhi': f"{TRONCOS[t[0]][0]} {RAMAS[t[1]][0]}",
                'tronco': TRONCOS[t[0]][0], 'elemento_tronco': TRONCOS[t[0]][2],
                'polaridad': TRONCOS[t[0]][3], 'animal': RAMAS[t[1]][2],
                'elemento_rama': RAMAS[t[1]][3]}

    res = {'sin_hora': sin_hora, 'anio_bazi': anio_bazi,
            'pilar_anio': gz(pilares[0]), 'pilar_mes': gz(pilares[1]),
            'pilar_dia': gz(pilares[2]),
            'pilar_hora': gz(pilar_hora) if pilar_hora else None,
            'hora_pilar': hora_pilar,
            'dia_maestro': {'tronco': dm[0], 'elemento': dm[2], 'polaridad': dm[3],
                            'descripcion': f"{dm[2]} {dm[3]}"},
            'balance': bal, 'balance_ponderado': balp,
            'fuerza_dm': round(fuerza, 3), 'umbral_fuerza': umbral,
            'en_estacion': en_estacion, 'elemento_mes': el_mes,
            'dm_fuerte': fuerte, 'elemento_util': util, 'ausentes': ausentes,
            'yong_shen_metodo': yong_shen_metodo,
            'metodo_fuerza': ("Fuerza calculada sobre el balance ponderado por pilar "
                              "(año 0.8 · mes 2.0 · día 1.2 · hora 1.0), con umbral "
                              f"corregido por estación ({umbral}). El balance que se "
                              "muestra es la cuenta plana, verificable a mano."),
            'relaciones': rel, 'avisos': avisos}
    if not sin_hora and not _alterna and cruce:
        signo, dmin = cruce
        otro = (local.astimezone(pytz.UTC) + timedelta(minutes=signo * (dmin + 1))).astimezone(pytz.timezone(tz))
        alt = bazi(otro.strftime("%Y-%m-%d"), otro.strftime("%H:%M"), tz, lon, convencion, _alterna=True)
        hora_pilar['pilar_hora_si_cruza'] = alt['pilar_hora']['ganzhi']
        hora_pilar['del_otro_lado'] = {
            'hora_reloj': otro.strftime("%H:%M"), 'pilar_hora': alt['pilar_hora']['ganzhi'],
            'pilar_dia': alt['pilar_dia']['ganzhi'], 'dia_maestro': alt['dia_maestro']['descripcion'],
            'elemento_util': alt['elemento_util'],
            'cambia_dia': alt['pilar_dia']['ganzhi'] != res['pilar_dia']['ganzhi'],
            'cambia_util': alt['elemento_util'] != util}
        o = hora_pilar['del_otro_lado']
        extra = []
        if o['cambia_dia']: extra.append(f"también el Día Maestro ({o['dia_maestro']})")
        if o['cambia_util']: extra.append(f"y el elemento que te hace bien ({o['elemento_util']})")
        avisos.append(f"La hora de nacimiento cae a {dmin} minutos del borde de una franja horaria "
                      f"china: unos minutos {'después' if signo > 0 else 'antes'} el pilar de hora "
                      f"sería {o['pilar_hora']}" + ((", y cambiaría " + " ".join(extra)) if extra else "")
                      + ". Conviene confirmar la hora exacta.")
    return res

# ============================================================
# 6. ENTRADA ÚNICA
# ============================================================
# v9.0 (D11) · REGLA DE LA CASA (Fabricio, 22/11/2026): «la casa toma como fórmula el sistema
# bazi, y si el sistema bazi lo corrobora la casa también, porque existe un fundamento».
# Un dato de los números que el motor publica solo como OBSERVACIÓN (otra forma de sumar el
# Camino) entra al cuerpo de la lectura solo si el Bazi de la carta dice lo mismo. La tabla
# es fija y la calcula el motor, para que cualquiera la pueda revisar (como la de la Y).
# Proporciones sobre el balance ponderado por pilar.
def _partes(b):
    tot = sum(b['balance_ponderado'].values()) or 1
    return {e: v / tot for e, v in b['balance_ponderado'].items()}

def corrobora_bazi(deuda: int, b: dict) -> dict:
    el = b['dia_maestro']['elemento']; pt = _partes(b); fuerte = b['dm_fuerte']
    expresion = DRENA[el]                                   # lo que el Día Maestro produce
    poder = CONTROLA[el]                                     # lo que controla al Día Maestro
    riqueza = next(e for e in ELEMENTOS if CONTROLA[e] == el)  # lo que el Día Maestro controla
    pct = lambda e: f"{e} {100 * pt[e]:.0f} %"
    if deuda == 13:      # trabajo paciente: Día Maestro débil y poca expresión/obra
        ok = (not fuerte) and pt[expresion] <= 0.10
        crit = "Día Maestro débil y el elemento de la obra (lo que el Día Maestro produce) en 10 % o menos"
        dato = f"Día Maestro {b['dia_maestro']['descripcion']} {'fuerte' if fuerte else 'débil'}; {pct(expresion)}"
    elif deuda == 14:    # moderación: un elemento en exceso
        top = max(pt, key=pt.get)
        ok = pt[top] > 0.35
        crit = "un elemento por encima del 35 % de la carta (exceso)"
        dato = f"el más pesado: {pct(top)}"
    elif deuda == 16:    # caída del ego: Día Maestro fuerte y su propio elemento domina
        top = max(pt, key=pt.get)
        ok = fuerte and top == el
        crit = "Día Maestro fuerte y su propio elemento (los compañeros) es el más pesado de la carta"
        dato = f"Día Maestro {b['dia_maestro']['descripcion']} {'fuerte' if fuerte else 'débil'}; el más pesado: {pct(top)}"
    elif deuda == 19:    # dar sin esperar: Día Maestro fuerte con riqueza o poder dominantes
        ok = fuerte and max(pt[riqueza], pt[poder]) >= 0.30
        crit = "Día Maestro fuerte y el elemento de la riqueza o el del poder en 30 % o más"
        dato = f"Día Maestro {b['dia_maestro']['descripcion']} {'fuerte' if fuerte else 'débil'}; {pct(riqueza)} (riqueza), {pct(poder)} (poder)"
    else:
        return {'corrobora': False, 'criterio': 'sin criterio para este dato', 'dato': ''}
    return {'corrobora': bool(ok), 'criterio': crit, 'dato': dato}

def _resolver_lugar(datos: dict):
    lat, lon = datos.get('lat'), datos.get('lon')
    if lat is None or lon is None:
        lugar = (datos.get('lugar') or "").strip()
        # P4 (v8.8.1): sin coordenadas explícitas, el texto tiene que traer país.
        # «Córdoba» sola cae en España en Nominatim; «Córdoba, Argentina» no.
        if len([p for p in lugar.split(",") if p.strip()]) < 2:
            raise ValueError(f"Lugar «{lugar}» sin país: pasá «Ciudad, País» "
                             "(por ejemplo «Córdoba, Argentina») o lat y lon explícitas.")
        lat, lon = geocodificar(lugar)
        if lat is None:
            raise ValueError(f"No se pudo geolocalizar «{lugar}». "
                             "Pasá lat y lon explícitas.")
    tz = datos.get('tz') or TimezoneFinder().timezone_at(lat=lat, lng=lon)
    if not tz:
        raise ValueError(f"No se pudo determinar zona horaria para lat={lat}, lon={lon}.")
    return lat, lon, tz

def calcular(datos: dict) -> dict:
    validar_fecha(datos.get('fecha'))
    validar_hora(datos.get('hora'))
    lat, lon, tz = _resolver_lugar(datos)
    hora = datos.get('hora') or None
    dst = datos.get('dst')                 # v9.0 (E6): lectura elegida si la hora es dudosa
    A = astro(datos['fecha'], hora, lat, lon, tz, dst)
    N = numerologia(datos.get('nombre'), datos['fecha'], datos.get('fecha_consulta'))
    B = bazi(datos['fecha'], hora, tz, lon, dst=dst)
    DY = da_yun(datos['fecha'], hora, tz, datos.get('sexo'),
                datos.get('nombre_pila') or datos.get('nombre'), lon=lon, dst=dst,
                es_pila=bool(datos.get('nombre_pila')))
    # v9.0 (E6, E10): la hora de reloj puede no alcanzar para saber el instante.
    hora_dudosa = None
    est = _estado_hora(datos['fecha'], hora, tz)
    if est in ('repetida', 'inexistente') and dst is None:
        A2 = astro(datos['fecha'], hora, lat, lon, tz, True)
        B2 = bazi(datos['fecha'], hora, tz, lon, dst=True)
        def _res(a_, b_):
            return {'utc': a_['utc'].strftime('%Y-%m-%d %H:%M UTC'), 'asc': a_['asc'], 'mc': a_['mc'],
                    'luna': a_['pos']['Luna']['fmt'],
                    'pilar_dia': b_['pilar_dia']['ganzhi'], 'pilar_hora': b_['pilar_hora']['ganzhi'],
                    'elemento_util': b_['elemento_util']}
        hora_dudosa = {'tipo': est, 'usada': _res(A, B), 'alternativa': _res(A2, B2),
                       'como_elegir': "pasar datos['dst']=True para la otra lectura"}
        txt = ("esa hora pasó dos veces porque esa noche se atrasó el reloj" if est == 'repetida'
               else "esa hora no existió porque esa noche se adelantó el reloj")
        cambia = [k for k in ('asc', 'mc', 'luna', 'pilar_dia', 'pilar_hora', 'elemento_util')
                  if hora_dudosa['usada'][k] != hora_dudosa['alternativa'][k]]
        nombres = {'asc': 'el Ascendente', 'mc': 'el Medio Cielo', 'luna': 'el grado de la Luna',
                   'pilar_dia': 'el Día Maestro', 'pilar_hora': 'el pilar de hora', 'elemento_util': 'el elemento útil'}
        A['avisos'].append(f"Hora de nacimiento dudosa: {txt} en {tz}. Se calculó con la hora estándar "
                           f"({hora_dudosa['usada']['utc']}); la otra lectura es {hora_dudosa['alternativa']['utc']}"
                           + (f" y cambia {', '.join(nombres[k] for k in cambia)}" if cambia else " y no cambia nada de lo publicado")
                           + ". Conviene confirmar con la partida de nacimiento.")
    # v9.0 (E7, D6): sin hora, se revisa el día entero (00:00 y 23:59 de reloj). Lo que
    # cambia dentro del día se publica con sus dos posibilidades; lo que no, queda firme.
    sin_hora_posibles = None
    if not hora:
        def _hm(mi): return f"{mi // 60:02d}:{mi % 60:02d}"
        def _val(mi, clave):
            h = _hm(mi)
            if clave in ('pilar_anio', 'pilar_mes', 'pilar_dia'):
                return bazi(datos['fecha'], h, tz, lon)[clave]['ganzhi']
            if clave == 'dia_maestro':
                return bazi(datos['fecha'], h, tz, lon)['dia_maestro']['descripcion']
            return astro(datos['fecha'], h, lat, lon, tz)['pos'][clave]['fmt'].split(' ', 1)[1]
        def _tramos(clave):
            v0, v1 = _val(0, clave), _val(1439, clave)
            if v0 == v1:
                return None
            lo, hi = 0, 1439                      # un solo cambio en el día (bisección al minuto)
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if _val(mid, clave) == v0: lo = mid
                else: hi = mid
            return [{'valor': v0, 'desde': '00:00', 'hasta': _hm(hi)},
                    {'valor': v1, 'desde': _hm(hi), 'hasta': '23:59'}]
        a0 = astro(datos['fecha'], "00:00", lat, lon, tz); a1 = astro(datos['fecha'], "23:59", lat, lon, tz)
        cambian = {}
        for k in list(a0['pos']) + ['pilar_anio', 'pilar_mes', 'pilar_dia', 'dia_maestro']:
            t = _tramos(k)
            if t: cambian[k] = t
        sin_hora_posibles = {'luna_desde': a0['pos']['Luna']['fmt'], 'luna_hasta': a1['pos']['Luna']['fmt'],
                             'cambian_en_el_dia': cambian}
        for x in A['aspectos']:
            if 'Luna' in (x['a'], x['b']):
                x['aproximado_sin_hora'] = True
        if cambian:
            nombres = {'pilar_anio': 'el año chino', 'pilar_mes': 'el mes chino', 'pilar_dia': 'el pilar de día',
                       'dia_maestro': 'el Día Maestro'}
            txt = "; ".join(f"{nombres.get(k, k)}: " + " o ".join(f"{t['valor']} (de {t['desde']} a {t['hasta']})" for t in v)
                            for k, v in cambian.items())
            A['avisos'].append("Sin hora de nacimiento, hay datos que cambian dentro de ese mismo día y "
                               f"dependen de la hora: {txt}, en hora de reloj. La lectura toma el valor "
                               "que rige la mayor parte del día y nombra el otro como posibilidad.")
    elif est == 'lmt' and hora:
        A['avisos'].append("Nacimiento anterior a la hora oficial del país: la hora se tomó como "
                           "hora media del lugar de nacimiento (por su longitud).")
    # v9.0 (D11): cada observación de deuda lleva si el calendario chino la corrobora.
    for o in N.get('observaciones', []):
        if o['tipo'] == 'deuda':
            o['bazi'] = corrobora_bazi(o['valor'], B)
            o['entra_al_cuerpo'] = o['bazi']['corrobora']
        else:
            o['bazi'] = None; o['entra_al_cuerpo'] = False
    # v9.0 (D10): escuela clásica en los dos hemisferios, declarada.
    if lat < 0:
        B['avisos'].append("El calendario chino se calcula igual en los dos hemisferios: es la escuela "
                           "clásica. Algunas escuelas modernas invierten las estaciones en el sur; esta no.")
    nivel = ("fecha" if hora is None and not datos.get('nombre') else
             "fecha+nombre" if hora is None else
             "completo" if datos.get('nombre') else "fecha+hora")
    lugar_txt = (datos.get('lugar') or '').strip()
    if datos.get('lat') is None and lugar_txt in _GEO_NOMBRE:
        A['avisos'].append(f"Lugar buscado: «{lugar_txt}». Lugar encontrado: «{_GEO_NOMBRE[lugar_txt]}» "
                           f"({lat:.4f}, {lon:.4f}). Si no es ese, la hora solar y las casas cambian.")
    return {'datos': {**datos, 'lat': lat, 'lon': lon, 'tz': tz,
                      'lugar_encontrado': _GEO_NOMBRE.get(lugar_txt) if datos.get('lat') is None else None},
            'astro': A, 'num': N, 'bazi': B, 'da_yun': DY, 'nivel': nivel, 'hora_dudosa': hora_dudosa,
            'sin_hora_posibles': sin_hora_posibles,
            'avisos': A['avisos'] + N['avisos'] + B['avisos']
                      + ([DY['declaracion_sexo']] if DY.get('declaracion_sexo') else []),
            'quiron_disponible': QUIRON_DISPONIBLE, 'efemerides': A['efemerides'],
            'version': VERSION}

# ============================================================
# 8. SEXO DERIVADO DEL NOMBRE — para la dirección del Da Yun
# ============================================================
_NOM_F = {
    "maria","ana","lucia","sofia","valentina","martina","camila","julieta","paula",
    "carolina","laura","daniela","gabriela","mariana","florencia","agustina","victoria",
    "isabel","isabella","catalina","antonella","emilia","renata","olivia","delfina",
    "milagros","pilar","rocio","belen","macarena","candelaria","josefina",
    "clara","elena","irene","marta","teresa","rosa","carmen","dolores","mercedes",
    "beatriz","raquel","esther","ruth","judith","ines","soledad","silvina","silvia",
    "veronica","patricia","claudia","alejandra","andrea","natalia","romina","yamila",
    "micaela","brenda","melina","ayelen","abril","mia","luna","zoe","alma","aurora",
    "eugenia","virginia","cecilia","monica","susana","norma","graciela","liliana",
    "adriana","viviana","marcela","sandra","karina","vanina","noelia","estela","nelida",
    "juana","francisca","manuela","antonia","carla","barbara",
    "debora","tamara","sara","rebeca","noemi","ester","miriam","perla","celeste","constanza","jazmin",
    "malena","matilda","matilde","amparo","consuelo","socorro","pia","ailen",
    # v9.0 (D9): ampliación
    "ines","raquel","ruth","beatriz","lourdes","nieves","marisol","maribel","mariel","abigail",
    "isabel","rocio","pilar","esperanza","azul","jimena","ximena","guillermina","ludmila",
    "luciana","bianca","sabrina","vanesa","vanessa","lorena","yesica","jesica","jessica",
    "karina","carina","marina","agostina","valeria","morena","nerea","noelia","ofelia","estela",
}
_NOM_M = {
    "juan","jose","luis","carlos","jorge","miguel","manuel","francisco","javier",
    "fernando","roberto","ricardo","eduardo","alberto","antonio","pedro","pablo",
    "diego","martin","nicolas","matias","sebastian","santiago","tomas","lucas",
    "agustin","facundo","joaquin","gonzalo","ignacio","rodrigo","alejandro","andres",
    "gabriel","daniel","david","marcos","emiliano","federico","gaston","damian",
    "leandro","mariano","maximiliano","hernan","ezequiel","gustavo","claudio","marcelo",
    "sergio","hugo","raul","ruben","oscar","hector","norberto","osvaldo","horacio",
    "guillermo","gerardo","rafael","ramiro","bruno","benjamin","bautista","luca",
    "thiago","valentin","lautaro","dante","enzo","franco","ivan","juanma","julian",
    "leonardo","lorenzo","mateo","maximo","nahuel","octavio","salvador","simon",
    "vicente","fabian","adrian","emanuel","cristian","walter",
    # v9.0 (D9): ampliación
    "fabricio","mauro","renzo","gino","aldo","elio","jesus","borja","joshua","josue","isaias","jeremias","kevin","alexander","alex","axel",
    "brian","jonathan","jonatan","elias","tobias","jonas","ulises","felipe","ramon","alfredo",
    "arturo","victor","enrique","alfonso","jaime","joel","isaac","abel","noel","samuel","ismael",
    "nehuen","ciro","gael","ian","liam","noah","benicio","mauricio","patricio","rodolfo","silvio",
    "teodoro","emilio","dario","marco","marcelino","nestor","omar","pascual","rogelio","wenceslao",
    "esteban","gregorio","ernesto","armando","aurelio","augusto","cesar","efrain",
}
_NOM_AMBIGUO = {
    "ariel","cruz","reyes","trinidad","rosario","guadalupe","yael","noa","alexis",
    "rene","denis","loan","ian","angel","angeles","concepcion","natividad","amor",
    "paz","alba","luz","sol","cielo","real","santi","robin","sasha","dylan","milan",
}
_A_MASC = {"luca","bautista","nicola","elisha","josua","jeremia","zacarias","matias",
           "tobias","elias","jonas","lucas","tomas","borja","joshua","nikita"}
_O_FEM = {"rosario","consuelo","amparo","socorro","carmelo"}

def _sin_tildes(x: str) -> str:
    x = unicodedata.normalize("NFD", x.lower())
    return "".join(c for c in x if unicodedata.category(c) != "Mn")

def sexo_desde_nombre(nombre: str | None, es_pila: bool = False):
    """Deriva el sexo del nombre de nacimiento. Devuelve una HIPÓTESIS.
    v9.0 (E8, D9): el segundo nombre desempata SOLO si el primero es ambiguo (2.1.3) y SOLO
    si se recibieron los nombres de pila aparte (`es_pila`): en el nombre completo la
    segunda palabra puede ser un apellido («Ariel Luna» no es mujer)."""
    if not nombre or not nombre.strip():
        return {'sexo': None, 'criterio': 'sin nombre', 'certeza': None,
                'declaracion': "No se derivó el sexo: falta el nombre completo de nacimiento."}
    partes = [_sin_tildes(w) for w in nombre.split() if len(w) > 1]
    partes = [w for w in partes if w not in ("de", "del", "la", "las", "los", "y")]
    if not partes:
        return {'sexo': None, 'criterio': 'nombre no analizable', 'certeza': None,
                'declaracion': "No se derivó el sexo: el nombre no pudo analizarse."}
    for i, w in enumerate(partes[:2]):
        etiqueta = "primer nombre" if i == 0 else "segundo nombre"
        if i == 1 and not (es_pila and partes[0] in _NOM_AMBIGUO):
            break
        if w in _NOM_AMBIGUO:
            continue
        for sx, lista in (('F', _NOM_F), ('M', _NOM_M)):
            if w in lista:
                return {'sexo': sx, 'criterio': f"{etiqueta} «{w}» en la lista {'femenina' if sx=='F' else 'masculina'}",
                        'certeza': 'alta',
                        'declaracion': f"El sexo se derivó del nombre de nacimiento ({etiqueta} "
                                       f"«{w}»), no fue declarado por el consultante. De él "
                                       f"depende la dirección del Da Yun: si el dato es otro, "
                                       f"la lectura de los ciclos cambia entera."}
    w = partes[0]
    if w not in _NOM_AMBIGUO:
        if w.endswith("a") and w not in _A_MASC: sx = 'F'
        elif w.endswith("o") and w not in _O_FEM: sx = 'M'
        else: sx = None
        if sx:
            return {'sexo': sx, 'criterio': f"morfología del primer nombre «{w}» (termina en -{w[-1]})",
                    'certeza': 'media',
                    'declaracion': f"El sexo se derivó por la terminación del nombre de "
                                   f"nacimiento («{w}»), no fue declarado ni figura en "
                                   f"lista. Es la inferencia más débil de este sistema: "
                                   f"convendría confirmarla antes de leer los ciclos."}
    return {'sexo': None,
            'criterio': f"«{partes[0]}» es ambiguo o no reconocido",
            'certeza': None,
            'declaracion': f"No se derivó el sexo: «{partes[0]}» se usa para ambos o no "
                           f"está en las listas. El Da Yun no se calcula y se declara "
                           f"la ausencia; si el consultante aporta el dato (o sus nombres "
                           f"de pila aparte, para desempatar con el segundo), se recalcula."}

# ============================================================
# 7. TIEMPO Y VÍNCULO
# ============================================================
LENTOS = ('Júpiter', 'Saturno', 'Urano', 'Neptuno', 'Plutón', 'Nodo N')
SENSIBLES = ('Sol', 'Luna', 'Mercurio', 'Venus', 'Marte', 'Júpiter', 'Saturno', 'Quirón',
             'Nodo N', 'Asc', 'MC')

def anio_bazi_actual(fecha_consulta: str | None = None, tz: str = "UTC"):
    """Tronco y rama del año Bazi en curso, con Lichun por instante (3.ter.2)."""
    f = fecha_consulta or date.today().isoformat()
    b = bazi(f, "12:00", tz)
    return {'anio': b['anio_bazi'], **b['pilar_anio']}

def da_yun(fecha: str, hora, tz: str, sexo: str | None = None,
           nombre: str | None = None, n: int = 8, lon: float | None = None, dst: bool | None = None,
           es_pila: bool = False):
    """Pilares de suerte (Da Yun). Dirección por polaridad del año + sexo; edad de
    inicio por distancia real al término solar (3 días = 1 año)."""
    origen = "declarado por el consultante"
    declaracion = None
    if sexo not in ("M", "F"):
        inf = sexo_desde_nombre(nombre, es_pila)
        sexo, origen, declaracion = inf['sexo'], inf['criterio'], inf['declaracion']
        certeza = inf['certeza']
    else:
        certeza = 'declarada'

    if sexo not in ("M", "F"):
        return {'disponible': False, 'origen_sexo': origen, 'certeza_sexo': None,
                'motivo': "El Da Yun no se calcula: la dirección del ciclo depende de la "
                          "polaridad del tronco de año combinada con el sexo, y el sexo no "
                          "pudo derivarse del nombre de nacimiento ni fue declarado. "
                          + (declaracion or "")
                          + " La lectura del Cielo Oriental se entrega sin Da Yun y se "
                            "declara la ausencia (8.5). No se supone: suponer mal la "
                            "dirección no da un matiz equivocado, da la década equivocada.",
                'ciclos': []}
    if not hora:
        return {'disponible': False,
                'motivo': "El Da Yun se calcula por distancia al término solar, que necesita "
                          "la hora de nacimiento. Sin hora se declara ausente (2.3).",
                'ciclos': []}

    b = bazi(fecha, hora, tz, lon, dst=dst)
    y, m, dd = [int(x) for x in fecha.split("-")]
    utc = _utc_desde_local(fecha, hora, tz, lon if hora else None, dst).replace(tzinfo=None)

    tronco_anio = next(i for i, t in enumerate(TRONCOS) if t[0] == b['pilar_anio']['tronco'])
    yang = TRONCOS[tronco_anio][3] == "Yang"
    adelante = (yang and sexo == "M") or (not yang and sexo == "F")

    jies = sorted(t for t, i in _jieqi_utc([y-1, y, y+1]) if i % 2 == 1)
    borde = min(t for t in jies if t > utc) if adelante else max(t for t in jies if t <= utc)
    dias = abs((borde - utc).total_seconds()) / 86400.0
    edad_inicio = dias / 3.0

    tm = next(i for i, t in enumerate(TRONCOS) if t[0] == b['pilar_mes']['tronco'])
    rm = next(i for i, r in enumerate(RAMAS) if r[2] == b['pilar_mes']['animal'])
    idx = next(c for c in range(60) if c % 10 == tm and c % 12 == rm)

    ciclos = []
    for k in range(1, n + 1):
        j = (idx + k) % 60 if adelante else (idx - k) % 60
        tg, dz = j % 10, j % 12
        desde = edad_inicio + (k - 1) * 10
        ciclos.append({'n': k, 'desde': round(desde, 1), 'hasta': round(desde + 10, 1),
                       'ganzhi': f"{TRONCOS[tg][0]} {RAMAS[dz][0]}",
                       'tronco': TRONCOS[tg][0], 'animal': RAMAS[dz][2],
                       'elemento_tronco': TRONCOS[tg][2], 'elemento_rama': RAMAS[dz][3]})
    return {'disponible': True, 'direccion': 'adelante' if adelante else 'atrás',
            'sexo': sexo, 'origen_sexo': origen, 'certeza_sexo': certeza,
            'declaracion_sexo': declaracion,
            'edad_inicio': round(edad_inicio, 2),
            'dias_al_termino': round(dias, 2), 'ciclos': ciclos,
            'nota': "Edad de inicio calculada por distancia real al término solar "
                    "(3 días = 1 año), no por aproximación estadística."}

CICLOS = {'Marte': 1.88, 'Júpiter': 11.86, 'Saturno': 29.46, 'Quirón': 50.70,
          'Urano': 84.02, 'Nodo N': 18.61}
HITOS = {0: 'Retorno', 180: 'Medio ciclo', 90: 'Cuarto de ciclo', 270: 'Cuarto de ciclo'}

def hitos_ciclicos(pos_natal: dict, pos_transito: dict, orbe_max: float = 1.5):
    """Hitos de ciclo: un cuerpo en tránsito sobre su propia posición natal."""
    out = []
    for cuerpo, anios in CICLOS.items():
        n, t = pos_natal.get(cuerpo), pos_transito.get(cuerpo)
        if not n or not t:
            continue
        sep = (t['grados'] - n['grados']) % 360
        for ang, nombre in HITOS.items():
            d = abs(sep - ang); d = min(d, 360 - d)
            if cuerpo == 'Marte' and nombre != 'Retorno':
                continue
            if d <= orbe_max:
                out.append({'cuerpo': cuerpo, 'hito': nombre, 'orbe': round(d, 2),
                            'ciclo_anios': anios, 'retro': t['retro'],
                            'pos_transito': t['fmt'], 'pos_natal': n['fmt'],
                            'etiqueta': f"{nombre} de {cuerpo}"})
                break
    out.sort(key=lambda x: (x['hito'] != 'Retorno', x['orbe']))
    return out

def _puntos_sensibles(A: dict):
    puntos = {k: v['grados'] for k, v in A['pos'].items() if k in SENSIBLES}
    if A['asc_deg'] is not None:
        puntos['Asc'] = A['asc_deg']; puntos['MC'] = A['mc_deg']
    return puntos

def _transitos_sobre(A: dict, T: dict, cusps=None):
    puntos = _puntos_sensibles(A)
    out = []
    for tp, ti in T['pos'].items():
        if tp in ('Nodo S', 'Lilith'):
            continue
        lento = tp in LENTOS or tp == 'Quirón'     # v9.0 (D4): Quirón se mueve como un lento
        for np_, ng in puntos.items():
            diff = abs(ti['grados'] - ng) % 360
            if diff > 180: diff = 360 - diff
            for nom, ang in ASPECTOS.items():
                orbe = abs(diff - ang)
                tope = (1.0 if tp == 'Luna' else (3.0 if lento else 2.0))
                if orbe <= tope:
                    out.append({'transito': tp, 'aspecto': nom, 'natal': np_,
                                'orbe': round(orbe, 2), 'lento': lento,
                                'retro': ti['retro'], 'pos': ti['fmt'],
                                'casa_natal': casa_de(ti['grados'], cusps) if cusps else None})
                    break
    out.sort(key=lambda x: (not x['lento'], x['orbe']))
    return out

def transitos(datos_natal: dict, fecha_objetivo: str, hora_objetivo: str = "12:00",
              natal: dict | None = None):
    """Tránsitos reales a una fecha (3.6). Lentos sobre puntos sensibles; Luna sólo
    con orbe ≤ 1°. `natal` permite pasar un calcular() ya hecho y no repetirlo."""
    nat = natal or calcular(datos_natal)
    A = nat['astro']
    lat, lon, tz = nat['datos']['lat'], nat['datos']['lon'], nat['datos']['tz']
    T = astro(fecha_objetivo, hora_objetivo, lat, lon, tz)
    out = _transitos_sobre(A, T, A['cusp_deg'])
    hitos = hitos_ciclicos(A['pos'], T['pos'])
    return {'fecha': fecha_objetivo, 'transitos': out, 'hitos': hitos,
            'pos_transito': {k: v['fmt'] for k, v in T['pos'].items()},
            'pos_transito_deg': {k: v['grados'] for k, v in T['pos'].items()},
            'casa_natal': ({k: casa_de(v['grados'], A['cusp_deg']) for k, v in T['pos'].items()}
                           if A['cusp_deg'] else None)}

# ---------- eventos del cielo en un rango (v8.7) ----------
def _rango_jd(desde: str, hasta: str, tz: str):
    j0 = _jd(_utc_desde_local(desde, "00:00", tz))
    j1 = _jd(_utc_desde_local(hasta, "23:59", tz))
    return j0, j1

def _refinar(f, a, b, n=40):
    """Bisección sobre f con cambio de signo entre a y b."""
    fa = f(a)
    for _ in range(n):
        m = (a + b) / 2; fm = f(m)
        if fa * fm <= 0: b = m
        else: a, fa = m, fm
    return (a + b) / 2

def lunaciones(desde: str, hasta: str, tz: str, cusps=None):
    """Lunas nuevas y llenas entre dos fechas locales, con grado, signo y (si se
    pasan cúspides natales) la casa natal donde cae."""
    j0, j1 = _rango_jd(desde, hasta, tz)
    def elong(jd):
        s = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)[0][0]
        m = swe.calc_ut(jd, swe.MOON, swe.FLG_SWIEPH)[0][0]
        return (m - s) % 360
    out = []
    jd = j0 - 1; paso = 1/24
    prev = elong(jd)
    while jd < j1 + 1:
        jd2 = jd + paso; e = elong(jd2)
        for ang, nombre in ((0, 'Luna nueva'), (180, 'Luna llena')):
            d1 = (prev - ang + 180) % 360 - 180
            d2 = (e - ang + 180) % 360 - 180
            if d1 < 0 <= d2 and abs(d1) < 30:
                jx = _refinar(lambda j: (elong(j) - ang + 180) % 360 - 180, jd, jd2)
                utc, local = _jd_a_local(jx, tz)
                if j0 <= jx <= j1:
                    L = swe.calc_ut(jx, swe.MOON, swe.FLG_SWIEPH)[0][0] % 360
                    out.append({'tipo': nombre, 'jd': jx, 'utc': utc, 'local': local,
                                'fecha': local.strftime('%Y-%m-%d'), 'hora': local.strftime('%H:%M'),
                                'grados': L, 'fmt': fmt(L),
                                'casa_natal': casa_de(L, cusps) if cusps else None})
        prev = e; jd = jd2
    return out

def estaciones(desde: str, hasta: str, tz: str, cuerpos=None):
    """Planetas que estacionan (retrógrado ↔ directo) entre dos fechas locales."""
    j0, j1 = _rango_jd(desde, hasta, tz)
    cuerpos = cuerpos or ['Mercurio','Venus','Marte','Júpiter','Saturno','Urano','Neptuno','Plutón','Quirón']
    out = []
    for nom in cuerpos:
        cod = PLANETAS.get(nom, swe.CHIRON if nom == 'Quirón' else None)
        if cod is None or (nom == 'Quirón' and not QUIRON_DISPONIBLE): continue
        def vel(jd, cod=cod): return swe.calc_ut(jd, cod, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][3]
        jd = j0 - 2; paso = 0.25; prev = vel(jd)
        while jd < j1 + 2:
            jd2 = jd + paso; v = vel(jd2)
            if prev * v < 0:
                jx = _refinar(vel, jd, jd2)
                if j0 <= jx <= j1:
                    utc, local = _jd_a_local(jx, tz)
                    L = swe.calc_ut(jx, cod, swe.FLG_SWIEPH)[0][0] % 360
                    out.append({'cuerpo': nom, 'estacion': 'retrógrado' if v < 0 else 'directo',
                                'jd': jx, 'local': local, 'fecha': local.strftime('%Y-%m-%d'),
                                'grados': L, 'fmt': fmt(L)})
            prev = v; jd = jd2
    return sorted(out, key=lambda x: x['jd'])

def pasos_exactos(cuerpo: str, grado_objetivo: float, desde: str, hasta: str, tz: str,
                  aspecto: str = 'Conjunción'):
    """Fechas en que un cuerpo en tránsito forma un aspecto EXACTO con un grado natal.
    Devuelve una entrada por pase (directo o retrógrado)."""
    j0, j1 = _rango_jd(desde, hasta, tz)
    cod = PLANETAS.get(cuerpo, swe.CHIRON if cuerpo == 'Quirón' else None)
    if cod is None: return []
    objetivo = (grado_objetivo + ASPECTOS[aspecto]) % 360
    objetivos = [objetivo] if ASPECTOS[aspecto] in (0, 180) else [objetivo, (grado_objetivo - ASPECTOS[aspecto]) % 360]
    out = []
    for obj in objetivos:
        def d(jd, obj=obj):
            L = swe.calc_ut(jd, cod, swe.FLG_SWIEPH)[0][0]
            return (L - obj + 180) % 360 - 180
        paso = 0.5 if cuerpo in ('Luna','Mercurio','Venus','Sol','Marte') else 2.0
        jd = j0; prev = d(jd)
        while jd < j1:
            jd2 = jd + paso; v = d(jd2)
            if prev * v < 0 and abs(prev) < 90:
                jx = _refinar(d, jd, jd2)
                utc, local = _jd_a_local(jx, tz)
                retro = swe.calc_ut(jx, cod, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][3] < 0
                out.append({'cuerpo': cuerpo, 'aspecto': aspecto, 'fecha': local.strftime('%Y-%m-%d'),
                            'local': local, 'jd': jx, 'retro': retro, 'fmt': fmt(obj)})
            prev = v; jd = jd2
    return sorted(out, key=lambda x: x['jd'])

# ---------- paquetes por lectura (v8.7) ----------
def anio(datos_natal: dict, anio_rs: int, lugar_rs: dict | None = None,
         fecha_consulta: str | None = None):
    """Todo lo que necesita «El año contado»: natal, Revolución Solar levantada en el
    lugar donde la persona está en su cumpleaños (por defecto el de nacimiento, y se
    declara), cruce RS→natal, hitos, calendario del año (lunaciones, estaciones,
    pasos exactos de los lentos sobre puntos natales), Año Personal y año Bazi."""
    nat = calcular({**datos_natal, 'fecha_consulta': fecha_consulta} if fecha_consulta else datos_natal)
    A = nat['astro']; d = nat['datos']
    if A['sin_hora']:
        raise ValueError("La Revolución Solar necesita hora de nacimiento: sin ella no hay "
                         "instante exacto del retorno ni casas del año.")
    avisos = list(nat['avisos'])
    if lugar_rs:
        lat, lon, tz = _resolver_lugar(lugar_rs)
        lugar_txt = lugar_rs.get('lugar', f"{lat:.3f}, {lon:.3f}")
    else:
        lat, lon, tz = d['lat'], d['lon'], d['tz']; lugar_txt = d['lugar']
        avisos.append("La carta del año se levantó para el lugar de nacimiento porque no se "
                      "declaró dónde estaba la persona el día de su cumpleaños. Si estaba en "
                      "otra ciudad, el Ascendente y las casas del año cambian; los aspectos "
                      "entre planetas no.")
    rs = revolucion_solar(A, anio_rs, lat, lon, tz)
    rs['lugar'] = lugar_txt
    ejes_rs = {'Asc RS': rs['asc_deg'], 'MC RS': rs['mc_deg']}
    ejes_nat = {'Asc natal': A['asc_deg'], 'MC natal': A['mc_deg']}
    cruz = aspectos_cruzados(rs['pos'], A['pos'], ejes_rs, ejes_nat)
    # casas natales de los planetas del año (la "casa prestada")
    casas_nat = {k: casa_de(v['grados'], A['cusp_deg']) for k, v in rs['pos'].items()}
    hitos = hitos_ciclicos(A['pos'], rs['pos'])

    desde = rs['local'].strftime('%Y-%m-%d')
    fin_local = (rs['local'] + timedelta(days=365)).strftime('%Y-%m-%d')
    lun = lunaciones(desde, fin_local, tz, A['cusp_deg'])
    est = estaciones(desde, fin_local, tz)
    # pasos exactos de los lentos sobre puntos natales en orbe ≤ 3° al inicio del año
    pasos = []
    puntos = _puntos_sensibles(A)
    for x in cruz:
        if x['a'] in LENTOS + ('Quirón',) and x['b'] in puntos and x['orbe'] <= 3.0:
            for p in pasos_exactos(x['a'], puntos[x['b']], desde, fin_local, tz, x['aspecto']):
                pasos.append({**p, 'natal': x['b']})
    pasos.sort(key=lambda p: p['jd'])

    # v9.0 (E4): el Año Personal del ciclo que abre se toma en el CUMPLEAÑOS, no en la fecha
    # local de la RS (que puede caer el día anterior y daría el ciclo viejo).
    _yn, _mn, _dn = [int(x) for x in d['fecha'].split("-")]
    num = numerologia(d.get('nombre'), d['fecha'], _cumple_en(anio_rs, _mn, _dn).isoformat())
    yb = anio_bazi_actual(desde, tz)
    return {'natal': nat, 'rs': rs, 'cruz': cruz, 'casas_natales_rs': casas_nat,
            'hitos': hitos, 'lunaciones': lun, 'estaciones': est, 'pasos': pasos,
            'num': num, 'anio_bazi': yb,
            'vigencia': {'desde': desde, 'hasta': fin_local},
            'avisos': avisos, 'version': VERSION}

def _cambio_de_ciclo(nombre, fecha: str, anio_: int, mes_: int):
    """v9.0: si el cumpleaños cae dentro del mes, el Año Personal cambia a mitad de mes.
    Devuelve la fecha y los números de antes y de después, o None. El Mes Personal se
    toma el día 15 (como hasta v8.9) y esto se publica para que nadie lea el ciclo viejo."""
    _y, m, dd = [int(x) for x in fecha.split("-")]
    c = _cumple_en(anio_, m, dd)
    if (c.year, c.month) != (anio_, mes_):
        return None
    antes = numerologia(nombre, fecha, (c - timedelta(days=1)).isoformat())
    despues = numerologia(nombre, fecha, c.isoformat())
    return {'fecha': c.isoformat(),
            'anio_personal_antes': antes['anio_personal'], 'mes_personal_antes': antes['mes_personal'],
            'anio_personal_despues': despues['anio_personal'], 'mes_personal_despues': despues['mes_personal']}

def mes(datos_natal: dict, anio_: int, mes_: int, fechas_muestra: int = 5):
    """Todo lo que necesita «Lectura del mes»: tránsitos muestreados a lo largo del
    mes, lunaciones y estaciones del mes, hitos de ciclo, pasos exactos, mes Bazi y
    Mes Personal."""
    nat = calcular(datos_natal)
    A = nat['astro']; d = nat['datos']; tz = d['tz']
    import calendar as _cal
    ultimo = _cal.monthrange(anio_, mes_)[1]
    desde = f"{anio_}-{mes_:02d}-01"; hasta = f"{anio_}-{mes_:02d}-{ultimo:02d}"
    dias = [1] + [int(round(1 + k * (ultimo - 1) / (fechas_muestra - 1))) for k in range(1, fechas_muestra - 1)] + [ultimo]
    muestras = {}
    for dd in dias:
        f = f"{anio_}-{mes_:02d}-{dd:02d}"
        muestras[f] = transitos(datos_natal, f, natal=nat)
    lun = lunaciones(desde, hasta, tz, A['cusp_deg'])
    est = estaciones(desde, hasta, tz)
    # pasos exactos: cualquier cuerpo (menos Luna) que aparezca en alguna muestra
    vistos = set()
    for t in muestras.values():
        for x in t['transitos']:
            if x['transito'] != 'Luna': vistos.add((x['transito'], x['natal'], x['aspecto']))
    puntos = _puntos_sensibles(A)
    pasos = []
    for cuerpo, natal_pt, asp in vistos:
        for p in pasos_exactos(cuerpo, puntos[natal_pt], desde, hasta, tz, asp):
            pasos.append({**p, 'natal': natal_pt})
    pasos.sort(key=lambda p: p['jd'])
    mitad = f"{anio_}-{mes_:02d}-15"
    b_mes = bazi(mitad, "12:00", tz)
    num = numerologia(d.get('nombre'), d['fecha'], mitad)
    return {'natal': nat, 'anio': anio_, 'mes': mes_, 'desde': desde, 'hasta': hasta,
            'muestras': muestras, 'lunaciones': lun, 'estaciones': est, 'pasos': pasos,
            'bazi_mes': {'pilar_anio': b_mes['pilar_anio'], 'pilar_mes': b_mes['pilar_mes']},
            'anio_personal': num['anio_personal'], 'mes_personal': num['mes_personal'],
            'cambio_de_ciclo': _cambio_de_ciclo(d.get('nombre'), d['fecha'], anio_, mes_),
            'avisos': nat['avisos'], 'version': VERSION}

def sinastria(datos_a: dict, datos_b: dict):
    """Aspectos cruzados entre dos cartas (lectura 4)."""
    A = calcular(datos_a)['astro']; B = calcular(datos_b)['astro']
    ejes_a = {'Asc': A['asc_deg'], 'MC': A['mc_deg']} if A['asc_deg'] is not None else None
    ejes_b = {'Asc': B['asc_deg'], 'MC': B['mc_deg']} if B['asc_deg'] is not None else None
    return {'aspectos': aspectos_cruzados(A['pos'], B['pos'], ejes_a, ejes_b),
            'sin_hora_a': A['sin_hora'], 'sin_hora_b': B['sin_hora']}

def sinastria_bazi(datos_a: dict, datos_b: dict):
    """Relaciones entre las ramas de dos cartas: Sanhé, Liuhé, Chong (3.ter.4)."""
    ca, cb = calcular(datos_a), calcular(datos_b)
    def ramas(c):
        b = c['bazi']
        ks = ['pilar_anio', 'pilar_mes', 'pilar_dia'] + (['pilar_hora'] if b['pilar_hora'] else [])
        return [(k.replace('pilar_', ''),
                 next(i for i, r in enumerate(RAMAS) if r[2] == b[k]['animal'])) for k in ks]
    ra, rb = ramas(ca), ramas(cb)
    rel = {'chong': [], 'liuhe': [], 'sanhe': []}
    for ka, ia in ra:
        for kb, ib in rb:
            par = tuple(sorted((ia, ib)))
            if par in [tuple(sorted(p)) for p in CHONG]:
                rel['chong'].append({'a': f"{ka}:{RAMAS[ia][2]}", 'b': f"{kb}:{RAMAS[ib][2]}"})
            if par in [tuple(sorted(p)) for p in LIUHE]:
                rel['liuhe'].append({'a': f"{ka}:{RAMAS[ia][2]}", 'b': f"{kb}:{RAMAS[ib][2]}"})
    # v9.0 (E19): una combinación es DEL VÍNCULO solo si la arman las dos cartas juntas:
    # cada una aporta al menos una rama que la otra no tiene. Un trío entero dentro de una
    # sola carta es de esa persona, no del vínculo. Se informan también las medias
    # combinaciones entre las dos (3.ter.4 pide distinguirlas).
    set_a, set_b = {i for _, i in ra}, {i for _, i in rb}
    for trio, el in SANHE:
        en_a = set(trio) & set_a; en_b = set(trio) & set_b
        juntas = en_a | en_b
        if not en_a or not en_b or not (en_a - en_b) or not (en_b - en_a):
            continue
        if len(juntas) == 3:
            rel['sanhe'].append({'elemento': el, 'completa': True, 'tipo': 'Sanhé (trío) entre las dos cartas',
                                 'ramas': [RAMAS[i][2] for i in trio],
                                 'aporta_a': [RAMAS[i][2] for i in sorted(en_a)],
                                 'aporta_b': [RAMAS[i][2] for i in sorted(en_b)]})
        elif len(juntas) == 2:
            rel['sanhe'].append({'elemento': el, 'completa': False, 'tipo': 'media combinación (Banhe) entre las dos cartas',
                                 'ramas': [RAMAS[i][2] for i in sorted(juntas)],
                                 'aporta_a': [RAMAS[i][2] for i in sorted(en_a)],
                                 'aporta_b': [RAMAS[i][2] for i in sorted(en_b)]})
    return {'dia_maestro_a': ca['bazi']['dia_maestro'],
            'dia_maestro_b': cb['bazi']['dia_maestro'],
            'util_a': ca['bazi']['elemento_util'], 'util_b': cb['bazi']['elemento_util'],
            'relaciones': rel}

# ============================================================
# 9. PAQUETES v8.8 — lunaciones, retorno, próximo año, sinastría completa, progresiones
# ============================================================
VERSION = "8.8"

def _contactos_punto(grado: float, A: dict, orbe_max: float = 3.0):
    """Aspectos de un grado suelto (una lunación, un cuerpo progresado) a los puntos natales."""
    out = []
    for np_, ng in _puntos_sensibles(A).items():
        diff = abs(grado - ng) % 360
        if diff > 180: diff = 360 - diff
        for nom, ang in ASPECTOS.items():
            o = abs(diff - ang)
            if o <= orbe_max:
                out.append({'aspecto': nom, 'natal': np_, 'orbe': round(o, 2)}); break
    return sorted(out, key=lambda x: x['orbe'])

def lunaciones_mes(datos_natal: dict, anio_: int, mes_: int):
    """«Lunaciones»: las lunas nueva y llena del mes sobre la carta, con casa natal y
    contactos a puntos natales; mes Bazi y Mes Personal."""
    import calendar as _cal
    nat = calcular(datos_natal); A = nat['astro']; d = nat['datos']; tz = d['tz']
    ultimo = _cal.monthrange(anio_, mes_)[1]
    desde = f"{anio_}-{mes_:02d}-01"; hasta = f"{anio_}-{mes_:02d}-{ultimo:02d}"
    lun = lunaciones(desde, hasta, tz, A['cusp_deg'])
    for l in lun:
        l['contactos'] = _contactos_punto(l['grados'], A)
        # fase: dónde cae respecto del Sol natal y la Luna natal
        l['sobre_sol_natal'] = round(min(abs((l['grados'] - A['pos']['Sol']['grados'] + 180) % 360 - 180), 180), 2)
        l['sobre_luna_natal'] = round(min(abs((l['grados'] - A['pos']['Luna']['grados'] + 180) % 360 - 180), 180), 2)
    mitad = f"{anio_}-{mes_:02d}-15"
    b = bazi(mitad, "12:00", tz); n = numerologia(d.get('nombre'), d['fecha'], mitad)
    return {'natal': nat, 'anio': anio_, 'mes': mes_, 'desde': desde, 'hasta': hasta,
            'lunaciones': lun, 'bazi_mes': {'pilar_anio': b['pilar_anio'], 'pilar_mes': b['pilar_mes']},
            'anio_personal': n['anio_personal'], 'mes_personal': n['mes_personal'],
            'cambio_de_ciclo': _cambio_de_ciclo(d.get('nombre'), d['fecha'], anio_, mes_),
            'avisos': nat['avisos'], 'version': VERSION}

def retorno(datos_natal: dict, cuerpo: str = 'Saturno', fecha_consulta: str | None = None,
            ventana_anios: float = 3.0):
    """«Retorno de Saturno o de Quirón»: pases exactos del cuerpo sobre su grado natal
    alrededor de la fecha de consulta, orbe actual, edad en cada pase, posición natal del
    cuerpo con sus aspectos, tránsitos al primer pase, Da Yun y Año Personal del retorno."""
    assert cuerpo in ('Saturno', 'Quirón', 'Júpiter', 'Nodo N')
    nat = calcular(datos_natal); A = nat['astro']; d = nat['datos']; tz = d['tz']
    if cuerpo not in A['pos']:
        raise ValueError(f"{cuerpo} no está calculado en esta carta.")
    hoy = datetime.strptime(fecha_consulta, "%Y-%m-%d").date() if fecha_consulta else date.today()
    nac = datetime.strptime(d['fecha'], "%Y-%m-%d").date()
    desde = (hoy - timedelta(days=int(365.25 * ventana_anios))).isoformat()
    hasta = (hoy + timedelta(days=int(365.25 * ventana_anios))).isoformat()
    g_nat = A['pos'][cuerpo]['grados']
    pases = pasos_exactos(cuerpo, g_nat, desde, hasta, tz, 'Conjunción')
    for p in pases:
        f = p['local'].date(); p['edad'] = round((f - nac).days / 365.25, 1)
    T = transitos(datos_natal, hoy.isoformat(), natal=nat)
    sep = (T['pos_transito_deg'][cuerpo] - g_nat + 180) % 360 - 180
    n_ret = round(((hoy - nac).days / 365.25) / CICLOS[cuerpo]) if cuerpo in CICLOS else None
    asp_nat = [x for x in A['aspectos'] if cuerpo in (x['a'], x['b']) and x['orbe'] <= 6]
    primer = pases[0] if pases else None
    T1 = transitos(datos_natal, primer['fecha'], natal=nat) if primer else None
    anio_ret = primer['local'].year if primer else hoy.year
    n = numerologia(d.get('nombre'), d['fecha'], _cumple_en(anio_ret, nac.month, nac.day).isoformat())  # v9.0: 29/2
    dy = nat['da_yun']; ciclo_activo = None
    if dy.get('disponible'):
        edad = (hoy - nac).days / 365.25
        for c in dy['ciclos']:
            if c['desde'] <= edad < c['hasta']: ciclo_activo = c
    return {'natal': nat, 'cuerpo': cuerpo, 'fecha_consulta': hoy.isoformat(),
            'pos_natal': A['pos'][cuerpo], 'aspectos_natales': asp_nat,
            'pases': pases, 'orbe_actual': round(sep, 2), 'retro_ahora': T['pos_transito_deg'] and any(
                x['transito'] == cuerpo and x['retro'] for x in T['transitos']) or False,
            'numero_retorno': n_ret, 'edad_actual': round((hoy - nac).days / 365.25, 1),
            'transitos_primer_pase': T1, 'anio_personal_retorno': n['anio_personal'],
            'anio_bazi_retorno': anio_bazi_actual(f"{anio_ret}-06-01", tz), 'da_yun_activo': ciclo_activo,
            'ventana': {'desde': desde, 'hasta': hasta}, 'avisos': nat['avisos'], 'version': VERSION}

def proximo_anio(datos_natal: dict, desde: str | None = None):
    """«Tu próximo año»: doce meses desde `desde` (por defecto el mes que viene), con los
    tránsitos lentos de cada mes (al 15), lunaciones, estaciones, pasos exactos, hitos,
    Mes Personal y pilar de mes Bazi."""
    import calendar as _cal
    nat = calcular(datos_natal); A = nat['astro']; d = nat['datos']; tz = d['tz']
    if desde is None:
        hoy = date.today(); y, m = (hoy.year + (hoy.month // 12), hoy.month % 12 + 1)
        desde = f"{y}-{m:02d}-01"
    y0, m0 = int(desde[:4]), int(desde[5:7])
    meses = []
    for k in range(12):
        y, m = y0 + (m0 - 1 + k) // 12, (m0 - 1 + k) % 12 + 1
        ult = _cal.monthrange(y, m)[1]
        mitad = f"{y}-{m:02d}-15"
        T = transitos(datos_natal, mitad, natal=nat)
        lentos = [x for x in T['transitos'] if x['lento'] or x['transito'] == 'Quirón']
        n = numerologia(d.get('nombre'), d['fecha'], mitad); b = bazi(mitad, "12:00", tz)
        meses.append({'anio': y, 'mes': m, 'desde': f"{y}-{m:02d}-01", 'hasta': f"{y}-{m:02d}-{ult:02d}",
                      'lentos': lentos, 'hitos': T['hitos'], 'casa_natal': T['casa_natal'],
                      'mes_personal': n['mes_personal'], 'anio_personal': n['anio_personal'],
                      'cambio_de_ciclo': _cambio_de_ciclo(d.get('nombre'), d['fecha'], y, m),
                      'pilar_mes': b['pilar_mes']})
    fin = meses[-1]['hasta']
    lun = lunaciones(desde, fin, tz, A['cusp_deg']); est = estaciones(desde, fin, tz)
    vistos = set()
    for mm in meses:
        for x in mm['lentos']: vistos.add((x['transito'], x['natal'], x['aspecto']))
    puntos = _puntos_sensibles(A); pasos = []
    for cuerpo, pt, asp in vistos:
        for p in pasos_exactos(cuerpo, puntos[pt], desde, fin, tz, asp):
            pasos.append({**p, 'natal': pt})
    pasos.sort(key=lambda p: p['jd'])
    return {'natal': nat, 'desde': desde, 'hasta': fin, 'meses': meses, 'lunaciones': lun,
            'estaciones': est, 'pasos': pasos, 'anio_bazi': anio_bazi_actual(desde, tz),
            'avisos': nat['avisos'], 'version': VERSION}

def sinastria_completa(datos_a: dict, datos_b: dict):
    """«Sinastría»: dos cartas completas, aspectos cruzados (A→B con ejes), casas de cada
    uno en la carta del otro, relaciones Bazi entre ramas, núcleos numerológicos."""
    ca, cb = calcular(datos_a), calcular(datos_b); A, B = ca['astro'], cb['astro']
    ejes_a = {'Asc A': A['asc_deg'], 'MC A': A['mc_deg']} if A['asc_deg'] is not None else None
    ejes_b = {'Asc B': B['asc_deg'], 'MC B': B['mc_deg']} if B['asc_deg'] is not None else None
    cruz = aspectos_cruzados(A['pos'], B['pos'], ejes_a, ejes_b)
    en_casas_de_b = {k: casa_de(v['grados'], B['cusp_deg']) for k, v in A['pos'].items()} if B['cusp_deg'] else None
    en_casas_de_a = {k: casa_de(v['grados'], A['cusp_deg']) for k, v in B['pos'].items()} if A['cusp_deg'] else None
    sb = sinastria_bazi(datos_a, datos_b)
    def nucleo(c):
        n = c['num']; return {k: n[k] for k in ('camino', 'alma', 'expresion', 'personalidad')}
    # relación entre los elementos de los Días Maestros
    ea, eb = ca['bazi']['dia_maestro']['elemento'], cb['bazi']['dia_maestro']['elemento']
    if ea == eb: rel_dm = 'mismo elemento'
    elif NUTRE[eb] == ea: rel_dm = f'{ea} nutre a {eb}'
    elif NUTRE[ea] == eb: rel_dm = f'{eb} nutre a {ea}'
    # v9.1.1 (24/11/2026): CONTROLA[x] es lo que controla a x (Agua: Tierra); antes las etiquetas salían al revés
    elif CONTROLA[ea] == eb: rel_dm = f'{eb} controla a {ea}'
    elif CONTROLA[eb] == ea: rel_dm = f'{ea} controla a {eb}'
    else: rel_dm = 'sin relación directa'
    return {'a': ca, 'b': cb, 'cruz': cruz, 'a_en_casas_de_b': en_casas_de_b, 'b_en_casas_de_a': en_casas_de_a,
            'bazi': {**sb, 'relacion_dias_maestros': rel_dm},
            'num': {'a': nucleo(ca), 'b': nucleo(cb)},
            'avisos': [f"A: {x}" for x in ca['avisos']] + [f"B: {x}" for x in cb['avisos']], 'version': VERSION}

def progresiones(datos_natal: dict, fecha_objetivo: str | None = None):
    """«Progresiones»: progresión secundaria (un día por año) a la fecha objetivo, con el
    Sol y la Luna progresados, su casa natal, los contactos progresado→natal (orbe ≤ 1°),
    la fase lunar progresada, y los cambios de signo de la Luna progresada en los 12 meses
    que siguen."""
    nat = calcular(datos_natal); A = nat['astro']; d = nat['datos']; tz = d['tz']
    if A['sin_hora']:
        raise ValueError("Las progresiones necesitan hora de nacimiento.")
    hoy = datetime.strptime(fecha_objetivo, "%Y-%m-%d").date() if fecha_objetivo else date.today()
    nac = A['utc']
    edad_dias = (pytz.timezone(tz).localize(datetime(hoy.year, hoy.month, hoy.day, 12)).astimezone(pytz.UTC) - nac).total_seconds() / 86400
    edad = edad_dias / 365.2422
    jd_p = A['jd'] + edad                    # 1 día = 1 año
    P = astro_jd(jd_p, d['lat'], d['lon'], False)
    # v9.0 (E1, decisión D8): los ÁNGULOS no se levantan en el instante progresado (eso los
    # hacía girar casi una vuelta por año, porque la fracción del día es rotación de la
    # Tierra). Medio Cielo progresado = MC natal + arco solar (Sol progresado − Sol natal);
    # Ascendente y casas, desde ese MC para la latitud de nacimiento, mismo sistema que la natal.
    arco = (P['pos']['Sol']['grados'] - A['pos']['Sol']['grados']) % 360
    mc_p = (A['mc_deg'] + arco) % 360
    eps = swe.calc_ut(jd_p, swe.ECL_NUT)[0][0]
    armc = math.degrees(math.atan2(math.sin(math.radians(mc_p)) * math.cos(math.radians(eps)),
                                   math.cos(math.radians(mc_p)))) % 360
    hsys = b'W' if (P['sistema_casas'] or '').startswith('Whole') else b'T'
    cusps_p, ang_p = swe.houses_armc(armc, d['lat'], eps, hsys)
    cusps_p = [c % 360 for c in cusps_p]
    P['cusp_deg'] = cusps_p; P['asc_deg'] = ang_p[0] % 360; P['mc_deg'] = mc_p
    P['asc'] = fmt(P['asc_deg']); P['mc'] = fmt(mc_p)
    P['arco_solar'] = round(arco, 4)
    P['metodo_angulos'] = ("Medio Cielo progresado por arco solar en longitud; Ascendente y casas "
                           "derivados de ese Medio Cielo para la latitud de nacimiento.")
    for k, v in P['pos'].items():
        v['casa'] = casa_de(v['grados'], cusps_p)
        v['casa_natal'] = casa_de(v['grados'], A['cusp_deg'])
    P['diurna'] = P['pos']['Sol']['casa'] in (7, 8, 9, 10, 11, 12)
    _pf = ((P['asc_deg'] + P['pos']['Luna']['grados'] - P['pos']['Sol']['grados']) if P['diurna']
           else (P['asc_deg'] + P['pos']['Sol']['grados'] - P['pos']['Luna']['grados'])) % 360
    P['fortuna'] = {'grados': _pf, 'fmt': fmt(_pf), 'casa': casa_de(_pf, cusps_p)}
    cont = []
    for k in ('Sol', 'Luna', 'Mercurio', 'Venus', 'Marte'):
        for c in _contactos_punto(P['pos'][k]['grados'], A, 1.0):
            cont.append({'progresado': k, **c})
    cont.sort(key=lambda x: x['orbe'])
    fase = (P['pos']['Luna']['grados'] - P['pos']['Sol']['grados']) % 360
    nombres = ['nueva', 'creciente', 'cuarto creciente', 'gibosa', 'llena', 'diseminante', 'cuarto menguante', 'balsámica']
    fase_nombre = nombres[int(fase // 45)]
    # ingresos de la Luna progresada en los próximos 12 meses: 1 año = 1 día → paso de 1/365 día
    ingresos = []
    prev = int(P['pos']['Luna']['grados'] // 30)
    for k in range(1, 366):
        L = swe.calc_ut(jd_p + k / 365.2422, swe.MOON, swe.FLG_SWIEPH)[0][0] % 360
        s = int(L // 30)
        if s != prev:
            f = hoy + timedelta(days=k)
            ingresos.append({'fecha': f.isoformat(), 'signo': SIGNOS[s], 'casa_natal': casa_de(L, A['cusp_deg'])})
            prev = s
    # contactos exactos de Sol y Luna progresados dentro de los 12 meses (orbe que cruza 0)
    exactos = []
    puntos = _puntos_sensibles(A)
    for k_cuerpo, cod in (('Sol', swe.SUN), ('Luna', swe.MOON)):
        for np_, ng in puntos.items():
            for nom, ang in ASPECTOS.items():
                objs = [(ng + ang) % 360] + ([(ng - ang) % 360] if ang not in (0, 180) else [])
                for obj in objs:
                    def dd(j, obj=obj, cod=cod): return (swe.calc_ut(j, cod, swe.FLG_SWIEPH)[0][0] - obj + 180) % 360 - 180
                    a0 = dd(jd_p); a1 = dd(jd_p + 1.0)
                    if a0 * a1 < 0 and abs(a0) < 15:
                        jx = _refinar(dd, jd_p, jd_p + 1.0)
                        f = hoy + timedelta(days=int(round((jx - jd_p) * 365.2422)))
                        exactos.append({'progresado': k_cuerpo, 'aspecto': nom, 'natal': np_, 'fecha': f.isoformat()})
    exactos.sort(key=lambda x: x['fecha'])
    return {'natal': nat, 'fecha': hoy.isoformat(), 'edad': round(edad, 2), 'jd_progresado': jd_p,
            'progresada': P, 'contactos': cont, 'fase': {'grados': round(fase, 1), 'nombre': fase_nombre},
            'ingresos_luna': ingresos, 'exactos_12m': exactos,
            'anio_personal': numerologia(d.get('nombre'), d['fecha'], hoy.isoformat())['anio_personal'],
            'avisos': nat['avisos'] + ["Progresión secundaria: un día de efemérides por cada año de vida. "
                                       "Medio Cielo progresado por arco solar; Ascendente y casas "
                                       "progresadas derivados de él para el lugar de nacimiento."],
            'version': VERSION}

# ============================================================
# 10. RECORTES DE LA INTEGRAL (v8.8) — año personal, décadas
# ============================================================
def anio_personal(datos_natal: dict, fecha_consulta: str | None = None):
    """«Tu año personal»: el ciclo numerológico en curso, de cumpleaños a cumpleaños, con el
    Mes Personal de cada uno de sus doce meses, el Pináculo y el Desafío vigentes."""
    nat = calcular(datos_natal); d = nat['datos']; n = nat['num']
    hoy = datetime.strptime(fecha_consulta, "%Y-%m-%d").date() if fecha_consulta else date.today()
    y, m, dd = [int(x) for x in d['fecha'].split("-")]
    # v9.0 (E2): el ciclo arranca el cumpleaños real (antes min(dd, 28) corría a los
    # nacidos el 29, 30 y 31 al ciclo anterior).
    inicio = _cumple_en(hoy.year, m, dd)
    if hoy < inicio:
        inicio = _cumple_en(hoy.year - 1, m, dd)
    ap = numerologia(d.get('nombre'), d['fecha'], inicio.isoformat())['anio_personal']
    meses = []
    for k in range(12):
        yy, mm = inicio.year + (inicio.month - 1 + k) // 12, (inicio.month - 1 + k) % 12 + 1
        mp, _ = reducir(ap + mm)
        meses.append({'anio': yy, 'mes': mm, 'mes_personal': mp, 'actual': (yy, mm) == (hoy.year, hoy.month)})
    fin = _cumple_en(inicio.year + 1, m, dd) - timedelta(days=1)
    edad = (hoy - date(y, m, dd)).days / 365.25
    edad_c = _edad_cumplida(date(y, m, dd), hoy)          # v9.0 (E3): por cumpleaños
    pin = next((p for p in n['pinaculos'] if p['desde'] <= edad_c and (p['hasta'] is None or edad_c < p['hasta'])), None)
    i_pin = n['pinaculos'].index(pin) if pin else None
    desafio = n['desafios'][i_pin] if i_pin is not None else None
    siguiente, _ = reducir(ap + 1) if ap < 9 else (1, None)
    return {'natal': nat, 'anio_personal': ap, 'siguiente': siguiente, 'inicio': inicio.isoformat(), 'fin': fin.isoformat(),
            'meses': meses, 'pinaculo': pin, 'desafio': desafio, 'edad': round(edad, 1),
            'camino': n['camino'], 'avisos': nat['avisos'], 'version': VERSION}

def decadas(datos_natal: dict, fecha_consulta: str | None = None):
    """«Tus décadas»: los pilares de suerte (Da Yun) con la década activa, la anterior y las
    dos siguientes marcadas, y la relación de cada una con el Día Maestro."""
    nat = calcular(datos_natal); d = nat['datos']; b = nat['bazi']; dy = nat['da_yun']
    hoy = datetime.strptime(fecha_consulta, "%Y-%m-%d").date() if fecha_consulta else date.today()
    y, m, dd = [int(x) for x in d['fecha'].split("-")]
    edad = (hoy - date(y, m, dd)).days / 365.25
    el_dm = b['dia_maestro']['elemento']
    def rel(e):
        if e == el_dm: return 'mismo elemento: te refuerza'
        if NUTRE[el_dm] == e: return 'te nutre'
        if DRENA[el_dm] == e: return 'te drena'
        if CONTROLA[el_dm] == e: return 'te controla'
        return 'lo controlás'
    ciclos = []
    if dy.get('disponible'):
        for c in dy['ciclos']:
            ciclos.append({**c, 'activa': c['desde'] <= edad < c['hasta'],
                           'rel_tronco': rel(c['elemento_tronco']), 'rel_rama': rel(c['elemento_rama']),
                           'util': c['elemento_tronco'] == b['elemento_util'] or c['elemento_rama'] == b['elemento_util'],
                           # v9.0 (E18): fecha real de inicio (antes y + int(desde) podía dar un año antes)
                           'fecha_desde': (date(y, m, dd) + timedelta(days=c['desde'] * 365.2422)).isoformat(),
                           'anio_desde': (date(y, m, dd) + timedelta(days=c['desde'] * 365.2422)).year,
                           'anio_hasta': (date(y, m, dd) + timedelta(days=c['hasta'] * 365.2422)).year})
    i_act = next((i for i, c in enumerate(ciclos) if c['activa']), None)
    return {'natal': nat, 'edad': round(edad, 1), 'disponible': dy.get('disponible', False), 'motivo': dy.get('motivo'),
            'ciclos': ciclos, 'indice_activa': i_act, 'anio_bazi': anio_bazi_actual(hoy.isoformat(), d['tz']),
            'avisos': nat['avisos'], 'version': VERSION}

# ============================================================
# 11. v8.9 — hora solar local para día y hora Bazi (decisión 28/10/2026)
# ============================================================
VERSION = "8.9"

# ============================================================
# 12. v9.0 — auditoría del 22/11/2026
# ============================================================
# E20: la ruta de las efemérides se fija en cada entrada, no solo al importar. Swiss
# Ephemeris guarda la ruta por hilo: llamado desde otro hilo (un servidor), sin esto caía
# a Moshier en silencio en revolución solar, lunaciones y pasos exactos.
import functools as _ft

def _con_ruta(f):
    @_ft.wraps(f)
    def g(*a, **k):
        swe.set_ephe_path(EPHE_DIR)
        return f(*a, **k)
    return g

for _n in ('astro_jd', 'revolucion_solar', 'lunaciones', 'estaciones', 'pasos_exactos',
           '_jieqi_utc', 'hora_solar_local', 'progresiones', 'calcular'):
    globals()[_n] = _con_ruta(globals()[_n])

VERSION = "9.0"


# ============================================================
# 13. v9.1 — EL CIELO DE TODOS (22/11/2026)
# ============================================================
# Pedido de Fabricio: «Que todos los flujos y todas las lecturas dependen del motor (…) que todo
# se basa en el 9.0». Hasta acá el cielo colectivo lo calculaban por su cuenta el calendario
# (IA\CIELO_calculo_v1.py, pestaña Cielo), los aspectos (IA\CIELO_aspectos_v1.py, pestaña
# Aspectos), el cielo de la web y los tips (servicio\cielo_hoy.py) y los scripts de los reels.
# Desde la v9.1 viven acá, con los mismos algoritmos (pasos y bisección) para que el resultado no
# cambie, y todos los llaman. Reglas de la adenda 8.6.4: grados truncados al minuto; horas
# redondeadas al minuto (decisión de Fabricio, 22/11: «Redondear»).
TZ_AR = "America/Argentina/Buenos_Aires"
CUERPOS_CIELO = [('Sol', swe.SUN), ('Mercurio', swe.MERCURY), ('Venus', swe.VENUS), ('Marte', swe.MARS),
                 ('Júpiter', swe.JUPITER), ('Saturno', swe.SATURN), ('Urano', swe.URANUS),
                 ('Neptuno', swe.NEPTUNE), ('Plutón', swe.PLUTO), ('Quirón', swe.CHIRON)]
_COD_CIELO = dict(CUERPOS_CIELO + [('Luna', swe.MOON)])
LENTOS_CIELO = {'Júpiter', 'Saturno', 'Urano', 'Neptuno', 'Plutón', 'Quirón'}
ASPECTOS_CIELO = [('Conjunción', 0.0), ('Sextil', 60.0), ('Cuadratura', 90.0), ('Trígono', 120.0), ('Oposición', 180.0)]
AU_KM = 149597870.7
_BACKENDS_CIELO = set()

def cielo_pos(jd: float, cuerpo) -> tuple:
    """(longitud, latitud, distancia en UA, velocidad en longitud) geocéntricas aparentes."""
    cod = _COD_CIELO[cuerpo] if isinstance(cuerpo, str) else cuerpo
    xx, ret = swe.calc_ut(jd, cod, swe.FLG_SWIEPH | swe.FLG_SPEED)
    _BACKENDS_CIELO.add(_backend(ret))
    return xx[0] % 360, xx[1], xx[2], xx[3]

def efemerides_cielo() -> str:
    return " + ".join(sorted(_BACKENDS_CIELO)) or "sin calcular"

def _n180(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0

def _bis_signo(f, a: float, b: float, n: int = 100) -> float:
    """Bisección por signo (la del calendario del cielo)."""
    fa = f(a)
    for _ in range(n):
        m_ = (a + b) / 2
        fm = f(m_)
        if (fm > 0) == (fa > 0):
            a, fa = m_, fm
        else:
            b = m_
    return (a + b) / 2

def _bis_producto(f, a: float, b: float, n: int = 50) -> float:
    """Bisección por producto (la de los aspectos y del cielo de la web)."""
    fa = f(a)
    for _ in range(n):
        m_ = (a + b) / 2
        fm = f(m_)
        if fa * fm <= 0:
            b = m_
        else:
            a, fa = m_, fm
    return (a + b) / 2

def fmt_de(g: float) -> str:
    """«g°mm' de Signo», con el grado TRUNCADO al minuto (E11)."""
    t = fmt(g)                                   # «g°mm' Signo»
    gm, signo = t.split(" ", 1)
    return f"{gm} de {signo}"

def signo_de(g: float) -> str:
    return SIGNOS[int((g % 360) // 30)]

def hora_exacta(jd: float, tz: str = TZ_AR) -> datetime:
    """Instante local con segundos (sin redondear), naive."""
    y, mo, d, h = swe.revjul(jd)
    u = pytz.UTC.localize(datetime(y, mo, d) + timedelta(seconds=h * 3600.0))
    return u.astimezone(pytz.timezone(tz)).replace(tzinfo=None)

def hora_minuto(jd: float, tz: str = TZ_AR) -> datetime:
    """Instante local redondeado al minuto (regla de la casa), naive."""
    t = hora_exacta(jd, tz) + timedelta(seconds=30)
    return t.replace(second=0, microsecond=0)

def jd_desde_local(fecha_hora: datetime, tz: str = TZ_AR) -> float:
    u = pytz.timezone(tz).localize(fecha_hora).astimezone(pytz.UTC)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3.6e9)

def fase_luna(jd: float) -> dict:
    """Fase y porcentaje iluminado (lo que usaba calculo_pregunta._fase_luna)."""
    elong = (cielo_pos(jd, 'Luna')[0] - cielo_pos(jd, 'Sol')[0]) % 360
    ilum = round((1 - math.cos(math.radians(elong))) / 2 * 100)
    if elong < 10 or elong > 350: nombre = "luna nueva"
    elif elong < 80: nombre = "creciente"
    elif elong < 100: nombre = "cuarto creciente"
    elif elong < 170: nombre = "gibosa creciente"
    elif elong < 190: nombre = "luna llena"
    elif elong < 260: nombre = "gibosa menguante"
    elif elong < 280: nombre = "cuarto menguante"
    else: nombre = "menguante"
    return {"fase": nombre, "iluminada_pct": ilum}

def lunaciones_jd(jd0: float, jd1: float) -> list:
    """[(jd, 'nueva'|'llena')] entre jd0 y jd1 (algoritmo del calendario: paso 0,5 d, bisección 100)."""
    out = []
    for objetivo, nombre in ((0.0, 'nueva'), (180.0, 'llena')):
        f = lambda t, o=objetivo: _n180(cielo_pos(t, 'Luna')[0] - cielo_pos(t, 'Sol')[0] - o)
        t = jd0 - 1
        prev = f(t)
        while t < jd1:
            t2 = t + 0.5
            cur = f(t2)
            if prev < 0 <= cur and abs(cur - prev) < 90:
                r = _bis_signo(f, t, t2)
                if jd0 <= r < jd1:
                    out.append((r, nombre))
            t, prev = t2, cur
    return sorted(out)

def proxima_fase(jd: float, objetivo: float, dias: float = 32) -> float | None:
    """La próxima vez que la Luna está a `objetivo` grados del Sol (0 nueva, 180 llena)."""
    f = lambda t: _n180(cielo_pos(t, 'Luna')[0] - cielo_pos(t, 'Sol')[0] - objetivo)
    t, ft = jd, f(jd)
    for _ in range(int(dias / 0.25)):
        t2 = t + 0.25
        f2 = f(t2)
        if ft * f2 < 0 and abs(ft) < 30 and abs(f2) < 30:
            return _bis_producto(f, t, t2)
        t, ft = t2, f2
    return None

def ingresos_y_estaciones(jd0: float, jd1: float, cuerpos=None, paso: float = 0.25):
    """Cambios de signo [(jd, cuerpo, signo, directo)] y estaciones [(jd, cuerpo, 'retrógrado'|'directo', lon)]
    (algoritmo del calendario)."""
    cuerpos = cuerpos or [c for c, _ in CUERPOS_CIELO]
    ing, est = [], []
    for nombre in cuerpos:
        t = jd0 - 2
        p = cielo_pos(t, nombre)
        while t < jd1:
            t2 = t + paso
            c = cielo_pos(t2, nombre)
            s1, s2 = int(p[0] // 30) % 12, int(c[0] // 30) % 12
            if s1 != s2:
                directo = _n180(c[0] - p[0]) > 0
                b = (s2 * 30.0) if directo else (s1 * 30.0)
                g = ((lambda x, b=b, n=nombre: _n180(cielo_pos(x, n)[0] - b)) if directo
                     else (lambda x, b=b, n=nombre: -_n180(cielo_pos(x, n)[0] - b)))
                r = _bis_signo(g, t, t2)
                if jd0 <= r < jd1:
                    ing.append((r, nombre, SIGNOS[s2], directo))
            if nombre != 'Sol' and (p[3] > 0) != (c[3] > 0):
                r = _bis_signo(lambda x, n=nombre: cielo_pos(x, n)[3], t, t2)
                if jd0 <= r < jd1:
                    est.append((r, nombre, 'retrógrado' if p[3] > 0 else 'directo', cielo_pos(r, nombre)[0]))
            t, p = t2, c
    return sorted(ing), sorted(est)

def ingresos_proximos(jd: float, dias: float = 7, cuerpos=None) -> list:
    """Cambios de signo de los próximos `dias` (lo que usaba el cielo de la web)."""
    ing, _ = ingresos_y_estaciones(jd, jd + dias, cuerpos or [c for c, _ in CUERPOS_CIELO if c != 'Quirón'])
    return [{'planeta': n, 'entra_en': s, 'jd': r, 'retrogrado': cielo_pos(r, n)[3] < 0} for r, n, s, d in ing]

def peso_aspecto(a: str, b: str, asp: str) -> str:
    """Peso de un aspecto entre planetas (criterio del taller, no astronómico)."""
    asp = asp.capitalize()
    la, lb = a in LENTOS_CIELO, b in LENTOS_CIELO
    duro = asp in ('Conjunción', 'Cuadratura', 'Oposición')
    if la and lb:
        return 'Alta' if duro else 'Media'
    if (la or lb) and asp in ('Conjunción', 'Oposición'):
        return 'Media'
    if not la and not lb and asp == 'Conjunción':
        return 'Media'
    return 'Baja'

def aspectos_exactos(jd0: float, jd1: float, cuerpos=None, paso: float = 0.1) -> list:
    """Aspectos exactos entre planetas en un período (algoritmo de la pestaña Aspectos)."""
    cuerpos = cuerpos or [c for c, _ in CUERPOS_CIELO]
    filas = []
    for i, na in enumerate(cuerpos):
        for nb in cuerpos[i + 1:]:
            for asp, ang in ASPECTOS_CIELO:
                for obj in ([ang] if ang in (0.0, 180.0) else [ang, 360.0 - ang]):
                    f = lambda jd, na=na, nb=nb, obj=obj: _n180(cielo_pos(jd, na)[0] - cielo_pos(jd, nb)[0] - obj)
                    t, fa = jd0, f(jd0)
                    while t < jd1:
                        t2 = t + paso
                        fb = f(t2)
                        if fa == 0 or (fa * fb < 0 and abs(fa) < 20 and abs(fb) < 20):
                            jd = _bis_producto(f, t, t2)
                            pa, pb = cielo_pos(jd, na), cielo_pos(jd, nb)
                            filas.append(dict(jd=jd, a=na, b=nb, asp=asp, lona=pa[0], lonb=pb[0],
                                              ra=pa[3] < 0, rb=pb[3] < 0, peso=peso_aspecto(na, nb, asp)))
                        t, fa = t2, fb
    return sorted(filas, key=lambda r: r['jd'])

def _exacto_cerca(f, jd0: float, dias: float = 40, paso: float = 0.25) -> float | None:
    mejor = None
    for sentido in (1, -1):
        t, ft = jd0, f(jd0)
        recorrido = 0.0
        while recorrido < dias:
            t2 = t + sentido * paso
            f2 = f(t2)
            if ft == 0 or (ft * f2 < 0 and abs(ft) < 20 and abs(f2) < 20):
                r = _bis_producto(f, min(t, t2), max(t, t2))
                if mejor is None or abs(r - jd0) < abs(mejor - jd0):
                    mejor = r
                break
            t, ft, recorrido = t2, f2, recorrido + paso
    return mejor

def aspectos_activos(jd: float, orbe_max: float = 3.0, cuerpos=None) -> list:
    """Aspectos entre planetas en orbe en un instante, con su momento exacto más cercano
    (lo que usaba el cielo de la web). Sin Quirón, como la web."""
    cuerpos = cuerpos or [c for c, _ in CUERPOS_CIELO if c != 'Quirón']
    out = []
    for i, na in enumerate(cuerpos):
        for nb in cuerpos[i + 1:]:
            pa, pb = cielo_pos(jd, na), cielo_pos(jd, nb)
            sep = abs(_n180(pa[0] - pb[0]))
            for asp, ang in ASPECTOS_CIELO:
                orbe = abs(sep - ang)
                if orbe > orbe_max:
                    continue
                objetivos = [ang] if ang in (0.0, 180.0) else [ang, -ang]
                obj = min(objetivos, key=lambda o: abs(_n180(pa[0] - pb[0] - o)))
                f = lambda t, na=na, nb=nb, o=obj: _n180(cielo_pos(t, na)[0] - cielo_pos(t, nb)[0] - o)
                lentos = na in LENTOS_CIELO and nb in LENTOS_CIELO
                jx = _exacto_cerca(f, jd, dias=420, paso=1.0) if lentos else _exacto_cerca(f, jd)
                out.append({'a': na, 'b': nb, 'aspecto': asp, 'angulo': int(ang), 'orbe': round(orbe, 2),
                            'lon_a': pa[0], 'lon_b': pb[0], 'retro_a': pa[3] < 0, 'retro_b': pb[3] < 0,
                            'jd_exacto': jx, 'peso': peso_aspecto(na, nb, asp)})
                break
    orden = {'Alta': 0, 'Media': 1, 'Baja': 2}
    return sorted(out, key=lambda x: (orden[x['peso']], x['orbe']))

def terminos_solares(jd0: float, jd1: float, solo_jie: bool = True) -> list:
    """Términos solares (jieqi) al segundo, con Swiss Ephemeris (E5): [(jd, longitud_del_sol, índice)]."""
    y0 = hora_exacta(jd0, 'UTC').year; y1 = hora_exacta(jd1, 'UTC').year
    out = []
    for t, idx in _jieqi_utc(list(range(y0 - 1, y1 + 2))):
        jd = swe.julday(t.year, t.month, t.day, t.hour + t.minute / 60 + t.second / 3600 + t.microsecond / 3.6e9)
        lon = (270.0 + 15.0 * idx) % 360.0
        if jd0 <= jd < jd1 and (not solo_jie or idx % 2 == 1):
            out.append((jd, lon, idx))
    return sorted(set(out))

def apsides_tierra(jd0: float, jd1: float) -> list:
    """Perihelio y afelio: [(jd, 'perihelio'|'afelio', distancia_km)] (paso 1 d, bisección)."""
    out = []
    t = jd0
    prev = cielo_pos(t, 'Sol')
    while t < jd1:
        t2 = t + 1
        cur = cielo_pos(t2, 'Sol')
        vd0 = swe.calc_ut(t, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][5]
        vd1 = swe.calc_ut(t2, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][5]
        if (vd0 < 0) != (vd1 < 0):
            r = _bis_signo(lambda x: swe.calc_ut(x, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED)[0][5], t, t2)
            out.append((r, 'perihelio' if vd0 < 0 else 'afelio', cielo_pos(r, 'Sol')[2] * AU_KM))
        t, prev = t2, cur
    return out

def eclipse_sol_global(jd0: float):
    """Próximo eclipse de Sol: (tipo_flag, tiempos) de swe.sol_eclipse_when_glob."""
    return swe.sol_eclipse_when_glob(jd0, swe.FLG_SWIEPH, 0, False)

def eclipse_sol_local(jd0: float, lon: float, lat: float, alt: float = 0.0):
    """Próximo eclipse de Sol visible en un lugar: (flag, tiempos, atributos)."""
    return swe.sol_eclipse_when_loc(jd0, (lon, lat, alt), swe.FLG_SWIEPH, False)

def eclipse_luna_siguiente(jd0: float):
    return swe.lun_eclipse_when(jd0, swe.FLG_SWIEPH, 0, False)

def eclipse_luna_como(jd: float, lon: float, lat: float, alt: float = 0.0):
    return swe.lun_eclipse_how(jd, (lon, lat, alt), swe.FLG_SWIEPH)

def salida(jd0: float, cuerpo, lon: float, lat: float, alt: float = 0.0, temp: float = 15.0):
    """Próxima salida de un cuerpo en un lugar (jd)."""
    cod = _COD_CIELO[cuerpo] if isinstance(cuerpo, str) else cuerpo
    return swe.rise_trans(jd0, cod, swe.CALC_RISE, (lon, lat, alt), 1013.25, temp, swe.FLG_SWIEPH)[1][0]

# E20: la ruta de las efemérides se fija en las funciones de entrada (no en cielo_pos, que se llama
# miles de veces dentro de los bucles).
for _n in ('fase_luna', 'lunaciones_jd', 'proxima_fase', 'ingresos_y_estaciones', 'ingresos_proximos',
           'aspectos_exactos', 'aspectos_activos', 'terminos_solares', 'apsides_tierra', 'eclipse_sol_global',
           'eclipse_sol_local', 'eclipse_luna_siguiente', 'eclipse_luna_como', 'salida'):
    globals()[_n] = _con_ruta(globals()[_n])

VERSION = "9.1.1"   # 24/11/2026: relación «controla» entre Días Maestros (sinastría) con las etiquetas bien
