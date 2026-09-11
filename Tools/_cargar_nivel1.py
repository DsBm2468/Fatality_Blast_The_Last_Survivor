import unreal
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level("/Game/ThirdPerson/Lvl_01_MilitaryBase")
print("NIVEL=%s" % unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world().get_name())
