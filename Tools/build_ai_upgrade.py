# -*- coding: utf-8 -*-
"""
Infraestructura de la IA ampliada: cobertura, deteccion de apuntado, aviso por
radio al sector y flanqueo.

Solo variables y valores. La logica va en el pegado que genera
Tools/gen_ai_upgrade.py.

NO se anaden entradas nuevas a E_GruntState a proposito: la API de Python no
sabe editar un UserDefinedEnum, asi que los estados nuevos se representan con
banderas (IsInCover, BeingAimedAt, IsFlanker) sobre el estado Combat que ya
existe.

Idempotente. Acaba en "PROBLEMAS: N".

Uso:
    python Tools/ue_remote.py Tools/build_ai_upgrade.py
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary

problemas = []


def log(ok, msg):
    print(("  OK    " if ok else "  FALLO ") + msg)
    if not ok:
        problemas.append(msg)


def pin_type(cat, sub="", subobj="None", contenedor="None"):
    """get_basic_type_by_name devuelve int para todo menos bool, asi que el
    tipo se construye por texto (medido el 2026-08-31)."""
    t = unreal.EdGraphPinType()
    ok = t.import_text(
        '(PinCategory="%s",PinSubCategory="%s",PinSubCategoryObject=%s,'
        'PinSubCategoryMemberReference=(),PinValueType=(),ContainerType=%s,'
        'bIsReference=False,bIsConst=False,bIsWeakPointer=False,'
        'bIsUObjectWrapper=False,bSerializeAsSinglePrecisionFloat=False)'
        % (cat, sub, subobj, contenedor))
    if not ok:
        raise RuntimeError("no se pudo construir el tipo %s/%s" % (cat, sub))
    return t


T_BOOL = ("bool",)
T_DOUBLE = ("real", "double", "None")
T_ACTOR = ("object", "", "Class'\"/Script/Engine.Actor\"'")
T_ACTOR_ARRAY = ("object", "", "Class'\"/Script/Engine.Actor\"'", "Array")


def cdo(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def tiene(bp, nombre):
    try:
        cdo(bp).get_editor_property(nombre)
        return True
    except Exception:
        return False


def add_var(bp, nombre, tipo, valor=None, editable=False):
    nuevo = False
    if not tiene(bp, nombre):
        BEL.add_member_variable(bp, nombre, pin_type(*tipo))
        BEL.compile_blueprint(bp)
        nuevo = True
    if not tiene(bp, nombre):
        log(False, "%s.%s no se creo" % (bp.get_name(), nombre))
        return
    if editable:
        try:
            BEL.set_blueprint_variable_instance_editable(bp, nombre, True)
        except Exception as e:
            log(False, "%s.%s no se pudo hacer editable (%s)" % (bp.get_name(), nombre, e))
    if valor is not None:
        try:
            cdo(bp).set_editor_property(nombre, valor)
        except Exception as e:
            log(False, "%s.%s no acepto %r (%s)" % (bp.get_name(), nombre, valor, e))
            return
    leido = cdo(bp).get_editor_property(nombre)
    log(True, "%s.%-20s = %r%s" % (bp.get_name(), nombre, leido,
                                   "  (nueva)" if nuevo else ""))


# =========================================== BP_GruntAIController: banderas
RUTA_AIC = "/Game/ThirdPerson/AI/BP_GruntAIController"
bp = EAL.load_asset(RUTA_AIC)
print("=== BP_GruntAIController ===")
if bp is None:
    log(False, "no existe " + RUTA_AIC)
else:
    add_var(bp, "CoverPoints", T_ACTOR_ARRAY)     # cacheado en BeginPlay
    add_var(bp, "CurrentCover", T_ACTOR)
    add_var(bp, "IsInCover", T_BOOL, False)
    add_var(bp, "BeingAimedAt", T_BOOL, False)
    add_var(bp, "IsFlanker", T_BOOL, False)
    add_var(bp, "SquadAlerted", T_BOOL, False)
    BEL.compile_blueprint(bp)
    EAL.save_asset(RUTA_AIC)

# ================================================ BP_Grunt: metricas nuevas
RUTA_GRUNT = "/Game/ThirdPerson/Blueprints/BP_Grunt"
bp = EAL.load_asset(RUTA_GRUNT)
print("\n=== BP_Grunt ===")
if bp is None:
    log(False, "no existe " + RUTA_GRUNT)
else:
    # AimDotThreshold se guarda ya como coseno para no calcular cos() en
    # runtime: cos(15 grados) = 0.9659. Subirlo estrecha el cono de apuntado.
    add_var(bp, "AimDotThreshold", T_DOUBLE, 0.9659, editable=True)
    add_var(bp, "AimDetectRange", T_DOUBLE, 2500.0, editable=True)
    add_var(bp, "CoverSearchRadius", T_DOUBLE, 1600.0, editable=True)
    add_var(bp, "CoverStandoff", T_DOUBLE, 500.0, editable=True)
    add_var(bp, "FlankOffset", T_DOUBLE, 900.0, editable=True)
    add_var(bp, "RadioRange", T_DOUBLE, 2500.0, editable=True)
    add_var(bp, "AimWatchInterval", T_DOUBLE, 0.25, editable=True)
    BEL.compile_blueprint(bp)
    EAL.save_asset(RUTA_GRUNT)

# ============================== comprobacion: los puntos de cobertura existen
print("\n=== Puntos de cobertura en el nivel ===")
try:
    EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cps = [a for a in EAS.get_all_level_actors()
           if a.get_actor_label().startswith("BO_CP_")]
    con_tag = [a for a in cps if unreal.Name("Cover") in list(a.tags)]
    log(len(con_tag) > 0,
        "%d puntos BO_CP_ en el nivel, %d con el tag 'Cover'" % (len(cps), len(con_tag)))
except Exception as e:
    log(False, "no se pudieron contar los puntos de cobertura (%s)" % e)

print("")
print("PROBLEMAS: %d" % len(problemas))
for p in problemas:
    print("   - " + p)
