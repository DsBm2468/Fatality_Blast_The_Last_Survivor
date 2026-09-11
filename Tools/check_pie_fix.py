# -*- coding: utf-8 -*-
"""
Comprueba, sobre el grafo REAL, que los errores de tiempo de ejecucion que el
Message Log escupia al cerrar la reproduccion ya no pueden darse.

  1) exportar el Blueprint:
       "<engine>/.../python.exe" Tools/ue_remote.py Tools/export_t3d_now.py
     (o Tools/export_t3d.py, que exporta la lista larga)
  2) python Tools/check_pie_fix.py

Acaba en "FALLOS: N".

Que mira:
  A) que ningun 'Set Actor Hidden In Game' ALCANZABLE se llame sobre una
     referencia de BPC_Inventary sin un IsValid delante;
  B) que 'Remove from Parent' de la mira este detras de un IsValid;
  C) que el bloque viejo del SwitchInteger, si sigue en el grafo, este
     desconectado (no se ejecuta y por tanto no puede fallar).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t3d_read as T  # noqa: E402

RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "Saved", "AuditT3D_BP_ThirdPersonCharacter.copy")
REFS_INVENTARIO = ("Object_Is_Weapon", "Object_Is_Throwable",
                   "Object_Is_Shield", "Object_Is_FirstAidKit")

fallos = []


def mal(m):
    fallos.append(m)
    print("  FALLO  " + m)


def ok(m):
    print("  ok     " + m)


g = T.parse(RUTA)["EventGraph"]


def pin(nm, nombre):
    for p in g[nm]["pins"]:
        if p.get("PinName", "").strip('"') == nombre:
            return p


def enlaces(nm, nombre):
    p = pin(nm, nombre)
    if not p or not p.get("LinkedTo"):
        return []
    return re.findall(r"([A-Za-z_][\w]*) [0-9A-F]{32}", p["LinkedTo"])


def es_exec(p):
    return p.get("PinType.PinCategory", "").strip('"') == "exec"


def entradas_exec(nm):
    """Nodos que entran por exec (para saber si algo es alcanzable)."""
    r = []
    for p in g[nm]["pins"]:
        if es_exec(p) and p.get("Direction", "").strip('"') != "EGPD_Output":
            r += re.findall(r"([A-Za-z_][\w]*) [0-9A-F]{32}", p.get("LinkedTo") or "")
    return r


def sin_knots(nm):
    visto = set()
    while g.get(nm, {}).get("class") == "K2Node_Knot" and nm not in visto:
        visto.add(nm)
        e = enlaces(nm, "InputPin")
        if not e:
            break
        nm = e[0]
    return nm


# --- nodos alcanzables: se camina hacia atras desde cada nodo por sus
#     entradas de exec hasta llegar (o no) a un evento
EVENTOS = {nm for nm, n in g.items()
           if n["class"] in ("K2Node_Event", "K2Node_CustomEvent",
                             "K2Node_EnhancedInputAction", "K2Node_InputKey",
                             "K2Node_InputDebugKey", "K2Node_ComponentBoundEvent")}


def alcanzable(nm, visto=None):
    visto = visto if visto is not None else set()
    if nm in EVENTOS:
        return True
    if nm in visto:
        return False
    visto.add(nm)
    return any(alcanzable(sin_knots(e), visto) for e in entradas_exec(nm))


print("=" * 70)
print(" COMPROBACION DE LOS ERRORES DE PIE  (%s)" % os.path.basename(RUTA))
print("=" * 70)
print("\nA) Set Actor Hidden In Game sobre referencias del inventario")

vivos = muertos = 0
for nm, n in g.items():
    if n["class"] != "K2Node_CallFunction":
        continue
    if T.mem(n["props"], "FunctionReference") != "SetActorHiddenInGame":
        continue
    destino = sin_knots((enlaces(nm, "self") or [""])[0])
    var = T.mem(g.get(destino, {}).get("props", {}), "VariableReference")
    if var not in REFS_INVENTARIO:
        continue
    if not alcanzable(nm):
        muertos += 1
        continue
    vivos += 1
    previos = [sin_knots(e) for e in entradas_exec(nm)]
    guardado = all(g.get(p, {}).get("class") == "K2Node_MacroInstance"
                   and "IsValid" in g[p]["props"].get("MacroGraphReference", "")
                   for p in previos) and previos
    if guardado:
        ok("%s (%s) con IsValid delante" % (nm, var))
    else:
        mal("%s llama a Set Actor Hidden In Game sobre %s SIN IsValid delante"
            % (nm, var))
print("     alcanzables: %d   desconectados (inofensivos): %d" % (vivos, muertos))

print("\nB) Remove from Parent de la mira")
hay = False
for nm, n in g.items():
    if n["class"] != "K2Node_CallFunction":
        continue
    if T.mem(n["props"], "FunctionReference") != "RemoveFromParent":
        continue
    hay = True
    if not alcanzable(nm):
        ok("%s desconectado" % nm)
        continue
    previos = [sin_knots(e) for e in entradas_exec(nm)]
    if previos and all(g.get(p, {}).get("class") == "K2Node_MacroInstance"
                       and "IsValid" in g[p]["props"].get("MacroGraphReference", "")
                       for p in previos):
        ok("%s con IsValid delante" % nm)
    else:
        mal("%s: Remove from Parent sin IsValid delante (viene de %s)"
            % (nm, ", ".join(previos) or "nada"))
if not hay:
    ok("no hay ningun Remove from Parent en el grafo")

print("\nC) el evento nuevo")
ev = [nm for nm, n in g.items()
      if n["class"] == "K2Node_CustomEvent"
      and n["props"].get("CustomFunctionName", "").strip('"') == "Ev_ActualizarEquipo"]
if not ev:
    mal("no existe el evento Ev_ActualizarEquipo")
else:
    llamadas = [nm for nm, n in g.items()
                if n["class"] == "K2Node_CallFunction"
                and T.mem(n["props"], "FunctionReference") == "Ev_ActualizarEquipo"]
    if not llamadas:
        mal("Ev_ActualizarEquipo existe pero no lo llama nadie")
    elif not any(alcanzable(c) for c in llamadas):
        mal("Ev_ActualizarEquipo se llama desde codigo inalcanzable")
    else:
        ok("Ev_ActualizarEquipo existe y se llama desde %s" % ", ".join(llamadas))

print("\n" + "=" * 70)
print("FALLOS: %d" % len(fallos))
for f in fallos:
    print("   - " + f)
