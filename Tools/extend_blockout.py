# -*- coding: utf-8 -*-
"""
Extension del blockout de Lvl_01_MilitaryBase  -  ACTO 0 "Infiltracion de emergencia".

Anade al SUR del nivel existente (todo Y < -220, region vacia) una secuencia de
pasillos y salas que el jugador recorre ANTES del Vestibulo de Conflicto, que
pasa a ser el umbral hacia la base propiamente dicha.

NO regenera el nivel: solo anade. El unico actor existente que toca es
BO_Wall_Vest_S, que se parte en dos para abrir la puerta de union.

Ademas siembra PUNTOS DE COBERTURA (TargetPoint con tag "Cover") alrededor de
toda pieza de cobertura del nivel, nuevos y viejos, para que la IA los consulte.

Idempotente: borra todo lo que empieza por BO_A0_ / BO_CP_ antes de crear.

Uso:
    python Tools/ue_remote.py Tools/extend_blockout.py
"""
import unreal

CUBE = unreal.EditorAssetLibrary.load_asset("/Game/LevelPrototyping/Meshes/SM_Cube")
CYL = unreal.EditorAssetLibrary.load_asset("/Game/LevelPrototyping/Meshes/SM_Cylinder")
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)

LEVEL = "/Game/ThirdPerson/Lvl_01_MilitaryBase"
PREFIJOS_BORRABLES = ("BO_A0_", "BO_CP_")

W = 200      # grosor de muro
H = 800      # altura de muro
CEIL = 400   # cara inferior del techo de pasillo


def P(s):
    print(s)


def limpiar():
    n = 0
    for a in list(EAS.get_all_level_actors()):
        if a.get_actor_label().startswith(PREFIJOS_BORRABLES):
            EAS.destroy_actor(a)
            n += 1
    P("Limpieza: %d actores previos borrados" % n)


def caja(nombre, x0, y0, z0, x1, y1, z1, mesh=None):
    """Caja por esquinas. SM_Cube: pivote en esquina minima, lado 100 UU."""
    a = EAS.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(x0, y0, z0), unreal.Rotator(0, 0, 0))
    a.set_actor_label(nombre)
    c = a.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.STATIC)
    c.set_static_mesh(mesh or CUBE)
    a.set_actor_scale3d(unreal.Vector(
        (x1 - x0) / 100.0, (y1 - y0) / 100.0, (z1 - z0) / 100.0))
    return a


def suelo(nombre, x0, y0, x1, y1, z=0.0):
    return caja(nombre, x0, y0, z - 20, x1, y1, z)


def techo(nombre, x0, y0, x1, y1, z=CEIL):
    return caja(nombre, x0, y0, z, x1, y1, z + 20)


def marcador(clase, nombre, x, y, z, tags=None, yaw=0.0):
    a = EAS.spawn_actor_from_class(clase, unreal.Vector(x, y, z), unreal.Rotator(0, yaw, 0))
    a.set_actor_label(nombre)
    if tags:
        a.set_editor_property("tags", [unreal.Name(t) for t in tags])
    return a


def buscar(label):
    for a in EAS.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


# ============================================================== 1. LIMPIEZA
LES.load_level(LEVEL)
limpiar()

# ================================= 2. ABRIR LA PUERTA HACIA EL VESTIBULO
# BO_Wall_Vest_S ocupa X[1800..2800] Y[-200..0]. Se parte dejando un vano de
# 400 UU en X[2000..2400], que es por donde entra el Acto 0.
# OJO: los tres trozos de sustitucion llevan prefijo BO_A0_, asi que limpiar()
# se los lleva en cada pasada. Hay que recrearlos SIEMPRE, exista o no el muro
# original (en la segunda pasada ya no existe: se destruyo en la primera).
vw = buscar("BO_Wall_Vest_S")
if vw is not None:
    EAS.destroy_actor(vw)
    P("BO_Wall_Vest_S destruido (se sustituye por dos jambas y un dintel)")
caja("BO_A0_Wall_VestS_W", 1800, -200, 0, 2000, 0, H)
caja("BO_A0_Wall_VestS_E", 2400, -200, 0, 2800, 0, H)
caja("BO_A0_Lintel_Vest", 2000, -200, 400, 2400, 0, H)
P("Puerta al Vestibulo abierta en X[2000..2400], Y=-200")

# ====================================================== 3. GEOMETRIA ACTO 0
# Espacios interiores (area libre), en UU:
#   A  Celda de contencion  X 2600..3400  Y -3400..-2800   INICIO
#   B  Pasillo de celdas    X  800..2600  Y -3200..-2800
#   B2 Vestuario (ramal N)  X 1600..2200  Y -2800..-2200
#   C  Puesto de guardia    X  400..1400  Y -2800..-2000
#   D  Pasillo de servicio  X  800..1200  Y -2000..-1400
#   E  Almacen              X  400..2000  Y -1400..-600
#   F  Pasillo de acceso    X 2000..2400  Y -1000..-200

# --- suelos
suelo("BO_A0_Floor_Celda", 2600, -3400, 3400, -2800)
suelo("BO_A0_Floor_PasCeldas", 800, -3200, 2600, -2800)
suelo("BO_A0_Floor_Vestuario", 1600, -2800, 2200, -2200)
suelo("BO_A0_Floor_Guardia", 400, -2800, 1400, -2000)
suelo("BO_A0_Floor_PasServ", 800, -2000, 1200, -1400)
suelo("BO_A0_Floor_Almacen", 400, -1400, 2000, -600)
suelo("BO_A0_Floor_PasAcceso", 2000, -1000, 2400, -200)
suelo("BO_A0_Floor_Puerta", 2000, -200, 2400, 0)   # vano hacia el Vestibulo

# --- perimetro exterior
caja("BO_A0_Wall_S_Celda", 2600, -3600, 0, 3600, -3400, H)
caja("BO_A0_Wall_S_Pas", 600, -3400, 0, 2600, -3200, H)
caja("BO_A0_Wall_E_Celda", 3400, -3600, 0, 3600, -2800, H)
caja("BO_A0_Wall_N_Celda", 2800, -2800, 0, 3600, -2600, H)   # vano en X2600..2800
caja("BO_A0_Wall_E_Pas", 2600, -2800, 0, 2800, -2600, H)
caja("BO_A0_Wall_W_Guardia", 200, -2800, 0, 400, -1400, H)
caja("BO_A0_Wall_S_Guardia", 200, -3000, 0, 800, -2800, H)
caja("BO_A0_Wall_W_Pas", 600, -3200, 0, 800, -2800, H)
caja("BO_A0_Wall_W_Almacen", 200, -1400, 0, 400, -400, H)
caja("BO_A0_Wall_N_Almacen", 200, -600, 0, 2000, -400, H)
caja("BO_A0_Wall_N_PasAcc", 2400, -600, 0, 2800, -400, H)
caja("BO_A0_Wall_E_PasAcc", 2400, -1200, 0, 2600, -200, H)
caja("BO_A0_Wall_S_PasAcc", 2000, -1400, 0, 2600, -1000, H)
caja("BO_A0_Wall_W_PasAcc", 1800, -600, 0, 2000, -200, H)

# --- tabiques interiores que forman los pasillos
# (el tabique X800..1600 se elimino: sellaba el paso del pasillo B al puesto de guardia)
caja("BO_A0_Part_PasCeldas_N2", 2200, -2800, 0, 2600, -2600, H)
caja("BO_A0_Part_Vestuario_W", 1400, -2800, 0, 1600, -2200, H)
caja("BO_A0_Part_Vestuario_E", 2200, -2800, 0, 2400, -2200, H)
caja("BO_A0_Part_Vestuario_N", 1400, -2200, 0, 2400, -2000, H)
caja("BO_A0_Part_Guardia_N", 400, -2000, 0, 800, -1800, H)
caja("BO_A0_Part_Guardia_NE", 1200, -2000, 0, 1400, -1400, H)
caja("BO_A0_Part_PasServ_W", 600, -1800, 0, 800, -1400, H)
caja("BO_A0_Part_Almacen_S", 400, -1600, 0, 800, -1400, H)
caja("BO_A0_Part_Almacen_SE", 1200, -1600, 0, 2000, -1400, H)

# --- techos de pasillo
techo("BO_A0_Ceil_PasCeldas", 800, -3200, 2600, -2800)
techo("BO_A0_Ceil_PasServ", 800, -2000, 1200, -1400)
techo("BO_A0_Ceil_PasAcceso", 2000, -1000, 2400, -200)

# --- coberturas del Acto 0
caja("BO_A0_Cover_Cel_A", 3000, -3200, 0, 3200, -3000, 280)
caja("BO_A0_Cover_Pas_A", 1700, -3150, 0, 1900, -3050, 110)
caja("BO_A0_Cover_Pas_B", 1150, -3000, 0, 1350, -2900, 110)
caja("BO_A0_Cover_Pas_C", 2150, -3000, 0, 2350, -2900, 110)
caja("BO_A0_Cover_Vest_A", 1750, -2650, 0, 1950, -2450, 280)
caja("BO_A0_Cover_Gua_A", 600, -2650, 0, 800, -2450, 280)
caja("BO_A0_Cover_Gua_B", 1000, -2400, 0, 1200, -2300, 110)
caja("BO_A0_Cover_Gua_C", 500, -2250, 0, 700, -2150, 110)
caja("BO_A0_Cover_Alm_A", 700, -1250, 0, 900, -1050, 280)
caja("BO_A0_Cover_Alm_B", 1200, -1300, 0, 1400, -1100, 280)
caja("BO_A0_Cover_Alm_C", 1600, -1000, 0, 1800, -800, 280)
caja("BO_A0_Cover_Alm_D", 500, -900, 0, 700, -800, 110)
caja("BO_A0_Cover_Acc_A", 2050, -800, 0, 2250, -700, 110)

# --- pilares del almacen
for i, (px, py) in enumerate([(950, -1150), (1500, -1150), (950, -800)]):
    caja("BO_A0_Pillar_%d" % (i + 1), px, py, 0, px + 120, py + 120, H, CYL)

P("Geometria del Acto 0 creada")

# ============================================ 4. INICIO, ENEMIGOS E ITEMS
ps = buscar("PlayerStart_Nivel1")
if ps is not None:
    marcador(unreal.TargetPoint, "BO_A0_Ref_InicioAntiguo", 2300, 200, 100)
    ps.set_actor_location(unreal.Vector(3250, -3100, 100), False, False)
    ps.set_actor_rotation(unreal.Rotator(0, 180, 0), False)
    P("PlayerStart movido a (3250,-3100,100), mirando al Oeste")
else:
    P("AVISO: PlayerStart_Nivel1 no encontrado")

GRUNT = unreal.EditorAssetLibrary.load_blueprint_class(
    "/Game/ThirdPerson/Blueprints/BP_Grunt")
MEDKIT = unreal.EditorAssetLibrary.load_blueprint_class(
    "/Game/ThirdPerson/Blueprints/Interactables/BP_FirstAidKit")
GUN = unreal.EditorAssetLibrary.load_blueprint_class(
    "/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun")
AMMO = unreal.EditorAssetLibrary.load_blueprint_class(
    "/Game/ThirdPerson/Blueprints/Interactables/BP_MunitionConventionalGun")

SOLDADOS = [
    ("E0_Soldado_1", (2300, -3000), [(2300, -3000), (1000, -3000), (1800, -3000)]),
    ("E0_Soldado_2", (1200, -3000), [(1200, -3000), (2400, -3000), (1600, -3000)]),
    ("E0_Soldado_3", (900, -2500), [(900, -2500), (600, -2200), (1200, -2650)]),
    ("E0_Soldado_4", (700, -2200), None),
    ("E0_Soldado_5", (1400, -900), [(1400, -900), (600, -1200), (1700, -1250)]),
]

for nombre, (gx, gy), ruta in SOLDADOS:
    g = EAS.spawn_actor_from_class(GRUNT, unreal.Vector(gx, gy, 90), unreal.Rotator(0, 0, 0))
    g.set_actor_label("BO_A0_" + nombre)
    if ruta:
        tps = []
        for i, (px, py) in enumerate(ruta):
            tps.append(marcador(unreal.TargetPoint,
                                "BO_A0_%s_P%d" % (nombre, i), px, py, 30))
        try:
            g.set_editor_property("PatrolPoints", tps)
        except Exception as e:
            P("   AVISO: PatrolPoints no asignados a %s (%s)" % (nombre, e))

P("5 soldados del Acto 0 colocados")

EAS.spawn_actor_from_class(MEDKIT, unreal.Vector(1900, -2350, 20),
                           unreal.Rotator(0, 0, 0)).set_actor_label("BO_A0_Item_Medkit_Vestuario")
EAS.spawn_actor_from_class(GUN, unreal.Vector(700, -2550, 20),
                           unreal.Rotator(0, 0, 0)).set_actor_label("BO_A0_Item_Gun_Guardia")
EAS.spawn_actor_from_class(AMMO, unreal.Vector(1300, -1200, 20),
                           unreal.Rotator(0, 0, 0)).set_actor_label("BO_A0_Item_Ammo_Almacen")
EAS.spawn_actor_from_class(AMMO, unreal.Vector(600, -850, 20),
                           unreal.Rotator(0, 0, 0)).set_actor_label("BO_A0_Item_Ammo_Almacen_2")
P("Items del Acto 0 colocados (1 botiquin, 1 arma, 2 municiones)")

# ================================= 5. AMPLIAR EL VOLUMEN DE NAVEGACION
nb = buscar("BO_NavMeshBounds")
if nb is not None:
    # El volumen viejo cubria Y[-200..4000] centrado en (2800,1900), escala (31,22,7).
    # El Acto 0 baja a Y=-3600 -> alto total 7600 -> centro Y = 200, escala Y = 39.
    nb.set_actor_location(unreal.Vector(2800, 200, 400), False, False)
    nb.set_actor_scale3d(unreal.Vector(31, 39, 7))
    P("NavMeshBounds ampliado: centro (2800,200,400) escala (31,39,7)")
else:
    P("AVISO: BO_NavMeshBounds no encontrado")

# ================================= 6. PUNTOS DE COBERTURA PARA LA IA
PATRONES = ("Cover", "Container", "Locker", "Pillar", "Crate", "Console", "Table")
EXCLUIR = ("MARCADOR", "Rail", "Ceil", "Floor", "Wall", "Part")

n_cp = 0
for a in list(EAS.get_all_level_actors()):
    if a.get_class().get_name() != "StaticMeshActor":
        continue
    lbl = a.get_actor_label()
    if not any(p in lbl for p in PATRONES):
        continue
    if any(x in lbl for x in EXCLUIR):
        continue
    o, e = a.get_actor_bounds(False)
    alto = 2.0 * e.z
    if alto < 80 or alto > 400:      # ni alfombras ni muros
        continue
    zbase = (o.z - e.z) + 40
    off = 95
    lados = [(e.x + off, 0), (-e.x - off, 0), (0, e.y + off), (0, -e.y - off)]
    for i, (dx, dy) in enumerate(lados):
        marcador(unreal.TargetPoint,
                 "BO_CP_%s_%d" % (lbl.replace("BO_", ""), i),
                 o.x + dx, o.y + dy, zbase, tags=["Cover"])
        n_cp += 1

P("Puntos de cobertura sembrados: %d (tag 'Cover')" % n_cp)

# ========================================================== 7. GUARDAR
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
P("Nivel guardado")
P("")
P("TOTAL ACTORES EN EL NIVEL: %d" % len(EAS.get_all_level_actors()))
