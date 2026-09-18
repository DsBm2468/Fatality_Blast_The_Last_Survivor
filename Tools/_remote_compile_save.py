# -*- coding: utf-8 -*-
"""Compila y guarda el Blueprint indicado en Saved/_paste_target.txt.

Los errores del compilador de Blueprint salen por el log del editor, que
ue_remote reenvia marcados como Error/Warning. La propiedad 'Status' del
Blueprint es protegida y no se puede leer desde Python, asi que el veredicto
se da por el log, no por el asset.
"""
import unreal, os

saved = unreal.Paths.project_saved_dir()
with open(os.path.join(saved, "_paste_target.txt"), "r", encoding="utf-8") as fh:
    asset_path = fh.read().splitlines()[0].strip()

bp = unreal.EditorAssetLibrary.load_asset(asset_path)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
print("COMPILADO:", asset_path)
unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
print("GUARDADO:", asset_path)
