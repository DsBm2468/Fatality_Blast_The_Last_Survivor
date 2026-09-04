# -*- coding: utf-8 -*-
"""
Mide la IA ampliada en PIE: cacheo de coberturas, deteccion de apuntado,
reaccion acelerada, cobertura y aviso por radio.

Por tandas desde el shell (un time.sleep dentro del script remoto bloquea el
hilo del editor y PIE no llega a arrancar):

    printf preparar > Tools/_modo.txt ; python Tools/ue_remote.py Tools/test_ai_upgrade.py
    (esperar)
    printf apuntar  > Tools/_modo.txt ; python Tools/ue_remote.py Tools/test_ai_upgrade.py
    (esperar)
    printf medir    > Tools/_modo.txt ; python Tools/ue_remote.py Tools/test_ai_upgrade.py

Las escrituras a instancias de PIE se revierten solas, asi que el apuntado se
RE-APLICA en cada tanda y se vuelve a leer antes de juzgar nada.
"""
import os
import unreal

UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)

_dir = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_dir, "_modo.txt"), "r", encoding="utf-8") as fh:
        modo = fh.read().strip()
except Exception:
    modo = "medir"
print("### modo: %s" % modo)

w = UES.get_game_world()
if w is None:
    print("FALLO: no hay mundo de juego (PIE no esta corriendo)")
    raise SystemExit

todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
grunts = [a for a in todos if a.get_class().get_name() == "BP_Grunt_C"]
ctrls = [a for a in todos if a.get_class().get_name() == "BP_GruntAIController_C"]
covers = unreal.GameplayStatics.get_all_actors_with_tag(w, unreal.Name("Cover"))
pj = unreal.GameplayStatics.get_player_character(w, 0)
pc = unreal.GameplayStatics.get_player_controller(w, 0)

ESTADOS = ["Patrulla", "Sospecha", "Investiga", "COMBATE", "Busca", "Muerto"]


def idx(v):
    """get_editor_property sobre un byte-enum devuelve el OBJETO enum, no un
    int: int(v) revienta. El indice esta en .value."""
    try:
        return int(getattr(v, "value", v))
    except Exception:
        return -1


def nombre_estado(v):
    i = idx(v)
    return ESTADOS[i] if 0 <= i < len(ESTADOS) else str(v)


def ctrl_de(g):
    for c in ctrls:
        try:
            if c.get_editor_property("GruntPawn") == g:
                return c
        except Exception:
            pass
    return None


def objetivo():
    """El Grunt mas cercano al jugador."""
    if pj is None or not grunts:
        return None
    lp = pj.get_actor_location()
    return min(grunts, key=lambda g: unreal.MathLibrary.vector_distance(
        g.get_actor_location(), lp))


def apuntar_a(g):
    """Coloca al jugador a 700 UU del soldado y le apunta con la camara.
    Se re-aplica en cada tanda porque PIE revierte las escrituras."""
    lg = g.get_actor_location()
    lp = pj.get_actor_location()
    d = unreal.MathLibrary.normal(unreal.Vector(lp.x - lg.x, lp.y - lg.y, 0.0))
    destino = unreal.Vector(lg.x + d.x * 700.0, lg.y + d.y * 700.0, lg.z + 10.0)
    pj.set_actor_location(destino, False, False)
    mirar = unreal.MathLibrary.find_look_at_rotation(destino, lg)
    if pc is not None:
        pc.set_control_rotation(mirar)
    pj.set_actor_rotation(unreal.Rotator(0.0, mirar.yaw, 0.0), False)
    try:
        pj.set_editor_property("HaveGun", True)
    except Exception as e:
        print("   AVISO: no se pudo poner HaveGun (%s)" % e)
    return destino, mirar


def pinta(g, etiqueta=""):
    c = ctrl_de(g)
    if c is None:
        print("   %-14s (sin controlador)" % g.get_name()[:14])
        return None
    d = unreal.MathLibrary.vector_distance(
        g.get_actor_location(), pj.get_actor_location()) if pj else -1
    print("   %-16s %-10s apuntado=%-5s cubierto=%-5s flanq=%-5s "
          "coberturas=%-4d dist=%5.0f %s"
          % (g.get_name()[:16],
             nombre_estado(c.get_editor_property("State")),
             c.get_editor_property("BeingAimedAt"),
             c.get_editor_property("IsInCover"),
             c.get_editor_property("IsFlanker"),
             len(c.get_editor_property("CoverPoints")),
             d, etiqueta))
    return c


if modo == "preparar":
    print("soldados=%d  controladores=%d  coberturas con tag=%d"
          % (len(grunts), len(ctrls), len(covers)))
    n_cache = sum(1 for c in ctrls if len(c.get_editor_property("CoverPoints")) > 0)
    n_flank = sum(1 for c in ctrls if c.get_editor_property("IsFlanker"))
    print("")
    print("COMPROBACION 1 - Ev_CacheCover se ejecuto")
    print("   controladores con CoverPoints cacheados: %d de %d" % (n_cache, len(ctrls)))
    print("   sorteados como flanqueadores:            %d de %d" % (n_flank, len(ctrls)))
    g = objetivo()
    if g is None:
        print("FALLO: no hay soldado al que apuntar")
    else:
        print("")
        print("Objetivo elegido: %s" % g.get_name())
        pinta(g, "(antes de apuntar)")

elif modo == "apuntar":
    g = objetivo()
    if g is None:
        print("FALLO: no hay soldado")
    else:
        destino, mirar = apuntar_a(g)
        real = pj.get_actor_location()
        print("jugador colocado en (%.0f,%.0f,%.0f), pedido (%.0f,%.0f,%.0f)"
              % (real.x, real.y, real.z, destino.x, destino.y, destino.z))
        if unreal.MathLibrary.vector_distance(real, destino) > 150:
            print("   AVISO: PIE revirtio la posicion")
        print("apuntando con yaw=%.0f  pitch=%.0f" % (mirar.yaw, mirar.pitch))
        pinta(g, "(justo al apuntar)")

elif modo == "medir":
    g = objetivo()
    if g is None:
        print("FALLO: no hay soldado")
        raise SystemExit
    apuntar_a(g)   # re-aplicar: PIE revierte
    print("")
    print("OBJETIVO")
    c = pinta(g)
    print("")
    print("COMPANEROS a menos de 25 m (aviso por radio)")
    lg = g.get_actor_location()
    cerca = [o for o in grunts
             if o != g and unreal.MathLibrary.vector_distance(
                 o.get_actor_location(), lg) <= 2500]
    for o in cerca:
        pinta(o)
    if not cerca:
        print("   (ninguno)")

    print("")
    print("COMPROBACIONES")
    fallos = 0

    def comp(nombre, ok, detalle=""):
        global fallos
        if not ok:
            fallos += 1
        print("   %-38s %s  %s" % (nombre, "OK" if ok else "FALLO", detalle))

    if c is not None:
        cp = len(c.get_editor_property("CoverPoints"))
        comp("coberturas cacheadas", cp > 0, "%d puntos" % cp)
        comp("detecta que le apuntan",
             bool(c.get_editor_property("BeingAimedAt")))
        est = idx(c.get_editor_property("State"))
        comp("reacciono (sospecha o combate)", est >= 1, nombre_estado(est))
        n_react = sum(1 for o in cerca
                      if ctrl_de(o) is not None
                      and idx(ctrl_de(o).get_editor_property("State")) >= 1)
        comp("companeros avisados por radio", n_react > 0 or not cerca,
             "%d de %d" % (n_react, len(cerca)))
    print("")
    print("FALLOS: %d" % fallos)
