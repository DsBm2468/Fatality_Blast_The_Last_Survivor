# -*- coding: utf-8 -*-
"""
M-7  Coloca en Lvl_01_MilitaryBase los items que existen como Blueprint y no
     estaban puestos en ninguna parte del nivel.

    python Tools/ue_remote.py Tools/place_missing_items.py

Faltaban BP_SubmachineGun, BP_Grenade, BP_Bomb y BP_Bandage. La metralleta es
la que mas duele: acababa de recibir el sistema de recarga completo (cargador
+ reserva, tecla R) y no habia ni una en el nivel con la que probarlo.

POR QUE LAS POSICIONES SON LAS QUE SON
--------------------------------------
Cada item nuevo se coloca a 150 UU de un item que YA ESTA en el nivel y
funciona. En modo commandlet no hay escena de fisica, asi que un line_trace
para buscar el suelo devuelve vacio (ver CLAUDE.md seccion 8): no hay forma de
comprobar por script que un punto inventado este sobre suelo pisable. Anclarse
a un item existente es la unica garantia barata de caer en sitio bueno.

Idempotente: borra todo lo que empiece por BO_M7_ antes de crear.
"""
import unreal

EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
EAL = unreal.EditorAssetLibrary

LEVEL = "/Game/ThirdPerson/Lvl_01_MilitaryBase"
PREFIJO = "BO_M7_"

CLASES = {
    "smg":     "/Game/ThirdPerson/Blueprints/Interactables/BP_SubmachineGun",
    "granada": "/Game/ThirdPerson/Blueprints/Interactables/BP_Grenade",
    "bomba":   "/Game/ThirdPerson/Blueprints/Interactables/BP_Bomb",
    "venda":   "/Game/ThirdPerson/Blueprints/Interactables/BP_Bandage",
}

# (clase, nombre, ancla existente, desplazamiento X, desplazamiento Y)
SIEMBRA = [
    # --- Acto 0: la celda y el vestuario. Una venda pronto, que el jugador
    #     empieza desarmado y con 10 balas.
    ("venda",   "Venda_Vestuario",   "BO_A0_Item_Medkit_Vestuario", -150,    0),
    ("granada", "Granada_Almacen",   "BO_A0_Item_Ammo_Almacen",      150,    0),

    # --- Encounter 1: la emboscada de la mesa redonda.
    ("venda",   "Venda_E1",          "BO_Item_Medkit_1",               0,  150),
    ("granada", "Granada_COT",       "BO_Item_AmmoConv_COT",         150,    0),

    # --- Nave / Beat 9: aqui es donde se prueba la recarga de la metralleta.
    ("smg",     "Metralleta_Nave",   "BO_Item_AmmoConv_Nave",        150,    0),
    ("bomba",   "Bomba_Nave",        "BO_Item_AmmoConv_Nave",       -150,    0),
    ("granada", "Granada_Beat9",     "BO_Item_Gun_DANADA_Beat9",     150,    0),

    # --- ZRT: ultimo respiro antes del tramo final.
    ("venda",   "Venda_ZRT",         "BO_Item_Shield_ZRT",          -150,    0),
]


def buscar(label):
    for a in EAS.get_all_level_actors():
        if a.get_actor_label() == label:
            return a
    return None


problemas = 0
LES.load_level(LEVEL)

# --- limpieza (idempotencia)
n = 0
for a in list(EAS.get_all_level_actors()):
    if a.get_actor_label().startswith(PREFIJO):
        EAS.destroy_actor(a)
        n += 1
print("Limpieza: %d actores BO_M7_ previos borrados" % n)

# --- clases
kls = {}
for k, ruta in CLASES.items():
    if not EAL.does_asset_exist(ruta):
        print("  NO EXISTE el Blueprint: %s" % ruta)
        problemas += 1
        continue
    c = unreal.load_object(None, ruta + "." + ruta.rsplit("/", 1)[-1] + "_C")
    if c is None:
        print("  NO CARGA la clase de: %s" % ruta)
        problemas += 1
        continue
    kls[k] = c

# --- siembra
print("")
puestos = 0
for clave, nombre, ancla, dx, dy in SIEMBRA:
    if clave not in kls:
        problemas += 1
        continue
    a = buscar(ancla)
    if a is None:
        print("  FALTA el ancla %s, no se coloca %s" % (ancla, nombre))
        problemas += 1
        continue
    l = a.get_actor_location()
    pos = unreal.Vector(l.x + dx, l.y + dy, l.z)
    nuevo = EAS.spawn_actor_from_class(kls[clave], pos, unreal.Rotator(0, 0, 0))
    if nuevo is None:
        print("  NO se pudo crear %s" % nombre)
        problemas += 1
        continue
    nuevo.set_actor_label(PREFIJO + nombre)
    puestos += 1
    print("  %-22s %-26s (%7.0f,%8.0f,%6.0f)  junto a %s"
          % (clave, nombre, pos.x, pos.y, pos.z, ancla))

print("")
print("Colocados: %d de %d" % (puestos, len(SIEMBRA)))

# --- recuento final por clase, para que quede en el informe
cuenta = {}
for a in EAS.get_all_level_actors():
    cuenta[a.get_class().get_name()] = cuenta.get(a.get_class().get_name(), 0) + 1
print("")
print("En el nivel ahora:")
for c in ("BP_SubmachineGun_C", "BP_Grenade_C", "BP_Bomb_C", "BP_Bandage_C",
          "BP_ConventionalGun_C", "BP_FirstAidKit_C", "BP_Shield_C",
          "BP_MunitionConventionalGun_C", "BP_Grunt_C"):
    print("   %-32s %d" % (c, cuenta.get(c, 0)))
    if c in ("BP_SubmachineGun_C", "BP_Grenade_C", "BP_Bomb_C",
             "BP_Bandage_C") and cuenta.get(c, 0) == 0:
        problemas += 1

if LES.save_current_level():
    print("")
    print("Nivel guardado.")
else:
    print("")
    print("  !! no se pudo guardar el nivel")
    problemas += 1

print("")
print("PROBLEMAS: %d" % problemas)
