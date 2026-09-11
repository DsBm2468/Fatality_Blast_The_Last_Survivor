# -*- coding: utf-8 -*-
"""
A-1  Banco del AGACHADO, medido en PIE por control remoto.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/test_crouch.py

No prueba la tecla C (eso se lee en el grafo con audit_graph.py); prueba lo
que estaba realmente roto: NavAgentProps.CanCrouch estaba en False, asi que
el nodo Crouch se ejecutaba y no hacia NADA, sin dar ningun error.

POR QUE VA EN FASES
-------------------
ACharacter::Crouch() NO agacha: solo pone bWantsToCrouch. El agachado lo
aplica UCharacterMovementComponent en el siguiente PerformMovement. Leer
bIsCrouched en la misma llamada remota devuelve siempre False y hace parecer
que sigue roto. La primera version de este banco dio 2 fallos falsos por eso.
Las esperas van AQUI, en el driver: mientras duerme, el editor sigue
tickeando.

Informe en Saved/Crouch_Report.txt. Acaba en "FALLOS: N".
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTO = os.path.join(AQUI, "ue_remote.py")
TMP = os.path.join(AQUI, "_crouch_paso.py")
INFORME = os.path.join(RAIZ, "Saved", "Crouch_Report.txt")

CABECERA = ("import unreal\n"
            "w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()\n"
            "if w is None:\n"
            "    print('SIN_MUNDO')\n"
            "else:\n"
            "    pc = unreal.GameplayStatics.get_player_character(w, 0)\n")

PASOS = {
    "pie_on": ("import unreal\n"
               "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
               ".editor_request_begin_play()\nprint('PIE_ON')\n"),
    "pie_off": ("import unreal\n"
                "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
                ".editor_request_end_play()\nprint('PIE_OFF')\n"),
    "leer": CABECERA + (
        "    cm = pc.character_movement\n"
        "    nav = cm.get_editor_property('nav_agent_props')\n"
        "    print('MUNDO=%s' % w.get_name())\n"
        "    print('CANCROUCH=%s' % nav.get_editor_property('can_crouch'))\n"
        "    print('CROUCHSPEED=%.1f' % cm.get_editor_property('max_walk_speed_crouched'))\n"
        "    print('WALKSPEED=%.1f' % cm.max_walk_speed)\n"
        "    print('CROUCHED=%s' % pc.get_editor_property('is_crouched'))\n"
        "    print('ALTURA=%.1f' % pc.capsule_component.get_editor_property('capsule_half_height'))\n"),
    "agachar": CABECERA + "    pc.crouch(False)\n    print('CROUCH_PEDIDO')\n",
    "levantar": CABECERA + "    pc.un_crouch(False)\n    print('UNCROUCH_PEDIDO')\n",
}


def remoto(paso):
    with open(TMP, "w", encoding="utf-8") as f:
        f.write(PASOS[paso])
    r = subprocess.run([sys.executable, REMOTO, TMP],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def campos(salida):
    d = {}
    for linea in salida.splitlines():
        if "=" in linea and linea.split("=")[0].isupper():
            k, _, v = linea.partition("=")
            d[k.strip()] = v.strip()
    return d


fallos = []
lineas = []


def say(m):
    print(m)
    lineas.append(m)


def comp(cond, msg):
    say(("   OK     " if cond else "   FALLO  ") + msg)
    if not cond:
        fallos.append(msg)


say("=" * 66)
say(" BANCO DEL AGACHADO (A-1)")
say("=" * 66)

say("fase 0: arrancando PIE")
remoto("pie_off")
time.sleep(3)
remoto("pie_on")
time.sleep(6)

base = campos(remoto("leer"))
if not base:
    say("FALLO: no hay mundo de PIE")
    fallos.append("sin PIE")
else:
    say("   mundo de PIE: %s" % base.get("MUNDO"))
    comp(base.get("CANCROUCH") == "True",
         "NavAgentProps.CanCrouch = True (era False: el nodo Crouch no hacia nada)")
    comp(abs(float(base.get("CROUCHSPEED", 0)) - 300.0) < 0.01,
         "MaxWalkSpeedCrouched = 300 (GDD)")
    comp(base.get("CROUCHED") == "False", "se arranca de pie")
    alto_pie = float(base.get("ALTURA", 0))
    say("   de pie:   media_altura = %.1f" % alto_pie)

    say("fase 1: agachar")
    remoto("agachar")
    time.sleep(1.5)
    ag = campos(remoto("leer"))
    alto_ag = float(ag.get("ALTURA", 0))
    say("   agachado: media_altura = %.1f" % alto_ag)
    comp(ag.get("CROUCHED") == "True", "Crouch() pone bIsCrouched = True")
    comp(alto_ag < alto_pie,
         "la capsula se encoge (%.1f -> %.1f)" % (alto_pie, alto_ag))

    say("fase 2: levantar")
    remoto("levantar")
    time.sleep(1.5)
    dp = campos(remoto("leer"))
    comp(dp.get("CROUCHED") == "False", "UnCrouch() vuelve a poner bIsCrouched = False")
    comp(abs(float(dp.get("ALTURA", 0)) - alto_pie) < 0.01,
         "la capsula recupera su altura")

    remoto("pie_off")

say("")
say("FALLOS: %d" % len(fallos))

with open(INFORME, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print("informe -> %s" % INFORME)
sys.exit(1 if fallos else 0)
