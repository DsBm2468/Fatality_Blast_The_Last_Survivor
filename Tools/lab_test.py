# -*- coding: utf-8 -*-
"""
Ejecuta UN paso del banco de pruebas dentro del editor.

No se llama a mano: lo conduce Tools/run_lab_tests.py, que escribe el nombre
del paso en Tools/_paso.txt y lanza este fichero por Remote Execution.

POR QUE UN PASO POR LLAMADA
---------------------------
Escribir una propiedad, invocar logica y leer el resultado en la MISMA llamada
devuelve el valor viejo: el Blueprint corre en el frame siguiente y la llamada
remota no cede el hilo. Separar accion y lectura en dos llamadas es la unica
forma fiable de medir (LAB_DE_PRUEBAS.md seccion 12, trampa 1).

Y las escrituras a instancias de PIE se revierten solas (seccion 15.3: 6 de 8
en una prueba). Por eso el estado vive en Saved/_lab_state.json y cada paso que
depende de un valor lo RE-APLICA y lo VERIFICA antes de actuar, en vez de
escribir y confiar.

Reconstruido el 2026-08-31 (el original se perdio con Tools/).
"""
import json
import os
import unreal

# --------------------------------------------------------------- rutas
G = "/Game/ThirdPerson"
P_CUR = G + "/Components/BPC_Curation.BPC_Curation_C"
P_PRO = G + "/Components/BPC_ProtectionSystem.BPC_ProtectionSystem_C"
P_HP = G + "/Components/BPC_HealthSystem.BPC_HealthSystem_C"
P_INV = G + "/Components/BPC_Inventary.BPC_Inventary_C"
P_DEALER = G + "/Blueprints/TestLab/BP_TestDamageDealer.BP_TestDamageDealer_C"
P_KIT = G + "/Blueprints/Interactables/BP_FirstAidKit.BP_FirstAidKit_C"
P_BAND = G + "/Blueprints/Interactables/BP_Bandage.BP_Bandage_C"
P_SHIELD = G + "/Blueprints/Interactables/BP_Shield.BP_Shield_C"
MAPA = G + "/Lvl_02_TestLab"

SAVED = unreal.Paths.project_saved_dir()
ESTADO = os.path.join(SAVED, "_lab_state.json")
PASO_TXT = os.path.join(unreal.Paths.project_dir(), "Tools", "_paso.txt")

# Centro de cada estacion (LAB_DE_PRUEBAS.md seccion 1). El puesto es el centro;
# el emisor esta 400 UU al sur, dentro de su Radius.
PUESTO = {
    "E1": (-1400, -800),
    "E2": (0, -800), "E3": (1400, -800),
    "E4": (-1400, 600), "E5": (0, 600), "E6": (1400, 600),
    "E7": (-1400, 2000), "E8": (0, 2000), "E9": (1400, 2000),
}
Z_SUELO = 100.0

# Variables que el banco necesita escribir por instancia. Sin marcarlas,
# Python responde "cannot be edited on instances" y el caso se queda a medias.
EDITABLES = {
    G + "/Components/BPC_HealthSystem": ["Health", "MaxHealth", "IsDead"],
    G + "/Components/BPC_Curation": ["IsChanneling", "ChannelProgress",
                                     "CooldownUntil", "PendingDecayMax"],
    G + "/Components/BPC_ProtectionSystem": ["ShieldDurability", "IsGuarding",
                                             "ShieldEquipped", "GuardStartTime",
                                             "LastFinalDamage"],
    G + "/Components/BPC_Inventary": ["Object_Is_Weapon", "Object_Is_Throwable",
                                     "Object_Is_Shield", "Object_Is_FirstAidKit"],
    G + "/Blueprints/TestLab/BP_TestDamageDealer": [
        "DamageValue", "Interval", "Radius", "AutoFire",
        "DamageCanBeBlocked", "ForceInterrupt", "Health"],
}


# ------------------------------------------------------------- estado
def cargar():
    if os.path.isfile(ESTADO):
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    return {"checks": [], "notas": []}


def guardar(st):
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


ST = cargar()


def check(caso, texto, cond, detalle=""):
    ST["checks"].append({"caso": caso, "texto": texto,
                         "ok": bool(cond), "detalle": str(detalle)})
    print("   %s  [%s] %s%s" % ("OK  " if cond else "FALLO", caso, texto,
                                ("  -> " + str(detalle)) if detalle else ""))
    return bool(cond)


def nota(m):
    ST["notas"].append(m)
    print("   .. " + m)


# ------------------------------------------------------------- mundo
def gw():
    """En PIE, get_editor_world() devuelve None. Hay que usar get_game_world()."""
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()


def pawn():
    w = gw()
    return unreal.GameplayStatics.get_player_pawn(w, 0) if w else None


def comp(ruta):
    p = pawn()
    if p is None:
        return None
    try:
        return p.get_component_by_class(unreal.load_class(None, ruta))
    except Exception:
        return None


def actores(ruta):
    w = gw()
    if not w:
        return []
    return unreal.GameplayStatics.get_all_actors_of_class(w, unreal.load_class(None, ruta))


def cerca_de(lista, x, y, tol=250.0):
    """Los actores de PIE no conservan el label del editor de forma fiable, asi
    que se localizan por posicion contra las coordenadas de la seccion 1."""
    mejor, dmin = None, 1e9
    for a in lista:
        l = a.get_actor_location()
        d = ((l.x - x) ** 2 + (l.y - y) ** 2) ** 0.5
        if d < dmin:
            mejor, dmin = a, d
    return mejor if (mejor is not None and dmin <= tol) else None


EMISOR = {"E2": (0, -1200), "E3": (1400, -1200), "E4": (-1400, 200),
          "E5": (0, 1020), "E6": (1400, 200), "E7": (-1400, 1600),
          "E8": (0, 1500), "E9": (1400, 1600)}


def emisor(est):
    x, y = EMISOR[est]
    return cerca_de(actores(P_DEALER), x, y)


def poner(obj, prop, val):
    """Escribe y devuelve si cuajo. Las escrituras de PIE se revierten, asi que
    quien dependa del valor lo vuelve a poner en su propio paso."""
    if obj is None:
        return False
    try:
        obj.set_editor_property(prop, val)
    except Exception as e:
        nota("no se pudo escribir %s: %s" % (prop, e))
        return False
    try:
        leido = obj.get_editor_property(prop)
    except Exception:
        return True
    if isinstance(val, float):
        return abs(float(leido) - val) < 0.01
    return leido == val


def leer(obj, prop, por_defecto=None):
    if obj is None:
        return por_defecto
    try:
        return obj.get_editor_property(prop)
    except Exception:
        return por_defecto


def velocidad():
    p = pawn()
    if p is None:
        return None
    return leer(p.get_editor_property("character_movement"), "max_walk_speed")


def teleport(est):
    p = pawn()
    if p is None:
        return False
    x, y = PUESTO[est]
    return p.set_actor_location(unreal.Vector(x, y, Z_SUELO), False, True)


def coger(clase, x, y):
    """Recoge un item del nivel llamando a su Interact. No se spawnea nada: E1
    ya tiene botiquines, vendas y escudos, y usarlos es mas fiel al juego."""
    it = cerca_de(actores(clase), x, y, tol=400.0)
    p = pawn()
    if it is None or p is None:
        return None
    try:
        it.call_method("Interact", args=(p,))
        return it
    except Exception as e:
        nota("Interact fallo: %s" % e)
        return None


def silenciar_emisores():
    """Todos los emisores en manual: el banco dispara con FireOnce cuando toca.
    Con AutoFire puesto, un emisor vecino mete dano en mitad de otro caso."""
    n = 0
    for a in actores(P_DEALER):
        if poner(a, "AutoFire", False):
            n += 1
    return n


# ------------------------------------------------------------- pasos
def paso_preparar():
    """Fase 0, sin PIE: nivel correcto y variables editables por instancia."""
    BEL = unreal.BlueprintEditorLibrary
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        # Parar PIE es asincrono: el mundo de editor sigue siendo None en esta
        # misma llamada. El driver para PIE y espera ANTES de llamar aqui.
        les.editor_request_end_play()
        check("prep", "el editor no estaba en PIE", False,
              "se ha pedido parar; repite el paso preparar")
        return
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if w is None or w.get_name() != "Lvl_02_TestLab":
        les.load_level(MAPA)
    w = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    check("prep", "nivel Lvl_02_TestLab cargado", w and w.get_name() == "Lvl_02_TestLab",
          w.get_name() if w else "None")
    for ruta, nombres in EDITABLES.items():
        bp = unreal.EditorAssetLibrary.load_asset(ruta)
        if bp is None:
            check("prep", "existe " + ruta.rsplit("/", 1)[-1], False)
            continue
        for n in nombres:
            try:
                BEL.set_blueprint_variable_instance_editable(bp, n, True)
            except Exception as e:
                nota("editable %s.%s: %s" % (ruta.rsplit('/', 1)[-1], n, e))
        BEL.compile_blueprint(bp)
        unreal.EditorAssetLibrary.save_asset(ruta, only_if_is_dirty=False)
    # AutoFire se lee UNA SOLA VEZ en BeginPlay para arrancar un K2_SetTimer.
    # Ponerlo a false durante PIE no para el timer ya lanzado: por eso el dano
    # perdido contaminaba media tanda (se midio la vida cayendo de 100 a 10 en
    # el caso 6). Hay que apagarlo en el mundo de EDITOR, antes de arrancar.
    ss = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    apagados = 0
    for a in ss.get_all_level_actors():
        if a.get_class().get_name() == "BP_TestDamageDealer_C":
            try:
                a.set_editor_property("AutoFire", False)
                apagados += 1
            except Exception as e:
                nota("AutoFire en %s: %s" % (a.get_actor_label(), e))
    check("prep", "emisores en manual antes de PIE", apagados >= 8,
          "%d emisores" % apagados)

    hechas, total = 0, 0
    for ruta, nombres in EDITABLES.items():
        bp = unreal.EditorAssetLibrary.load_asset(ruta)
        for n in nombres:
            total += 1
            try:
                unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, n, True)
                hechas += 1
            except Exception:
                pass
    check("prep", "variables editables por instancia", hechas == total,
          "%d de %d" % (hechas, total))


def paso_pie_on():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.is_in_play_in_editor():
        les.editor_request_begin_play()
    print("   .. PIE arrancando")


def paso_pie_off():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
    print("   .. PIE parado")


def paso_base():
    """Mide la velocidad base en vez de suponerla: la plantilla Third Person
    anda a 600, no a 500 (LAB_DE_PRUEBAS.md seccion 14)."""
    p = pawn()
    check("base", "hay pawn en PIE", p is not None)
    if p is None:
        return
    n = silenciar_emisores()
    check("base", "emisores en manual (AutoFire=false)", n >= 8, "%d emisores" % n)
    v = velocidad()
    ST["v_base"] = float(v) if v else 600.0
    check("base", "velocidad base medida", v is not None, ST.get("v_base"))
    for ruta, etiqueta in ((P_CUR, "BPC_Curation"), (P_PRO, "BPC_ProtectionSystem"),
                           (P_HP, "BPC_HealthSystem"), (P_INV, "BPC_Inventary")):
        check("base", "el personaje tiene %s" % etiqueta, comp(ruta) is not None)


PASOS = {"preparar": paso_preparar, "pie_on": paso_pie_on,
         "pie_off": paso_pie_off, "base": paso_base}



# =====================================================================
# LOS 11 CASOS  (guion de LAB_DE_PRUEBAS.md seccion 9)
# =====================================================================
KIT = (-1700, -1050)
KIT2 = (-1550, -1050)
KIT3 = (-1400, -1050)
VENDA = (-1250, -1050)
ESCUDO = (-1700, -420)


def _hp():
    return comp(P_HP)


def _cur():
    return comp(P_CUR)


def _pro():
    return comp(P_PRO)


def _inv():
    return comp(P_INV)


def _vida():
    v = leer(_hp(), "Health")
    return -1.0 if v is None else float(v)


def _tiene_kit():
    o = leer(_inv(), "Object_Is_FirstAidKit")
    if o is None:
        return False
    if not unreal.SystemLibrary.is_valid(o):
        nota("C-3: el inventario conserva la referencia al botiquin destruido")
        return False
    return True


def _mirar_a(est):
    """Encara al emisor. El arco frontal es un producto escalar contra
    cos(FrontalArcDegrees/2): si el pawn no mira al emisor, el caso mide otra
    cosa."""
    p = pawn()
    if p is None:
        return
    ex, ey = EMISOR[est]
    px, py = PUESTO[est]
    rot = unreal.MathLibrary.find_look_at_rotation(
        unreal.Vector(px, py, Z_SUELO), unreal.Vector(ex, ey, 60.0))
    p.set_actor_rotation(rot, False)


def _colocar(est, vida=100.0, mirar=True):
    teleport(est)
    silenciar_emisores()
    if mirar:
        _mirar_a(est)
    poner(_hp(), "Health", float(vida))
    poner(_hp(), "IsDead", False)


def _disparo(est):
    e = emisor(est)
    if e is None:
        nota("no encuentro el emisor de %s" % est)
        return False
    try:
        e.call_method("FireOnce")
        return True
    except Exception as ex:
        nota("FireOnce %s: %s" % (est, ex))
        return False


# ---------------------------------------------------------- caso 1
def paso_c1_montar():
    _colocar("E1", 40.0, mirar=False)
    it = coger(P_KIT, KIT[0], KIT[1])
    check("caso 1 botiquin", "botiquin recogido del nivel", it is not None)


def paso_c1_lanzar():
    poner(_hp(), "Health", 40.0)          # las escrituras de PIE se revierten
    check("caso 1 botiquin", "vida a 40 antes de curar", abs(_vida() - 40.0) < 0.5, _vida())
    check("caso 1 botiquin", "el botiquin esta en el inventario", _tiene_kit())
    _cur().call_method("TryStartHeal")


def paso_c1_medio():
    check("caso 1 botiquin", "esta canalizando", leer(_cur(), "IsChanneling") is True)
    v = velocidad()
    check("caso 1 botiquin", "inmoviliza (MaxWalkSpeed = 0)", v is not None and v < 1.0, v)
    pr = leer(_cur(), "ChannelProgress", 0.0)
    check("caso 1 botiquin", "ChannelProgress avanza", pr > 0.0, pr)


def paso_c1_fin():
    check("caso 1 botiquin", "cura al 100 %", abs(_vida() - 100.0) < 0.5, _vida())
    check("caso 1 botiquin", "ya no canaliza", leer(_cur(), "IsChanneling") is False)
    check("caso 1 botiquin", "consume el botiquin", not _tiene_kit())
    v = velocidad()
    check("caso 1 botiquin", "devuelve la velocidad", v is not None and v > 1.0, v)


# ---------------------------------------------------------- caso 2
def paso_c2_montar():
    _colocar("E1", 100.0, mirar=False)
    coger(P_KIT, KIT2[0], KIT2[1])


def paso_c2_lanzar():
    poner(_hp(), "Health", 100.0)
    check("caso 2 vida llena", "vida llena y con botiquin",
          _tiene_kit() and _vida() >= 99.5, _vida())
    _cur().call_method("TryStartHeal")


def paso_c2_check():
    check("caso 2 vida llena", "no canaliza con la vida llena",
          leer(_cur(), "IsChanneling") is False)
    check("caso 2 vida llena", "NO consume el botiquin", _tiene_kit())


# ---------------------------------------------------------- caso 3
def paso_c3_montar():
    _colocar("E1", 40.0, mirar=False)
    poner(_inv(), "Object_Is_FirstAidKit", None)


def paso_c3_lanzar():
    poner(_hp(), "Health", 40.0)
    poner(_inv(), "Object_Is_FirstAidKit", None)
    check("caso 3 sin suministros", "inventario vacio", not _tiene_kit())
    _cur().call_method("TryStartHeal")


def paso_c3_check():
    check("caso 3 sin suministros", "no canaliza", leer(_cur(), "IsChanneling") is False)
    check("caso 3 sin suministros", "la vida no cambia", abs(_vida() - 40.0) < 0.5, _vida())


# ---------------------------------------------------------- caso 4
def paso_c4_montar():
    _colocar("E3", 40.0)
    it = coger(P_KIT, KIT3[0], KIT3[1])
    check("caso 4 interrupcion", "botiquin recogido", it is not None)
    e = emisor("E3")
    check("caso 4 interrupcion", "el emisor E3 fuerza interrupcion",
          leer(e, "ForceInterrupt") is True)


def paso_c4_lanzar():
    poner(_hp(), "Health", 40.0)
    _cur().call_method("TryStartHeal")


def paso_c4_golpe():
    check("caso 4 interrupcion", "estaba canalizando antes del golpe",
          leer(_cur(), "IsChanneling") is True)
    check("caso 4 interrupcion", "el emisor dispara", _disparo("E3"))


def paso_c4_check():
    check("caso 4 interrupcion", "la cura se corta", leer(_cur(), "IsChanneling") is False)
    check("caso 4 interrupcion", "CONSERVA el botiquin", _tiene_kit())
    v = velocidad()
    check("caso 4 interrupcion", "devuelve la velocidad", v is not None and v > 1.0, v)
    check("caso 4 interrupcion", "no llego a curar del todo", _vida() < 99.5, _vida())


# ---------------------------------------------------------- caso 5
def paso_c5_montar():
    _colocar("E1", 40.0, mirar=False)
    it = coger(P_BAND, VENDA[0], VENDA[1])
    ST["c5_hay_venda"] = it is not None
    if it is None:
        nota("caso 5 NO EJECUTADO: BP_Bandage no implementa Interact, "
             "asi que la venda no se puede recoger. Es el hallazgo C-2 de la "
             "auditoria del 2026-08-28, que sigue abierto.")
    check("caso 5 vendas", "venda recogida del nivel (requiere C-2)", it is not None)


def paso_c5_lanzar():
    if not ST.get("c5_hay_venda"):
        return
    poner(_hp(), "Health", 40.0)
    _cur().call_method("TryStartHeal")


def paso_c5_curado():
    if not ST.get("c5_hay_venda"):
        return
    v = _vida()
    ST["c5_curado"] = v
    check("caso 5 vendas", "cura el 20 % (40 -> 60)", abs(v - 60.0) < 1.5, v)
    check("caso 5 vendas", "el canal ha terminado (1.2 s)",
          leer(_cur(), "IsChanneling") is False)
    vel = velocidad()
    check("caso 5 vendas", "deja andar (velocidad > 0)", vel is not None and vel > 1.0, vel)


def paso_c5_decay():
    if not ST.get("c5_hay_venda"):
        return
    v = _vida()
    ST["c5_decay"] = v
    check("caso 5 vendas", "a los 10 s empieza a decaer",
          v < ST.get("c5_curado", 60.0) - 0.5, v)


def paso_c5_fin():
    if not ST.get("c5_hay_venda"):
        return
    v = _vida()
    check("caso 5 vendas", "no devuelve mas de lo que curo (no baja de 40)", v >= 39.5, v)
    check("caso 5 vendas", "nunca baja de 1 HP", v >= 1.0, v)


# ---------------------------------------------------------- caso 6
def paso_c6_montar():
    _colocar("E4", 100.0)
    it = coger(P_SHIELD, ESCUDO[0], ESCUDO[1])
    check("caso 6 durabilidad", "escudo recogido del nivel", it is not None)
    poner(_pro(), "ShieldDurability", 5)
    ST["c6_tiros"] = 0


def paso_c6_guardia():
    poner(_hp(), "Health", 100.0)
    poner(_pro(), "ShieldDurability", 5)
    _pro().call_method("StartGuard")


def paso_c6_verguardia():
    check("caso 6 durabilidad", "la guardia se levanta", leer(_pro(), "IsGuarding") is True)
    check("caso 6 durabilidad", "ShieldEquipped se deriva del inventario",
          leer(_pro(), "ShieldEquipped") is True)


def paso_c6_tiro():
    ST["c6_tiros"] = ST.get("c6_tiros", 0) + 1
    _disparo("E4")


def paso_c6_check():
    d = leer(_pro(), "ShieldDurability")
    check("caso 6 durabilidad", "5 impactos dejan la durabilidad a 0", d == 0, d)
    check("caso 6 durabilidad", "el escudo se rompe (guardia abajo)",
          leer(_pro(), "IsGuarding") is False)
    check("caso 6 durabilidad", "la vida queda intacta", abs(_vida() - 100.0) < 0.5, _vida())


# ---------------------------------------------------------- caso 7
def paso_c7_montar():
    _colocar("E5", 100.0, mirar=False)
    coger(P_SHIELD, -1550, -420)
    poner(_pro(), "ShieldDurability", 5)
    p = pawn()
    if p:   # de espaldas al emisor, que esta al norte
        p.set_actor_rotation(unreal.Rotator(0.0, -90.0, 0.0), False)


def paso_c7_guardia():
    poner(_hp(), "Health", 100.0)
    poner(_pro(), "ShieldDurability", 5)
    _pro().call_method("StartGuard")


def paso_c7_golpe():
    ST["c7_dur"] = leer(_pro(), "ShieldDurability")
    _disparo("E5")


def paso_c7_check():
    v = _vida()
    check("caso 7 arco frontal", "por la espalda entra el dano integro (10)",
          abs(v - 90.0) < 1.5, v)
    d = leer(_pro(), "ShieldDurability")
    check("caso 7 arco frontal", "no gasta durabilidad", d == ST.get("c7_dur"), d)


# ---------------------------------------------------------- caso 8
def paso_c8_montar():
    _colocar("E6", 100.0)
    coger(P_SHIELD, -1700, -420)
    poner(_pro(), "ShieldDurability", 5)


def paso_c8_parry():
    """StartGuard y FireOnce en la MISMA llamada: call_method es sincrono, asi
    que la ventana de parry (0.35 s) se cumple con margen. Separarlos en dos
    pasos remotos la deja pasar."""
    poner(_hp(), "Health", 100.0)
    poner(_pro(), "ShieldDurability", 5)
    _pro().call_method("StartGuard")
    _disparo("E6")


def paso_c8_check():
    v = _vida()
    check("caso 8 parry", "0 de dano", abs(v - 100.0) < 0.5, v)
    d = leer(_pro(), "ShieldDurability")
    check("caso 8 parry", "durabilidad intacta (5)", d == 5, d)
    r = leer(_pro(), "LastBlockResult")
    check("caso 8 parry", "LastBlockResult = Parried", "PARRIED" in str(r).upper(), r)


# ---------------------------------------------------------- caso 9
def paso_c9_montar():
    _colocar("E7", 100.0)
    coger(P_SHIELD, -1550, -420)
    poner(_pro(), "ShieldDurability", 5)
    e = emisor("E7")
    check("caso 9 no bloqueable", "el emisor E7 no es bloqueable",
          leer(e, "DamageCanBeBlocked") is False)


def paso_c9_golpe():
    poner(_hp(), "Health", 100.0)
    poner(_pro(), "ShieldDurability", 5)
    _pro().call_method("StartGuard")
    _disparo("E7")


def paso_c9_check():
    v = _vida()
    check("caso 9 no bloqueable", "entran los 15 con la guardia arriba",
          abs(v - 85.0) < 1.5, v)


# ---------------------------------------------------------- caso 10
def paso_c10_montar():
    _colocar("E8", 100.0)
    # Baja la guardia: el caso 9 la deja levantada y el escudo se comia los 20,
    # de modo que la cobertura no se estaba midiendo (la vida quedaba en 100).
    _pro().call_method("StopGuard")
    p = pawn()
    try:
        # La bandera no esta en el CharacterMovementComponent sino en su
        # struct NavAgentProps, y hay que reasignar el struct entero.
        cmc = p.get_editor_property("character_movement")
        nav = cmc.get_editor_property("nav_agent_props")
        nav.set_editor_property("can_crouch", True)
        cmc.set_editor_property("nav_agent_props", nav)
    except Exception as e:
        nota("can_crouch: %s" % e)
    try:
        p.crouch()
    except Exception as e:
        nota("Crouch: %s" % e)


def paso_c10_golpe():
    poner(_hp(), "Health", 100.0)
    ag = leer(pawn(), "is_crouched")
    check("caso 10 cobertura", "el jugador esta agachado", ag is True, ag)
    _disparo("E8")


def paso_c10_check():
    v = _vida()
    check("caso 10 cobertura", "20 de dano se quedan en 13 (-35 %)",
          abs(v - 87.0) < 1.5, v)


# ---------------------------------------------------------- caso 11
def paso_c11_montar():
    _colocar("E9", 100.0)
    coger(P_SHIELD, -1550, -420)
    poner(_pro(), "ShieldDurability", 5)
    e = emisor("E9")
    poner(e, "Health", 100.0)
    check("caso 11 reflejo", "ReflectOnAbsorb activo",
          leer(_pro(), "ReflectOnAbsorb") is True)


def paso_c11_golpe():
    poner(_hp(), "Health", 100.0)
    poner(_pro(), "ShieldDurability", 5)
    e = emisor("E9")
    poner(e, "Health", 100.0)
    _pro().call_method("StartGuard")
    _disparo("E9")


def paso_c11_check():
    e = emisor("E9")
    ve = leer(e, "Health")
    check("caso 11 reflejo", "el emisor baja de 100 a 90", ve is not None and abs(ve - 90.0) < 1.5, ve)
    check("caso 11 reflejo", "el jugador no recibe dano", abs(_vida() - 100.0) < 0.5, _vida())
    d = leer(_pro(), "ShieldDurability")
    check("caso 11 reflejo", "sin ping-pong: el reflejo no es bloqueable", d in (4, 5), d)


for _n, _f in list(globals().items()):
    if _n.startswith("paso_c") and callable(_f):
        PASOS[_n[5:]] = _f


def paso_informe():
    ok = sum(1 for c in ST["checks"] if c["ok"])
    fallos = [c for c in ST["checks"] if not c["ok"]]
    ruta = os.path.join(SAVED, "LabTest_Report.txt")
    L = ["=" * 70,
         " BANCO DE PRUEBAS DE CURACION Y PROTECCION - Lvl_02_TestLab",
         " %d comprobaciones, %d OK, %d fallos" % (len(ST["checks"]), ok, len(fallos)),
         "=" * 70, ""]
    caso = None
    for c in ST["checks"]:
        if c["caso"] != caso:
            caso = c["caso"]
            L.append("")
            L.append("-- %s" % caso)
        L.append("   %-6s %s%s" % ("OK" if c["ok"] else "FALLO", c["texto"],
                                   ("  -> " + c["detalle"]) if c["detalle"] else ""))
    if ST.get("notas"):
        L += ["", "-- notas"] + ["   " + n for n in ST["notas"]]
    L += ["", "=" * 70, "FALLOS: %d" % len(fallos)]
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L[-3:]))
    print("   informe -> " + ruta)


PASOS["informe"] = paso_informe


def paso_reset():
    if os.path.isfile(ESTADO):
        os.remove(ESTADO)
    print("   .. estado limpio")


PASOS["reset"] = paso_reset

# ------------------------------------------------------------- ejecucion
with open(PASO_TXT, encoding="utf-8") as f:
    _paso = f.read().strip()

print("[paso] %s" % _paso)
if _paso not in PASOS:
    print("   FALLO  paso desconocido: %s" % _paso)
else:
    # Silenciar no se sostiene: la escritura de AutoFire se revierte sola y el
    # emisor vuelve a disparar en mitad del caso siguiente (se midio la vida
    # bajando de 40 a 10 durante el caso 1). Se re-aplica en cada paso.
    if _paso.startswith("c") and pawn() is not None:
        silenciar_emisores()
    try:
        PASOS[_paso]()
    except Exception as _err:
        import traceback
        traceback.print_exc()
        check(_paso, "el paso no reventó", False, str(_err))
    if _paso != "reset":
        guardar(ST)
