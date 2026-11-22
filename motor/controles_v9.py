# -*- coding: utf-8 -*-
"""controles_v9.py · controles nuevos de la auditoría del 22/11/2026 (motor v9.0).
Cada control sale de un caso concreto que la v8.9 calculaba mal. Lo llama validar_elbrujo.py."""
from datetime import date

def _d(fecha, hora="10:00", nombre="Ana Prueba"):
    return dict(fecha=fecha, hora=hora, nombre=nombre, lugar="Buenos Aires, Argentina",
                lat=-34.6037, lon=-58.3816, tz="America/Argentina/Buenos_Aires")

def correr(chk, titulo, E):
    titulo("20 · v9.0 — CICLOS NUMÉRICOS (auditoría 22/11/2026: E2, E3, E4, E14 parcial, E18)")
    # E2: Año Personal de los nacidos los días 29, 30 y 31 (30+3+2026 → 3+3+1 = 7)
    chk("E2 · nacido el 30/3: Año Personal 7 (v8.9 daba 6)", 7, E.anio_personal(_d("1990-03-30"), "2026-11-22")["anio_personal"])
    chk("E2 · nacido el 31/1: Año Personal 6 (v8.9 daba 5)", 6, E.anio_personal(_d("1985-01-31"), "2026-11-22")["anio_personal"])
    chk("E2 · nacido el 29/2, año no bisiesto: ciclo desde el 1/3", ("2026-03-01", 5),
        (lambda r: (r["inicio"], r["anio_personal"]))(E.anio_personal(_d("1992-02-29"), "2026-11-22")))
    chk("E2 · nacido el 29/2, año bisiesto: ciclo desde el 29/2", ("2028-02-29", 7),
        (lambda r: (r["inicio"], r["anio_personal"]))(E.anio_personal(_d("1992-02-29"), "2028-03-01")))
    chk("E2 · el ciclo termina el día antes del cumpleaños", "2027-03-29", E.anio_personal(_d("1990-03-30"), "2026-11-22")["fin"])
    # E3: Pináculos sin hueco (Camino 9: 0–27, 27–36, 36–45, 45+)
    pin = E.numerologia("Ana Prueba", "1990-03-14", "2026-11-22")["pinaculos"]
    chk("E3 · tramos contiguos (Camino 9)", [(0, 27), (27, 36), (36, 45), (45, None)], [(p["desde"], p["hasta"]) for p in pin])
    chk("E3 · a los 36 años y 8 meses hay pináculo (v8.9: ninguno)", 3, E.anio_personal(_d("1990-03-14"), "2026-11-22")["pinaculo"]["n"])
    chk("E3 · el día antes de cumplir 27 sigue el P1", 1, E.anio_personal(_d("1990-03-14"), "2017-03-13")["pinaculo"]["n"])
    chk("E3 · el día que cumple 27 empieza el P2", 2, E.anio_personal(_d("1990-03-14"), "2017-03-14")["pinaculo"]["n"])
    # E4: «El año contado» toma el Año Personal del ciclo que abre (nacido 00:20, RS el día antes)
    chk("E4 · anio(): Año Personal del cumpleaños, no de la fecha local de la RS", 9,
        E.anio(_d("1990-03-14", "00:20"), 2026)["num"]["anio_personal"])
    # mes del cumpleaños: se publica el cambio de ciclo
    cc = E.mes(_d("1990-03-30"), 2027, 3)["cambio_de_ciclo"]
    chk("mes(): el cumpleaños dentro del mes publica el cambio de Año Personal", ("2027-03-30", 7, 8),
        (cc["fecha"], cc["anio_personal_antes"], cc["anio_personal_despues"]))
    chk("mes(): sin cumpleaños en el mes no hay cambio", None, E.mes(_d("1990-03-30"), 2027, 5)["cambio_de_ciclo"])
    # retorno con nacidos el 29/2 (v8.9: ValueError)
    chk("retorno(): nacido el 29/2 no se cae", True, isinstance(E.retorno(_d("1992-02-29"), "Saturno", "2021-06-01")["anio_personal_retorno"], int))
    # E18: año real de inicio de la década
    c = E.decadas(_d("1990-11-20"), "2026-11-22")["ciclos"][0]
    chk("E18 · la primera década arranca en 1995-03 (desde 4,3 años), no redondeada", ("1995", 1995), (c["fecha_desde"][:4], c["anio_desde"]))

def correr_bazi(chk, titulo, E):
    titulo("21 · v9.0 — BAZI: términos solares al segundo (E5) y borde de franja (E9)")
    # E5: Lichun 1950 = 04/02 09:20:45,6 UTC. 03:20 en CDMX (UTC−6) = 09:20 UTC: todavía año Ji Chou.
    b = E.bazi("1950-02-04", "03:20", "America/Mexico_City", -99.13)
    chk("E5 · 45 s antes del Lichun el año sigue siendo Ji Chou (v8.9: Geng Yin)", ("Ji Chou", "Ding Chou"),
        (b["pilar_anio"]["ganzhi"], b["pilar_mes"]["ganzhi"]))
    b = E.bazi("1950-02-04", "03:21", "America/Mexico_City", -99.13)
    chk("E5 · 15 s después del Lichun ya es Geng Yin", ("Geng Yin", "Wu Yin"), (b["pilar_anio"]["ganzhi"], b["pilar_mes"]["ganzhi"]))
    jq = [t for t, i in E._jieqi_utc([1950]) if i == 3][0]
    chk("E5 · el término lleva segundos (09:20:45)", "09:20:45", jq.strftime("%H:%M:%S"))
    # E9: Buenos Aires 1985-11-23 23:36 reloj = 22:55 solar → borde adelante (23:00): del otro lado, Geng Zi y otro día
    b = E.bazi("1985-11-23", "23:36", "America/Argentina/Buenos_Aires", -58.3816)
    o = b["hora_pilar"].get("del_otro_lado") or {}
    chk("E9 · el aviso nombra el pilar del OTRO lado (Geng Zi), no el actual (Ji Hai)", ("Ji Hai", "Geng Zi"),
        (b["pilar_hora"]["ganzhi"], b["hora_pilar"].get("pilar_hora_si_cruza")))
    chk("E9 · y avisa que del otro lado cambia el Día Maestro (early-zi)", True, o.get("cambia_dia"))
    chk("E9 · el aviso menciona el Día Maestro", True, any("Día Maestro" in a and "borde" in a for a in b["avisos"]))
    # borde ATRÁS: 01:05 solar → del otro lado (00:59) sigue Zi
    bM = E.bazi("1993-11-09", "00:30", "America/Argentina/Mendoza", -68.8458)   # 23:10 solar
    chk("E9 · borde atrás (23:10 solar): del otro lado es Hai", "Hai", bM["hora_pilar"]["pilar_hora_si_cruza"].split()[1])

def correr_astro(chk, titulo, E):
    titulo("22 · v9.0 — CIELO: ángulos progresados (E1)")
    D = dict(fecha="1990-03-14", hora="09:45", lugar="Rosario, Santa Fe, Argentina", lat=-32.9442, lon=-60.6505)
    nat = E.calcular(D)["astro"]
    p1 = E.progresiones(D, "2026-11-22")["progresada"]; p2 = E.progresiones(D, "2026-11-29")["progresada"]
    p3 = E.progresiones(D, "2026-12-22")["progresada"]
    chk("E1 · MC progresado = MC natal + arco solar", True, abs(((p1["mc_deg"] - nat["mc_deg"] - p1["arco_solar"]) + 180) % 360 - 180) < 1e-3)
    chk("E1 · en una semana el MC progresado se mueve menos de 0,05° (v8.9: ~7°)", True, abs(((p2["mc_deg"] - p1["mc_deg"]) + 180) % 360 - 180) < 0.05)
    chk("E1 · en un mes, menos de 0,15° (v8.9: ~32°)", True, abs(((p3["mc_deg"] - p1["mc_deg"]) + 180) % 360 - 180) < 0.15)
    p0 = E.progresiones(D, "1990-03-14")["progresada"]
    chk("E1 · el día del nacimiento, ángulos progresados = natales (menos de 0,05°)", True,
        all(abs(((p0[k] - nat[k]) + 180) % 360 - 180) < 0.05 for k in ("mc_deg", "asc_deg")))
    chk("E1 · el método se declara", True, "arco solar" in p1["metodo_angulos"])

def correr_horas(chk, titulo, E):
    titulo("23 · v9.0 — HORAS: cambio de horario (E6), hora media antigua (E10), medianoche UTC (E12)")
    BA = dict(lat=-34.6037, lon=-58.3816, tz="America/Argentina/Buenos_Aires")
    c = E.calcular(dict(fecha="2008-03-15", hora="23:30", **BA))
    chk("E6 · 15/3/2008 23:30 en Buenos Aires: hora repetida, se declara", "repetida", (c["hora_dudosa"] or {}).get("tipo"))
    chk("E6 · las dos lecturas del Ascendente (21°06' y 5°35' Sagitario, truncado)", ("21°06' Sagitario", "5°35' Sagitario"),
        (c["hora_dudosa"]["usada"]["asc"], c["hora_dudosa"]["alternativa"]["asc"]))
    chk("E6 · el aviso llega a la carta", True, any("Hora de nacimiento dudosa" in a for a in c["avisos"]))
    chk("E6 · 30/12/2007 00:30 en Buenos Aires: hora inexistente", "inexistente", E.calcular(dict(fecha="2007-12-30", hora="00:30", **BA))["hora_dudosa"]["tipo"])
    chk("E6 · con dst elegido no hay duda", None, E.calcular(dict(fecha="2008-03-15", hora="23:30", dst=True, **BA))["hora_dudosa"])
    chk("E6 · una hora normal no se marca", None, E.calcular(dict(fecha="2008-05-15", hora="23:30", **BA))["hora_dudosa"])
    a = E.astro("1879-03-14", "11:30", 48.4011, 9.9876, "Europe/Berlin")
    chk("E10 · Einstein (Ulm, 1879): hora media del lugar → 10:50 UTC, Asc 11°38' Cáncer, igual que astro.com",
        ("10:50", "11°38' Cáncer"), (a["utc"].strftime("%H:%M"), a["asc"]))
    chk("E12 · un instante a 20 s de la medianoche UTC no se cae", "2000-01-02 00:00", E._jd_a_local(2451545.49977, "UTC")[0].strftime("%Y-%m-%d %H:%M"))

def correr_numeros(chk, titulo, E):
    titulo("24 · v9.0 — NÚMEROS: forma del Camino (D1), deudas individuales (D2, E17), ecos (E16)")
    t = E.numerologia("Lucía Mariana Ferreyra", "1990-03-14", "2026-11-22")
    chk("D2 · carta testigo: núcleo intacto 9·9·1·1", (9, 9, 1, 1), (t["camino"], t["alma"], t["expresion"], t["personalidad"]))
    chk("D2 · carta testigo: deudas [14] (el 19 del año 1990 ya no cuenta)", [14], t["deudas"])
    chk("E17 · la deuda 14 sale del día de nacimiento", "día de nacimiento", t["deudas_por_posicion"][0]["posicion"])
    x = E.numerologia(None, "1940-01-01", "2026-11-22")
    chk("D1 · 1940-01-01: la casa da Camino 7 sin deuda", (7, []), (x["camino"], x["deudas"]))
    chk("D1 · la suma completa (1942 → 16 → 7) queda como observación de deuda 16", True,
        any(o["tipo"] == "deuda" and o["valor"] == 16 for o in x["observaciones"]))
    chk("D1 · 1957-07-13 sigue dando Camino 33 (la forma de la casa conserva maestros en los componentes)", 33,
        E.numerologia(None, "1957-07-13", "2026-11-22")["camino"])
    chk("D2 · 16/3/1971: deuda 16 del día y 19 de la suma del Camino (7+3+9)", [(16, "día de nacimiento"), (19, "Camino de Vida")], [(x["deuda"], x["posicion"]) for x in E.numerologia(None, "1971-03-16", "2026-11-22")["deudas_por_posicion"]])
    chk("E16 · eco oculto en el P1 (1990-02-09: 2+9 = 11 → 2)", 11, E.numerologia(None, "1990-02-09", "2026-11-22")["ecos"]["P1"]["eco"])

def correr_sin_hora_sexo(chk, titulo, E):
    titulo("25 · v9.0 — SIN HORA (E7, D6) y SEXO PARA EL DA YUN (E8, D9)")
    BA = dict(lat=-34.6037, lon=-58.3816, tz="America/Argentina/Buenos_Aires")
    c = E.calcular(dict(fecha="2026-02-03", **BA))["sin_hora_posibles"]["cambian_en_el_dia"]
    chk("D6 · día del Lichun 2026 sin hora: el año cambia a las 17:03 (Yi Si → Bing Wu)", ["Yi Si", "Bing Wu", "17:03"],
        [c["pilar_anio"][0]["valor"], c["pilar_anio"][1]["valor"], c["pilar_anio"][1]["desde"]])
    chk("D6 · y la Luna pasa de Leo a Virgo a las 00:22", ["Leo", "Virgo", "00:22"], [c["Luna"][0]["valor"], c["Luna"][1]["valor"], c["Luna"][1]["desde"]])
    c = E.calcular(dict(fecha="1990-07-10", lat=40.4168, lon=-3.7038, tz="Europe/Madrid"))
    chk("D6 · Madrid en verano sin hora: Día Maestro distinto hasta las 01:21", "01:21", c["sin_hora_posibles"]["cambian_en_el_dia"]["pilar_dia"][1]["desde"])
    chk("D6 · el aviso sin hora ya no dice que los aspectos de la Luna son válidos", False,
        any("aspectos son válidos" in a for a in c["avisos"]))
    chk("D6 · aspectos de la Luna marcados como aproximados", True,
        all(x.get("aproximado_sin_hora") for x in c["astro"]["aspectos"] if "Luna" in (x["a"], x["b"])))
    sx = lambda n, p=False: E.sexo_desde_nombre(n, p)["sexo"]
    chk("D9 · «Ariel Luna»: el apellido no decide (sin sexo)", None, sx("Ariel Luna"))
    chk("D9 · «Kevin Luna» es M", "M", sx("Kevin Luna"))
    chk("D9 · «Jesús María Díaz» es M", "M", sx("Jesús María Díaz"))
    chk("D9 · «Borja» y «Joshua» son M", ("M", "M"), (sx("Borja Pérez"), sx("Joshua Gómez")))
    chk("D9 · José María / María José", ("M", "F"), (sx("José María Paz"), sx("María José Paz")))
    chk("D9 · con nombres de pila aparte, el segundo desempata («Ariel Ignacio»)", "M", sx("Ariel Ignacio", True))


def correr_resto(chk, titulo, E):
    titulo("26 · v9.0 — latitudes altas (E13), fechas y nombres (E14, E15), sinastría china (E19), efemérides (E20), lugar (E21)")
    T = (69.6492, 18.9553, "Europe/Oslo")
    chk("E13 · Tromsø, sol de medianoche (20/6/1990 00:00): carta diurna", True, E.astro("1990-06-20", "00:00", *T)["diurna"])
    chk("E13 · Tromsø, noche polar (20/12/1990 12:00): carta nocturna", False, E.astro("1990-12-20", "12:00", *T)["diurna"])
    def frena(f):
        try:
            f(); return False
        except ValueError:
            return True
    chk("E14 · 30/2 no existe: frena con mensaje", True, frena(lambda: E.numerologia("Ana", "1990-02-30")))
    chk("E14 · mes 13 no existe (v8.9 anotaba deuda 13)", True, frena(lambda: E.numerologia("Ana", "1990-13-01")))
    chk("E14 · formato 14/03/1990: frena con mensaje", True, frena(lambda: E.numerologia("Ana", "14/03/1990")))
    chk("E14 · fuera del rango de efemérides (1700): frena", True, frena(lambda: E.numerologia("Ana", "1700-01-01")))
    chk("E14 · consulta anterior al nacimiento: frena", True, frena(lambda: E.numerologia("Ana", "2030-01-01", "2026-01-01")))
    chk("E14 · hora 25:00: frena", True, frena(lambda: E.calcular(dict(fecha="1990-01-01", hora="25:00", lat=-34.6, lon=-58.4))))
    chk("E15 · «Søren» = «Soren»", E.numerologia("Soren Kierkegaard", "1813-05-05", "2026-01-01")["alma"],
        E.numerologia("Søren Kierkegaard", "1813-05-05", "2026-01-01")["alma"])
    chk("E15 · «Æsa» = «Aesa»", E.numerologia("Aesa Lund", "1990-01-01", "2026-01-01")["expresion"],
        E.numerologia("Æsa Lund", "1990-01-01", "2026-01-01")["expresion"])
    chk("E15 · nombre en cirílico: frena (v8.9 daba 0 sin aviso)", True, frena(lambda: E.numerologia("Иван", "1990-01-01", "2026-01-01")))
    chk("E15 · Ñ vale 5 como N", E.numerologia("Nandu Pena", "1990-01-01", "2026-01-01")["expresion"],
        E.numerologia("Ñandú Peña", "1990-01-01", "2026-01-01")["expresion"])
    # E19: un trío entero en una sola carta no es del vínculo
    import types
    rel = E.sinastria_bazi(dict(fecha="1990-03-14", hora="09:45", lat=-32.9442, lon=-60.6505, tz="America/Argentina/Cordoba"),
                           dict(fecha="1985-11-23", hora="18:20", lat=-34.6037, lon=-58.3816, tz="America/Argentina/Buenos_Aires"))["relaciones"]
    chk("E19 · toda combinación informada tiene aporte de las dos cartas", True,
        all(x.get("aporta_a") and x.get("aporta_b") for x in rel["sanhe"]))
    # E20: desde otro hilo sigue con Swiss Ephemeris
    import threading
    out = {}
    th = threading.Thread(target=lambda: out.update(e=E.astro("1990-03-14", "09:45", -32.9442, -60.6505, "America/Argentina/Cordoba")["efemerides"]))
    th.start(); th.join()
    chk("E20 · en otro hilo sigue Swiss Ephemeris (no Moshier)", "Swiss Ephemeris", out.get("e"))
    # E21: el lugar encontrado se declara (búsqueda simulada, sin red)
    orig = E.geocodificar
    def falso(lugar):
        E._GEO_NOMBRE[lugar] = "San Martín, Partido de General San Martín, Buenos Aires, Argentina"
        return -34.5750, -58.5370
    E.geocodificar = falso
    try:
        c = E.calcular(dict(fecha="1990-01-01", hora="10:00", lugar="San Martín, Argentina"))
    finally:
        E.geocodificar = orig
    chk("E21 · el lugar encontrado queda en los datos", True, (c["datos"].get("lugar_encontrado") or "").startswith("San Martín, Partido"))
    chk("E21 · y en los avisos", True, any("Lugar encontrado" in a for a in c["avisos"]))


def correr_doctrina(chk, titulo, E):
    titulo("27 · v9.0 — decisiones de la adenda 8.6.4 (D3, D4, D5, D7, D10, D11)")
    a = E.astro("1990-03-14", "09:45", -32.9442, -60.6505, "America/Argentina/Cordoba")
    chk("D3 · la carta publica que el Nodo es el verdadero", "Nodo verdadero", a["convenciones"]["nodo"])
    chk("D4 · cada aspecto dice si es cerrado (≤ 4°)", True, all(("cerrado" in x) and (x["cerrado"] == (x["orbe"] <= 4.0)) for x in a["aspectos"]))
    chk("D4 · Quirón en tránsito usa orbe de lento (3°)", True,
        all(x["lento"] for x in E.transitos(dict(fecha="1990-03-14", hora="09:45", lat=-32.9442, lon=-60.6505,
                                                 tz="America/Argentina/Cordoba"), "2026-11-22")["transitos"] if x["transito"] == "Quirón"))
    chk("D5 · la Lilith osculante se publica como referencia", True, bool(a.get("lilith_osculante")))
    b = E.bazi("1948-07-01", "11:46", "America/Argentina/Buenos_Aires", -58.3816)
    chk("D7 · Fuego fuerte: el útil ya no es Madera (su propio recurso)", True, b["dm_fuerte"] and b["elemento_util"] not in ("Madera", "Fuego"))
    c = E.calcular(dict(fecha="1990-03-14", hora="09:45", lat=-32.9442, lon=-60.6505))
    chk("D10 · en el sur se declara la escuela clásica", True, any("dos hemisferios" in x for x in c["avisos"]))
    c = E.calcular(dict(fecha="1940-01-01", hora="10:00", lat=-34.6, lon=-58.4, tz="America/Argentina/Buenos_Aires"))
    o = c["num"]["observaciones"][0]
    chk("D11 · la observación de deuda 16 trae el veredicto del calendario chino", (16, False, False),
        (o["valor"], o["bazi"]["corrobora"], o["entra_al_cuerpo"]))
    b = dict(dia_maestro={"elemento": "Fuego", "descripcion": "Fuego Yang"}, dm_fuerte=True,
             balance_ponderado={"Madera": 1.0, "Fuego": 4.0, "Tierra": 1.0, "Metal": 1.0, "Agua": 1.0})
    chk("D11 · tabla: 16 se confirma con Día Maestro fuerte y su elemento como el más pesado", True, E.corrobora_bazi(16, b)["corrobora"])
    chk("D11 · tabla: 14 se confirma con un elemento por encima del 35 %", True, E.corrobora_bazi(14, b)["corrobora"])
    chk("D11 · tabla: 13 no se confirma con Día Maestro fuerte", False, E.corrobora_bazi(13, b)["corrobora"])


def correr_referencia_privada(chk, titulo, E):
    """Carta de referencia externa (Meridian Pro Gold, de una astróloga), privada: vive en
    C:\\ElBrujo\\secretos\\referencias y no se imprime ningún dato. Si no está (servidor), se saltea."""
    import json, os, re
    titulo("28 · v9.0 — REFERENCIA EXTERNA PRIVADA (carta de Meridian Pro Gold)")
    ruta = r"C:\ElBrujo\secretos\referencias\referencia_externa_1.json"
    if not os.path.exists(ruta):
        print("  [SALTEA] no está la referencia privada en esta máquina")
        return
    R = json.load(open(ruta, encoding="utf-8"))
    SIG = ["Aries", "Tauro", "Géminis", "Cáncer", "Leo", "Virgo", "Libra", "Escorpio", "Sagitario", "Capricornio", "Acuario", "Piscis"]
    def grados(txt):
        m = re.match(r"(\d+)°(\d+)' (\S+)", txt)
        return SIG.index(m.group(3)) * 30 + int(m.group(1)) + int(m.group(2)) / 60
    d = R["datos"]
    def coord(txt):          # «S 34°55'» → −34,9167
        m = re.match(r"([NSEW]) (\d+)°(\d+)'", txt)
        v = int(m.group(2)) + int(m.group(3)) / 60
        return -v if m.group(1) in "SW" else v
    lat, lon = coord(d["lat"]), coord(d["lon"])
    a = E.astro(d["fecha"], d["hora"], lat, lon, "America/Argentina/Buenos_Aires")
    pares = {"Sol": "Sol", "Luna": "Luna", "Mercurio": "Mercurio", "Venus": "Venus", "Marte": "Marte",
             "Júpiter": "Júpiter", "Saturno": "Saturno", "Urano": "Urano", "Neptuno": "Neptuno",
             "Plutón": "Plutón", "Nodo N verdadero": "Nodo N", "Quirón": "Quirón"}
    peor = 0.0
    for k_ref, k_mot in pares.items():
        dif = abs(((a["pos"][k_mot]["grados"] - grados(R["pos"][k_ref])) + 180) % 360 - 180) * 60
        peor = max(peor, dif)
    chk("referencia · los 12 cuerpos coinciden con Meridian a menos de 1,5'", True, peor < 1.5)
    chk("referencia · Ascendente y Medio Cielo a menos de 1,5'", True,
        abs(((a["asc_deg"] - grados(R["cuspides_placidus"][0])) + 180) % 360 - 180) * 60 < 1.5 and
        abs(((a["mc_deg"] - grados(R["cuspides_placidus"][9])) + 180) % 360 - 180) * 60 < 1.5)
    chk("referencia · Parte de la Fortuna a menos de 1,5'", True,
        abs(((a["fortuna"]["grados"] - grados(R["pos"]["Fortuna"])) + 180) % 360 - 180) * 60 < 1.5)
    chk("referencia · Lilith osculante de referencia a menos de 1,5'", True,
        abs(((grados(a["lilith_osculante"]) - grados(R["pos"]["Lilith (osculante)"].replace(" R", ""))) + 180) % 360 - 180) * 60 < 1.5)

def correr_cielo(chk, titulo, E):
    titulo("29 · v9.1 — EL CIELO DE TODOS (calendario, aspectos, cielo de la web)")
    from datetime import datetime as _dt
    jd0 = E.jd_desde_local(_dt(2026, 11, 2)); jd1 = E.jd_desde_local(_dt(2028, 1, 1))
    lun = E.lunaciones_jd(jd0, jd1)
    chk("cielo · 29 lunaciones del 2/11/2026 al 31/12/2027 (igual al calendario v1)", 29, len(lun))
    ll = [r for r, n in lun if n == "llena"][0]
    chk("cielo · luna llena del 24/11: 11:53:34 exacta, 11:54 redondeada (decisión del 22/11)",
        ("11:53:34", "11:54"), (E.hora_exacta(ll).strftime("%H:%M:%S"), E.hora_minuto(ll).strftime("%H:%M")))
    ing, est = E.ingresos_y_estaciones(jd0, jd1)
    chk("cielo · 59 cambios de signo (54 ingresos + 5 solsticios y equinoccios) y 24 estaciones, igual al calendario v1", (59, 24), (len(ing), len(est)))
    m13 = [e for e in est if e[1] == "Mercurio"][0]
    chk("cielo · Mercurio directo el 13/11/2026 a las 12:54", ("Mercurio", "directo", "2026-11-13 12:54"),
        (m13[1], m13[2], E.hora_minuto(m13[0]).strftime("%Y-%m-%d %H:%M")))
    asp = E.aspectos_exactos(E.jd_desde_local(_dt(2026, 11, 14)), E.jd_desde_local(_dt(2026, 11, 17)))
    mj = [x for x in asp if (x["a"], x["b"], x["asp"]) == ("Marte", "Júpiter", "Conjunción")][0]
    chk("cielo · conjunción Marte–Júpiter 16/11/2026 03:23:39 (igual a la pestaña Aspectos)",
        ("03:23:39", "Media", "25°53' de Leo"), (E.hora_exacta(mj["jd"]).strftime("%H:%M:%S"), mj["peso"], E.fmt_de(mj["lona"])))
    lichun = [r for r, lon, i in E.terminos_solares(E.jd_desde_local(_dt(2027, 1, 1)), E.jd_desde_local(_dt(2027, 3, 1))) if round(lon) == 315][0]
    chk("cielo · Lichun 2027: miércoles 3/2 a las 22:46 hora argentina", "2027-02-03 22:46", E.hora_minuto(lichun).strftime("%Y-%m-%d %H:%M"))
    ap = E.apsides_tierra(E.jd_desde_local(_dt(2026, 12, 25)), E.jd_desde_local(_dt(2027, 1, 10)))
    chk("cielo · perihelio en los primeros días de enero de 2027", ("perihelio", 1), (ap[0][1], E.hora_minuto(ap[0][0]).month))
    chk("cielo · fase de la Luna: luna llena el 24/11/2026 al mediodía", "luna llena", E.fase_luna(E.jd_desde_local(_dt(2026, 11, 24, 12)))["fase"])
    act = E.aspectos_activos(E.jd_desde_local(_dt(2026, 11, 16, 12)))
    chk("cielo · aspecto activo Marte–Júpiter el 16/11 con su exacto (cielo de la web)", True,
        any(x["a"] == "Marte" and x["b"] == "Júpiter" and x["jd_exacto"] for x in act))
    chk("cielo · grados truncados en el texto (fmt_de)", "29°59' de Aries", E.fmt_de(29.9959))
