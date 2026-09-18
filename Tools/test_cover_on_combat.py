# -*- coding: utf-8 -*-
"""
Mide que los soldados BUSCAN COBERTURA al entrar en combate, SIN que el
jugador les apunte.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/test_cover_on_combat.py

POR QUE NO VALE test_ai_upgrade.py
----------------------------------
Ese banco daba 0 fallos en cobertura y aun asi los soldados no se cubrian
jugando. El motivo: su funcion apuntar_a() se RE-APLICA en cada tanda, o sea
que mantiene al jugador encanonando al soldado durante toda la medicion. Y
hasta el 2026-09-05 el UNICO llamador de Ev_TakeCover estaba dentro de
Ev_AimWatch, detras de BeingAimedAt. La prueba pasaba por el motivo
equivocado: medía justo la unica condicion en la que funcionaba.

Aqui NO se toca la rotacion de la camara ni HaveGun en ningun momento. El
soldado tiene que detectar al jugador por la VISTA, entrar en combate y
cubrirse por su cuenta.

Al jugador se le sostiene la vida en cada sondeo: dos soldados a 500 UU lo
matan en unos 8 s, y a un cadaver dejan de dispararle (eso ya produjo una
medicion falsa el mismo dia).

Informe en Saved/Cover_Report.txt. Acaba en "FALLOS: N".
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTO = os.path.join(AQUI, "ue_remote.py")
TMP = os.path.join(AQUI, "_cover_paso.py")
INFORME = os.path.join(RAIZ, "Saved", "Cover_Report.txt")
LOG = os.path.join(RAIZ, "Saved", "Logs", "FatalityBlast.log")

NIVEL = "/Game/ThirdPerson/Lvl_01_MilitaryBase"
VIDA_SOSTEN = 90.0

COMUN = """
import unreal
w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()

def comp(a, nombre):
    for c in a.get_components_by_class(unreal.ActorComponent):
        if c.get_class().get_name() == nombre:
            return c
    return None

def actores(cls):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
            if a.get_class().get_name() == cls]

def idx(v):
    try:
        return int(getattr(v, 'value', v))
    except Exception:
        return -1
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

# Coloca al jugador DELANTE del soldado para que lo vea.
# NO se toca la rotacion de control ni HaveGun: nada de apuntar.
PASOS["colocar"] = COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    print('MUNDO=%s' % w.get_name())
    pj = unreal.GameplayStatics.get_player_character(w, 0)
    gs = actores('BP_Grunt_C')
    print('GRUNTS=%d' % len(gs))
    g = min(gs, key=lambda a: unreal.MathLibrary.vector_distance(
        a.get_actor_location(), pj.get_actor_location()))
    lg = g.get_actor_location()
    fw = g.get_actor_forward_vector()
    pj.set_actor_location(
        unreal.Vector(lg.x + fw.x * 600.0, lg.y + fw.y * 600.0, lg.z),
        False, False)
    print('OBJETIVO=%s' % g.get_name())
    try:
        print('HAVEGUN=%s' % pj.get_editor_property('HaveGun'))
    except Exception:
        pass
"""

PASOS["tick"] = (COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    pj = unreal.GameplayStatics.get_player_character(w, 0)
    hs = comp(pj, 'BPC_HealthSystem_C')
    hs.set_editor_property('Health', __VIDA__)
    hs.set_editor_property('IsDead', False)
    ctrls = actores('BP_GruntAIController_C')
    en_combate = 0
    cubiertos = 0
    apuntados = 0
    for c in ctrls:
        if idx(c.get_editor_property('State')) == 3:
            en_combate += 1
            if c.get_editor_property('IsInCover'):
                cubiertos += 1
        if c.get_editor_property('BeingAimedAt'):
            apuntados += 1
    print('EN_COMBATE=%d' % en_combate)
    print('CUBIERTOS=%d' % cubiertos)
    print('APUNTADOS=%d' % apuntados)
""").replace("__VIDA__", repr(VIDA_SOSTEN))


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


fallos = []
lineas = []


def say(m):
    print(m)
    lineas.append(m)


def comp_(cond, msg):
    say(("   OK     " if cond else "   FALLO  ") + msg)
    if not cond:
        fallos.append(msg)


say("=" * 70)
say(" COBERTURA AL ENTRAR EN COMBATE, SIN APUNTAR")
say("=" * 70)

say("fase 0: cargando el nivel y arrancando PIE")
remoto("pie_off")
time.sleep(3)
say("   nivel: %s" % campos(remoto("cargar")).get("NIVEL", "?"))
time.sleep(2)
remoto("pie_on")
time.sleep(8)
marca = log_tam()

say("fase 1: poniendo al jugador a la vista de un soldado (sin apuntarle)")
c0 = campos(remoto("colocar"))
say("   soldados=%s  objetivo=%s  el jugador lleva arma=%s"
    % (c0.get("GRUNTS"), c0.get("OBJETIVO"), c0.get("HAVEGUN")))

say("fase 2: dejando que reaccionen solos (16 s, sosteniendo la vida)")
serie = []
for i in range(11):
    time.sleep(1.5)
    t = campos(remoto("tick"))
    serie.append((t.get("EN_COMBATE", "?"), t.get("CUBIERTOS", "?"),
                  t.get("APUNTADOS", "?")))
say("   en combate / cubiertos / apuntados por sondeo:")
say("     " + "  ".join("%s/%s/%s" % s for s in serie))

texto = log_desde(marca)
n_alerta = texto.count("entra en combate")
n_decide = texto.count("SIN cobertura -> a cubrirse")
n_cubierto = texto.count("GRUNT: a cubierto")

say("")
say("   trazas:")
say("     'entra en combate' ............... %d" % n_alerta)
say("     'SIN cobertura -> a cubrirse' .... %d" % n_decide)
say("     'GRUNT: a cubierto' ............. %d" % n_cubierto)

ult = serie[-1] if serie else ("0", "0", "0")
comp_(int(ult[2]) == 0,
      "NADIE fue apuntado en toda la prueba (%s): si alguno lo fue, la medida "
      "no distingue el camino nuevo del viejo" % ult[2])
comp_(n_alerta > 0, "algun soldado entro en combate (%d)" % n_alerta)
comp_(n_decide > 0,
      "la rama nueva se ejecuto: decidieron cubrirse al entrar en combate (%d)"
      % n_decide)
comp_(n_cubierto > 0,
      "algun soldado LLEGO a su cobertura (traza 'a cubierto': %d)" % n_cubierto)
comp_(int(ult[1]) > 0,
      "al final hay soldados con IsInCover = True (%s de %s en combate)"
      % (ult[1], ult[0]))

remoto("pie_off")

say("")
say("FALLOS: %d" % len(fallos))
with open(INFORME, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print("informe -> %s" % INFORME)
sys.exit(1 if fallos else 0)
