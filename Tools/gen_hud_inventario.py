# -*- coding: utf-8 -*-
"""
Genera el EventGraph de WBP_HUB_Inventary: que el HUD MUESTRE lo que llevas.

EL PROBLEMA, medido en PIE el 2026-09-15: el widget si esta en el viewport y
sus cuatro casillas se ven, pero **las diez imagenes estan en HIDDEN** y nada
las enciende nunca. Los iconos y sus texturas ya estaban hechos
(ARMA_CONVENCIONAL, METRALLETA, NUEVA_GRANADA, Bomba, Venenoo, NUEVO_ESCUDO,
BOTIQUIN...), pero el `EventGraph` del widget tenia exactamente tres nodos:
los override vacios de PreConstruct, Construct y Tick. O sea, cero logica.
Por eso "no aparece nada" y "los objetos no se ven relacionados".

LO QUE HACE AHORA, cada Tick:
  - lee `BPC_Inventary.InventoryItems` del jugador (4 huecos, uno por
    categoria: 0 arma, 1 lanzable, 2 proteccion, 3 curacion);
  - **enciende el icono del hueco ocupado y apaga el del vacio**, mirando
    QuantityOfItems > 0, que es justo lo que `AddItem` y `Ev_VaciarHueco`
    escriben;
  - **resalta el hueco seleccionado** con la rueda del raton, bajando la
    opacidad de los otros tres (`ValueOptionInventary` del personaje).

Por que en Tick y no por eventos: son cuatro casillas y una lectura de array;
el coste es despreciable, y asi el HUD refleja SIEMPRE el estado real sin
tener que enganchar recogida, soltado y lanzamiento por separado. Si alguno de
esos caminos cambia, el HUD sigue bien.

Uso:
    python Tools/gen_hud_inventario.py
    python Tools/paste_bp.py <WBP_HUB_Inventary> EventGraph <pegado>
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "Tools"))
import bpgen as B  # noqa: E402

SALIDA = os.path.join(RAIZ, "Tools", "bp_paste", "60_HUD_Inventario.txt")

C_INVENTARY = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
C_CHAR = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C"
S_INV = ("/Game/ThirdPerson/Components/InventoryData/"
         "S_InventoryItemStruct.S_InventoryItemStruct")
F_CANT = "QuantityOfItems_14_A2D5A7E347FE828C140D7A8803F2F6FA"
F_CLASE = "ItemClass_17_525F5B33449D92EF0134CBB90F9F2E2A"
C_ITEM = ("/Game/ThirdPerson/Blueprints/Interactables/"
          "FixedInteractables/BP_Item.BP_Item_C")

UMG_WIDGET = "/Script/UMG.Widget"
E_VIS = "/Script/UMG.ESlateVisibility"
MATH = "/Script/Engine.KismetMathLibrary"

# (indice del hueco, SizeBox del hueco, Image del icono). Los nombres son los
# reales del arbol del widget, leidos del export T3D: las cuatro casillas ya
# venian nombradas por categoria y marcadas como variable.
HUECOS = [
    (0, "Arm", "IMG-ConvencionalGun"),
    (1, "Throwable", "IMG-Grenade"),
    (2, "Shield", "IMG-BulletproofShield"),
    (3, "FirstAidKit", "IMG-FirstAidKit"),
]

OPACO = "1.000000"      # el hueco seleccionado
TENUE = "0.350000"      # los demas


def main():
    g = B.Graph("hudinv", "HUD del inventario: encender el icono de cada "
                          "hueco ocupado y resaltar el seleccionado.")

    # --- cabecera: de donde salen los datos -------------------------------
    # OJO: en UUserWidget el evento se llama "Tick", no "ReceiveTick" como en
    # Actor. Con el nombre de Actor el nodo se pega igual y compila, pero no
    # se dispara nunca.
    tick = g.event("Tick", "/Script/UMG.UserWidget", -1700, 0)

    pawn = g.call("GetOwningPlayerPawn", "/Script/UMG.UserWidget", -1700, 320,
                  pure=True)
    pawn.pin("ReturnValue", B.CAT_OBJECT, out=True,
             sub_object=B.cls("/Script/Engine.Pawn"))

    comp = g.call("GetComponentByClass", "/Script/Engine.Actor", -1380, 320,
                  pure=True)
    comp.pin("self", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    comp.pin("ComponentClass", B.CAT_CLASS,
             sub_object=B.cls("/Script/Engine.ActorComponent"),
             default=C_INVENTARY)
    comp.pin("ReturnValue", B.CAT_OBJECT, out=True,
             sub_object=B.cls(C_INVENTARY))
    pawn.get("ReturnValue").to(comp.get("self"))

    val = g.is_valid(-1050, 0, sub_object=B.cls(C_INVENTARY))
    tick.exec_out.to(val.get("Exec"))
    comp.get("ReturnValue").to(val.get("InputObject"))

    # el indice seleccionado vive en el personaje: hace falta el cast
    cast = g.cast(C_CHAR, -750, 0)
    val.get("Is Valid").to(cast.exec_in)
    pawn.get("ReturnValue").to(cast.get("Object"))

    seleccion = g.var_get_target("ValueOptionInventary", B.CAT_INT, C_CHAR,
                                 -750, 380)
    cast.get("AsTarget").to(seleccion.get("self"))

    lista = g.var_get_target("InventoryItems", B.CAT_STRUCT, C_INVENTARY,
                             -750, 520, sub_object=B.obj("ScriptStruct", S_INV),
                             container="Array")
    comp.get("ReturnValue").to(lista.get("self"))

    seq = g.node_sequence(-420, 0, n=4)
    cast.exec_out.to(seq.exec_in)

    # --- un bloque por hueco ----------------------------------------------
    for indice, caja, icono in HUECOS:
        y = indice * 700

        # 1) ¿esta ocupado? Se mira **ItemClass**, NO QuantityOfItems.
        #    TRAMPA medida en PIE: el Array_Resize de BeginPlay crea los cuatro
        #    huecos con el VALOR POR DEFECTO DEL STRUCT, y ahi QuantityOfItems
        #    vale 1. O sea que con el inventario vacio los cuatro huecos dicen
        #    "tengo 1" y los cuatro iconos se encendian. ItemClass, en cambio,
        #    es None en un hueco recien creado o vaciado, y apunta al item real
        #    cuando lo recoges: esa si es la marca buena.
        leer = B.Node(g, "K2Node_GetArrayItem",
                      "K2Node_GetArrayItem_hud%d" % indice, -120, y + 240)
        leer.pin("Array", B.CAT_STRUCT, sub_object=B.obj("ScriptStruct", S_INV),
                 container="Array")
        leer.pin("Dimension 1", B.CAT_INT, default=str(indice))
        leer.pin("Output", B.CAT_STRUCT, out=True,
                 sub_object=B.obj("ScriptStruct", S_INV))
        lista.get("InventoryItems").to(leer.get("Array"))

        romper = g.break_struct(S_INV, "S_InventoryItemStruct", 180, y + 240)
        romper.pin(F_CLASE, B.CAT_OBJECT, out=True, sub_object=B.cls(C_ITEM))
        leer.get("Output").to(romper.get("S_InventoryItemStruct"))

        hay = g.call("IsValid", "/Script/Engine.KismetSystemLibrary",
                     460, y + 240, pure=True)
        hay.pin("Object", B.CAT_OBJECT,
                sub_object=B.cls("/Script/CoreUObject.Object"))
        hay.pin("ReturnValue", B.CAT_BOOL, out=True)
        romper.get(F_CLASE).to(hay.get("Object"))

        rama = g.branch(760, y)
        seq.get("then_%d" % indice).to(rama.exec_in)
        hay.get("ReturnValue").to(rama.get("Condition"))

        def ver(x, yy, estado):
            n = g.call("SetVisibility", UMG_WIDGET, x, yy)
            n.pin("self", B.CAT_OBJECT, sub_object=B.cls(UMG_WIDGET))
            n.pin("InVisibility", B.CAT_BYTE,
                  sub_object=B.obj("Enum", E_VIS), default=estado)
            img = g.var_get(icono, B.CAT_OBJECT, x, yy + 190,
                            sub_object=B.cls("/Script/UMG.Image"))
            img.get(icono).to(n.get("self"))
            return n

        encender = ver(1060, y, "Visible")
        apagar = ver(1060, y + 380, "Hidden")
        rama.get("then").to(encender.exec_in)
        rama.get("else").to(apagar.exec_in)

        # 2) ¿es el hueco seleccionado? Se resalta bajando la opacidad de los
        #    otros tres, que se ve de un vistazo y no necesita ningun asset.
        igual = g.call("EqualEqual_IntInt", MATH, 1400, y + 240, pure=True)
        igual.pin("A", B.CAT_INT)
        igual.pin("B", B.CAT_INT, default=str(indice))
        igual.pin("ReturnValue", B.CAT_BOOL, out=True)
        seleccion.get("ValueOptionInventary").to(igual.get("A"))

        rama2 = g.branch(1700, y)
        encender.exec_out.to(rama2.exec_in)
        apagar.exec_out.to(rama2.exec_in)
        igual.get("ReturnValue").to(rama2.get("Condition"))

        def opacidad(x, yy, v):
            n = g.call("SetRenderOpacity", UMG_WIDGET, x, yy)
            n.pin("self", B.CAT_OBJECT, sub_object=B.cls(UMG_WIDGET))
            n.pin("InOpacity", B.CAT_REAL, sub="float", default=v)
            box = g.var_get(caja, B.CAT_OBJECT, x, yy + 190,
                            sub_object=B.cls("/Script/UMG.SizeBox"))
            box.get(caja).to(n.get("self"))
            return n

        rama2.get("then").to(opacidad(2020, y, OPACO).exec_in)
        rama2.get("else").to(opacidad(2020, y + 380, TENUE).exec_in)

    g.comment("HUD DEL INVENTARIO\\n"
              "Las diez imagenes del widget estaban en HIDDEN y nada las "
              "encendia: el EventGraph tenia tres nodos, los override vacios "
              "de PreConstruct, Construct y Tick. Aqui se enciende el icono "
              "del hueco ocupado y se resalta el seleccionado.",
              -1750, -300, 4200, 320,
              color="(R=0.000000,G=0.120000,B=0.180000,A=0.500000)")

    g.save(SALIDA)
    print("escrito %s  (%d nodos)" % (SALIDA, len(g.nodes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
