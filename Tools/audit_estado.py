"""Auditoria de estado 2026-09-03: reflexion de los assets clave + inventario del nivel."""
import unreal, os

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary

ASSETS = [
    "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_SubmachineGun",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_MunitionConventionalGun",
    "/Game/ThirdPerson/Blueprints/Interfaces/BPI_WeaponSystem",
    "/Game/ThirdPerson/AI/BP_GruntAIController",
    "/Game/ThirdPerson/Blueprints/BP_Grunt",
    "/Game/ThirdPerson/AI/E_GruntState",
]

def dump(path):
    bp = EAL.load_asset(path)
    print("\n" + "="*70)
    print("ASSET:", path)
    if bp is None:
        print("  NO EXISTE"); return
    print("  clase:", type(bp).__name__)
    if isinstance(bp, unreal.UserDefinedEnum):
        n = unreal.EnumBase.cast(bp) if hasattr(unreal,'EnumBase') else bp
        try:
            for i in range(bp.num_enums()):
                print("   [%d] %s" % (i, bp.get_display_name_by_index(i)))
        except Exception as e:
            print("   (no enumerable:", e, ")")
        return
    gen = getattr(bp, "generated_class", None)
    gen = gen() if callable(gen) else gen
    if gen is None:
        print("  sin generated_class"); return
    cdo = unreal.get_default_object(gen)
    # variables
    print("  -- VARIABLES (CDO) --")
    try:
        props = [p for p in dir(cdo) if not p.startswith("_")]
    except Exception:
        props = []
    shown = 0
    for name in sorted(props):
        try:
            v = cdo.get_editor_property(name)
        except Exception:
            continue
        print("     %-34s = %r" % (name, v))
        shown += 1
    if not shown: print("     (ninguna legible)")
    # grafos
    print("  -- GRAFOS --")
    try:
        for g in BEL.get_all_graphs(bp):
            print("     ", g.get_name())
    except Exception as e:
        print("      error:", e)

for a in ASSETS:
    dump(a)

# ---- Inventario de niveles ----
print("\n" + "#"*70)
for lvl in ["/Game/ThirdPerson/Lvl_01_MilitaryBase", "/Game/ThirdPerson/Lvl_ThirdPerson"]:
    print("\nNIVEL:", lvl, "existe:", EAL.does_asset_exist(lvl))
