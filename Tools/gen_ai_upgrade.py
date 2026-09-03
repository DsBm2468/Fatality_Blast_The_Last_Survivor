# -*- coding: utf-8 -*-
"""
Genera el pegado de la IA AMPLIADA de BP_GruntAIController:

  * deteccion de apuntado  (el jugador te encara con el arma -> reaccionas antes)
  * busqueda de cobertura  (al ser apuntado en combate, te cubres)
  * aviso por radio al sector (GDD pag. 24)
  * flanqueo               (la mitad de la escuadra rodea en vez de cubrirse)

ADITIVO: no reescribe los 194 nodos que ya hay. Se apoya en dos cosas que ya
son ciertas en el grafo actual:
  - Ev_Spot comprueba State DESPUES de su Delay, asi que si aceleramos la
    reaccion poniendo State=Combat, la rama lenta se aborta sola.
  - Ev_Spot comprueba State==Combat al entrar, asi que no reentra.

Eventos nuevos, encadenados por SALTO (tail call), que es como funciona este
proyecto: llamar a un evento personalizado del propio grafo NO vuelve.

  Ev_CacheCover  cachea los puntos de cobertura y sortea el rol de flanqueador
  Ev_AimWatch    bucle de vigilancia del apuntado (se reprograma solo)
  Ev_FastCombat  reaccion acelerada       -> salta a Ev_RadioAlert
  Ev_RadioAlert  avisa al sector          -> salta a Ev_EnterCombat
  Ev_TakeCover   elige y ocupa cobertura  -> vuelve a Ev_AimWatch

Uso:
    python Tools/gen_ai_upgrade.py
    powershell -File Tools/clip.ps1 30
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bpgen import (Graph, cls, obj, CAT_EXEC, CAT_BOOL, CAT_INT, CAT_REAL,
                   CAT_STRING, CAT_OBJECT, CAT_STRUCT, CAT_BYTE, CAT_NAME)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_paste")

# --- clases del motor -------------------------------------------------------
C_ACTOR = "/Script/Engine.Actor"
C_PAWN = "/Script/Engine.Pawn"
C_CHAR = "/Script/Engine.Character"
C_CTRL = "/Script/Engine.Controller"
C_AICON = "/Script/AIModule.AIController"
C_KSL = "/Script/Engine.KismetSystemLibrary"
C_KML = "/Script/Engine.KismetMathLibrary"
C_GSL = "/Script/Engine.GameplayStatics"
C_ARR = "/Script/Engine.KismetArrayLibrary"
C_CAMMGR = "/Script/Engine.PlayerCameraManager"

# --- clases del proyecto ----------------------------------------------------
C_GRUNT = "/Game/ThirdPerson/Blueprints/BP_Grunt.BP_Grunt_C"
C_AICTRL = "/Game/ThirdPerson/AI/BP_GruntAIController.BP_GruntAIController_C"
C_PJ = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter.BP_ThirdPersonCharacter_C"

E_STATE = "UserDefinedEnum'\"/Game/ThirdPerson/AI/E_GruntState.E_GruntState\"'"
S_VECTOR = "ScriptStruct'\"/Script/CoreUObject.Vector\"'"
S_ROTATOR = "ScriptStruct'\"/Script/CoreUObject.Rotator\"'"

# indices internos de E_GruntState
ST_PATROL, ST_SUSPECT, ST_INVESTIGATE = 0, 1, 2
ST_COMBAT, ST_SEARCH, ST_DEAD = 3, 4, 5


# =========================================================== ayudantes

def print_dbg(g, texto, x, y, color="(R=1.0,G=0.55,B=0.0,A=1.0)"):
    p = g.call("PrintString", C_KSL, x, y)
    p.pin("InString", CAT_STRING, default=texto)
    p.pin("bPrintToScreen", CAT_BOOL, default="true")
    p.pin("bPrintToLog", CAT_BOOL, default="true")
    p.pin("Duration", CAT_REAL, sub="double", default="2.000000")
    return p


def delay(g, x, y, defecto="0.250000"):
    """NO existe K2Node_Delay: el Delay es una llamada normal a la funcion
    latente KismetSystemLibrary::Delay (trampa medida el 2026-08-27)."""
    d = g.call("Delay", C_KSL, x, y)
    d.pin("Duration", CAT_REAL, sub="double", default=defecto)
    return d


def get_state(g, x, y):
    return g.var_get("State", CAT_BYTE, x, y, sub_object=E_STATE)


def state_cmp(g, funcion, indice, x, y):
    """Compara State con una entrada del enum.

    TRAMPA (2026-08-27): la firma de EqualEqual_ByteByte es (uint8, uint8),
    o sea BYTE PELADO. Al reconstruirse el nodo pierde la referencia al enum,
    y entonces rechaza 'NewEnumeratorN' con "se esperaba un numero sin signo".
    Hay que darle el INDICE numerico."""
    gv = get_state(g, x, y)
    eq = g.call(funcion, C_KML, x + 200, y, pure=True)
    eq.pin("A", CAT_BYTE, sub_object=E_STATE)
    eq.pin("B", CAT_BYTE, default=str(indice))
    eq.pin("ReturnValue", CAT_BOOL, out=True)
    gv.get("State").to(eq.get("A"))
    return gv, eq


def set_state(g, indice, x, y):
    n = g.var_set("State", CAT_BYTE, x, y, sub_object=E_STATE)
    n.get("State").default = "NewEnumerator%d" % indice
    return n


def get_grunt(g, x, y):
    return g.var_get("GruntPawn", CAT_OBJECT, x, y, sub_object=cls(C_GRUNT))


def grunt_float(g, nombre, x, y):
    """Lee un float del BP_Grunt usando GruntPawn como destino."""
    gp = get_grunt(g, x, y + 90)
    v = g.var_get_target(nombre, CAT_REAL, C_GRUNT, x + 200, y, sub="double")
    gp.get("GruntPawn").to(v.get("self"))
    return v


def loc_de(g, nodo_pin, x, y):
    """K2_GetActorLocation sobre el actor que sale de nodo_pin."""
    n = g.call("K2_GetActorLocation", C_ACTOR, x, y, pure=True)
    n.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    n.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    nodo_pin.to(n.get("self"))
    return n


def dist(g, x, y):
    """OJO: los pines de Vector_Distance se llaman V1 y V2, no A y B."""
    n = g.call("Vector_Distance", C_KML, x, y, pure=True)
    n.pin("V1", CAT_STRUCT, sub_object=S_VECTOR)
    n.pin("V2", CAT_STRUCT, sub_object=S_VECTOR)
    n.pin("ReturnValue", CAT_REAL, out=True, sub="double")
    return n


def op2(g, funcion, x, y, cat_a=CAT_REAL, cat_r=CAT_BOOL, sub="double",
        sub_obj=None, b_def=None):
    n = g.call(funcion, C_KML, x, y, pure=True)
    n.pin("A", cat_a, sub=sub if cat_a == CAT_REAL else "", sub_object=sub_obj)
    n.pin("B", cat_a, sub=sub if cat_a == CAT_REAL else "", sub_object=sub_obj,
          default=b_def)
    n.pin("ReturnValue", cat_r, out=True,
          sub="double" if cat_r == CAT_REAL else "")
    return n


def vec2(g, funcion, x, y, cat_r=CAT_STRUCT):
    n = g.call(funcion, C_KML, x, y, pure=True)
    n.pin("A", CAT_STRUCT, sub_object=S_VECTOR)
    n.pin("B", CAT_STRUCT, sub_object=S_VECTOR)
    n.pin("ReturnValue", cat_r, out=True,
          sub_object=S_VECTOR if cat_r == CAT_STRUCT else None,
          sub="double" if cat_r == CAT_REAL else "")
    return n


# =========================================================== el pegado

def generar():
    g = Graph("AIC_Upgrade", titulo=(
        "PEGADO 30 - IA AMPLIADA\n"
        "Destino: BP_GruntAIController > EventGraph  (SE ANADE, no sustituye)\n"
        "\n"
        "Ev_CacheCover  cachea los TargetPoint con tag 'Cover' y sortea si\n"
        "               este soldado sera flanqueador. Salta a Ev_AimWatch.\n"
        "Ev_AimWatch    cada AimWatchInterval mira si el jugador le esta\n"
        "               apuntando (arma en mano + camara dentro del cono\n"
        "               AimDotThreshold + dentro de AimDetectRange).\n"
        "               Se reprograma SIEMPRE por la rama 0 de la secuencia,\n"
        "               antes de decidir nada, para que el bucle sobreviva a\n"
        "               los saltos de la rama 1.\n"
        "Ev_FastCombat  si te apuntan estando en sospecha, no esperas los\n"
        "               1.5 s: pones Combat ya. La rama lenta de Ev_Spot se\n"
        "               aborta sola porque comprueba State al despertar.\n"
        "Ev_RadioAlert  avisa a los companeros dentro de RadioRange que aun\n"
        "               no estan en combate, y les pasa la ultima posicion.\n"
        "Ev_TakeCover   elige un punto de cobertura y va a el. El supresor\n"
        "               busca al otro lado de si mismo respecto al jugador;\n"
        "               el flanqueador busca de costado."))

    # ==================================================== Ev_CacheCover
    ev_cache = g.custom_event("Ev_CacheCover", 0, 0)

    tags = g.call("GetAllActorsWithTag", C_GSL, 260, 0)
    tags.pin("WorldContextObject", CAT_OBJECT, sub_object=cls("/Script/CoreUObject.Object"), hidden=True)
    tags.pin("Tag", CAT_NAME, default="Cover")
    tags.pin("OutActors", CAT_OBJECT, out=True, sub_object=cls(C_ACTOR), container="Array")
    ev_cache.get("then").to(tags.get("execute"))

    set_cps = g.var_set("CoverPoints", CAT_OBJECT, 620, 0,
                        sub_object=cls(C_ACTOR), container="Array")
    tags.get("then").to(set_cps.get("execute"))
    tags.get("OutActors").to(set_cps.get("CoverPoints"))

    rnd = g.call("RandomBool", C_KML, 620, 260, pure=True)
    rnd.pin("ReturnValue", CAT_BOOL, out=True)
    set_flank = g.var_set("IsFlanker", CAT_BOOL, 900, 0)
    set_cps.get("then").to(set_flank.get("execute"))
    rnd.get("ReturnValue").to(set_flank.get("IsFlanker"))

    p_cache = print_dbg(g, "GRUNT: coberturas cacheadas", 1160, 0)
    set_flank.get("then").to(p_cache.get("execute"))

    d_cache = delay(g, 1440, 0, defecto="1.000000")
    p_cache.get("then").to(d_cache.get("execute"))
    ir_watch = g.call_self("Ev_AimWatch", C_AICTRL, 1720, 0)
    d_cache.get("then").to(ir_watch.get("execute"))

    g.comment("Ev_CacheCover  (lo llama el PUENTE A)", -40, -180, 2000, 560,
              color="(R=0.100000,G=0.500000,B=1.000000,A=0.300000)")

    # ==================================================== Ev_AimWatch
    Y = 700
    ev_aim = g.custom_event("Ev_AimWatch", 0, Y)

    # La secuencia reprograma el bucle ANTES de hacer nada. Asi el bucle
    # sobrevive aunque la rama 1 salte a otro evento y no vuelva.
    seq = g.node_sequence(240, Y, 2)
    ev_aim.get("then").to(seq.get("execute"))

    # --- rama 0: reprogramar
    d_aim = delay(g, 500, Y - 220)
    seq.get("then_0").to(d_aim.get("execute"))
    v_int = grunt_float(g, "AimWatchInterval", 240, Y - 480)
    v_int.get("AimWatchInterval").to(d_aim.get("Duration"))

    gs_d, eq_d = state_cmp(g, "EqualEqual_ByteByte", ST_DEAD, 500, Y - 60)
    br_d = g.branch(900, Y - 220)
    d_aim.get("then").to(br_d.get("execute"))
    eq_d.get("ReturnValue").to(br_d.get("Condition"))
    re_aim = g.call_self("Ev_AimWatch", C_AICTRL, 1160, Y - 180)
    br_d.get("else").to(re_aim.get("execute"))

    # --- rama 1: detectar el apuntado
    pj = g.call("GetPlayerCharacter", C_GSL, 240, Y + 700, pure=True)
    pj.pin("WorldContextObject", CAT_OBJECT, sub_object=cls("/Script/CoreUObject.Object"), hidden=True)
    pj.pin("PlayerIndex", CAT_INT, default="0")
    pj.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_CHAR))

    cast_pj = g.cast(C_PJ, 500, Y + 200)
    seq.get("then_1").to(cast_pj.get("execute"))
    pj.get("ReturnValue").to(cast_pj.get("Object"))

    # si no lleva arma, no puede estar apuntando
    have = g.var_get_target("HaveGun", CAT_BOOL, C_PJ, 800, Y + 460)
    cast_pj.get("AsTarget").to(have.get("self"))
    br_have = g.branch(820, Y + 200)
    cast_pj.get("then").to(br_have.get("execute"))
    have.get("HaveGun").to(br_have.get("Condition"))

    # distancia <= AimDetectRange
    l_pj = loc_de(g, cast_pj.get("AsTarget"), 800, Y + 620)
    gp1 = get_grunt(g, 800, Y + 760)
    l_gr = loc_de(g, gp1.get("GruntPawn"), 1000, Y + 760)
    dd = dist(g, 1240, Y + 660)
    l_gr.get("ReturnValue").to(dd.get("V1"))
    l_pj.get("ReturnValue").to(dd.get("V2"))
    v_rng = grunt_float(g, "AimDetectRange", 1240, Y + 900)
    le = op2(g, "LessEqual_DoubleDouble", 1520, Y + 660)
    dd.get("ReturnValue").to(le.get("A"))
    v_rng.get("AimDetectRange").to(le.get("B"))

    br_rng = g.branch(1120, Y + 200)
    br_have.get("then").to(br_rng.get("execute"))
    le.get("ReturnValue").to(br_rng.get("Condition"))

    # direccion de la camara del jugador (en 3a persona el personaje NO mira
    # a donde apuntas: quien apunta es la camara)
    cam = g.call("GetPlayerCameraManager", C_GSL, 1520, Y + 1060, pure=True)
    cam.pin("WorldContextObject", CAT_OBJECT, sub_object=cls("/Script/CoreUObject.Object"), hidden=True)
    cam.pin("PlayerIndex", CAT_INT, default="0")
    cam.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_CAMMGR))
    rot = g.call("K2_GetActorRotation", C_ACTOR, 1760, Y + 1060, pure=True)
    rot.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    rot.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_ROTATOR)
    cam.get("ReturnValue").to(rot.get("self"))
    fwd = g.call("GetForwardVector", C_KML, 2000, Y + 1060, pure=True)
    fwd.pin("InRot", CAT_STRUCT, sub_object=S_ROTATOR)
    fwd.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    rot.get("ReturnValue").to(fwd.get("InRot"))

    # vector jugador -> soldado, normalizado
    resta = vec2(g, "Subtract_VectorVector", 1760, Y + 1240)
    l_gr.get("ReturnValue").to(resta.get("A"))
    l_pj.get("ReturnValue").to(resta.get("B"))
    norm = g.call("Normal", C_KML, 2000, Y + 1240, pure=True)
    norm.pin("A", CAT_STRUCT, sub_object=S_VECTOR)
    norm.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    resta.get("ReturnValue").to(norm.get("A"))

    dot = vec2(g, "Dot_VectorVector", 2260, Y + 1140, cat_r=CAT_REAL)
    fwd.get("ReturnValue").to(dot.get("A"))
    norm.get("ReturnValue").to(dot.get("B"))

    v_thr = grunt_float(g, "AimDotThreshold", 2260, Y + 1380)
    ge = op2(g, "GreaterEqual_DoubleDouble", 2540, Y + 1140)
    dot.get("ReturnValue").to(ge.get("A"))
    v_thr.get("AimDotThreshold").to(ge.get("B"))

    set_aim = g.var_set("BeingAimedAt", CAT_BOOL, 1420, Y + 200)
    br_rng.get("then").to(set_aim.get("execute"))
    ge.get("ReturnValue").to(set_aim.get("BeingAimedAt"))

    # si NO le apuntan, no hay nada mas que hacer (el bucle ya esta reprogramado)
    br_aim = g.branch(1720, Y + 200)
    set_aim.get("then").to(br_aim.get("execute"))
    set_aim.get("Output_Get").to(br_aim.get("Condition"))

    # le apuntan: guardar objetivo y ultima posicion conocida
    set_tgt = g.var_set("TargetPlayer", CAT_OBJECT, 1980, Y + 200,
                        sub_object=cls(C_ACTOR))
    br_aim.get("then").to(set_tgt.get("execute"))
    cast_pj.get("AsTarget").to(set_tgt.get("TargetPlayer"))

    set_lkl = g.var_set("LastKnownLocation", CAT_STRUCT, 2260, Y + 200,
                        sub_object=S_VECTOR)
    set_tgt.get("then").to(set_lkl.get("execute"))
    l_pj.get("ReturnValue").to(set_lkl.get("LastKnownLocation"))

    p_aim = print_dbg(g, "GRUNT: ME ESTAN APUNTANDO", 2540, Y + 200,
                      color="(R=1.0,G=0.85,B=0.0,A=1.0)")
    set_lkl.get("then").to(p_aim.get("execute"))

    # en sospecha -> reaccion acelerada
    gs_s, eq_s = state_cmp(g, "EqualEqual_ByteByte", ST_SUSPECT, 2540, Y + 440)
    br_s = g.branch(2860, Y + 200)
    p_aim.get("then").to(br_s.get("execute"))
    eq_s.get("ReturnValue").to(br_s.get("Condition"))
    ir_fast = g.call_self("Ev_FastCombat", C_AICTRL, 3160, Y + 120)
    br_s.get("then").to(ir_fast.get("execute"))

    # en combate y sin cobertura -> cubrirse
    gs_c, eq_c = state_cmp(g, "EqualEqual_ByteByte", ST_COMBAT, 2860, Y + 620)
    v_cov = g.var_get("IsInCover", CAT_BOOL, 2860, Y + 800)
    no_cov = g.call("Not_PreBool", C_KML, 3060, Y + 800, pure=True)
    no_cov.pin("A", CAT_BOOL)
    no_cov.pin("ReturnValue", CAT_BOOL, out=True)
    v_cov.get("IsInCover").to(no_cov.get("A"))
    y_and = g.call("BooleanAND", C_KML, 3260, Y + 660, pure=True)
    y_and.pin("A", CAT_BOOL)
    y_and.pin("B", CAT_BOOL)
    y_and.pin("ReturnValue", CAT_BOOL, out=True)
    eq_c.get("ReturnValue").to(y_and.get("A"))
    no_cov.get("ReturnValue").to(y_and.get("B"))

    br_c = g.branch(3480, Y + 200)
    br_s.get("else").to(br_c.get("execute"))
    y_and.get("ReturnValue").to(br_c.get("Condition"))
    ir_cov = g.call_self("Ev_TakeCover", C_AICTRL, 3760, Y + 200)
    br_c.get("then").to(ir_cov.get("execute"))

    g.comment("Ev_AimWatch  (bucle: la rama 0 se reprograma siempre)",
              -40, Y - 560, 4100, 2100,
              color="(R=1.000000,G=0.700000,B=0.000000,A=0.250000)")

    # ==================================================== Ev_FastCombat
    Y = 3100
    ev_fast = g.custom_event("Ev_FastCombat", 0, Y)
    ss = set_state(g, ST_COMBAT, 260, Y)
    ev_fast.get("then").to(ss.get("execute"))
    p_fast = print_dbg(g, "GRUNT: te vi apuntar - reaccion acelerada",
                       540, Y, color="(R=1.0,G=0.2,B=0.0,A=1.0)")
    ss.get("then").to(p_fast.get("execute"))
    ir_radio = g.call_self("Ev_RadioAlert", C_AICTRL, 860, Y)
    p_fast.get("then").to(ir_radio.get("execute"))

    g.comment("Ev_FastCombat", -40, Y - 180, 1200, 400,
              color="(R=1.000000,G=0.100000,B=0.100000,A=0.350000)")

    # ==================================================== Ev_RadioAlert
    Y = 3700
    ev_radio = g.custom_event("Ev_RadioAlert", 0, Y)

    set_alert = g.var_set("SquadAlerted", CAT_BOOL, 260, Y)
    set_alert.get("SquadAlerted").default = "true"
    ev_radio.get("then").to(set_alert.get("execute"))

    todos = g.call("GetAllActorsOfClass", C_GSL, 540, Y)
    todos.pin("WorldContextObject", CAT_OBJECT, sub_object=cls("/Script/CoreUObject.Object"), hidden=True)
    todos.pin("ActorClass", "class", sub_object=cls(C_ACTOR), default=C_GRUNT)
    todos.pin("OutActors", CAT_OBJECT, out=True, sub_object=cls(C_ACTOR), container="Array")
    set_alert.get("then").to(todos.get("execute"))

    fe = g.for_each(860, Y, sub_object=cls(C_ACTOR))
    todos.get("then").to(fe.get("Exec"))
    todos.get("OutActors").to(fe.get("Array"))

    # --- filtro: no soy yo, esta cerca, y aun no esta en combate
    gp2 = get_grunt(g, 860, Y + 420)
    distinto = g.call("NotEqual_ObjectObject", C_KML, 1120, Y + 360, pure=True)
    distinto.pin("A", CAT_OBJECT, sub_object=cls("/Script/CoreUObject.Object"))
    distinto.pin("B", CAT_OBJECT, sub_object=cls("/Script/CoreUObject.Object"))
    distinto.pin("ReturnValue", CAT_BOOL, out=True)
    fe.get("Array Element").to(distinto.get("A"))
    gp2.get("GruntPawn").to(distinto.get("B"))

    l_otro = loc_de(g, fe.get("Array Element"), 1120, Y + 560)
    l_yo = loc_de(g, gp2.get("GruntPawn"), 1120, Y + 700)
    d2 = dist(g, 1380, Y + 620)
    l_otro.get("ReturnValue").to(d2.get("V1"))
    l_yo.get("ReturnValue").to(d2.get("V2"))
    v_radio = grunt_float(g, "RadioRange", 1380, Y + 860)
    cerca = op2(g, "LessEqual_DoubleDouble", 1660, Y + 620)
    d2.get("ReturnValue").to(cerca.get("A"))
    v_radio.get("RadioRange").to(cerca.get("B"))

    and1 = g.call("BooleanAND", C_KML, 1900, Y + 420, pure=True)
    and1.pin("A", CAT_BOOL)
    and1.pin("B", CAT_BOOL)
    and1.pin("ReturnValue", CAT_BOOL, out=True)
    distinto.get("ReturnValue").to(and1.get("A"))
    cerca.get("ReturnValue").to(and1.get("B"))

    br_f = g.branch(1180, Y)
    fe.get("LoopBody").to(br_f.get("execute"))
    and1.get("ReturnValue").to(br_f.get("Condition"))

    # --- avisar: su NoiseLocation = mi LastKnownLocation, y a investigar
    cast_g = g.cast(C_GRUNT, 1460, Y)
    br_f.get("then").to(cast_g.get("execute"))
    fe.get("Array Element").to(cast_g.get("Object"))

    getctrl = g.call("GetController", C_PAWN, 1760, Y + 200, pure=True)
    getctrl.pin("self", CAT_OBJECT, sub_object=cls(C_PAWN), hidden=True)
    getctrl.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_CTRL))
    cast_g.get("AsTarget").to(getctrl.get("self"))

    cast_c = g.cast(C_AICTRL, 1760, Y)
    cast_g.get("then").to(cast_c.get("execute"))
    getctrl.get("ReturnValue").to(cast_c.get("Object"))

    # solo a quien todavia no esta en combate
    otro_st = g.var_get_target("State", CAT_BYTE, C_AICTRL, 2060, Y + 300,
                               sub_object=E_STATE)
    cast_c.get("AsTarget").to(otro_st.get("self"))
    menor = g.call("Less_ByteByte", C_KML, 2280, Y + 300, pure=True)
    menor.pin("A", CAT_BYTE, sub_object=E_STATE)
    menor.pin("B", CAT_BYTE, default=str(ST_INVESTIGATE))
    menor.pin("ReturnValue", CAT_BOOL, out=True)
    otro_st.get("State").to(menor.get("A"))

    br_st = g.branch(2320, Y)
    cast_c.get("then").to(br_st.get("execute"))
    menor.get("ReturnValue").to(br_st.get("Condition"))

    mi_lkl = g.var_get("LastKnownLocation", CAT_STRUCT, 2320, Y + 480,
                       sub_object=S_VECTOR)
    set_nl = g.var_set_target("NoiseLocation", CAT_STRUCT, C_AICTRL, 2600, Y,
                              sub_object=S_VECTOR)
    br_st.get("then").to(set_nl.get("execute"))
    cast_c.get("AsTarget").to(set_nl.get("self"))
    mi_lkl.get("LastKnownLocation").to(set_nl.get("NoiseLocation"))

    # Ev_Investigate de OTRO controlador: esto SI es una llamada de verdad
    # (un evento personalizado es una UFunction de la clase). El "no vuelve"
    # solo pasa al llamarlo dentro del propio grafo.
    inv = g.call("Ev_Investigate", C_AICTRL, 2900, Y)
    inv.pin("self", CAT_OBJECT, sub_object=cls(C_AICTRL), hidden=True)
    set_nl.get("then").to(inv.get("execute"))
    cast_c.get("AsTarget").to(inv.get("self"))

    p_radio = print_dbg(g, "RADIO: companero avisado", 3200, Y,
                        color="(R=0.2,G=0.7,B=1.0,A=1.0)")
    inv.get("then").to(p_radio.get("execute"))

    ir_combat = g.call_self("Ev_EnterCombat", C_AICTRL, 1180, Y - 260)
    fe.get("Completed").to(ir_combat.get("execute"))

    g.comment("Ev_RadioAlert  (avisa al sector y entra en combate)",
              -40, Y - 420, 3600, 1500,
              color="(R=0.200000,G=0.600000,B=1.000000,A=0.250000)")

    # ==================================================== Ev_TakeCover
    Y = 5600
    ev_cov = g.custom_event("Ev_TakeCover", 0, Y)

    # sin coberturas cacheadas no hay nada que hacer: vuelve al bucle
    cps = g.var_get("CoverPoints", CAT_OBJECT, 260, Y + 320,
                    sub_object=cls(C_ACTOR), container="Array")
    largo = g.call("Array_Length", C_ARR, 500, Y + 320, pure=True)
    largo.pin("TargetArray", CAT_OBJECT, sub_object=cls(C_ACTOR), container="Array")
    largo.pin("ReturnValue", CAT_INT, out=True)
    cps.get("CoverPoints").to(largo.get("TargetArray"))
    hay = g.call("Greater_IntInt", C_KML, 740, Y + 320, pure=True)
    hay.pin("A", CAT_INT)
    hay.pin("B", CAT_INT, default="0")
    hay.pin("ReturnValue", CAT_BOOL, out=True)
    largo.get("ReturnValue").to(hay.get("A"))

    br_hay = g.branch(300, Y)
    ev_cov.get("then").to(br_hay.get("execute"))
    hay.get("ReturnValue").to(br_hay.get("Condition"))
    volver1 = g.call_self("Ev_AimWatch", C_AICTRL, 560, Y - 220)
    br_hay.get("else").to(volver1.get("execute"))

    # --- punto de referencia desde el que buscar cobertura
    gp3 = get_grunt(g, 300, Y + 560)
    l_yo2 = loc_de(g, gp3.get("GruntPawn"), 540, Y + 560)
    tgt = g.var_get("TargetPlayer", CAT_OBJECT, 300, Y + 700,
                    sub_object=cls(C_ACTOR))
    l_tg = loc_de(g, tgt.get("TargetPlayer"), 540, Y + 700)

    # direccion jugador -> soldado, normalizada
    dif = vec2(g, "Subtract_VectorVector", 800, Y + 620)
    l_yo2.get("ReturnValue").to(dif.get("A"))
    l_tg.get("ReturnValue").to(dif.get("B"))
    ndir = g.call("Normal", C_KML, 1040, Y + 620, pure=True)
    ndir.pin("A", CAT_STRUCT, sub_object=S_VECTOR)
    ndir.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    dif.get("ReturnValue").to(ndir.get("A"))

    # SUPRESOR: alejarse en linea recta del jugador
    v_stand = grunt_float(g, "CoverStandoff", 1040, Y + 860)
    mul_s = g.call("Multiply_VectorFloat", C_KML, 1320, Y + 620, pure=True)
    mul_s.pin("A", CAT_STRUCT, sub_object=S_VECTOR)
    mul_s.pin("B", CAT_REAL, sub="double")
    mul_s.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    ndir.get("ReturnValue").to(mul_s.get("A"))
    v_stand.get("CoverStandoff").to(mul_s.get("B"))
    ref_s = vec2(g, "Add_VectorVector", 1580, Y + 560)
    l_yo2.get("ReturnValue").to(ref_s.get("A"))
    mul_s.get("ReturnValue").to(ref_s.get("B"))

    # FLANQUEADOR: de costado respecto al eje jugador-soldado
    arriba = g.call("MakeVector", C_KML, 1040, Y + 1040, pure=True)
    arriba.pin("X", CAT_REAL, sub="double", default="0.000000")
    arriba.pin("Y", CAT_REAL, sub="double", default="0.000000")
    arriba.pin("Z", CAT_REAL, sub="double", default="1.000000")
    arriba.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    perp = vec2(g, "Cross_VectorVector", 1320, Y + 1000)
    ndir.get("ReturnValue").to(perp.get("A"))
    arriba.get("ReturnValue").to(perp.get("B"))
    v_flank = grunt_float(g, "FlankOffset", 1320, Y + 1240)
    mul_f = g.call("Multiply_VectorFloat", C_KML, 1580, Y + 1000, pure=True)
    mul_f.pin("A", CAT_STRUCT, sub_object=S_VECTOR)
    mul_f.pin("B", CAT_REAL, sub="double")
    mul_f.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    perp.get("ReturnValue").to(mul_f.get("A"))
    v_flank.get("FlankOffset").to(mul_f.get("B"))
    ref_f = vec2(g, "Add_VectorVector", 1840, Y + 940)
    l_tg.get("ReturnValue").to(ref_f.get("A"))
    mul_f.get("ReturnValue").to(ref_f.get("B"))

    # elegir referencia segun el rol
    v_isf = g.var_get("IsFlanker", CAT_BOOL, 1840, Y + 760)
    sel = g.call("SelectVector", C_KML, 2100, Y + 700, pure=True)
    sel.pin("A", CAT_STRUCT, sub_object=S_VECTOR)
    sel.pin("B", CAT_STRUCT, sub_object=S_VECTOR)
    sel.pin("bPickA", CAT_BOOL)
    sel.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    ref_f.get("ReturnValue").to(sel.get("A"))
    ref_s.get("ReturnValue").to(sel.get("B"))
    v_isf.get("IsFlanker").to(sel.get("bPickA"))

    # el punto de cobertura mas cercano a esa referencia
    cps2 = g.var_get("CoverPoints", CAT_OBJECT, 2100, Y + 480,
                     sub_object=cls(C_ACTOR), container="Array")
    fna = g.call("FindNearestActor", C_GSL, 2400, Y + 480, pure=True)
    fna.pin("Origin", CAT_STRUCT, sub_object=S_VECTOR)
    fna.pin("ActorsToCheck", CAT_OBJECT, sub_object=cls(C_ACTOR), container="Array")
    fna.pin("Distance", CAT_REAL, out=True, sub="double")
    fna.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_ACTOR))
    sel.get("ReturnValue").to(fna.get("Origin"))
    cps2.get("CoverPoints").to(fna.get("ActorsToCheck"))

    set_cur = g.var_set("CurrentCover", CAT_OBJECT, 620, Y,
                        sub_object=cls(C_ACTOR))
    br_hay.get("then").to(set_cur.get("execute"))
    fna.get("ReturnValue").to(set_cur.get("CurrentCover"))

    val = g.is_valid(900, Y, sub_object=cls(C_ACTOR))
    set_cur.get("then").to(val.get("Exec"))
    set_cur.get("Output_Get").to(val.get("InputObject"))
    volver2 = g.call_self("Ev_AimWatch", C_AICTRL, 1160, Y - 220)
    val.get("Is Not Valid").to(volver2.get("execute"))

    mover = g.call("MoveToActor", C_AICON, 1180, Y)
    mover.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    mover.pin("Goal", CAT_OBJECT, sub_object=cls(C_ACTOR))
    mover.pin("AcceptanceRadius", CAT_REAL, sub="double", default="60.000000")
    mover.pin("bStopOnOverlap", CAT_BOOL, default="true")
    mover.pin("bUsePathfinding", CAT_BOOL, default="true")
    mover.pin("bCanStrafe", CAT_BOOL, default="true")
    mover.pin("bAllowPartialPath", CAT_BOOL, default="true")
    val.get("Is Valid").to(mover.get("execute"))
    set_cur.get("Output_Get").to(mover.get("Goal"))

    set_inc = g.var_set("IsInCover", CAT_BOOL, 1500, Y)
    set_inc.get("IsInCover").default = "true"
    mover.get("then").to(set_inc.get("execute"))

    p_cov = print_dbg(g, "GRUNT: a cubierto", 1780, Y,
                      color="(R=0.0,G=0.9,B=0.5,A=1.0)")
    set_inc.get("then").to(p_cov.get("execute"))

    volver3 = g.call_self("Ev_AimWatch", C_AICTRL, 2080, Y)
    p_cov.get("then").to(volver3.get("execute"))

    g.comment("Ev_TakeCover  (supresor se aleja, flanqueador rodea)",
              -40, Y - 420, 2800, 1900,
              color="(R=0.000000,G=0.800000,B=0.400000,A=0.250000)")

    # ============================ PUENTE A: enganche en ReceiveBeginPlay
    # Hoy BeginPlay acaba en "call Ev_StartPatrol", que es un SALTO y no
    # vuelve, asi que no se puede encadenar nada detras. La solucion es un
    # Sequence: then_0 arranca el cacheo (que cede el control con su Delay) y
    # then_1 sigue con la patrulla de siempre.
    Y = 7900
    seq_bp = g.node_sequence(300, Y, 2)
    ir_cache = g.call_self("Ev_CacheCover", C_AICTRL, 620, Y - 120)
    seq_bp.get("then_0").to(ir_cache.get("execute"))
    g.comment("PUENTE A - meter entre 'SET State' y 'call Ev_StartPatrol' de "
              "ReceiveBeginPlay:  SET State -> este Sequence;  then_1 -> "
              "call Ev_StartPatrol", -40, Y - 320, 1100, 620,
              color="(R=1.000000,G=0.000000,B=0.600000,A=0.300000)")

    # ============================ PUENTE B: no salir de la cobertura
    # Ev_FireLoop reemite MoveToActor(jugador) cada vez que no puede disparar,
    # lo que cancelaria el movimiento a cobertura al segundo siguiente. Este
    # Branch lo salta mientras IsInCover este puesto.
    Y = 8700
    v_inc = g.var_get("IsInCover", 'bool', 300, Y + 220)
    br_inc = g.branch(560, Y)
    v_inc.get("IsInCover").to(br_inc.get("Condition"))
    g.comment("PUENTE B - en Ev_FireLoop:  las DOS entradas que hoy van a "
              "'MoveToActor' (la salida False del Branch de rango y la salida "
              "True del Branch del trazo) -> este Branch;  su False -> "
              "MoveToActor;  su True -> el Delay de 1 s",
              -40, Y - 320, 1100, 700,
              color="(R=1.000000,G=0.000000,B=0.600000,A=0.300000)")

    ruta = g.save(os.path.join(OUT, "30_AIC_Upgrade.txt"))
    print("  %-32s %3d nodos" % ("30_AIC_Upgrade.txt", len(g.nodes)))
    return ruta


if __name__ == "__main__":
    print("Generando el pegado de la IA ampliada en %s\n" % OUT)
    generar()
