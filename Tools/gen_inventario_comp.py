# -*- coding: utf-8 -*-
"""
Genera el pegado de BPC_Inventary: el evento que VACIA un hueco.

El inventario que venia de main sabia dar de alta (AddItem) pero no dar de
baja, asi que soltar o lanzar un objeto lo dejaba registrado para siempre.
`Ev_VaciarHueco(Tipo)` es el simetrico de `AddItem`: traduce la categoria al
mismo indice (0 arma, 1 lanzable, 2 proteccion, 3 curacion) y escribe en ese
hueco un struct vacio con QuantityOfItems = 0, que es justo lo que `AddItem`
interpreta como "casilla libre".

Es una ANADIDURA pura al EventGraph: no toca ningun nodo existente, asi que
se puede pegar sin vaciar el grafo.

Uso:
    python Tools/gen_inventario_comp.py
    python Tools/paste_bp.py /Game/ThirdPerson/Components/BPC_Inventary \
        EventGraph Tools/bp_paste/52_Inventary_VaciarHueco.txt
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "Tools"))
import bpgen as B  # noqa: E402

SALIDA = os.path.join(RAIZ, "Tools", "bp_paste", "52_Inventary_VaciarHueco.txt")

E_ITEMTYPE = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
              "InformationItem/E_ItemType.E_ItemType")
E_ITEMTYPE_LARGO = "/Script/Engine.UserDefinedEnum'%s'" % E_ITEMTYPE
S_INV = ("/Game/ThirdPerson/Components/InventoryData/"
         "S_InventoryItemStruct.S_InventoryItemStruct")
C_ITEM = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
          "BP_Item.BP_Item_C")

F_NOMBRE = "ItemName_11_B8B88FF84E0D450B45780B8FBCF9B473"
F_TIPO = "ItemType_9_421CEC67424D1B7E30935DA04CE12B1E"
F_ICONO = "ItemIcon_8_513CFD9849DA9B9A4B7361B9095956E9"
F_CANT = "QuantityOfItems_14_A2D5A7E347FE828C140D7A8803F2F6FA"
F_CLASE = "ItemClass_17_525F5B33449D92EF0134CBB90F9F2E2A"

# Los nombres internos NO siguen el orden de las entradas: se leyeron del
# DisplayNameMap del propio enum.
#   NewEnumerator0 None | 3 Weapon | 4 Throwable | 5 Protection | 6 Curation
#   NewEnumerator8 Interactive_Object | 9 Temporal_PickUp_Object
CATEGORIAS = [("NewEnumerator3", 0, "Weapon"),
              ("NewEnumerator4", 1, "Throwable"),
              ("NewEnumerator5", 2, "Protection"),
              ("NewEnumerator6", 3, "Curation")]
ENTRADAS = ["NewEnumerator0", "NewEnumerator3", "NewEnumerator4",
            "NewEnumerator5", "NewEnumerator6", "NewEnumerator8",
            "NewEnumerator9"]


def main():
    g = B.Graph("invvac", "Vaciar un hueco del inventario")

    ev = g.custom_event("Ev_VaciarHueco", -600, 2200,
                        params=[("Tipo", B.CAT_BYTE,
                                 B.obj("Enum", E_ITEMTYPE), E_ITEMTYPE_LARGO)])

    sw = g.switch_enum(E_ITEMTYPE, ENTRADAS, -250, 2200)
    ev.exec_out.to(sw.exec_in)
    ev.get("Tipo").to(sw.get("Selection"))

    # Un SET IndexTarget por categoria; los cuatro desembocan en el mismo
    # Array_Set (un pin de EJECUCION de entrada si admite varios cables).
    poner = g.call("Array_Set", "/Script/Engine.KismetArrayLibrary", 600, 2200,
                   node_class="K2Node_CallArrayFunction")
    poner.pin("TargetArray", B.CAT_STRUCT,
              sub_object=B.obj("ScriptStruct", S_INV),
              container="Array", is_ref=True)
    poner.pin("Index", B.CAT_INT)
    poner.pin("Item", B.CAT_STRUCT, sub_object=B.obj("ScriptStruct", S_INV))
    poner.pin("bSizeToFit", B.CAT_BOOL, default="false")

    for i, (entrada, indice, _nombre) in enumerate(CATEGORIAS):
        s = g.var_set("IndexTarget", B.CAT_INT, 120, 2000 + i * 180)
        s.get("IndexTarget").default = str(indice)
        sw.get(entrada).to(s.exec_in)
        s.exec_out.to(poner.exec_in)

    lista = g.var_get("InventoryItems", B.CAT_STRUCT, 300, 2500,
                      sub_object=B.obj("ScriptStruct", S_INV), container="Array")
    lista.get("InventoryItems").to(poner.get("TargetArray"))
    idx = g.var_get("IndexTarget", B.CAT_INT, 300, 2620)
    idx.get("IndexTarget").to(poner.get("Index"))

    # Hueco vacio = QuantityOfItems 0. Es lo que AddItem mira para decidir si
    # la casilla esta libre.
    vacio = g.make_struct(S_INV, 300, 2720)
    vacio.pin(F_NOMBRE, B.CAT_TEXT, default="")
    vacio.pin(F_TIPO, B.CAT_BYTE, sub_object=B.obj("Enum", E_ITEMTYPE),
              default="NewEnumerator0")
    vacio.pin(F_ICONO, B.CAT_OBJECT,
              sub_object=B.cls("/Script/Engine.Texture2D"))
    # TRAMPA: un MakeStruct REPONE el valor por defecto de sus pines al
    # pegarlo (los toma del struct, donde QuantityOfItems vale 1), asi que
    # escribir "0" en el pin no sirve de nada y el hueco "vacio" salia con
    # cantidad 1. Hay que metérselo desde un nodo: el default de un pin de
    # K2Node_CallFunction si se respeta.
    vacio.pin(F_CANT, B.CAT_INT)
    cero = g.call("MakeLiteralInt", "/Script/Engine.KismetSystemLibrary",
                  60, 2900, pure=True)
    cero.pin("Value", B.CAT_INT, default="0")
    cero.pin("ReturnValue", B.CAT_INT, out=True)
    cero.get("ReturnValue").to(vacio.get(F_CANT))
    vacio.pin(F_CLASE, B.CAT_OBJECT, sub_object=B.cls(C_ITEM))
    vacio.get("StructOut").to(poner.get("Item"))

    g.comment("VACIAR UN HUECO\\nSimetrico de AddItem: soltar o lanzar un "
              "objeto tiene que darlo de baja.", -650, 1900, 1500, 240)

    g.save(SALIDA)
    print("escrito %s  (%d nodos)" % (SALIDA, len(g.nodes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
