import unreal
BEL=unreal.BlueprintEditorLibrary
EAL=unreal.EditorAssetLibrary
KIT=unreal.load_object(None,"/Game/ThirdPerson/Blueprints/Interactables/BP_FirstAidKit.BP_FirstAidKit_C")
IFC=unreal.load_object(None,"/Game/ThirdPerson/Blueprints/Interfaces/BPI_Interactable.BPI_Interactable_C")
for ruta in ["/Game/ThirdPerson/Blueprints/Interactables/BP_Bandage",
             "/Game/ThirdPerson/Blueprints/Interactables/BP_FirstAidKit"]:
    bp=EAL.load_asset(ruta); k=BEL.generated_class(bp)
    cdo=unreal.get_default_object(k)
    print("="*60); print(ruta)
    print("   hereda de BP_FirstAidKit:", isinstance(cdo, type(unreal.get_default_object(KIT))))
    print("   ClassIsChildOf(k, KIT) :", unreal.MathLibrary.class_is_child_of(k, KIT) if hasattr(unreal,'MathLibrary') else unreal.KismetMathLibrary.class_is_child_of(k, KIT))
    print("   implementa Interactable:", unreal.KismetMathLibrary.class_is_child_of(k, IFC))
