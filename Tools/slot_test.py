# -*- coding: utf-8 -*-
"""Un paso del banco de visibilidad de slots. Lo conduce test_slot_visibility.py;
el paso llega por Tools/_slot_paso.txt porque ue_remote no pasa argumentos."""
import os

import unreal

UES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
_dir = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_dir, "_slot_paso.txt"), encoding="utf-8") as fh:
        paso = fh.read().strip()
except Exception:
    paso = "leer"

REFS = ["Object_Is_Weapon", "Object_Is_Throwable",
        "Object_Is_Shield", "Object_Is_FirstAidKit"]


def pawn():
    w = UES.get_game_world()
    if w is None:
        return None
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        if a.get_class().get_name() == "BP_ThirdPersonCharacter_C":
            return a
    return None


if paso == "exponer":
    # ValueOptionInventary no es editable por instancia, asi que Python no
    # puede escribirla en PIE ("cannot be edited on instances"). Se expone
    # antes de arrancar, como hace lab_test.py, y se restaura al acabar.
    bp = unreal.EditorAssetLibrary.load_asset(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter")
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(
        bp, "ValueOptionInventary", True)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    inv = unreal.EditorAssetLibrary.load_asset(
        "/Game/ThirdPerson/Components/BPC_Inventary")
    for r in REFS:
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(
            inv, r, True)
    unreal.BlueprintEditorLibrary.compile_blueprint(inv)
    print("ValueOptionInventary y las 4 refs del inventario expuestas")

elif paso == "restaurar":
    bp = unreal.EditorAssetLibrary.load_asset(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter")
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(
        bp, "ValueOptionInventary", False)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    unreal.EditorAssetLibrary.save_asset(
        "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter")
    inv = unreal.EditorAssetLibrary.load_asset(
        "/Game/ThirdPerson/Components/BPC_Inventary")
    for r in REFS:
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(
            inv, r, False)
    unreal.BlueprintEditorLibrary.compile_blueprint(inv)
    unreal.EditorAssetLibrary.save_asset(
        "/Game/ThirdPerson/Components/BPC_Inventary")
    print("variables restauradas y assets guardados")

elif paso == "arrancar":
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
    print("PIE solicitado")

elif paso == "parar":
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
    print("PIE detenido")

elif paso == "equipar":
    p = pawn()
    w = UES.get_game_world()
    if p is None or w is None:
        print("FALLO: no hay pawn del jugador (PIE no esta corriendo)")
        raise SystemExit
    arma = None
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        if a.get_class().get_name() == "BP_ConventionalGun_C":
            arma = a
            break
    if arma is None:
        print("FALLO: no hay ningun BP_ConventionalGun_C en el nivel")
        raise SystemExit
    inv = p.get_editor_property("BPC_Inventary")
    for _ in range(5):
        inv.set_editor_property("Object_Is_Weapon", arma)
        if inv.get_editor_property("Object_Is_Weapon") == arma:
            break
    puesto = inv.get_editor_property("Object_Is_Weapon")
    print("equipado Object_Is_Weapon = %s"
          % ("None" if puesto is None else puesto.get_name()))

elif paso.startswith("slot"):
    # Todo en UNA llamada remota: escribir, llamar y leer. Las escrituras a
    # instancias de PIE se revierten entre llamadas (LAB_DE_PRUEBAS seccion 15,
    # trampa 3), asi que leer el resultado en la llamada siguiente daba
    # siempre el valor viejo.
    p = pawn()
    if p is None:
        print("FALLO: no hay pawn del jugador (PIE no esta corriendo)")
        raise SystemExit
    n = int(paso[4:])
    for _ in range(5):
        p.set_editor_property("ValueOptionInventary", n)
        if p.get_editor_property("ValueOptionInventary") == n:
            break
    puesto = p.get_editor_property("ValueOptionInventary")
    inv = p.get_editor_property("BPC_Inventary")
    refs = {r: (inv.get_editor_property(r) if inv else None) for r in REFS}
    p.call_method("Ev_ActualizarEquipo")
    arma = refs["Object_Is_Weapon"]
    try:
        oculta = "?" if arma is None else arma.get_editor_property("hidden")
    except Exception:
        oculta = "?"
    print("SLOT=%d(pedido %d) ARMA_OCULTA=%s HaveGun=%s HaveGrenade=%s | %s"
          % (puesto, n, oculta,
             p.get_editor_property("HaveGun"),
             p.get_editor_property("HaveGrenade"),
             "  ".join("%s=%s" % (r, "None" if v is None else v.get_name())
                       for r, v in refs.items())))

elif paso == "leer":
    p = pawn()
    if p is None:
        print("FALLO: no hay pawn del jugador (PIE no esta corriendo)")
        raise SystemExit
    inv = p.get_editor_property("BPC_Inventary")
    estado = []
    for r in REFS:
        it = inv.get_editor_property(r) if inv else None
        if it is None:
            estado.append("%s=None" % r)
        else:
            try:
                oculto = it.get_editor_property("hidden")
            except Exception:
                oculto = "?"
            estado.append("%s=%s(oculto=%s)" % (r, it.get_name(), oculto))
    print("SLOT=%d HaveGun=%s HaveGrenade=%s | %s"
          % (p.get_editor_property("ValueOptionInventary"),
             p.get_editor_property("HaveGun"),
             p.get_editor_property("HaveGrenade"),
             "  ".join(estado)))
