# -*- coding: utf-8 -*-
"""
Valida la infraestructura de la IA del Grunt construida por build_grunt_ai.py.
Informe en Saved/GruntAI_Report.txt. Acaba en "TOTAL DE PROBLEMAS: N".

Uso:
  "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/ue_remote.py Tools/validate_grunt_ai.py
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
SDS = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
SDL = unreal.SubobjectDataBlueprintFunctionLibrary

P_AIC = "/Game/ThirdPerson/AI/BP_GruntAIController"
P_GRUNT = "/Game/ThirdPerson/Blueprints/BP_Grunt"
P_STATE = "/Game/ThirdPerson/AI/E_GruntState"

out = []
problemas = []


def say(m):
    out.append(m)
    print(m)


def chk(cond, ok_msg, bad_msg):
    if cond:
        say("  OK   " + ok_msg)
    else:
        say("  FALLO " + bad_msg)
        problemas.append(bad_msg)


def cdo_of(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def tiene_var(cdo, name):
    try:
        cdo.get_editor_property(name)
        return True
    except Exception:
        return False


def check_vars(bp, esperadas, etiqueta):
    """Blueprint.NewVariables no es legible desde Python, asi que se comprueba
    contra el CDO: existe la propiedad, y no existe un '<nombre>_0' que
    delataria un duplicado renombrado por el editor."""
    cdo = cdo_of(bp)
    for e in esperadas:
        chk(tiene_var(cdo, e), "%s.%s existe" % (etiqueta, e),
            "falta la variable %s.%s" % (etiqueta, e))
        chk(not tiene_var(cdo, e + "_0"),
            "%s.%s sin duplicado" % (etiqueta, e),
            "existe %s.%s_0: variable duplicada" % (etiqueta, e))


def check_float(bp, nombres, etiqueta):
    """Verifica que sean floats de verdad y no enteros (trampa de
    get_basic_type_by_name('float'))."""
    cdo = cdo_of(bp)
    for n in nombres:
        try:
            old = cdo.get_editor_property(n)
            cdo.set_editor_property(n, 1.5)
            v = float(cdo.get_editor_property(n))
            cdo.set_editor_property(n, old)
            chk(abs(v - 1.5) < 0.001, "%s.%s es float real" % (etiqueta, n),
                "%s.%s es ENTERO (1.5 se guarda como %s)" % (etiqueta, n, v))
        except Exception as e:
            chk(False, "", "no pude probar el tipo de %s.%s: %s" % (etiqueta, n, e))


def components(bp):
    res = {}
    for h in SDS.k2_gather_subobject_data_for_blueprint(bp):
        d = SDL.get_data(h)
        o = SDL.get_object_for_blueprint(d, bp)
        if o:
            res[o.get_name()] = o
    return res


say("=" * 62)
say(" VALIDACION DE LA IA DEL GRUNT")
say("=" * 62)

# ------------------------------------------------ 1. BP_GruntAIController
say("")
say("-- 1. BP_GruntAIController --")
chk(EAL.does_asset_exist(P_AIC), "el asset existe", "no existe " + P_AIC)
aic = EAL.load_asset(P_AIC)
esperadas_aic = ["GruntPawn", "TargetPlayer", "LastKnownLocation", "PatrolIndex",
                 "HasSeenPlayer", "IsFiring", "ReactionHandle", "FireHandle",
                 "SearchHandle"]
check_vars(aic, esperadas_aic, "AIC")

# tipos que get_basic_type_by_name se inventa en silencio
caic = cdo_of(aic)
try:
    caic.set_editor_property("LastKnownLocation", unreal.Vector(1, 2, 3))
    chk(True, "AIC.LastKnownLocation es un Vector de verdad", "")
    caic.set_editor_property("LastKnownLocation", unreal.Vector(0, 0, 0))
except Exception:
    chk(False, "", "AIC.LastKnownLocation NO es Vector (se creo como entero): "
                   "hay que borrarla a mano y reejecutar build_grunt_ai.py")
chk(tiene_var(caic, "State"), "AIC.State existe",
    "falta AIC.State (tipo E_GruntState, hay que crearla a mano)")
try:
    v = caic.get_editor_property("State")
    chk(type(v).__name__ == "E_GruntState",
        "AIC.State es del tipo E_GruntState",
        "AIC.State es %s, deberia ser E_GruntState" % type(v).__name__)
except Exception:
    pass

comps = components(aic)
say("  componentes: %s" % ", ".join(sorted(comps)))
perc = None
for k, v in comps.items():
    if isinstance(v, unreal.AIPerceptionComponent):
        perc = v
chk(perc is not None, "AIPerceptionComponent presente",
    "falta el AIPerceptionComponent")
if perc:
    cfgs = perc.get_editor_property("senses_config")
    say("  sentidos: %d" % len(cfgs))
    sight = [c for c in cfgs if isinstance(c, unreal.AISenseConfig_Sight)]
    hear = [c for c in cfgs if isinstance(c, unreal.AISenseConfig_Hearing)]
    chk(len(sight) == 1, "config de vista", "falta o sobra config de vista")
    chk(len(hear) == 1, "config de oido", "falta o sobra config de oido")
    if sight:
        s = sight[0]
        r = s.get_editor_property("sight_radius")
        a = s.get_editor_property("peripheral_vision_angle_degrees")
        lr = s.get_editor_property("lose_sight_radius")
        say("     vista: radio=%.0f perder=%.0f semiangulo=%.0f" % (r, lr, a))
        chk(abs(r - 1200.0) < 0.5, "radio de vista 1200 UU (12 m, GDD)",
            "radio de vista %.0f, el GDD pide 1200" % r)
        chk(abs(a - 45.0) < 0.5, "semiangulo 45 deg (90 deg total, GDD)",
            "semiangulo %.0f, el GDD pide 45" % a)
        aff = s.get_editor_property("detection_by_affiliation")
        chk(aff.get_editor_property("detect_neutrals"),
            "detecta neutrales (sin equipos, el jugador es neutral)",
            "detect_neutrals apagado: NO vera nunca al jugador")
        # el sobre de las pruebas: outer correcto para que se guarde
        chk(s.get_outer() is not None and "Transient" not in s.get_path_name(),
            "config de vista guardada dentro del asset",
            "config de vista en el paquete transitorio: NO se guardara")
    if hear:
        h = hear[0]
        hr = h.get_editor_property("hearing_range")
        say("     oido: rango=%.0f" % hr)
        chk(abs(hr - 600.0) < 0.5, "rango de oido 600 UU (6 m, GDD)",
            "rango de oido %.0f, el GDD pide 600" % hr)

# ------------------------------------------------------------- 2. BP_Grunt
say("")
say("-- 2. BP_Grunt --")
grunt = EAL.load_asset(P_GRUNT)
FLOATS_G = ["Damage", "FireRange", "FireInterval", "Accuracy", "ReactionTime",
            "SearchTime", "SuspicionTime", "PatrolSpeed", "ChaseSpeed"]
check_vars(grunt, ["PatrolPoints"] + FLOATS_G, "Grunt")
check_float(grunt, FLOATS_G, "Grunt")

cg = components(grunt)
say("  componentes: %s" % ", ".join(sorted(cg)))
tr = [v for v in cg.values() if isinstance(v, unreal.TextRenderComponent)]
chk(len(tr) == 1, "indicador StateIcon (TextRender) presente, sin duplicados",
    "hay %d TextRenderComponent en BP_Grunt, deberia haber 1" % len(tr))

gc = BEL.generated_class(grunt)
cdo = unreal.get_default_object(gc)

GDD = {"Damage": 10.0, "FireRange": 1200.0, "FireInterval": 1.0, "Accuracy": 0.60,
       "ReactionTime": 1.5, "SearchTime": 5.0, "SuspicionTime": 3.0,
       "PatrolSpeed": 175.0, "ChaseSpeed": 400.0}
for k, v in sorted(GDD.items()):
    try:
        got = float(cdo.get_editor_property(k))
        chk(abs(got - v) < 0.001, "%s = %s" % (k, got),
            "%s = %s, se esperaba %s" % (k, got, v))
    except Exception as e:
        chk(False, "", "no pude leer %s: %s" % (k, e))

try:
    aicls = cdo.get_editor_property("ai_controller_class")
    chk(aicls is not None and "GruntAIController" in str(aicls),
        "AIControllerClass = %s" % aicls,
        "AIControllerClass = %s (deberia ser BP_GruntAIController)" % aicls)
    ap = cdo.get_editor_property("auto_possess_ai")
    chk(ap == unreal.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED,
        "AutoPossessAI = %s" % ap,
        "AutoPossessAI = %s (deberia ser PlacedInWorldOrSpawned)" % ap)
except Exception as e:
    chk(False, "", "CDO de IA ilegible: %s" % e)

mv = cdo.get_editor_property("character_movement")
ws = mv.get_editor_property("max_walk_speed")
chk(abs(ws - 400.0) < 0.5, "MaxWalkSpeed = 400 (4 m/s, GDD)",
    "MaxWalkSpeed = %.0f, el GDD pide 400" % ws)

hcomp = None
for k, v in cg.items():
    if "HealthSystem" in k:
        hcomp = v
if hcomp:
    hp = hcomp.get_editor_property("Health")
    mhp = hcomp.get_editor_property("MaxHealth")
    chk(abs(hp - 50.0) < 0.5 and abs(mhp - 50.0) < 0.5,
        "Vida = %.0f / %.0f (GDD: baja, 50)" % (hp, mhp),
        "Vida = %.0f / %.0f, el GDD pide 50" % (hp, mhp))
else:
    chk(False, "", "no encontre BPC_HealthSystem en BP_Grunt")

# ----------------------------------------------------------- 3. E_GruntState
say("")
say("-- 3. E_GruntState --")
chk(EAL.does_asset_exist(P_STATE), "el asset existe", "falta " + P_STATE)
en = EAL.load_asset(P_STATE)
ESPERADO = ["Patrolling", "Suspicious", "Investigating", "Combat", "Searching", "Dead"]
# La API de Python no enumera las entradas de un UserDefinedEnum
# (num_enums no existe en el wrapper), asi que se leen del binario del
# .uasset, que es donde estan de verdad.
import os
import re
ruta_enum = os.path.join(unreal.Paths.project_dir(),
                         "Content/ThirdPerson/AI/E_GruntState.uasset")
if os.path.isfile(ruta_enum):
    d = open(ruta_enum, "rb").read()
    internos = sorted({m.decode() for m in re.findall(rb'NewEnumerator\d+', d)})
    presentes = [e for e in ESPERADO if e.encode() in d]
    say("  entradas internas: %s" % ", ".join(internos))
    say("  nombres visibles : %s" % ", ".join(presentes))
    chk(len(internos) >= 6, "tiene las 6 entradas internas",
        "solo %d entradas: faltan por escribir a mano" % len(internos))
    faltan = [e for e in ESPERADO if e not in presentes]
    chk(not faltan, "los 6 nombres del diseno estan puestos",
        "faltan estos nombres en E_GruntState: %s" % ", ".join(faltan))
else:
    chk(False, "", "E_GruntState no esta guardado en disco todavia")

# ------------------------------------------------------------- 4. El nivel
say("")
say("-- 4. Nivel --")
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
say("  mapa: %s" % w.get_name())
grunts = unreal.GameplayStatics.get_all_actors_of_class(w, gc)
say("  Grunts: %d" % len(grunts))
con, sin = 0, 0
for g in grunts:
    try:
        pts = g.get_editor_property("PatrolPoints")
        if pts and len(pts) > 0:
            con += 1
        else:
            sin += 1
    except Exception:
        sin += 1
say("  con ruta de patrulla: %d   estaticos: %d" % (con, sin))
chk(con == 8, "los 8 soldados de E2/E3 tienen ruta",
    "solo %d soldados con ruta, se esperaban 8" % con)
chk(sin == 7, "los 7 de la emboscada E1 son estaticos (correcto segun GDD)",
    "%d estaticos, se esperaban 7" % sin)

navs = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.NavMeshBoundsVolume)
chk(len(navs) >= 1, "NavMeshBoundsVolume presente",
    "no hay NavMeshBoundsVolume: la IA no podra moverse")

# --------------------------------------------------------------- resumen
say("")
say("=" * 62)
say("TOTAL DE PROBLEMAS: %d" % len(problemas))
for p in problemas:
    say("   - " + p)

path = unreal.Paths.project_saved_dir() + "GruntAI_Report.txt"
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("")
print("informe -> " + path)
