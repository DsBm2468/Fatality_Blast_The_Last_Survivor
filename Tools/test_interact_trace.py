# -*- coding: utf-8 -*-
"""
Comprueba que el trazo de deteccion del Tick sigue a la CAMARA y no al cuerpo.

La prueba de verdad: poner al jugador delante de un item que esta EN EL SUELO,
mirando al frente (horizontal) y luego mirando hacia abajo. Con el trazo viejo
(GetActorForwardVector) ActiveInteractable no cambiaba nunca; con el nuevo solo
se rellena al agachar la mirada.

Por tandas:
    printf horizontal > Tools/_modo.txt ; python Tools/ue_remote.py Tools/test_interact_trace.py
    printf abajo      > Tools/_modo.txt ; python Tools/ue_remote.py Tools/test_interact_trace.py
"""
import os
import unreal

UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

_dir = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_dir, "_modo.txt"), "r", encoding="utf-8") as fh:
        modo = fh.read().strip()
except Exception:
    modo = "horizontal"
print("### modo: %s" % modo)

w = UES.get_game_world()
if w is None:
    print("FALLO: PIE no esta corriendo")
    raise SystemExit

pj = unreal.GameplayStatics.get_player_character(w, 0)
pc = unreal.GameplayStatics.get_player_controller(w, 0)
todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)

# un item que este apoyado en el suelo
items = [a for a in todos
         if a.get_class().get_name() in ("BP_FirstAidKit_C",
                                         "BP_MunitionConventionalGun_C",
                                         "BP_ConventionalGun_C")]
if not items or pj is None:
    print("FALLO: no hay item o no hay jugador")
    raise SystemExit

lp = pj.get_actor_location()
item = min(items, key=lambda a: unreal.MathLibrary.vector_distance(
    a.get_actor_location(), lp))
li = item.get_actor_location()

# colocar al jugador a 130 UU en horizontal del item; el item queda POR DEBAJO
d = unreal.MathLibrary.normal(unreal.Vector(1.0, 0.0, 0.0))
destino = unreal.Vector(li.x + 130.0, li.y, li.z + 90.0)
pj.set_actor_location(destino, False, False)

if modo == "horizontal":
    # mirando al frente, en horizontal: el item esta por debajo del trazo
    rot = unreal.Rotator(0.0, 180.0, 0.0)
else:
    # mirando hacia abajo, hacia el item
    rot = unreal.MathLibrary.find_look_at_rotation(
        unreal.Vector(destino.x, destino.y, destino.z + 40.0), li)

if pc is not None:
    pc.set_control_rotation(rot)
pj.set_actor_rotation(unreal.Rotator(0.0, rot.yaw, 0.0), False)

real = pj.get_actor_location()
print("item     : %-28s (%.0f, %.0f, %.0f)"
      % (item.get_name(), li.x, li.y, li.z))
print("jugador  : (%.0f, %.0f, %.0f)   pedido (%.0f, %.0f, %.0f)"
      % (real.x, real.y, real.z, destino.x, destino.y, destino.z))
print("camara   : pitch=%.1f  yaw=%.1f" % (rot.pitch, rot.yaw))
print("desnivel : %.0f UU por debajo de los ojos" % (destino.z + 50.0 - li.z))

try:
    act = pj.get_editor_property("ActiveInteractable")
except Exception as e:
    print("no se pudo leer ActiveInteractable: %s" % e)
    act = None
print("")
print("ActiveInteractable = %s" % (act.get_name() if act else "None"))
if act is not None and act == item:
    print("  -> DETECTA el item")
elif act is None:
    print("  -> no detecta nada")
else:
    print("  -> detecta OTRA cosa")
