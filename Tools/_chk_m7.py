import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w is None:
    print("SIN_MUNDO"); raise SystemExit
print("MUNDO=%s" % w.get_name())
for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
    if a.get_actor_label().startswith("BO_M7_"):
        l=a.get_actor_location()
        print("  %-28s (%7.0f,%8.0f,%7.1f)" % (a.get_actor_label()[6:], l.x, l.y, l.z))
