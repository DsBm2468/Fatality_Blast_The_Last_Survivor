# -*- coding: utf-8 -*-
"""
Genera el texto de pegado de los grafos de la IA del Grunt.
Python puro, no necesita el editor abierto.

    python Tools/gen_grunt_paste.py

Escribe en Tools/bp_paste/NN_*.txt. Para cargar uno en el portapapeles:

    powershell -File Tools\\clip.ps1 01

DISENO (por que esta hecho asi)
-------------------------------
* Toda la logica vive en BP_GruntAIController salvo la muerte, que va en
  BP_Grunt porque ahi esta el dispatcher OnDeath.
* NO se usan Behavior Trees: los hijos de un nodo BT son 'protected' y no hay
  forma de generarlos por script (medido el 2026-08-26).
* NO se usan funciones con parametros: K2Node_FunctionEntry no se puede pegar.
* Las transiciones de estado son SALTOS a eventos personalizados. En un
  ubergraph, llamar a un evento propio es un salto y NO vuelve, asi que cada
  transicion es lo ultimo que hace su rama (tail call). El diseno se apoya en
  eso en vez de pelearse con ello.
* Se usan nodos Delay en vez de temporizadores: Set Timer by Event necesita un
  K2Node_CreateDelegate con el GUID de la funcion destino, que es fragil.
  Cada rama con Delay se protege comprobando State al despertar.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bpgen import (Graph, cls, obj, CAT_EXEC, CAT_BOOL, CAT_INT, CAT_REAL, CAT_TEXT,
                   CAT_STRING, CAT_NAME, CAT_OBJECT, CAT_CLASS, CAT_STRUCT,
                   CAT_BYTE)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_paste")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

# --- clases del motor -------------------------------------------------------
C_OBJ_BASE = "/Script/CoreUObject.Object"
C_ACTOR = "/Script/Engine.Actor"
C_PAWN = "/Script/Engine.Pawn"
C_CHAR = "/Script/Engine.Character"
C_CTRL = "/Script/Engine.Controller"
C_AICON = "/Script/AIModule.AIController"
C_PERC = "/Script/AIModule.AIPerceptionComponent"
C_KSL = "/Script/Engine.KismetSystemLibrary"
C_KML = "/Script/Engine.KismetMathLibrary"
C_GSL = "/Script/Engine.GameplayStatics"
C_ARR = "/Script/Engine.KismetArrayLibrary"
C_CMC = "/Script/Engine.CharacterMovementComponent"
C_SCENE = "/Script/Engine.SceneComponent"
C_TEXTR = "/Script/Engine.TextRenderComponent"
C_AIPERCSYS = "/Script/AIModule.AIPerceptionSystem"
C_AISENSE = "/Script/AIModule.AISense"
C_AISENSE_SIGHT = "/Script/AIModule.AISense_Sight"
C_PRIM = "/Script/Engine.PrimitiveComponent"
C_MESH = "/Script/Engine.MeshComponent"
C_SKEL = "/Script/Engine.SkinnedMeshComponent"

# --- clases del proyecto ----------------------------------------------------
C_GRUNT = "/Game/ThirdPerson/Blueprints/BP_Grunt.BP_Grunt_C"
C_AICTRL = "/Game/ThirdPerson/AI/BP_GruntAIController.BP_GruntAIController_C"
C_BPI_HEALTH = "/Game/ThirdPerson/Blueprints/Interfaces/BPI_HealthSystem.BPI_HealthSystem_C"

E_STATE = "UserDefinedEnum'\"/Game/ThirdPerson/AI/E_GruntState.E_GruntState\"'"
E_DMGTYPE = "UserDefinedEnum'\"/Game/ThirdPerson/Blueprints/Interfaces/DamageSystem/E_DamageType.E_DamageType\"'"
E_DMGREACT = "UserDefinedEnum'\"/Game/ThirdPerson/Blueprints/Interfaces/DamageSystem/E_DamageReaction.E_DamageReaction\"'"
S_TAKEDMG = "ScriptStruct'\"/Game/ThirdPerson/Blueprints/Interfaces/DamageSystem/S_TakeDamage.S_TakeDamage\"'"
S_VECTOR = "ScriptStruct'\"/Script/CoreUObject.Vector\"'"
S_AISTIM = "ScriptStruct'\"/Script/AIModule.AIStimulus\"'"
E_PATHSTATUS = "Enum'\"/Script/AIModule.EPathFollowingStatus\"'"
E_TRACETYPE = "Enum'\"/Script/Engine.ETraceTypeQuery\"'"
E_DRAWDEBUG = "Enum'\"/Script/Engine.EDrawDebugTrace\"'"

# Entradas internas de los enums. Los UserDefinedEnum guardan
# NewEnumeratorN y el nombre bonito solo en el DisplayNameMap.
ST_PATROL = "NewEnumerator0"      # Patrolling
ST_SUSPECT = "NewEnumerator1"     # Suspicious
ST_INVESTIGATE = "NewEnumerator2"  # Investigating
ST_COMBAT = "NewEnumerator3"      # Combat
ST_SEARCH = "NewEnumerator4"      # Searching
ST_DEAD = "NewEnumerator5"        # Dead

DMG_CONVENTIONAL = "NewEnumerator0"   # ConventionalBullet
REACT_HIT = "NewEnumerator1"          # HitReaction

# Nombres internos de los campos de S_TakeDamage, leidos del .uasset.
# OJO: si se toca el struct hay que volver a leerlos, cambian.
F_VALUE = "ValueDamage_2_3399F16E4F048EE316C42FA07B3A6EB3"
F_TYPE = "DamageType_14_3683AE664ABB2D7830ADD685F555DD4C"
F_REACT = "DamageReaction_15_E3DFFECC4F6638DE259EA594EB65E007"
F_BLOCK = "CanBeBlocked_12_A15F2A2C4E9DC54D65074688153CFCFA"
F_FORCE = "ShouldForceInterrupt_11_F798AF9644C08D97F4B4068725B80C89"
F_INSTIG = "DamageInstigator_18_608F481847B2CB83E6C1469C3E03BB17"

generados = []


def emit(g, fichero):
    g.save(os.path.join(OUT, fichero))
    generados.append((fichero, len(g.nodes)))
    print("  %-44s %2d nodos" % (fichero, len(g.nodes)))


# --------------------------------------------------------------- ayudantes

def get_state(g, x, y):
    return g.var_get("State", CAT_BYTE, x, y, sub_object=E_STATE)


def set_state(g, entrada, x, y):
    n = g.var_set("State", CAT_BYTE, x, y, sub_object=E_STATE)
    n.get("State").default = entrada
    return n


def state_es(g, entrada, x, y):
    """Devuelve (nodo_get, nodo_igual). El pin ReturnValue del segundo es el
    bool que se enchufa a un Branch.

    TRAMPA: la firma de EqualEqual_ByteByte es (uint8 A, uint8 B), o sea BYTE
    PELADO. Al reconstruirse el nodo pierde la referencia al enum que le
    pongamos en PinSubCategoryObject, y entonces rechaza el nombre de la
    entrada con "se esperaba un numero sin signo para una propiedad byte".
    Hay que darle el INDICE. Solo colaba NewEnumerator0 porque el compilador
    lo lee como el numero 0. Medido el 2026-08-27."""
    indice = entrada.replace("NewEnumerator", "")
    gv = get_state(g, x, y)
    eq = g.call("EqualEqual_ByteByte", C_KML, x + 190, y, pure=True)
    eq.pin("A", CAT_BYTE, sub_object=E_STATE)
    eq.pin("B", CAT_BYTE, default=indice)
    eq.pin("ReturnValue", CAT_BOOL, out=True)
    gv.get("State").to(eq.get("A"))
    return gv, eq


def print_dbg(g, texto, x, y, color="(R=0.0,G=1.0,B=0.4,A=1.0)"):
    """Traza. En este proyecto el PrintString NO es andamiaje: las escrituras
    a instancias de PIE se revierten y el log no, asi que es el instrumento
    de medida (ver LAB_DE_PRUEBAS.md)."""
    p = g.call("PrintString", C_KSL, x, y)
    p.pin("InString", CAT_STRING, default=texto)
    p.pin("bPrintToScreen", CAT_BOOL, default="true")
    p.pin("bPrintToLog", CAT_BOOL, default="true")
    p.pin("Duration", CAT_REAL, sub="double", default="2.000000")
    return p


def delay(g, segundos_pin_default, x, y):
    """TRAMPA: NO existe la clase K2Node_Delay. El nodo Delay de Blueprint es
    un K2Node_CallFunction normal a la funcion latente KismetSystemLibrary
    ::Delay. Usar una clase de nodo inexistente no da error al pegar: el nodo
    simplemente NO se crea, y con el desaparecen todas las conexiones que
    pasaban por el. Costo una sesion entera de depuracion el 2026-08-27."""
    d = g.call("Delay", C_KSL, x, y)
    d.pin("Duration", CAT_REAL, sub="double", default=segundos_pin_default)
    return d


def get_grunt(g, x, y):
    return g.var_get("GruntPawn", CAT_OBJECT, x, y, sub_object=cls(C_GRUNT))


def grunt_float(g, nombre, x, y):
    """Lee una variable float del BP_Grunt (Damage, FireRange...) usando
    GruntPawn como destino."""
    gp = get_grunt(g, x, y + 90)
    v = g.var_get_target(nombre, CAT_REAL, C_GRUNT, x + 190, y, sub="double")
    gp.get("GruntPawn").to(v.get("self"))
    return v


def set_speed(g, nombre_var_grunt, x, y):
    """GruntPawn -> GetCharacterMovement -> Set MaxWalkSpeed = <var del Grunt>"""
    gp = get_grunt(g, x, y + 130)
    # OJO: "Get Character Movement" NO es una funcion, es la propiedad
    # CharacterMovement de ACharacter. Verificado por reflexion.
    cm = g.var_get_target("CharacterMovement", CAT_OBJECT, C_CHAR,
                          x + 190, y + 130, sub_object=cls(C_CMC))
    gp.get("GruntPawn").to(cm.get("self"))

    sv = g.var_set_target("MaxWalkSpeed", CAT_REAL, C_CMC, x + 420, y, sub="double")
    cm.get("CharacterMovement").to(sv.get("self"))

    val = grunt_float(g, nombre_var_grunt, x + 190, y - 150)
    val.get(nombre_var_grunt).to(sv.get("MaxWalkSpeed"))
    return sv


def set_icon(g, texto, x, y, visible=True, rojo=False):
    """GruntPawn -> StateIcon -> SetText + SetVisibility."""
    gp = get_grunt(g, x, y + 150)
    ic = g.var_get_target("StateIcon", CAT_OBJECT, C_GRUNT, x + 190, y + 150,
                          sub_object=cls(C_TEXTR))
    gp.get("GruntPawn").to(ic.get("self"))

    # OJO: hay DOS funciones. SetText es la vieja con FString, obsoleta y
    # no invocable desde Blueprint; el nodo "Set Text" real es K2_SetText.
    # Llamar a la obsoleta hace que Unreal descarte el nodo al pegar.
    #
    # Y su pin Value es POR REFERENCIA, asi que no admite un literal escrito
    # en el pin: exige un cable. Se le pone delante un Make Literal Text.
    lit = g.call("MakeLiteralText", C_KSL, x + 190, y - 120, pure=True)
    lit.pin("Value", CAT_TEXT, default=texto)
    lit.pin("ReturnValue", CAT_TEXT, out=True)

    st = g.call("K2_SetText", C_TEXTR, x + 400, y)
    st.pin("self", CAT_OBJECT, sub_object=cls(C_TEXTR), hidden=True)
    st.pin("Value", CAT_TEXT, is_ref=True)
    lit.get("ReturnValue").to(st.get("Value"))
    ic.get("StateIcon").to(st.get("self"))

    vis = g.call("SetVisibility", C_SCENE, x + 640, y)
    vis.pin("self", CAT_OBJECT, sub_object=cls(C_SCENE), hidden=True)
    vis.pin("bNewVisibility", CAT_BOOL, default="true" if visible else "false")
    vis.pin("bPropagateToChildren", CAT_BOOL, default="false")
    ic.get("StateIcon").to(vis.get("self"))

    st.get("then").to(vis.get("execute"))
    return st, vis


# =========================================================================
# 01 - BeginPlay
# =========================================================================
def paste_01():
    g = Graph("AIC_BeginPlay", titulo=(
        "PEGADO 01 - ARRANQUE\n"
        "Destino: BP_GruntAIController > EventGraph\n"
        "\n"
        "Event BeginPlay -> cachea el pawn en GruntPawn -> estado Patrulla\n"
        "-> salta a Ev_StartPatrol (que llega en el pegado 03).\n"
        "\n"
        "Hasta que no pegues el 03 el compilador se quejara de que\n"
        "Ev_StartPatrol no existe. Es normal: pega 01..05 y compila al final."))

    ev = g.event("ReceiveBeginPlay", C_ACTOR, 0, 0)

    pawn = g.call("K2_GetPawn", C_CTRL, 260, 180, pure=True)
    pawn.pin("self", CAT_OBJECT, sub_object=cls(C_CTRL), hidden=True)
    pawn.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_PAWN))

    cast = g.cast(C_GRUNT, 500, 0)
    pawn.get("ReturnValue").to(cast.get("Object"))
    ev.get("then").to(cast.get("execute"))

    setp = g.var_set("GruntPawn", CAT_OBJECT, 820, 0, sub_object=cls(C_GRUNT))
    cast.get("AsTarget").to(setp.get("GruntPawn"))
    cast.get("then").to(setp.get("execute"))

    sst = set_state(g, ST_PATROL, 1080, 0)
    setp.get("then").to(sst.get("execute"))

    ini = g.call_self("Ev_StartPatrol", C_AICTRL, 1340, 0)
    sst.get("then").to(ini.get("execute"))

    g.comment("ARRANQUE - cachear el pawn y empezar a patrullar",
              -40, -160, 1560, 420,
              color="(R=0.100000,G=0.500000,B=1.000000,A=0.350000)")

    # ---------------- Ev_StartPatrol ------------------------------------
    # Se define AQUI, en el mismo pegado que lo llama por primera vez.
    # Si la definicion llega en un pegado POSTERIOR a la primera llamada,
    # Unreal considera el nombre ocupado y renombra el evento a "CustomEvent",
    # dejando las llamadas apuntando al vacio. Medido el 2026-08-27: paso dos
    # veces seguidas con Ev_StartPatrol, mientras que Ev_Spot (definido y
    # llamado en el mismo pegado) nunca fallo.
    y0 = 700
    evp = g.custom_event("Ev_StartPatrol", 0, y0)
    sst2 = set_state(g, ST_PATROL, 260, y0)
    evp.get("then").to(sst2.get("execute"))

    ic, vis = set_icon(g, "", 520, y0, visible=False)
    sst2.get("then").to(ic.get("execute"))

    sp = set_speed(g, "PatrolSpeed", 1280, y0)
    vis.get("then").to(sp.get("execute"))

    nxt = g.call_self("Ev_MoveToPatrolPoint", C_AICTRL, 1800, y0)
    sp.get("then").to(nxt.get("execute"))

    g.comment("Ev_StartPatrol", -40, y0 - 200, 2020, 560,
              color="(R=0.200000,G=0.800000,B=0.300000,A=0.350000)")

    emit(g, "01_AIC_BeginPlay.txt")


# =========================================================================
# 02 - Percepcion
# =========================================================================
def paste_02():
    g = Graph("AIC_Perception", titulo=(
        "PEGADO 02 - PERCEPCION\n"
        "Destino: BP_GruntAIController > EventGraph\n"
        "\n"
        "Evento OnTargetPerceptionUpdated del componente AIPerception.\n"
        "  Estimulo percibido  -> guarda objetivo y su posicion -> Ev_Spot\n"
        "  Estimulo perdido    -> Ev_LosePlayer\n"
        "\n"
        "Ev_Spot aplica el tiempo de reaccion del GDD (1.5 s): primero\n"
        "sospecha con el '?' y solo despues pasa a combate con el '!'.\n"
        "Si el jugador se va durante la espera, el guardia de estado corta."))

    # --- evento del componente ------------------------------------------
    ev = g.component_bound_event(
        "AIPerception", "OnTargetPerceptionUpdated", C_PERC,
        "BP_GruntAIController", 0, 0)
    ev.pin("Actor", CAT_OBJECT, out=True, sub_object=cls(C_ACTOR))
    ev.pin("Stimulus", CAT_STRUCT, out=True, sub_object=S_AISTIM)

    # solo nos interesa el jugador
    pc = g.call("GetPlayerPawn", C_GSL, 300, 320, pure=True)
    pc.pin("PlayerIndex", CAT_INT, default="0")
    pc.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_PAWN))

    eq = g.call("EqualEqual_ObjectObject", C_KML, 520, 300, pure=True)
    eq.pin("A", CAT_OBJECT, sub_object=cls(C_OBJ_BASE))
    eq.pin("B", CAT_OBJECT, sub_object=cls(C_OBJ_BASE))
    eq.pin("ReturnValue", CAT_BOOL, out=True)
    ev.get("Actor").to(eq.get("A"))
    pc.get("ReturnValue").to(eq.get("B"))

    br_player = g.branch(760, 0)
    ev.get("then").to(br_player.get("execute"))
    eq.get("ReturnValue").to(br_player.get("Condition"))

    # bSuccessfullySensed del estimulo
    # No hay funcion "BreakAIStimulus": es un nodo Break Struct. El pin de
    # entrada se llama como el struct y el campo real es bSuccessfullySensed.
    bs = g.break_struct("/Script/AIModule.AIStimulus", "AIStimulus", 760, 330)
    bs.pin("bSuccessfullySensed", CAT_BOOL, out=True)
    ev.get("Stimulus").to(bs.get("AIStimulus"))

    bs.pin("StimulusLocation", CAT_STRUCT, out=True, sub_object=S_VECTOR)

    # --- G-3: ramificar POR SENTIDO -------------------------------------
    # Antes NO se miraba de que sentido venia el estimulo: la vista y el oido
    # entraban por la misma puerta. Consecuencias medidas en la auditoria del
    # 2026-08-28: Ev_Investigate tenia CERO llamadas (el oido de 6 m no hacia
    # nada) y cualquier estimulo que caducaba soltaba el objetivo (25 "perdi
    # al objetivo" contra 16 entradas en combate).
    #
    # OJO: GetSenseClassForStimulus es BlueprintCallable, NO pura. Lleva
    # pines de ejecucion y hay que meterla en la cadena. Su pin
    # WorldContextObject no se declara: al pegar, el nodo lo reconstruye
    # desde la firma y el compilador lo rellena solo.
    sense = g.call("GetSenseClassForStimulus", C_AIPERCSYS, 1020, 0)
    sense.pin("Stimulus", CAT_STRUCT, sub_object=S_AISTIM)
    sense.pin("ReturnValue", CAT_CLASS, out=True, sub_object=cls(C_AISENSE))
    ev.get("Stimulus").to(sense.get("Stimulus"))
    br_player.get("then").to(sense.get("execute"))

    es_vista = g.call("EqualEqual_ClassClass", C_KML, 1280, 330, pure=True)
    es_vista.pin("A", CAT_CLASS, sub_object=cls(C_OBJ_BASE))
    es_vista.pin("B", CAT_CLASS, sub_object=cls(C_OBJ_BASE),
                 default=cls(C_AISENSE_SIGHT))
    es_vista.pin("ReturnValue", CAT_BOOL, out=True)
    sense.get("ReturnValue").to(es_vista.get("A"))

    br_sense = g.branch(1560, 0)
    sense.get("then").to(br_sense.get("execute"))
    es_vista.get("ReturnValue").to(br_sense.get("Condition"))

    # --- VISTA ----------------------------------------------------------
    br_sensed = g.branch(1820, -60)
    br_sense.get("then").to(br_sensed.get("execute"))
    bs.get("bSuccessfullySensed").to(br_sensed.get("Condition"))

    # --- percibido: guardar objetivo y posicion -------------------------
    set_t = g.var_set("TargetPlayer", CAT_OBJECT, 2080, -160,
                      sub_object=cls(C_ACTOR))
    ev.get("Actor").to(set_t.get("TargetPlayer"))
    br_sensed.get("then").to(set_t.get("execute"))

    loc = g.call("K2_GetActorLocation", C_ACTOR, 2080, 60, pure=True)
    loc.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    loc.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    ev.get("Actor").to(loc.get("self"))

    set_l = g.var_set("LastKnownLocation", CAT_STRUCT, 2360, -160,
                      sub_object=S_VECTOR)
    loc.get("ReturnValue").to(set_l.get("LastKnownLocation"))
    set_t.get("then").to(set_l.get("execute"))

    spot = g.call_self("Ev_Spot", C_AICTRL, 2640, -160)
    set_l.get("then").to(spot.get("execute"))

    # perdido DE VISTA: eso si suelta el objetivo
    lose = g.call_self("Ev_LosePlayer", C_AICTRL, 2080, 180)
    br_sensed.get("else").to(lose.get("execute"))

    # --- OIDO -----------------------------------------------------------
    # G-4: un estimulo de oido que caduca NO suelta el objetivo. La rama
    # 'else' muere aqui a proposito.
    br_heard = g.branch(1820, 560)
    br_sense.get("else").to(br_heard.get("execute"))
    bs.get("bSuccessfullySensed").to(br_heard.get("Condition"))

    set_n = g.var_set("NoiseLocation", CAT_STRUCT, 2080, 560,
                      sub_object=S_VECTOR)
    bs.get("StimulusLocation").to(set_n.get("NoiseLocation"))
    br_heard.get("then").to(set_n.get("execute"))

    inv = g.call_self("Ev_Investigate", C_AICTRL, 2360, 560)
    set_n.get("then").to(inv.get("execute"))

    g.comment("PERCEPCION - filtra al jugador y separa VISTA de OIDO",
              -40, -280, 2880, 1080,
              color="(R=1.000000,G=0.800000,B=0.100000,A=0.350000)")

    # ================= Ev_Spot ==========================================
    y0 = 780
    spot_ev = g.custom_event("Ev_Spot", 0, y0)

    gv, eqc = state_es(g, ST_COMBAT, 260, y0 + 240)
    br_ya = g.branch(700, y0)
    spot_ev.get("then").to(br_ya.get("execute"))
    eqc.get("ReturnValue").to(br_ya.get("Condition"))
    # si ya esta en combate no reinicia la reaccion (rama 'then' muere aqui)

    sst = set_state(g, ST_SUSPECT, 960, y0 + 60)
    br_ya.get("else").to(sst.get("execute"))

    ic1, vis1 = set_icon(g, "?", 1220, y0 + 60)
    sst.get("then").to(ic1.get("execute"))

    pr1 = print_dbg(g, "GRUNT: sospecha (?)", 1980, y0 + 60)
    vis1.get("then").to(pr1.get("execute"))

    # tiempo de reaccion del GDD
    rt = grunt_float(g, "ReactionTime", 2240, y0 + 250)
    dl = delay(g, "1.500000", 2240, y0 + 60)
    rt.get("ReactionTime").to(dl.get("Duration"))
    pr1.get("then").to(dl.get("execute"))

    # al despertar: sigue siendo el mismo estado?
    gv2, eqs = state_es(g, ST_SUSPECT, 2500, y0 + 250)
    br_sig = g.branch(2940, y0 + 60)
    dl.get("then").to(br_sig.get("execute"))
    eqs.get("ReturnValue").to(br_sig.get("Condition"))

    comb = g.call_self("Ev_EnterCombat", C_AICTRL, 3200, y0 + 60)
    br_sig.get("then").to(comb.get("execute"))

    g.comment("Ev_Spot - sospecha, espera ReactionTime (1.5 s) y entra en combate",
              -40, y0 - 160, 3420, 620,
              color="(R=1.000000,G=0.500000,B=0.000000,A=0.350000)")

    # ================= Ev_LosePlayer ====================================
    y1 = 1560
    lose_ev = g.custom_event("Ev_LosePlayer", 0, y1)
    gv3, eqd = state_es(g, ST_DEAD, 260, y1 + 220)
    br_d = g.branch(700, y1)
    lose_ev.get("then").to(br_d.get("execute"))
    eqd.get("ReturnValue").to(br_d.get("Condition"))

    sea = g.call_self("Ev_StartSearch", C_AICTRL, 960, y1 + 60)
    br_d.get("else").to(sea.get("execute"))

    g.comment("Ev_LosePlayer - si no esta muerto, pasa a buscar",
              -40, y1 - 160, 1180, 560,
              color="(R=0.600000,G=0.600000,B=0.600000,A=0.350000)")

    emit(g, "02_AIC_Percepcion.txt")



# =========================================================================
# 03 - Patrulla
# =========================================================================
def paste_03():
    g = Graph("AIC_Patrol", titulo=(
        "PEGADO 03 - PATRULLA\n"
        "Destino: BP_GruntAIController > EventGraph\n"
        "\n"
        "Ev_StartPatrol      pone estado Patrulla, quita el icono, baja la\n"
        "                    velocidad a PatrolSpeed y va al punto actual.\n"
        "Ev_NextPatrolPoint  avanza el indice en circulo y mueve.\n"
        "ReceiveMoveCompleted espera 2 s y encadena al siguiente punto.\n"
        "\n"
        "Los 7 soldados del Encounter 1 no tienen PatrolPoints (estan en la\n"
        "emboscada de la mesa): el Length=0 los deja quietos, que es lo que\n"
        "pide el GDD."))

    # ---------------- Ev_MoveToPatrolPoint ------------------------------
    y0 = 700
    mv = g.custom_event("Ev_MoveToPatrolPoint", 0, y0)

    gp = get_grunt(g, 200, y0 + 420)
    arr = g.var_get_target("PatrolPoints", CAT_OBJECT, C_GRUNT, 420, y0 + 420,
                           sub_object=cls("/Script/Engine.TargetPoint"),
                           container="Array")
    gp.get("GruntPawn").to(arr.get("self"))

    ln = g.call("Array_Length", C_ARR, 700, y0 + 500, pure=True,
                node_class="K2Node_CallArrayFunction")
    ln.pin("TargetArray", CAT_OBJECT, sub_object=cls("/Script/Engine.TargetPoint"),
           container="Array")
    ln.pin("ReturnValue", CAT_INT, out=True)
    arr.get("PatrolPoints").to(ln.get("TargetArray"))

    gt = g.call("Greater_IntInt", C_KML, 940, y0 + 500, pure=True)
    gt.pin("A", CAT_INT)
    gt.pin("B", CAT_INT, default="0")
    gt.pin("ReturnValue", CAT_BOOL, out=True)
    ln.get("ReturnValue").to(gt.get("A"))

    br = g.branch(1180, y0)
    mv.get("then").to(br.get("execute"))
    gt.get("ReturnValue").to(br.get("Condition"))

    # indice en circulo
    idx = g.var_get("PatrolIndex", CAT_INT, 700, y0 + 640)
    md = g.call("Percent_IntInt", C_KML, 940, y0 + 640, pure=True)
    md.pin("A", CAT_INT)
    md.pin("B", CAT_INT)
    md.pin("ReturnValue", CAT_INT, out=True)
    idx.get("PatrolIndex").to(md.get("A"))
    ln.get("ReturnValue").to(md.get("B"))

    get = g.call("Array_Get", C_ARR, 1180, y0 + 640, pure=True,
                 node_class="K2Node_CallArrayFunction")
    get.pin("TargetArray", CAT_OBJECT,
            sub_object=cls("/Script/Engine.TargetPoint"), container="Array")
    get.pin("Index", CAT_INT)
    get.pin("Item", CAT_OBJECT, out=True,
            sub_object=cls("/Script/Engine.TargetPoint"))
    arr.get("PatrolPoints").to(get.get("TargetArray"))
    md.get("ReturnValue").to(get.get("Index"))

    mt = g.call("MoveToActor", C_AICON, 1480, y0)
    mt.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    mt.pin("Goal", CAT_OBJECT, sub_object=cls(C_ACTOR))
    mt.pin("AcceptanceRadius", CAT_REAL, sub="double", default="60.000000")
    mt.pin("bStopOnOverlap", CAT_BOOL, default="true")
    mt.pin("bUsePathfinding", CAT_BOOL, default="true")
    mt.pin("bCanStrafe", CAT_BOOL, default="false")
    mt.pin("bAllowPartialPath", CAT_BOOL, default="true")
    br.get("then").to(mt.get("execute"))
    get.get("Item").to(mt.get("Goal"))

    esperar = g.call_self("Ev_WaitArrive", C_AICTRL, 1740, y0)
    mt.get("then").to(esperar.get("execute"))

    g.comment("Ev_MoveToPatrolPoint - indice circular sobre PatrolPoints",
              -40, y0 - 200, 1960, 1000,
              color="(R=0.200000,G=0.800000,B=0.300000,A=0.350000)")

    # ---------------- Ev_WaitArrive -------------------------------------
    # NO se usa ReceiveMoveCompleted: en AAIController eso NO es un evento
    # que se pueda sobreescribir, es una PROPIEDAD delegada
    # (FAIMoveCompletedSignature). Pegarlo como K2Node_Event da
    # "Colision de nombre: la funcion y la propiedad tienen el mismo nombre".
    # En su lugar se sondea GetMoveStatus cada 0.4 s, que ademas cubre el
    # caso de que el camino se corte (el estado vuelve a Idle igual).
    y1 = 1900
    wa = g.custom_event("Ev_WaitArrive", 0, y1)

    dl0 = delay(g, "0.400000", 260, y1)
    wa.get("then").to(dl0.get("execute"))

    gvp, eqp = state_es(g, ST_PATROL, 520, y1 + 260)
    brp = g.branch(960, y1)
    dl0.get("then").to(brp.get("execute"))
    eqp.get("ReturnValue").to(brp.get("Condition"))

    ms = g.call("GetMoveStatus", C_AICON, 1220, y1 + 260, pure=True)
    ms.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    ms.pin("ReturnValue", CAT_BYTE, out=True, sub_object=E_PATHSTATUS)
    idle = g.call("EqualEqual_ByteByte", C_KML, 1460, y1 + 260, pure=True)
    idle.pin("A", CAT_BYTE, sub_object=E_PATHSTATUS)
    idle.pin("B", CAT_BYTE, sub_object=E_PATHSTATUS, default="Idle")
    idle.pin("ReturnValue", CAT_BOOL, out=True)
    ms.get("ReturnValue").to(idle.get("A"))

    bra = g.branch(1720, y1)
    brp.get("then").to(bra.get("execute"))
    idle.get("ReturnValue").to(bra.get("Condition"))

    # sigue andando -> vuelve a esperar
    otra = g.call_self("Ev_WaitArrive", C_AICTRL, 1980, y1 + 160)
    bra.get("else").to(otra.get("execute"))

    # ha llegado -> siguiente punto
    inc = g.call("Add_IntInt", C_KML, 1980, y1 + 400, pure=True)
    inc.pin("A", CAT_INT)
    inc.pin("B", CAT_INT, default="1")
    inc.pin("ReturnValue", CAT_INT, out=True)
    gi = g.var_get("PatrolIndex", CAT_INT, 1780, y1 + 400)
    gi.get("PatrolIndex").to(inc.get("A"))

    si = g.var_set("PatrolIndex", CAT_INT, 2240, y1)
    inc.get("ReturnValue").to(si.get("PatrolIndex"))
    bra.get("then").to(si.get("execute"))

    dl = delay(g, "2.000000", 2500, y1)
    si.get("then").to(dl.get("execute"))

    again = g.call_self("Ev_MoveToPatrolPoint", C_AICTRL, 2760, y1)
    dl.get("then").to(again.get("execute"))

    g.comment("Ev_WaitArrive - sondea GetMoveStatus hasta llegar al punto",
              -40, y1 - 200, 2980, 780,
              color="(R=0.200000,G=0.800000,B=0.300000,A=0.350000)")

    emit(g, "03_AIC_Patrulla.txt")


# =========================================================================
# 04 - Combate
# =========================================================================
def paste_04():
    g = Graph("AIC_Combat", titulo=(
        "PEGADO 04 - COMBATE\n"
        "Destino: BP_GruntAIController > EventGraph\n"
        "\n"
        "Ev_EnterCombat  estado Combate, icono '!', velocidad ChaseSpeed,\n"
        "                persigue al jugador y arranca el bucle de disparo.\n"
        "Ev_FireLoop     cada FireInterval (1 s = DPS 10 del GDD):\n"
        "                  - si no sigue en combate, corta\n"
        "                  - si esta a mas de FireRange (12 m), no dispara\n"
        "                  - tira Accuracy (60 %): si acierta manda\n"
        "                    S_TakeDamage por BPI_HealthSystem\n"
        "                  - el disparo hace ruido (MakeNoise) para que lo\n"
        "                    oigan los demas: es la alerta de sector del GDD"))

    # ---------------- Ev_EnterCombat ------------------------------------
    ev = g.custom_event("Ev_EnterCombat", 0, 0)
    sst = set_state(g, ST_COMBAT, 260, 0)
    ev.get("then").to(sst.get("execute"))

    ic, vis = set_icon(g, "!", 520, 0)
    sst.get("then").to(ic.get("execute"))

    sp = set_speed(g, "ChaseSpeed", 1280, 0)
    vis.get("then").to(sp.get("execute"))

    pr = print_dbg(g, "GRUNT: ALERTA (!) - entra en combate", 1800, 0)
    sp.get("then").to(pr.get("execute"))

    tg = g.var_get("TargetPlayer", CAT_OBJECT, 2060, 260, sub_object=cls(C_ACTOR))
    mt = g.call("MoveToActor", C_AICON, 2060, 0)
    mt.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    mt.pin("Goal", CAT_OBJECT, sub_object=cls(C_ACTOR))
    mt.pin("AcceptanceRadius", CAT_REAL, sub="double", default="500.000000")
    mt.pin("bStopOnOverlap", CAT_BOOL, default="true")
    mt.pin("bUsePathfinding", CAT_BOOL, default="true")
    mt.pin("bCanStrafe", CAT_BOOL, default="true")
    mt.pin("bAllowPartialPath", CAT_BOOL, default="true")
    tg.get("TargetPlayer").to(mt.get("Goal"))
    pr.get("then").to(mt.get("execute"))

    fl = g.call_self("Ev_FireLoop", C_AICTRL, 2380, 0)
    mt.get("then").to(fl.get("execute"))

    g.comment("Ev_EnterCombat", -40, -200, 2600, 620,
              color="(R=1.000000,G=0.100000,B=0.100000,A=0.350000)")

    # ---------------- Ev_FireLoop ---------------------------------------
    y0 = 780
    fev = g.custom_event("Ev_FireLoop", 0, y0)

    gvc, eqc = state_es(g, ST_COMBAT, 260, y0 + 300)
    brc = g.branch(700, y0)
    fev.get("then").to(brc.get("execute"))
    eqc.get("ReturnValue").to(brc.get("Condition"))

    # distancia al objetivo
    gp = get_grunt(g, 700, y0 + 480)
    lg = g.call("K2_GetActorLocation", C_ACTOR, 940, y0 + 480, pure=True)
    lg.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    lg.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    gp.get("GruntPawn").to(lg.get("self"))

    tg2 = g.var_get("TargetPlayer", CAT_OBJECT, 700, y0 + 620,
                    sub_object=cls(C_ACTOR))
    lt = g.call("K2_GetActorLocation", C_ACTOR, 940, y0 + 620, pure=True)
    lt.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    lt.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    tg2.get("TargetPlayer").to(lt.get("self"))

    # OJO: los pines de Vector_Distance se llaman V1 y V2, NO A y B.
    dist = g.call("Vector_Distance", C_KML, 1200, y0 + 540, pure=True)
    dist.pin("V1", CAT_STRUCT, sub_object=S_VECTOR)
    dist.pin("V2", CAT_STRUCT, sub_object=S_VECTOR)
    dist.pin("ReturnValue", CAT_REAL, out=True, sub="double")
    lg.get("ReturnValue").to(dist.get("V1"))
    lt.get("ReturnValue").to(dist.get("V2"))

    rng = grunt_float(g, "FireRange", 1200, y0 + 760)
    le = g.call("LessEqual_DoubleDouble", C_KML, 1480, y0 + 540, pure=True)
    le.pin("A", CAT_REAL, sub="double")
    le.pin("B", CAT_REAL, sub="double")
    le.pin("ReturnValue", CAT_BOOL, out=True)
    dist.get("ReturnValue").to(le.get("A"))
    rng.get("FireRange").to(le.get("B"))

    brr = g.branch(1740, y0)
    brc.get("then").to(brr.get("execute"))
    le.get("ReturnValue").to(brr.get("Condition"))

    # --- G-2: LINEA DE VISION -------------------------------------------
    # Hasta la auditoria del 2026-08-28 la UNICA condicion para disparar era
    # la distancia, asi que el Grunt disparaba a traves de las paredes y la
    # cobertura del blockout no significaba nada.
    #
    # El trazado va de pecho a pecho (la posicion del actor de un Character
    # es el centro de la capsula) IGNORANDO a los dos implicados. Asi que:
    #   no choca con nada  -> via libre, dispara
    #   choca              -> hay geometria en medio, no dispara y se reposiciona
    ign = g.make_array(2, CAT_OBJECT, 1740, y0 + 900, sub_object=cls(C_ACTOR))
    gp_i = get_grunt(g, 1480, y0 + 880)
    tg_i = g.var_get("TargetPlayer", CAT_OBJECT, 1480, y0 + 1000,
                     sub_object=cls(C_ACTOR))
    gp_i.get("GruntPawn").to(ign.get("[0]"))
    tg_i.get("TargetPlayer").to(ign.get("[1]"))

    los = g.call("LineTraceSingle", C_KSL, 1740, y0 - 40)
    los.pin("Start", CAT_STRUCT, sub_object=S_VECTOR)
    los.pin("End", CAT_STRUCT, sub_object=S_VECTOR)
    los.pin("TraceChannel", CAT_BYTE, sub_object=E_TRACETYPE,
            default="TraceTypeQuery1")          # Visibility
    los.pin("bTraceComplex", CAT_BOOL, default="false")
    los.pin("ActorsToIgnore", CAT_OBJECT, sub_object=cls(C_ACTOR),
            container="Array")
    los.pin("DrawDebugType", CAT_BYTE, sub_object=E_DRAWDEBUG, default="None")
    los.pin("bIgnoreSelf", CAT_BOOL, default="true")
    los.pin("ReturnValue", CAT_BOOL, out=True)
    lg.get("ReturnValue").to(los.get("Start"))
    lt.get("ReturnValue").to(los.get("End"))
    ign.get("Array").to(los.get("ActorsToIgnore"))
    brr.get("then").to(los.get("execute"))

    br_los = g.branch(2000, y0 - 40)
    los.get("then").to(br_los.get("execute"))
    los.get("ReturnValue").to(br_los.get("Condition"))

    # encarar al jugador
    face = g.call("K2_SetActorRotation", C_ACTOR, 2260, y0)
    face.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    face.pin("NewRotation", CAT_STRUCT,
             sub_object="ScriptStruct'\"/Script/CoreUObject.Rotator\"'")
    face.pin("bTeleportPhysics", CAT_BOOL, default="false")
    look = g.call("FindLookAtRotation", C_KML, 2000, y0 + 300, pure=True)
    look.pin("Start", CAT_STRUCT, sub_object=S_VECTOR)
    look.pin("Target", CAT_STRUCT, sub_object=S_VECTOR)
    look.pin("ReturnValue", CAT_STRUCT, out=True,
             sub_object="ScriptStruct'\"/Script/CoreUObject.Rotator\"'")
    lg.get("ReturnValue").to(look.get("Start"))
    lt.get("ReturnValue").to(look.get("Target"))
    gp2 = get_grunt(g, 2000, y0 + 200)
    gp2.get("GruntPawn").to(face.get("self"))
    look.get("ReturnValue").to(face.get("NewRotation"))
    br_los.get("else").to(face.get("execute"))   # sin obstaculo -> dispara

    # ruido del disparo: asi lo oyen los demas (alerta de sector del GDD)
    noise = g.call("MakeNoise", C_ACTOR, 2320, y0)
    noise.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    noise.pin("Loudness", CAT_REAL, sub="float", default="1.000000")
    noise.pin("MaxRange", CAT_REAL, sub="float", default="0.000000")
    gp2.get("GruntPawn").to(noise.get("self"))
    face.get("then").to(noise.get("execute"))

    # tirada de punteria
    rnd = g.call("RandomFloat", C_KML, 2600, y0 + 300, pure=True)
    rnd.pin("ReturnValue", CAT_REAL, out=True, sub="double")
    acc = grunt_float(g, "Accuracy", 2600, y0 + 460)
    hit = g.call("LessEqual_DoubleDouble", C_KML, 2860, y0 + 320, pure=True)
    hit.pin("A", CAT_REAL, sub="double")
    hit.pin("B", CAT_REAL, sub="double")
    hit.pin("ReturnValue", CAT_BOOL, out=True)
    rnd.get("ReturnValue").to(hit.get("A"))
    acc.get("Accuracy").to(hit.get("B"))

    brh = g.branch(2860, y0)
    noise.get("then").to(brh.get("execute"))
    hit.get("ReturnValue").to(brh.get("Condition"))

    # ---- acierto: montar S_TakeDamage y mandarlo por la interfaz
    mk = g.make_struct(S_TAKEDMG.split("'")[1].strip('"'), 3120, y0 + 320)
    mk.pin(F_VALUE, CAT_REAL, sub="double")
    mk.pin(F_TYPE, CAT_BYTE, sub_object=E_DMGTYPE, default=DMG_CONVENTIONAL)
    mk.pin(F_REACT, CAT_BYTE, sub_object=E_DMGREACT, default=REACT_HIT)
    mk.pin(F_BLOCK, CAT_BOOL, default="true")
    # C-1: recibir un disparo TIENE que cortar la cura. Con False el
    # jugador se quedaba 3.5 s quieto a plena vista, encajaba 3-4
    # impactos y terminaba de curarse igual.
    mk.pin(F_FORCE, CAT_BOOL, default="true")
    mk.pin(F_INSTIG, CAT_OBJECT, sub_object=cls(C_ACTOR))
    dmg = grunt_float(g, "Damage", 3120, y0 + 620)
    dmg.get("Damage").to(mk.get(F_VALUE))
    gp3 = get_grunt(g, 3120, y0 + 760)
    gp3.get("GruntPawn").to(mk.get(F_INSTIG))

    msg = g.message("TakeDamage", C_BPI_HEALTH, 3480, y0)
    msg.pin("self", CAT_OBJECT, sub_object=cls(C_OBJ_BASE))
    msg.pin("DamageInfo", CAT_STRUCT, sub_object=S_TAKEDMG)
    tg3 = g.var_get("TargetPlayer", CAT_OBJECT, 3480, y0 + 220,
                    sub_object=cls(C_ACTOR))
    tg3.get("TargetPlayer").to(msg.get("self"))
    mk.get("StructOut").to(msg.get("DamageInfo"))
    brh.get("then").to(msg.get("execute"))

    pr_hit = print_dbg(g, "GRUNT: DISPARO ACERTADO (10)", 3800, y0)
    msg.get("then").to(pr_hit.get("execute"))

    pr_miss = print_dbg(g, "GRUNT: disparo fallado", 3120, y0 + 160)
    brh.get("else").to(pr_miss.get("execute"))

    # ---- reencolar el bucle
    itv = grunt_float(g, "FireInterval", 4400, y0 + 300)
    dl = delay(g, "1.000000", 4400, y0)
    itv.get("FireInterval").to(dl.get("Duration"))
    pr_hit.get("then").to(dl.get("execute"))
    pr_miss.get("then").to(dl.get("execute"))

    # --- G-5: volver a moverse ------------------------------------------
    # Ev_EnterCombat emitia UN MoveToActor y Ev_FireLoop solo rotaba, asi que
    # el soldado entraba en combate, se plantaba y no perseguia mas.
    # Ahora los dos casos en los que NO dispara -fuera de rango y sin linea
    # de vision- reemiten la orden de movimiento antes de reencolar.
    chase = g.call("MoveToActor", C_AICON, 3200, y0 + 700)
    chase.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    chase.pin("Goal", CAT_OBJECT, sub_object=cls(C_ACTOR))
    chase.pin("AcceptanceRadius", CAT_REAL, sub="double", default="500.000000")
    chase.pin("bStopOnOverlap", CAT_BOOL, default="true")
    chase.pin("bUsePathfinding", CAT_BOOL, default="true")
    chase.pin("bCanStrafe", CAT_BOOL, default="true")
    chase.pin("bAllowPartialPath", CAT_BOOL, default="true")
    tg_c = g.var_get("TargetPlayer", CAT_OBJECT, 3200, y0 + 900,
                     sub_object=cls(C_ACTOR))
    tg_c.get("TargetPlayer").to(chase.get("Goal"))
    brr.get("else").to(chase.get("execute"))      # fuera de rango
    br_los.get("then").to(chase.get("execute"))   # pared en medio
    chase.get("then").to(dl.get("execute"))

    loop = g.call_self("Ev_FireLoop", C_AICTRL, 4680, y0)
    dl.get("then").to(loop.get("execute"))

    g.comment("Ev_FireLoop - rango, LINEA DE VISION, punteria 60 %, dano por "
              "interfaz, ruido y reemision de la persecucion",
              -40, y0 - 220, 4900, 1500,
              color="(R=1.000000,G=0.100000,B=0.100000,A=0.350000)")

    emit(g, "04_AIC_Combate.txt")


# =========================================================================
# 05 - Busqueda
# =========================================================================
def paste_05():
    g = Graph("AIC_Search", titulo=(
        "PEGADO 05 - BUSQUEDA Y RUIDO\n"
        "Destino: BP_GruntAIController > EventGraph\n"
        "\n"
        "Ev_StartSearch  estado Buscando, va a LastKnownLocation, espera\n"
        "                SearchTime (5 s) y vuelve a patrullar si no ha\n"
        "                vuelto a ver a nadie.\n"
        "Ev_Investigate  reaccion a un ruido: icono '?', va al sitio.\n"
        "                Es el 'estado de distraccion (si detecta ruido)'\n"
        "                que pide la tabla del GDD para el soldado."))

    # ---------------- Ev_StartSearch ------------------------------------
    ev = g.custom_event("Ev_StartSearch", 0, 0)
    sst = set_state(g, ST_SEARCH, 260, 0)
    ev.get("then").to(sst.get("execute"))

    ic, vis = set_icon(g, "?", 520, 0)
    sst.get("then").to(ic.get("execute"))

    pr = print_dbg(g, "GRUNT: perdi al objetivo, voy a la ultima posicion",
                   1280, 0)
    vis.get("then").to(pr.get("execute"))

    lk = g.var_get("LastKnownLocation", CAT_STRUCT, 1540, 240,
                   sub_object=S_VECTOR)
    mt = g.call("MoveToLocation", C_AICON, 1540, 0)
    mt.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    mt.pin("Dest", CAT_STRUCT, sub_object=S_VECTOR)
    mt.pin("AcceptanceRadius", CAT_REAL, sub="double", default="80.000000")
    mt.pin("bStopOnOverlap", CAT_BOOL, default="true")
    mt.pin("bUsePathfinding", CAT_BOOL, default="true")
    mt.pin("bProjectDestinationToNavigation", CAT_BOOL, default="true")
    mt.pin("bCanStrafe", CAT_BOOL, default="false")
    mt.pin("bAllowPartialPath", CAT_BOOL, default="true")
    lk.get("LastKnownLocation").to(mt.get("Dest"))
    pr.get("then").to(mt.get("execute"))

    stime = grunt_float(g, "SearchTime", 1880, 240)
    dl = delay(g, "5.000000", 1880, 0)
    stime.get("SearchTime").to(dl.get("Duration"))
    mt.get("then").to(dl.get("execute"))

    gvs, eqs = state_es(g, ST_SEARCH, 2160, 300)
    br = g.branch(2600, 0)
    dl.get("then").to(br.get("execute"))
    eqs.get("ReturnValue").to(br.get("Condition"))

    back = g.call_self("Ev_StartPatrol", C_AICTRL, 2860, 0)
    br.get("then").to(back.get("execute"))

    g.comment("Ev_StartSearch - vigila la ultima posicion SearchTime (5 s)",
              -40, -200, 3080, 700,
              color="(R=0.500000,G=0.300000,B=0.900000,A=0.350000)")

    # ---------------- Ev_Investigate ------------------------------------
    y0 = 900
    iev = g.custom_event("Ev_Investigate", 0, y0)

    gvc, eqc = state_es(g, ST_COMBAT, 260, y0 + 260)
    br2 = g.branch(700, y0)
    iev.get("then").to(br2.get("execute"))
    eqc.get("ReturnValue").to(br2.get("Condition"))
    # en combate se ignora el ruido: la rama 'then' muere aqui

    sst2 = set_state(g, ST_INVESTIGATE, 960, y0 + 60)
    br2.get("else").to(sst2.get("execute"))

    ic2, vis2 = set_icon(g, "?", 1220, y0 + 60)
    sst2.get("then").to(ic2.get("execute"))

    pr2 = print_dbg(g, "GRUNT: he oido algo (?)", 1980, y0 + 60)
    vis2.get("then").to(pr2.get("execute"))

    sp2 = set_speed(g, "ChaseSpeed", 2240, y0 + 60)
    pr2.get("then").to(sp2.get("execute"))

    # El oido tiene su propio destino: LastKnownLocation es donde se VIO al
    # jugador por ultima vez, y machacarla con un ruido borraria la pista.
    lk2 = g.var_get("NoiseLocation", CAT_STRUCT, 2760, y0 + 300,
                    sub_object=S_VECTOR)
    mt2 = g.call("MoveToLocation", C_AICON, 2760, y0 + 60)
    mt2.pin("self", CAT_OBJECT, sub_object=cls(C_AICON), hidden=True)
    mt2.pin("Dest", CAT_STRUCT, sub_object=S_VECTOR)
    mt2.pin("AcceptanceRadius", CAT_REAL, sub="double", default="80.000000")
    mt2.pin("bStopOnOverlap", CAT_BOOL, default="true")
    mt2.pin("bUsePathfinding", CAT_BOOL, default="true")
    mt2.pin("bProjectDestinationToNavigation", CAT_BOOL, default="true")
    mt2.pin("bCanStrafe", CAT_BOOL, default="false")
    mt2.pin("bAllowPartialPath", CAT_BOOL, default="true")
    lk2.get("NoiseLocation").to(mt2.get("Dest"))
    sp2.get("then").to(mt2.get("execute"))

    stime2 = grunt_float(g, "SuspicionTime", 3100, y0 + 300)
    dl2 = delay(g, "3.000000", 3100, y0 + 60)
    stime2.get("SuspicionTime").to(dl2.get("Duration"))
    mt2.get("then").to(dl2.get("execute"))

    gvi, eqi = state_es(g, ST_INVESTIGATE, 3380, y0 + 300)
    br3 = g.branch(3820, y0 + 60)
    dl2.get("then").to(br3.get("execute"))
    eqi.get("ReturnValue").to(br3.get("Condition"))

    back2 = g.call_self("Ev_StartPatrol", C_AICTRL, 4080, y0 + 60)
    br3.get("then").to(back2.get("execute"))

    g.comment("Ev_Investigate - distraccion por ruido (tabla del GDD)",
              -40, y0 - 220, 4300, 700,
              color="(R=0.500000,G=0.300000,B=0.900000,A=0.350000)")

    emit(g, "05_AIC_Busqueda.txt")


# =========================================================================
# 06 - Muerte (en BP_Grunt)
# =========================================================================
def paste_06():
    g = Graph("Grunt_Death", titulo=(
        "PEGADO 06 - MUERTE\n"
        "Destino: BP_Grunt > EventGraph\n"
        "\n"
        "Ev_GruntDeath: para la IA, tumba al soldado en ragdoll, apaga\n"
        "colision e icono y lo borra a los 8 s.\n"
        "\n"
        "*** HAY QUE CONECTAR UN CABLE A MANO ***\n"
        "BP_Grunt ya tiene un evento 'Death' enganchado al dispatcher OnDeath\n"
        "de BPC_HealthSystem. Arrastra la salida de ejecucion de ESE evento\n"
        "hasta la entrada de Ev_GruntDeath. No puedo hacerlo yo: no hay forma\n"
        "de leer los nodos de un grafo existente (UEdGraph.Nodes es\n"
        "protected), asi que no se donde acaba tu cadena actual."))

    ev = g.custom_event("Ev_GruntDeath", 0, 0)

    pr = print_dbg(g, "GRUNT: abatido", 260, 0)
    ev.get("then").to(pr.get("execute"))

    # 1. parar la IA
    ctrl = g.call("GetController", C_PAWN, 520, 300, pure=True)
    ctrl.pin("self", CAT_OBJECT, sub_object=cls(C_PAWN), hidden=True)
    ctrl.pin("ReturnValue", CAT_OBJECT, out=True, sub_object=cls(C_CTRL))
    slf = g.self_node(520, 420)
    slf.get("self").to(ctrl.get("self"))

    stop = g.call("StopMovement", C_CTRL, 520, 0)
    stop.pin("self", CAT_OBJECT, sub_object=cls(C_CTRL), hidden=True)
    ctrl.get("ReturnValue").to(stop.get("self"))
    pr.get("then").to(stop.get("execute"))

    unp = g.call("UnPossess", C_CTRL, 800, 0)
    unp.pin("self", CAT_OBJECT, sub_object=cls(C_CTRL), hidden=True)
    ctrl.get("ReturnValue").to(unp.get("self"))
    stop.get("then").to(unp.get("execute"))

    # 2. apagar el icono
    ic = g.var_get("StateIcon", CAT_OBJECT, 1080, 300, sub_object=cls(C_TEXTR))
    vis = g.call("SetVisibility", C_SCENE, 1080, 0)
    vis.pin("self", CAT_OBJECT, sub_object=cls(C_SCENE), hidden=True)
    vis.pin("bNewVisibility", CAT_BOOL, default="false")
    vis.pin("bPropagateToChildren", CAT_BOOL, default="false")
    ic.get("StateIcon").to(vis.get("self"))
    unp.get("then").to(vis.get("execute"))

    # 3. quitar la capsula de en medio
    cap = g.var_get_target("CapsuleComponent", CAT_OBJECT, C_CHAR, 1360, 300,
                           sub_object=cls("/Script/Engine.CapsuleComponent"))
    slf.get("self").to(cap.get("self"))
    coll = g.call("SetCollisionEnabled", C_PRIM, 1360, 0)
    coll.pin("self", CAT_OBJECT, sub_object=cls(C_PRIM), hidden=True)
    coll.pin("NewType", CAT_BYTE,
             sub_object="Enum'\"/Script/Engine.ECollisionEnabled\"'",
             default="NoCollision")
    cap.get("CapsuleComponent").to(coll.get("self"))
    vis.get("then").to(coll.get("execute"))

    # 4. ragdoll
    mesh = g.var_get_target("Mesh", CAT_OBJECT, C_CHAR, 1640, 420,
                            sub_object=cls("/Script/Engine.SkeletalMeshComponent"))
    slf.get("self").to(mesh.get("self"))

    prof = g.call("SetCollisionProfileName", C_PRIM, 1640, 0)
    prof.pin("self", CAT_OBJECT, sub_object=cls(C_PRIM), hidden=True)
    prof.pin("InCollisionProfileName", CAT_NAME, default="Ragdoll")
    prof.pin("bUpdateOverlaps", CAT_BOOL, default="true")
    mesh.get("Mesh").to(prof.get("self"))
    coll.get("then").to(prof.get("execute"))

    sim = g.call("SetSimulatePhysics", C_PRIM, 1920, 0)
    sim.pin("self", CAT_OBJECT, sub_object=cls(C_PRIM), hidden=True)
    sim.pin("bSimulate", CAT_BOOL, default="true")
    mesh.get("Mesh").to(sim.get("self"))
    prof.get("then").to(sim.get("execute"))

    # 5. limpiar
    dl = delay(g, "8.000000", 2200, 0)
    sim.get("then").to(dl.get("execute"))

    dst = g.call("K2_DestroyActor", C_ACTOR, 2460, 0)
    dst.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR), hidden=True)
    slf.get("self").to(dst.get("self"))
    dl.get("then").to(dst.get("execute"))

    g.comment("Ev_GruntDeath - CONECTA AQUI la salida de tu evento Death",
              -40, -220, 2680, 800,
              color="(R=0.800000,G=0.000000,B=0.000000,A=0.400000)")

    emit(g, "06_Grunt_Muerte.txt")



def combinar():
    """Junta los 5 pegados del controlador en UNO solo.

    Se puede porque los nombres de nodo llevan un sufijo por grafo, asi que no
    colisionan al concatenar (LinkedTo referencia los nodos POR NOMBRE).

    Un solo pegado evita ademas el problema del evento renombrado: si un
    pegado llama a un evento que define OTRO pegado posterior, Unreal crea un
    grafo-stub con ese nombre y luego renombra el evento de verdad a
    "CustomEvent". Con todo en el mismo Ctrl+V eso no puede pasar.
    """
    nl = chr(10)
    partes = []
    for f in ["01_AIC_BeginPlay.txt", "02_AIC_Percepcion.txt",
              "03_AIC_Patrulla.txt", "04_AIC_Combate.txt",
              "05_AIC_Busqueda.txt"]:
        with open(os.path.join(OUT, f), encoding="utf-8") as fh:
            lineas = fh.read().split(nl)
        i0 = next(i for i, l in enumerate(lineas) if l.startswith("Begin Object"))
        partes.append(nl.join(lineas[i0:]).rstrip())

    cab = [
        "// PEGADO UNICO - TODA LA IA DEL CONTROLADOR",
        "// Destino: BP_GruntAIController > EventGraph",
        "//",
        "// Contiene los 5 bloques (arranque, percepcion, patrulla, combate",
        "// y busqueda) en un solo Ctrl+V.",
        "//",
        "// ORDEN OBLIGATORIO:",
        "//   1. Ctrl+A y Supr en el EventGraph",
        "//   2. Compile con el grafo vacio (libera los nombres de evento)",
        "//   3. Ctrl+V",
        "//   4. File > Refresh All Nodes",
        "//   5. Compile y Save",
        "",
    ]
    ruta = os.path.join(OUT, "10_TODO_AIController.txt")
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(nl.join(cab) + nl + nl.join(partes) + nl)
    n = sum(pt.count("Begin Object Class=") for pt in partes)
    print("  %-44s %2d nodos  <-- USA ESTE" % ("10_TODO_AIController.txt", n))


if __name__ == "__main__":
    print("Generando texto de pegado en %s" % OUT)
    print("")
    paste_01()
    paste_02()
    paste_03()
    paste_04()
    paste_05()
    paste_06()
    combinar()
    print("")
    print("Total: %d ficheros, %d nodos"
          % (len(generados), sum(n for _, n in generados)))
