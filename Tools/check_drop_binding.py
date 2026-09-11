# -*- coding: utf-8 -*-
"""
check_drop_binding.py - comprueba que la tecla F llega de verdad al evento de
soltar, sin necesidad de jugar.

Existe porque hay un trozo del camino que el banco en PIE no puede cubrir: la
entrada inyectada NO llega al viewport de Unreal (se probo con keybd_event y
con SendInput por scancode, con la ventana en primer plano y el raton
capturado por el juego; ni el movimiento ni la pausa surtian efecto). El banco
llama directamente a `BPC_Interaction.Ev_SoltarEquipado`, que es lo mismo que
llama la tecla; lo que queda por demostrar es justamente ese "es lo mismo", y
eso si se puede leer:

  1. IA_Drop existe y esta mapeada a F en IMC_Default;
  2. el EventGraph del personaje tiene un nodo de Enhanced Input de IA_Drop;
  3. su salida Started llega a una llamada a Ev_SoltarEquipado;
  4. esa llamada apunta al componente BPC_Interaction;
  5. BPC_Interaction define el evento Ev_SoltarEquipado.

Uso:  python Tools/ue_remote.py Tools/check_drop_binding.py
Acaba en "PROBLEMAS: N".
"""
import os
import re

import unreal

RAIZ = unreal.Paths.project_dir()
SAVED = unreal.Paths.project_saved_dir()
CHAR = "/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter"
INTER = "/Game/ThirdPerson/Components/BPC_Interaction"
IMC = "/Game/Input/IMC_Default"

problemas = []


def check(texto, cond, detalle=""):
    print("   %-5s %s%s" % ("OK" if cond else "FALLO", texto,
                            ("  -> " + str(detalle)) if detalle else ""))
    if not cond:
        problemas.append(texto)
    return bool(cond)


def exportar(ruta, nombre):
    destino = os.path.join(SAVED, "Bind_%s.copy" % nombre)
    t = unreal.AssetExportTask()
    t.object = unreal.EditorAssetLibrary.load_asset(ruta)
    t.filename = destino
    t.automated = True
    t.prompt = False
    t.replace_identical = True
    t.exporter = unreal.ObjectExporterT3D()
    unreal.Exporter.run_asset_export_task(t)
    raw = open(destino, "rb").read()
    try:
        return raw.decode("utf-16")
    except Exception:
        return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------- 1. el mapeo
imc = unreal.EditorAssetLibrary.load_asset(IMC)
tecla = None
if check("IMC_Default carga", imc is not None):
    datos = imc.get_editor_property("default_key_mappings")
    for m in datos.get_editor_property("mappings"):
        a = m.get_editor_property("action")
        if a is not None and a.get_name() == "IA_Drop":
            tecla = str(m.get_editor_property("key").get_editor_property("key_name"))
    check("IA_Drop esta mapeada a la tecla F", tecla == "F", "tecla=%s" % tecla)

# ------------------------------------------------- 2..4. el grafo del personaje
txt = exportar(CHAR, "Char")

# el nodo de entrada de IA_Drop, y el pin al que va su salida Started
nodo_entrada = None
for m in re.finditer(r'Begin Object Class=\S*K2Node_EnhancedInputAction '
                     r'Name="([^"]+)"(.*?)\nEnd Object', txt, re.S):
    if "IA_Drop" in m.group(2):
        nodo_entrada = (m.group(1), m.group(2))
check("el personaje tiene un nodo de entrada de IA_Drop", nodo_entrada is not None,
      nodo_entrada[0] if nodo_entrada else "")

destino = None
if nodo_entrada:
    for l in nodo_entrada[1].splitlines():
        if 'PinName="Started"' in l:
            mm = re.search(r'LinkedTo=\((\w+)\s', l)
            destino = mm.group(1) if mm else None
    check("la salida Started esta conectada", destino is not None,
          "-> %s" % destino)

if destino:
    m = re.search(r'Begin Object Class=\S+ Name="%s"(.*?)\nEnd Object'
                  % re.escape(destino), txt, re.S)
    cuerpo = m.group(1) if m else ""
    check("Started llama a Ev_SoltarEquipado",
          'MemberName="Ev_SoltarEquipado"' in cuerpo)
    check("la llamada apunta a BPC_Interaction",
          "BPC_Interaction_C" in cuerpo)

# ------------------------------------------------- 5. el evento en el componente
txt2 = exportar(INTER, "Inter")
check("BPC_Interaction define Ev_SoltarEquipado",
      'CustomFunctionName="Ev_SoltarEquipado"' in txt2)

print("")
print("PROBLEMAS: %d" % len(problemas))
