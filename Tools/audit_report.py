# -*- coding: utf-8 -*-
"""
Fase 2 de la auditoria: analiza los Saved/AuditT3D_*.copy que dejo audit_full.py
y saca los hallazgos que NO da el compilador.

Busca las formas de fallo que en este proyecto compilan en verde:
  * nodos inalcanzables (tienen entrada de ejecucion y nadie se la conecta)
  * pines huerfanos y nodos con ErrorType
  * eventos personalizados duplicados (pegados encima de si mismos)
  * eventos personalizados que no llama nadie
  * CustomEvent llamado literalmente "CustomEvent" (evento de interfaz
    degradado porque el Blueprint no declara la interfaz)
  * ruido de PrintString

Uso:   python Tools/audit_report.py
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_graph as ag

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Saved")

# nodos que ARRANCAN una cadena: es normal que no tengan entrada conectada
ARRANCADORES = {
    "K2Node_Event", "K2Node_CustomEvent", "K2Node_FunctionEntry",
    "K2Node_InputKey", "K2Node_InputDebugKey", "K2Node_EnhancedInputAction",
    "K2Node_ComponentBoundEvent", "K2Node_ActorBoundEvent",
    "K2Node_InputAxisEvent", "K2Node_Timeline",
}
# grafos que son stubs del compilador, no logica de verdad
def es_stub(nodos):
    clases = [n["class"] for n in nodos.values()]
    return len(nodos) <= 3 and "K2Node_FunctionEntry" in clases


hallazgos = []


def H(sev, bp, titulo, detalle=""):
    hallazgos.append((sev, bp, titulo, detalle))


ficheros = sorted(glob.glob(os.path.join(RAIZ, "AuditT3D_*.copy")))
print("Analizando %d Blueprints exportados\n" % len(ficheros))

resumen = []

for f in ficheros:
    nombre = os.path.basename(f)[len("AuditT3D_"):-len(".copy")]
    try:
        gs = ag.parse(f)
        txt = ag.load(f)
    except Exception as e:
        H("ALTO", nombre, "no se pudo leer el export", str(e))
        continue

    n_nodos = sum(len(v) for v in gs.values())
    huerfanos = txt.count("bOrphanedPin=True")
    errortype = len(re.findall(r"ErrorType=\d", txt))
    prints = len(re.findall(r'MemberName="PrintString"', txt))

    # --- eventos personalizados: duplicados y sin llamar
    eventos = collections.Counter(re.findall(r'CustomFunctionName="(\w+)"', txt))
    dups = {k: v for k, v in eventos.items() if v > 1}
    llamados = set(re.findall(r'MemberName="(\w+)",bSelfContext=True', txt))
    llamados |= set(re.findall(
        r'MemberParent=[^,]*%s_C[^,]*,MemberName="(\w+)"' % re.escape(nombre), txt))

    # --- nodos inalcanzables
    inalcanzables = []
    for gname, nodos in gs.items():
        if es_stub(nodos):
            continue
        for nm, n in nodos.items():
            if n["class"] in ARRANCADORES:
                continue
            tiene_exec_in = False
            conectado = False
            for p in n["pins"]:
                if p.get("PinType.PinCategory", "").strip('"') != "exec":
                    continue
                if p.get("Direction", "").strip('"') == "EGPD_Output":
                    continue
                tiene_exec_in = True
                if p.get("LinkedTo"):
                    conectado = True
            if tiene_exec_in and not conectado:
                inalcanzables.append((gname, ag.label(n)))

    resumen.append((nombre, n_nodos, huerfanos, errortype,
                    len(inalcanzables), prints))

    if huerfanos:
        H("ALTO", nombre, "%d pines huerfanos" % huerfanos,
          "un pin huerfano no rompe la compilacion y no se ejecuta")
    if dups:
        H("ALTO", nombre, "eventos personalizados DUPLICADOS",
          ", ".join("%s x%d" % (k, v) for k, v in sorted(dups.items())))
    if "CustomEvent" in eventos:
        H("ALTO", nombre, "evento llamado literalmente 'CustomEvent'",
          "senal de evento de interfaz degradado, o resto de un pegado")
    if inalcanzables:
        muestra = "; ".join("%s: %s" % (g, l) for g, l in inalcanzables[:6])
        if len(inalcanzables) > 6:
            muestra += " ... (+%d)" % (len(inalcanzables) - 6)
        H("MEDIO", nombre, "%d nodos inalcanzables" % len(inalcanzables), muestra)
    if errortype:
        H("BAJO", nombre, "%d nodos con ErrorType" % errortype)

    sin_llamar = [e for e in eventos
                  if e not in llamados
                  and not e.startswith("BndEvt")
                  and e != "CustomEvent"]
    if sin_llamar:
        H("MEDIO", nombre, "eventos personalizados que nadie llama",
          ", ".join(sorted(sin_llamar)))

    if prints >= 8:
        H("BAJO", nombre, "%d PrintString" % prints,
          "instrumento de medida en este proyecto, pero es ruido en el juego")

# ---------------------------------------------------------------- salida
print("%-30s %6s %5s %5s %6s %7s" % ("BLUEPRINT", "nodos", "huer", "err",
                                     "inalc", "prints"))
for r in sorted(resumen, key=lambda x: -x[1]):
    if r[1] == 0:
        continue
    print("%-30s %6d %5d %5d %6d %7d" % r)

print("")
print("=" * 78)
orden = {"BLOQUEANTE": 0, "ALTO": 1, "MEDIO": 2, "BAJO": 3}
hallazgos.sort(key=lambda h: (orden.get(h[0], 9), h[1]))
print("HALLAZGOS: %d" % len(hallazgos))
print("")
for sev, bp, titulo, detalle in hallazgos:
    print("[%-5s] %-26s %s" % (sev, bp, titulo))
    if detalle:
        print("          %s" % detalle)

ruta = os.path.join(RAIZ, "Auditoria_Report.txt")
with open(ruta, "w", encoding="utf-8") as fh:
    fh.write("HALLAZGOS: %d\n\n" % len(hallazgos))
    for sev, bp, titulo, detalle in hallazgos:
        fh.write("[%s] %s  %s\n" % (sev, bp, titulo))
        if detalle:
            fh.write("      %s\n" % detalle)
print("")
print("informe -> " + os.path.normpath(ruta))
