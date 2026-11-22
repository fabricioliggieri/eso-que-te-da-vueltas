# -*- coding: utf-8 -*-
"""
generar_llano.py · El Brujo v8.9 — generador único en registro llano (anexo: convención de hora Bazi y backend de efemérides).
=====================================================================
Tres lecturas sobre una misma base (CSS, tapa, rueda, anexo, render, textos fijos):

  generar('integral', datos, L, salida)                      Lectura Integral (v8.6 + adenda 8.6.1)
  generar('anio',     datos, L, salida, anio_rs=2026,
                      lugar_rs={...} | None)                  El año contado (Revolución Solar como cuento)
  generar('mes',      datos, L, salida, anio=2026, mes=11)   Lectura del mes

El motor hace TODO el cálculo (elbrujo_calculo v8.7). El generador no calcula nada:
sólo da forma. El texto interpretativo llega en `L`; los datos técnicos, en el
anexo, salen del motor y no se escriben a mano.

Contrato de `L` por lectura (claves obligatorias salvo que se diga lo contrario):

  comunes       consultante · datos_linea · fecha_entrega · anexo{helenistica, metodo}
                si_no{afirmo, desmentiria, otra, por_que, cuando, arbitra?}
                preguntas{marco, q1, q2, q3, fuentes}      (en anio y mes es opcional:
                                                            si falta, la sección no se imprime)
  integral      sabe · luz[{titulo, parrafos}] · figura_luz · llave_luz
                nodos[{titulo, texto, fuente, manda, trabajado}] · nodos_declaracion?
                figura_sombra · llave_sombra · cierre
  anio          prologo · el_cielo · escenas[{num, titulo, fecha, parrafos}]
                moraleja · llave_luz
                nodos[{titulo, texto, fuente, manda, trabajado}] · nodos_declaracion?
                figura_sombra · llave_sombra · cierre
  mes           clima · fechas[{titulo, fecha, parrafos}] · lunas · advertencia · llave
                cierre

Los `parrafos` son listas; cada ítem es un str, o una tupla (texto, fuente) para que
la fuente salga al pie del párrafo en letra chica.
"""
from __future__ import annotations
import math, html
from elbrujo_calculo import (calcular, anio as calc_anio, mes as calc_mes,
                             lunaciones_mes as calc_lunaciones, retorno as calc_retorno,
                             proximo_anio as calc_proximo, sinastria_completa as calc_sinastria,
                             progresiones as calc_progresiones,
                             anio_personal as calc_anio_personal, decadas as calc_decadas,
                             ROMANO, SIGNOS, QUIRON_DISPONIBLE, VERSION)

GL = {'Sol':'☉','Luna':'☽','Mercurio':'☿','Venus':'♀','Marte':'♂','Júpiter':'♃',
      'Saturno':'♄','Plutón':'♇','Nodo N':'☊','Urano':'♅','Neptuno':'♆','Lilith':'⚸','Quirón':'⚷'}
ORDEN = ['Sol','Luna','Mercurio','Venus','Marte','Júpiter','Saturno','Urano','Neptuno','Plutón','Nodo N','Lilith','Quirón']
NOMBRE_ES = {'Nodo N':'Nodo Norte','Nodo S':'Nodo Sur'}
MESES = ['', 'enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre']
QUE = {'Sol':'lo que sos cuando estás en tu centro','Luna':'cómo necesitás sentirte para estar bien',
       'Mercurio':'cómo pensás y hablás','Venus':'cómo querés y qué te atrae','Marte':'cómo actuás y cómo peleás',
       'Júpiter':'dónde crecés y confiás','Saturno':'dónde te exigís y dónde construís',
       'Urano':'lo que te hace distinto','Neptuno':'lo que te disuelve los bordes','Plutón':'dónde te transformás',
       'Nodo N':'hacia dónde vas','Nodo S':'de dónde venís','Lilith':'tu deseo que no se somete','Quirón':'tu herida que puede volverse don'}
QUE_ANIO = {'Sol':'dónde está el centro del año','Luna':'qué te sostiene este año',
            'Mercurio':'de qué se habla y se piensa este año','Venus':'qué se quiere y qué se disfruta este año',
            'Marte':'dónde se empuja este año','Júpiter':'dónde crece el año','Saturno':'dónde pesa el año',
            'Urano':'dónde se rompe algo','Neptuno':'dónde se desdibuja algo','Plutón':'dónde se transforma algo de fondo',
            'Nodo N':'hacia dónde empuja el año','Nodo S':'de dónde viene el año','Lilith':'lo que no se somete este año','Quirón':'dónde duele y se cura este año'}

def _f(dt):
    return f"{dt.day} de {MESES[dt.month]} de {dt.year}"
def _fh(dt):
    return f"{_f(dt)} · {dt.strftime('%H:%M')}"

# ============================================================ rueda
def rueda_svg(a, tam: int = 360):
    """Rueda de cualquier carta con casas: natal, revolución solar, etc. Acepta el
    dict `astro` o el resultado entero de calcular()."""
    if 'astro' in a: a = a['astro']
    if a['sin_hora'] or not a['cusp_deg']:
        return '<p class="nota" style="text-align:center">Sin hora de nacimiento no hay casas, y sin casas no hay rueda.</p>'
    asc, cusps = a['asc_deg'], a['cusp_deg']
    SA = ['Ari','Tau','Gém','Cán','Leo','Vir','Lib','Esc','Sag','Cap','Acu','Pis']
    CX = CY = 235.0; R_OUT=212.; R_ZOD=180.; R_HOUSE=150.; R_PL=165.; R_HN=60.
    CB='#b9ac90'; CF='#ddd3bf'; CST='#5f6e78'; CG='#33424c'; CD='#7a6f5b'; CHN='#9aa6ae'; CAX='#8a7c64'
    def XY(L, r):
        ang = math.radians(180. + (L - asc)); return (CX + r*math.cos(ang), CY - r*math.sin(ang))
    s = [f'<svg viewBox="0 0 470 470" width="{tam}" height="{tam}" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<circle cx="{CX}" cy="{CY}" r="{R_OUT}" fill="#fbf8f1" stroke="{CB}" stroke-width="1.4"/>')
    s.append(f'<circle cx="{CX}" cy="{CY}" r="{R_ZOD}" fill="none" stroke="{CB}" stroke-width="1"/>')
    s.append(f'<circle cx="{CX}" cy="{CY}" r="{R_HOUSE}" fill="none" stroke="{CF}" stroke-width="0.8"/>')
    s.append(f'<circle cx="{CX}" cy="{CY}" r="{R_HN-12}" fill="none" stroke="{CF}" stroke-width="0.6"/>')
    for sg in range(12):
        L = sg*30.; x1,y1 = XY(L, R_ZOD); x2,y2 = XY(L, R_OUT)
        s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{CB}" stroke-width="0.8"/>')
        xm,ym = XY(L+15, (R_ZOD+R_OUT)/2)
        s.append(f'<text x="{xm:.1f}" y="{ym+3:.1f}" font-family="Georgia,serif" font-size="11" fill="{CST}" text-anchor="middle">{SA[sg]}</text>')
    for dg in range(0, 360, 5):
        rr = R_ZOD - (6 if dg % 30 == 0 else 3); x1,y1 = XY(dg, R_ZOD); x2,y2 = XY(dg, rr)
        s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{CF}" stroke-width="0.6"/>')
    for i, c in enumerate(cusps):
        ax = i in (0,3,6,9); w = 1.5 if ax else 0.7; col = CAX if ax else CF
        x2,y2 = XY(c, R_HOUSE)
        s.append(f'<line x1="{CX}" y1="{CY}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}"/>')
        span = (cusps[(i+1) % 12] - c) % 360; xn,yn = XY((c + span/2) % 360, R_HN)
        s.append(f'<text x="{xn:.1f}" y="{yn+3:.1f}" font-family="Georgia,serif" font-size="9" fill="{CHN}" text-anchor="middle">{i+1}</text>')
    for L, lab in [(cusps[0],'ASC'),(cusps[9],'MC'),(cusps[6],'DSC'),(cusps[3],'IC')]:
        xl,yl = XY(L, R_OUT)
        s.append(f'<text x="{xl:.1f}" y="{yl-4:.1f}" font-family="Georgia,serif" font-size="8" fill="{CAX}" text-anchor="middle">{lab}</text>')
    items = [(n, a['pos'][n]['grados']) for n in ORDEN if n in a['pos']]
    items.sort(key=lambda t: t[1]); placed = []
    for n, L in items:
        bump = sum(1 for (Lp,_) in placed if abs(((L-Lp+180) % 360)-180) < 8)
        r = R_PL - bump*15; placed.append((L, r))
        gx,gy = XY(L, r)
        s.append(f'<text x="{gx:.1f}" y="{gy+4:.1f}" font-family="Georgia,serif" font-size="13" fill="{CG}" text-anchor="middle">{GL[n]}</text>')
        bx,by = XY(L, R_HOUSE); ex,ey = XY(L, R_HOUSE-4)
        s.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{CG}" stroke-width="0.7"/>')
        dx,dy = XY(L, r-13)
        s.append(f'<text x="{dx:.1f}" y="{dy+3:.1f}" font-family="Georgia,serif" font-size="6.5" fill="{CD}" text-anchor="middle">{int(L % 30)}°</text>')
    if a['fortuna']:
        fx,fy = XY(a['fortuna']['grados'], R_PL-30)
        s.append(f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="4.5" fill="none" stroke="{CAX}" stroke-width="1"/>')
        s.append(f'<line x1="{fx-4.5:.1f}" y1="{fy:.1f}" x2="{fx+4.5:.1f}" y2="{fy:.1f}" stroke="{CAX}" stroke-width="1"/>')
        s.append(f'<line x1="{fx:.1f}" y1="{fy-4.5:.1f}" x2="{fx:.1f}" y2="{fy+4.5:.1f}" stroke="{CAX}" stroke-width="1"/>')
    s.append('</svg>'); return '\n'.join(s)

# ============================================================ CSS
CSS = """
@page { size: A4; margin: 22mm 20mm 24mm 20mm; background: #fdfbf6;
  @bottom-left { content: "__PIE__"; font: 7.5pt Georgia, serif; color: #8a857b; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 7.5pt Georgia, serif; color: #8a857b; } }
@page :first { @bottom-left { content: none } @bottom-right { content: none } }
@page negra { background: #15171c; @bottom-left { content: none } @bottom-right { content: none } }
body { font-family: Georgia, serif; font-size: 10.5pt; line-height: 1.62; color: #2a2823; background: transparent; margin:0; }
p { text-align: justify; margin: 0 0 9pt 0; orphans:2; widows:2; }
h1, h2, h3 { color: #33424c; font-weight: bold; }
h2 { font-size: 14.5pt; margin: 22pt 0 8pt 0; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 16pt 0 5pt 0; page-break-after: avoid; }
.brujo { font-size: 9pt; letter-spacing: 3px; text-transform: uppercase; color: #5f6e78; }
.cover { text-align: center; padding-top: 70mm; page-break-after: always; }
.cover .title { font-size: 26pt; color: #33424c; font-weight: bold; margin: 10pt 0 2pt 0; }
.cover .sub { font-size: 12pt; color: #5f5346; font-style: italic; }
.cover .glifos { font-size: 16pt; color: #5f6e78; letter-spacing: 8px; margin: 18pt 0; }
.datos { display: inline-block; margin-top: 28pt; padding: 10pt 18pt; border: 1px solid #d2c8b6; background: #f4efe4; font-size: 10pt; text-align: left; line-height: 1.5; }
.ritual { margin-top: 36pt; font-size: 9.5pt; color: #5f5346; font-style: italic; }
.negra { page: negra; page-break-before: always; page-break-after: always; text-align: center; padding-top: 85mm; }
.negra .t { font-size: 24pt; color: #e6eaee; font-weight: bold; }
.negra .s { font-size: 11pt; color: #9aa0a8; font-style: italic; margin-top: 14pt; }
.pb { page-break-before: always; }
.fuente { display: block; text-align: right; font-size: 8pt; color: #8a857b; font-style: italic; margin: -5pt 0 10pt 0; }
.caja { background: #f1eadc; border: 1px solid #d9cfba; padding: 10pt 14pt; margin: 10pt 0 14pt 0; }
.caja p:last-child { margin-bottom: 0; }
.nodo { border-left: 3px solid #5f6e78; padding: 2pt 0 2pt 12pt; margin: 14pt 0; }
.nodo h3 { margin-top: 0; }
.marker { padding: 7pt 11pt; margin: 6pt 0; font-size: 10pt; page-break-inside: avoid; }
.m-shadow { background: #e9e4da; border-left: 3px solid #5f5346; }
.m-light { background: #eef0ea; border-left: 3px solid #6e7a66; }
.marker b { color: #211f1a; }
.diablo { background: #2a2c33; color: #dfe3e8; padding: 14pt 18pt; margin: 14pt 0; page-break-inside: avoid; }
.diablo h2 { color: #e6eaee; margin-top: 0; }
.diablo p { color: #dfe3e8; }
.diablo .q { margin: 10pt 0; padding-left: 8pt; border-left: 2px solid #8a93a0; }
.diablo .nota { color:#9aa0a8; }
.llave { text-align: center; font-style: italic; color: #5f5346; margin: 18pt 30pt; font-size: 11pt; }
.cierre { text-align: center; border-top: 1px solid #d2c8b6; padding-top: 14pt; margin-top: 24pt; font-style: italic; color: #5f5346; }
.rueda { text-align:center; margin: 4pt 0 0 0; }
.vistazo { font-size: 9pt; line-height:1.4; margin: 4pt 0 0 0; }
.vistazo td { padding: 2pt 8pt 2pt 0; vertical-align: top; }
.vistazo td:first-child { color:#33424c; font-weight:bold; white-space:nowrap; }
.escena { margin: 18pt 0 8pt 0; }
.escena .num { font-size: 8.5pt; letter-spacing: 2.5px; text-transform: uppercase; color: #7f8b94; font-weight: bold; }
.escena h3 { margin: 1pt 0 1pt 0; }
.escena .fecha { font-size: 9pt; color: #7a6f5b; font-style: italic; margin-bottom: 7pt; }
.semana { margin: 14pt 0 6pt 0; border-top: 1px solid #e0d8c8; padding-top: 8pt; }
.semana h3 { margin-top: 0; }
.semana .fecha { font-size: 9pt; color: #7a6f5b; font-style: italic; margin: -2pt 0 6pt 0; }
.anexo { font-size: 9pt; line-height: 1.5; color: #4a463f; }
.anexo h2 { font-size: 12pt; }
.anexo h3 { font-size: 10pt; margin-top: 12pt; }
.anexo table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0; }
.anexo td, .anexo th { border-bottom: 1px solid #e0d8c8; padding: 3pt 6pt; text-align: left; vertical-align: top; }
.anexo th { color: #33424c; font-weight: bold; }
.nota { font-size: 9pt; color: #5f5346; font-style: italic; }
"""

# ============================================================ textos fijos (adenda 8.6.1)
CIERRE_INTEGRAL = ("Esta lectura no te dice quién sos: te muestra con qué naciste. Todo lo que está en la "
    "parte de luz es tuyo y ya lo tenés. Todo lo que está en la parte de sombra es lo mismo, sin trabajar, "
    "y se trabaja. Nada de lo que leíste está cerrado: el cielo del día en que naciste no va a cambiar, y "
    "lo que hacés con él cambia todos los días. Que te sirva para elegir con más claridad, no para explicarte.")
# Mismo espíritu, adaptado al año y al mes (v8.7, a validar por Fabricio).
CIERRE_ANIO = ("Este cuento no te dice cómo va a ser tu año: te muestra con qué cielo arranca. Las escenas "
    "son ventanas, no citas; el capítulo en negro es lo mismo sin trabajar, y se trabaja. Cuando el año "
    "termine vas a saber cuál de los dos finales lo describió mejor, y esa respuesta es tuya, no del cielo. "
    "Que te sirva para elegir con más claridad, no para esperar.")
CIERRE_MES = ("Esta lectura no te dice qué va a pasar este mes: te muestra qué parte de tu vida toca el cielo "
    "y en qué fechas. Donde dice «puede», es puede. Lo que hagas con cada ventana es tuyo. Que te sirva para "
    "elegir el momento con más claridad, no para esperarlo.")
IRREDUCIBLE = ("Quien escribió esta lectura es también quien escribió su control. Hay dos cosas que reducen "
    "ese problema —una segunda lectura hecha a ciegas sobre los mismos datos, y la capacidad del consultante "
    "de desmentir lo que leyó, por el canal que acompaña a esta entrega— pero ninguna lo elimina.")
RITUAL = "🜍 El círculo se cierra. Los símbolos hablaron. Que tus pasos honren lo que el cielo reveló. 🜃"
NOTA_FUENTES = ("Cada párrafo lleva al pie, en letra chica, de dónde sale. No hace falta entenderlo para leer; "
    "está para que cualquiera pueda verificarlo. Al final hay un anexo con todos los datos técnicos, para quien quiera mirarlos.")

ANTES_INTEGRAL = """
<h2>Antes de leer</h2>
<p>Esta lectura cruza tres lenguajes que no tienen nada que ver entre sí: el cielo del momento en que naciste, los números de tu nombre y tu fecha, y el calendario chino. Cuando los tres dicen lo mismo sobre algo tuyo, eso me importa. Cuando dicen cosas distintas, te lo digo también, porque ahí es donde vos sabés más que yo.</p>
<p>Vas a leer dos partes. La primera es tu cielo <b>en luz</b>: lo que traés a favor. La segunda es el mismo cielo <b>en sombra</b>: qué es cada una de esas cosas cuando no se trabaja. No son dos personas distintas. Son dos lecturas de la misma, y ninguna de las dos sola te describe.</p>
<p>Al final hay dos secciones que no suelen estar en una lectura. Una se llama <i>Si esto no es así</i>, y dice qué tendría que pasar en tu vida para que yo esté equivocado. La otra son tres preguntas que no te van a gustar. Las dos existen por la misma razón: una lectura que solo te halaga no sirve para nada.</p>
"""
ANTES_ANIO = """
<h2>Cómo leer este cuento</h2>
<p>Cada cumpleaños, en el instante exacto en que el Sol vuelve al lugar donde estaba cuando naciste, se dibuja un cielo nuevo. Ese cielo dura un año. No reemplaza a tu carta de nacimiento: le pone la ropa de este año. Esta lectura lo cuenta como un cuento, en escenas con fecha, porque así se recuerda mejor que como una lista de posiciones.</p>
<p>Cada escena lleva al pie, en letra chica, de dónde sale. No hace falta entenderlo para leer. Después del cuento viene <b>el capítulo en negro</b>: las mismas escenas cuando no se trabajan. Y al final, <i>el otro final posible</i>: el mismo cielo leído al revés, para que vos decidas cuál de los dos describió mejor tu año cuando lo mires de atrás.</p>
"""
ANTES_MES = """
<h2>Cómo leer esto</h2>
<p>Tu carta de nacimiento no cambia. Lo que cambia es el cielo que pasa por encima de ella. Cuando un planeta pasa justo sobre un punto de tu carta, esa parte de tu vida se activa: se vuelve más sensible, más visible, más urgente. Esta lectura es el calendario de esos contactos durante el mes, con las fechas en que son más fuertes.</p>
<p>Una regla para todo lo que sigue: los planetas lentos pesan más que los rápidos. El Sol y Mercurio pasan y se van en días; Plutón o Júpiter se quedan semanas sobre el mismo punto. Una sola influencia lenta vale más que diez rápidas. Y donde dice «puede», es puede: nada de esto es una sentencia.</p>
"""

# ============================================================ helpers
def _p(parrafos):
    out = []
    for item in parrafos or []:
        if isinstance(item, tuple):
            t, f = item
            out.append(f"<p>{t}</p>" + (f'<span class="fuente">{f}</span>' if f else ""))
        else:
            out.append(f"<p>{item}</p>")
    return "\n".join(out)

def _vistazo(a, que=QUE, titulo_casa='zona'):
    """Qué hay en la rueda, en una línea por cuerpo, sin jerga."""
    if 'astro' in a: a = a['astro']
    p = a['pos']; rows = []
    if a['asc']:
        rows.append(f"<tr><td>Ascendente</td><td>{a['asc'].split(' ',1)[1]} — cómo salís al mundo, lo primero que ven de vos</td></tr>")
    for n in ORDEN + ['Nodo S']:
        if n not in p: continue
        i = p[n]; signo = i['fmt'].split(' ',1)[1]
        casa = f", en la {titulo_casa} {ROMANO[i['casa']-1]}" if i.get('casa') else ""
        rows.append(f"<tr><td>{NOMBRE_ES.get(n,n)}</td><td>{signo}{casa} — {que[n]}</td></tr>")
    return '<table class="vistazo">' + "".join(rows) + '</table>'

def _tabla_carta(a):
    """Tabla técnica de una carta con casas (natal o RS)."""
    p = a['pos']; filas = ""
    if a['asc']: filas += f"<tr><td>Ascendente</td><td>{a['asc']}</td><td>—</td><td></td></tr>"
    secta = a['secta']
    for k in ORDEN + ['Nodo S']:
        if k not in p: continue
        i = p[k]; nota = []
        if k in a['dignidades']: nota.append(a['dignidades'][k]['dignidad'])
        if secta and k in secta['de_secta']: nota.append('de secta')
        if secta and k in secta['fuera_secta']: nota.append('fuera de secta')
        filas += (f"<tr><td>{GL.get(k,'')} {NOMBRE_ES.get(k,k)}</td><td>{i['fmt']}{' R' if i['retro'] else ''}</td>"
                  f"<td>{ROMANO[i['casa']-1] if i.get('casa') else '—'}</td><td>{' · '.join(nota)}</td></tr>")
    if a['mc']: filas += f"<tr><td>Medio Cielo</td><td>{a['mc']}</td><td>—</td><td></td></tr>"
    if a.get('lilith_osculante'):
        filas += (f"<tr><td>Lilith osculante (referencia)</td><td>{a['lilith_osculante']}</td><td>—</td>"
                  f"<td>otra convención; la casa usa la media</td></tr>")
    if a['fortuna']: filas += f"<tr><td>Parte de la Fortuna</td><td>{a['fortuna']['fmt']}</td><td>{ROMANO[a['fortuna']['casa']-1]}</td><td></td></tr>"
    return f"<table><tr><th>Cuerpo</th><th>Posición</th><th>Casa</th><th>Dignidad / secta</th></tr>{filas}</table>"

def _tabla_aspectos(asp, tope=None):
    # v9.0 (D4): se publican TODOS los aspectos que el motor detecta (la lectura puede citar
    # cualquiera, y la fuente tiene que estar en el anexo); el orbe dice si es cerrado o amplio.
    return ("<table><tr><th>Planeta</th><th>Aspecto</th><th>Planeta</th><th>Orbe</th></tr>" +
            "".join(f"<tr><td>{x['a']}</td><td>{x['aspecto']}</td><td>{x['b']}</td><td>{x['orbe']:.2f}°"
                    f"{'' if x['orbe'] <= 4.0 else ' (amplio)'}</td></tr>"
                    for x in asp if tope is None or x['orbe'] <= tope) + "</table>")

def _deudas_txt(n):
    """v9.0 (E17): cada deuda con la posición de donde sale."""
    if n.get('deudas_por_posicion') is None:
        return "; ".join(f"{k} — {t}" for k, t in n['deudas_txt'].items()) or "ninguna"
    _art = {'día de nacimiento': 'del', 'Camino de Vida': 'del', 'Alma': 'del', 'Expresión': 'de la', 'Personalidad': 'de la'}
    return "; ".join(f"{x['deuda']} (sale {_art.get(x['posicion'], 'de')} {x['posicion']}: " + " → ".join(map(str, x['traza'])) + f") — {n['deudas_txt'][x['deuda']]}"
                     for x in n['deudas_por_posicion']) or "ninguna"

def _obs_num(n):
    """v9.0 (D1, E16): ecos ocultos fuera del núcleo y observaciones de otras formas de sumar el
    Camino. Van al anexo; al cuerpo, solo si las corrobora el calendario chino (3.bis.12)."""
    out = ""
    ecos = {k: v for k, v in (n.get('ecos') or {}).items() if k != 'Madurez'}
    if ecos:
        out += "<p>Ecos ocultos (un 11, 22 o 33 que aparece en el camino de la suma y matiza, sin el peso de un maestro): " + "; ".join(
            f"{k}: " + " → ".join(map(str, v['traza'])) for k, v in ecos.items()) + ".</p>"
    if n.get('observaciones'):
        out += ("<p>Observación sobre el Camino de Vida: la casa lo suma reduciendo día, mes y año por separado. "
                "Otras formas de la tradición dan: " + "; ".join(
                    f"{o['forma']} → " + " → ".join(map(str, o['traza'])) + f" ({'número maestro' if o['tipo'] == 'maestro' else 'deuda'} {o['valor']})"
                    + ((f" — el calendario chino lo confirma ({o['bazi']['dato']})" if o['bazi']['corrobora']
                        else f" — el calendario chino no lo confirma ({o['bazi']['dato']}), queda solo acá")
                       if o.get('bazi') else " — queda solo acá")
                    for o in n['observaciones']) + ". Regla de la casa: un dato así se nombra en la lectura solo si el calendario chino dice lo mismo.</p>")
    return out

def _bloque_num(ch):
    n = ch['num']; b = ch['bazi']; d = ch['da_yun']; dat = ch['datos']
    def v(k): return n[k] if n[k] is not None else '—'
    traza = " → ".join(str(x) for x in n['madurez_traza']) if n['madurez_traza'] else ''
    eco = f" (eco oculto del {n['madurez_eco']})" if n.get('madurez_eco') else ''
    deu = _deudas_txt(n)
    lec = ", ".join(str(x) for x in n['lecciones']) if n['lecciones'] else "ninguna"
    pin = " · ".join(f"P{x['n']} {x['valor']} ({x['desde']}–{x['hasta'] if x['hasta'] else '…'})" for x in n['pinaculos'])
    des = " · ".join(f"D{i+1} {x}" for i, x in enumerate(n['desafios']))
    yv = _obs_num(n)
    if n['y_vocal']:
        yv += "<p>Criterio de la Y: " + "; ".join(f"«{y['palabra']}» → {y['regla']} → {y['cuenta_como']}" for y in n['y_vocal']) + ".</p>"
    bal = "".join(f"<td>{b['balance'][e]}</td>" for e in ('Madera','Fuego','Tierra','Metal','Agua'))
    balp = "".join(f"<td>{b['balance_ponderado'][e]}</td>" for e in ('Madera','Fuego','Tierra','Metal','Agua'))
    ys = b['yong_shen_metodo']
    ys_txt = (f"Candidatos ({'controlar o drenar' if b['dm_fuerte'] else 'nutrir o reforzar'}): "
              f"{', '.join(e + ' ' + str(ys['pesos_candidatos'][e]) for e in ys['candidatos_finales'])}. "
              f"Elegido: <b>{b['elemento_util']}</b>, margen {ys['margen']}.")
    if ys['margen_estrecho']:
        ys_txt += (f" <b>Margen estrecho:</b> el útil es una indicación abierta entre "
                   f"{ys['candidatos_finales'][0]} y {ys['candidatos_finales'][1]}, no un veredicto.")
    if ys['excedente']:
        ys_txt += f" Excedente {ys['excedente']} ({ys['participacion_excedente']:.0%}); descartados por alimentarlo: {', '.join(ys['descartados_por_generar_exceso']) or 'ninguno'}."
    rel = []
    for x in b['relaciones']['liuhe']: rel.append(f"Liuhé {x[0]}–{x[1]}")
    for x in b['relaciones']['chong']: rel.append(f"Chong {x[0]}–{x[1]}")
    for x in b['relaciones']['sanhe']: rel.append(f"{x['tipo']} de {x['elemento']}: {', '.join(x['presentes'])}")
    rel = "; ".join(rel) or "sin relaciones mayores entre ramas"
    if d.get('disponible'):
        dy = (f"Dirección {d['direccion']}, inicio a los {d['edad_inicio']} años. " +
              " · ".join(f"{c['ganzhi']} ({c['animal']}) {c['desde']:.0f}–{c['hasta']:.0f}" for c in d['ciclos'][:7]) + ".")
    else:
        dy = d.get('motivo', 'no calculado')
    pil = (f"{b['pilar_anio']['ganzhi']} ({b['pilar_anio']['animal']}) · {b['pilar_mes']['ganzhi']} ({b['pilar_mes']['animal']}) · "
           f"<b>{b['pilar_dia']['ganzhi']}</b> ({b['pilar_dia']['animal']})" +
           (f" · {b['pilar_hora']['ganzhi']} ({b['pilar_hora']['animal']})" if b['pilar_hora'] else " · sin pilar de hora"))
    return f"""
<h3>Numerología pitagórica (escuela estricta)</h3>
<p>Nombre de nacimiento usado: {dat.get('nombre') or '—'}.</p>
<table>
<tr><th>Camino de Vida</th><th>Alma</th><th>Expresión</th><th>Personalidad</th><th>Madurez</th></tr>
<tr><td>{v('camino')}</td><td>{v('alma')}</td><td>{v('expresion')}</td><td>{v('personalidad')}</td><td>{v('madurez')} ({traza}){eco}</td></tr>
</table>
<p>Deudas kármicas: {deu}. Lecciones kármicas (números ausentes del nombre): {lec}.<br>Pináculos: {pin}. Desafíos: {des}.<br>Año Personal {n['anio_personal']} · Mes Personal {n['mes_personal']} (a la fecha de esta lectura).</p>
{yv}
"""

def _bloque_bazi(ch):
    n = ch['num']; b = ch['bazi']; d = ch['da_yun']; dat = ch['datos']
    def v(k): return n[k] if n[k] is not None else '—'
    traza = " → ".join(str(x) for x in n['madurez_traza']) if n['madurez_traza'] else ''
    eco = f" (eco oculto del {n['madurez_eco']})" if n.get('madurez_eco') else ''
    deu = _deudas_txt(n)
    lec = ", ".join(str(x) for x in n['lecciones']) if n['lecciones'] else "ninguna"
    pin = " · ".join(f"P{x['n']} {x['valor']} ({x['desde']}–{x['hasta'] if x['hasta'] else '…'})" for x in n['pinaculos'])
    des = " · ".join(f"D{i+1} {x}" for i, x in enumerate(n['desafios']))
    yv = _obs_num(n)
    if n['y_vocal']:
        yv += "<p>Criterio de la Y: " + "; ".join(f"«{y['palabra']}» → {y['regla']} → {y['cuenta_como']}" for y in n['y_vocal']) + ".</p>"
    bal = "".join(f"<td>{b['balance'][e]}</td>" for e in ('Madera','Fuego','Tierra','Metal','Agua'))
    balp = "".join(f"<td>{b['balance_ponderado'][e]}</td>" for e in ('Madera','Fuego','Tierra','Metal','Agua'))
    ys = b['yong_shen_metodo']
    ys_txt = (f"Candidatos ({'controlar o drenar' if b['dm_fuerte'] else 'nutrir o reforzar'}): "
              f"{', '.join(e + ' ' + str(ys['pesos_candidatos'][e]) for e in ys['candidatos_finales'])}. "
              f"Elegido: <b>{b['elemento_util']}</b>, margen {ys['margen']}.")
    if ys['margen_estrecho']:
        ys_txt += (f" <b>Margen estrecho:</b> el útil es una indicación abierta entre "
                   f"{ys['candidatos_finales'][0]} y {ys['candidatos_finales'][1]}, no un veredicto.")
    if ys['excedente']:
        ys_txt += f" Excedente {ys['excedente']} ({ys['participacion_excedente']:.0%}); descartados por alimentarlo: {', '.join(ys['descartados_por_generar_exceso']) or 'ninguno'}."
    rel = []
    for x in b['relaciones']['liuhe']: rel.append(f"Liuhé {x[0]}–{x[1]}")
    for x in b['relaciones']['chong']: rel.append(f"Chong {x[0]}–{x[1]}")
    for x in b['relaciones']['sanhe']: rel.append(f"{x['tipo']} de {x['elemento']}: {', '.join(x['presentes'])}")
    rel = "; ".join(rel) or "sin relaciones mayores entre ramas"
    if d.get('disponible'):
        dy = (f"Dirección {d['direccion']}, inicio a los {d['edad_inicio']} años. " +
              " · ".join(f"{c['ganzhi']} ({c['animal']}) {c['desde']:.0f}–{c['hasta']:.0f}" for c in d['ciclos'][:7]) + ".")
    else:
        dy = d.get('motivo', 'no calculado')
    pil = (f"{b['pilar_anio']['ganzhi']} ({b['pilar_anio']['animal']}) · {b['pilar_mes']['ganzhi']} ({b['pilar_mes']['animal']}) · "
           f"<b>{b['pilar_dia']['ganzhi']}</b> ({b['pilar_dia']['animal']})" +
           (f" · {b['pilar_hora']['ganzhi']} ({b['pilar_hora']['animal']})" if b['pilar_hora'] else " · sin pilar de hora"))
    return f"""
<h3>Bazi (Cuatro Pilares)</h3>
<p>Pilares: {pil}. Año Bazi desde Lichun; escuela early-zi para la hora Zi. {_hora_pilar_txt(b)}</p>
<table><tr><th></th><th>Madera</th><th>Fuego</th><th>Tierra</th><th>Metal</th><th>Agua</th></tr>
<tr><td>Balance descriptivo (cuenta plana)</td>{bal}</tr>
<tr><td>Balance ponderado (año 0.8 · mes 2.0 · día 1.2 · hora 1.0)</td>{balp}</tr></table>
<p><b>Día Maestro {b['dia_maestro']['tronco']}</b> ({b['dia_maestro']['descripcion']}). Rama de mes: {b['elemento_mes']}; el Día Maestro {'está' if b['en_estacion'] else 'no está'} en estación, umbral {b['umbral_fuerza']}. Fuerza medida {b['fuerza_dm']} → <b>{'fuerte' if b['dm_fuerte'] else 'débil'}</b>.</p>
<p><b>Elemento útil (yong shen):</b> {ys_txt}</p>
<p>Relaciones entre ramas: {rel}.</p>
<p><b>Da Yun:</b> {dy}</p>"""

def _hora_pilar_txt(b):
    """v8.9: declara sobre qué hora se calcularon día y hora (3.ter, decisión 28/10/2026)."""
    hp = b.get('hora_pilar')
    if not hp:
        return "Sin hora de nacimiento: sin pilar de hora."
    if hp['convencion'].startswith('hora solar'):
        txt = (f"Pilar de hora y giro de día sobre la <b>hora solar local aparente</b>: reloj {hp['hora_reloj']} "
               f"→ solar {hp['hora_solar']} (longitud {hp['correccion_longitud_min']:+.0f} min, ecuación del tiempo "
               f"{hp['ecuacion_tiempo_min']:+.0f} min{', horario de verano incluido' if hp.get('dst_activo') else ''}).")
        if hp.get('cambia_hora') or hp.get('cambia_dia'):
            txt += f" Por hora de reloj habrían salido día {hp['pilar_dia_por_reloj']} y hora {hp['pilar_hora_por_reloj']}."
        return txt
    return f"Pilar de hora sobre la hora de reloj ({hp['hora_reloj']}); {hp.get('motivo', 'convención reloj')}."

def _bloque_num_bazi(ch):
    return _bloque_num(ch) + _bloque_bazi(ch)

def _linea_natal(ch):
    a = ch['astro']; dat = ch['datos']
    return (f"{dat['fecha']} · {dat.get('hora') or 'sin hora'} ({dat['tz']}) · {dat['lugar']} ({dat['lat']:.4f}, {dat['lon']:.4f}) · "
            f"zodíaco tropical · casas {a['sistema_casas'] or 'no calculadas'} · carta {a['secta']['tipo'] if a['secta'] else '—'} · "
            f"Luna Negra media · Quirón {'incluido' if 'Quirón' in a['pos'] else 'no incluido'} · efemérides {ch.get('efemerides') or a.get('efemerides') or 'Swiss Ephemeris'} · motor v{VERSION}.")

def _anexo_abre():
    return ('<div class="pb anexo"><h2>Anexo técnico</h2>'
            '<p class="nota">Esta parte no hace falta para entender la lectura. Está para que cualquier persona que sepa de estas '
            'tradiciones pueda verificar de dónde sale cada afirmación. Si no te interesa, no la leas.</p>')

def _anexo_cierra(L, avisos):
    av = "".join(f"<li>{x}</li>" for x in avisos)
    return (f"<h3>Límites declarados</h3><ul>{av}</ul>"
            f"<h3>Contraste helenístico</h3><p>{L['anexo']['helenistica']}</p>"
            f"<h3>Método</h3><p>{L['anexo']['metodo']}</p>"
            f"<h3>Lo que queda irreducible</h3><p>{IRREDUCIBLE}</p></div>")

def _si_no(sn, titulo="Si esto no es así", intro="Una lectura que no puede estar equivocada no vale nada. Esta puede. Acá va cómo."):
    return f"""
<h2>{titulo}</h2>
<p>{intro}</p>
<div class="caja">
<p><b>Lo que afirmo.</b> {sn['afirmo']}</p>
<p><b>Lo que la desmentiría.</b> {sn['desmentiria']}</p>
<p><b>La otra lectura posible.</b> {sn['otra']}</p>
<p><b>Por qué {('elijo' if sn.get('arbitra') else 'no elijo entre las dos')}.</b> {sn['por_que']}</p>
<p><b>Cuándo revisarla.</b> {sn['cuando']}</p>
</div>"""

def _preguntas(q):
    if not q: return ""
    return f"""
<div class="diablo"><h2>Tres preguntas que no te van a gustar</h2>
<p>{q['marco']}</p>
<div class="q"><p><b>1.</b> {q['q1']}</p></div>
<div class="q"><p><b>2.</b> {q['q2']}</p></div>
<div class="q"><p><b>3.</b> {q['q3']}</p></div>
<p class="nota">{q['fuentes']}</p></div>"""

def _nodos(nodos):
    out = ""
    for i, nd in enumerate(nodos):
        out += (f'<div class="nodo"><h3>{i+1}. {nd["titulo"]}</h3><p>{nd["texto"]}</p>'
                f'<span class="fuente">{nd["fuente"]}</span>'
                f'<div class="marker m-shadow"><b>Cuando manda:</b> {nd["manda"]}</div>'
                f'<div class="marker m-light"><b>Cuando está trabajado:</b> {nd["trabajado"]}</div></div>')
    return out

def _tapa(L, titulo, sub, datos_extra=""):
    return f"""<div class="cover">
  <div class="brujo">El Brujo</div>
  <div class="glifos">🜂 🜃 🜁 🜄</div>
  <div class="title">{titulo}</div>
  <div class="sub">{sub}</div>
  <div class="datos"><b>{L['consultante']}</b><br>{L['datos_linea']}{datos_extra}<br>Lectura entregada el {L['fecha_entrega']}</div>
  <div class="ritual">Tres tradiciones, un mismo cielo.<br>Lo que sigue no es un veredicto sobre vos: es un mapa. El camino lo elegís vos.</div>
</div>"""

def _doc(L, pie, titulo, cuerpo):
    css = CSS.replace('__PIE__', html.escape(f"{pie} · {L['consultante']}"))
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>El Brujo — {titulo} — '
            f'{html.escape(L["consultante"])}</title><style>{css}</style></head><body>{cuerpo}</body></html>')

# ============================================================ 1 · LECTURA INTEGRAL
def plantilla_integral(L, ch):
    secs = "".join(f"<h3>{s['titulo']}</h3>" + _p(s['parrafos']) for s in L['luz'])
    cuantos = {1:'uno', 2:'dos', 3:'tres'}[len(L['nodos'])]
    decl = L.get('nodos_declaracion', '')
    cuerpo = f"""
{_tapa(L, 'Lectura Integral', 'Tu cielo, en luz y en sombra')}
{ANTES_INTEGRAL}
<div class="caja">{_p(L['sabe'])}</div>
<p class="nota">{NOTA_FUENTES}</p>

<h2 class="pb">Tu cielo, dibujado</h2>
<p>Esta es la foto del cielo del momento exacto en que naciste, vista desde el lugar donde naciste. No es decorativa: es tu carta. Todo lo que sigue sale de acá.</p>
<div class="rueda">{rueda_svg(ch)}</div>
<p class="nota" style="text-align:center">Los doce sectores numerados son las zonas de tu vida (la 1 es vos, la 7 la pareja, la 10 el trabajo público, y así). Los símbolos son los planetas. Dónde cae cada uno es lo que se lee.</p>
{_vistazo(ch)}

<h2 class="pb">Parte I — Lo que traés a favor</h2>
{secs}
<h3>La figura de tu carta</h3>
{_p(L['figura_luz'])}
<div class="llave">✧ {L['llave_luz']}</div>

<div class="negra"><div class="t">Parte II — La sombra</div>
<div class="s">Leíste tu cielo en luz. Lo que sigue es el mismo cielo en su cara oculta.<br>No es un veredicto: es lo que cada don es cuando no se trabaja.<br>Se lee después de la luz, nunca en su lugar.</div></div>

<h2>Parte II — Lo mismo, cuando no se trabaja</h2>
<p>Acá no voy planeta por planeta. Busqué los lugares donde las tres tradiciones —el cielo, los números y el calendario chino— señalan la misma herida. Cuando una sola lo dice, puede ser casualidad o puede ser mi sesgo. Cuando lo dicen las tres, hay que mirarlo.</p>
<p>Encontré {cuantos}.{(' ' + decl) if decl else ''} Cada uno viene con dos señales: cómo se ve cuando manda, y cómo se ve cuando lo tenés trabajado. <b>La diferencia entre esas dos señales es lo que te llevás de esta lectura.</b> Son conductas, no sentimientos: cosas que podés verificar en tu propia semana.</p>
{_nodos(L['nodos'])}
<h3>La figura de la sombra</h3>
{_p(L['figura_sombra'])}
<div class="llave">✧ {L['llave_sombra']}</div>
{_si_no(L['si_no'])}
{_preguntas(L['preguntas'])}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_INTEGRAL}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(ch)}</p>
{_tabla_carta(ch['astro'])}
<h3>Aspectos mayores (orbes: Sol y Luna 8°, Mercurio a Saturno 6°, el resto 4° o menos; «amplio» si pasa de 4°)</h3>{_tabla_aspectos(ch['astro']['aspectos'])}
{_bloque_num_bazi(ch)}
{_anexo_cierra(L, ch['avisos'])}"""
    return _doc(L, 'Lectura Integral', 'Lectura Integral', cuerpo)

# ============================================================ 2 · EL AÑO CONTADO
def _calendario_anio(Y):
    """Tabla de fechas calculadas: pasos exactos de lentos, estaciones, lunaciones sobre puntos natales."""
    filas = []
    for p in Y['pasos']:
        filas.append((p['jd'], p['fecha'], f"{p['cuerpo']} {p['aspecto'].lower()} exacto a {p['natal']} natal{' (retrógrado)' if p['retro'] else ''}"))
    for e in Y['estaciones']:
        if e['cuerpo'] in ('Mercurio',): continue
        filas.append((e['jd'], e['fecha'], f"{e['cuerpo']} estaciona {e['estacion']} a {e['fmt']}"))
    for l in Y['lunaciones']:
        filas.append((l['jd'], l['fecha'], f"{l['tipo']} a {l['fmt']}, casa natal {ROMANO[l['casa_natal']-1]}"))
    filas.sort()
    return ("<table><tr><th>Fecha</th><th>Evento</th></tr>" +
            "".join(f"<tr><td>{f}</td><td>{t}</td></tr>" for _, f, t in filas) + "</table>")

def plantilla_anio(L, Y):
    nat, rs = Y['natal'], Y['rs']
    esc = ""
    for e in L['escenas']:
        esc += (f'<div class="escena"><div class="num">{e["num"]}</div><h3>{e["titulo"]}</h3>'
                f'<div class="fecha">{e["fecha"]}</div>{_p(e["parrafos"])}</div>')
    cuantos = {1:'uno', 2:'dos', 3:'tres'}[len(L['nodos'])]
    decl = L.get('nodos_declaracion', '')
    from datetime import timedelta as _td
    vig = f"del {_f(rs['local'])} al {_f(rs['local'].replace(year=rs['local'].year+1) - _td(days=1))}"
    extra = f"<br>Retorno solar: {_fh(rs['local'])} · {rs['lugar']}<br>Vigencia: {vig}"
    cruz = [x for x in Y['cruz'] if x['orbe'] <= 3.0 and x['a'] != 'Sol'][:18]
    cruz_t = ("<table><tr><th>Cuerpo del año</th><th>Aspecto</th><th>Punto natal</th><th>Orbe</th></tr>" +
              "".join(f"<tr><td>{x['a']}</td><td>{x['aspecto']}</td><td>{x['b']}</td><td>{x['orbe']:.2f}°</td></tr>" for x in cruz) + "</table>")
    casas = ", ".join(f"{k} en {ROMANO[c-1]}" for k, c in Y['casas_natales_rs'].items() if k in ORDEN)
    hitos = "; ".join(f"{h['etiqueta']} (orbe {h['orbe']}°)" for h in Y['hitos']) or "ninguno en orbe al inicio del año"
    yb = Y['anio_bazi']
    cuerpo = f"""
{_tapa(L, 'El año contado', f"Tu Revolución Solar {rs['anio']}–{rs['anio']+1} · un cuento con su cielo al margen", extra)}
{ANTES_ANIO}
{_p(L['prologo'])}
<h2 class="pb">El cielo del cuento</h2>
<p>Esta es la rueda del año: el cielo del instante exacto en que el Sol volvió a tu grado de nacimiento, el {_fh(rs['local'])}, visto desde {rs['lugar']}. Es la casa prestada donde transcurre el cuento.</p>
<div class="rueda">{rueda_svg(rs, 340)}</div>
{_vistazo(rs, QUE_ANIO)}
{_p(L['el_cielo'])}
<h2 class="pb">El cuento</h2>
{esc}
<h2>La moraleja, si la hay</h2>
{_p(L['moraleja'])}
<div class="llave">✧ Llave del año: {L['llave_luz']}</div>

<div class="negra"><div class="t">El capítulo en negro</div>
<div class="s">Leíste tu año en luz. Lo que sigue es el mismo cuento, contado al revés.<br>No es un veredicto: es lo que cada escena es cuando no se trabaja.<br>Se lee después de la luz, nunca en su lugar.</div></div>

<h2>El capítulo en negro</h2>
<p>Busqué los lugares donde el cielo del año, el número del año y el elemento del año señalan la misma herida. Encontré {cuantos}.{(' ' + decl) if decl else ''} Cada uno viene con dos señales: cómo se ve cuando manda, y cómo se ve cuando está trabajado. Son conductas, no sentimientos: cosas que podés verificar en tu propia semana.</p>
{_nodos(L['nodos'])}
<h3>La figura en negro</h3>
{_p(L['figura_sombra'])}
<div class="llave">✧ Llave en negro: {L['llave_sombra']}</div>
{_si_no(L['si_no'], 'El otro final posible', 'Un cuento con un solo final posible no es una lectura: es una sentencia. Este tiene dos.')}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_ANIO}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(nat)}</p>
{_tabla_carta(nat['astro'])}
<h3>Revolución Solar {rs['anio']}</h3>
<p>Instante del retorno: {rs['utc'].strftime('%d/%m/%Y %H:%M')} UTC ({rs['local'].strftime('%H:%M')} hora local) · levantada en {rs['lugar']} ({rs['lat']:.4f}, {rs['lon']:.4f}) · Sol a {nat['astro']['pos']['Sol']['fmt']}, residuo {abs(rs['residuo_deg']):.1e}° · casas {rs['sistema_casas']} · carta {rs['secta']['tipo']}.</p>
{_tabla_carta(rs)}
<p>Casa natal de cada cuerpo del año: {casas}.</p>
<h3>Aspectos mayores de la carta del año (mismos orbes que la natal; «amplio» si pasa de 4°)</h3>{_tabla_aspectos(rs['aspectos'])}
<h3>Cuerpos del año sobre puntos natales (orbe ≤ 3°)</h3>{cruz_t}
<p>Hitos de ciclo: {hitos}.</p>
<h3>Calendario calculado del año</h3>
<p>Pasos exactos de los planetas lentos sobre puntos natales, estaciones (sin Mercurio) y lunaciones con su casa natal. Son ventanas, no citas.</p>
{_calendario_anio(Y)}
<h3>Número y elemento del año</h3>
<p>Año Personal <b>{Y['num']['anio_personal']}</b> (vigente desde el cumpleaños) · Camino de Vida {Y['num']['camino']}. Año Bazi en curso: <b>{yb['ganzhi']}</b> ({yb['animal']} de {yb['elemento_tronco']} {yb['polaridad']}), desde Lichun.</p>
{_bloque_num_bazi(nat)}
{_anexo_cierra(L, Y['avisos'])}"""
    return _doc(L, f"El año contado {rs['anio']}–{rs['anio']+1}", 'El año contado', cuerpo)

# ============================================================ 3 · LECTURA DEL MES
def _anexo_mes(M):
    out = ""
    for f, t in M['muestras'].items():
        filas = "".join(f"<tr><td>{x['transito']}{' R' if x['retro'] else ''} {x['pos']}</td><td>{x['aspecto']}</td><td>{x['natal']}</td>"
                        f"<td>{x['orbe']:.2f}°</td><td>{ROMANO[x['casa_natal']-1] if x['casa_natal'] else '—'}</td></tr>"
                        for x in t['transitos'] if x['transito'] != 'Luna')
        hit = "; ".join(h['etiqueta'] for h in t['hitos'])
        out += (f"<p><b>{f}</b>{(' · hitos: ' + hit) if hit else ''}</p>"
                f"<table><tr><th>En tránsito</th><th>Aspecto</th><th>Punto natal</th><th>Orbe</th><th>Casa natal</th></tr>{filas}</table>")
    lun = "".join(f"<tr><td>{l['fecha']} {l['hora']}</td><td>{l['tipo']}</td><td>{l['fmt']}</td><td>{ROMANO[l['casa_natal']-1] if l['casa_natal'] else '—'}</td></tr>" for l in M['lunaciones'])
    est = "".join(f"<tr><td>{e['fecha']}</td><td>{e['cuerpo']}</td><td>{e['estacion']}</td><td>{e['fmt']}</td></tr>" for e in M['estaciones'])
    pas = "".join(f"<tr><td>{p['fecha']}</td><td>{p['cuerpo']}{' R' if p['retro'] else ''}</td><td>{p['aspecto']}</td><td>{p['natal']}</td></tr>" for p in M['pasos'] if p['cuerpo'] not in ('Sol',))
    return f"""
<h3>Tránsitos sobre puntos natales, en cinco fechas del mes</h3>
<p>Lentos con orbe ≤ 3°, rápidos ≤ 2°; la Luna no se lista. Posiciones al mediodía local.</p>
{out}
<h3>Lunaciones del mes</h3><table><tr><th>Fecha</th><th></th><th>Grado</th><th>Casa natal</th></tr>{lun}</table>
<h3>Estaciones del mes</h3>{('<table><tr><th>Fecha</th><th>Planeta</th><th>Estación</th><th>Grado</th></tr>' + est + '</table>') if est else '<p>Ningún planeta estaciona este mes.</p>'}
<h3>Pasos exactos dentro del mes (sin Sol ni Luna)</h3><table><tr><th>Fecha</th><th>En tránsito</th><th>Aspecto</th><th>Punto natal</th></tr>{pas}</table>
<h3>Número y elemento del mes</h3>
<p>Año Personal <b>{M['anio_personal']}</b> · Mes Personal <b>{M['mes_personal']}</b>. Pilar de año Bazi {M['bazi_mes']['pilar_anio']['ganzhi']} ({M['bazi_mes']['pilar_anio']['animal']}) · pilar de mes <b>{M['bazi_mes']['pilar_mes']['ganzhi']}</b> ({M['bazi_mes']['pilar_mes']['animal']}, {M['bazi_mes']['pilar_mes']['elemento_tronco']} {M['bazi_mes']['pilar_mes']['polaridad']}), al 15 del mes.</p>"""

def plantilla_mes(L, M):
    nat = M['natal']; mes_nombre = f"{MESES[M['mes']]} de {M['anio']}"
    fechas = ""
    for b in L['fechas']:
        fechas += (f'<div class="semana"><h3>{b["titulo"]}</h3><div class="fecha">{b["fecha"]}</div>{_p(b["parrafos"])}</div>')
    cuerpo = f"""
{_tapa(L, 'Lectura del mes', f"{mes_nombre[0].upper() + mes_nombre[1:]} · el cielo que pasa sobre tu carta")}
{ANTES_MES}
<p class="nota">{NOTA_FUENTES}</p>
<h2>Tu carta, de referencia</h2>
<p>Todo lo que sigue se lee contra esta foto: el cielo del momento en que naciste. Las zonas numeradas son las áreas de tu vida; cuando un planeta de este mes pasa por una, esa área es la que se activa.</p>
<div class="rueda">{rueda_svg(nat, 300)}</div>
<h2 class="pb">El mes, en una mirada</h2>
{_p(L['clima'])}
<h2>Las fechas</h2>
{fechas}
<h2>Las lunas del mes</h2>
{_p(L['lunas'])}
<h2>Una advertencia</h2>
{_p(L['advertencia'])}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'], 'Si esto no es así', 'Una lectura de un mes es fácil de verificar: el mes pasa. Acá va cómo saber si esta estuvo bien.')}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_MES}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(nat)}</p>
{_tabla_carta(nat['astro'])}
{_anexo_mes(M)}
{_anexo_cierra(L, M['avisos'])}"""
    return _doc(L, f"Lectura del mes · {mes_nombre}", 'Lectura del mes', cuerpo)

# ============================================================ 4 · LUNACIONES
CIERRE_LUNACIONES = ("Dos lunas por mes, todos los meses: una para empezar algo y otra para ver qué dio. "
    "Esta lectura no te dice qué va a pasar: te dice qué parte de tu vida ilumina cada una. Lo que siembres y lo que cierres es tuyo.")
CIERRE_RETORNO = ("Un retorno no es una sentencia: es un examen que ya rendiste una vez sin saberlo, y que ahora rendís sabiendo. "
    "Lo que está en estas páginas es el programa. Lo que hagas con él en los meses que vienen es tuyo, y es lo único que cuenta.")
CIERRE_PROXIMO = ("Doce meses son muchas ventanas. No hace falta recordarlas todas: con saber cuáles son las tres o cuatro que pesan, alcanza. "
    "Esta lectura no te dice cómo va a ser tu año: te dice cuándo mirar. Que te sirva para elegir el momento, no para esperarlo.")
CIERRE_SINASTRIA = ("Dos cartas no dicen si un vínculo va a funcionar: dicen dónde se encuentra fácil y dónde se traba. "
    "Lo que está en luz ya lo tienen. Lo que está en sombra es lo mismo sin trabajar, y se trabaja de a dos. Que les sirva para hablar de lo que cuesta nombrar, no para explicarse.")
CIERRE_PROGRESIONES = ("Lo que avanza en tu carta avanza despacio, y por eso no se nota hasta que ya cambió. Esta lectura te muestra en qué punto de ese movimiento estás. "
    "No es un pronóstico: es un clima. Que te sirva para entender por qué este año se siente distinto, no para esperar que pase.")

def _contactos_txt(l):
    return "; ".join("%s %s %.2f°" % (c['aspecto'], c['natal'], c['orbe']) for c in l.get('contactos', [])[:4]) or "—"

def _tabla_lunas(lun):
    filas = ""
    for l in lun:
        casa = ROMANO[l['casa_natal']-1] if l['casa_natal'] else '—'
        filas += "<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (l['fecha'], l['hora'], l['tipo'], l['fmt'], casa, _contactos_txt(l))
    return "<table><tr><th>Fecha</th><th></th><th>Grado</th><th>Casa natal</th><th>Contactos (orbe ≤ 3°)</th></tr>" + filas + "</table>"

def plantilla_lunaciones(L, M):
    nat = M['natal']; mes_nombre = f"{MESES[M['mes']]} de {M['anio']}"
    bloques = ""
    for l, b in zip(M['lunaciones'], L['lunas']):
        loc = l['local']
        bloques += (f'<div class="semana"><h3>{b["titulo"]}</h3><div class="fecha">{l["tipo"]} · {_fh(loc)} · zona {ROMANO[l["casa_natal"]-1] if l["casa_natal"] else "—"}</div>{_p(b["parrafos"])}</div>')
    cuerpo = f"""
{_tapa(L, 'Lunaciones', f"{mes_nombre[0].upper() + mes_nombre[1:]} · las dos lunas del mes sobre tu carta")}
<h2>Cómo leer esto</h2>
<p>Cada mes el cielo te da dos momentos: la luna nueva, para empezar algo, y la luna llena, para ver qué dio lo que empezaste. Dónde caen en tu carta dice qué parte de tu vida está en juego esa quincena. Es una lectura corta, para leer al principio del mes y volver a mirar en cada luna.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="rueda">{rueda_svg(nat, 280)}</div>
<h2>El mes, en una mirada</h2>
{_p(L['clima'])}
{bloques}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'], 'Si esto no es así', 'Una luna nueva se verifica en quince días. Acá va cómo saber si esta lectura estuvo bien.')}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_LUNACIONES}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(nat)}</p>
{_tabla_carta(nat['astro'])}
<h3>Lunaciones de {mes_nombre}</h3>{_tabla_lunas(M['lunaciones'])}
<p>Año Personal <b>{M['anio_personal']}</b> · Mes Personal <b>{M['mes_personal']}</b> · pilar de mes Bazi <b>{M['bazi_mes']['pilar_mes']['ganzhi']}</b> ({M['bazi_mes']['pilar_mes']['animal']}).</p>
{_anexo_cierra(L, M['avisos'])}"""
    return _doc(L, f"Lunaciones · {mes_nombre}", 'Lunaciones', cuerpo)

# ============================================================ 5 · RETORNO
def plantilla_retorno(L, R):
    nat = R['natal']; c = R['cuerpo']
    nombre = {'Saturno': 'Retorno de Saturno', 'Quirón': 'Retorno de Quirón', 'Júpiter': 'Retorno de Júpiter', 'Nodo N': 'Retorno nodal'}[c]
    fechas = ""
    for b in L['fechas']:
        fechas += (f'<div class="semana"><h3>{b["titulo"]}</h3><div class="fecha">{b["fecha"]}</div>{_p(b["parrafos"])}</div>')
    pases = ("<table><tr><th>Pase exacto</th><th>Edad</th><th>Movimiento</th></tr>" +
             "".join(f"<tr><td>{p['fecha']}</td><td>{p['edad']}</td><td>{'retrógrado' if p['retro'] else 'directo'}</td></tr>" for p in R['pases']) + "</table>") if R['pases'] else "<p>Ningún pase exacto dentro de la ventana calculada.</p>"
    asp = _tabla_aspectos(R['aspectos_natales'], 6.0)
    T1 = R['transitos_primer_pase']
    t1 = ("<table><tr><th>En tránsito</th><th>Aspecto</th><th>Punto natal</th><th>Orbe</th></tr>" +
          "".join(f"<tr><td>{x['transito']} {x['pos']}</td><td>{x['aspecto']}</td><td>{x['natal']}</td><td>{x['orbe']:.2f}°</td></tr>" for x in T1['transitos'] if x['transito'] != 'Luna') + "</table>") if T1 else ""
    dy = R['da_yun_activo']
    nod = ""
    if L.get('nodos'):
        nod = f"<h2>Lo que este umbral pone a prueba</h2>{_nodos(L['nodos'])}"
    cuerpo = f"""
{_tapa(L, nombre, 'Una lectura de umbral', f"<br>{'Primer' if R['numero_retorno']==1 else 'Segundo' if R['numero_retorno']==2 else 'Tercer'} retorno · a {abs(R['orbe_actual']):.1f}° del punto exacto al {R['fecha_consulta'][8:]}/{R['fecha_consulta'][5:7]}/{R['fecha_consulta'][:4]}")}
<h2>Qué es esto</h2>
{_p(L['umbral'])}
<p class="nota">{NOTA_FUENTES}</p>
<h2 class="pb">Lo que vuelve</h2>
<p>Esta es tu carta. El punto que importa en esta lectura es uno solo: dónde estaba {c} cuando naciste. A eso vuelve.</p>
<div class="rueda">{rueda_svg(nat, 300)}</div>
{_p(L['lo_que_vuelve'])}
<h2>Las fechas</h2>
{fechas}
<h2>La tarea</h2>
{_p(L['tarea'])}
<h2>Una advertencia</h2>
{_p(L['advertencia'])}
<div class="llave">✧ {L['llave']}</div>
{nod}
{_si_no(L['si_no'], 'Si esto no es así', 'Un retorno dura entre uno y dos años. Acá va qué tendría que pasar en ese tiempo para que esta lectura esté equivocada.')}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_RETORNO}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(nat)}</p>
{_tabla_carta(nat['astro'])}
<h3>{c} natal y sus aspectos (orbe ≤ 6°)</h3>
<p>{c} natal a {R['pos_natal']['fmt']}, casa {ROMANO[R['pos_natal']['casa']-1] if R['pos_natal'].get('casa') else '—'}{' R' if R['pos_natal']['retro'] else ''}.</p>{asp}
<h3>Pases exactos (ventana {R['ventana']['desde']} → {R['ventana']['hasta']})</h3>{pases}
<p>Edad actual {R['edad_actual']} · orbe actual {R['orbe_actual']:+.2f}° · ciclo de {c}: {__import__('elbrujo_calculo').CICLOS.get(c, '—')} años.</p>
{('<h3>Tránsitos al primer pase (' + T1['fecha'] + ')</h3>' + t1) if T1 else ''}
<h3>Número y elemento</h3>
<p>Año Personal del retorno <b>{R['anio_personal_retorno']}</b> · año Bazi {R['anio_bazi_retorno']['ganzhi']} ({R['anio_bazi_retorno']['animal']}){(' · década Da Yun activa ' + dy['ganzhi'] + ' (' + dy['animal'] + ', ' + str(dy['desde']) + '–' + str(dy['hasta']) + ')') if dy else ''}.</p>
{_bloque_num_bazi(nat)}
{_anexo_cierra(L, R['avisos'])}"""
    return _doc(L, nombre, nombre, cuerpo)

# ============================================================ 6 · TU PRÓXIMO AÑO
def plantilla_proximo_anio(L, P):
    nat = P['natal']
    meses = ""
    for mm, b in zip(P['meses'], L['meses']):
        nom = f"{MESES[mm['mes']][0].upper() + MESES[mm['mes']][1:]} {mm['anio']}"
        meses += (f'<div class="semana"><h3>{nom}{(" — " + b["titulo"]) if b.get("titulo") else ""}</h3>'
                  f'<div class="fecha">Mes Personal {mm["mes_personal"]} · mes de {mm["pilar_mes"]["animal"]}</div>{_p(b["parrafos"])}</div>')
    anexo_meses = ""
    for mm in P['meses']:
        filas = "".join(f"<tr><td>{x['transito']}{' R' if x['retro'] else ''} {x['pos']}</td><td>{x['aspecto']}</td><td>{x['natal']}</td><td>{x['orbe']:.2f}°</td><td>{ROMANO[x['casa_natal']-1] if x['casa_natal'] else '—'}</td></tr>" for x in mm['lentos'])
        hit = "; ".join(h['etiqueta'] for h in mm['hitos'])
        anexo_meses += (f"<p><b>{MESES[mm['mes']]} {mm['anio']}</b> · Mes Personal {mm['mes_personal']} · pilar {mm['pilar_mes']['ganzhi']}{(' · hitos: ' + hit) if hit else ''}</p>"
                        f"<table><tr><th>Lento en tránsito (al 15)</th><th>Aspecto</th><th>Punto natal</th><th>Orbe</th><th>Casa natal</th></tr>{filas or '<tr><td colspan=5>sin lentos en orbe</td></tr>'}</table>")
    lun = "".join(f"<tr><td>{l['fecha']}</td><td>{l['tipo']}</td><td>{l['fmt']}</td><td>{ROMANO[l['casa_natal']-1] if l['casa_natal'] else '—'}</td></tr>" for l in P['lunaciones'])
    est = "".join(f"<tr><td>{e['fecha']}</td><td>{e['cuerpo']}</td><td>{e['estacion']}</td><td>{e['fmt']}</td></tr>" for e in P['estaciones'] if e['cuerpo'] != 'Mercurio')
    pas = "".join(f"<tr><td>{p['fecha']}</td><td>{p['cuerpo']}{' R' if p['retro'] else ''}</td><td>{p['aspecto']}</td><td>{p['natal']}</td></tr>" for p in P['pasos'])
    d0, d1 = P['desde'], P['hasta']
    cuerpo = f"""
{_tapa(L, 'Tu próximo año', f"Del {d0[8:]}/{d0[5:7]}/{d0[:4]} al {d1[8:]}/{d1[5:7]}/{d1[:4]} · lo lento que pasa sobre tu carta")}
{ANTES_MES.replace('durante el mes', 'durante los doce meses que vienen')}
<p class="nota">{NOTA_FUENTES}</p>
<div class="rueda">{rueda_svg(nat, 280)}</div>
<h2 class="pb">El año, en una mirada</h2>
{_p(L['clima'])}
<h2>Mes por mes</h2>
{meses}
<h2>Las tres o cuatro fechas que pesan</h2>
{_p(L['hitos'])}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'], 'Si esto no es así', 'Un año entero es fácil de verificar: pasa. Acá va cómo saber si esta lectura estuvo bien.')}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_PROXIMO}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(nat)}</p>
{_tabla_carta(nat['astro'])}
<h3>Tránsitos lentos, mes por mes</h3>
<p>Júpiter, Saturno, Urano, Neptuno, Plutón, Nodo y Quirón sobre puntos natales, orbe ≤ 3°, posición al 15 de cada mes. Año Bazi al inicio: {P['anio_bazi']['ganzhi']} ({P['anio_bazi']['animal']}).</p>
{anexo_meses}
<h3>Pasos exactos</h3><table><tr><th>Fecha</th><th>En tránsito</th><th>Aspecto</th><th>Punto natal</th></tr>{pas}</table>
<h3>Lunaciones</h3><table><tr><th>Fecha</th><th></th><th>Grado</th><th>Casa natal</th></tr>{lun}</table>
<h3>Estaciones (sin Mercurio)</h3><table><tr><th>Fecha</th><th>Planeta</th><th>Estación</th><th>Grado</th></tr>{est}</table>
{_anexo_cierra(L, P['avisos'])}"""
    return _doc(L, f"Tu próximo año · {d0[:7]} → {d1[:7]}", 'Tu próximo año', cuerpo)

# ============================================================ 7 · SINASTRÍA
def plantilla_sinastria(L, S):
    A, B = S['a'], S['b']
    na, nb = L['consultante'], L['consultante_b']
    secs = "".join(f"<h3>{s['titulo']}</h3>" + _p(s['parrafos']) for s in L['encuentro'])
    cuantos = {0: 'ninguno', 1: 'uno', 2: 'dos', 3: 'tres'}[len(L['nodos'])]
    decl = L.get('nodos_declaracion', '')
    cruz = [x for x in S['cruz'] if x['orbe'] <= 3.0][:24]
    cruz_t = ("<table><tr><th>" + html.escape(na) + "</th><th>Aspecto</th><th>" + html.escape(nb) + "</th><th>Orbe</th></tr>" +
              "".join(f"<tr><td>{x['a']}</td><td>{x['aspecto']}</td><td>{x['b']}</td><td>{x['orbe']:.2f}°</td></tr>" for x in cruz) + "</table>")
    def casas(dic, quien, de):
        if not dic: return f"<p>Sin hora de {de}: no hay casas donde ubicar los planetas de {quien}.</p>"
        return "<p>" + ", ".join(f"{k} de {quien} en {ROMANO[c-1]} de {de}" for k, c in dic.items() if k in ORDEN) + ".</p>"
    bz = S['bazi']; rel = bz['relaciones']
    rel_t = "; ".join([f"Chong {r['a']}–{r['b']}" for r in rel['chong']] + [f"Liuhé {r['a']}–{r['b']}" for r in rel['liuhe']] +
                      [f"{r.get('tipo', 'Sanhé')} de {r['elemento']}: {', '.join(r['ramas'])}" for r in rel['sanhe']]) or "sin relaciones mayores entre ramas"
    nu = S['num']
    cuerpo = f"""
{_tapa(L, 'Sinastría', 'Dos cielos, y lo que pasa entre los dos', f"<br>con <b>{html.escape(nb)}</b><br>{L['datos_linea_b']}<br>Vínculo: {L['vinculo']}")}
<h2>Cómo leer esto</h2>
<p>Una sinastría pone una carta sobre la otra y mira dónde se tocan. No dice si el vínculo va a funcionar: dice dónde se encuentra fácil, dónde se traba, y qué le pide cada uno al otro sin saberlo. Se lee de a dos, o se lee solo y después se conversa.</p>
<p>Primero, cada uno en una frase. Después, los lugares donde las dos cartas se encuentran. Después, <b>el nudo</b>: lo que se traba, con sus señales. Y al final, como siempre, cómo saber si esto no es así.</p>
<p class="nota">{NOTA_FUENTES}</p>
<h2 class="pb">Las dos cartas</h2>
<div class="rueda"><table style="margin:0 auto"><tr><td style="text-align:center"><b>{html.escape(na)}</b><br>{rueda_svg(A, 230)}</td><td style="text-align:center"><b>{html.escape(nb)}</b><br>{rueda_svg(B, 230)}</td></tr></table></div>
{_p(L['dos'])}
<h2>Donde se encuentran</h2>
{secs}
<h2>El nudo</h2>
{_p(L['nudo'])}
<div class="llave">✧ {L['llave_luz']}</div>

<div class="negra"><div class="t">La sombra del vínculo</div>
<div class="s">Leyeron el encuentro en luz. Lo que sigue es lo mismo cuando no se trabaja.<br>No es un veredicto sobre ninguno de los dos: es lo que cada contacto es cuando se deja solo.<br>Se lee después de la luz, nunca en su lugar.</div></div>
<h2>Lo mismo, cuando no se trabaja</h2>
<p>Busqué los lugares donde el cielo, los números y el calendario chino señalan la misma traba entre los dos. Encontré {cuantos}.{(' ' + decl) if decl else ''} Cada uno viene con dos señales: cómo se ve cuando manda, y cómo se ve cuando está trabajado. Son conductas de a dos, no sentimientos.</p>
{_nodos(L['nodos'])}
<h3>La figura de la sombra</h3>
{_p(L['figura_sombra'])}
<div class="llave">✧ {L['llave_sombra']}</div>
{_si_no(L['si_no'])}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_SINASTRIA}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta de {html.escape(na)}</h3><p>{_linea_natal(A)}</p>{_tabla_carta(A['astro'])}
<h3>Carta de {html.escape(nb)}</h3><p>{_linea_natal(B)}</p>{_tabla_carta(B['astro'])}
<h3>Aspectos cruzados (orbe ≤ 3°, orbes natales × 0,75)</h3>{cruz_t}
<h3>Casas</h3>{casas(S['a_en_casas_de_b'], na, nb)}{casas(S['b_en_casas_de_a'], nb, na)}
<h3>Bazi entre las dos cartas</h3>
<p>Día Maestro de {html.escape(na)}: {bz['dia_maestro_a']['tronco']} ({bz['dia_maestro_a']['descripcion']}), útil {bz['util_a']} · Día Maestro de {html.escape(nb)}: {bz['dia_maestro_b']['tronco']} ({bz['dia_maestro_b']['descripcion']}), útil {bz['util_b']} · relación entre elementos: {bz['relacion_dias_maestros']}.<br>Relaciones entre ramas: {rel_t}.</p>
<h3>Numerología</h3>
<p>{html.escape(na)}: Camino {nu['a']['camino']} · Alma {nu['a']['alma']} · Expresión {nu['a']['expresion']} · Personalidad {nu['a']['personalidad']}.<br>{html.escape(nb)}: Camino {nu['b']['camino']} · Alma {nu['b']['alma']} · Expresión {nu['b']['expresion']} · Personalidad {nu['b']['personalidad']}.</p>
{_anexo_cierra(L, S['avisos'])}"""
    return _doc(L, f"Sinastría · {na} y {nb}", 'Sinastría', cuerpo)

# ============================================================ 8 · PROGRESIONES
def plantilla_progresiones(L, G):
    nat = G['natal']; P = G['progresada']
    cont = ""
    for b in L['contactos']:
        cont += (f'<div class="semana"><h3>{b["titulo"]}</h3><div class="fecha">{b["fecha"]}</div>{_p(b["parrafos"])}</div>')
    tabla_p = ("<table><tr><th>Progresado</th><th>Posición</th><th>Casa natal</th></tr>" +
               "".join(f"<tr><td>{GL.get(k,'')} {NOMBRE_ES.get(k,k)}</td><td>{P['pos'][k]['fmt']}{' R' if P['pos'][k]['retro'] else ''}</td><td>{ROMANO[P['pos'][k]['casa_natal']-1]}</td></tr>" for k in ORDEN if k in P['pos']) +
               f"<tr><td>Ascendente progresado</td><td>{P['asc']}</td><td>—</td></tr><tr><td>Medio Cielo progresado</td><td>{P['mc']}</td><td>—</td></tr></table>")
    cont_t = ("<table><tr><th>Progresado</th><th>Aspecto</th><th>Punto natal</th><th>Orbe</th></tr>" +
              "".join(f"<tr><td>{x['progresado']}</td><td>{x['aspecto']}</td><td>{x['natal']}</td><td>{x['orbe']:.2f}°</td></tr>" for x in G['contactos']) + "</table>") if G['contactos'] else "<p>Ningún contacto progresado→natal con orbe ≤ 1° a la fecha.</p>"
    ex_t = ("<table><tr><th>Fecha</th><th>Progresado</th><th>Aspecto</th><th>Punto natal</th></tr>" +
            "".join(f"<tr><td>{x['fecha']}</td><td>{x['progresado']}</td><td>{x['aspecto']}</td><td>{x['natal']}</td></tr>" for x in G['exactos_12m']) + "</table>") if G['exactos_12m'] else "<p>Sin pases exactos de Sol o Luna progresados en los próximos doce meses.</p>"
    ing = "; ".join(f"{i['fecha']}: entra en {i['signo']} (casa natal {ROMANO[i['casa_natal']-1]})" for i in G['ingresos_luna']) or "la Luna progresada no cambia de signo en los próximos doce meses"
    cuerpo = f"""
{_tapa(L, 'Progresiones', f"Al {G['fecha'][8:]}/{G['fecha'][5:7]}/{G['fecha'][:4]} · tu carta, avanzada un día por cada año de vida")}
<h2>Cómo leer esto</h2>
<p>Hay una técnica antigua que dice que cada día después de tu nacimiento cuenta como un año de tu vida: el cielo del día 36 después de que naciste describe tu año 36. No es el cielo de afuera, el que pasa por encima de tu carta: es tu propia carta, avanzando despacio. Por eso habla de clima interno, no de hechos.</p>
<p>Dos cosas mandan acá: dónde está tu Sol avanzado, que cambia de signo una vez cada treinta años y marca una época entera; y dónde está tu Luna avanzada, que da la vuelta cada veintisiete años y cambia de signo cada dos y pico: es el estado de ánimo de fondo de este tramo.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="rueda">{rueda_svg(nat, 280)}</div>
<h2 class="pb">El clima interno</h2>
{_p(L['clima_interno'])}
<h3>Tu Luna avanzada</h3>
{_p(L['luna'])}
<h3>Tu Sol avanzado</h3>
{_p(L['sol'])}
<h2>Los contactos que vienen</h2>
{cont}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'], 'Si esto no es así', 'El clima interno es lo más difícil de verificar desde afuera, y lo más fácil desde adentro. Acá va cómo.')}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_PROGRESIONES}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(nat)}</p>
{_tabla_carta(nat['astro'])}
<h3>Carta progresada al {G['fecha']} (edad {G['edad']})</h3>
<p>Progresión secundaria, un día por año. Medio Cielo progresado por arco solar; Ascendente y casas progresadas derivados de él para el lugar de nacimiento. Fase lunar progresada: <b>{G['fase']['nombre']}</b> ({G['fase']['grados']}° de separación Sol–Luna).</p>
{tabla_p}
<h3>Contactos progresado → natal (orbe ≤ 1°)</h3>{cont_t}
<h3>Pases exactos de Sol y Luna progresados, próximos doce meses</h3>{ex_t}
<p>Ingresos de la Luna progresada: {ing}.</p>
<p>Año Personal <b>{G['anio_personal']}</b>.</p>
{_anexo_cierra(L, G['avisos'])}"""
    return _doc(L, 'Progresiones', 'Progresiones', cuerpo)

# ============================================================ 9 · RECORTES DE LA INTEGRAL
CIERRE_NATAL = ("Esta lectura no te dice quién sos: te muestra el cielo con el que naciste. Todo lo que leíste ya es tuyo. "
    "Lo que hagas con eso cambia todos los días. Que te sirva para reconocerte, no para explicarte.")
CIERRE_NOMBRE = ("Tus números no te mandan: te describen desde otro ángulo, con una aritmética que cualquiera puede repetir. "
    "Lo que está acá ya lo tenés; lo que te tensa, se trabaja. Que te sirva para ponerle nombre a lo que ya sabías.")
CIERRE_PILARES = ("Tu carta china no te dice qué va a pasar: te dice de qué estás hecho y qué te hace bien. "
    "Lo que te sobra no es un defecto: es lo que hay que encauzar. Que te sirva para cuidarte mejor, no para explicarte.")
CIERRE_DECADAS = ("Las décadas no deciden: cambian el clima en el que decidís. Saber en cuál estás parado y cuál viene "
    "no te ahorra el camino, pero te deja elegir el calzado. Que te sirva para eso.")
CIERRE_ANIO_PERSONAL = ("Un año personal es un ritmo, no una sentencia. Saber cuál es te deja empujar cuando el año empuja "
    "y descansar cuando el año descansa. Lo que hagas en cada mes es tuyo.")
CIERRE_HIJO = ("Esta lectura no dice quién va a ser: muestra con qué nació. Nada de lo que está acá es un límite, y mucho "
    "menos un veredicto. Es una forma de mirarlo con más paciencia. Que te sirva para acompañar, no para dirigir.")

QUE_HIJO = {'Sol':'lo que es cuando está en su centro','Luna':'cómo necesita sentirse para estar bien',
            'Mercurio':'cómo piensa y habla','Venus':'cómo quiere y qué le gusta','Marte':'cómo actúa y cómo se enoja',
            'Júpiter':'dónde crece y confía','Saturno':'dónde se exige y dónde va a construir',
            'Urano':'lo que lo hace distinto','Neptuno':'lo que lo disuelve','Plutón':'dónde se transforma',
            'Nodo N':'hacia dónde va','Nodo S':'de dónde viene','Lilith':'su deseo que no se somete','Quirón':'su herida que puede volverse don'}

def plantilla_natal(L, ch):
    secs = "".join(f"<h3>{s['titulo']}</h3>" + _p(s['parrafos']) for s in L['luz'])
    cuerpo = f"""
{_tapa(L, 'Lectura natal', 'El cielo del día en que naciste')}
<h2>Antes de leer</h2>
<p>Esta lectura es sólo el cielo: la foto del momento exacto en que naciste, vista desde el lugar donde naciste. No cruza con los números ni con el calendario chino: eso es la Lectura Integral. Acá va la carta sola, leída en luz, con una llave al final.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="caja">{_p(L['sabe'])}</div>
<h2 class="pb">Tu cielo, dibujado</h2>
<p>No es decorativa: es tu carta. Todo lo que sigue sale de acá.</p>
<div class="rueda">{rueda_svg(ch)}</div>
<p class="nota" style="text-align:center">Los doce sectores numerados son las zonas de tu vida (la 1 es vos, la 7 la pareja, la 10 el trabajo público, y así). Los símbolos son los planetas. Dónde cae cada uno es lo que se lee.</p>
{_vistazo(ch)}
<h2 class="pb">Lo que traés</h2>
{secs}
<h3>La figura de tu carta</h3>
{_p(L['figura_luz'])}
<div class="llave">✧ {L['llave_luz']}</div>
{_si_no(L['si_no'])}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_NATAL}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(ch)}</p>
{_tabla_carta(ch['astro'])}
<h3>Aspectos mayores (orbes: Sol y Luna 8°, Mercurio a Saturno 6°, el resto 4° o menos; «amplio» si pasa de 4°)</h3>{_tabla_aspectos(ch['astro']['aspectos'])}
{_anexo_cierra(L, ch['astro']['avisos'])}"""
    return _doc(L, 'Lectura natal', 'Lectura natal', cuerpo)

def plantilla_nombre(L, ch):
    n = ch['num']
    secs = "".join(f"<h3>{s['titulo']}</h3>" + _p(s['parrafos']) for s in L['nucleo'])
    vist = ('<table class="vistazo">' +
            f"<tr><td>Tu camino</td><td>{n['camino']} — lo que viniste a aprender, sale de tu fecha</td></tr>" +
            (f"<tr><td>Tu alma</td><td>{n['alma']} — lo que querés por dentro, sale de las vocales de tu nombre</td></tr>"
             f"<tr><td>Cómo te expresás</td><td>{n['expresion']} — con qué herramientas, sale de todas las letras</td></tr>"
             f"<tr><td>Cómo te ven</td><td>{n['personalidad']} — la primera impresión, sale de las consonantes</td></tr>"
             f"<tr><td>Tu segunda mitad</td><td>{n['madurez']} — hacia dónde madura todo esto, de los 35 en adelante</td></tr>" if n['alma'] is not None else "") +
            f"<tr><td>Tu año</td><td>{n['anio_personal']} — el ritmo de este año, cambia en tu cumpleaños</td></tr></table>")
    cuerpo = f"""
{_tapa(L, 'Tu nombre y tu fecha', 'Lo que dicen tus números')}
<h2>Antes de leer</h2>
<p>Esta lectura usa una sola tradición: la numerología pitagórica. Cada letra de tu nombre legal vale un número, y tu fecha también. Con eso se calculan cinco números que te describen y uno que describe tu año. No es el cielo ni el calendario chino: eso es la Lectura Integral. Acá van los números solos, y lo que se tensa entre ellos.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="caja">{_p(L['sabe'])}</div>
<h2>Tus números, de un vistazo</h2>
{vist}
<h2 class="pb">Uno por uno</h2>
{secs}
<h2>Lo que se tensa entre ellos</h2>
{_p(L['tension'])}
<h2>Tus ciclos</h2>
{_p(L['ciclos'])}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'])}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_NOMBRE}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<p>Fecha {ch['datos']['fecha']} · nombre legal usado: {ch['datos'].get('nombre') or '—'} · motor v{VERSION}.</p>
{_bloque_num(ch)}
{_anexo_cierra(L, ch['num']['avisos'])}"""
    return _doc(L, 'Tu nombre y tu fecha', 'Tu nombre y tu fecha', cuerpo)

IMAGEN_DM = {'Jia': 'el roble', 'Yi': 'la enredadera', 'Bing': 'el sol', 'Ding': 'la vela', 'Wu': 'la montaña',
             'Ji': 'el campo cultivado', 'Geng': 'el hierro', 'Xin': 'la joya', 'Ren': 'el río', 'Gui': 'la lluvia'}

def plantilla_pilares(L, ch):
    b = ch['bazi']
    pil = " · ".join(f"{x['animal']} de {x['elemento_tronco']}" for x in (b['pilar_anio'], b['pilar_mes'], b['pilar_dia']) ) + (f" · {b['pilar_hora']['animal']} de {b['pilar_hora']['elemento_tronco']}" if b['pilar_hora'] else " · sin pilar de hora")
    bal = " · ".join(f"{e} {b['balance'][e]}" for e in ('Madera','Fuego','Tierra','Metal','Agua'))
    vist = ('<table class="vistazo">' +
            f"<tr><td>Vos</td><td>{IMAGEN_DM[b['dia_maestro']['tronco']]} — {b['dia_maestro']['descripcion']}, {'fuerte' if b['dm_fuerte'] else 'débil'} en tu carta</td></tr>"
            f"<tr><td>Tus pilares</td><td>{pil}</td></tr>"
            f"<tr><td>Lo que hay</td><td>{bal}</td></tr>"
            f"<tr><td>Lo que te hace bien</td><td>{b['elemento_util']}{' (en empate con ' + b['yong_shen_metodo']['candidatos_finales'][1] + ')' if b['yong_shen_metodo']['margen_estrecho'] and len(b['yong_shen_metodo']['candidatos_finales'])>1 else ''}</td></tr>"
            f"<tr><td>Lo que te sobra</td><td>{b['yong_shen_metodo']['excedente'] or 'nada por encima del umbral'}</td></tr></table>")
    cuerpo = f"""
{_tapa(L, 'Tus cuatro pilares', 'Tu carta china: de qué estás hecho')}
<h2>Antes de leer</h2>
<p>Esta lectura usa una sola tradición: el calendario chino de los Cuatro Pilares. Tu fecha y tu hora se convierten en cuatro pares de signos: el año, el mes, el día y la hora. El del día sos vos. Los otros tres son el paisaje en el que estás parado. De ahí sale de qué elemento estás hecho, qué te sobra y qué te hace bien. No es el cielo ni los números: eso es la Lectura Integral.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="caja">{_p(L['sabe'])}</div>
<h2>De un vistazo</h2>
{vist}
<h2 class="pb">Quién sos en este calendario</h2>
{_p(L['quien_sos'])}
<h2>Lo que te hace bien</h2>
{_p(L['lo_que_te_hace_bien'])}
<h2>Lo que te sobra</h2>
{_p(L['lo_que_te_sobra'])}
<h2>Cómo se llevan tus pilares</h2>
{_p(L['relaciones'])}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'])}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_PILARES}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<p>Fecha {ch['datos']['fecha']} · {ch['datos'].get('hora') or 'sin hora'} ({ch['datos']['tz']}) · motor v{VERSION}.</p>
{_bloque_bazi(ch)}
{_anexo_cierra(L, ch['bazi']['avisos'] + ([ch['da_yun']['declaracion_sexo']] if ch['da_yun'].get('declaracion_sexo') else []))}"""
    return _doc(L, 'Tus cuatro pilares', 'Tus cuatro pilares', cuerpo)

def plantilla_decadas(L, X):
    ch = X['natal']; b = ch['bazi']
    if not X['disponible']:
        raise ValueError("Da Yun no disponible: " + str(X['motivo']))
    filas = "".join(f"<tr><td>{'▶ ' if c['activa'] else ''}{c['n']}</td><td>{c['anio_desde']}–{c['anio_hasta']} (de {int(c['desde'])} a {int(c['hasta'])} años)</td><td>{c['ganzhi']} · {c['animal']} de {c['elemento_tronco']}</td><td>{c['rel_tronco']} / {c['rel_rama']}</td><td>{'sí' if c['util'] else ''}</td></tr>" for c in X['ciclos'])
    tabla = f"<table><tr><th></th><th>Década</th><th>Pilar</th><th>Con tu elemento (tronco / rama)</th><th>Trae lo que te hace bien</th></tr>{filas}</table>"
    dec = ""
    for d_ in L['decadas']:
        dec += (f'<div class="semana"><h3>{d_["titulo"]}</h3><div class="fecha">{d_["rango"]}</div>{_p(d_["parrafos"])}</div>')
    act = X['ciclos'][X['indice_activa']] if X['indice_activa'] is not None else None
    cuerpo = f"""
{_tapa(L, 'Tus décadas', 'Los ciclos de diez años del calendario chino', (f"<br>Década en curso: {act['anio_desde']}–{act['anio_hasta']}, {act['animal']} de {act['elemento_tronco']}" if act else ""))}
<h2>Antes de leer</h2>
<p>En el calendario chino la vida se recorre en tramos de diez años, y cada tramo trae un elemento y un animal que se cruzan con los tuyos. No cambian quién sos: cambian el clima en el que vivís. Esta lectura mira la década que estás viviendo, la que dejaste y las dos que vienen. Sos {IMAGEN_DM[b['dia_maestro']['tronco']]}; lo que te hace bien es {b['elemento_util']}. Con eso se lee cada tramo.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="caja">{_p(L['sabe'])}</div>
<h2>Tus décadas, de un vistazo</h2>
{tabla}
<h2 class="pb">Una por una</h2>
{_p(L['intro'])}
{dec}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'])}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_DECADAS}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<p>Fecha {ch['datos']['fecha']} · {ch['datos'].get('hora') or 'sin hora'} ({ch['datos']['tz']}) · edad {X['edad']} · año Bazi en curso {X['anio_bazi']['ganzhi']} ({X['anio_bazi']['animal']}) · motor v{VERSION}.</p>
{_bloque_bazi(ch)}
{_anexo_cierra(L, X['avisos'])}"""
    return _doc(L, 'Tus décadas', 'Tus décadas', cuerpo)

def plantilla_anio_personal(L, A):
    ch = A['natal']
    i0, f0 = A['inicio'], A['fin']
    filas = "".join(f"<tr><td>{'▶ ' if m['actual'] else ''}{MESES[m['mes']]} {m['anio']}</td><td>{m['mes_personal']}</td></tr>" for m in A['meses'])
    mes_b = ""
    for m, b in zip(A['meses'], L['meses']):
        mes_b += (f'<div class="semana"><h3>{MESES[m["mes"]][0].upper() + MESES[m["mes"]][1:]} {m["anio"]} — mes {m["mes_personal"]}</h3>{_p(b["parrafos"])}</div>')
    pin = A['pinaculo']
    cuerpo = f"""
{_tapa(L, 'Tu año personal', f"Año {A['anio_personal']} · del {i0[8:]}/{i0[5:7]}/{i0[:4]} al {f0[8:]}/{f0[5:7]}/{f0[:4]}")}
<h2>Antes de leer</h2>
<p>En numerología cada año de tu vida tiene un número, del 1 al 9, que se repite en ciclo. Empieza en tu cumpleaños, no el primero de enero. Cada mes dentro del año tiene también el suyo. No dicen qué va a pasar: dicen qué ritmo pide cada tramo, cuándo empujar y cuándo esperar.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="caja">{_p(L['sabe'])}</div>
<h2>Tu año, de un vistazo</h2>
<table class="vistazo"><tr><td>Este año</td><td>{A['anio_personal']} — desde tu cumpleaños de {i0[:4]} hasta el de {int(i0[:4])+1}</td></tr>
<tr><td>El que viene</td><td>{A['siguiente']}</td></tr>
<tr><td>Tu camino</td><td>{A['camino']} — el número de fondo, con el que este año conversa</td></tr>
{('<tr><td>El tramo largo</td><td>' + str(pin['valor']) + ' — vigente desde los ' + str(pin['desde']) + ' años' + ('' if pin['hasta'] is None else ' hasta los ' + str(pin['hasta'])) + '; su desafío es el ' + str(A['desafio']) + '</td></tr>') if pin else ''}</table>
<h2 class="pb">El año</h2>
{_p(L['el_anio'])}
<h2>Mes a mes</h2>
<table class="vistazo">{filas}</table>
{mes_b}
<div class="llave">✧ {L['llave']}</div>
{_si_no(L['si_no'])}
{_preguntas(L.get('preguntas'))}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_ANIO_PERSONAL}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<p>Fecha {ch['datos']['fecha']} · nombre legal usado: {ch['datos'].get('nombre') or '—'} · motor v{VERSION}. Año Personal = día + mes de nacimiento + año del último cumpleaños, reducido; Mes Personal = Año Personal + número del mes, reducido.</p>
{_bloque_num(ch)}
{_anexo_cierra(L, A['avisos'])}"""
    return _doc(L, f"Tu año personal {A['anio_personal']}", 'Tu año personal', cuerpo)

def plantilla_hijo(L, ch):
    secs = "".join(f"<h3>{s['titulo']}</h3>" + _p(s['parrafos']) for s in L['luz'])
    cuerpo = f"""
{_tapa(L, 'Lectura de un hijo o hija', 'Con qué nació, para quien lo cría', f"<br>Para: {L['para']}")}
<h2>Antes de leer</h2>
<p>Esta lectura es la carta de un chico o una chica, escrita para quien lo cría. Cruza el cielo del momento en que nació, los números de su nombre y el calendario chino, igual que una Lectura Integral. Pero no tiene parte de sombra ni preguntas incómodas: un chico no eligió esta lectura, y lo que se diga de él tiene que poder leerse en voz alta delante de él sin lastimarlo.</p>
<p>Lo que sigue describe con qué nació. No describe quién va a ser: eso lo va a decidir él, con el tiempo y con ustedes. Donde dice «necesita», es una forma de mirar, no una receta.</p>
<p class="nota">{NOTA_FUENTES}</p>
<div class="caja">{_p(L['sabe'])}</div>
<h2 class="pb">Su cielo, dibujado</h2>
<div class="rueda">{rueda_svg(ch)}</div>
<p class="nota" style="text-align:center">Los doce sectores numerados son las zonas de la vida (la 1 es él, la 4 la casa, la 5 el juego, y así). Los símbolos son los planetas.</p>
{_vistazo(ch, QUE_HIJO)}
<h2 class="pb">Con qué nació</h2>
{secs}
<h3>Lo que pide de quien lo cría</h3>
{_p(L['lo_que_pide'])}
<h3>La figura de su carta</h3>
{_p(L['figura_luz'])}
<div class="llave">✧ {L['llave_luz']}</div>
{_si_no(L['si_no'], 'Si esto no es así', 'Nadie conoce a este chico mejor que ustedes. Acá va qué tendría que ser distinto para que esta lectura esté equivocada.')}
<h2>Cierre</h2>
{_p(L['cierre'])}
<p>{CIERRE_HIJO}</p>
<div class="cierre">{RITUAL}</div>
{_anexo_abre()}
<h3>Carta natal</h3><p>{_linea_natal(ch)}</p>
{_tabla_carta(ch['astro'])}
<h3>Aspectos mayores (orbes: Sol y Luna 8°, Mercurio a Saturno 6°, el resto 4° o menos; «amplio» si pasa de 4°)</h3>{_tabla_aspectos(ch['astro']['aspectos'])}
{_bloque_num_bazi(ch)}
{_anexo_cierra(L, ch['avisos'])}"""
    return _doc(L, 'Lectura de un hijo o hija', 'Lectura de un hijo o hija', cuerpo)

# ============================================================ render y entrada única
def render(html_str, salida):
    from fontTools.ttLib.tables.O_S_2f_2 import table_O_S_2f_2
    _o = table_O_S_2f_2.setUnicodeRanges
    table_O_S_2f_2.setUnicodeRanges = lambda self, bits: _o(self, set(b for b in bits if 0 <= b <= 122))
    from weasyprint import HTML
    HTML(string=html_str).write_pdf(salida); return salida

def generar(tipo, datos, lectura, salida, **kw):
    """tipo ∈ {'integral', 'anio', 'mes'}. Devuelve la ruta del PDF."""
    if tipo == 'integral':
        return render(plantilla_integral(lectura, calcular(datos)), salida)
    if tipo == 'anio':
        Y = calc_anio(datos, kw['anio_rs'], kw.get('lugar_rs'), kw.get('fecha_consulta'))
        return render(plantilla_anio(lectura, Y), salida)
    if tipo == 'mes':
        M = calc_mes(datos, kw['anio'], kw['mes'])
        return render(plantilla_mes(lectura, M), salida)
    if tipo == 'lunaciones':
        return render(plantilla_lunaciones(lectura, calc_lunaciones(datos, kw['anio'], kw['mes'])), salida)
    if tipo == 'retorno':
        return render(plantilla_retorno(lectura, calc_retorno(datos, kw.get('cuerpo', 'Saturno'), kw.get('fecha_consulta'))), salida)
    if tipo == 'proximo_anio':
        return render(plantilla_proximo_anio(lectura, calc_proximo(datos, kw.get('desde'))), salida)
    if tipo == 'sinastria':
        return render(plantilla_sinastria(lectura, calc_sinastria(datos, kw['datos_b'])), salida)
    if tipo == 'progresiones':
        return render(plantilla_progresiones(lectura, calc_progresiones(datos, kw.get('fecha_consulta'))), salida)
    if tipo == 'natal':
        return render(plantilla_natal(lectura, calcular(datos)), salida)
    if tipo == 'nombre':
        return render(plantilla_nombre(lectura, calcular(datos)), salida)
    if tipo == 'pilares':
        return render(plantilla_pilares(lectura, calcular(datos)), salida)
    if tipo == 'hijo':
        return render(plantilla_hijo(lectura, calcular(datos)), salida)
    if tipo == 'anio_personal':
        return render(plantilla_anio_personal(lectura, calc_anio_personal(datos, kw.get('fecha_consulta'))), salida)
    if tipo == 'decadas':
        return render(plantilla_decadas(lectura, calc_decadas(datos, kw.get('fecha_consulta'))), salida)
    raise ValueError(f"tipo desconocido: {tipo}")

# compatibilidad con los scripts de lectura anteriores (lectura_*_llano.py)
def plantilla(L, ch):
    return plantilla_integral(L, ch)
