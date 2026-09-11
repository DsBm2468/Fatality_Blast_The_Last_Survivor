# -*- coding: utf-8 -*-
"""
Genera los pegados que quitan los errores de tiempo de ejecucion que salen al
cerrar la reproduccion (el Message Log acumula todo lo de la sesion y lo
enseña de golpe al pulsar ESC).

Dos familias, las dos en BP_ThirdPersonCharacter.EventGraph:

  A) "Accessed None ... Object_Is_Throwable / Object_Is_Shield /
      Object_Is_FirstAidKit en BPC_Inventary_C"   (nodo Set Actor Hidden In Game)
     El cambio de slot muestra el item elegido y ESCONDE los otros tres, pero
     solo valida el que muestra. Los otros tres se llaman sobre referencias
     None (o sobre un item ya consumido y pendiente de recoleccion: el
     "no es valido (eliminacion o basura pendientes)" del BP_FirstAidKit).
     16 llamadas, 4 validadas.
     -> 45_Char_ActualizarEquipo.txt: un evento Ev_ActualizarEquipo que hace lo
        mismo con UNA validacion por item, y sustituye a las 4 ramas del
        SwitchInteger.

  B) "Accessed None ... CallFunc_Create_ReturnValue_2"  (nodo Remove from Parent)
     Al soltar el apuntado (IA_Point Completed) se llama a Remove from Parent
     sobre el valor de retorno del Create Widget de la mira. Si nunca se ha
     apuntado, ese temporal es None.
     -> 46_Char_MiraIsValid.txt: la macro IsValid que hay que intercalar.

Convenio de ValueOptionInventary, leido del SwitchInteger real (no estaba
documentado en ninguna parte):
    0 = Object_Is_Weapon   1 = Object_Is_Throwable
    2 = Object_Is_Shield   3 = Object_Is_FirstAidKit
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpgen as B  # noqa: E402

SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_paste")

INV_C = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
ACTOR = B.cls("/Script/Engine.Actor")
MATH = "/Script/Engine.KismetMathLibrary"

# (variable en BPC_Inventary, indice de slot, texto que imprimia la rama)
ITEMS = [
    ("Object_Is_Weapon", 0, "ARMA SELECCIONADA"),
    ("Object_Is_Throwable", 1, "LANZABLE SELECCIONADA"),
    ("Object_Is_Shield", 2, "ESCUDO SELECCIONADO"),
    ("Object_Is_FirstAidKit", 3, "BOTIQUIN SELECCIONADO"),
]
VERDE = '(R=0.014579,G=0.198458,B=0.012857,A=1.000000)'


def bloque_a():
    g = B.Graph("FixEquip", "Ev_ActualizarEquipo - sustituye al SwitchInteger "
                            "del cambio de slot, validando los cuatro items.")

    ev = g.custom_event("Ev_ActualizarEquipo", 0, 0)
    seq = g.node_sequence(260, 0, n=5)
    ev.exec_out.to(seq.exec_in)

    # lecturas comunes: el componente y el slot activo
    inv = g.var_get("BPC_Inventary", B.CAT_OBJECT, -60, 1980,
                    sub_object=B.cls(INV_C))
    slot = g.var_get("ValueOptionInventary", B.CAT_INT, -60, 2100)

    # then_0: las dos banderas a false; cada rama las vuelve a poner
    sg = g.var_set("HaveGun", B.CAT_BOOL, 560, -180)
    sg.get("HaveGun").default = "false"
    sr = g.var_set("HaveGrenade", B.CAT_BOOL, 800, -180)
    sr.get("HaveGrenade").default = "false"
    seq.get("then_0").to(sg.exec_in)
    sg.exec_out.to(sr.exec_in)

    # then_1..then_4: un bloque identico por item
    for fila, (var, idx, texto) in enumerate(ITEMS):
        y = 120 + fila * 420

        item = g.var_get_target(var, B.CAT_OBJECT, INV_C, 560, y + 150,
                                sub_object=ACTOR)
        inv.get("BPC_Inventary").to(item.get("self"))

        val = g.is_valid(860, y)
        item.get(var).to(val.get("InputObject"))
        seq.get("then_%d" % (fila + 1)).to(val.get("Exec"))

        # bNewHidden = (slot != idx): un solo Set Actor Hidden In Game por item
        ne = g.call("NotEqual_IntInt", MATH, 860, y + 240, pure=True)
        ne.pin("A", B.CAT_INT)
        ne.pin("B", B.CAT_INT, default=str(idx))
        ne.pin("ReturnValue", B.CAT_BOOL, out=True)
        slot.get("ValueOptionInventary").to(ne.get("A"))

        ocultar = g.call_self("SetActorHiddenInGame", None, 1160, y)
        ocultar.pin("self", B.CAT_OBJECT, sub_object=ACTOR)
        ocultar.pin("bNewHidden", B.CAT_BOOL)
        item.get(var).to(ocultar.get("self"))
        ne.get("ReturnValue").to(ocultar.get("bNewHidden"))
        val.get("Is Valid").to(ocultar.exec_in)

        # el aviso en pantalla solo cuando ESTE es el slot elegido, que es lo
        # que hacia el grafo original (la rama del switch colgaba del IsValid)
        br = g.branch(1460, y)
        ne.get("ReturnValue").to(br.get("Condition"))
        ocultar.exec_out.to(br.exec_in)

        pr = g.call("PrintString", "/Script/Engine.KismetSystemLibrary", 1720, y)
        pr.pin("InString", B.CAT_STRING, default=texto)
        pr.pin("bPrintToScreen", B.CAT_BOOL, default="true")
        pr.pin("bPrintToLog", B.CAT_BOOL, default="true")
        pr.pin("TextColor", B.CAT_STRUCT, default=VERDE,
               sub_object=B.obj("ScriptStruct", "/Script/CoreUObject.LinearColor"))
        pr.pin("Duration", B.CAT_REAL, sub="double", default="5.000000")
        br.get("else").to(pr.exec_in)

        if idx in (0, 1):
            nombre = "HaveGun" if idx == 0 else "HaveGrenade"
            s = g.var_set(nombre, B.CAT_BOOL, 2060, y)
            s.get(nombre).default = "true"
            pr.exec_out.to(s.exec_in)

    return g


def bloque_b():
    g = B.Graph("FixMira", "IsValid a intercalar entre 'SET Socket Offset' y "
                           "'Remove from Parent' de la mira (IA_Point Completed).")
    v = g.is_valid(0, 0)
    return g


if __name__ == "__main__":
    if not os.path.isdir(SALIDA):
        os.makedirs(SALIDA)
    for nombre, g in (("45_Char_ActualizarEquipo", bloque_a()),
                      ("46_Char_MiraIsValid", bloque_b())):
        ruta = os.path.join(SALIDA, nombre + ".txt")
        g.save(ruta)
        print("%-22s %3d nodos  %s" % (nombre, len(g.nodes), ruta))
