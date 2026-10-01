class StreamlitFlowNode:
    def __init__(self, id, pos=(0, 0), data=None, node_type='default', **kw):
        self.id = id; self.pos = pos; self.data = dict(data or {}); self.type = node_type; self.kw = kw
    def __repr__(self):
        return f"Node({self.id!r},{self.data!r})"
class StreamlitFlowEdge:
    def __init__(self, id, source, target, **kw):
        self.id = id; self.source = source; self.target = target; self.kw = kw
    def __repr__(self):
        return f"Edge({self.source}->{self.target})"
