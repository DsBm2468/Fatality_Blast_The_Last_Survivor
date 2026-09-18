import unreal
ar=unreal.AssetRegistryHelpers.get_asset_registry()
for a in ar.get_assets_by_path(unreal.Name("/Game/ThirdPerson"), recursive=True):
    n=str(a.asset_name)
    if n in ("WBP_HUB_Inventary","BP_Bandage","BPC_Inventary","BP_ThirdPersonCharacter","BPI_Interactable","BP_FirstAidKit"):
        print("%-26s %s" % (n, a.package_name))
