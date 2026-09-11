import unreal, os
BEL=unreal.BlueprintEditorLibrary
EAL=unreal.EditorAssetLibrary
SALIDA=unreal.Paths.project_saved_dir()
for ruta in [r"/Game/ThirdPerson/Blueprints/AI/BP_GruntAIController"]:
    bp=EAL.load_asset(ruta)
    BEL.compile_blueprint(bp)
    nombre=ruta.rsplit("/",1)[-1]
    t=unreal.AssetExportTask()
    t.set_editor_property("object", bp)
    t.set_editor_property("filename", os.path.join(SALIDA,"AuditT3D_%s.copy"%nombre))
    t.set_editor_property("automated", True); t.set_editor_property("prompt", False)
    t.set_editor_property("exporter", unreal.ObjectExporterT3D())
    print(nombre, "->", unreal.Exporter.run_asset_export_task(t))
