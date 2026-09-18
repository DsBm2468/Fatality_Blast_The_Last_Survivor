# -*- coding: utf-8 -*-
"""
Reproduce EN EL NIVEL REAL el caso que Walter ve fallar: curarse mientras un
SOLDADO dispara, y comprobar si la canalizacion se corta.

    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/test_heal_interrupt_real.py

POR QUE NO VALE EL CASO 4 DE run_lab_tests.py
---------------------------------------------
Ese mide en Lvl_02_TestLab con un BP_TestDamageDealer, que llama a la interfaz
con ForceInterrupt puesto a mano. En juego el dano viene del Ev_FireLoop de
BP_GruntAIController y pasa por MSG TakeDamage -> la implementacion de
BPI_HealthSystem del personaje -> BPC_HealthSystem -> GetComponentByClass
(BPC_Curation) -> OnDamageReaction. Son dos caminos distintos y solo uno
estaba probado.

TRES FORMAS DE MEDIR MAL QUE COSTARON TRES INTENTOS
---------------------------------------------------
1. **El botiquin hay que RECOGERLO.** Escribir Object_Is_FirstAidKit con
   set_editor_property no sirve: la escritura de PIE se revierte antes de que
   el grafo la lea, TryStartHeal se cae por la guarda de "sin suministros" y
   ademas esa guarda NO imprime, asi que parece que el evento no se ejecuto.
   Hay que llamar a Interact sobre el ACTOR botiquin.
2. **Al jugador hay que mantenerlo VIVO.** Dos soldados a 500 UU lo bajan de
   100 a 0 en unos 8 s. En el primer intento la cura acabo entera y sin
   interrumpirse... porque el jugador ya estaba muerto y a un cadaver no le
   disparan. Aqui la vida se re-inyecta en CADA sondeo.
3. **La prueba es la LINEA DEL LOG, no la variable.** IsChanneling leido desde
   Python da False mientras el log dice "Curando...". El log no miente.

Informe en Saved/HealInterrupt_Report.txt. Acaba en "FALLOS: N".
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
REMOTO = os.path.join(AQUI, "ue_remote.py")
TMP = os.path.join(AQUI, "_heal_paso.py")
INFORME = os.path.join(RAIZ, "Saved", "HealInterrupt_Report.txt")
LOG = os.path.join(RAIZ, "Saved", "Logs", "FatalityBlast.log")

NIVEL = "/Game/ThirdPerson/Lvl_01_MilitaryBase"
VIDA_SOSTEN = 90.0      # se re-inyecta en cada sondeo para que no muera

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
        unreal.Vector(lg.x + fw.x * 500.0, lg.y + fw.y * 500.0, lg.z),
        False, False)
    print('OBJETIVO=%s' % g.get_name())
    print('DIST=%.0f' % unreal.MathLibrary.vector_distance(
        pj.get_actor_location(), lg))
"""

# sostiene la vida y devuelve el estado. Se llama en cada sondeo.
# OJO: aqui NO se usa el operador % para inyectar VIDA_SOSTEN; el cuerpo ya
# lleva %.1f y %s por todas partes y mezclar las dos cosas revienta.
PASOS["tick"] = COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    pj = unreal.GameplayStatics.get_player_character(w, 0)
    hs = comp(pj, 'BPC_HealthSystem_C')
    cur = comp(pj, 'BPC_Curation_C')
    print('VIDA_LEIDA=%.1f' % hs.get_editor_property('Health'))
    hs.set_editor_property('Health', __VIDA__)
    hs.set_editor_property('IsDead', False)
    print('CANALIZANDO=%s' % cur.get_editor_property('IsChanneling'))
    gs = actores('BP_Grunt_C')
    g = min(gs, key=lambda a: unreal.MathLibrary.vector_distance(
        a.get_actor_location(), pj.get_actor_location()))
    for x in actores('BP_GruntAIController_C'):
        if x.get_editor_property('GruntPawn') == g:
            v = x.get_editor_property('State')
            print('ESTADO_SOLDADO=%s' % int(getattr(v, 'value', v)))
            print('CUBIERTO=%s' % x.get_editor_property('IsInCover'))
""".replace("__VIDA__", repr(VIDA_SOSTEN))

PASOS["curar"] = COMUN + """
if w is None:
    print('SIN_MUNDO')
else:
    pj = unreal.GameplayStatics.get_player_character(w, 0)
    hs = comp(pj, 'BPC_HealthSystem_C')
    inv = comp(pj, 'BPC_Inventary_C')
    cur = comp(pj, 'BPC_Curation_C')
    kits = actores('BP_FirstAidKit_C')
    print('KITS=%d' % len(kits))
    if kits:
        kits[0].call_method('Interact', args=(pj,))   # RECOGERLO, no escribirlo
    print('KIT=%s' % (inv.get_editor_property('Object_Is_FirstAidKit') is not None))
    hs.set_editor_property('Health', 60.0)
    hs.set_editor_property('IsDead', False)
    try:
        cur.call_method('TryStartHeal')
        print('CURA_PEDIDA=si')
    except Exception as e:
        print('CURA_PEDIDA=no (%s)' % e)
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
say(" CURACION INTERRUMPIDA POR UN SOLDADO, EN EL NIVEL REAL")
say("=" * 70)

say("fase 0: cargando el nivel y arrancando PIE")
remoto("pie_off")
time.sleep(3)
say("   nivel: %s" % campos(remoto("cargar")).get("NIVEL", "?"))
time.sleep(2)
remoto("pie_on")
time.sleep(8)

say("fase 1: poniendo al jugador delante de un soldado")
c0 = campos(remoto("colocar"))
say("   soldados=%s  objetivo=%s  dist=%s"
    % (c0.get("GRUNTS"), c0.get("OBJETIVO"), c0.get("DIST")))

say("fase 2: esperando a que el soldado entre en combate (sosteniendo la vida)")
est = "?"
for i in range(10):
    time.sleep(1.5)
    t = campos(remoto("tick"))
    est = t.get("ESTADO_SOLDADO", "?")
    if est == "3":
        break
say("   estado del soldado=%s  cubierto=%s" % (est, t.get("CUBIERTO")))
comp_(est == "3", "el soldado llega a COMBATE")

marca = log_tam()
say("fase 3: arrancando la curacion con el soldado disparando")
cu = campos(remoto("curar"))
say("   botiquines en el nivel=%s  recogido=%s  cura pedida=%s"
    % (cu.get("KITS"), cu.get("KIT"), cu.get("CURA_PEDIDA")))

say("fase 4: sosteniendo la vida durante el canal y mirando el log")
for i in range(12):
    time.sleep(0.4)
    remoto("tick")

texto = log_desde(marca)
n_curando = texto.count("Curando...")
n_inter = texto.count("Curacion interrumpida")
n_completa = texto.count("Curacion completa")
n_impactos = texto.count("DISPARO ACERTADO")
n_muerto = texto.count("PLAYER MUERTO")

say("")
say("   trazas desde que arranco la cura:")
say("     'Curando...' ................... %d" % n_curando)
say("     'DISPARO ACERTADO' ............. %d" % n_impactos)
say("     'Curacion interrumpida' ........ %d" % n_inter)
say("     'Curacion completa' ............ %d" % n_completa)
say("     'PLAYER MUERTO' ................ %d" % n_muerto)

comp_(n_curando > 0, "la curacion llego a arrancar")
comp_(n_impactos > 0, "el soldado acerto algun disparo durante el canal")
comp_(n_muerto == 0,
      "el jugador siguio vivo durante el canal (si muere, dejan de dispararle "
      "y la medida no vale)")
comp_(n_inter > 0,
      "LA CURACION SE INTERRUMPIO al recibir el disparo "
      "(interrumpida=%d, completada=%d)" % (n_inter, n_completa))

remoto("pie_off")

say("")
say("FALLOS: %d" % len(fallos))
with open(INFORME, "w", encoding="utf-8") as f:
    f.write("\n".join(lineas) + "\n")
print("informe -> %s" % INFORME)
sys.exit(1 if fallos else 0)
