import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pj=unreal.GameplayStatics.get_player_character(w,0)
def comp(a,n):
    for c in a.get_components_by_class(unreal.ActorComponent):
        if c.get_class().get_name()==n: return c
cur=comp(pj,"BPC_Curation_C"); hs=comp(pj,"BPC_HealthSystem_C"); inv=comp(pj,"BPC_Inventary_C")
kits=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
      if a.get_class().get_name()=="BP_FirstAidKit_C"]
print("KITS=%d" % len(kits))
# recogerlo como en el banco: Interact sobre el ACTOR
kits[0].call_method("Interact", args=(pj,))
print("KIT_EN_INVENTARIO=%s" % (inv.get_editor_property("Object_Is_FirstAidKit") is not None))
hs.set_editor_property("Health", 40.0)
print("VIDA=%s" % hs.get_editor_property("Health"))
print("CANALIZANDO_ANTES=%s" % cur.get_editor_property("IsChanneling"))
cur.call_method("TryStartHeal")
print("CANALIZANDO_DESPUES=%s" % cur.get_editor_property("IsChanneling"))
print("PROGRESO=%s" % cur.get_editor_property("ChannelProgress"))
print("VELOCIDAD=%.0f" % pj.character_movement.max_walk_speed)
