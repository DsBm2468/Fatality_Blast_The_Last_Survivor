# -*- coding: utf-8 -*-
"""
Ejecuta UN paso del banco de inventario / soltar / lanzar, dentro del editor.

No se llama a mano: lo conduce Tools/run_item_tests.py, que escribe el nombre
del paso en Tools/_paso_item.txt y lanza este fichero por Remote Execution.

POR QUE UN PASO POR LLAMADA: escribir, invocar y leer en la misma llamada
devuelve el valor viejo, porque el Blueprint corre en el frame siguiente y la
llamada remota no cede el hilo. La excepcion util es la logica SINCRONA: si un
evento no tiene nodos latentes (Delay, temporizadores), call_method vuelve con
el trabajo hecho y se puede leer el resultado acto seguido. La deteccion de la
explosion es de esas, y por eso se mide en un solo paso.
"""
import json
import os

import unreal

G = "/Game/ThirdPerson"
P_ITEM = G + "/Blueprints/Interactables/FixedInteractables/BP_Item.BP_Item_C"
P_GUN = (G + "/Blueprints/Interactables/FixedInteractables/"
         "BP_WB_ConventionalGun.BP_WB_ConventionalGun_C")
P_GRANADA = (G + "/Blueprints/Interactables/FixedInteractables/"
             "BP_Item_ThrowB_Grenade.BP_Item_ThrowB_Grenade_C")
P_INTER = G + "/Components/BPC_Interaction.BPC_Interaction_C"
P_INV = G + "/Components/BPC_Inventary.BPC_Inventary_C"
MAPA = G + "/Lvl_02_TestLab"

SAVED = unreal.Paths.project_saved_dir()
ESTADO = os.path.join(SAVED, "_item_state.json")
PASO_TXT = os.path.join(unreal.Paths.project_dir(), "Tools", "_paso_item.txt")

# Sitio despejado del suelo del laboratorio (va de y=-2000 a y=+2800; las
# estaciones estan en y=-800, 600 y 2000, asi que y=-1500 esta libre).
POS_GUN = (0.0, -1500.0, 120.0)
POS_GRANADA = (350.0, -1500.0, 120.0)
POS_BOMBA_TEST = (1400.0, -1500.0, 120.0)   # granada solo para la explosion
POS_LEJOS = (-1800.0, 2600.0, 120.0)
ETIQUETA = "TEST_ITEM_"

# Los nombres reales de los campos del struct, con su GUID: es como los expone
# la reflexion.
F_CANT = "QuantityOfItems_14_A2D5A7E347FE828C140D7A8803F2F6FA"
F_CLASE = "ItemClass_17_525F5B33449D92EF0134CBB90F9F2E2A"
F_TIPO = "ItemType_9_421CEC67424D1B7E30935DA04CE12B1E"


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
    print("   %-5s [%s] %s%s" % ("OK" if cond else "FALLO", caso, texto,
                                 ("  -> " + str(detalle)) if detalle else ""))
    return bool(cond)


def nota(t):
    ST["notas"].append(t)
    print("   .. " + t)


# ------------------------------------------------------------- mundo
def gw():
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
    return unreal.GameplayStatics.get_all_actors_of_class(
        w, unreal.load_class(None, ruta))


def uno(ruta):
    lista = actores(ruta)
    return lista[0] if lista else None


def mover_pawn(x, y, z=120.0):
    p = pawn()
    if p is None:
        return False
    p.set_actor_location(unreal.Vector(x, y, z), False, True)
    return True


def hueco(indice):
    """Devuelve (cantidad, clase_del_item) del hueco pedido, o (None, None)."""
    c = comp(P_INV)
    if c is None:
        return None, None
    try:
        lista = c.get_editor_property("InventoryItems")
    except Exception as e:
        nota("no se puede leer InventoryItems: %s" % e)
        return None, None
    if indice >= len(lista):
        return None, None
    s = lista[indice]
    try:
        return (s.get_editor_property(F_CANT), s.get_editor_property(F_CLASE))
    except Exception:
        # por si la reflexion expone los nombres amigables
        try:
            return (s.get_editor_property("QuantityOfItems"),
                    s.get_editor_property("ItemClass"))
        except Exception as e:
            nota("no se pueden leer los campos del struct: %s" % e)
            return None, None


# --- HUD -------------------------------------------------------------
# (indice del hueco, SizeBox de la casilla, Image del icono). Los nombres son
# los del arbol de WBP_HUB_Inventary.
HUD = [(0, "Arm", "IMG-ConvencionalGun"),
       (1, "Throwable", "IMG-Grenade"),
       (2, "Shield", "IMG-BulletproofShield"),
       (3, "FirstAidKit", "IMG-FirstAidKit")]


def hud():
    """El widget de inventario que tiene el jugador, o None."""
    p = pawn()
    if p is None:
        return None
    try:
        return p.get_editor_property("WBP HUB inventary")
    except Exception:
        return None


def icono_visible(indice):
    """True si el icono de ese hueco esta encendido en el HUD."""
    w = hud()
    if w is None:
        return None
    _, _, img = HUD[indice]
    try:
        v = w.get_editor_property(img).get_editor_property("visibility")
    except Exception as e:
        nota("no se puede leer la visibilidad de %s: %s" % (img, e))
        return None
    return "HIDDEN" not in str(v).upper() and "COLLAPSED" not in str(v).upper()


def opacidad_hueco(indice):
    w = hud()
    if w is None:
        return None
    _, caja, _ = HUD[indice]
    try:
        return round(w.get_editor_property(caja).get_editor_property("render_opacity"), 2)
    except Exception:
        return None


def equipado():
    c = comp(P_INTER)
    if c is None:
        return None
    try:
        return c.get_editor_property("EquippedItem")
    except Exception:
        return None


def en_rango():
    c = comp(P_INTER)
    if c is None:
        return []
    try:
        return list(c.get_editor_property("InteractablesInRange"))
    except Exception:
        return []


# =====================================================================
# fase 0
# =====================================================================
def paso_reset():
    if os.path.isfile(ESTADO):
        os.remove(ESTADO)
    globals()["ST"] = {"checks": [], "notas": []}
    print("   .. estado limpio")


def paso_pie_off():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
    print("   .. PIE parado")


def paso_pie_on():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not les.is_in_play_in_editor():
        les.editor_request_begin_play()
    print("   .. PIE arrancando")


def paso_preparar():
    """Sin PIE: carga el nivel y siembra los items de prueba en el mundo de
    EDITOR, que es lo que PIE copia al arrancar. No se pueden spawnear dentro
    de PIE: spawn_actor_from_class trabaja contra el mundo del editor."""
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if les.is_in_play_in_editor():
        les.editor_request_end_play()
        check("prep", "el editor no estaba en PIE", False,
              "se ha pedido parar; repite el paso preparar")
        return
    w = ues.get_editor_world()
    if w is None or w.get_name() != "Lvl_02_TestLab":
        les.load_level(MAPA)
        w = ues.get_editor_world()
    check("prep", "nivel Lvl_02_TestLab cargado",
          w is not None and w.get_name() == "Lvl_02_TestLab",
          w.get_name() if w else "None")

    # fuera los de la tanda anterior
    borrados = 0
    for a in eas.get_all_level_actors():
        try:
            if a.get_actor_label().startswith(ETIQUETA):
                eas.destroy_actor(a)
                borrados += 1
        except Exception:
            pass
    nota("%d actores de prueba anteriores borrados" % borrados)

    def sembrar(ruta, pos, etiqueta):
        cl = unreal.load_class(None, ruta)
        if cl is None:
            check("prep", "existe la clase " + ruta.rsplit(".")[-1], False)
            return None
        a = eas.spawn_actor_from_class(cl, unreal.Vector(*pos))
        if a is not None:
            a.set_actor_label(ETIQUETA + etiqueta)
        return a

    g = sembrar(P_GUN, POS_GUN, "GUN")
    n = sembrar(P_GRANADA, POS_GRANADA, "GRANADA")
    x = sembrar(P_GRANADA, POS_BOMBA_TEST, "EXPLOSION")
    check("prep", "arma sembrada", g is not None)
    check("prep", "granada sembrada", n is not None)
    check("prep", "granada de explosion sembrada", x is not None)

    # tres peones alrededor de la granada de explosion, dentro de su radio
    # (ExplosionRange = 150): son el objeto de la prueba de alcance multiple
    px, py, pz = POS_BOMBA_TEST
    puestos = [(px + 80, py, pz), (px - 80, py, pz), (px, py + 80, pz)]
    n_peones = 0
    for i, p in enumerate(puestos):
        a = eas.spawn_actor_from_class(unreal.Character, unreal.Vector(*p))
        if a is not None:
            a.set_actor_label(ETIQUETA + "PEON_%d" % i)
            n_peones += 1
    check("prep", "tres peones alrededor de la granada", n_peones == 3,
          "%d peones" % n_peones)


def paso_base():
    p = pawn()
    check("base", "hay pawn en PIE", p is not None)
    check("base", "el pawn tiene BPC_Interaction", comp(P_INTER) is not None)
    check("base", "el pawn tiene BPC_Inventary", comp(P_INV) is not None)
    c = comp(P_INV)
    if c is not None:
        try:
            lista = c.get_editor_property("InventoryItems")
            check("base", "el inventario tiene 4 huecos", len(lista) == 4,
                  "%d huecos" % len(lista))
        except Exception as e:
            check("base", "se puede leer InventoryItems", False, e)
    check("base", "hay armas de prueba en el nivel", len(actores(P_GUN)) >= 1,
          "%d" % len(actores(P_GUN)))
    check("base", "hay granadas de prueba en el nivel",
          len(actores(P_GRANADA)) >= 2, "%d" % len(actores(P_GRANADA)))
    # El HUD: con el inventario vacio no puede haber ningun icono encendido.
    # Es justo lo que fallaba el 2026-09-15: las cuatro casillas se veian pero
    # las imagenes estaban SIEMPRE en HIDDEN, y nada las encendia nunca.
    check("base", "el jugador tiene el widget de inventario", hud() is not None)
    encendidos = [i for i in range(4) if icono_visible(i)]
    check("base", "con el inventario vacio no hay ningun icono encendido",
          encendidos == [], "encendidos: %s" % encendidos)


# =====================================================================
# caso 1: recoger un arma -> se equipa y entra en el inventario
# =====================================================================
def _mas_cerca(ruta, x, y):
    mejor, dmin = None, 1e9
    for a in actores(ruta):
        l = a.get_actor_location()
        d = ((l.x - x) ** 2 + (l.y - y) ** 2) ** 0.5
        if d < dmin:
            mejor, dmin = a, d
    return mejor


def paso_c1_acercar():
    check("c1", "el jugador se mueve junto al arma",
          mover_pawn(POS_GUN[0] + 90, POS_GUN[1]))


def paso_c1_recoger():
    arma = _mas_cerca(P_GUN, POS_GUN[0], POS_GUN[1])
    p = pawn()
    if arma is None or p is None:
        check("c1", "hay arma y jugador", False)
        return
    ST["arma"] = arma.get_path_name()
    guardar(ST)
    try:
        arma.call_method("Interact", (p,))
        nota("Interact llamado sobre el arma")
    except Exception as e:
        check("c1", "se puede invocar Interact", False, e)


def paso_c1_check():
    arma = _mas_cerca(P_GUN, POS_GUN[0], POS_GUN[1])
    eq = equipado()
    check("c1", "EquippedItem apunta al arma",
          eq is not None and arma is not None
          and eq.get_path_name() == arma.get_path_name(),
          "EquippedItem=%s" % (eq.get_name() if eq else "None"))
    cant, clase = hueco(0)
    check("c1", "el hueco 0 (arma) queda ocupado", cant is not None and cant > 0,
          "cantidad=%s" % cant)
    check("c1", "el hueco 0 guarda el arma recogida",
          clase is not None and arma is not None
          and clase.get_path_name() == arma.get_path_name(),
          "clase=%s" % (clase.get_name() if clase else "None"))
    if arma is not None:
        padre = arma.get_attach_parent_actor()
        check("c1", "el arma queda enganchada al jugador",
              padre is not None and pawn() is not None
              and padre.get_path_name() == pawn().get_path_name(),
              "padre=%s" % (padre.get_name() if padre else "None"))
    check("c1", "el arma sale de la lista de interactuables",
          arma is not None and arma not in en_rango(),
          "%d en rango" % len(en_rango()))
    check("c1", "el HUD enciende el icono del hueco del arma",
          icono_visible(0) is True)
    check("c1", "y NO enciende los otros tres",
          [i for i in (1, 2, 3) if icono_visible(i)] == [],
          "encendidos: %s" % [i for i in (1, 2, 3) if icono_visible(i)])
    check("c1", "el hueco seleccionado se resalta y los demas se atenuan",
          opacidad_hueco(0) == 1.0 and opacidad_hueco(1) < 1.0,
          "opacidades: %s" % [opacidad_hueco(i) for i in range(4)])


# =====================================================================
# caso 2: soltar
# =====================================================================
def paso_c2_soltar():
    """Llama al MISMO evento que llama la tecla F.

    No se pulsa F de verdad porque la entrada inyectada no llega al viewport
    de PIE: se probo con keybd_event y con SendInput (scancode), con la
    ventana enfocada y el raton capturado por el juego, y ni el movimiento
    (W) ni la pausa (P) surtian efecto. Que F esta atada a este evento se
    comprueba aparte, leyendo el grafo y el mapeo de entrada
    (Tools/check_drop_binding.py), que es verificable sin jugar.
    """
    c = comp(P_INTER)
    if c is None:
        check("c2", "hay BPC_Interaction", False)
        return
    try:
        c.call_method("Ev_SoltarEquipado", ())
        nota("Ev_SoltarEquipado llamado")
    except Exception as e:
        check("c2", "se puede invocar Ev_SoltarEquipado", False, e)


def paso_c2_check():
    arma = _mas_cerca(P_GUN, POS_GUN[0], POS_GUN[1])
    eq = equipado()
    check("c2", "EquippedItem queda libre tras soltar", eq is None,
          "EquippedItem=%s" % (eq.get_name() if eq else "None"))
    cant, clase = hueco(0)
    check("c2", "el hueco 0 queda vacio", cant == 0, "cantidad=%s" % cant)
    if arma is not None:
        padre = arma.get_attach_parent_actor()
        check("c2", "el arma ya no cuelga del jugador", padre is None,
              "padre=%s" % (padre.get_name() if padre else "None"))
        check("c2", "el arma vuelve a estar en rango", arma in en_rango(),
              "%d en rango" % len(en_rango()))
    check("c2", "el HUD apaga el icono al soltar", icono_visible(0) is False)


# =====================================================================
# caso 3: recoger una granada -> hueco 1
# =====================================================================
def paso_c3_acercar():
    check("c3", "el jugador se mueve junto a la granada",
          mover_pawn(POS_GRANADA[0] + 90, POS_GRANADA[1]))


def paso_c3_recoger():
    gr = _mas_cerca(P_GRANADA, POS_GRANADA[0], POS_GRANADA[1])
    p = pawn()
    if gr is None or p is None:
        check("c3", "hay granada y jugador", False)
        return
    try:
        gr.call_method("Interact", (p,))
        nota("Interact llamado sobre la granada")
    except Exception as e:
        check("c3", "se puede invocar Interact", False, e)


def paso_c3_check():
    gr = _mas_cerca(P_GRANADA, POS_GRANADA[0], POS_GRANADA[1])
    eq = equipado()
    check("c3", "EquippedItem apunta a la granada",
          eq is not None and gr is not None
          and eq.get_path_name() == gr.get_path_name(),
          "EquippedItem=%s" % (eq.get_name() if eq else "None"))
    cant, clase = hueco(1)
    check("c3", "el hueco 1 (lanzable) queda ocupado",
          cant is not None and cant > 0, "cantidad=%s" % cant)
    cant0, _ = hueco(0)
    check("c3", "el hueco 0 sigue vacio: cada categoria va a su hueco",
          cant0 == 0, "cantidad hueco 0=%s" % cant0)
    check("c3", "el HUD enciende el icono del lanzable", icono_visible(1) is True)
    check("c3", "y el del arma sigue apagado", icono_visible(0) is False)


# =====================================================================
# caso 4: lanzar
# =====================================================================
def paso_c4_lanzar():
    gr = _mas_cerca(P_GRANADA, POS_GRANADA[0], POS_GRANADA[1])
    if gr is None:
        check("c4", "hay granada equipada", False)
        return
    ST["granada"] = gr.get_path_name()
    guardar(ST)
    # lanzar exige apuntar: es la condicion RequirePointing AND IsPointing
    try:
        gr.call_method("SetPointingState", (True,))
    except Exception as e:
        nota("SetPointingState fallo: %s" % e)
    try:
        gr.call_method("UseItem", ())
        nota("UseItem llamado sobre la granada")
    except Exception as e:
        check("c4", "se puede invocar UseItem", False, e)


def paso_c4_check():
    ruta = ST.get("granada")
    gr = None
    for a in actores(P_GRANADA):
        if a.get_path_name() == ruta:
            gr = a
    check("c4", "la granada lanzada sigue viva (aun no ha explotado)",
          gr is not None)
    if gr is not None:
        padre = gr.get_attach_parent_actor()
        check("c4", "la granada se desengancha de la mano", padre is None,
              "padre=%s" % (padre.get_name() if padre else "None"))
    eq = equipado()
    check("c4", "EquippedItem queda libre tras lanzar", eq is None,
          "EquippedItem=%s" % (eq.get_name() if eq else "None"))
    cant, _ = hueco(1)
    check("c4", "el hueco 1 queda vacio tras lanzar", cant == 0,
          "cantidad=%s" % cant)
    check("c4", "el HUD apaga el icono del lanzable", icono_visible(1) is False)


# =====================================================================
# caso 5: la explosion alcanza a TODOS los del radio, no a uno
# =====================================================================
def paso_c5_explotar():
    """ReactionOfItem no tiene nodos latentes antes de llenar DetectedActors,
    asi que call_method vuelve con la lista ya hecha y se puede leer aqui
    mismo. El Delay de 0.2 s y el DestroyActor van despues."""
    gr = _mas_cerca(P_GRANADA, POS_BOMBA_TEST[0], POS_BOMBA_TEST[1])
    if gr is None:
        check("c5", "hay granada para la explosion", False)
        return
    try:
        antes = list(gr.get_editor_property("DetectedActors"))
    except Exception as e:
        check("c5", "se puede leer DetectedActors", False, e)
        return
    check("c5", "DetectedActors empieza vacia", len(antes) == 0,
          "%d" % len(antes))
    try:
        gr.call_method("ReactionOfItem", ())
    except Exception as e:
        check("c5", "se puede invocar ReactionOfItem", False, e)
        return
    detectados = list(gr.get_editor_property("DetectedActors"))
    nombres = ", ".join(a.get_name() for a in detectados if a)
    check("c5", "la explosion alcanza a los tres peones, no a uno solo",
          len(detectados) >= 3, "%d detectados: %s" % (len(detectados), nombres))


# =====================================================================
# caso 6: salir del radio quita el item de la lista de interactuables
# =====================================================================
def paso_c6_acercar():
    check("c6", "el jugador vuelve junto al arma",
          mover_pawn(POS_GUN[0] + 90, POS_GUN[1]))


def paso_c6_dentro():
    arma = _mas_cerca(P_GUN, POS_GUN[0], POS_GUN[1])
    lista = en_rango()
    check("c6", "el arma esta en rango al acercarse",
          arma is not None and arma in lista, "%d en rango" % len(lista))
    veces = sum(1 for a in lista if arma is not None and a == arma)
    check("c6", "y solo aparece UNA vez (Array_AddUnique)", veces <= 1,
          "%d veces" % veces)


def paso_c6_alejar():
    check("c6", "el jugador se va lejos", mover_pawn(*POS_LEJOS))


def paso_c6_fuera():
    arma = _mas_cerca(P_GUN, POS_GUN[0], POS_GUN[1])
    lista = en_rango()
    check("c6", "al alejarse, el arma deja de estar en rango (End Overlap)",
          arma is not None and arma not in lista, "%d en rango" % len(lista))


# =====================================================================
PASOS = {
    "reset": paso_reset, "pie_off": paso_pie_off, "pie_on": paso_pie_on,
    "preparar": paso_preparar, "base": paso_base,
    "c1_acercar": paso_c1_acercar, "c1_recoger": paso_c1_recoger,
    "c1_check": paso_c1_check,
    "c2_soltar": paso_c2_soltar, "c2_check": paso_c2_check,
    "c3_acercar": paso_c3_acercar, "c3_recoger": paso_c3_recoger,
    "c3_check": paso_c3_check,
    "c4_lanzar": paso_c4_lanzar, "c4_check": paso_c4_check,
    "c5_explotar": paso_c5_explotar,
    "c6_acercar": paso_c6_acercar, "c6_dentro": paso_c6_dentro,
    "c6_alejar": paso_c6_alejar, "c6_fuera": paso_c6_fuera,
}

with open(PASO_TXT, encoding="utf-8") as f:
    PASO = f.read().strip()

if PASO not in PASOS:
    print("PASO DESCONOCIDO: %r" % PASO)
else:
    print(">> %s" % PASO)
    PASOS[PASO]()
    guardar(ST)
