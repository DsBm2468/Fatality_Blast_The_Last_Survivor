# -*- coding: utf-8 -*-
"""
Arregla la direccion del trazo de deteccion de objetos del Tick de
BP_ThirdPersonCharacter.

El SphereTrace azul se construye asi:

    Start = GetActorLocation + (0,0,50)
    End   = GetActorLocation + (GetActorForwardVector * 200) + (0,0,50)

GetActorForwardVector es la direccion del CUERPO del personaje: siempre
horizontal, sigue al movimiento y no tiene nada que ver con hacia donde mira el
jugador. Por eso el trazo no baja ni sube nunca y no ve un objeto que este
delante pero por debajo.

La cadena de disparo ya lo hace bien (FollowCamera -> GetForwardVector). Este
pegado trae ese mismo par de nodos, ya cableado entre si, para engancharlo al
multiplicador del trazo.

Uso:
    python Tools/gen_fix_interact_trace.py
    powershell -File Tools/clip.ps1 23
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bpgen import Graph, cls, CAT_OBJECT, CAT_STRUCT

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bp_paste")

C_KML = "/Script/Engine.KismetMathLibrary"
C_CAMERA = "/Script/Engine.CameraComponent"
S_VECTOR = "ScriptStruct'\"/Script/CoreUObject.Vector\"'"
S_ROTATOR = "ScriptStruct'\"/Script/CoreUObject.Rotator\"'"


def generar():
    g = Graph("Fix_InteractTrace", titulo=(
        "PEGADO 23 - EL TRAZO DE DETECCION SIGUE AL RATON\n"
        "Destino: BP_ThirdPersonCharacter > EventGraph  (SE ANADE)\n"
        "\n"
        "Hoy el SphereTrace azul del Tick apunta con GetActorForwardVector,\n"
        "o sea con el cuerpo del personaje: siempre horizontal. Estos dos\n"
        "nodos dan la direccion de la CAMARA, que es hacia donde mira el\n"
        "jugador de verdad.\n"
        "\n"
        "Al pegar, arrastra la salida de 'Get Forward Vector' hasta el pin A\n"
        "del nodo '*' que multiplica por 200. El cable viejo desde\n"
        "GetActorForwardVector se suelta solo (un pin de ENTRADA de datos\n"
        "solo admite uno)."))

    cam = g.var_get("FollowCamera", CAT_OBJECT, 0, 0, sub_object=cls(C_CAMERA))

    # OJO: aqui hace falta GetForwardVector del COMPONENTE (SceneComponent),
    # no el de KismetMathLibrary que toma un Rotator. Es el mismo nodo que ya
    # usa la cadena de disparo.
    fwd = g.call("GetForwardVector", "/Script/Engine.SceneComponent",
                 260, 0, pure=True)
    fwd.pin("self", CAT_OBJECT, sub_object=cls("/Script/Engine.SceneComponent"),
            hidden=True)
    fwd.pin("ReturnValue", CAT_STRUCT, out=True, sub_object=S_VECTOR)
    cam.get("FollowCamera").to(fwd.get("self"))

    g.comment("DIRECCION DE LA CAMARA  ->  llevar la salida al pin A del '*' "
              "que multiplica por 200 en el trazo del Tick",
              -40, -180, 700, 420,
              color="(R=1.000000,G=0.000000,B=0.600000,A=0.300000)")

    ruta = g.save(os.path.join(OUT, "23_Char_InteractTrace_Camera.txt"))
    print("  %-38s %2d nodos" % ("23_Char_InteractTrace_Camera.txt", len(g.nodes)))
    return ruta


if __name__ == "__main__":
    generar()
