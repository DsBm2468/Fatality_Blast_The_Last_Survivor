"""Exporta Blueprints a T3D en Saved/AuditT3D_<Nombre>.copy  (sale en UTF-16).

Uso remoto:
    python Tools/ue_remote.py Tools/export_t3d.py
Edita ASSETS abajo para cambiar la lista.
"""
import unreal, os

ASSETS = [
    "/Game/ThirdPerson/Components/BPC_HealthSystem",
    "/Game/ThirdPerson/Components/BPC_ProtectionSystem",
    "/Game/ThirdPerson/Components/BPC_Curation",
    "/Game/ThirdPerson/Components/BPC_Inventary",
    "/Game/ThirdPerson/Components/BPC_Interaction",
    "/Game/ThirdPerson/AI/BP_GruntAIController",
    "/Game/ThirdPerson/Blueprints/BP_Grunt",
    "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_Bandage",
    "/Game/ThirdPerson/Blueprints/Interactables/BP_FirstAidKit",
    "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item_Weapon_Base",
    "/Game/ThirdPerson/Blueprints/Interactables/FixedInteractables/BP_Item",
    "/Game/ThirdPerson/Blueprints/WBP/HUB/WBP_HUB_LifeBar",
]

out_dir = os.path.join(unreal.Paths.project_saved_dir(), "")
for path in ASSETS:
    name = path.rsplit("/", 1)[-1]
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        print("NO EXISTE:", path)
        continue
    task = unreal.AssetExportTask()
    task.object = asset
    task.filename = os.path.join(out_dir, "AuditT3D_%s.copy" % name)
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.exporter = unreal.ObjectExporterT3D()
    ok = unreal.Exporter.run_asset_export_task(task)
    print(("OK  " if ok else "FALLO "), name, task.filename)
