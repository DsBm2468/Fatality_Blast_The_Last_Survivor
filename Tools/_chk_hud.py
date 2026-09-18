import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pj=unreal.GameplayStatics.get_player_character(w,0)
print("MUNDO=%s" % w.get_name())
for nombre in ("WBP HUB inventary","WBP HUB Life Bar"):
    v=pj.get_editor_property(nombre)
    g=v.get_cached_geometry()
    print("%-20s in_viewport=%-5s  geometria=%s" % (nombre, v.is_in_viewport(), g))
