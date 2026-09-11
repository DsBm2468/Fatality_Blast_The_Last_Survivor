# -*- coding: utf-8 -*-
"""
Re-aplica sobre el personaje de `main` el arreglo del cambio de slot que esta
rama hizo el 2026-09-08 y que la fusion se llevo por delante.

EL PROBLEMA (vuelve a estar, tal cual): el `SwitchInteger` del cambio de slot
muestra el item elegido y **esconde los otros tres**, pero solo valida el que
muestra. Son **16 llamadas a `Set Actor Hidden In Game` y solo 4 validadas**,
asi que cada cambio de slot con el inventario incompleto suelta tres
`Accessed None`. Unreal los acumula y los enseña de golpe al parar la
reproduccion: ~282 por sesion.

EL ARREGLO: una cadena con **un `IsValid` por item**, y el `SwitchInteger`
viejo desconectado (queda como codigo muerto inofensivo: `check_pie_fix.py`
distingue alcanzable de desconectado).

POR QUE NO SE LLAMA A UN EVENTO, SINO QUE SE ENTRA EN LINEA: una llamada de
CONTEXTO PROPIO a una funcion que todavia no existe abre al pegar el modal
"Arreglar referencias de funciones de contexto propio", que bloquea el pegado
automatico. Aqui el cambio de slot entra DIRECTAMENTE en la cadena validada
(`SET HaveGrenade.then` -> el `Sequence`), y `Ev_ActualizarEquipo` se conserva
como segunda entrada a la misma cadena, para poder invocarla desde un banco de
pruebas sin depender de la tecla.

Uso:
    python Tools/gen_fix_slot_main.py
    python Tools/reemplazar_grafo.py <BP_ThirdPersonCharacter>
    python Tools/paste_bp.py <BP_ThirdPersonCharacter> EventGraph <pegado> --no-abrir
"""
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(RAIZ, "Tools")
sys.path.insert(0, TOOLS)

import t3d_edit          # noqa: E402
import t3d_to_paste      # noqa: E402
import gen_fix_pie_errors as FIX   # noqa: E402

EXPORT = os.path.join(RAIZ, "Saved", "T3D_char3.copy")
SALIDA = os.path.join(TOOLS, "bp_paste", "59_Char_EventGraph.txt")

# Nodos del grafo de main, leidos del export (no supuestos)
SET_HAVEGRENADE = "K2Node_VariableSet_14"   # su 'then' alimentaba el switch
SWITCH_VIEJO = "K2Node_SwitchInteger_0"


class Falso(object):
    """Pin de mentira: deja que bpgen escriba un LinkedTo hacia un nodo que
    viene del export y que por tanto no es un objeto Pin suyo."""

    def __init__(self, pin_id, nodo):
        self.id = pin_id
        self.node = type("N", (), {"name": nodo})()
        self.links = []


def main():
    if not os.path.isfile(EXPORT):
        raise SystemExit("falta %s: exporta antes el personaje a T3D" % EXPORT)

    ed = t3d_edit.Bloques(EXPORT, "EventGraph")
    g = FIX.bloque_a()          # el bloque validado, con su evento y su Sequence

    # el Sequence es la puerta de entrada del bloque
    seq = None
    for n in g.nodes:
        if n.ue_class == "K2Node_ExecutionSequence":
            seq = n
    if seq is None:
        raise SystemExit("el bloque no trae Sequence")

    # 1. el cambio de slot entra ahora en la cadena validada
    id_switch = ed.pin_id(SWITCH_VIEJO, "execute")
    id_have = ed.pin_id(SET_HAVEGRENADE, "then")
    ed.enlazar(SET_HAVEGRENADE, "then", [(seq.name, seq.get("execute").id)])
    seq.get("execute").links.append(Falso(id_have, SET_HAVEGRENADE))

    # 2. el SwitchInteger viejo se queda sin entrada: codigo muerto inofensivo
    ed.enlazar(SWITCH_VIEJO, "execute", [])

    texto = ed.texto() + g.render()
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(texto)
    n = texto.count("Begin Object Class=")
    print("escrito %s  (%d nodos: %d del grafo + %d del arreglo)"
          % (SALIDA, n, n - len(g.nodes), len(g.nodes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
