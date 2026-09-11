# -*- coding: utf-8 -*-
"""
Pegados (T3D) de los arreglos de la AUDITORIA_2026-09-04.

  40_Char_Crouch.txt        A-1b  IA_Crouch (tecla C) -> Crouch / UnCrouch
                                  en el EventGraph de BP_ThirdPersonCharacter
  41_AIC_AimFromPatrol.txt  A-8   apuntarle desde Patrulla lo pasa a Sospecha
                                  en el EventGraph de BP_GruntAIController
  43_Bandage_Interact.txt   A-6   la venda se puede recoger (BP_Bandage
                                  estaba vacio: 4 nodos sin logica)
  42_Grunt_DeathDestroy.txt A-3   Delay(5) -> DestroyActor al final de la
                                  cadena de muerte, en el EventGraph de
                                  BP_Grunt (cuelga del PRINT "SOLDADO
                                  MUERTO!!!!!", que es el ultimo nodo real)

Uso:
    python Tools/gen_fixes_0905.py
    powershell -File Tools/clip.ps1 40
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bpgen import (Graph, cls, obj, CAT_BOOL, CAT_REAL, CAT_STRING,
                   CAT_OBJECT, CAT_BYTE, CAT_STRUCT, CAT_CLASS, CAT_NAME)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_paste")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

C_KSL = "/Script/Engine.KismetSystemLibrary"
C_KML = "/Script/Engine.KismetMathLibrary"
C_ACTOR = "/Script/Engine.Actor"
C_CHARACTER = "/Script/Engine.Character"
C_WIDGET = "/Script/UMG.Widget"

C_BPI_INTERACT = ("/Game/ThirdPerson/Blueprints/Interfaces/BPI_Interactable."
                  "BPI_Interactable_C")
C_CHAR = ("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter."
          "BP_ThirdPersonCharacter_C")
C_INVENT = "/Game/ThirdPerson/Components/BPC_Inventary.BPC_Inventary_C"
C_WBP_INV = ("/Game/ThirdPerson/Blueprints/WBP/HUB/WBP_HUB_Inventary."
             "WBP_HUB_Inventary_C")

E_STATE = "UserDefinedEnum'\"/Game/ThirdPerson/AI/E_GruntState.E_GruntState\"'"
ST_PATROL = "NewEnumerator0"

IA_CROUCH = "/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Crouch.IA_Crouch'"

generados = []


def emit(g, fichero):
    g.save(os.path.join(OUT, fichero))
    generados.append((fichero, len(g.nodes)))
    print("  %-32s %3d nodos" % (fichero, len(g.nodes)))


def print_dbg(g, texto, x, y, color="(R=0.0,G=1.0,B=0.4,A=1.0)"):
    """En este proyecto el PrintString es el instrumento de medida: las
    escrituras a instancias de PIE se revierten y el log no."""
    p = g.call("PrintString", C_KSL, x, y)
    p.pin("InString", CAT_STRING, default=texto)
    p.pin("bPrintToScreen", CAT_BOOL, default="true")
    p.pin("bPrintToLog", CAT_BOOL, default="true")
    p.pin("TextColor", CAT_STRUCT, default=color,
          sub_object=obj("ScriptStruct", "/Script/CoreUObject.LinearColor"))
    p.pin("Duration", CAT_REAL, sub="double", default="2.000000")
    return p


def delay(g, segundos, x, y):
    """TRAMPA ya medida: NO existe la clase K2Node_Delay. El nodo Delay es un
    K2Node_CallFunction a la funcion latente KismetSystemLibrary::Delay. Con
    una clase inexistente el nodo no se crea y no da ningun error."""
    d = g.call("Delay", C_KSL, x, y)
    d.pin("Duration", CAT_REAL, sub="double", default=segundos)
    return d


# ===========================================================================
# 40  -  A-1b  el agachado
# ===========================================================================
def gen_crouch():
    g = Graph("Char_Crouch", titulo="""
A-1b  AGACHARSE  -  pegar en el EventGraph de BP_ThirdPersonCharacter.

IA_Crouch ya esta mapeada a la tecla C en IMC_Default; lo que faltaba era el
evento. Es agachado MANTENIDO: Started agacha, Completed levanta.

Antes de que esto sirva de algo hay que tener NavAgentProps.CanCrouch = True
en el CharacterMovement; lo pone Tools/fix_crouch_enable.py (ya aplicado el
2026-09-05). Sin esa casilla el nodo Crouch se ejecuta y no hace NADA.

MaxWalkSpeedCrouched ya vale 300, que es lo que pide el GDD.

Esto es lo que desbloquea la rama de COBERTURA AGACHADO (-35 % de dano) de
BPC_ProtectionSystem, que estaba construida y verificada en el laboratorio
pero era inalcanzable en juego.
""")

    ev = g.input_action(IA_CROUCH, 0, 0)

    # --- agacharse
    ag = g.call("Crouch", C_CHARACTER, 340, -60)
    ag.pin("bClientSimulation", CAT_BOOL, default="false")
    ev.get("Started").to(ag.exec_in)

    p_ag = print_dbg(g, "AGACHADO (velocidad 300, ruido 0.5 m)", 600, -60)
    ag.exec_out.to(p_ag.exec_in)

    # --- levantarse
    lev = g.call("UnCrouch", C_CHARACTER, 340, 260)
    lev.pin("bClientSimulation", CAT_BOOL, default="false")
    ev.get("Completed").to(lev.exec_in)

    p_lev = print_dbg(g, "DE PIE (velocidad 600, ruido 3 m)", 600, 260,
                      color="(R=1.0,G=0.8,B=0.0,A=1.0)")
    lev.exec_out.to(p_lev.exec_in)

    g.comment("A-1b  AGACHARSE (tecla C, mantenida)", -60, -220, 1400, 700)
    emit(g, "40_Char_Crouch.txt")


# ===========================================================================
# 41  -  A-8  apuntarle desde Patrulla
# ===========================================================================
def gen_aim_from_patrol():
    g = Graph("AIC_AimFromPatrol", titulo="""
A-8  APUNTARLE A UN SOLDADO QUE AUN NO TE HA VISTO
     pegar en el EventGraph de BP_GruntAIController.

Hoy Ev_AimWatch pone bien la bandera BeingAimedAt, guarda TargetPlayer y
LastKnownLocation, y luego ramifica:
    State == Sospecha              -> Ev_FastCombat
    State == Combate && !IsInCover -> Ev_TakeCover
DESDE PATRULLA NO HAY RAMA: encanonar a un soldado que aun no te ha visto no
hace nada. Lo que se midio el 2026-09-03 funcionaba porque la VISTA ya lo
habia pasado a Sospecha antes.

Esta isla anade la rama que falta:
    State == Patrulla -> Ev_Spot   (pone Sospecha, icono '?', y tras
                                    ReactionTime entra en combate)

CABLES QUE HAY QUE HACER A MANO (dos):
  1. el PRINT "GRUNT: ME ESTAN APUNTANDO"  ->  este BRANCH nuevo
  2. la salida "False" de este BRANCH      ->  el BRANCH que ya existia
                                               (el de State == Sospecha)

TargetPlayer y LastKnownLocation ya se han puesto antes en la cadena, asi que
Ev_Spot tiene todo lo que necesita.
""")

    gv = g.var_get("State", CAT_BYTE, 0, 200, sub_object=E_STATE)

    # TRAMPA: EqualEqual_ByteByte es (uint8, uint8). Al reconstruirse el nodo
    # pierde la referencia al enum, asi que a B hay que darle el INDICE, no el
    # nombre de la entrada.
    eq = g.call("EqualEqual_ByteByte", C_KML, 220, 200, pure=True)
    eq.pin("A", CAT_BYTE, sub_object=E_STATE)
    eq.pin("B", CAT_BYTE, default=ST_PATROL.replace("NewEnumerator", ""))
    eq.pin("ReturnValue", CAT_BOOL, out=True)
    gv.get("State").to(eq.get("A"))

    b = g.branch(460, 40)
    eq.get("ReturnValue").to(b.get("Condition"))

    p = print_dbg(g, "GRUNT: me estan apuntando desde patrulla -> sospecha",
                  700, -60, color="(R=1.0,G=0.5,B=0.0,A=1.0)")
    b.get("then").to(p.exec_in)

    spot = g.call_self("Ev_Spot", None, 1060, -60)
    p.exec_out.to(spot.exec_in)

    g.comment("A-8  apuntado desde PATRULLA -> Ev_Spot. "
              "Entrada: del PRINT 'ME ESTAN APUNTANDO'. "
              "False: al BRANCH de State == Sospecha",
              -60, -220, 1500, 620,
              color="(R=1.000000,G=0.500000,B=0.000000,A=0.400000)")
    emit(g, "41_AIC_AimFromPatrol.txt")


# ===========================================================================
# 42  -  A-3  el cadaver
# ===========================================================================
def gen_grunt_destroy():
    g = Graph("Grunt_DeathDestroy", titulo="""
A-3  EL CADAVER DEL SOLDADO NO DESAPARECE
     pegar en el EventGraph de BP_Grunt.

El K2_DestroyActor que ya hay en el grafo esta SUELTO, sin entrada de
ejecucion. Con 20 soldados en el nivel eso son hasta 20 cadaveres
acumulandose. Esta isla es el final que falta: Delay(5) -> DestroyActor.

DONDE ENGANCHARLO, Y POR QUE AHI
--------------------------------
La muerte son DOS cadenas encadenadas, no una viva y otra muerta como decia
la auditoria del 09-04:

  EVENT Death -> call Ev_GruntDeath -> [PRINT "Hello", StopMovement,
                                        UnPossess, ocultar icono, capsula
                                        NoCollision, Mesh profile "None",
                                        Mesh Simulate FALSE]
              -> (VUELVE) -> capsula NoCollision -> Mesh profile "Ragdoll"
                          -> Mesh Simulate TRUE -> PRINT "SOLDADO MUERTO!!!!!"

Que vuelve esta MEDIDO, no supuesto: en el log del 2026-09-04 aparecen las dos
trazas, "Hello" 2 veces y "SOLDADO MUERTO" 2 veces, en la misma sesion. O sea
que el ragdoll SI ocurre: la segunda cadena pisa el "None"/false de la primera.

Por eso el enganche va al FINAL DE TODO. Colgarlo del SetSimulatePhysics de
Ev_GruntDeath destruiria el actor antes de que se aplicase el ragdoll.

CABLE QUE HAY QUE HACER A MANO (uno):
  el PRINT "SOLDADO MUERTO!!!!!"  ->  este Delay
""")

    d = delay(g, "5.000000", 0, 0)

    p = print_dbg(g, "GRUNT: cadaver retirado", 300, 0,
                  color="(R=0.6,G=0.6,B=0.6,A=1.0)")
    d.exec_out.to(p.exec_in)

    self_n = g.self_node(560, 220)
    dest = g.call("K2_DestroyActor", C_ACTOR, 640, 0)
    dest.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR))
    p.exec_out.to(dest.exec_in)
    self_n.get("self").to(dest.get("self"))

    g.comment("A-3  esperar 5 s tras el ragdoll y retirar el cadaver. "
              "Entrada: del PRINT SOLDADO MUERTO",
              -60, -220, 1000, 620,
              color="(R=0.600000,G=0.000000,B=0.000000,A=0.400000)")
    emit(g, "42_Grunt_DeathDestroy.txt")


# ===========================================================================
# 43  -  A-6  la venda
# ===========================================================================
def gen_bandage():
    g = Graph("Bandage_Interact", titulo="""
A-6  LA VENDA NO SE PUEDE RECOGER  -  pegar en el EventGraph de BP_Bandage.

BP_Bandage tenia 4 nodos y ninguna logica: los tres eventos de plantilla
(BeginPlay, ActorBeginOverlap, Tick) sin nada colgando. Por eso el caso 5 del
guion de QA (vendas) es el unico que falla del banco de laboratorio.

Esta es la MISMA cadena que BP_FirstAidKit, y eso es deliberado: la venda
ocupa el mismo hueco del inventario (Object_Is_FirstAidKit) y BPC_Curation
distingue una de otra con ClassIsChildOf(clase_del_item, BP_Bandage). Por eso
tambien enciende el icono IMG-FirstAidKit: no existe IMG-Bandage en
WBP_HUB_Inventary, comparten slot.

ANTES DE PEGAR, OBLIGATORIO
---------------------------
BP_Bandage NO implementa BPI_Interactable (comprobado en su T3D: no tiene
linea Interfaces). Hay que anadirsela en Class Settings > Interfaces ANTES
del Ctrl+V. Si no, el evento Interact se degrada a un CustomEvent huerfano
que compila en verde y no se dispara nunca. Ya paso con la caja de municion.
""")

    ev = g.event("Interact", C_BPI_INTERACT, 0, 0)
    ev.pin("Interactor", CAT_OBJECT, out=True, sub_object=cls(C_ACTOR))

    cast = g.cast(C_CHAR, 300, 0)
    ev.exec_out.to(cast.exec_in)
    ev.get("Interactor").to(cast.get("Object"))

    # BPC_Inventary del jugador
    inv = g.call("GetComponentByClass", C_ACTOR, 300, 320, pure=True)
    inv.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR))
    inv.pin("ComponentClass", CAT_CLASS, default=C_INVENT,
            sub_object=cls("/Script/Engine.ActorComponent"))
    inv.pin("ReturnValue", CAT_OBJECT, out=True,
            sub_object=cls("/Script/Engine.ActorComponent"))
    cast.get("AsTarget").to(inv.get("self"))

    # el hueco del botiquin pasa a ser esta venda
    s_ref = g.var_set_target("Object_Is_FirstAidKit", CAT_OBJECT, C_INVENT,
                             640, 0, sub_object=cls(C_ACTOR))
    cast.exec_out.to(s_ref.exec_in)
    inv.get("ReturnValue").to(s_ref.get("self"))
    yo = g.self_node(640, 240)
    yo.get("self").to(s_ref.get("Object_Is_FirstAidKit"))

    # pegarla a la mano derecha
    malla = g.var_get_target("Mesh", CAT_OBJECT, C_CHARACTER, 900, 320,
                             sub_object=cls("/Script/Engine.SkeletalMeshComponent"))
    cast.get("AsTarget").to(malla.get("self"))

    att = g.call("K2_AttachToComponent", C_ACTOR, 960, 0)
    att.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR))
    att.pin("Parent", CAT_OBJECT,
            sub_object=cls("/Script/Engine.SceneComponent"))
    att.pin("SocketName", CAT_NAME, default="Hand_r")
    att.pin("LocationRule", CAT_BYTE, default="SnapToTarget")
    att.pin("RotationRule", CAT_BYTE, default="SnapToTarget")
    att.pin("ScaleRule", CAT_BYTE, default="KeepWorld")
    att.pin("bWeldSimulatedBodies", CAT_BOOL, default="TRUE")
    s_ref.exec_out.to(att.exec_in)
    yo.get("self").to(att.get("self"))
    malla.get("Mesh").to(att.get("Parent"))

    # encender el icono del slot (comparte el del botiquin)
    wbp = g.var_get_target("WBP HUB inventary", CAT_OBJECT, C_CHAR, 1260, 320,
                           sub_object=cls(C_WBP_INV))
    cast.get("AsTarget").to(wbp.get("self"))
    img = g.var_get_target("IMG-FirstAidKit", CAT_OBJECT, C_WBP_INV, 1500, 320,
                           sub_object=cls("/Script/UMG.Image"))
    wbp.get("WBP HUB inventary").to(img.get("self"))

    vis = g.call("SetVisibility", C_WIDGET, 1300, 0)
    vis.pin("self", CAT_OBJECT, sub_object=cls(C_WIDGET))
    vis.pin("InVisibility", CAT_BYTE, default="Visible",
            sub_object=obj("Enum", "/Script/UMG.ESlateVisibility"))
    att.exec_out.to(vis.exec_in)
    img.get("IMG-FirstAidKit").to(vis.get("self"))

    # que no se pueda volver a recoger del suelo
    col = g.call("SetActorEnableCollision", C_ACTOR, 1640, 0)
    col.pin("self", CAT_OBJECT, sub_object=cls(C_ACTOR))
    col.pin("bNewActorEnableCollision", CAT_BOOL, default="false")
    vis.exec_out.to(col.exec_in)
    yo.get("self").to(col.get("self"))

    p = print_dbg(g, "VENDA RECOGIDA", 1920, 0)
    col.exec_out.to(p.exec_in)

    g.comment("A-6  recoger la venda (misma cadena que BP_FirstAidKit, "
              "mismo slot del inventario)", -60, -220, 2300, 700,
              color="(R=0.000000,G=0.600000,B=0.300000,A=0.400000)")
    emit(g, "43_Bandage_Interact.txt")


# ===========================================================================
# 44  -  COBERTURA AL ENTRAR EN COMBATE
# ===========================================================================
def gen_cover_on_combat():
    g = Graph("AIC_CoverOnCombat", titulo="""
LOS SOLDADOS NO BUSCAN COBERTURA  -  pegar en el EventGraph de
                                     BP_GruntAIController.

EL DIAGNOSTICO (2026-09-05, contra los grafos reales)
-----------------------------------------------------
Ev_TakeCover tiene UN SOLO llamador en todo el controlador, y esta dentro de
Ev_AimWatch detras de cuatro condiciones encadenadas:

  1. HaveGun del jugador
  2. distancia <= AimDetectRange
  3. BeingAimedAt  (le estas apuntando con la camara)
  4. State == Combate && !IsInCover

O sea: el soldado SOLO se cubre mientras le estas encanonando. Si disparas sin
apuntar, si sueltas el apuntado o si aun no llevas arma, no se cubre nunca.

Y Ev_EnterCombat -el evento de "te he visto, voy a por ti"- va directo a
MoveToActor(TargetPlayer, radio 500) y a Ev_FireLoop: carga a pecho
descubierto.

test_ai_upgrade.py daba 0 fallos porque su funcion apuntar_a() se RE-APLICA en
cada tanda: mantiene al jugador encanonando al soldado durante toda la
medicion. Es justo la condicion que no se da jugando.

QUE HACE ESTA ISLA
------------------
    PRINT "ALERTA (!)" -> Branch( NOT IsInCover )
        True  -> Sequence -> then_0: Ev_FireLoop
                          -> then_1: Ev_TakeCover
        False -> MoveToActor(TargetPlayer)      [el nodo que ya existe]

El Sequence NO es decorativo: Ev_TakeCover termina en el bucle de vigilancia
(Ev_AimWatch), no en el de disparo, asi que un soldado que se cubriese sin
arrancar antes Ev_FireLoop se quedaria a cubierto SIN DISPARAR NUNCA. Se pone
primero el disparo y despues la cobertura porque una cadena que se topa con un
nodo latente (el Delay de Ev_FireLoop, el MoveToActor de Ev_TakeCover) devuelve
el control, y el Sequence sigue por su segunda salida.

Donde cubrirse ya lo decide Ev_TakeCover con IsFlanker, que se sortea en
BeginPlay: la mitad de la escuadra flanquea. Eso no se toca.

CABLES QUE HAY QUE HACER A MANO (dos):
  1. el PRINT "GRUNT: ALERTA (!) - entra en combate"  ->  este BRANCH nuevo
  2. la salida "False" de este BRANCH                 ->  el MoveToActor que
                                                          ya existe
""")

    gv = g.var_get("IsInCover", CAT_BOOL, 0, 220)
    no = g.call("Not_PreBool", C_KML, 220, 220, pure=True)
    no.pin("A", CAT_BOOL)
    no.pin("ReturnValue", CAT_BOOL, out=True)
    gv.get("IsInCover").to(no.get("A"))

    b = g.branch(440, 40)
    no.get("ReturnValue").to(b.get("Condition"))

    p = print_dbg(g, "GRUNT: entro en combate SIN cobertura -> a cubrirse",
                  680, -80, color="(R=0.0,G=0.66,B=1.0,A=1.0)")
    b.get("then").to(p.exec_in)

    seq = g.node_sequence(1040, -80, n=2)
    p.exec_out.to(seq.exec_in)

    fuego = g.call_self("Ev_FireLoop", None, 1300, -160)
    seq.get("then_0").to(fuego.exec_in)

    cubrir = g.call_self("Ev_TakeCover", None, 1300, 60)
    seq.get("then_1").to(cubrir.exec_in)

    g.comment("COBERTURA AL ENTRAR EN COMBATE. "
              "Entrada: del PRINT 'ALERTA (!)'. "
              "False: al MoveToActor que ya existe",
              -60, -240, 1700, 640,
              color="(R=0.000000,G=0.400000,B=0.800000,A=0.400000)")
    emit(g, "44_AIC_CoverOnCombat.txt")


if __name__ == "__main__":
    print("Generando pegados de los arreglos 2026-09-05 en %s\n" % OUT)
    gen_crouch()
    gen_aim_from_patrol()
    gen_grunt_destroy()
    gen_bandage()
    gen_cover_on_combat()
    print("\n%d ficheros, %d nodos en total"
          % (len(generados), sum(n for _, n in generados)))
