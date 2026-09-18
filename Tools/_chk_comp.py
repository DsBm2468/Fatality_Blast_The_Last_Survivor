import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w is None:
    print("SIN_MUNDO"); raise SystemExit
print("MUNDO=%s" % w.get_name())
pj=unreal.GameplayStatics.get_player_character(w,0)
print("JUGADOR=%s" % pj.get_name())
for c in pj.get_components_by_class(unreal.ActorComponent):
    print("   %s" % c.get_class().get_name())
