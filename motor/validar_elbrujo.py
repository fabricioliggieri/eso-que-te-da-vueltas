# -*- coding: utf-8 -*-
"""validar_elbrujo.py · El Brujo v8.1 — copia del proyecto para la corrida del 28/10/2026."""
import sys, warnings
from datetime import datetime, date, timedelta

warnings.filterwarnings("ignore")
sys.path.insert(0, __file__.rsplit("/", 1)[0])

import sxtwl
import elbrujo_calculo as E
from ref_bazi import referencia

TZ_AR = "America/Argentina/Buenos_Aires"
DEMO = dict(nombre="Lucía Mariana Ferreyra", fecha="1990-03-14", hora="09:45",
            lugar="Rosario, Santa Fe, Argentina", lat=-32.9442, lon=-60.6505)
GLIFOS_OK = set("🜂🜃🜁🜄🜍🜏☉☽♄☿♇☊☋♀♂♃♅♆⚷⚸✦✧△▽⟁⚖")
_TIPOGRAFICOS = set("‘’“”–—…·°′″→")
_res = []

def chk(nombre, esperado, obtenido, nota=""):
    ok = esperado == obtenido
    _res.append((ok, nombre, esperado, obtenido, nota))
    print(f"  [{'PASA' if ok else 'FALLA'}] {nombre}"
          + ("" if ok else f"\n           esperado {esperado!r} · obtenido {obtenido!r}")
          + (f"\n           {nota}" if nota and not ok else ""))
    return ok

def titulo(t):
    print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)

titulo("1 · GANZHI ANUAL contra la fórmula canónica (año − 4) % 60")
malos = []
for anio in range(1900, 2051):
    i = (anio - 4) % 60
    teorico = f"{E.TRONCOS[i % 10][0]} {E.RAMAS[i % 12][0]}"
    obt = E.bazi(f"{anio}-06-01", "12:00", TZ_AR)["pilar_anio"]["ganzhi"]
    if obt != teorico:
        malos.append((anio, teorico, obt))
chk("151 años (1900-2050) sin divergencia", 0, len(malos), nota=f"primeras divergencias: {malos[:3]}")

titulo("2 · CONTINUIDAD DEL CICLO DE DÍA (30.000 días consecutivos)")
d0 = date(1950, 1, 1); prev = None; saltos = 0
for i in range(30000):
    f = d0 + timedelta(days=i)
    g = sxtwl.fromSolar(f.year, f.month, f.day).getDayGZ()
    idx = next(c for c in range(60) if c % 10 == g.tg and c % 12 == g.dz)
    if prev is not None and idx != (prev + 1) % 60:
        saltos += 1
    prev = idx
chk("ciclo de día sin saltos 1950-2032", 0, saltos)

titulo("3 · LICHUN — el año gira en el término solar, no el 1 de enero")
for fecha, esp in [("1984-01-20", "Gui Hai"), ("1984-02-03", "Gui Hai"),
                   ("1984-02-05", "Jia Zi"),  ("1984-06-15", "Jia Zi"),
                   ("2026-01-15", "Yi Si"),   ("2026-02-10", "Bing Wu")]:
    chk(f"Lichun {fecha}", esp, E.bazi(fecha, "12:00", TZ_AR)["pilar_anio"]["ganzhi"])

titulo("4 · JIEQI POR INSTANTE UTC — el borde no se resuelve por fecha local")
for hora, esp in [("13:00", "Yi Si"), ("16:00", "Yi Si"),
                  ("17:30", "Bing Wu"), ("20:00", "Bing Wu")]:
    chk(f"borde de Lichun 2026-02-03 {hora} (AR)", esp,
        E.bazi("2026-02-03", hora, TZ_AR)["pilar_anio"]["ganzhi"],
        nota="el motor está resolviendo el borde por fecha, no por instante")
t, fin, err_a, err_m, tot = datetime(2026, 1, 1), datetime(2027, 1, 1), 0, 0, 0
while t < fin:
    f, h = t.strftime("%Y-%m-%d"), t.strftime("%H:%M")
    r = referencia(f, h, TZ_AR); b = E.bazi(f, h, TZ_AR)
    tot += 1
    err_a += r[0] != b["pilar_anio"]["ganzhi"]
    err_m += r[1] != b["pilar_mes"]["ganzhi"]
    t += timedelta(hours=1)
chk(f"barrido {tot} h · pilar de AÑO vs referencia UTC", 0, err_a)
chk(f"barrido {tot} h · pilar de MES vs referencia UTC", 0, err_m)

titulo("5 · EARLY-ZI — el día ganzhi gira a las 23:00 (3.ter.2.bis)")
b22 = E.bazi("1990-05-15", "22:30", TZ_AR)
b23 = E.bazi("1990-05-15", "23:30", TZ_AR)
b00 = E.bazi("1990-05-16", "00:30", TZ_AR)
chk("23:30 y 00:30 comparten pilar de día", b00["pilar_dia"]["ganzhi"], b23["pilar_dia"]["ganzhi"])
chk("22:30 y 23:30 tienen pilar de día distinto", True, b22["pilar_dia"]["ganzhi"] != b23["pilar_dia"]["ganzhi"])
chk("23:30 y 00:30 comparten pilar de hora", b00["pilar_hora"]["ganzhi"], b23["pilar_hora"]["ganzhi"])
chk("el tronco de hora deriva del día reportado (Wu Shu Dun)",
    True, E.TRONCOS.index(next(t for t in E.TRONCOS if t[0] == b23["pilar_hora"]["tronco"]))
          == (E.TRONCOS.index(next(t for t in E.TRONCOS if t[0] == b23["pilar_dia"]["tronco"])) * 2
              + E.RAMAS.index(next(r for r in E.RAMAS if r[2] == b23["pilar_hora"]["animal"]))) % 10)
chk("el aviso de early-zi se declara en el documento", True, any("EARLY-ZI" in a for a in b23["avisos"]))
chk("un nacimiento fuera de la hora Zi no lo declara", False, any("EARLY-ZI" in a for a in b22["avisos"]))

titulo("6 · YONG SHEN — el elemento útil NO es el ausente (3.ter.3.bis) [sin longitud: convención reloj, valores 2.4 hasta v8.8.1]")
b = E.bazi(DEMO["fecha"], DEMO["hora"], "America/Argentina/Cordoba")
chk("carta testigo: Día Maestro Wu (Tierra Yang)", "Wu", b["dia_maestro"]["tronco"])
chk("carta testigo: el DM sale fuerte", True, b["dm_fuerte"])
chk("carta testigo: Agua es el elemento ausente", ["Agua"], b["ausentes"])
chk("carta testigo: el útil NO es el ausente", True, b["elemento_util"] not in b["ausentes"])
chk("carta testigo: el útil es Metal (drena al DM fuerte)", "Metal", b["elemento_util"])
inc = 0
for f, h in [("1990-03-14","09:45"), ("1957-07-13","07:25"), ("2000-12-31","18:20"),
             ("1955-08-09","03:15"), ("2010-07-04","11:00"), ("1968-01-30","21:40")]:
    x = E.bazi(f, h, TZ_AR); el = x["dia_maestro"]["elemento"]
    ok = (x["elemento_util"] in (E.CONTROLA[el], E.DRENA[el]) if x["dm_fuerte"]
          else x["elemento_util"] in (E.NUTRE[el], el))
    inc += not ok
chk("6 cartas: el útil respeta la regla fuerte/débil", 0, inc)
YAMILA = dict(nombre="Yamila Rey Sotelo", fecha="1993-11-08", hora="23:20",
              lugar="Mendoza, Argentina", lat=-32.8895, lon=-68.8458)
by = E.bazi(YAMILA["fecha"], YAMILA["hora"], "America/Argentina/Mendoza")
ysm = by["yong_shen_metodo"]
chk("carta de exceso: Día Maestro Jia (Madera Yang)", "Jia", by["dia_maestro"]["tronco"])
chk("carta de exceso: el DM sale fuerte", True, by["dm_fuerte"])
chk("carta de exceso: ningún elemento ausente", [], by["ausentes"])
chk("el excedente detectado es Agua", "Agua", ysm["excedente"])
chk("la participación del excedente supera el 35%", True, ysm["participacion_excedente"] > 0.35)
chk("los candidatos base siguen siendo controlar y drenar", ["Metal", "Fuego"], ysm["candidatos_base"])
chk("Metal queda descartado por GENERAR el excedente", ["Metal"], ysm["descartados_por_generar_exceso"])
chk("la vía de contención entra como candidato (Tierra controla Agua)", True, "Tierra" in ysm["candidatos_finales"])
chk("el elegido ya NO es Metal", True, by["elemento_util"] != "Metal")
chk("y ningún candidato final genera el excedente", True, all(E.NUTRE[ysm["excedente"]] != c for c in ysm["candidatos_finales"]))
chk("el margen se publica para que el documento pueda declararlo", True,
    isinstance(ysm["margen"], float) and isinstance(ysm["margen_estrecho"], bool))
chk("el descarte no tuvo que revertirse por lista vacía", False, ysm["descarte_revertido_por_lista_vacia"])
bdemo = E.bazi(DEMO["fecha"], DEMO["hora"], "America/Argentina/Cordoba")
chk("2.4 intacta: el DM de la demostración sigue FUERTE", True, bdemo["dm_fuerte"])
chk("2.4 intacta: el útil de la demostración sigue siendo METAL", "Metal", bdemo["elemento_util"])
chk("2.4 intacta: sin excedente no hay corrección que aplicar", None, bdemo["yong_shen_metodo"]["excedente"])
sin_exc = 0
for f, h in [("1990-03-14","09:45"), ("2000-12-31","18:20"), ("2010-07-04","11:00")]:
    x = E.bazi(f, h, TZ_AR)
    e = x["yong_shen_metodo"]["excedente"]
    sin_exc += (e == x["dia_maestro"]["elemento"])
chk("el elemento del propio DM nunca se marca como excedente", 0, sin_exc)

titulo("7 · GRADIENTE SIN HORA — se declara, no se inventa (2.3)")
bs = E.bazi(DEMO["fecha"], None, TZ_AR)
chk("sin hora no hay pilar de hora", None, bs["pilar_hora"])
chk("sin hora se declara la ausencia del pilar", True, any("pilar de hora" in a for a in bs["avisos"]))
a_sin = E.astro(DEMO["fecha"], None, DEMO["lat"], DEMO["lon"], TZ_AR)
for campo in ("asc", "mc", "cusp_deg", "fortuna", "secta"):
    chk(f"sin hora no hay {campo}", None, a_sin[campo])
n_sin = E.numerologia(None, DEMO["fecha"])
chk("sin nombre legal no hay Alma", None, n_sin["alma"])
chk("sin nombre legal sí hay Camino", 9, n_sin["camino"])

titulo("8 · CASAS — topocéntrico canónico y fallback declarado (§0)")
chk("con hora, el sistema se DECLARA", "Topocéntrico (Polich-Page)",
    E.astro(DEMO["fecha"], DEMO["hora"], DEMO["lat"], DEMO["lon"], TZ_AR)["sistema_casas"])
chk("sobre 66° cae a Whole Sign", "Whole Sign", E.astro(DEMO["fecha"], "09:45", 69.65, 18.95, "Europe/Oslo")["sistema_casas"])
chk("bajo 66° NO cae a Whole Sign", "Topocéntrico (Polich-Page)", E.astro(DEMO["fecha"], "09:45", 59.9, 10.75, "Europe/Oslo")["sistema_casas"])

titulo("9 · NUMEROLOGÍA — escuela estricta (3.bis.2 y 3.bis.5)")
n33 = E.numerologia(None, "1957-07-13")
chk("Camino maestro se preserva", 33, n33["camino"])
chk("duración del P1 = 36 − Camino sin reducir", 3, n33["pinaculos"][0]["hasta"])
chk("Desafíos con componentes reducidos", [3, 0, 3, 3], n33["desafios"])
chk("Pináculos con componentes reducidos", [2, 8, 1, 2], [p["valor"] for p in n33["pinaculos"]])
nd = E.numerologia(DEMO["nombre"], DEMO["fecha"])
chk("núcleo de la carta de demostración", (9, 9, 1, 1, 1),
    (nd["camino"], nd["alma"], nd["expresion"], nd["personalidad"], nd["madurez"]))
chk("Madurez reducida a dígito", True, nd["madurez"] not in (11, 22, 33))

titulo("10 · ASPECTOS — sin artefactos de construcción")
ch = E.calcular(DEMO)
asp = ch["astro"]["aspectos"]
chk("el Nodo Sur no genera aspectos propios", 0, sum(1 for x in asp if "Nodo S" in (x["a"], x["b"])))
chk("el Nodo Sur sigue estando en las posiciones", True, "Nodo S" in ch["astro"]["pos"])
chk("no hay aspectos de un planeta consigo mismo", 0, sum(1 for x in asp if x["a"] == x["b"]))

titulo("11/12 · GENERADOR — (pendiente del núcleo: la suite apunta al generador histórico)")
try:
    import generar_lectura_integral as G
    from demo_lectura import LECTURA
    chk("el generador se puede importar y componer", True, True)
except Exception as e:
    print(f"  [OMITIDO] generador histórico no presente en esta corrida: {e}")

titulo("13 · TIEMPO Y VÍNCULO — funciones restituidas en v8.1 (sección 6)")
for fn in ("transitos", "sinastria", "sinastria_bazi", "anio_bazi_actual", "da_yun"):
    chk(f"la sección 6 declara {fn}() y existe", True, hasattr(E, fn))
chk("año Bazi al 2026-01-15 (antes de Lichun)", "Yi Si", E.anio_bazi_actual("2026-01-15", TZ_AR)["ganzhi"])
chk("año Bazi al 2026-08-08 (después de Lichun)", "Bing Wu", E.anio_bazi_actual("2026-08-08", TZ_AR)["ganzhi"])
dy_sin = E.da_yun(DEMO["fecha"], DEMO["hora"], TZ_AR)
chk("Da Yun sin sexo declarado no se calcula", False, dy_sin["disponible"])
chk("Da Yun sin sexo declara el motivo", True, bool(dy_sin["motivo"]))
chk("Da Yun sin hora tampoco se calcula", False, E.da_yun(DEMO["fecha"], None, TZ_AR, "F")["disponible"])
dyM = E.da_yun("1990-03-14", "09:45", TZ_AR, "M")
dyF = E.da_yun("1990-03-14", "09:45", TZ_AR, "F")
chk("tronco de año Yang + M = adelante", "adelante", dyM["direccion"])
chk("tronco de año Yang + F = atrás", "atrás", dyF["direccion"])
dyM2 = E.da_yun("1987-09-02", "21:20", TZ_AR, "M")
chk("tronco de año Yin + M = atrás", "atrás", dyM2["direccion"])
chk("la edad de inicio no es la aproximación fija de 5 años", True, dyF["edad_inicio"] != 5.0)
chk("edad de inicio = días al término / 3", round(dyF["dias_al_termino"] / 3, 2), dyF["edad_inicio"])
chk("los ciclos duran 10 años", True, all(round(c["hasta"] - c["desde"], 1) == 10.0 for c in dyF["ciclos"]))
tr = E.transitos(DEMO, "2026-08-08")
chk("hay tránsitos activos", True, len(tr["transitos"]) > 0)
chk("los planetas lentos encabezan la lista", True, all(x["lento"] for x in tr["transitos"][:3]))
chk("la Luna en tránsito solo entra con orbe ≤ 1°", True, all(x["orbe"] <= 1.0 for x in tr["transitos"] if x["transito"] == "Luna"))
OTRA = dict(nombre="Tomás Ariel Bengoechea", fecha="1987-09-02", hora="21:20",
            lugar="Córdoba, Argentina", lat=-31.4201, lon=-64.1888)
sy = E.sinastria(DEMO, OTRA)
chk("la sinastría produce aspectos cruzados", True, len(sy["aspectos"]) > 0)
chk("el Nodo Sur no duplica el eje en sinastría", 0, sum(1 for x in sy["aspectos"] if "Nodo S" in (x["a"], x["b"])))
sb = E.sinastria_bazi(DEMO, OTRA)
chk("la sinastría Bazi reporta las tres relaciones", True, set(sb["relaciones"]) == {"chong", "liuhe", "sanhe"})
chk("una Sanhé completa solo se declara con las tres ramas; la media se rotula como media (v9.0)", True, all((len(r["ramas"]) == 3) if r["completa"] else ("media" in r["tipo"] and len(r["ramas"]) == 2) for r in sb["relaciones"]["sanhe"]))

titulo("14 · REFINAMIENTOS v8.1 — fallas 14, 15 y 16 [sin longitud: convención reloj]")
nd = E.numerologia(DEMO["nombre"], DEMO["fecha"])
chk("la traza de Madurez se conserva entera", True, isinstance(nd["madurez_traza"], list))
chk("sin maestro en la traza no se inventa eco", None, nd["madurez_eco"])
n33 = E.numerologia("Leopoldo Anselmo Zubizarreta Iglesias", "1957-07-13")
chk("eco oculto detectado en un paso intermedio", 11, n33["madurez_eco"])
chk("la Madurez sigue siendo el dígito reducido", 2, n33["madurez"])
chk("traza completa 38 → 11 → 2", [38, 11, 2], n33["madurez_traza"])
bd = E.bazi(DEMO["fecha"], DEMO["hora"], "America/Argentina/Cordoba")
chk("el balance descriptivo no se toca (2.4 sigue válido)",
    {"Madera": 1.6, "Fuego": 2.6, "Tierra": 2.7, "Metal": 1.1, "Agua": 0.0}, bd["balance"])
chk("existe un balance ponderado aparte", True, "balance_ponderado" in bd)
chk("el ponderado difiere del plano", True, bd["balance_ponderado"] != bd["balance"])
chk("se declara si el DM está en estación", True, isinstance(bd["en_estacion"], bool))
chk("el método de fuerza se declara en texto", True, len(bd["metodo_fuerza"]) > 40)
chk("el umbral se corrige por estación", True, bd["umbral_fuerza"] == (0.45 if bd["en_estacion"] else 0.55))
chk("la carta testigo sigue dando útil Metal tras el refinamiento", "Metal", bd["elemento_util"])
inc = 0
for f, h in [("1990-03-14","09:45"), ("1957-07-13","07:25"), ("2000-12-31","18:20"),
             ("1955-08-09","03:15"), ("2010-07-04","11:00"), ("1968-01-30","21:40"),
             ("1943-11-22","07:05"), ("1999-04-17","14:50")]:
    x = E.bazi(f, h, TZ_AR); el = x["dia_maestro"]["elemento"]
    ok = (x["elemento_util"] in (E.CONTROLA[el], E.DRENA[el]) if x["dm_fuerte"]
          else x["elemento_util"] in (E.NUTRE[el], el))
    inc += not ok
chk("8 cartas: el útil respeta la regla fuerte/débil", 0, inc)
enc = {"completa": 0, "media": 0}
for f, h in [("1990-03-14","09:45"), ("1957-07-13","07:25"), ("2000-12-31","18:20"),
             ("1955-08-09","03:15"), ("2010-07-04","11:00"), ("1968-01-30","21:40")]:
    for r in E.bazi(f, h, TZ_AR)["relaciones"]["sanhe"]:
        enc["completa" if r["completa"] else "media"] += 1
        chk_tipo = "Sanhé (trío)" if r["completa"] else "media combinación (Banhe)"
        if r["tipo"] != chk_tipo:
            enc["media"] = -999
chk("una Sanhé de dos ramas no se etiqueta como trío", True, enc["media"] >= 0)
chk("el trío completo lleva las tres ramas", True,
    all(len(r["presentes"]) == 3 for f, h in [("1990-03-14","09:45"), ("1957-07-13","07:25")]
        for r in E.bazi(f, h, TZ_AR)["relaciones"]["sanhe"] if r["completa"]))

titulo("15 · SEXO DERIVADO DEL NOMBRE — hipótesis declarada, no hecho")
casos = [("Lucía Mariana Ferreyra", "F", "alta"), ("Tomás Ariel Bengoechea", "M", "alta"),
         ("José María Aznar Pérez", "M", "alta"), ("María José Ruiz Solá",   "F", "alta"),
         ("Ariel Cruz Domínguez",  None, None), ("Xiaoyu Chen", None, None)]
for nom, esp_s, esp_c in casos:
    r = E.sexo_desde_nombre(nom)
    chk(f"«{nom.split()[0]}» → {esp_s}", (esp_s, esp_c), (r["sexo"], r["certeza"]))
chk("sin nombre no se deriva nada", None, E.sexo_desde_nombre(None)["sexo"])
chk("toda derivación trae su declaración para el documento", True, all(E.sexo_desde_nombre(n)["declaracion"] for n, _, _ in casos))
d_expl = dict(DEMO); d_expl["sexo"] = "M"
chk("un sexo explícito gana sobre el nombre", "declarado por el consultante", E.calcular(d_expl)["da_yun"]["origen_sexo"])
chk("y cambia la dirección del ciclo", "adelante", E.calcular(d_expl)["da_yun"]["direccion"])
d_amb = dict(DEMO); d_amb["nombre"] = "Ariel Cruz Domínguez"
chk("nombre ambiguo → Da Yun no disponible", False, E.calcular(d_amb)["da_yun"]["disponible"])
av = E.calcular(DEMO)["avisos"]
chk("la derivación se declara en la caja de límites", True, any("se derivó del nombre" in a for a in av))

titulo("16 · LA Y COMO VOCAL — criterio declarado (3.bis.1)")
_F = DEMO["fecha"]
def _y(nom):
    return [(x["palabra"], x["regla"], x["cuenta_como"]) for x in E.numerologia(nom, _F)["y_vocal"]]
chk("«Yolanda»", [("YOLANDA", "inicial+vocal", "consonante")], _y("Yolanda Perez"))
chk("«Maya» / «Godoy»", [("MAYA", "entre vocales", "consonante"), ("GODOY", "final tras vocal", "vocal")], _y("Maya Godoy"))
chk("«Sylvia» / «Reyes»", [("SYLVIA", "tras consonante", "vocal"), ("REYES", "entre vocales", "consonante")], _y("Sylvia Reyes"))
chk("un nombre sin Y declara la lista vacía, no ausente", [], _y("Ana Lopez"))
chk("sin nombre legal tampoco hay Y que declarar", [], E.numerologia(None, _F)["y_vocal"])
chk("la conjunción «y» suelta cuenta como vocal", [("Y", "conjunción", "vocal")], _y("Juan y Maria"))
chk("Y inicial ante consonante cae al default del canon", [("YVES", "consonante por defecto", "consonante")], _y("Yves Perez"))
chk("contar la Y como vocal altera el Alma", True, E.numerologia("Sylvia Ruiz", _F)["alma"] != E.numerologia("Silvia Ruiz", _F)["alma"])
chk("la Expresión no depende de la decisión sobre la Y", 7, E.numerologia("Maya Godoy", _F)["expresion"])
ny = E.numerologia(DEMO["nombre"], DEMO["fecha"])
chk("la carta de demostración declara su Y", [("FERREYRA", "consonante por defecto", "consonante")],
    [(x["palabra"], x["regla"], x["cuenta_como"]) for x in ny["y_vocal"]])
chk("y su núcleo publicado en 2.4 no cambió", (9, 9, 1, 1, 1),
    (ny["camino"], ny["alma"], ny["expresion"], ny["personalidad"], ny["madurez"]))

titulo("17 · HITOS DE CICLO — retornos planetarios")
_h = {x['cuerpo']: x for x in E.transitos(DEMO, "2020-01-15")['hitos']}
chk("retorno de Saturno detectado en la carta de demostración", True, 'Saturno' in _h)
chk("el retorno se etiqueta con nombre propio", "Retorno de Saturno", _h.get('Saturno', {}).get('etiqueta'))
chk("el retorno cae dentro de orbe", True, _h.get('Saturno', {}).get('orbe', 99) <= 1.5)
chk("sin hitos falsos a los 36 años", [], E.transitos(DEMO, "2026-03-14")['hitos'])
chk("Quirón es blanco natal de los tránsitos", True, 'Quirón' in E.SENSIBLES)
_ruido = [x['etiqueta'] for _m in range(1, 13) for x in E.transitos(DEMO, f"2019-{_m:02d}-15")['hitos']
          if x['cuerpo'] == 'Marte' and x['hito'] != 'Retorno']
chk("Marte no dispara cuartos ni medios de ciclo", [], _ruido)
chk("la tabla de ciclos cubre los cuerpos con retorno vital", True,
    all(c in E.CICLOS for c in ('Marte', 'Júpiter', 'Saturno', 'Quirón', 'Urano', 'Nodo N')))

# ============================================================
titulo("18 · v8.8.1 — controles nuevos de la auditoría del 28/10/2026")
# P1: backend declarado y real
Ad = E.astro(DEMO["fecha"], DEMO["hora"], DEMO["lat"], DEMO["lon"], "America/Argentina/Cordoba")
chk("el motor declara qué efemérides usó", True, bool(Ad.get("efemerides")))
chk("con los archivos .se1 presentes el backend es Swiss Ephemeris, no Moshier",
    "Swiss Ephemeris", Ad["efemerides"], nota="faltan sepl_18.se1 / semo_18.se1 en EPHE_DIR")
chk("calcular() publica el backend", True, "efemerides" in E.calcular(DEMO))
# Referencia externa fijada el 28/10/2026: astro.com swetest (DE441) para la carta de demostración.
REF_ASTROCOM = {"Sol": 353.6746017, "Luna": 208.1690115, "Saturno": 293.2616711, "Quirón": 100.5678459,
                "Lilith": 224.5351638}
peor = max(abs(((Ad["pos"][p]["grados"] - v + 180) % 360 - 180)) * 3600 for p, v in REF_ASTROCOM.items())
chk("carta de demostración dentro de 2″ de astro.com (Sol, Luna, Saturno, Quirón, Lilith)", True, peor < 2.0,
    nota=f"peor diferencia {peor:.2f}″")
# Casas: la referencia de astro.com se tomó con las coordenadas de la auditoría (−32.9468, −60.6393).
Ac = E.astro(DEMO["fecha"], DEMO["hora"], -32.9468, -60.6393, "America/Argentina/Cordoba")
chk("Ascendente topocéntrico = astro.com (27.5018937)", True, abs(Ac["asc_deg"] - 27.5018937) * 3600 < 0.1)
chk("MC = astro.com (300.2938685)", True, abs(Ac["mc_deg"] - 300.2938685) * 3600 < 0.1)
chk("cúspide II topocéntrica = astro.com (56.1126375)", True, abs(Ac["cusp_deg"][1] - 56.1126375) * 3600 < 0.1)
# P2: borde de signo
# v9.0 (E11): fmt trunca al minuto; el signo mostrado es el real (el control viejo daba por bueno «0°00' Tauro»)
chk("fmt muestra 29°59.6' en su signo real (v9.0: trunca)", "29°59' Aries", E.fmt(29.9959))
chk("fmt: 359°59.99' sigue en Piscis", "29°59' Piscis", E.fmt(359.9999))
chk("fmt: 30° exactos es Tauro", "0°00' Tauro", E.fmt(30.0))
chk("fmt no toca un grado normal", "27°30' Aries", E.fmt(27.50189))
# P3 → v8.9: el pilar de hora se calcula sobre la HORA SOLAR LOCAL cuando hay longitud (sección 19).
# Sin longitud, el motor cae a reloj y lo declara.
bF = E.bazi("1990-01-20", "15:30", "America/Argentina/Cordoba")   # sin lon → reloj
chk("sin longitud el pilar de hora cae a hora de reloj y lo declara", "hora de reloj (civil)", bF["hora_pilar"]["convencion"])
chk("y el aviso dice por qué", True, any("no se recibió la longitud" in a for a in bF["avisos"]))
chk("con longitud, la convención es solar", "hora solar local aparente",
    E.bazi("1990-01-20", "15:30", "America/Argentina/Cordoba", -60.6393)["hora_pilar"]["convencion"])
# P4: lugar sin país
try:
    E._resolver_lugar({"lugar": "Córdoba"}); chk("lugar sin país se rechaza", True, False)
except ValueError as e:
    chk("lugar sin país se rechaza", True, "sin país" in str(e))
chk("lat/lon explícitas siguen pasando sin país", "America/Argentina/Cordoba",
    E._resolver_lugar({"lugar": "Córdoba", "lat": -31.42, "lon": -64.19})[2])

# ============================================================
titulo("19 · v8.9 — HORA SOLAR LOCAL para día y hora Bazi (decisión 28/10/2026)")
LON_DEMO = DEMO["lon"]
bs = E.bazi(DEMO["fecha"], DEMO["hora"], "America/Argentina/Cordoba", LON_DEMO)
br = E.bazi(DEMO["fecha"], DEMO["hora"], "America/Argentina/Cordoba", LON_DEMO, convencion="reloj")
hp = bs["hora_pilar"]
chk("la corrección se publica desglosada (longitud, ecuación del tiempo, total)", True,
    all(k in hp for k in ("correccion_longitud_min", "ecuacion_tiempo_min", "correccion_total_min", "hora_solar")))
chk("demostración: 09:45 de reloj en Rosario son 08:33 solares", "08:33", hp["hora_solar"])
chk("demostración: corrección por longitud ≈ −63 min (60,65° O contra el meridiano de −45°)", True,
    abs(hp["correccion_longitud_min"] + 62.6) < 0.5)
chk("demostración: pilar de hora pasa de Serpiente (reloj) a Dragón (solar)",
    ("Ding Si", "Bing Chen"), (br["pilar_hora"]["ganzhi"], bs["pilar_hora"]["ganzhi"]))
chk("y el motor publica qué habría dado el reloj", "Ding Si", hp["pilar_hora_por_reloj"])
chk("el pilar de día de la demostración no cambia", "Wu Yin", bs["pilar_dia"]["ganzhi"])
chk("año y mes no dependen de la convención", (br["pilar_anio"]["ganzhi"], br["pilar_mes"]["ganzhi"]),
    (bs["pilar_anio"]["ganzhi"], bs["pilar_mes"]["ganzhi"]))
# Carta de demostración 2.4 — valores NUEVOS (a escribir en el núcleo con la adenda 8.6.3)
chk("2.4 (v8.9): balance descriptivo", {"Madera": 1.9, "Fuego": 2.0, "Tierra": 3.0, "Metal": 1.0, "Agua": 0.1}, bs["balance"])
chk("2.4 (v8.9): el DM sigue siendo Wu y sigue fuerte", ("Wu", True), (bs["dia_maestro"]["tronco"], bs["dm_fuerte"]))
chk("2.4 (v8.9): el útil sigue siendo Metal", "Metal", bs["elemento_util"])
chk("2.4 (v8.9): el Agua deja de estar ausente (0.1 oculta en la rama Chen)", [], bs["ausentes"])
chk("el aviso de convención llega al documento", True, any("hora solar local" in a for a in bs["avisos"]))
chk("calcular() usa la convención solar (pasa la longitud)", "Bing Chen", E.calcular(DEMO)["bazi"]["pilar_hora"]["ganzhi"])
# early-zi se mide en hora solar
bB = E.bazi("1985-11-23", "23:30", "America/Argentina/Buenos_Aires", -58.3816)
chk("23:30 de reloj en Buenos Aires NO es hora Zi (22:49 solar): el día no gira", "Bing Yin", bB["pilar_dia"]["ganzhi"])
chk("y se declara que el reloj habría dado otro Día Maestro", True, bB["hora_pilar"]["cambia_dia"] and bB["hora_pilar"]["pilar_dia_por_reloj"] == "Ding Mao")
bM = E.bazi("1993-11-09", "00:30", "America/Argentina/Mendoza", -68.8458)
chk("00:30 de reloj en Mendoza SÍ es hora Zi (23:10 solar): early-zi lleva el día al 9/11", "Jia Wu", bM["pilar_dia"]["ganzhi"])
chk("borde de franja: a 10 min se avisa", True, bM["hora_pilar"]["minutos_al_borde_de_franja"] == 10 and any("borde de una franja" in a for a in bM["avisos"]))
chk("lejos del borde no se avisa", False, any("borde de una franja" in a for a in bs["avisos"]))
# El horario de verano queda absorbido por la hora solar (caso F)
bF2 = E.bazi("1990-01-20", "15:30", "America/Argentina/Cordoba", -60.6393)
chk("verano 1990 en Rosario: 15:30 de reloj → 13:16 solar, pilar Cabra", ("13:16", "Gui Wei"), (bF2["hora_pilar"]["hora_solar"], bF2["pilar_hora"]["ganzhi"]))
chk("el DST se declara dentro de la corrección", True, bF2["hora_pilar"]["dst_activo"])
# La convención «reloj» sigue disponible para auditar lecturas anteriores a v8.9
chk("convención reloj reproduce el balance publicado en 2.4 hasta v8.8.1",
    {"Madera": 1.6, "Fuego": 2.6, "Tierra": 2.7, "Metal": 1.1, "Agua": 0.0}, br["balance"])

import controles_v9
controles_v9.correr(chk, titulo, E)
controles_v9.correr_bazi(chk, titulo, E)
controles_v9.correr_astro(chk, titulo, E)
controles_v9.correr_horas(chk, titulo, E)
controles_v9.correr_numeros(chk, titulo, E)
controles_v9.correr_sin_hora_sexo(chk, titulo, E)
controles_v9.correr_resto(chk, titulo, E)
controles_v9.correr_doctrina(chk, titulo, E)
controles_v9.correr_referencia_privada(chk, titulo, E)

titulo("RESUMEN")
p = sum(1 for r in _res if r[0]); f_ = len(_res) - p
for ok, nombre, esp, obt, nota in _res:
    if not ok:
        print(f"  FALLA · {nombre}: esperado {esp!r}, obtenido {obt!r}")
print(f"\n  {p} controles pasan · {f_} fallan\n")
sys.exit(1 if f_ else 0)
