import unreal, os
ASSETS = [
 "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter",
 "/Game/ThirdPerson/Blueprints/Interactables/BP_ConventionalGun",
 "/Game/ThirdPerson/Blueprints/Interactables/BP_SubmachineGun",
 "/Game/ThirdPerson/Blueprints/Interactables/BP_MunitionConventionalGun",
 "/Game/ThirdPerson/Blueprints/Interfaces/BPI_WeaponSystem",
 "/Game/ThirdPerson/AI/BP_GruntAIController",
 "/Game/ThirdPerson/Blueprints/BP_Grunt",
 "/Game/ThirdPerson/Components/BPC_HealthSystem",
 "/Game/ThirdPerson/Components/BPC_Inventary",
 "/Game/ThirdPerson/Blueprints/WBP/HUB/WBP_HUB_Inventary",
]
out_dir = unreal.Paths.project_saved_dir()
for path in ASSETS:
    name = path.rsplit("/",1)[-1]
    a = unreal.EditorAssetLibrary.load_asset(path)
    if a is None:
        print("NO EXISTE:", path); continue
    t = unreal.AssetExportTask()
    t.object=a; t.filename=os.path.join(out_dir,"AuditT3D_%s.copy"%name)
    t.automated=True; t.prompt=False; t.replace_identical=True
    t.exporter=unreal.ObjectExporterT3D()
    print(("OK   " if unreal.Exporter.run_asset_export_task(t) else "FALLO"), name)
