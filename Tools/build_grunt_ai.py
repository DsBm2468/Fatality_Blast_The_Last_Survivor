# -*- coding: utf-8 -*-
"""
Construye la infraestructura de la IA del Grunt (todo lo que la API de Python
SI puede generar): assets, componentes, variables, valores del GDD y el
reparto de rutas de patrulla en el nivel.

La LOGICA de los grafos NO se genera aqui: los pines de Blueprint no son
UObjects. Esa parte va por texto de pegado (Tools/bp_paste/).

Idempotente: se puede reejecutar. Solo anade lo que falta.

Uso:
  "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/ue_remote.py Tools/build_grunt_ai.py
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
SDS = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary

AI_DIR = "/Game/ThirdPerson/AI"
P_AIC = AI_DIR + "/BP_GruntAIController"
P_STATE = AI_DIR + "/E_GruntState"
P_GRUNT = "/Game/ThirdPerson/Blueprints/BP_Grunt"

# ---- Metricas del GDD (pag. 20). No inventar otras. -------------------------
GDD = {
    "Health": 50.0,          # Vida baja
    "WalkSpeed": 400.0,      # 4 m/s
    "PatrolSpeed": 175.0,    # paso de patrulla, arma baja
    "Damage": 10.0,          # dano por disparo
    "FireRange": 1200.0,     # 12 m
    "FireInterval": 1.0,     # DPS 10 con dano 10 => 1 disparo/s
    "Accuracy": 0.60,        # 60 %
    "ReactionTime": 1.5,     # 1.5 s
    "SightRadius": 1200.0,   # 12 m
    "LoseSight": 1500.0,
    "SightAngle": 45.0,      # semiangulo => 90 deg horizontal
    "HearingRange": 600.0,   # 6 m
    "SearchTime": 5.0,       # vigilar ultima posicion conocida
    "SuspicionTime": 3.0,
}

log = []


def say(msg):
    log.append(msg)
    print(msg)


# ---------------------------------------------------------------- utilidades
def subobject_handles(bp):
    return SDS.k2_gather_subobject_data_for_blueprint(bp)


def find_subobject(bp, name):
    for h in subobject_handles(bp):
        d = SDL.get_data(h)
        o = SDL.get_object_for_blueprint(d, bp)
        if o and name.lower() in o.get_name().lower():
            return h, o
    return None, None


def add_component(bp, cls, name):
    h, o = find_subobject(bp, name)
    if o:
        say("    = %s ya existe" % name)
        return h, o
    root = subobject_handles(bp)[0]
    params = unreal.AddNewSubobjectParams(
        parent_handle=root, new_class=cls, blueprint_context=bp)
    nh, fail = SDS.add_new_subobject(params)
    # Ojo: 'fail' es un FText y un FText VACIO sigue siendo truthy en Python.
    # Hay que mirar su texto, no el objeto.
    if str(fail).strip():
        say("    ! fallo al crear %s: %s" % (name, fail))
        return None, None
    if not SDL.is_handle_valid(nh):
        say("    ! handle invalido al crear %s" % name)
        return None, None
    SDS.rename_subobject(nh, name)
    d = SDL.get_data(nh)
    o = SDL.get_object_for_blueprint(d, bp)
    say("    + componente %s (%s)" % (name, cls.static_class().get_name()))
    return nh, o


def tiene_var(bp, name):
    """Blueprint.NewVariables no es legible desde Python; se pregunta al CDO."""
    try:
        cdo = unreal.get_default_object(BEL.generated_class(bp))
        cdo.get_editor_property(name)
        return True
    except Exception:
        return False


def add_var(bp, name, pin_type, editable=False):
    # OJO: add_member_variable NO es idempotente. Llamarla dos veces con el
    # mismo nombre crea 'Nombre_0'. Hay que preguntar antes.
    if tiene_var(bp, name):
        say("    = var %s ya existe" % name)
    else:
        if not BEL.add_member_variable(bp, name, pin_type):
            say("    ! no pude crear la var %s" % name)
            return False
        say("    + var %s" % name)
    if editable:
        try:
            BEL.set_blueprint_variable_instance_editable(bp, name, True)
        except Exception as e:
            say("    ! editable %s: %s" % (name, e))
    return True


def limpiar_duplicados(bp, esperadas, etiqueta):
    """Si una pasada anterior dejo 'Nombre_0', borra todas las variables no
    usadas para que se vuelvan a crear limpias. Solo es seguro mientras los
    grafos no las referencien todavia."""
    dups = [n for n in esperadas if tiene_var(bp, n + "_0")]
    if dups:
        say("  ! %s: %d variables duplicadas %s" % (etiqueta, len(dups), dups))
        BEL.remove_unused_variables(bp)
        BEL.compile_blueprint(bp)
        say("    reparado: borradas las no usadas, se vuelven a crear")


def delete_orphan_components(bp, esperados):
    """Borra componentes anadidos por una pasada anterior que se quedaron con
    el nombre por defecto. Pasa cuando add_new_subobject reporta un FText
    vacio y se aborta antes del rename."""
    for h in subobject_handles(bp):
        d = SDL.get_data(h)
        o = SDL.get_object_for_blueprint(d, bp)
        if not o or not SDL.can_delete(d):
            continue
        n = o.get_name().replace("_GEN_VARIABLE", "")
        if n in esperados:
            SDS.delete_subobject(subobject_handles(bp)[0], h, bp)
            say("    - borrado componente huerfano %s" % n)


# TRAMPA GORDA de get_basic_type_by_name: cuando no reconoce el nombre NO
# falla, devuelve un tipo por defecto. Medido el 2026-08-26:
#   "float"  y "double"  -> ENTERO  (1.5 se guarda como 1, 0.6 como 0)
#   "vector"             -> ENTERO
#   "E_GruntState"       -> byte pelado, sin referencia al enum
# Solo "real", "int" y "bool" dan lo que dicen. Para lo demas hay que usar
# get_struct_type / get_object_reference_type. Los enums no hay forma: van
# a mano.
T_FLOAT = BEL.get_basic_type_by_name("real")
T_INT = BEL.get_basic_type_by_name("int")
T_BOOL = BEL.get_basic_type_by_name("bool")
T_VECTOR = BEL.get_struct_type(unreal.load_object(None, "/Script/CoreUObject.Vector"))


def var_es_real(cdo, name):
    """None = no existe. True = float de verdad. False = se creo como entero."""
    try:
        old = cdo.get_editor_property(name)
    except Exception:
        return None
    try:
        cdo.set_editor_property(name, 1.5)
        v = float(cdo.get_editor_property(name))
        cdo.set_editor_property(name, old)
        return abs(v - 1.5) < 0.001
    except Exception:
        return False


def reparar_tipos(bp, float_vars, etiqueta):
    """Si alguna variable float quedo como entero, las borra todas (ninguna
    esta referenciada aun en grafos) para que se vuelvan a crear bien."""
    try:
        cdo = unreal.get_default_object(BEL.generated_class(bp))
    except Exception:
        return
    malas = [n for n in float_vars if var_es_real(cdo, n) is False]
    if malas:
        say("  ! %s: %d variables float creadas como ENTERO %s"
            % (etiqueta, len(malas), malas))
        BEL.remove_unused_variables(bp)
        BEL.compile_blueprint(bp)
        say("    reparado: borradas las no usadas, se vuelven a crear como real")


def T_OBJ(cls):
    return BEL.get_object_reference_type(cls)


def T_ARR(t):
    return BEL.get_array_type(t)


# =========================================================== 1. carpeta / enum
say("== 1. Carpeta y enum de estado ==")
if not EAL.does_directory_exist(AI_DIR):
    EAL.make_directory(AI_DIR)
    say("  + carpeta %s" % AI_DIR)

if not EAL.does_asset_exist(P_STATE):
    AT.create_asset("E_GruntState", AI_DIR, None, unreal.EnumFactory())
    say("  + E_GruntState creado (VACIO: las entradas van a mano)")
else:
    say("  = E_GruntState ya existe")

for probe in [AI_DIR + "/_probe", AI_DIR + "/_probe2"]:
    if EAL.does_directory_exist(probe):
        EAL.delete_directory(probe)
        say("  - borrado %s" % probe)

# ================================================== 2. BP_GruntAIController
say("")
say("== 2. BP_GruntAIController ==")
if not EAL.does_asset_exist(P_AIC):
    f = unreal.BlueprintFactory()
    f.set_editor_property("parent_class", unreal.AIController)
    AT.create_asset("BP_GruntAIController", AI_DIR, None, f)
    say("  + creado")
aic = EAL.load_asset(P_AIC)

ph, perc = add_component(aic, unreal.AIPerceptionComponent, "AIPerception")
if perc:
    sight = unreal.new_object(unreal.AISenseConfig_Sight, perc)
    sight.set_editor_property("sight_radius", GDD["SightRadius"])
    sight.set_editor_property("lose_sight_radius", GDD["LoseSight"])
    sight.set_editor_property("peripheral_vision_angle_degrees", GDD["SightAngle"])
    sight.set_editor_property("auto_success_range_from_last_seen_location", -1.0)
    sight.set_editor_property("max_age", 5.0)
    aff = unreal.AISenseAffiliationFilter()
    aff.set_editor_property("detect_enemies", True)
    aff.set_editor_property("detect_neutrals", True)
    aff.set_editor_property("detect_friendlies", True)
    sight.set_editor_property("detection_by_affiliation", aff)

    hear = unreal.new_object(unreal.AISenseConfig_Hearing, perc)
    hear.set_editor_property("hearing_range", GDD["HearingRange"])
    hear.set_editor_property("max_age", 3.0)
    aff2 = unreal.AISenseAffiliationFilter()
    aff2.set_editor_property("detect_enemies", True)
    aff2.set_editor_property("detect_neutrals", True)
    aff2.set_editor_property("detect_friendlies", True)
    hear.set_editor_property("detection_by_affiliation", aff2)

    perc.set_editor_property("senses_config", [sight, hear])
    try:
        perc.set_editor_property("dominant_sense", unreal.AISense_Sight.static_class())
    except Exception as e:
        say("    ! dominant_sense: %s" % e)
    say("    - vista %.0f UU / %.0f deg  -  oido %.0f UU"
        % (GDD["SightRadius"], GDD["SightAngle"] * 2, GDD["HearingRange"]))

VARS_AIC = ["GruntPawn", "TargetPlayer", "LastKnownLocation", "PatrolIndex",
            "HasSeenPlayer", "IsFiring", "ReactionHandle", "FireHandle",
            "SearchHandle"]
limpiar_duplicados(aic, VARS_AIC, "BP_GruntAIController")

say("  variables:")
grunt_cls = unreal.load_object(None, P_GRUNT + ".BP_Grunt_C")
T_TIMER = BEL.get_struct_type(unreal.load_object(None, "/Script/Engine.TimerHandle"))
add_var(aic, "GruntPawn", T_OBJ(grunt_cls))
add_var(aic, "TargetPlayer", T_OBJ(unreal.Actor.static_class()))
add_var(aic, "LastKnownLocation", T_VECTOR)
add_var(aic, "PatrolIndex", T_INT)
add_var(aic, "HasSeenPlayer", T_BOOL)
add_var(aic, "IsFiring", T_BOOL)
add_var(aic, "ReactionHandle", T_TIMER)
add_var(aic, "FireHandle", T_TIMER)
add_var(aic, "SearchHandle", T_TIMER)

BEL.compile_blueprint(aic)
EAL.save_asset(P_AIC)
say("  compilado y guardado")

# ================================================================ 3. BP_Grunt
say("")
say("== 3. BP_Grunt ==")
grunt = EAL.load_asset(P_GRUNT)

FLOAT_VARS_GRUNT = ["Damage", "FireRange", "FireInterval", "Accuracy",
                    "ReactionTime", "SearchTime", "SuspicionTime",
                    "PatrolSpeed", "ChaseSpeed"]
limpiar_duplicados(grunt, ["PatrolPoints"] + FLOAT_VARS_GRUNT, "BP_Grunt")
reparar_tipos(grunt, FLOAT_VARS_GRUNT, "BP_Grunt")

say("  variables:")
add_var(grunt, "PatrolPoints",
        T_ARR(T_OBJ(unreal.TargetPoint.static_class())), editable=True)
for n in FLOAT_VARS_GRUNT:
    add_var(grunt, n, T_FLOAT, editable=True)

delete_orphan_components(grunt, ["TextRender"])
ih, icon = add_component(grunt, unreal.TextRenderComponent, "StateIcon")
if icon:
    icon.set_editor_property("relative_location", unreal.Vector(0, 0, 110))
    icon.set_editor_property("world_size", 48.0)
    try:
        icon.set_editor_property("horizontal_alignment",
                                 unreal.HorizTextAligment.EHTA_CENTER)
    except Exception as e:
        say("    ! alineacion: %s" % e)
    icon.set_editor_property("text", unreal.Text(""))
    icon.set_editor_property("text_render_color", unreal.Color(255, 200, 0, 255))
    icon.set_editor_property("visible", False)
    say("    - indicador de estado a Z=110")

BEL.compile_blueprint(grunt)

gc = BEL.generated_class(grunt)
cdo = unreal.get_default_object(gc)
aic_cls = BEL.generated_class(aic)
try:
    cdo.set_editor_property("ai_controller_class", aic_cls)
    cdo.set_editor_property("auto_possess_ai",
                            unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED)
    say("  - AIControllerClass = BP_GruntAIController / AutoPossessAI = PlacedInWorldOrSpawned")
except Exception as e:
    say("  ! CDO IA: %s" % e)

# valores por defecto de las variables nuevas
for n, v in [("Damage", GDD["Damage"]), ("FireRange", GDD["FireRange"]),
             ("FireInterval", GDD["FireInterval"]), ("Accuracy", GDD["Accuracy"]),
             ("ReactionTime", GDD["ReactionTime"]), ("SearchTime", GDD["SearchTime"]),
             ("SuspicionTime", GDD["SuspicionTime"]),
             ("PatrolSpeed", GDD["PatrolSpeed"]), ("ChaseSpeed", GDD["WalkSpeed"])]:
    try:
        cdo.set_editor_property(n, v)
    except Exception as e:
        say("  ! default %s: %s" % (n, e))
say("  - valores del GDD escritos en el CDO")

mv = cdo.get_editor_property("character_movement")
mv.set_editor_property("max_walk_speed", GDD["WalkSpeed"])
mv.set_editor_property("orient_rotation_to_movement", True)
mv.set_editor_property("rotation_rate", unreal.Rotator(0, 0, 360))
say("  - MaxWalkSpeed = %.0f" % GDD["WalkSpeed"])

hh, hcomp = find_subobject(grunt, "BPC_HealthSystem")
if hcomp:
    for n in ("Health", "MaxHealth"):
        try:
            hcomp.set_editor_property(n, GDD["Health"])
        except Exception as e:
            say("  ! %s: %s" % (n, e))
    try:
        say("  - Vida = %.0f / %.0f" % (hcomp.get_editor_property("Health"),
                                        hcomp.get_editor_property("MaxHealth")))
    except Exception:
        pass
else:
    say("  ! no encontre BPC_HealthSystem en BP_Grunt")

BEL.compile_blueprint(grunt)
EAL.save_asset(P_GRUNT)
say("  compilado y guardado")

# ====================================== 4. rutas de patrulla en el nivel
say("")
say("== 4. Rutas de patrulla en el nivel ==")
w = unreal.UnrealEditorSubsystem().get_editor_world()
say("  mapa: %s" % w.get_name())
tps = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.TargetPoint)
grunts = unreal.GameplayStatics.get_all_actors_of_class(w, gc)

rutas = {}
for t in tps:
    for tag in t.tags:
        s = str(tag)
        if s.startswith("BO_E") and "Soldado" in s:
            rutas.setdefault(s, []).append(t)
for k in rutas:
    rutas[k].sort(key=lambda a: a.get_actor_label())

asignados = 0
sin_ruta = []
for g in grunts:
    lbl = g.get_actor_label()
    pts = rutas.get(lbl)
    if pts:
        try:
            g.set_editor_property("PatrolPoints", pts)
            asignados += 1
            say("  - %-22s <- %d puntos" % (lbl, len(pts)))
        except Exception as e:
            say("  ! %s: %s" % (lbl, e))
    else:
        sin_ruta.append(lbl)

if sin_ruta:
    say("  - sin ruta (estaticos, Encounter 1): %s" % ", ".join(sorted(sin_ruta)))

say("")
say("== RESUMEN ==")
say("  Grunts en el nivel : %d" % len(grunts))
say("  con ruta asignada  : %d" % asignados)
say("  estaticos          : %d" % len(sin_ruta))
say("  puntos de patrulla : %d en %d rutas" % (len(tps), len(rutas)))
say("")
say("  FALTA (no scriptable): entradas de E_GruntState + logica de los grafos.")
