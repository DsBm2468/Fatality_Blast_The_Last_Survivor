# -*- coding: utf-8 -*-
"""
Arreglos de la AUDITORIA_2026-08-28 que se pueden hacer SIN tocar cables.

Corre dentro del editor abierto:
    python Tools/ue_remote.py Tools/fix_audit_assets.py

Idempotente. Al final imprime "PROBLEMAS: N".
Lo que NO hace (y no puede): conectar pines. Eso va en
Docs_Contexto/PLAN_ARREGLOS_2026-08-31.md, paso a paso.
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
# ---------------------------------------------------------------- tipos
# TRAMPA (medida el 2026-08-31): BEL.get_basic_type_by_name() devuelve
# PinCategory="int" para TODO menos "bool". Da igual que se le pida
# "double", "float", "real" o "vector". Un Blueprint compila en verde con
# la variable equivocada y el cable de float no engancha.
# Lo que si funciona es construir el EdGraphPinType por texto.
def pin_type(cat, sub="", subobj="None"):
    t = unreal.EdGraphPinType()
    ok = t.import_text(
        '(PinCategory="%s",PinSubCategory="%s",PinSubCategoryObject=%s,'
        'PinSubCategoryMemberReference=(),PinValueType=(),ContainerType=None,'
        'bIsReference=False,bIsConst=False,bIsWeakPointer=False,'
        'bIsUObjectWrapper=False,bSerializeAsSinglePrecisionFloat=False)'
        % (cat, sub, subobj))
    if not ok:
        raise RuntimeError("no se pudo construir el tipo %s/%s" % (cat, sub))
    return t


T_DOUBLE = ("real", "double", "None")
T_VECTOR = ("struct", "", "ScriptStruct'\"/Script/CoreUObject.Vector\"'")

EAL = unreal.EditorAssetLibrary
problemas = []


def log(ok, msg):
    print(("  OK   " if ok else "  FALLO ") + msg)
    if not ok:
        problemas.append(msg)


def cdo(bp):
    return unreal.get_default_object(BEL.generated_class(bp))


def tiene(bp, nombre):
    try:
        cdo(bp).get_editor_property(nombre)
        return True
    except Exception:
        return False


def add_var(bp, nombre, tipo, valor=None, esperado=None):
    """Anade una variable si no existe. add_member_variable NO es idempotente:
    llamarla dos veces crea 'Nombre' y 'Nombre1'. De ahi el guardia."""
    if not tiene(bp, nombre):
        BEL.add_member_variable(bp, nombre, pin_type(*tipo))
        BEL.compile_blueprint(bp)
    if not tiene(bp, nombre):
        log(False, "%s.%s no se creo" % (bp.get_name(), nombre))
        return
    if valor is not None:
        try:
            cdo(bp).set_editor_property(nombre, valor)
        except Exception as e:
            log(False, "%s.%s valor por defecto: %s" % (bp.get_name(), nombre, e))
    v = cdo(bp).get_editor_property(nombre)
    log(esperado is None or isinstance(v, esperado),
        "%s.%s = %r  (%s)" % (bp.get_name(), nombre, v, type(v).__name__))


def load(p):
    a = EAL.load_asset(p)
    if a is None:
        log(False, "no se pudo cargar " + p)
    return a


print("")
print("=" * 70)
print("1. BPC_HealthSystem  -  T-4 (vars muertas) + P-6 (IncomingDamage)")
print("=" * 70)
hs = load("/Game/ThirdPerson/Components/BPC_HealthSystem")
if hs:
    BEL.remove_unused_variables(hs)   # se lleva por delante
    BEL.compile_blueprint(hs)         # las mal tipadas de antes
    antes = [n for n in ("DecayLost", "DecayRate", "DecayMaxLoss") if tiene(hs, n)]
    if antes:
        BEL.remove_unused_variables(hs)
        BEL.compile_blueprint(hs)
    quedan = [n for n in ("DecayLost", "DecayRate", "DecayMaxLoss") if tiene(hs, n)]
    log(not quedan, "T-4: Decay* borradas (quedaban %s)" % (quedan or "ninguna"))
    for n in ("Health", "MaxHealth", "IsDead"):
        log(tiene(hs, n), "T-4: %s sigue viva" % n)
    # P-6: la vida deja de depender de la proteccion para saber cuanto duele.
    add_var(hs, "IncomingDamage", T_DOUBLE, 0.0, float)
    # T-4: funcion vacia
    g = BEL.find_graph(hs, "EvaluateHealthState")
    if g:
        BEL.remove_function_graph(hs, "EvaluateHealthState")
        BEL.compile_blueprint(hs)
    log(BEL.find_graph(hs, "EvaluateHealthState") is None,
        "T-4: EvaluateHealthState (vacia) borrada")

print("")
print("=" * 70)
print("2. BP_GruntAIController  -  G-8 (handles sin uso)")
print("=" * 70)
ai = load("/Game/ThirdPerson/AI/BP_GruntAIController")
if ai:
    BEL.remove_unused_variables(ai)
    BEL.compile_blueprint(ai)
    quedan = [n for n in ("ReactionHandle", "FireHandle", "SearchHandle") if tiene(ai, n)]
    log(not quedan, "G-8: handles de temporizador borrados (quedaban %s)" % (quedan or "ninguno"))
    for n in ("State", "GruntPawn", "TargetPlayer", "LastKnownLocation", "PatrolIndex"):
        log(tiene(ai, n), "G-8: %s sigue viva" % n)
    # G-3: el oido necesita su propio destino, distinto de LastKnownLocation.
    add_var(ai, "NoiseLocation", T_VECTOR)

print("")
print("=" * 70)
print("3. BP_Item_Weapon_Base  -  G-1 causa 1 (el arma no tiene dano)")
print("=" * 70)
wb = load("/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item_Weapon_Base")
if wb:
    BEL.remove_unused_variables(wb)   # limpia una ValueDamage mal tipada
    BEL.compile_blueprint(wb)         # de una pasada anterior
    for n in ("Ownersito", "CurrentMunition", "MaxMunition", "TimeBetweenShots"):
        log(tiene(wb, n), "G-1: %s sigue viva" % n)
    # OJO: la auditoria decia que el arma "tiene su variable ValueDamage al
    # lado". No la tiene: no existe ninguna variable de dano en el arma.
    add_var(wb, "ValueDamage", T_DOUBLE, 10.0, float)   # GDD: convencional 10/impacto
    if tiene(wb, "ValueDamage"):
        BEL.set_blueprint_variable_instance_editable(wb, "ValueDamage", True)
        log(True, "G-1: ValueDamage editable por instancia (10.0 = GDD)")

print("")
print("=" * 70)
print("4. BP_Bandage  -  C-2 (la venda no se puede recoger)")
print("=" * 70)
bd = load("/Game/ThirdPerson/Blueprints/Interactables/BP_Bandage")
if bd:
    log(True, "C-2: BP_Bandage cargado; la interfaz y el grafo van a mano")

print("")
print("=" * 70)
print("5. Guardar")
print("=" * 70)
for p in ["/Game/ThirdPerson/Components/BPC_HealthSystem",
          "/Game/ThirdPerson/AI/BP_GruntAIController",
          "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item_Weapon_Base"]:
    # TRAMPA: en modo Play el editor rechaza el guardado EN SILENCIO.
    log(EAL.save_asset(p, only_if_is_dirty=False), "guardado " + p.rsplit("/", 1)[-1])

print("")
print("PROBLEMAS: %d" % len(problemas))
for p in problemas:
    print("   - " + p)
