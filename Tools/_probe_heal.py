import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if w is None:
    print("SIN_MUNDO"); raise SystemExit
pj=unreal.GameplayStatics.get_player_character(w,0)
def comp(a,n):
    for c in a.get_components_by_class(unreal.ActorComponent):
        if c.get_class().get_name()==n: return c
cur=comp(pj,"BPC_Curation_C"); hs=comp(pj,"BPC_HealthSystem_C"); inv=comp(pj,"BPC_Inventary_C")
hs.set_editor_property("Health", 40.0)
kits=[a for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor)
      if a.get_class().get_name()=="BP_FirstAidKit_C"]
inv.set_editor_property("Object_Is_FirstAidKit", kits[0])
print("VIDA=%s" % hs.get_editor_property("Health"))
print("KIT=%s" % inv.get_editor_property("Object_Is_FirstAidKit"))
print("CANALIZANDO_ANTES=%s" % cur.get_editor_property("IsChanneling"))
print("COOLDOWN=%s  AHORA=%s" % (cur.get_editor_property("CooldownUntil"),
                                 unreal.GameplayStatics.get_time_seconds(w)))
cur.call_method("TryStartHeal")
print("LLAMADO=si")
print("CANALIZANDO_DESPUES=%s" % cur.get_editor_property("IsChanneling"))
