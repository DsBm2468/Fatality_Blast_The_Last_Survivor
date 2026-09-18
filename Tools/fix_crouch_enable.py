"""A-1a: habilitar el agachado en BP_ThirdPersonCharacter.

NavAgentProps.can_crouch esta en False a nivel de clase, asi que aunque se
enlace IA_Crouch el nodo Crouch no hace nada. El campo vive dentro de un
struct (FNavAgentProperties): no basta con set_editor_property sobre el campo,
hay que leer el struct, modificarlo y REASIGNARLO entero.

Idempotente. Acaba en PROBLEMAS: N.
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
RUTA = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"

problemas = 0
bp = EAL.load_asset(RUTA)
cdo = unreal.get_default_object(BEL.generated_class(bp))
cm = cdo.get_editor_property("character_movement")

nav = cm.get_editor_property("nav_agent_props")
print("ANTES  can_crouch:", nav.get_editor_property("can_crouch"))

if not nav.get_editor_property("can_crouch"):
    nav.set_editor_property("can_crouch", True)
    cm.set_editor_property("nav_agent_props", nav)   # reasignar el struct entero
    print("  -> can_crouch puesto a True")
else:
    print("  -> ya estaba en True, no se toca")

# Metricas del GDD (ya correctas, se comprueban por si acaso)
if abs(cm.get_editor_property("max_walk_speed_crouched") - 300.0) > 0.01:
    cm.set_editor_property("max_walk_speed_crouched", 300.0)
    print("  -> MaxWalkSpeedCrouched puesto a 300")

nav2 = cm.get_editor_property("nav_agent_props")
ok = nav2.get_editor_property("can_crouch")
print("DESPUES can_crouch:", ok)
if not ok:
    problemas += 1
    print("  !! no se aplico")

if EAL.save_asset(RUTA, only_if_is_dirty=False):
    print("Guardado", RUTA)
else:
    problemas += 1
    print("  !! no se pudo guardar")

print("PROBLEMAS:", problemas)
