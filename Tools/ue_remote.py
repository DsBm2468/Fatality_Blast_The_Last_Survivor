"""
Puente con el editor de Unreal abierto (Remote Execution).

Uso:
    "<engine>/Binaries/ThirdParty/Python3/Win64/python.exe" Tools/ue_remote.py script.py
    ... Tools/ue_remote.py -c "import unreal; print(unreal.SystemLibrary.get_engine_version())"

Requiere que en Project Settings > Plugins > Python este marcado
"Enable Remote Execution?" (o bRemoteExecution=True en DefaultEngine.ini
antes de arrancar el editor).

Recreado el 2026-08-26: la carpeta Tools/ original se perdio (nunca estuvo
en git, .gitignore no la cubre pero jamas se hizo commit).
"""
import os
import sys
import time

ENGINE_ROOT = os.environ.get("UE_ENGINE_ROOT", r"C:\Program Files\Epic Games\UE_5.7")
_RE_DIR = os.path.join(
    ENGINE_ROOT, "Engine", "Plugins", "Experimental",
    "PythonScriptPlugin", "Content", "Python",
)
if _RE_DIR not in sys.path:
    sys.path.append(_RE_DIR)

import remote_execution as remote  # noqa: E402


def _connect(timeout=10.0):
    conn = remote.RemoteExecution()
    conn.start()
    deadline = time.time() + timeout
    while time.time() < deadline:
        nodes = conn.remote_nodes
        if nodes:
            conn.open_command_connection(nodes)
            return conn
        time.sleep(0.25)
    conn.stop()
    raise SystemExit(
        "ERROR: no se encontro ningun editor de Unreal escuchando.\n"
        "  1. El editor tiene que estar abierto.\n"
        "  2. Project Settings > Plugins > Python > 'Enable Remote Execution?' marcado.\n"
        "  3. Multicast 239.0.0.1:6766 no bloqueado por el firewall."
    )


def run_source(source, exec_mode=remote.MODE_EXEC_FILE):
    conn = _connect()
    try:
        result = conn.run_command(source, unattended=True, exec_mode=exec_mode)
    finally:
        conn.stop()

    for entry in result.get("output") or []:
        stream = sys.stderr if entry.get("type") in ("Error", "Warning") else sys.stdout
        print(entry.get("output", "").rstrip("\n"), file=stream)

    if not result.get("success"):
        print("FALLO: " + str(result.get("result")), file=sys.stderr)
        return 1
    return 0


def main(argv):
    if len(argv) >= 2 and argv[0] == "-c":
        return run_source(argv[1], remote.MODE_EXEC_STATEMENT)

    if not argv:
        print(__doc__)
        return 2

    path = os.path.abspath(argv[0])
    if not os.path.isfile(path):
        print("ERROR: no existe " + path, file=sys.stderr)
        return 2

    with open(path, "r", encoding="utf-8") as fh:
        body = fh.read()

    # El script remoto se ejecuta como texto: le damos __file__ para que pueda
    # resolver rutas relativas a si mismo (lo hacia la version original).
    header = "__file__ = r'''{0}'''\n".format(path)
    return run_source(header + body)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
