# -*- coding: utf-8 -*-
"""
graph_dump.py - imprime un grafo exportado a T3D con sus conexiones reales.

audit_graph.py mezcla grafos en Blueprints con muchos grafos-stub de evento;
este usa t3d_read, que respeta el anidamiento de Begin/End Object.

Uso:
    python Tools/graph_dump.py Saved/T3D_BP_Item.copy            (lista grafos)
    python Tools/graph_dump.py Saved/T3D_BP_Item.copy Interact   (vuelca uno)
    ... --pines-todos    (tambien los pines sin cable ni valor)
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t3d_read as T


def nombre_pin(g, pid):
    for n in g.values():
        for p in n["pins"]:
            if p.get("PinId") == pid:
                return p.get("PinName", "?").strip('"')
    return "?"


def destinos(g, linked):
    out = []
    for m in re.finditer(r'([\w]+)\s+([0-9A-F]{32})', linked or ""):
        out.append("%s.%s" % (m.group(1), nombre_pin(g, m.group(2))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("grafo", nargs="?")
    ap.add_argument("--pines-todos", action="store_true")
    a = ap.parse_args()

    grafos = T.parse(a.export)
    if not a.grafo:
        for gn, g in grafos.items():
            vivos = sum(1 for n in g.values() if n["class"] != "EdGraphNode_Comment")
            print("  %-58s %3d nodos (%d sin contar comentarios)"
                  % (gn, len(g), vivos))
        return 0

    if a.grafo not in grafos:
        print("no existe el grafo %r. Hay: %s" % (a.grafo, ", ".join(grafos)))
        return 2

    g = grafos[a.grafo]
    print("=== %s :: %s  (%d nodos) ===" % (os.path.basename(a.export), a.grafo, len(g)))
    for nm, n in g.items():
        if n["class"] == "EdGraphNode_Comment":
            txt = n["props"].get("NodeComment", "").strip('"')
            print("  # COMENTARIO: %s" % txt[:90])
            continue
        print("  %-44s [%s]" % (T.label(n), nm))
        for p in n["pins"]:
            lk = p.get("LinkedTo")
            dv = p.get("DefaultValue") or p.get("DefaultObject") or p.get("DefaultTextValue")
            if not (lk or dv or a.pines_todos):
                continue
            flecha = "->" if p.get("Direction") else "<-"
            huerf = "  HUERFANO" if p.get("bOrphanedPin") == "True" else ""
            print("      %-22s %s %-52s %s%s" % (
                p.get("PinName", "").strip('"'), flecha,
                ", ".join(destinos(g, lk)),
                ("= " + dv) if dv else "", huerf))
    return 0


if __name__ == "__main__":
    sys.exit(main())
