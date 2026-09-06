# -*- coding: utf-8 -*-
"""
Quita el grafo de FUNCION 'Interact' de los items interactuables.

Contexto (2026-08-31): BPI_Interactable.Interact tenia una salida (Item), asi
que era una FUNCION de interfaz, y una funcion de interfaz con salida NO se
puede implementar como evento. Los cuatro items la tenian implementada como
evento, asi que el compilador los degrado:

    'Interact' se promovio a partir de un evento a una funcion; se reemplazo
    por un evento personalizado, que no se activara a menos que lo llame
    manualmente.

Resultado: la funcion 'Interact' quedo VACIA -y es la que se ejecuta-, y toda
la logica de recoger quedo colgando de un CustomEvent 'Interact_1' sin pines
que nadie llama. Sintoma: ves el objeto, sale OBJETO DETECTADO, y E no hace
nada.

Ya se quito la salida Item de la interfaz. Falta borrar el grafo de funcion
que la sombrea; luego, a mano, un nodo 'Event Interact' en cada EventGraph.

    python Tools/ue_remote.py Tools/fix_interact_event.py
"""
import unreal

BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
ITEMS = [
    "/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_FirstAidKit",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_Grenade",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_Shield",
]
problemas = []
for p in ITEMS:
    bp = EAL.load_asset(p)
    nombre = p.rsplit("/", 1)[-1]
    if BEL.find_graph(bp, "Interact") is not None:
        BEL.remove_function_graph(bp, "Interact")
        BEL.compile_blueprint(bp)
    fuera = BEL.find_graph(bp, "Interact") is None
    guardado = EAL.save_asset(p, only_if_is_dirty=False)
    print("  %-22s funcion Interact fuera=%-5s guardado=%s" % (nombre, fuera, guardado))
    if not (fuera and guardado):
        problemas.append(nombre)
print("")
print("PROBLEMAS: %d %s" % (len(problemas), problemas or ""))
