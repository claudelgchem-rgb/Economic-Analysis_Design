class StreamlitFlowState:
    def __init__(self, nodes, edges, selected_id=None, timestamp=0):
        self.nodes = list(nodes); self.edges = list(edges); self.selected_id = selected_id; self.timestamp = timestamp
    def __repr__(self):
        return f"FlowState(nodes={self.nodes!r}, edges={self.edges!r}, sel={self.selected_id!r})"
