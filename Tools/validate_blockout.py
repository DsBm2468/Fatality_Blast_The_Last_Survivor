# -*- coding: utf-8 -*-
"""
Valida el blockout extendido y PODA los puntos de cobertura invalidos.

1. Reconstruye la navegacion.
2. Proyecta cada BO_CP_* al NavMesh: el que no proyecta (dentro de un muro,
   sobre una caja, fuera del volumen) se borra.
3. Comprueba que existe camino navegable por la ruta critica completa,
   del PlayerStart nuevo hasta la salida.
4. Informe en Saved/Blockout_Report.txt

Uso:
    python Tools/ue_remote.py Tools/validate_blockout.py
"""
import unreal
import os

EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = UES.get_editor_world()

lineas = []


def P(s):
    lineas.append(s)
    print(s)


# ------------------------------------------------- 1. reconstruir navegacion
unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
P("RebuildNavigation lanzado")

nav = unreal.NavigationSystemV1.get_navigation_system(world)
P("NavigationSystem: %s" % ("OK" if nav else "NO DISPONIBLE"))


def proyecta(v, radio=unreal.Vector(200, 200, 300)):
    """Devuelve el punto proyectado al NavMesh, o None."""
    try:
        p = unreal.NavigationSystemV1.project_point_to_navigation(
            world, v, None, None, radio)
    except Exception:
        return None
    if p is None:
        return None
    # project_point_to_navigation devuelve (0,0,0) cuando falla
    if abs(p.x) < 0.01 and abs(p.y) < 0.01 and abs(p.z) < 0.01:
        return None
    return p


# ------------------------------------------- 2. podar puntos de cobertura
cps = [a for a in EAS.get_all_level_actors()
       if a.get_actor_label().startswith("BO_CP_")]
P("")
P("Puntos de cobertura antes de podar: %d" % len(cps))

borrados = 0
for a in cps:
    loc = a.get_actor_location()
    p = proyecta(loc, unreal.Vector(120, 120, 200))
    if p is None:
        EAS.destroy_actor(a)
        borrados += 1
    else:
        # pegarlo al suelo navegable real
        a.set_actor_location(unreal.Vector(p.x, p.y, p.z + 10), False, False)

quedan = len([a for a in EAS.get_all_level_actors()
              if a.get_actor_label().startswith("BO_CP_")])
P("Podados (no navegables): %d" % borrados)
P("Puntos de cobertura validos: %d" % quedan)

# ------------------------------------------- 3. camino por la ruta critica
HITOS = [
    ("Inicio (celda)",         unreal.Vector(3250, -3100, 100)),
    ("Pasillo de celdas",      unreal.Vector(1800, -3000, 100)),
    ("Vestuario",              unreal.Vector(1900, -2350, 100)),
    ("Puesto de guardia",      unreal.Vector(900, -2550, 100)),
    ("Pasillo de servicio",    unreal.Vector(1000, -1700, 100)),
    ("Almacen",                unreal.Vector(1100, -950, 100)),
    ("Pasillo de acceso",      unreal.Vector(2200, -500, 100)),
    ("Vestibulo (INICIO GDD)", unreal.Vector(2300, 200, 100)),
    ("COT",                    unreal.Vector(900, 1000, 100)),
    ("Nave central",           unreal.Vector(1800, 1000, 100)),
    ("Plataforma ZRT",         unreal.Vector(4700, 2000, 450)),
    ("Nave oeste",             unreal.Vector(2600, 2750, 100)),
    ("Escaleras de servicio",  unreal.Vector(2150, 2800, 60)),
    ("Salida de emergencia",   unreal.Vector(600, 3400, 420)),
]

P("")
P("RUTA CRITICA (camino navegable entre hitos consecutivos)")
total = 0.0
fallos = 0
for i in range(len(HITOS) - 1):
    na, a = HITOS[i]
    nb, b = HITOS[i + 1]
    pa, pb = proyecta(a), proyecta(b)
    if pa is None or pb is None:
        P("  FALLO  %-22s -> %-22s  (hito fuera del NavMesh: %s)"
          % (na, nb, "origen" if pa is None else "destino"))
        fallos += 1
        continue
    try:
        path = unreal.NavigationSystemV1.find_path_to_location_synchronously(
            world, pa, pb, None)
    except Exception as e:
        P("  ERROR  %-22s -> %-22s  (%s)" % (na, nb, e))
        fallos += 1
        continue
    if path is None or not path.is_valid() or not path.path_points:
        P("  FALLO  %-22s -> %-22s  SIN CAMINO" % (na, nb))
        fallos += 1
        continue
    d = path.get_path_length()
    # OJO: is_valid() vale True tambien para un camino PARCIAL, que se queda a
    # medias sin avisar. La unica comprobacion honesta es donde acaba.
    err = unreal.MathLibrary.vector_distance(path.path_points[-1], pb)
    if err >= 250:
        P("  FALLO  %-22s -> %-22s  PARCIAL (acaba a %.0f UU del destino)"
          % (na, nb, err))
        fallos += 1
        continue
    total += d
    P("  OK     %-22s -> %-22s  %7.0f UU" % (na, nb, d))

P("")
P("Longitud total de la ruta critica: %.0f UU (%.0f m)" % (total, total / 100.0))
P("A 500 UU/s de carrera limpia: %.0f s de puro desplazamiento" % (total / 500.0))

# ------------------------------------------- 4. resumen de actores
import collections
byc = collections.Counter(a.get_class().get_name() for a in EAS.get_all_level_actors())
P("")
P("ACTORES EN EL NIVEL")
for c, n in byc.most_common():
    P("  %-34s %d" % (c, n))

unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
P("")
P("FALLOS: %d" % fallos)

ruta = os.path.join(unreal.Paths.project_saved_dir(), "Blockout_Report.txt")
with open(ruta, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lineas))
print("Informe: " + ruta)
