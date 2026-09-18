import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pj=unreal.GameplayStatics.get_player_character(w,0)
def comp(a,n):
    for c in a.get_components_by_class(unreal.ActorComponent):
        if c.get_class().get_name()==n: return c
cur=comp(pj,"BPC_Curation_C")
cm=pj.character_movement
cur.set_editor_property("CachedWalkSpeed", 333.0)
cm.set_editor_property("max_walk_speed", 777.0)
print("CachedWalkSpeed=%s" % cur.get_editor_property("CachedWalkSpeed"))
print("VEL_ANTES=%.0f" % cm.max_walk_speed)
cur.call_method("CancelHeal")
print("VEL_DESPUES=%.0f  (333 => el evento SI se ejecuto)" % cm.max_walk_speed)
