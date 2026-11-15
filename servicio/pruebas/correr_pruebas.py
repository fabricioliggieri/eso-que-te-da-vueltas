# -*- coding: utf-8 -*-
"""
correr_pruebas.py · «Eso que te da vueltas» · las pruebas contra el modelo real, por lotes (mitad de precio).

Pasos (cada uno se corre a mano; el estado queda en estado.json, al lado):
  python correr_pruebas.py preparar               filtros fijos y cálculo de los 146 casos (sin API)
  python correr_pruebas.py enviar-gen sonnet|opus  manda el lote de respuestas
  python correr_pruebas.py ver                    estado de los lotes
  python correr_pruebas.py bajar-gen sonnet|opus   baja las respuestas, controles por código, manda el lote del revisor
  python correr_pruebas.py bajar-rev sonnet|opus   baja los veredictos y escribe el informe
Los datos son inventados: por eso se pueden mandar por lotes (que guardan 29 días). Nunca preguntas reales.
"""
from __future__ import annotations
import csv, json, os, re, sys
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI)); sys.path.insert(0, AQUI)
import filtros, calculo_pregunta, pregunta, modelo  # noqa: E402
from set_pruebas import casos  # noqa: E402
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming  # noqa: E402
from anthropic.types.messages.batch_create_params import Request  # noqa: E402

ESTADO = os.path.join(AQUI, "estado.json")
HOY = "2026-11-15"
MODELOS = {"sonnet": modelo.MODELO_SONNET, "opus": modelo.MODELO_OPUS}
# USD por millón de tokens (precios oficiales al 15/11/2026), entrada / salida; los lotes cobran la mitad.
PRECIO = {modelo.MODELO_SONNET: (2.0, 10.0), modelo.MODELO_OPUS: (4.0, 20.0), modelo.MODELO_REVISOR: (0.10, 0.50)}


def cargar(): return json.load(open(ESTADO, encoding="utf-8")) if os.path.exists(ESTADO) else {}
def guardar(e): json.dump(e, open(ESTADO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def preparar():
    e = {"casos": {}, "lotes": {}}
    for c in casos():
        fijo = filtros.revisar(c["pregunta"], c["fecha"], date.fromisoformat(HOY))
        item = {**c, "fijo": fijo["tipo"] if fijo else None}
        if not fijo:
            h = calculo_pregunta.hechos(c["fecha"], c["hora"], c["lat"], c["lon"], c["tz"], HOY)
            item["hechos"] = h
            item["mensaje"] = pregunta.armar_mensaje(h, c["pregunta"])
        e["casos"][c["id"]] = item
    guardar(e)
    n = sum(1 for x in e["casos"].values() if x["fijo"])
    print(f"{len(e['casos'])} casos · {n} frenados por los filtros fijos · {len(e['casos'])-n} van al modelo")


def enviar(lista, modelo_id, system, esquema):
    reqs = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**modelo.parametros(modelo_id, system, msg, esquema)))
            for cid, msg in lista]
    lote = modelo.cliente().messages.batches.create(requests=reqs)
    return lote.id


def enviar_gen(clave):
    e = cargar()
    lista = [(cid, x["mensaje"]) for cid, x in e["casos"].items() if not x["fijo"]]
    e["lotes"][f"gen_{clave}"] = enviar(lista, MODELOS[clave], pregunta.PROMPT_BRUJO, modelo.ESQ_BRUJO)
    guardar(e); print("lote de respuestas:", e["lotes"][f"gen_{clave}"], f"({len(lista)} pedidos)")


def ver():
    e = cargar()
    for k, lid in e.get("lotes", {}).items():
        b = modelo.cliente().messages.batches.retrieve(lid)
        print(k, lid, b.processing_status, dict(b.request_counts))


def bajar(lid):
    out = {}
    for r in modelo.cliente().messages.batches.results(lid):
        if r.result.type == "succeeded":
            datos, uso = modelo.leer(r.result.message)
            out[r.custom_id] = {"datos": datos, "uso": uso}
        else:
            out[r.custom_id] = {"datos": None, "uso": {"stop": r.result.type}}
    return out


def bajar_gen(clave):
    e = cargar(); res = bajar(e["lotes"][f"gen_{clave}"])
    para_revisar = []
    for cid, r in res.items():
        x = e["casos"][cid]
        d = r["datos"] or {"respuesta": "", "tipo": "otra", "puerta": "ninguna"}
        d["puerta"] = None if d.get("puerta") == "ninguna" else d.get("puerta")
        fallas = pregunta.controles_codigo(d, x["hechos"])
        x.setdefault("res", {})[clave] = {"salida": d, "uso_gen": r["uso"], "fallas": fallas}
        if not fallas:
            para_revisar.append((cid, x["mensaje"] + f"\n<respuesta>\n{d['respuesta']}\n</respuesta>"))
    e["lotes"][f"rev_{clave}"] = enviar(para_revisar, modelo.MODELO_REVISOR, pregunta.PROMPT_REVISOR, modelo.ESQ_REVISOR)
    guardar(e); print(f"{len(res)} respuestas bajadas · {len(para_revisar)} al revisor · lote {e['lotes'][f'rev_{clave}']}")


def lotes_rev(e, clave):
    return [v for k, v in sorted(e["lotes"].items()) if v and re.fullmatch(rf"rev\d*_{clave}", k)]


def veredictos(e, clave):
    out = {}
    for lid in lotes_rev(e, clave):
        if modelo.cliente().messages.batches.retrieve(lid).processing_status == "ended":
            out.update(bajar(lid))
    return out


def rerevisar(clave):
    """Después de corregir los controles por código: recalcula las fallas y manda al revisor
    las respuestas que ahora pasan y todavía no tienen veredicto (sin volver a generarlas)."""
    e = cargar()
    previo = veredictos(e, clave)
    pendientes = [lid for lid in lotes_rev(e, clave)
                  if modelo.cliente().messages.batches.retrieve(lid).processing_status != "ended"]
    if pendientes:
        print("Hay lotes del revisor sin terminar:", pendientes); return
    lista = []
    for cid, x in e["casos"].items():
        if x["fijo"] or clave not in x.get("res", {}): continue
        rr = x["res"][clave]
        rr["fallas"] = pregunta.controles_codigo(rr["salida"], x["hechos"])
        if not rr["fallas"] and cid not in previo:
            lista.append((cid, x["mensaje"] + f"\n<respuesta>\n{rr['salida']['respuesta']}\n</respuesta>"))
    n = len(lotes_rev(e, clave)) + 1
    e["lotes"][f"rev{n}_{clave}"] = enviar(lista, modelo.MODELO_REVISOR, pregunta.PROMPT_REVISOR, modelo.ESQ_REVISOR) if lista else None
    guardar(e); print(f"{clave}: {len(lista)} más al revisor · lote {e['lotes'][f'rev{n}_{clave}']}")


def costo(uso, modelo_id):
    if not uso or "entrada" not in uso: return 0.0
    pe, ps = PRECIO[modelo_id]
    return (uso["entrada"] * pe + uso["salida"] * ps) / 1e6 / 2  # lote: mitad


def bajar_rev(clave):
    e = cargar()
    res = veredictos(e, clave)
    for x in e["casos"].values():
        if clave in x.get("res", {}):
            x["res"][clave]["fallas"] = pregunta.controles_codigo(x["res"][clave]["salida"], x["hechos"])
    filas = []
    total = 0.0
    for cid, x in e["casos"].items():
        f_now = filtros.revisar(x["pregunta"], x["fecha"], date.fromisoformat(HOY))
        if f_now and not x["fijo"]:
            x["fijo"] = f_now["tipo"]  # lo frena el filtro corregido: no llega al modelo
        if x["fijo"]:
            filas.append({"id": cid, "categoria": x["categoria"], "persona": x["persona"], "pregunta": x["pregunta"],
                          "resultado": f"fijo:{x['fijo']}", "reglas": "", "tipo": "", "puerta": "", "palabras": "",
                          "respuesta": filtros.RESPUESTAS.get(x["fijo"], "")[:120], "costo_usd": 0})
            continue
        rr = x["res"][clave]; d = rr["salida"]
        v = res.get(cid, {}).get("datos") if not rr["fallas"] else None
        rr["veredicto"] = v; rr["uso_rev"] = res.get(cid, {}).get("uso")
        reglas = rr["fallas"] + (v["reglas"] if v else [])
        if d.get("tipo") == "crisis" or "R6" in reglas: resultado = "crisis->fija"
        elif rr["fallas"] or not (v and v["pasa"]): resultado = "frenada"
        else: resultado = "mostrada"
        c = costo(rr["uso_gen"], MODELOS[clave]) + costo(rr["uso_rev"], modelo.MODELO_REVISOR)
        total += c
        filas.append({"id": cid, "categoria": x["categoria"], "persona": x["persona"], "pregunta": x["pregunta"],
                      "resultado": resultado, "reglas": ",".join(reglas), "tipo": d.get("tipo"),
                      "puerta": d.get("puerta") or "", "palabras": len((d.get("respuesta") or "").split()),
                      "respuesta": d.get("respuesta"), "costo_usd": round(c, 5),
                      "motivo_revisor": (v or {}).get("motivo", "")})
    guardar(e)
    ruta = os.path.join(AQUI, f"informe_{clave}.csv")
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[-1].keys()) + (["motivo_revisor"] if "motivo_revisor" not in filas[-1] else []),
                           extrasaction="ignore"); w.writeheader(); w.writerows(filas)
    from collections import Counter
    print(f"Modelo {clave}: {Counter(f['resultado'] for f in filas)} · costo total USD {total:.3f}")
    print("Informe:", ruta)


if __name__ == "__main__":
    paso = sys.argv[1]
    {"preparar": lambda: preparar(), "ver": lambda: ver(),
     "enviar-gen": lambda: enviar_gen(sys.argv[2]), "bajar-gen": lambda: bajar_gen(sys.argv[2]),
     "bajar-rev": lambda: bajar_rev(sys.argv[2]), "rerevisar": lambda: rerevisar(sys.argv[2])}[paso]()
