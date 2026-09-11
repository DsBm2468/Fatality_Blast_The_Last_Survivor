# -*- coding: utf-8 -*-
"""Cierra y reabre el editor del Blueprint indicado, para que arranque en el
EventGraph (el editor recuerda la ultima pestana abierta)."""
import unreal, os

saved = unreal.Paths.project_saved_dir()
with open(os.path.join(saved, "_paste_target.txt"), "r", encoding="utf-8") as fh:
    asset_path = fh.read().splitlines()[0].strip()

asset = unreal.EditorAssetLibrary.load_asset(asset_path)
ss = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
ss.close_all_editors_for_asset(asset)
ss.open_editor_for_assets([asset])
print("ABIERTO:", asset_path)
