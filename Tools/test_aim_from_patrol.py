# -*- coding: utf-8 -*-
"""
A-8  Banco AISLADO del apuntado desde PATRULLA.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/test_aim_from_patrol.py

POR QUE EXISTE ESTE BANCO Y NO VALE test_ai_upgrade.py
------------------------------------------------------
test_ai_upgrade.py coloca al jugador A 700 UU DE FRENTE al soldado. Ahi la
VISTA (12 m, 90 grados) lo pasa a Sospecha sola, y el apuntado solo acelera lo
que ya iba a pasar. Por eso el 2026-09-03 dio 0 fallos y se dio por terminada
la deteccion de apuntado, cuando desde Patrulla no habia rama ninguna.
Ese es el aviso de metodo de la auditoria: una prueba puede pasar por el
motivo equivocado.

Aqui el jugador se coloca DETRAS del soldado, fuera de su cono de vision, y le
apunta con la camara. Si el soldado reacciona, solo puede ser por el apuntado.

La prueba de verdad es la LINEA DEL LOG, no la variable: las escrituras a
instancias de PIE se revierten, el log no. La traza
"me estan apuntando desde patrulla" solo es alcanzable desde State == Patrulla.

Informe en Saved/AimPatrol_Report.txt. Acaba en "FALLOS: N".
"""
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTO = os.path.join(AQUI, "ue_remote.py")
TMP = os.path.join(AQUI, "_aim_paso.py")
INFORME = os.path.join(RAIZ, "Saved", "AimPatrol_Report.txt")
LOG = os.path.join(RAIZ, "Saved", "Logs", "FatalityBlast.log")

NIVEL = "/Game/ThirdPerson/Lvl_01_MilitaryBase"
MARCA = "me estan apuntando desde patrulla"

COMUN = """
import unreal
UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
w = UES.get_game_world()
ESTADOS = ["Patrulla", "Sospecha", "Investiga", "COMBATE", "Busca", "Muerto"]

def idx(v):
    # get_editor_property sobre un byte-enum devuelve el OBJETO enum, no un int
    try:
        return int(getattr(v, "value", v))
    except Exception:
        return -1

def ctrl_de(g, ctrls):
    for c in ctrls:
        try:
            if c.get_editor_property("GruntPawn") == g:
                return c
        except Exception:
            pass
    return None
"""

PASOS = {
    "cargar": ("import unreal\n"
               "les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)\n"
               "les.load_level('%s')\n"
               "print('NIVEL=%%s' %% unreal.get_editor_subsystem("
               "unreal.UnrealEditorSubsystem).get_editor_world().get_name())\n" % NIVEL),

    "pie_on": ("import unreal\n"
               "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
               ".editor_request_begin_play()\nprint('PIE_ON')\n"),

    "pie_off": ("import unreal\n"
                "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
                ".editor_request_end_play()\nprint('PIE_OFF')\n"),

    # Coloca al jugador DETRAS del soldado elegido, fuera del cono de vision,
    # apuntandole con la camara. Se re-aplica en cada tanda: PIE revierte.
    "apuntar": COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    print('MUNDO=%s' % w.get_name())
    todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
    grunts = [a for a in todos if a.get_class().get_name() == 'BP_Grunt_C']
    ctrls = [a for a in todos if a.get_class().get_name() == 'BP_GruntAIController_C']
    pj = unreal.GameplayStatics.get_player_character(w, 0)
    pcon = unreal.GameplayStatics.get_player_controller(w, 0)
    # solo sirven los que siguen en Patrulla
    cand = []
    for g in grunts:
        c = ctrl_de(g, ctrls)
        if c is not None and idx(c.get_editor_property('State')) == 0:
            cand.append((g, c))
    print('PATRULLANDO=%d de %d' % (len(cand), len(grunts)))
    if not cand:
        print('SIN_CANDIDATO')
    else:
        lp = pj.get_actor_location()
        g, c = min(cand, key=lambda p: unreal.MathLibrary.vector_distance(
            p[0].get_actor_location(), lp))
        lg = g.get_actor_location()
        # DETRAS del soldado: -ForwardVector, para quedar fuera del cono de 90 grados
        fw = g.get_actor_forward_vector()
        destino = unreal.Vector(lg.x - fw.x * 700.0, lg.y - fw.y * 700.0, lg.z + 10.0)
        pj.set_actor_location(destino, False, False)
        mirar = unreal.MathLibrary.find_look_at_rotation(pj.get_actor_location(), lg)
        if pcon is not None:
            pcon.set_control_rotation(mirar)
        pj.set_actor_rotation(unreal.Rotator(0.0, mirar.yaw, 0.0), False)
        try:
            pj.set_editor_property('HaveGun', True)
        except Exception as e:
            print('AVISO_HAVEGUN=%s' % e)
        real = pj.get_actor_location()
        # angulo entre el frente del soldado y la direccion al jugador:
        # > 45 grados quiere decir que NO lo tiene en el cono de vision
        dirp = unreal.MathLibrary.normal(
            unreal.Vector(real.x - lg.x, real.y - lg.y, 0.0))
        dot = fw.x * dirp.x + fw.y * dirp.y
        print('OBJETIVO=%s' % g.get_name())
        print('DIST=%.0f' % unreal.MathLibrary.vector_distance(real, lg))
        print('DOT_VISION=%.3f' % dot)
        print('ESTADO=%d' % idx(c.get_editor_property('State')))
        print('APUNTADO=%s' % c.get_editor_property('BeingAimedAt'))
        print('DESVIO=%.0f' % unreal.MathLibrary.vector_distance(real, destino))
""",

    "medir": COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
    grunts = [a for a in todos if a.get_class().get_name() == 'BP_Grunt_C']
    ctrls = [a for a in todos if a.get_class().get_name() == 'BP_GruntAIController_C']
    pj = unreal.GameplayStatics.get_player_character(w, 0)
    lp = pj.get_actor_location()
    g = min(grunts, key=lambda a: unreal.MathLibrary.vector_distance(
        a.get_actor_location(), lp))
    c = ctrl_de(g, ctrls)
    print('OBJETIVO=%s' % g.get_name())
    print('ESTADO=%d' % idx(c.get_editor_property('State')))
    print('ESTADO_NOMBRE=%s' % ESTADOS[idx(c.get_editor_property('State'))])
    print('APUNTADO=%s' % c.get_editor_property('BeingAimedAt'))
    print('DIST=%.0f' % unreal.MathLibrary.vector_distance(
        g.get_actor_location(), lp))
""",
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
        if "=" in linea:
            k, _, v = linea.partition("=")
            k = k.strip()
            if k.isupper():
                d[k] = v.strip()
    return d


def log_tam():
    try:
        return os.path.getsize(LOG)
    except OSError:
        return 0


def log_desde(pos):
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            f.seek(pos)
            return f.read()
    except OSError:
        return ""


fallos = []
lineas = []


def say(m):
    print(m)
    lineas.append(m)


def comp(cond, msg):
    say(("   OK     " if cond else "   FALLO  ") + msg)
    if not cond:
        fallos.append(msg)


say("=" * 70)
say(" BANCO AISLADO DEL APUNTADO DESDE PATRULLA (A-8)")
say("=" * 70)

say("fase 0: cargando %s y arrancando PIE" % NIVEL.rsplit("/", 1)[-1])
remoto("pie_off")
time.sleep(3)
sal = remoto("cargar")
say("   %s" % campos(sal).get("NIVEL", "?"))
time.sleep(2)
remoto("pie_on")
time.sleep(8)

marca_log = log_tam()

say("fase 1: colocando al jugador DETRAS del soldado y apuntandole")
ap = campos(remoto("apuntar"))
if "SIN_CANDIDATO" in str(ap) or not ap.get("OBJETIVO"):
    say("   FALLO: no hay ningun soldado en Patrulla al que apuntar")
    fallos.append("sin candidato en Patrulla")
else:
    say("   mundo=%s  patrullando=%s" % (ap.get("MUNDO"), ap.get("PATRULLANDO")))
    say("   objetivo=%s  dist=%s  estado inicial=%s  apuntado=%s"
        % (ap.get("OBJETIVO"), ap.get("DIST"), ap.get("ESTADO"), ap.get("APUNTADO")))
    say("   dot del cono de vision = %s  (negativo = el jugador esta a su espalda)"
        % ap.get("DOT_VISION"))

    comp(float(ap.get("DESVIO", 999)) < 150,
         "el jugador se quedo donde se le puso (PIE no revirtio)")
    comp(float(ap.get("DOT_VISION", 1)) < 0.0,
         "el jugador esta FUERA del cono de vision (dot=%s): si reacciona, "
         "es por el apuntado" % ap.get("DOT_VISION"))
    comp(ap.get("ESTADO") == "0", "el soldado partia de Patrulla")

    say("fase 2: esperando a que Ev_AimWatch haga su pasada")
    for i in range(6):
        time.sleep(2.5)
        remoto("apuntar")      # re-aplicar: PIE revierte las escrituras
    med = campos(remoto("medir"))
    say("   estado final=%s  apuntado=%s  dist=%s"
        % (med.get("ESTADO_NOMBRE"), med.get("APUNTADO"), med.get("DIST")))

    texto = log_desde(marca_log)
    n_marca = texto.count(MARCA)
    n_spot = texto.count("GRUNT: sospecha")
    say("")
    say("   trazas nuevas en el log desde que arranco PIE:")
    say("     '%s' ............ %d" % (MARCA, n_marca))
    say("     'GRUNT: sospecha (?)' ......................... %d" % n_spot)

    comp(med.get("APUNTADO") == "True", "BeingAimedAt = True")
    comp(n_marca > 0,
         "la rama nueva se ejecuto (esa traza SOLO es alcanzable con "
         "State == Patrulla)")
    comp(n_spot > 0, "Ev_Spot se ejecuto detras de la rama")
    comp(med.get("ESTADO") != "0",
         "el soldado dejo de patrullar (estado final: %s)"
         % med.get("ESTADO_NOMBRE"))

    remoto("pie_off")

say("")
say("FALLOS: %d" % len(fallos))

with open(INFORME, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print("informe -> %s" % INFORME)
sys.exit(1 if fallos else 0)
