# -*- coding: utf-8 -*-
"""BP_Item no compila: su grafo Interact conserva un nodo de retorno con el pin
'Item', salida que se elimino de BPI_Interactable.Interact el 2026-08-31.
refresh_all_nodes() reconstruye los nodos contra la firma actual de la interfaz
y deberia tirar el pin muerto."""
import unreal
BEL = unreal.BlueprintEditorLibrary
EAL = unreal.EditorAssetLibrary
P = "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item"
bp = EAL.load_asset(P)
print("refrescando nodos de BP_Item...")
BEL.refresh_all_nodes(bp)
BEL.compile_blueprint(bp)
EAL.save_asset(P)
print("hecho: refresh + compile + save")
