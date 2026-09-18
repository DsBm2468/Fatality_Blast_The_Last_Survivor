# -*- coding: utf-8 -*-
"""
Genera el sistema de SOLTAR objetos (tecla F). Dos pegados:

  56_Interaction_Soltar.txt  -> BPC_Interaction: el evento Ev_SoltarEquipado
                                con TODA la logica. Anadidura pura.
  57_Char_DropInput.txt      -> BP_ThirdPersonCharacter: IA_Drop llama a ese
                                evento. Tres nodos.

POR QUE LA LOGICA VA EN EL COMPONENTE Y NO EN EL PERSONAJE
----------------------------------------------------------
Dos razones, y la segunda es la que importa:

 1. `BPC_Interaction` es quien posee `EquippedItem` e `InteractablesInRange`.
    La logica de soltar es suya.

 2. **Para poder PROBARLA.** La entrada de Enhanced Input no se puede invocar
    por reflexion, y la inyeccion de teclas no llega al viewport de PIE: se
    probo con keybd_event y con SendInput (scancode), y ni el movimiento (W)
    ni la pausa (P) surtian efecto, con la ventana enfocada y el raton
    capturado por el juego. Con la logica detras de un evento personalizado,
    el banco llama exactamente al mismo evento que llama la tecla, y lo que
    queda sin cubrir -- que F esta atada a ese evento -- se comprueba leyendo
    el grafo y el mapeo de entrada, que es verificable sin jugar.

    Ademas asi se evita la trampa del pegado: una llamada de CONTEXTO PROPIO
    a una funcion que aun no existe abre el modal "Arreglar referencias de
    funciones de contexto propio", que bloquea el pegado automatico. Llamando
    a un evento de OTRA clase (el componente) no sale el modal.

Que hace al soltar, si hay algo equipado:
  1. desengancha el item de la mano conservando su posicion en el mundo;
  2. le devuelve colision y fisica a la malla, para que caiga al suelo;
  3. le devuelve la colision a la esfera de deteccion -- que la recogida
     habia apagado --, para que el objeto vuelva a ser interactuable;
  4. lo mete otra vez en InteractablesInRange, asi se puede recoger de nuevo
     sin salir del radio y volver a entrar;
  5. lo da de baja del inventario con Ev_VaciarHueco(su categoria);
  6. deja EquippedItem a None. Va AL FINAL: todo lo anterior lo lee.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "Tools"))
import bpgen as B  # noqa: E402

SAL_COMP = os.path.join(RAIZ, "Tools", "bp_paste", "56_Interaction_Soltar.txt")
SAL_CHAR = os.path.join(RAIZ, "Tools", "bp_paste", "57_Char_DropInput.txt")

C_INTERACTION = "/Game/ThirdPerson/Components/BPC_Interaction.BPC_Interaction_C"
C_INVENTARY = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
C_ITEM = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
          "BP_Item.BP_Item_C")
E_ITEMTYPE = ("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/"
              "InformationItem/E_ItemType.E_ItemType")
IA_DROP = "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Drop.IA_Drop'"


def componente():
    """BPC_Interaction: el evento con la logica."""
    g = B.Graph("soltar", "SOLTAR EL OBJETO EQUIPADO")
    Y = 900

    ev = g.custom_event("Ev_SoltarEquipado", -1400, Y)

    def item(x, y):
        """Un get de EquippedItem propio del componente."""
        n = g.var_get("EquippedItem", B.CAT_OBJECT, x, y,
                      sub_object=B.cls(C_ITEM))
        return n.get("EquippedItem")

    val = g.is_valid(-1050, Y, sub_object=B.cls(C_ITEM))
    ev.exec_out.to(val.get("Exec"))
    item(-1400, Y + 260).to(val.get("InputObject"))

    # 1. soltar de la mano, dejandolo donde esta
    desenganchar = g.call("K2_DetachFromActor", "/Script/Engine.Actor", -700, Y)
    desenganchar.pin("self", B.CAT_OBJECT,
                     sub_object=B.cls("/Script/Engine.Actor"))
    for regla in ("LocationRule", "RotationRule", "ScaleRule"):
        desenganchar.pin(regla, B.CAT_BYTE,
                         sub_object=B.obj("Enum", "/Script/Engine.EDetachmentRule"),
                         default="KeepWorld")
    val.get("Is Valid").to(desenganchar.exec_in)
    item(-700, Y + 260).to(desenganchar.get("self"))

    # 2. la malla recupera colision y fisica: el objeto cae
    malla = g.var_get_target("StaticMesh", B.CAT_OBJECT, C_ITEM, -350, Y + 300,
                             sub_object=B.cls("/Script/Engine.StaticMeshComponent"))
    item(-350, Y + 460).to(malla.get("self"))

    col_malla = g.call("SetCollisionEnabled", "/Script/Engine.PrimitiveComponent",
                       -350, Y)
    col_malla.pin("self", B.CAT_OBJECT,
                  sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    col_malla.pin("NewType", B.CAT_BYTE,
                  sub_object=B.obj("Enum", "/Script/Engine.ECollisionEnabled"),
                  default="QueryAndPhysics")
    desenganchar.exec_out.to(col_malla.exec_in)
    malla.get("StaticMesh").to(col_malla.get("self"))

    fisica = g.call("SetSimulatePhysics", "/Script/Engine.PrimitiveComponent",
                    0, Y)
    fisica.pin("self", B.CAT_OBJECT,
               sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    fisica.pin("bSimulate", B.CAT_BOOL, default="true")
    col_malla.exec_out.to(fisica.exec_in)
    malla.get("StaticMesh").to(fisica.get("self"))

    # 3. la esfera vuelve a detectar (la recogida la habia apagado)
    esfera = g.var_get_target("Sphere", B.CAT_OBJECT, C_ITEM, 350, Y + 300,
                              sub_object=B.cls("/Script/Engine.SphereComponent"))
    item(350, Y + 460).to(esfera.get("self"))

    col_esfera = g.call("SetCollisionEnabled", "/Script/Engine.PrimitiveComponent",
                        350, Y)
    col_esfera.pin("self", B.CAT_OBJECT,
                   sub_object=B.cls("/Script/Engine.PrimitiveComponent"))
    col_esfera.pin("NewType", B.CAT_BYTE,
                   sub_object=B.obj("Enum", "/Script/Engine.ECollisionEnabled"),
                   default="QueryOnly")
    fisica.exec_out.to(col_esfera.exec_in)
    esfera.get("Sphere").to(col_esfera.get("self"))

    # 4. vuelve a la lista de interactuables
    lista = g.var_get("InteractablesInRange", B.CAT_OBJECT, 700, Y + 300,
                      sub_object=B.cls("/Script/Engine.Actor"), container="Array")
    volver = g.call("Array_AddUnique", "/Script/Engine.KismetArrayLibrary",
                    700, Y, node_class="K2Node_CallArrayFunction")
    volver.pin("TargetArray", B.CAT_OBJECT,
               sub_object=B.cls("/Script/Engine.Actor"),
               container="Array", is_ref=True)
    volver.pin("NewItem", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    col_esfera.exec_out.to(volver.exec_in)
    lista.get("InteractablesInRange").to(volver.get("TargetArray"))
    item(700, Y + 460).to(volver.get("NewItem"))

    # 5. baja en el inventario del propietario
    duenyo = g.call("GetOwner", "/Script/Engine.ActorComponent", 1050, Y + 300,
                    pure=True)
    duenyo.pin("self", B.CAT_OBJECT,
               sub_object=B.cls("/Script/Engine.ActorComponent"))
    duenyo.pin("ReturnValue", B.CAT_OBJECT, out=True,
               sub_object=B.cls("/Script/Engine.Actor"))
    yo = g.self_node(1050, Y + 460)
    yo.get("self").to(duenyo.get("self"))

    inv = g.call("GetComponentByClass", "/Script/Engine.Actor", 1400, Y + 300,
                 pure=True)
    inv.pin("self", B.CAT_OBJECT, sub_object=B.cls("/Script/Engine.Actor"))
    inv.pin("ComponentClass", B.CAT_CLASS,
            sub_object=B.cls("/Script/Engine.ActorComponent"),
            default=C_INVENTARY)
    inv.pin("ReturnValue", B.CAT_OBJECT, out=True,
            sub_object=B.cls(C_INVENTARY))
    duenyo.get("ReturnValue").to(inv.get("self"))

    val_inv = g.is_valid(1050, Y, sub_object=B.cls(C_INVENTARY))
    volver.exec_out.to(val_inv.get("Exec"))
    inv.get("ReturnValue").to(val_inv.get("InputObject"))

    baja = g.call("Ev_VaciarHueco", C_INVENTARY, 1400, Y)
    baja.pin("self", B.CAT_OBJECT, sub_object=B.cls(C_INVENTARY))
    baja.pin("Tipo", B.CAT_BYTE, sub_object=B.obj("Enum", E_ITEMTYPE))
    val_inv.get("Is Valid").to(baja.exec_in)
    inv.get("ReturnValue").to(baja.get("self"))

    tipo = g.var_get_target("ItemType", B.CAT_BYTE, C_ITEM, 1400, Y + 620,
                            sub_object=B.obj("Enum", E_ITEMTYPE))
    item(1400, Y + 780).to(tipo.get("self"))
    tipo.get("ItemType").to(baja.get("Tipo"))

    # 6. aviso en pantalla: es el instrumento de medida (las variables de PIE
    #    se revierten, el log no)
    nombre = g.var_get_target("ItemName", B.CAT_STRING, C_ITEM, 1750, Y + 300)
    item(1750, Y + 460).to(nombre.get("self"))
    junta = g.call("Concat_StrStr", "/Script/Engine.KismetStringLibrary",
                   1750, Y + 180, pure=True)
    junta.pin("A", B.CAT_STRING, default="SOLTADO: ")
    junta.pin("B", B.CAT_STRING)
    junta.pin("ReturnValue", B.CAT_STRING, out=True)
    nombre.get("ItemName").to(junta.get("B"))

    aviso = g.call("PrintString", "/Script/Engine.KismetSystemLibrary", 1750, Y)
    aviso.pin("InString", B.CAT_STRING)
    aviso.pin("Duration", B.CAT_REAL, sub="double", default="3.000000")
    aviso.pin("TextColor", B.CAT_STRUCT,
              sub_object=B.obj("ScriptStruct", "/Script/CoreUObject.LinearColor"),
              default="(R=1.000000,G=0.800000,B=0.000000,A=1.000000)")
    baja.exec_out.to(aviso.exec_in)
    junta.get("ReturnValue").to(aviso.get("InString"))

    # 7. y lo ultimo, soltar la referencia
    limpiar = g.var_set("EquippedItem", B.CAT_OBJECT, 2150, Y,
                        sub_object=B.cls(C_ITEM))
    aviso.exec_out.to(limpiar.exec_in)

    g.comment("SOLTAR EL OBJETO EQUIPADO\\n"
              "La logica vive aqui, en el componente que posee EquippedItem, "
              "para que la pueda llamar tanto la tecla F como el banco de "
              "pruebas: la entrada de Enhanced Input no se puede invocar por "
              "reflexion y las teclas inyectadas no llegan al viewport de PIE.",
              -1450, Y - 320, 3900, 1300,
              color="(R=0.150000,G=0.080000,B=0.000000,A=0.500000)")
    g.save(SAL_COMP)
    print("escrito %s  (%d nodos)" % (SAL_COMP, len(g.nodes)))


def personaje():
    """BP_ThirdPersonCharacter: la tecla F llama al evento del componente."""
    g = B.Graph("dropin", "")
    Y = 5200
    ia = g.input_action(IA_DROP, -1600, Y)
    comp = g.var_get("BPC_Interaction", B.CAT_OBJECT, -1600, Y + 400,
                     sub_object=B.cls(C_INTERACTION))
    llamar = g.call("Ev_SoltarEquipado", C_INTERACTION, -1200, Y)
    llamar.pin("self", B.CAT_OBJECT, sub_object=B.cls(C_INTERACTION))
    ia.get("Started").to(llamar.exec_in)
    comp.get("BPC_Interaction").to(llamar.get("self"))
    g.comment("SOLTAR (F): la logica esta en BPC_Interaction.Ev_SoltarEquipado",
              -1650, Y - 200, 1300, 800,
              color="(R=0.150000,G=0.080000,B=0.000000,A=0.500000)")
    g.save(SAL_CHAR)
    print("escrito %s  (%d nodos)" % (SAL_CHAR, len(g.nodes)))


if __name__ == "__main__":
    componente()
    personaje()
