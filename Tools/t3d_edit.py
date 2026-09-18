# -*- coding: utf-8 -*-
"""
t3d_edit.py - utilidades para MODIFICAR nodos ya exportados a T3D.

t3d_to_paste.py mueve nodos de un grafo a otro; esto es para lo otro que hace
falta a menudo: cambiar un cable, una propiedad o el valor de un pin de un
nodo que ya existe, conservando todo lo demas tal y como lo escribio el
exportador.

La API de Python de UE no puede tocar pines, asi que la unica forma de
"editar" un grafo es reconstruirlo entero: exportar, modificar el texto,
vaciar el grafo y volver a pegar. Estas funciones son el paso del medio.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t3d_read  # noqa: E402
import t3d_to_paste  # noqa: E402


class Bloques(object):
    """Los nodos de un grafo exportado, como texto editable."""

    def __init__(self, export, grafo):
        self.grafo = grafo
        self.nodos = {}          # nombre -> [lineas]
        self.orden = []
        for nombre, clase, lineas in t3d_to_paste.bloques(export, grafo):
            self.nodos[nombre] = lineas
            self.orden.append(nombre)
        self.parsed = t3d_read.parse(export)[grafo]

    # ------------------------------------------------------------- consulta
    def pin_id(self, nodo, pin):
        """GUID del pin (nodo, pin). Falla si no existe, que es lo que se
        quiere: un nombre de pin mal escrito es un cable que no se crea y un
        Blueprint que compila en verde sin hacer nada."""
        for p in self.parsed[nodo]["pins"]:
            if p.get("PinName", "").strip('"') == pin:
                return p["PinId"]
        raise KeyError("el nodo %s no tiene el pin %r (tiene: %s)"
                       % (nodo, pin, ", ".join(
                           q.get("PinName", "").strip('"')
                           for q in self.parsed[nodo]["pins"])))

    # ----------------------------------------------------------- edicion
    def _linea_pin(self, nodo, pin):
        pid = self.pin_id(nodo, pin)
        for i, l in enumerate(self.nodos[nodo]):
            if "PinId=%s" % pid in l:
                return i
        raise KeyError("no se encontro la linea del pin %s.%s" % (nodo, pin))

    def enlazar(self, nodo, pin, destinos):
        """Sustituye el LinkedTo de un pin. destinos: [(nodo, pin_id), ...]."""
        i = self._linea_pin(nodo, pin)
        l = self.nodos[nodo][i]
        nuevo = ("LinkedTo=(%s,)," % ",".join("%s %s" % d for d in destinos)
                 if destinos else "")
        if "LinkedTo=(" in l:
            l = re.sub(r"LinkedTo=\([^)]*\),", nuevo, l)
        elif nuevo:
            # se inserta justo antes de PersistentGuid, que siempre esta
            l = l.replace("PersistentGuid=", nuevo + "PersistentGuid=")
        self.nodos[nodo][i] = l

    def valor(self, nodo, pin, valor, clave="DefaultValue"):
        i = self._linea_pin(nodo, pin)
        l = self.nodos[nodo][i]
        if "%s=" % clave in l:
            l = re.sub(r'%s="[^"]*",' % clave, '%s="%s",' % (clave, valor), l)
        else:
            l = l.replace("PersistentGuid=",
                          '%s="%s",PersistentGuid=' % (clave, valor))
        self.nodos[nodo][i] = l

    def propiedad(self, nodo, patron, reemplazo):
        """Sustitucion regex sobre las lineas de propiedades del nodo."""
        tocado = False
        for i, l in enumerate(self.nodos[nodo]):
            if "CustomProperties Pin" in l or l.strip().startswith("Begin Object"):
                continue
            nueva = re.sub(patron, reemplazo, l)
            if nueva != l:
                self.nodos[nodo][i] = nueva
                tocado = True
        if not tocado:
            raise KeyError("ninguna propiedad de %s casa con %r" % (nodo, patron))

    def tipo_pin(self, nodo, pin, sub_object):
        """Cambia PinType.PinSubCategoryObject de un pin. Hace falta al
        duplicar un GetComponentByClass: su ReturnValue se tipa segun la clase
        pedida, y si no se cambia, el cable al componente nuevo no engancha."""
        i = self._linea_pin(nodo, pin)
        self.nodos[nodo][i] = re.sub(
            r'PinType\.PinSubCategoryObject=[^,]*,',
            'PinType.PinSubCategoryObject=%s,' % sub_object,
            self.nodos[nodo][i])

    def duplicar(self, nodo, nuevo):
        """Clona un nodo con GUIDs de pin nuevos y sin ningun cable.

        Sirve para reutilizar un nodo del propio grafo como plantilla en vez
        de volver a declararlo a mano: asi los tipos de pin salen exactos.
        """
        import hashlib
        lineas = []
        for l in self.nodos[nodo]:
            l = re.sub(r'(Name=")%s(")' % re.escape(nodo),
                       r'\g<1>%s\g<2>' % nuevo, l)
            l = re.sub(r'\s*ExportPath="[^"]*"', '', l)
            m = re.search(r'PinId=([0-9A-F]{32})', l)
            if m:
                nuevo_id = hashlib.md5(
                    ("%s|%s" % (nuevo, m.group(1))).encode()).hexdigest().upper()
                l = l.replace(m.group(1), nuevo_id)
                l = re.sub(r"LinkedTo=\([^)]*\),", "", l)
            if l.strip().startswith("NodeGuid="):
                l = "   NodeGuid=%s" % hashlib.md5(
                    nuevo.encode()).hexdigest().upper()
            lineas.append(l)
        self.nodos[nuevo] = lineas
        self.orden.append(nuevo)
        # el parseo tiene que conocer el nodo nuevo para que pin_id funcione
        import copy
        clon = copy.deepcopy(self.parsed[nodo])
        for p in clon["pins"]:
            import hashlib as _h
            p["PinId"] = _h.md5(
                ("%s|%s" % (nuevo, p["PinId"])).encode()).hexdigest().upper()
            p.pop("LinkedTo", None)
        self.parsed[nuevo] = clon
        return nuevo

    def quitar(self, *nombres):
        for n in nombres:
            self.nodos.pop(n, None)
            if n in self.orden:
                self.orden.remove(n)

    # ------------------------------------------------------------- salida
    def texto(self):
        return "\n".join("\n".join(self.nodos[n]) for n in self.orden) + "\n"
