import unreal
BEL=unreal.BlueprintEditorLibrary
bp=unreal.EditorAssetLibrary.load_asset("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter")
cdo=unreal.get_default_object(BEL.generated_class(bp))
cm=cdo.get_editor_property("character_movement")
print("MaxWalkSpeed        :", cm.get_editor_property("max_walk_speed"))
print("MaxWalkSpeedCrouched:", cm.get_editor_property("max_walk_speed_crouched"))
nav=cm.get_editor_property("nav_agent_props")
print("NavAgentProps.can_crouch:", nav.get_editor_property("can_crouch"))
print("CrouchedHalfHeight  :", cm.get_editor_property("crouched_half_height"))
