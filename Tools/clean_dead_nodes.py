# -*- coding: utf-8 -*-
"""
Barre por script los nodos muertos que estan AISLADOS (sin un solo cable) y,
en BP_ThirdPersonCharacter, las variables basura.

Se corre dentro del editor:
    "<engine>/.../python.exe" Tools/ue_remote.py Tools/clean_dead_nodes.py

Que NO toca, a proposito:
  * BP_TestDamageDealer  -> su TakeDamage tiene un K2Node_FunctionResult
    inalcanzable. Sale como muerto pero DEFINE LA SALIDA de la funcion:
    borrarlo rompe la firma.
  * BP_SubmachineGun, BP_Bomb, BP_Grunt, BPC_Inventary -> su codigo muerto es
    la segunda familia de recogida y la cadena de muerte vieja. Puede que sea
    un fallo (que el item no se pueda coger) y no basura. Decision de Walter.

`remove_unused_variables` se lleva por delante TODAS las variables sin cablear
del Blueprint, no las que le pidas. En BP_ThirdPersonCharacter las unicas sin
usar son las cuatro basura (`NewVar`, `Object in Hand`, `Root Component`,
`Root Component_0`), asi que ahi es seguro; en los demas Blueprints NO lo es,
porque sus variables sin usar son mandos de diseno expuestos.
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary

NODOS = [
    "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter",
    "/Game/ThirdPerson/Components/BPC_Curation",
    "/Game/ThirdPerson/Components/BPC_ProtectionSystem",
    "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item",
    "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item_Weapon_Base",
    "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item_Throwable_Base",
    "/Game/ThirdPerson/Blueprints/WBP/HUB/WBP_HUB_LifeBar",
]
VARIABLES = ["/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"]

print("=" * 66)
print(" LIMPIEZA DE NODOS AISLADOS")
print("=" * 66)
# remove_unused_nodes SOLO se lleva los nodos sin un solo cable. Al quitarlos
# quedan otros huerfanos, asi que se repite hasta que una pasada no cambie
# nada. Lo que siga conectado entre si, aunque sea inalcanzable, no lo coge:
# para eso habria que romper pines, y UEdGraphPin no es un UObject.
PASADAS = 4
for ruta in NODOS:
    bp = EAL.load_asset(ruta)
    if bp is None:
        print("  NO EXISTE %s" % ruta)
        continue
    for i in range(PASADAS):
        BEL.remove_unused_nodes(bp)
        BEL.compile_blueprint(bp)
    print("  barrido   %-28s (%d pasadas)" % (ruta.rsplit("/", 1)[-1], PASADAS))

print("\n LIMPIEZA DE VARIABLES SIN USAR")
for ruta in VARIABLES:
    bp = EAL.load_asset(ruta)
    BEL.remove_unused_variables(bp)
    BEL.compile_blueprint(bp)
    print("  barrido   %s" % ruta.rsplit("/", 1)[-1])

print("\n GUARDANDO")
for ruta in set(NODOS) | set(VARIABLES):
    print("  %s  %s" % ("OK   " if EAL.save_asset(ruta) else "FALLO",
                        ruta.rsplit("/", 1)[-1]))
print("\nHECHO")
