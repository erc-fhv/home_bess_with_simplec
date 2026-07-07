"""
Graph Dashboard — interactive visualization of SimPlEC scenario graphs.

Run with:
    python data_explorer/graph_dashboard.py

Requires: dash, dash-bootstrap-components, dash-cytoscape
"""

import os
import json

import dash
from dash import dcc, html, Input, Output, State, ctx, no_update
import dash_bootstrap_components as dbc
import dash_cytoscape as cyto

# Load dagre layout extension for hierarchical rendering
cyto.load_extra_layouts()

# =====================
# Config
# =====================
ROOT_PATH = "./data/graph"
SIDEBAR_WIDTH = "380px"

# =====================
# Helpers
# =====================

def scan_dirs(path):
    """Return sorted list of subdirectory names."""
    if not os.path.exists(path):
        return []
    return sorted(
        d for d in os.listdir(path)
        if os.path.isdir(os.path.join(path, d))
    )


def scan_json(path):
    """Return list of {label, value} for .json files in *path*."""
    if not os.path.exists(path):
        return []
    files = sorted(f for f in os.listdir(path) if f.endswith(".json"))
    result = []
    for f in files:
        stem = f.removesuffix(".json")
        # Format YYYYMMDD_HHMM → YYYY-MM-DD HH:MM (if applicable)
        if len(stem) == 13 and stem[8] == '_':
            label = (stem[:4] + '-' + stem[4:6] + '-' + stem[6:8]
                     + ' ' + stem[9:11] + ':' + stem[11:13])
        else:
            label = stem
        result.append({'label': label, 'value': f})
    return result


def build_cytoscape_elements(graph_data):
    """Convert the exported JSON dict into Cytoscape elements."""
    elements = []

    # --- Nodes ---
    for model in graph_data['models']:
        elements.append({
            'data': {
                'id': model['name'],
                'label': model['name'],
                'class': model['class'],
                'module': model.get('module', ''),
                'inputs': json.dumps(model.get('inputs', [])),
                'outputs': json.dumps(model.get('outputs', [])),
                'delta_t': model.get('delta_t'),
                'docstring': model.get('docstring', ''),
                'params': json.dumps(model.get('params')) if model.get('params') else None,
            },
            'classes': 'model-node',
        })

    # --- Edges: group connections by (source, target) pair ---
    edge_map: dict[tuple[str, str], list[dict]] = {}
    constant_nodes_added: set[str] = set()

    for conn in graph_data['connections']:
        conn_type = conn.get('connection_type', 'data')

        # For constant connections, add a small sentinel node
        if conn_type == 'constant':
            const_id = conn['source']
            if const_id not in constant_nodes_added:
                const_val = conn.get('constant_value')
                label = str(const_val) if const_val is not None else '?'
                if len(label) > 20:
                    label = label[:17] + '...'
                elements.append({
                    'data': {'id': const_id, 'label': label},
                    'classes': 'constant-node',
                })
                constant_nodes_added.add(const_id)

        pair = (conn['source'], conn['target'])
        edge_map.setdefault(pair, []).append(conn)

    for (src, tgt), conns in edge_map.items():
        has_time_shifted = any(c.get('time_shifted', False) for c in conns)
        is_exec_order = all(c.get('connection_type') == 'execution_order' for c in conns)
        is_constant = all(c.get('connection_type') == 'constant' for c in conns)

        classes = []
        if has_time_shifted:
            classes.append('time-shifted')
        if is_exec_order:
            classes.append('exec-order')
        if is_constant:
            classes.append('constant-edge')

        elements.append({
            'data': {
                'id': f'{src}→{tgt}',
                'source': src,
                'target': tgt,
                'connections': json.dumps([
                    {
                        'attr_out': c.get('attr_out'),
                        'attr_in': c.get('attr_in'),
                        'time_shifted': c.get('time_shifted', False),
                        'connection_type': c.get('connection_type', 'data'),
                        'constant_value': c.get('constant_value'),
                    }
                    for c in conns
                ]),
                'has_time_shifted': has_time_shifted,
                'n_connections': len(conns),
            },
            'classes': ' '.join(classes),
        })

    return elements


# =====================
# Cytoscape Stylesheet
# =====================
CYTO_STYLESHEET = [
    # --- Nodes (Simulink-like rectangular blocks) ---
    {
        'selector': 'node.model-node',
        'style': {
            'shape': 'round-rectangle',
            'width': 'label',
            'height': '40px',
            'padding': '12px',
            'background-color': '#ffffff',
            'border-color': '#333333',
            'border-width': 2,
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '13px',
            'font-family': 'monospace',
            'color': '#222222',
            'text-wrap': 'wrap',
            'text-max-width': '160px',
        },
    },
    # --- Constant nodes (small rounded) ---
    {
        'selector': 'node.constant-node',
        'style': {
            'shape': 'ellipse',
            'width': 'label',
            'height': '28px',
            'padding': '8px',
            'background-color': '#FFF9C4',
            'border-color': '#F9A825',
            'border-width': 1.5,
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-family': 'monospace',
            'color': '#555555',
        },
    },
    # --- Node: selected ---
    {
        'selector': 'node:selected',
        'style': {
            'border-color': '#0d6efd',
            'border-width': 3,
            'background-color': '#e7f1ff',
        },
    },
    # --- Edges: default (same-time data) ---
    {
        'selector': 'edge',
        'style': {
            'width': 2,
            'line-color': '#4CAF50',
            'target-arrow-color': '#4CAF50',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 1.2,
            'curve-style': 'bezier',
        },
    },
    # --- Edges: time-shifted ---
    {
        'selector': 'edge.time-shifted',
        'style': {
            'line-color': '#F44336',
            'target-arrow-color': '#F44336',
            'line-style': 'dashed',
        },
    },
    # --- Edges: constant ---
    {
        'selector': 'edge.constant-edge',
        'style': {
            'line-color': '#F9A825',
            'target-arrow-color': '#F9A825',
            'width': 1.5,
            'line-style': 'solid',
        },
    },
    # --- Edges: execution-order-only (connect_nothing) ---
    {
        'selector': 'edge.exec-order',
        'style': {
            'line-color': '#9E9E9E',
            'target-arrow-color': '#9E9E9E',
            'line-style': 'dotted',
            'width': 1.5,
        },
    },
    # --- Edge: selected ---
    {
        'selector': 'edge:selected',
        'style': {
            'width': 3.5,
            'line-color': '#0d6efd',
            'target-arrow-color': '#0d6efd',
        },
    },
]

# =====================
# App
# =====================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)
app.title = "SimPlEC Graph Viewer"

# =====================
# Layout
# =====================
app.layout = dbc.Container([

    # --- Top bar: file selection ---
    dbc.Card(
        dbc.CardBody(
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id="scenario-dd",
                        placeholder="Scenario",
                        options=[{'label': d, 'value': d} for d in scan_dirs(ROOT_PATH)],
                    ),
                    width=3,
                ),
                dbc.Col(
                    dcc.Dropdown(id="subscenario-dd", placeholder="Sub-scenario"),
                    width=3,
                ),
                dbc.Col(
                    dcc.Dropdown(id="timestamp-dd", placeholder="Graph file"),
                    width=3,
                ),
                dbc.Col(
                    dbc.Button("Load Graph", id="load-btn", color="primary", className="w-100"),
                    width=2,
                ),
                dbc.Col(
                    dbc.Button("⟳", id="refresh-btn", color="secondary",
                               outline=True, title="Refresh file list"),
                    width=1,
                ),
            ], className="align-items-center"),
        ),
        className="mb-2 mt-2",
    ),

    # --- Main area: graph + side panel ---
    dbc.Row([
        # Central graph area
        dbc.Col(
            cyto.Cytoscape(
                id='cytoscape',
                elements=[],
                layout={
                    'name': 'dagre',
                    'rankDir': 'LR',
                    'nodeSep': 60,
                    'rankSep': 120,
                    'edgeSep': 20,
                },
                stylesheet=CYTO_STYLESHEET,
                style={'width': '100%', 'height': '87vh'},
                boxSelectionEnabled=False,
            ),
            width=9,
            className="pe-0",
        ),

        # Right side panel
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(html.H5("Details", className="mb-0")),
                dbc.CardBody(
                    dcc.Markdown(
                        id="detail-panel",
                        children="_Click a model or connection to inspect it._",
                        style={
                            'overflowY': 'auto',
                            'maxHeight': '82vh',
                            'fontSize': '13px',
                        },
                        dangerously_allow_html=True,
                    ),
                ),
            ], style={'height': '87vh'}),
            width=3,
            className="ps-1",
        ),
    ]),

    # Hidden store for loaded graph data
    dcc.Store(id='graph-store', data=None),

], fluid=True)


# =====================
# Callbacks
# =====================

# --- Dropdown cascade ---
@app.callback(
    Output("scenario-dd", "options"),
    Input("refresh-btn", "n_clicks"),
    prevent_initial_call=False,
)
def refresh_scenarios(_):
    return [{'label': d, 'value': d} for d in scan_dirs(ROOT_PATH)]


@app.callback(
    Output("subscenario-dd", "options"),
    Output("subscenario-dd", "value"),
    Input("scenario-dd", "value"),
)
def update_subscenarios(scenario):
    if not scenario:
        return [], None
    path = os.path.join(ROOT_PATH, scenario)
    return [{'label': d, 'value': d} for d in scan_dirs(path)], None


@app.callback(
    Output("timestamp-dd", "options"),
    Output("timestamp-dd", "value"),
    Input("subscenario-dd", "value"),
    State("scenario-dd", "value"),
)
def update_timestamps(sub, scenario):
    if not scenario or not sub:
        return [], None
    path = os.path.join(ROOT_PATH, scenario, sub)
    return scan_json(path), None


# --- Load graph ---
@app.callback(
    Output("graph-store", "data"),
    Output("cytoscape", "elements"),
    Output("detail-panel", "children"),
    Input("load-btn", "n_clicks"),
    State("scenario-dd", "value"),
    State("subscenario-dd", "value"),
    State("timestamp-dd", "value"),
    prevent_initial_call=True,
)
def load_graph(_, scenario, sub, filename):
    if not all([scenario, sub, filename]):
        return no_update, no_update, "_Select a scenario, sub-scenario, and file first._"

    filepath = os.path.join(ROOT_PATH, scenario, sub, filename)
    if not os.path.exists(filepath):
        return no_update, no_update, f"**File not found:** `{filepath}`"

    with open(filepath, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)

    elements = build_cytoscape_elements(graph_data)
    n_models = len(graph_data['models'])
    n_conns = len(graph_data['connections'])
    n_const = sum(1 for c in graph_data['connections']
                  if c.get('connection_type') == 'constant')

    info = (
        f"**Loaded:** `{scenario}/{sub}/{filename}`\n\n"
        f"**{n_models}** models, **{n_conns}** connections"
    )
    if n_const:
        info += f" ({n_const} constant)"
    info += "\n\n_Click a model or connection to inspect it._"
    return graph_data, elements, info


# --- Node tap: show model details ---
@app.callback(
    Output("detail-panel", "children", allow_duplicate=True),
    Input("cytoscape", "tapNodeData"),
    State("graph-store", "data"),
    prevent_initial_call=True,
)
def display_node_details(node_data, graph_data):
    if not node_data or not graph_data:
        return no_update

    name = node_data['id']

    # Find model info
    model_info = None
    for m in graph_data['models']:
        if m['name'] == name:
            model_info = m
            break

    if not model_info:
        # Likely a constant sentinel node — find its connections
        const_conns = [c for c in graph_data['connections']
                       if c['source'] == name and c.get('connection_type') == 'constant']
        if const_conns:
            md = f"## Constant: `{name}`\n\n"
            md += f"**Value:** `{const_conns[0].get('constant_value')}`\n\n"
            md += "**Connected to:**\n"
            for c in const_conns:
                md += f"- `{c['target']}.{c['attr_in']}`\n"
            return md
        return f"_Node `{name}` not found in graph data._"

    inputs = model_info.get('inputs', [])
    outputs = model_info.get('outputs', [])
    delta_t = model_info.get('delta_t')
    docstring = model_info.get('docstring', '')
    params = model_info.get('params')

    # Format delta_t
    if delta_t is None:
        dt_str = "event-based"
    elif delta_t >= 3600:
        dt_str = f"{delta_t}s ({delta_t/3600:.1f}h)"
    elif delta_t >= 60:
        dt_str = f"{delta_t}s ({delta_t/60:.0f}min)"
    else:
        dt_str = f"{delta_t}s"

    # Build markdown
    md = f"## {name}\n\n"
    md += f"**Class:** `{model_info.get('class', '?')}`  \n"
    md += f"**Module:** `{model_info.get('module', '?')}`  \n"
    md += f"**Δt:** {dt_str}\n\n"

    if params:
        md += "**Parameters:**\n"
        for k, v in params.items():
            md += f"- `{k}`: `{v}`\n"
        md += "\n"

    if inputs:
        md += "**Inputs:**\n"
        for inp in inputs:
            md += f"- `{inp}`\n"
        md += "\n"
    else:
        md += "**Inputs:** _(none)_\n\n"

    if outputs:
        md += "**Outputs:**\n"
        for out in outputs:
            md += f"- `{out}`\n"
        md += "\n"
    else:
        md += "**Outputs:** _(none)_\n\n"

    # Find connections involving this model
    incoming = []
    outgoing = []
    for conn in graph_data['connections']:
        if conn['target'] == name:
            incoming.append(conn)
        if conn['source'] == name:
            outgoing.append(conn)

    if incoming:
        md += "**Incoming connections:**\n"
        for c in incoming:
            ct = c.get('connection_type', 'data')
            ts = " ⏱️" if c.get('time_shifted') else ""
            if ct == 'execution_order':
                md += f"- ← `{c['source']}` _(exec order only)_{ts}\n"
            elif ct == 'constant':
                md += f"- ← const `{c.get('constant_value')}` → `{c['attr_in']}`\n"
            else:
                md += f"- `{c['source']}.{c['attr_out']}` → `{c['attr_in']}`{ts}\n"
        md += "\n"

    if outgoing:
        md += "**Outgoing connections:**\n"
        for c in outgoing:
            ct = c.get('connection_type', 'data')
            ts = " ⏱️" if c.get('time_shifted') else ""
            if ct == 'execution_order':
                md += f"- → `{c['target']}` _(exec order only)_{ts}\n"
            else:
                md += f"- `{c['attr_out']}` → `{c['target']}.{c['attr_in']}`{ts}\n"
        md += "\n"

    if docstring:
        md += "---\n\n"
        md += "### Documentation\n\n"
        md += docstring + "\n"

    return md


# --- Edge tap: show connection details ---
@app.callback(
    Output("detail-panel", "children", allow_duplicate=True),
    Input("cytoscape", "tapEdgeData"),
    prevent_initial_call=True,
)
def display_edge_details(edge_data):
    if not edge_data:
        return no_update

    src = edge_data['source']
    tgt = edge_data['target']
    conns = json.loads(edge_data.get('connections', '[]'))

    md = f"## {src} → {tgt}\n\n"
    md += f"**{len(conns)}** connection(s)\n\n"

    md += "| # | Output | Input | Type | Time-shifted |\n"
    md += "|---|--------|-------|------|--------------|\n"

    for i, c in enumerate(conns, 1):
        ct = c.get('connection_type', 'data')
        if ct == 'execution_order':
            md += f"| {i} | — | — | exec order | — |\n"
        elif ct == 'constant':
            val = c.get('constant_value', '?')
            md += f"| {i} | `{val}` | `{c['attr_in']}` | constant | — |\n"
        else:
            ts = "⏱️ yes" if c.get('time_shifted') else "no"
            md += f"| {i} | `{c['attr_out']}` | `{c['attr_in']}` | data | {ts} |\n"

    md += "\n\n"

    # Legend
    md += "---\n"
    md += "**Legend:**  \n"
    md += "🟢 Same-time data connection  \n"
    md += "🔴 Time-shifted connection (⏱️ dashed)  \n"
    md += "🟡 Constant connection  \n"
    md += "⚫ Execution-order only (dotted)  \n"

    return md


# =====================
# Run
# =====================
if __name__ == '__main__':
    app.run(debug=True, port=8051)
