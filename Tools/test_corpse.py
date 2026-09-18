# -*- coding: utf-8 -*-
"""
A-3  Banco del CADAVER: matar a un soldado en PIE y ver si desaparece.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/test_corpse.py

QUE SE MIDE
-----------
La cadena de muerte completa:

    EVENT Death -> call Ev_GruntDeath -> [PRINT "Hello", StopMovement,
                                          UnPossess, ocultar icono, capsula
                                          NoCollision, Mesh profile "None",
                                          Mesh Simulate FALSE]
                -> (VUELVE) -> capsula NoCollision -> Mesh profile "Ragdoll"
                            -> Mesh Simulate TRUE -> PRINT "SOLDADO MUERTO!!!!!"
                            -> Delay(5) -> PRINT "cadaver retirado"
                            -> DestroyActor          <-- esto es A-3

Antes del 2026-09-05 el DestroyActor estaba SUELTO, sin entrada de ejecucion,
y con 20 soldados en el nivel eso eran hasta 20 ragdolls acumulandose.

Que `call Ev_GruntDeath` VUELVE esta medido, no supuesto: en el log del
2026-09-04 aparecen las dos trazas, "Hello" y "SOLDADO MUERTO", en la misma
sesion. Por eso el arreglo cuelga del final del todo y no de Ev_GruntDeath:
colgarlo antes destruiria el actor antes de aplicar el ragdoll.

COMO SE MATA AL SOLDADO, Y POR QUE ASI
--------------------------------------
Con `g.call_method('Death')`. Los eventos personalizados de un Blueprint son
UFunctions y se pueden invocar por nombre desde Python.

Lo que NO vale, y se probo:
  * Escribirle Health = 0: las escrituras a instancias de PIE se revierten, y
    ademas el dispatcher OnDeath no se emitiria.
  * BP_TestDamageDealer.FireOnce(): ese emisor pega SIEMPRE al GetPlayerPawn.
    Es un emisor de laboratorio apuntado al jugador; no puede danar a un
    soldado por mucho que se le ponga al lado y se le suba el Radius.
  * Spawnear cualquier cosa en el mundo de PIE: GameplayStatics no expone el
    spawn (begin_deferred_actor_spawn_from_class NO existe) y
    EditorLevelLibrary solo toca el mundo de EDITOR.

La ruta del dano (bala -> BPI_HealthSystem -> OnDeath -> Death) no la cubre
este banco; se cubre disparando en juego.

Informe en Saved/Corpse_Report.txt. Acaba en "FALLOS: N".
"""
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTO = os.path.join(AQUI, "ue_remote.py")
TMP = os.path.join(AQUI, "_corpse_paso.py")
INFORME = os.path.join(RAIZ, "Saved", "Corpse_Report.txt")
LOG = os.path.join(RAIZ, "Saved", "Logs", "FatalityBlast.log")

NIVEL = "/Game/ThirdPerson/Lvl_01_MilitaryBase"
ESPERA_CADAVER = 5.0     # el Delay cableado el 2026-09-05

COMUN = """
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()

def grunts():
    todos = unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
    return [a for a in todos if a.get_class().get_name() == 'BP_Grunt_C']
"""

PASOS = {}

PASOS["cargar"] = (
    "import unreal\n"
    "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('%s')\n"
    "print('NIVEL=%%s' %% unreal.get_editor_subsystem("
    "unreal.UnrealEditorSubsystem).get_editor_world().get_name())\n" % NIVEL)

PASOS["pie_on"] = ("import unreal\n"
                   "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
                   ".editor_request_begin_play()\nprint('PIE_ON')\n")

PASOS["pie_off"] = ("import unreal\n"
                    "unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)"
                    ".editor_request_end_play()\nprint('PIE_OFF')\n")

PASOS["matar"] = COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    print('MUNDO=%s' % w.get_name())
    gs = grunts()
    print('GRUNTS_ANTES=%d' % len(gs))
    if not gs:
        print('SIN_GRUNTS')
    else:
        g = gs[0]
        print('VICTIMA=%s' % g.get_name())
        try:
            g.call_method('Death')
            print('MUERTO=si')
        except Exception as e:
            print('MUERTO=no (%s)' % e)
"""

PASOS["contar"] = COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    print('GRUNTS=%d' % len(grunts()))
"""


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
            if k.strip().isupper():
                d[k.strip()] = v.strip()
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


def sello(texto, marca):
    """Segundos del sello de tiempo de la primera linea que contenga `marca`.
    Sirve para medir el Delay de verdad en vez de fiarse de que "paso algo"."""
    for linea in texto.splitlines():
        if marca in linea:
            m = re.match(r"\[[\d.]+-(\d\d)\.(\d\d)\.(\d\d):(\d\d\d)\]", linea)
            if m:
                h, mi, s, ms = (int(x) for x in m.groups())
                return h * 3600 + mi * 60 + s + ms / 1000.0
    return None


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
say(" BANCO DEL CADAVER (A-3)")
say("=" * 70)

say("fase 0: cargando el nivel y arrancando PIE")
remoto("pie_off")
time.sleep(3)
say("   nivel abierto: %s" % campos(remoto("cargar")).get("NIVEL", "?"))
time.sleep(2)
remoto("pie_on")
time.sleep(8)
marca = log_tam()

say("fase 1: matando a un soldado (call_method('Death'))")
m = campos(remoto("matar"))
say("   mundo=%s  soldados=%s  victima=%s  muerto=%s"
    % (m.get("MUNDO"), m.get("GRUNTS_ANTES"), m.get("VICTIMA"), m.get("MUERTO")))
antes = int(m.get("GRUNTS_ANTES", 0) or 0)

if m.get("MUERTO") != "si" or antes == 0:
    say("   FALLO: no se pudo matar al soldado")
    fallos.append("no se pudo invocar Death")
else:
    time.sleep(2.0)
    d1 = campos(remoto("contar"))
    texto = log_desde(marca)
    say("   a los 2 s: soldados=%s" % d1.get("GRUNTS"))
    comp(texto.count("SOLDADO MUERTO") > 0,
         "la cadena de muerte llego al final (traza 'SOLDADO MUERTO')")
    comp(int(d1.get("GRUNTS", 0)) == antes,
         "el cadaver sigue en el mundo a los 2 s (%s de %d): el ragdoll "
         "tiene que poder verse" % (d1.get("GRUNTS"), antes))

    say("fase 2: esperando los %.0f s del Delay y un margen" % ESPERA_CADAVER)
    time.sleep(ESPERA_CADAVER + 4.0)
    d2 = campos(remoto("contar"))
    texto = log_desde(marca)
    say("   a los %.0f s: soldados=%s" % (ESPERA_CADAVER + 6, d2.get("GRUNTS")))

    comp(texto.count("cadaver retirado") > 0,
         "el Delay llego hasta el DestroyActor (traza 'cadaver retirado')")
    comp(int(d2.get("GRUNTS", 99)) < antes,
         "el cadaver DESAPARECIO del mundo (%d -> %s soldados)"
         % (antes, d2.get("GRUNTS")))

    t0 = sello(texto, "SOLDADO MUERTO")
    t1 = sello(texto, "cadaver retirado")
    if t0 is not None and t1 is not None:
        dt = t1 - t0
        say("   retardo medido entre las dos trazas: %.2f s" % dt)
        comp(abs(dt - ESPERA_CADAVER) < 1.0,
             "el retardo es el Delay(%.0f) (medido %.2f s)" % (ESPERA_CADAVER, dt))
    else:
        comp(False, "no se pudieron leer los sellos de tiempo del log")

    remoto("pie_off")

say("")
say("FALLOS: %d" % len(fallos))

with open(INFORME, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print("informe -> %s" % INFORME)
sys.exit(1 if fallos else 0)
