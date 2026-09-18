import sys, re, collections

def load(path):
    raw=open(path,'rb').read()
    try: return raw.decode('utf-16')
    except Exception: return raw.decode('utf-8','replace')

PIN = re.compile(r'CustomProperties Pin \((.*)\)\s*$')

def kv(blob):
    d={}
    for m in re.finditer(r'([\w\.]+)=("[^"]*"|\((?:[^()]|\([^()]*\))*\)|[^,]*)', blob):
        d[m.group(1)]=m.group(2)
    return d

def parse(path):
    t=load(path)
    graphs=collections.OrderedDict(); curg=None; curn=None
    for line in t.splitlines():
        s=line.strip()
        m=re.match(r'Begin Object (?:Class=([\w/\.]+) )?Name="([^"]+)"', s)
        if m:
            cls=(m.group(1) or '').split('.')[-1]; nm=m.group(2)
            # OJO: un grafo-stub de evento y su nodo se llaman IGUAL
            # (p.ej. Interact_1_1). Si al reabrir el bloque sin Class= se
            # interpreta como cambio de grafo, se pierde ese nodo Y todos
            # los que vengan detras. Medido el 2026-08-31.
            ya_es_nodo = curg is not None and nm in graphs.get(curg, {})
            if cls=='EdGraph' or (not cls and nm in graphs and not ya_es_nodo):
                curg=nm; graphs.setdefault(curg, collections.OrderedDict()); curn=None
            elif curg is not None:
                # OJO: el export declara cada nodo DOS veces, primero un stub
                # vacio y luego el bloque con props y pines. Recrear la entrada
                # en la segunda vuelta borraba los pines y hacia parecer que el
                # nodo no tenia ninguno. Medido el 2026-08-31.
                if cls and nm not in graphs[curg]:
                    graphs[curg][nm]={'class':cls,'props':{},'pins':[]}
                elif cls:
                    graphs[curg][nm]['class']=cls
                curn=nm if nm in graphs[curg] else None
            continue
        if s.startswith('End Object'): continue
        if curg is None or curn is None: continue
        m=PIN.match(s)
        if m: graphs[curg][curn]['pins'].append(kv(m.group(1))); continue
        m=re.match(r'([\w\.]+)=(.*)$', s)
        if m: graphs[curg][curn]['props'][m.group(1)]=m.group(2)
    return graphs

def mem(p, key):
    mn=re.search(r'MemberName="?(\w+)', p.get(key,'')); return mn.group(1) if mn else '?'

def label(n):
    p=n['props']; c=n['class']
    if c=='K2Node_CustomEvent': return 'EVENT '+p.get('CustomFunctionName','?').strip('"')
    if c=='K2Node_Event': return 'EVENT(ovr) '+mem(p,'EventReference')
    if c=='K2Node_FunctionEntry': return '>> ENTRY'
    if c=='K2Node_FunctionResult': return '<< RETURN'
    if c=='K2Node_CallFunction':
        f=mem(p,'FunctionReference')
        if f=='PrintString':
            return 'PRINT'
        return 'call '+f
    if c=='K2Node_CallDelegate': return 'BROADCAST '+mem(p,'DelegateReference')
    if c=='K2Node_VariableSet': return 'SET '+mem(p,'VariableReference')
    if c=='K2Node_VariableGet': return 'get '+mem(p,'VariableReference')
    if c=='K2Node_IfThenElse': return 'BRANCH'
    if c=='K2Node_Message': return 'MSG '+mem(p,'FunctionReference')
    if c=='K2Node_EnumLiteral': return 'enum'
    if c=='K2Node_DynamicCast': return 'CAST '+p.get('TargetType','?').split('.')[-1].strip('"\'')
    if c=='K2Node_MacroInstance': return 'macro '+re.sub(r'.*:(\w+)\'.*',r'\1',p.get('MacroGraphReference',''))
    if c=='K2Node_Knot': return '(knot)'
    if c.startswith('K2Node_'): return c[7:]
    return c

def show(graphs, gname, data=False):
    g=graphs[gname]
    owner={}
    for nm,n in g.items():
        for pin in n['pins']:
            pid=pin.get('PinId','').strip('"')
            if pid: owner[pid]=nm
    print("="*74); print("GRAFO: %s  (%d nodos)"%(gname,len(g)))
    for nm,n in g.items():
        rows=[]
        for pin in n['pins']:
            cat=pin.get('PinType.PinCategory','').strip('"')
            out=pin.get('Direction','').strip('"')=='EGPD_Output'
            if cat!='exec':
                if not data: continue
            pn=pin.get('PinName','').strip('"')
            tg=[]
            for pid in re.findall(r'\b([0-9A-F]{32})\b', pin.get('LinkedTo','')):
                o=owner.get(pid); tg.append(("%s[%s]"%(label(g[o]), o.split('_')[-1])) if o else "?")
            dv=pin.get('DefaultValue','').strip('"')
            if cat=='exec' and out:
                rows.append("%s=> %s"%(pn, " | ".join(tg) if tg else "(NADA)"))
            elif data and not out:
                rows.append("  %s <- %s%s"%(pn, " | ".join(tg) if tg else "", (" ="+dv) if dv and not tg else ""))
        has_in=any(p.get('PinType.PinCategory','').strip('"')=='exec' and p.get('Direction','').strip('"')!='EGPD_Output' for p in n['pins'])
        if not rows and not has_in: continue
        print("  [%s] %-30s"%(nm.split('_')[-1], label(n)))
        for r in rows: print("        "+r)

if __name__=='__main__':
    args=[a for a in sys.argv[1:] if not a.startswith('-')]
    data='-d' in sys.argv
    gs=parse(args[0]); want=args[1:]
    for gname in gs:
        if want and gname not in want: continue
        show(gs,gname,data)

# ---------------------------------------------------------------------------
# Uso:
#   1) exportar el Blueprint a T3D desde el editor (AssetExportTask +
#      ObjectExporterT3D) -> Saved/AuditT3D_<Nombre>.copy   (sale en UTF-16)
#   2) python Tools/audit_graph.py Saved/AuditT3D_BP_X.copy [Grafo ...] [-d]
#
# Sin -d imprime solo la cadena de ejecucion; con -d anade los pines de datos
# con sus literales. Resuelve LinkedTo (que va por GUID de pin) al nodo dueno.
#
# Es la unica forma de leer las CONEXIONES de un grafo sin Ctrl+A/Ctrl+C a mano:
# UEdGraph.Nodes es protected, pero el export a T3D si trae los pines.
# Los grafos de 2-3 nodos (Entry + ExecuteUbergraph) son stubs del compilador
# para eventos personalizados: la logica de verdad esta en el EventGraph.
