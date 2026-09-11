import unreal, os
EAL=unreal.EditorAssetLibrary
SALIDA=unreal.Paths.project_saved_dir()
for ruta in ["/Game/ThirdPerson/AI/BP_GruntAIController"]:
    if not EAL.does_asset_exist(ruta):
        print("NO EXISTE:", ruta); continue
    bp=EAL.load_asset(ruta)
    if bp is None:
        print("NO CARGA:", ruta); continue
    nombre=ruta.rsplit("/",1)[-1]
    t=unreal.AssetExportTask()
    t.set_editor_property("object", bp)
    t.set_editor_property("filename", os.path.join(SALIDA,"AuditT3D_%s.copy"%nombre))
    t.set_editor_property("automated", True); t.set_editor_property("prompt", False)
    t.set_editor_property("replace_identical", True)
    t.set_editor_property("exporter", unreal.ObjectExporterT3D())
    print("OK" if unreal.Exporter.run_asset_export_task(t) else "FALLO", nombre)
