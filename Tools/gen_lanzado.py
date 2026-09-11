# -*- coding: utf-8 -*-
"""
Genera el EventGraph de BP_Item_Throwable_Base con los dos arreglos del
sistema de lanzado.

1. **La explosion solo alcanzaba a UN actor.** `ReactionOfItem` usaba
   `SphereTraceSingleForObjects`, que por definicion devuelve un unico
   impacto, y metia ese unico actor en `DetectedActors`. Los hijos (granada,
   bomba, frasco de veneno) recorren esa lista para aplicar su efecto, asi que
   una granada en medio de cuatro soldados afectaba a uno. Se cambia por
   `SphereOverlapActors`, que devuelve TODOS los actores del radio, y un
   ForEach los mete uno a uno.

2. **Al lanzar, el objeto no salia del inventario.** Seguia registrado en su
   hueco y `EquippedItem` seguia apuntandolo, asi que el personaje creia tener
   en la mano una granada que ya estaba volando. Ahora, tras dar el impulso,
   se limpia `BPC_Interaction.EquippedItem` y se llama a `Ev_VaciarHueco`.

Lo demas del lanzamiento ya estaba bien y se conserva tal cual: desenganchar,
devolver la fisica, ignorar al lanzador, impulso y temporizador.

Nota sobre la condicion de lanzamiento: es `RequirePointing AND IsPointing`,
o sea que un lanzable con RequirePointing = false no se podria lanzar nunca.
Hoy los tres lanzables lo tienen a true, asi que se comporta como "solo se
lanza apuntando", que es el diseno. Se deja como esta y se anota.

Uso:
    python Tools/gen_lanzado.py
    python Tools/reemplazar_grafo.py <BP_Item_Throwable_Base>
    python Tools/paste_bp.py <BP_Item_Throwable_Base> EventGraph <pegado> --no-abrir
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "Tools"))

import bpgen as B      # noqa: E402
import t3d_edit        # noqa: E402

EXPORT = os.path.join(RAIZ, "Saved", "T3D_thr.copy")
SALIDA = os.path.join(RAIZ, "Tools", "bp_paste", "55_Throw_EventGraph.txt")

C_INTERACTION = "/Game/ThirdPerson/Components/BPC_Interaction.BPC_Interaction_C"
C_INVENTARY = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
C_ITEM = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
          "BP_Item.BP_Item_C")
E_ITEMTYPE = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
              "InformationItem/E_ItemType.E_ItemType")


class Falso(object):
    """Pin de mentira para poder cablear desde bpgen hacia un nodo que viene
    del export (que no es un objeto Pin de bpgen)."""

    def __init__(self, pin_id, nodo):
        self.id = pin_id
        self.node = type("N", (), {"name": nodo})()
        self.links = []


def main():
    ed = t3d_edit.Bloques(EXPORT, "EventGraph")
    g = B.Graph("lanzar")

    # ============================================================== (1)
    # Fuera la traza de un solo impacto y todo lo que colgaba de ella.
    id_delay = ed.pin_id("K2Node_CallFunction_13", "execute")
    pos_start = ed.pin_id("K2Node_CallFunction_12", "ReturnValue")
    pos_radio = ed.pin_id("K2Node_VariableGet_2", "ExplosionRange")
    pos_tipos = ed.pin_id("K2Node_MakeArray_0", "Array")
    pos_lista = ed.pin_id("K2Node_VariableGet_8", "DetectedActors")
    id_reaccion = ed.pin_id("K2Node_CustomEvent_2", "then")

    ed.quitar("K2Node_CallFunction_6",      # SphereTraceSingleForObjects
              "K2Node_IfThenElse_0",        # Branch sobre el resultado
              "K2Node_CallFunction_10",     # BreakHitResult
              "K2Node_CallArrayFunction_0",  # el AddUnique viejo
              "K2Node_Knot_10", "K2Node_Knot_11",
              "K2Node_Knot_13", "K2Node_Knot_14",
              "K2Node_CallFunction_5")      # GetActorLocation sin usar

    solape = g.call("SphereOverlapActors", "/Script/Engine.KismetSystemLibrary",
                    1200, 3000)
    solape.pin("WorldContextObject", B.CAT_OBJECT,
               sub_object=B.cls("/Script/CoreUObject.Object"))
    solape.pin("SpherePos", B.CAT_STRUCT,
               sub_object=B.obj("ScriptStruct", "/Script/CoreUObject.Vector"))
    solape.pin("SphereRadius", B.CAT_REAL, sub="float")
    solape.pin("ObjectTypes", B.CAT_BYTE,
               sub_object=B.obj("Enum", "/Script/Engine.EObjectTypeQuery"),
               container="Array")
    solape.pin("OutActors", B.CAT_OBJECT, out=True,
               sub_object=B.cls("/Script/Engine.Actor"), container="Array",
               is_ref=True)

    yo = g.self_node(1200, 3300)
    yo.get("self").to(solape.get("WorldContextObject"))

    # el evento ahora arranca el solape
    ed.enlazar("K2Node_CustomEvent_2", "then",
               [(solape.name, solape.get("execute").id)])
    solape.get("execute").links.append(Falso(id_reaccion, "K2Node_CustomEvent_2"))
    # y los datos vienen de los nodos que ya estaban
    for nodo, pin, destino in (
            ("K2Node_CallFunction_12", "ReturnValue", "SpherePos"),
            ("K2Node_VariableGet_2", "ExplosionRange", "SphereRadius"),
            ("K2Node_MakeArray_0", "Array", "ObjectTypes")):
        ed.enlazar(nodo, pin, [(solape.name, solape.get(destino).id)])
        solape.get(destino).links.append(
            Falso(ed.pin_id(nodo, pin), nodo))

    bucle = g.for_each(1700, 3000, category=B.CAT_OBJECT,
                       sub_object=B.cls("/Script/Engine.Actor"))
    solape.exec_out.to(bucle.get("Exec"))
    solape.get("OutActors").to(bucle.get("Array"))

    meter = g.call("Array_AddUnique", "/Script/Engine.KismetArrayLibrary",
                   2100, 3000, node_class="K2Node_CallArrayFunction")
    meter.pin("TargetArray", B.CAT_OBJECT,
              sub_object=B.cls("/Script/Engine.Actor"),
              container="Array", is_ref=True)
    meter.pin("NewItem", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    bucle.get("LoopBody").to(meter.exec_in)
    bucle.get("Array Element").to(meter.get("NewItem"))
    ed.enlazar("K2Node_VariableGet_8", "DetectedActors",
               [(meter.name, meter.get("TargetArray").id)])
    meter.get("TargetArray").links.append(Falso(pos_lista, "K2Node_VariableGet_8"))

    # al terminar el bucle, el Delay de siempre (que da tiempo a los hijos a
    # leer la lista antes de que el objeto se destruya)
    ed.enlazar("K2Node_CallFunction_13", "execute",
               [(bucle.name, bucle.get("Completed").id)])
    bucle.get("Completed").links.append(Falso(id_delay, "K2Node_CallFunction_13"))

    # ============================================================== (2)
    # Tras el impulso y el temporizador, el objeto sale del inventario.
    # OJO: NO se usa la variable `Thrower`. Existe y parece la buena, pero su
    # unico SET esta SUELTO en el grafo, sin cables: nunca se escribe, asi que
    # siempre vale None y toda esta rama se quedaba sin ejecutar (medido en
    # PIE: el objeto se desenganchaba pero no salia del inventario).
    # `Ownersito` si lo escribe la recogida, en BP_Item.Interact.
    lanzador = g.var_get("Ownersito", B.CAT_OBJECT, 900, 1400,
                         sub_object=B.cls("/Script/Engine.Actor"))

    comp = g.call("GetComponentByClass", "/Script/Engine.Actor", 1200, 1250,
                  pure=True)
    comp.pin("self", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    comp.pin("ComponentClass", B.CAT_CLASS,
             sub_object=B.cls("/Script/Engine.ActorComponent"),
             default=C_INTERACTION)
    comp.pin("ReturnValue", B.CAT_OBJECT, out=True,
             sub_object=B.cls(C_INTERACTION))
    lanzador.get("Ownersito").to(comp.get("self"))

    val = g.is_valid(1500, 1100, sub_object=B.cls(C_INTERACTION))
    comp.get("ReturnValue").to(val.get("InputObject"))
    id_timer = ed.pin_id("K2Node_CallFunction_4", "then")
    ed.enlazar("K2Node_CallFunction_4", "then",
               [(val.name, val.get("Exec").id)])
    val.get("Exec").links.append(Falso(id_timer, "K2Node_CallFunction_4"))

    soltar_ref = g.var_set_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                                  1850, 1100, sub_object=B.cls(C_ITEM))
    val.get("Is Valid").to(soltar_ref.exec_in)
    comp.get("ReturnValue").to(soltar_ref.get("self"))

    comp_inv = g.call("GetComponentByClass", "/Script/Engine.Actor", 1200, 1550,
                      pure=True)
    comp_inv.pin("self", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    comp_inv.pin("ComponentClass", B.CAT_CLASS,
                 sub_object=B.cls("/Script/Engine.ActorComponent"),
                 default=C_INVENTARY)
    comp_inv.pin("ReturnValue", B.CAT_OBJECT, out=True,
                 sub_object=B.cls(C_INVENTARY))
    lanzador.get("Ownersito").to(comp_inv.get("self"))

    val_inv = g.is_valid(2200, 1100, sub_object=B.cls(C_INVENTARY))
    soltar_ref.exec_out.to(val_inv.get("Exec"))
    comp_inv.get("ReturnValue").to(val_inv.get("InputObject"))

    baja = g.call("Ev_VaciarHueco", C_INVENTARY, 2550, 1100)
    baja.pin("self", B.CAT_OBJECT, sub_object=B.cls(C_INVENTARY))
    baja.pin("Tipo", B.CAT_BYTE, sub_object=B.obj("Enum", E_ITEMTYPE))
    val_inv.get("Is Valid").to(baja.exec_in)
    comp_inv.get("ReturnValue").to(baja.get("self"))
    mi_tipo = g.var_get("ItemType", B.CAT_BYTE, 2550, 1400,
                        sub_object=B.obj("Enum", E_ITEMTYPE))
    mi_tipo.get("ItemType").to(baja.get("Tipo"))

    g.comment("LA EXPLOSION ALCANZA A TODOS\\n"
              "SphereTraceSingleForObjects devolvia UN solo actor, asi que "
              "una granada en medio de cuatro soldados afectaba a uno. "
              "SphereOverlapActors devuelve todos.",
              1150, 2850, 1500, 300)
    g.comment("AL LANZAR, EL OBJETO SALE DEL INVENTARIO\\n"
              "Antes seguia registrado y EquippedItem seguia apuntandolo.",
              1150, 980, 1800, 260)

    texto = ed.texto() + g.render()
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(texto)
    print("escrito %s  (%d nodos)" % (SALIDA, texto.count("Begin Object Class=")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
