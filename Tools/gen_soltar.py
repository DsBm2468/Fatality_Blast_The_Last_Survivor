# -*- coding: utf-8 -*-
"""
Genera el sistema de SOLTAR objetos (tecla F) para BP_ThirdPersonCharacter.

No existia nada: ni accion de entrada ni logica. El commit de main decia
"incluir opcion de soltar objetos en interaccion" como pendiente.

Lo que hace al pulsar F, si hay algo equipado:
  1. desengancha el item de la mano conservando su posicion en el mundo;
  2. le devuelve la colision y la fisica a la malla, para que caiga al suelo;
  3. le devuelve la colision a la esfera de deteccion -- que la recogida habia
     apagado -- para que el objeto vuelva a ser interactuable;
  4. lo vuelve a meter en InteractablesInRange, asi se puede recoger otra vez
     sin salir y volver a entrar al radio;
  5. lo da de baja del inventario con Ev_VaciarHueco(su categoria);
  6. deja EquippedItem a None.

Es una ANADIDURA pura al EventGraph del personaje: no toca ni un nodo de los
que ya habia, asi que se pega sin vaciar el grafo.

Uso:
    python Tools/gen_soltar.py
    python Tools/paste_bp.py /Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter \
        EventGraph Tools/bp_paste/54_Char_Soltar.txt
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "Tools"))
import bpgen as B  # noqa: E402

SALIDA = os.path.join(RAIZ, "Tools", "bp_paste", "54_Char_Soltar.txt")

C_INTERACTION = "/Game/ThirdPerson/Components/BPC_Interaction.BPC_Interaction_C"
C_INVENTARY = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
C_ITEM = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
          "BP_Item.BP_Item_C")
E_ITEMTYPE = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
              "InformationItem/E_ItemType.E_ItemType")
IA_DROP = "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Drop.IA_Drop'"

Y = 5200          # zona despejada del EventGraph del personaje


def main():
    g = B.Graph("soltar", "SOLTAR OBJETO (F)")

    ia = g.input_action(IA_DROP, -1600, Y)

    # El personaje tiene los componentes como variables, asi que no hace falta
    # GetComponentByClass.
    comp = g.var_get("BPC_Interaction", B.CAT_OBJECT, -1600, Y + 420,
                     sub_object=B.cls(C_INTERACTION))
    inv = g.var_get("BPC_Inventary", B.CAT_OBJECT, -1600, Y + 520,
                    sub_object=B.cls(C_INVENTARY))

    equipado = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                                -1250, Y + 300, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(equipado.get("self"))

    val = g.is_valid(-950, Y, sub_object=B.cls(C_ITEM))
    ia.get("Started").to(val.get("Exec"))
    equipado.get("EquippedItem").to(val.get("InputObject"))

    # 1. soltar de la mano, dejandolo donde esta
    desenganchar = g.call("K2_DetachFromActor", "/Script/Engine.Actor", -650, Y)
    desenganchar.pin("self", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    for regla in ("LocationRule", "RotationRule", "ScaleRule"):
        desenganchar.pin(regla, B.CAT_BYTE,
                         sub_object=B.obj("Enum", "/Script/Engine.EDetachmentRule"),
                         default="KeepWorld")
    val.get("Is Valid").to(desenganchar.exec_in)

    it1 = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                           -650, Y + 300, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(it1.get("self"))
    it1.get("EquippedItem").to(desenganchar.get("self"))

    # 2. la malla recupera colision y fisica: el objeto cae
    malla = g.var_get_target("StaticMesh", B.CAT_OBJECT, C_ITEM, -300, Y + 400,
                             sub_object=B.cls("/Script/Engine.StaticMeshComponent"))
    it2 = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                           -300, Y + 560, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(it2.get("self"))
    it2.get("EquippedItem").to(malla.get("self"))

    col_malla = g.call("SetCollisionEnabled", "/Script/Engine.PrimitiveComponent",
                       -300, Y)
    col_malla.pin("self", B.CAT_OBJECT,
                  sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    col_malla.pin("NewType", B.CAT_BYTE,
                  sub_object=B.obj("Enum", "/Script/Engine.ECollisionEnabled"),
                  default="QueryAndPhysics")
    desenganchar.exec_out.to(col_malla.exec_in)
    malla.get("StaticMesh").to(col_malla.get("self"))

    fisica = g.call("SetSimulatePhysics", "/Script/Engine.PrimitiveComponent",
                    50, Y)
    fisica.pin("self", B.CAT_OBJECT,
               sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    fisica.pin("bSimulate", B.CAT_BOOL, default="true")
    col_malla.exec_out.to(fisica.exec_in)
    malla.get("StaticMesh").to(fisica.get("self"))

    # 3. la esfera vuelve a detectar: la recogida la habia apagado
    esfera = g.var_get_target("Sphere", B.CAT_OBJECT, C_ITEM, 400, Y + 400,
                              sub_object=B.cls("/Script/Engine.SphereComponent"))
    it3 = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                           400, Y + 560, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(it3.get("self"))
    it3.get("EquippedItem").to(esfera.get("self"))

    col_esfera = g.call("SetCollisionEnabled", "/Script/Engine.PrimitiveComponent",
                        400, Y)
    col_esfera.pin("self", B.CAT_OBJECT,
                   sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    col_esfera.pin("NewType", B.CAT_BYTE,
                   sub_object=B.obj("Enum", "/Script/Engine.ECollisionEnabled"),
                   default="QueryOnly")
    fisica.exec_out.to(col_esfera.exec_in)
    esfera.get("Sphere").to(col_esfera.get("self"))

    # 4. vuelve a la lista de interactuables, para poder recogerlo de nuevo
    #    sin tener que salir del radio y entrar otra vez
    lista = g.var_get_target("InteractablesInRange", B.CAT_OBJECT, C_INTERACTION,
                             750, Y + 400, sub_object=B.cls("/Script/Engine.Actor"),
                             container="Array")
    comp.get("BPC_Interaction").to(lista.get("self"))
    volver = g.call("Array_AddUnique", "/Script/Engine.KismetArrayLibrary",
                    750, Y, node_class="K2Node_CallArrayFunction")
    volver.pin("TargetArray", B.CAT_OBJECT,
               sub_object=B.cls("/Script/Engine.Actor"),
               container="Array", is_ref=True)
    volver.pin("NewItem", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    col_esfera.exec_out.to(volver.exec_in)
    lista.get("InteractablesInRange").to(volver.get("TargetArray"))
    it4 = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                           750, Y + 560, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(it4.get("self"))
    it4.get("EquippedItem").to(volver.get("NewItem"))

    # 5. baja en el inventario
    baja = g.call("Ev_VaciarHueco", C_INVENTARY, 1150, Y)
    baja.pin("self", B.CAT_OBJECT, sub_object=B.cls(C_INVENTARY))
    baja.pin("Tipo", B.CAT_BYTE, sub_object=B.obj("Enum", E_ITEMTYPE))
    volver.exec_out.to(baja.exec_in)
    inv.get("BPC_Inventary").to(baja.get("self"))

    tipo = g.var_get_target("ItemType", B.CAT_BYTE, C_ITEM, 1150, Y + 400,
                            sub_object=B.obj("Enum", E_ITEMTYPE))
    it5 = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                           1150, Y + 560, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(it5.get("self"))
    it5.get("EquippedItem").to(tipo.get("self"))
    tipo.get("ItemType").to(baja.get("Tipo"))

    # 6. aviso en pantalla (es el instrumento de medida del banco de pruebas:
    #    las variables de PIE se revierten, el log no)
    nombre = g.var_get_target("ItemName", B.CAT_STRING, C_ITEM, 1500, Y + 400)
    it6 = g.var_get_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                           1500, Y + 560, sub_object=B.cls(C_ITEM))
    comp.get("BPC_Interaction").to(it6.get("self"))
    it6.get("EquippedItem").to(nombre.get("self"))

    junta = g.call("Concat_StrStr", "/Script/Engine.KismetStringLibrary",
                   1500, Y + 250, pure=True)
    junta.pin("A", B.CAT_STRING, default="SOLTADO: ")
    junta.pin("B", B.CAT_STRING)
    junta.pin("ReturnValue", B.CAT_STRING, out=True)
    nombre.get("ItemName").to(junta.get("B"))

    aviso = g.call("PrintString", "/Script/Engine.KismetSystemLibrary", 1500, Y)
    aviso.pin("InString", B.CAT_STRING)
    aviso.pin("Duration", B.CAT_REAL, sub="double", default="3.000000")
    aviso.pin("TextColor", B.CAT_STRUCT,
              sub_object=B.obj("ScriptStruct", "/Script/CoreUObject.LinearColor"),
              default="(R=1.000000,G=0.800000,B=0.000000,A=1.000000)")
    baja.exec_out.to(aviso.exec_in)
    junta.get("ReturnValue").to(aviso.get("InString"))

    # 7. ...y por ultimo se suelta la referencia. Va AL FINAL a proposito:
    #    todos los pasos anteriores leen EquippedItem.
    limpiar = g.var_set_target("EquippedItem", B.CAT_OBJECT, C_INTERACTION,
                               1900, Y, sub_object=B.cls(C_ITEM))
    aviso.exec_out.to(limpiar.exec_in)
    comp.get("BPC_Interaction").to(limpiar.get("self"))

    g.comment("SOLTAR OBJETO (F)\\n"
              "Desengancha, devuelve colision y fisica, lo vuelve a hacer "
              "interactuable, lo da de baja del inventario y libera "
              "EquippedItem (lo ultimo: todo lo anterior lo lee).",
              -1650, Y - 300, 3700, 1100,
              color="(R=0.150000,G=0.080000,B=0.000000,A=0.500000)")

    g.save(SALIDA)
    print("escrito %s  (%d nodos)" % (SALIDA, len(g.nodes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
