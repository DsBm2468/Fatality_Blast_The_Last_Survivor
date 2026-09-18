import unreal
imc=unreal.EditorAssetLibrary.load_asset("/Game/Input/IMC_Default")
for m in imc.get_editor_property("default_key_mappings").get_editor_property("mappings"):
    ia=m.get_editor_property("action")
    if ia and "Crouch" in ia.get_name() or (ia and "Heal" in ia.get_name()):
        k=m.get_editor_property("key")
        print(ia.get_name(), "->", k.get_editor_property("key_name"))
