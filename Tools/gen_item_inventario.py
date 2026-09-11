# -*- coding: utf-8 -*-
"""
Genera el EventGraph completo de BP_Item: recogida + alta en el inventario.

Que arregla (todo medido sobre los grafos reales el 2026-09-11):

 1. **El eslabon roto de la fusion.** El personaje alimentaba `EquippedItem`
    desde un pin `Item` del nodo `Interact` que ya no existe: la rama de
    desarrollo le quito la salida a `BPI_Interactable.Interact` el
    2026-08-31. El pin quedo huerfano y compila en verde, asi que
    `EquippedItem` era SIEMPRE None: atacar imprimia "ALGO ESTA FALLANDO...",
    y como `SetPointingState` se llamaba sobre ese None, `IsPointing` nunca
    se ponia a true -- y lanzar exige apuntar, asi que lanzar tampoco
    funcionaba nunca. Ahora lo escribe el propio item, sobre el componente:
    `BPC_Interaction.EquippedItem = Self`.

 2. **`AddItem` no se llamaba desde ningun sitio del proyecto.** El array
    `InventoryItems` (4 huecos, uno por categoria) se creaba vacio y se
    quedaba vacio. Ahora la recogida da de alta el item.

 3. `Array_Add` en vez de `Array_AddUnique` al entrar en el radio: cada
    entrada y salida del trigger metia un duplicado en `InteractablesInRange`.

 4. No habia **End Overlap**: al alejarte, el item seguia en la lista de
    interactuables para siempre.

 5. `SetCollisionEnabled` tenia DOS cables en el pin de entrada `self`
    (Sphere y StaticMesh). Un pin de datos de entrada solo admite uno, asi
    que una de las dos colisiones no se desactivaba nunca. Ahora son dos
    llamadas encadenadas.

Uso:
    python Tools/gen_item_inventario.py            (escribe el pegado)
    python Tools/paste_bp.py <BP_Item> EventGraph <pegado> --vaciar
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "Tools"))

import bpgen as B          # noqa: E402
import t3d_edit            # noqa: E402

EXPORT = os.path.join(RAIZ, "Saved", "T3D_BP_Item.copy")
SALIDA = os.path.join(RAIZ, "Tools", "bp_paste", "51_Item_EventGraph.txt")

C_INTERACTION = "/Game/ThirdPerson/Components/BPC_Interaction.BPC_Interaction_C"
C_INVENTARY = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
C_ITEM = "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item.BP_Item_C"
E_ITEMTYPE = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
              "InformationItem/E_ItemType.E_ItemType")
S_INV = ("/Game/ThirdPerson/Components/InventoryData/"
         "S_InventoryItemStruct.S_InventoryItemStruct")

# Nombres reales de los campos del struct (los del exportador, con su GUID).
F_NOMBRE = "ItemName_11_B8B88FF84E0D450B45780B8FBCF9B473"
F_TIPO = "ItemType_9_421CEC67424D1B7E30935DA04CE12B1E"
F_ICONO = "ItemIcon_8_513CFD9849DA9B9A4B7361B9095956E9"
F_CANT = "QuantityOfItems_14_A2D5A7E347FE828C140D7A8803F2F6FA"
F_CLASE = "ItemClass_17_525F5B33449D92EF0134CBB90F9F2E2A"


def main():
    ed = t3d_edit.Bloques(EXPORT, "EventGraph")
    g = B.Graph("iteminv")

    # ================================================================ (3)
    # Array_Add -> Array_AddUnique al entrar en el radio de interaccion.
    ed.propiedad("K2Node_CallArrayFunction_0",
                 r'MemberName="Array_Add"', 'MemberName="Array_AddUnique"')

    # ================================================================ (4)
    # Evento End Overlap: al salir del radio, el item se quita de la lista.
    # Se declaran solo los pines que se usan; K2Node_ComponentBoundEvent
    # reconstruye el resto desde la firma del delegado al pegar.
    ev_fin = B.Node(g, "K2Node_ComponentBoundEvent", "K2Node_CBE_FinOverlap",
                    -1800, 1100, {
                        "ComponentPropertyName": '"Sphere"',
                        "DelegatePropertyName": '"OnComponentEndOverlap"',
                        "DelegateOwnerClass":
                            "\"/Script/CoreUObject.Class'/Script/Engine.PrimitiveComponent'\"",
                        "EventReference":
                            '(MemberParent="/Script/CoreUObject.Package\'/Script/Engine\'",'
                            'MemberName="ComponentEndOverlapSignature__DelegateSignature")',
                        "CustomFunctionName":
                            '"BndEvt__BP_Item_Sphere_K2Node_CBE_FinOverlap_'
                            'ComponentEndOverlapSignature__DelegateSignature"',
                        "bInternalEvent": "True",
                        "bOverrideFunction": "False",
                    })
    ev_fin.pin("then", B.CAT_EXEC, out=True)
    p_otro = ev_fin.pin("OtherActor", B.CAT_OBJECT, out=True,
                        sub_object=B.cls("/Script/Engine.Actor"))

    # GetComponentByClass(OtherActor, BPC_Interaction) -- se clona el que ya
    # existe en el grafo para que los tipos de pin salgan exactos.
    ed.duplicar("K2Node_CallFunction_0", "K2Node_GetComp_Fin")
    ed.enlazar("K2Node_GetComp_Fin", "self",
               [(ev_fin.name, p_otro.id)])
    p_otro.links.append(_Falso(ed.pin_id("K2Node_GetComp_Fin", "self"),
                               "K2Node_GetComp_Fin"))

    val_fin = g.is_valid(-1400, 1100, sub_object=B.cls(C_INTERACTION))
    ev_fin.get("then").to(val_fin.get("Exec"))
    ed.enlazar("K2Node_GetComp_Fin", "ReturnValue",
               [(val_fin.name, val_fin.get("InputObject").id)])
    val_fin.get("InputObject").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Fin", "ReturnValue"), "K2Node_GetComp_Fin"))

    lista_fin = g.var_get_target("InteractablesInRange", B.CAT_OBJECT,
                                 C_INTERACTION, -1150, 1240,
                                 sub_object=B.cls("/Script/Engine.Actor"),
                                 container="Array")
    ed.enlazar("K2Node_GetComp_Fin", "ReturnValue",
               [(val_fin.name, val_fin.get("InputObject").id),
                (lista_fin.name, lista_fin.get("self").id)])
    lista_fin.get("self").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Fin", "ReturnValue"), "K2Node_GetComp_Fin"))

    quitar_fin = g.call("Array_RemoveItem", "/Script/Engine.KismetArrayLibrary",
                        -900, 1100, node_class="K2Node_CallArrayFunction")
    quitar_fin.pin("TargetArray", B.CAT_OBJECT,
                   sub_object=B.cls("/Script/Engine.Actor"),
                   container="Array", is_ref=True)
    quitar_fin.pin("Item", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    val_fin.get("Is Valid").to(quitar_fin.exec_in)
    lista_fin.get("InteractablesInRange").to(quitar_fin.get("TargetArray"))
    self_fin = g.self_node(-900, 1300)
    self_fin.get("self").to(quitar_fin.get("Item"))

    # ================================================================ (1)(2)
    # Tras SET Ownersito se abre un Sequence: una rama da de alta el item en
    # el inventario y lo equipa, la otra hace lo fisico (el Switch que ya
    # estaba). Con Sequence las dos ramas corren pase lo que pase; colgar el
    # alta del Switch la dejaria fuera para Protection y Curation.
    seq = g.node_sequence(-100, 1700, n=2)
    ed.enlazar("K2Node_VariableSet_0_iv", "then", [(seq.name, seq.get("execute").id)])
    seq.get("execute").links.append(
        _Falso(ed.pin_id("K2Node_VariableSet_0_iv", "then"), "K2Node_VariableSet_0_iv"))
    # then_1 -> el SwitchEnum que ya existe
    id_sw = ed.pin_id("K2Node_SwitchEnum_1_iv", "execute")
    ed.enlazar("K2Node_SwitchEnum_1_iv", "execute",
               [(seq.name, seq.get("then_1").id)])
    seq.get("then_1").links.append(_Falso(id_sw, "K2Node_SwitchEnum_1_iv"))

    # --- rama del alta en inventario -----------------------------------
    ed.duplicar("K2Node_CallFunction_0", "K2Node_GetComp_Inter")
    ed.duplicar("K2Node_CallFunction_0", "K2Node_GetComp_Inv")
    ed.valor("K2Node_GetComp_Inv", "ComponentClass", C_INVENTARY,
             clave="DefaultObject")
    ed.tipo_pin("K2Node_GetComp_Inv", "ReturnValue", B.cls(C_INVENTARY))

    owner = g.var_get("Ownersito", B.CAT_OBJECT, 100, 2050,
                      sub_object=B.cls("/Script/Engine.Actor"))
    for destino in ("K2Node_GetComp_Inter", "K2Node_GetComp_Inv"):
        ed.enlazar(destino, "self", [(owner.name, owner.get("Ownersito").id)])
        owner.get("Ownersito").links.append(
            _Falso(ed.pin_id(destino, "self"), destino))

    val_ci = g.is_valid(300, 1700, sub_object=B.cls(C_INTERACTION))
    seq.get("then_0").to(val_ci.get("Exec"))
    ed.enlazar("K2Node_GetComp_Inter", "ReturnValue",
               [(val_ci.name, val_ci.get("InputObject").id)])
    val_ci.get("InputObject").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Inter", "ReturnValue"), "K2Node_GetComp_Inter"))

    # SET BPC_Interaction.EquippedItem = Self   <- (1), el eslabon roto
    set_eq = g.var_set_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                              600, 1700, sub_object=B.cls(C_ITEM))
    val_ci.get("Is Valid").to(set_eq.exec_in)
    ed.enlazar("K2Node_GetComp_Inter", "ReturnValue",
               [(val_ci.name, val_ci.get("InputObject").id),
                (set_eq.name, set_eq.get("self").id)])
    set_eq.get("self").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Inter", "ReturnValue"), "K2Node_GetComp_Inter"))
    self_eq = g.self_node(600, 1900)
    self_eq.get("self").to(set_eq.get("EquippedItem"))

    # ...y el item deja de estar "en rango": ya lo llevas encima.
    lista_q = g.var_get_target("InteractablesInRange", B.CAT_OBJECT,
                               C_INTERACTION, 900, 1900,
                               sub_object=B.cls("/Script/Engine.Actor"),
                               container="Array")
    ed.enlazar("K2Node_GetComp_Inter", "ReturnValue",
               [(val_ci.name, val_ci.get("InputObject").id),
                (set_eq.name, set_eq.get("self").id),
                (lista_q.name, lista_q.get("self").id)])
    lista_q.get("self").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Inter", "ReturnValue"), "K2Node_GetComp_Inter"))

    quitar = g.call("Array_RemoveItem", "/Script/Engine.KismetArrayLibrary",
                    950, 1700, node_class="K2Node_CallArrayFunction")
    quitar.pin("TargetArray", B.CAT_OBJECT,
               sub_object=B.cls("/Script/Engine.Actor"),
               container="Array", is_ref=True)
    quitar.pin("Item", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    set_eq.exec_out.to(quitar.exec_in)
    lista_q.get("InteractablesInRange").to(quitar.get("TargetArray"))
    self_q = g.self_node(950, 2100)
    self_q.get("self").to(quitar.get("Item"))

    # AddItem(inventario, struct del item)   <- (2)
    val_inv = g.is_valid(1300, 1700, sub_object=B.cls(C_INVENTARY))
    quitar.exec_out.to(val_inv.get("Exec"))
    ed.enlazar("K2Node_GetComp_Inv", "ReturnValue",
               [(val_inv.name, val_inv.get("InputObject").id)])
    val_inv.get("InputObject").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Inv", "ReturnValue"), "K2Node_GetComp_Inv"))

    add = g.call("AddItem", C_INVENTARY, 1650, 1700)
    add.pin("self", B.CAT_OBJECT, sub_object=B.cls(C_INVENTARY))
    add.pin("Item", B.CAT_STRUCT, sub_object=B.obj("ScriptStruct", S_INV))
    val_inv.get("Is Valid").to(add.exec_in)
    ed.enlazar("K2Node_GetComp_Inv", "ReturnValue",
               [(val_inv.name, val_inv.get("InputObject").id),
                (add.name, add.get("self").id)])
    add.get("self").links.append(
        _Falso(ed.pin_id("K2Node_GetComp_Inv", "ReturnValue"), "K2Node_GetComp_Inv"))

    mk = g.make_struct(S_INV, 1350, 1950)
    mk.pin(F_NOMBRE, B.CAT_TEXT)
    mk.pin(F_TIPO, B.CAT_BYTE, sub_object=B.obj("Enum", E_ITEMTYPE))
    mk.pin(F_ICONO, B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Texture2D"))
    mk.pin(F_CANT, B.CAT_INT, default="1")
    mk.pin(F_CLASE, B.CAT_OBJECT, sub_object=B.cls(C_ITEM))
    mk.get("StructOut").to(add.get("Item"))

    # ItemName es string en BP_Item y text en el struct: hay que convertir.
    nom = g.var_get("ItemName", B.CAT_STRING, 900, 2250)
    conv = g.call("Conv_StringToText", "/Script/Engine.KismetTextLibrary",
                  1130, 2250, pure=True)
    conv.pin("InString", B.CAT_STRING)
    conv.pin("ReturnValue", B.CAT_TEXT, out=True)
    nom.get("ItemName").to(conv.get("InString"))
    conv.get("ReturnValue").to(mk.get(F_NOMBRE))

    tipo = g.var_get("ItemType", B.CAT_BYTE, 1130, 2400,
                     sub_object=B.obj("Enum", E_ITEMTYPE))
    tipo.get("ItemType").to(mk.get(F_TIPO))
    icono = g.var_get("ItemIcon", B.CAT_OBJECT, 1130, 2500,
                      sub_object=B.cls("/Script/Engine.Texture2D"))
    icono.get("ItemIcon").to(mk.get(F_ICONO))
    self_mk = g.self_node(1130, 2600)
    self_mk.get("self").to(mk.get(F_CLASE))

    # ================================================================ (5)
    # SetCollisionEnabled tenia dos cables en 'self'. Se deja el de la esfera
    # (que es la que dispara los overlaps y por tanto la que hay que callar al
    # coger el objeto) y la malla se apaga en una llamada nueva encadenada.
    id_malla = ed.pin_id("K2Node_Knot_6_iv", "OutputPin")
    ed.enlazar("K2Node_CallFunction_8_iv", "self",
               [("K2Node_Knot_4_iv", ed.pin_id("K2Node_Knot_4_iv", "OutputPin"))])
    ed.enlazar("K2Node_Knot_6_iv", "OutputPin", [])

    col2 = g.call("SetCollisionEnabled", "/Script/Engine.PrimitiveComponent",
                  2100, 1400)
    col2.pin("self", B.CAT_OBJECT,
             sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    col2.pin("NewType", B.CAT_BYTE,
             sub_object=B.obj("Enum", "/Script/Engine.ECollisionEnabled"),
             default="NoCollision")
    # SetCollisionEnabled_8 -> col2 -> el Print que ya estaba
    id_print = ed.pin_id("K2Node_CallFunction_4_iv", "execute")
    ed.enlazar("K2Node_CallFunction_8_iv", "then",
               [(col2.name, col2.get("execute").id)])
    col2.get("execute").links.append(
        _Falso(ed.pin_id("K2Node_CallFunction_8_iv", "then"), "K2Node_CallFunction_8_iv"))
    ed.enlazar("K2Node_CallFunction_4_iv", "execute",
               [(col2.name, col2.get("then").id)])
    col2.get("then").links.append(_Falso(id_print, "K2Node_CallFunction_4_iv"))
    ed.enlazar("K2Node_Knot_6_iv", "OutputPin",
               [(col2.name, col2.get("self").id)])
    col2.get("self").links.append(_Falso(id_malla, "K2Node_Knot_6_iv"))

    # -------------------------------------------------------------- salida
    g.comment("ALTA EN EL INVENTARIO Y EQUIPADO\\n"
              "Lo que faltaba: AddItem no se llamaba desde ningun sitio, y "
              "EquippedItem colgaba de un pin huerfano.",
              -150, 1600, 2100, 260)
    g.comment("SALIR DEL RADIO: el item deja de ser interactuable",
              -1850, 1020, 1200, 200)

    texto = ed.texto() + g.render()
    with open(SALIDA, "w", encoding="utf-8") as fh:
        fh.write(texto)
    print("escrito %s" % SALIDA)
    print("  nodos totales: %d" % texto.count("Begin Object Class="))
    return 0


class _Falso(object):
    """Pin de mentira: solo aporta nombre de nodo e id para que bpgen pueda
    escribir un LinkedTo hacia un nodo que viene del export (y que por tanto
    no es un objeto Pin de bpgen)."""

    def __init__(self, pin_id, nombre_nodo):
        self.id = pin_id
        self.node = type("N", (), {"name": nombre_nodo})()
        self.links = []


if __name__ == "__main__":
    sys.exit(main())
