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


def valida(g, nombre):
    """True si ese nodo GARANTIZA que lo siguiente solo corre con un objeto
    valido. Hay DOS formas de hacerlo en Blueprint, no una:

      - la macro IsValid de la biblioteca estandar;
      - un **get validado** (`K2Node_VariableGet` con
        `CurrentVariation = ValidatedObject`), que es un get normal al que se
        le han sacado pines de ejecucion y una salida `else`.

    Mirar solo la macro daba un falso positivo en el `Remove from Parent` del
    menu de pausa, que va detras de un get validado de `WidgetPause`.
    """
    n = g.get(nombre)
    if not n:
        return False
    if (n.get("class") == "K2Node_MacroInstance"
            and "IsValid" in n["props"].get("MacroGraphReference", "")):
        return True
    return (n.get("class") == "K2Node_VariableGet"
            and n["props"].get("CurrentVariation", "") == "ValidatedObject")

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
    guardado = all(valida(g, p) for p in previos) and previos
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
    if previos and all(valida(g, p) for p in previos):
        ok("%s con IsValid delante" % nm)
    else:
        mal("%s: Remove from Parent sin IsValid delante (viene de %s)"
            % (nm, ", ".join(previos) or "nada"))
if not hay:
    ok("no hay ningun Remove from Parent en el grafo")

print("\nC) la cadena validada del cambio de slot")
# Lo que de verdad importa ya se midio en A: que no quede ni un
# Set Actor Hidden In Game ALCANZABLE sin IsValid delante. Aqui solo se
# comprueba que el SwitchInteger viejo quedo fuera de juego y que el punto de
# entrada con nombre sigue existiendo.
#
# OJO: ya NO se exige que Ev_ActualizarEquipo tenga un nodo que lo LLAME.
# Desde la fusion del 2026-09-11 el cambio de slot entra EN LINEA en la cadena
# validada, porque una llamada de CONTEXTO PROPIO a una funcion que aun no
# existe abre al pegar el modal "Arreglar referencias de funciones de contexto
# propio", y eso bloquea el pegado automatico. El evento se conserva como
# segunda entrada a la misma cadena, para poder invocarla desde un banco.
ev = [nm for nm, n in g.items()
      if n["class"] == "K2Node_CustomEvent"
      and n["props"].get("CustomFunctionName", "").strip('"') == "Ev_ActualizarEquipo"]
if not ev:
    mal("no existe el punto de entrada Ev_ActualizarEquipo")
else:
    ok("existe Ev_ActualizarEquipo (%s)" % ", ".join(ev))

viejos = [nm for nm, n in g.items() if n["class"] == "K2Node_SwitchInteger"]
vivos = [nm for nm in viejos if alcanzable(nm)]
if vivos:
    mal("el SwitchInteger viejo del cambio de slot SIGUE conectado: %s"
        % ", ".join(vivos))
elif viejos:
    ok("el SwitchInteger viejo esta desconectado (%s)" % ", ".join(viejos))
else:
    ok("ya no hay ningun SwitchInteger en el grafo")

print("\n" + "=" * 70)
print("FALLOS: %d" % len(fallos))
for f in fallos:
    print("   - " + f)
