# -*- coding: utf-8 -*-
"""Re-mide la ruta critica distinguiendo camino COMPLETO de camino PARCIAL."""
import unreal

UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = UES.get_editor_world()

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


def proyecta(v):
    p = unreal.NavigationSystemV1.project_point_to_navigation(
        world, v, None, None, unreal.Vector(300, 300, 400))
    if p is None or (abs(p.x) < .01 and abs(p.y) < .01 and abs(p.z) < .01):
        return None
    return p


print("%-24s %-24s %9s %9s %8s %s" % ("DESDE", "HASTA", "RECTA", "CAMINO", "PUNTOS", "ESTADO"))
total = 0.0
malos = 0
for i in range(len(HITOS) - 1):
    na, a = HITOS[i]
    nb, b = HITOS[i + 1]
    pa, pb = proyecta(a), proyecta(b)
    if pa is None or pb is None:
        print("%-24s %-24s %s" % (na, nb, "HITO FUERA DEL NAVMESH"))
        malos += 1
        continue
    recta = unreal.MathLibrary.vector_distance(pa, pb)
    path = unreal.NavigationSystemV1.find_path_to_location_synchronously(world, pa, pb, None)
    if path is None or not path.is_valid():
        print("%-24s %-24s %9.0f %9s %8s %s" % (na, nb, recta, "-", "-", "SIN CAMINO"))
        malos += 1
        continue
    npts = len(path.path_points)
    d = path.get_path_length()
    # un camino parcial acaba lejos del destino pedido
    fin = path.path_points[-1] if npts else pa
    err = unreal.MathLibrary.vector_distance(fin, pb)
    estado = "COMPLETO" if err < 250 else "PARCIAL (acaba a %.0f UU del destino)" % err
    if err >= 250:
        malos += 1
    total += d
    print("%-24s %-24s %9.0f %9.0f %8d %s" % (na, nb, recta, d, npts, estado))

print("")
print("TOTAL: %.0f UU (%.0f m)   TRAMOS MALOS: %d" % (total, total / 100.0, malos))
