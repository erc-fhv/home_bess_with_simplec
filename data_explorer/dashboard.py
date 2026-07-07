import os
from pathlib import Path
import json
import copy
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import dash
from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc

# =====================
# Config
# =====================
ROOT_PATH = "./data/output"
CONFIG_DIR = "./.configs"
N_PLOTS = 3

os.makedirs(CONFIG_DIR, exist_ok=True)

AXIS_ROWS = [f"Plot {i+1}" for i in range(N_PLOTS)]
AXIS_SIDE_MAP = {"primary": "Left", "secondary": "Right"}

SIDEBAR_WIDTH = '40%'


def make_empty_cfg():
    return {
                'scenario_path': None,
                'available_cols': [], # list[list[str]] # tuples would not be preserved in json
                "plots": [
                    {
                        side: {
                            "traces": [],
                            "label": ''
                            } for side in ("left", "right")
                    }
                    for _ in range(N_PLOTS)
                ]
            }

def make_empty_figure():
    return make_subplots(
        rows=N_PLOTS,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        specs=[[{"secondary_y": True}] for _ in range(N_PLOTS)],
    )

# =====================
# App
# =====================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP]
)
app.title = "Simulation Dashboard"

# =====================
# Layout
# =====================
app.layout = html.Div([

    dbc.Button("Open Config", id="open-offcanvas", className="m-2"),

    dbc.Offcanvas(
        [
            dbc.Switch(id='pin-offcanvas-btn', label='Pin Configuration', value=False),
            dbc.Container([
                dbc.Row([
                    dbc.Col(html.H5("Scenario Selection"), width="auto"),
                    dbc.Col(
                        dbc.Button(
                            "Refresh Data",
                            id="refresh-data-btn",
                            color="secondary",
                            outline=True,
                            size="sm",
                            className="mb-2",
                        ),
                        width="auto",
                        className="ms-auto",
                    ),
                ], className="align-items-center mb-2"),
                dcc.Dropdown(id="scenario-dd", placeholder="Scenario", className="mb-2"),
                dcc.Dropdown(id="subscenario-dd", placeholder="Sub-scenario", className="mb-2"),
                dcc.Dropdown(id="timestamp-dd", placeholder="Execution time", className="mb-2"),
                dbc.InputGroup([
                    dbc.Input(
                        value='.../.../...', id='scenario-name-text',
                        disabled=True, valid=False, invalid=True),
                    dbc.Button("Load Scenario", id='load_scenario_btn', disabled=True),
                ], className="mb-2"),
                html.Hr(),

                html.H5("Axes Configuration"),

                dbc.Row([
                    dbc.Col(width=1),
                    dbc.Col([
                        dcc.Tabs(id="tabs-y-axis", value='left', vertical=False,
                            children=[
                                dcc.Tab(label='Primary', value='left'),
                                dcc.Tab(label='Secondary', value='right')
                        ])
                    ])
                ]),
                dbc.Row([
                    dbc.Col([
                        dcc.Tabs(id="tabs-axis", value='0', vertical=True,
                            # style={'align': 'center', 'justify': 'center', 'height':'100%'},
                            children=[dcc.Tab(label=str(i+1), value=str(i),) for i in range(N_PLOTS)
                            ])
                    ], width=1),
                    dbc.Col([
                        dbc.Container(id='tabs-content', class_name='mb-2',
                            children=[
                            html.H5(id='tabs-heading-txt', className="mt-3"),
                            dbc.InputGroup([
                                dbc.InputGroupText('Axis Label'),
                                dbc.Input('label-input', placeholder='Axis Label'),
                                dbc.Button('Apply', id='apply-label_btn')
                            ], className="mb-2"),
                            dbc.InputGroup([
                                dbc.InputGroupText('Add Trace'),
                                dbc.Select(id="model-dd", placeholder="Model"),
                                dbc.Select(id="io-dd", placeholder="I/O", style={'width':'floating'}),
                                dbc.Select(id="value-dd", placeholder="Value"),
                                dbc.Button("Apply", id="add-trace-btn", color="primary"),
                            ], className="mb-2"),
                            dbc.ListGroup(id="selected-traces-div")
                            # dbc.InputGroup([
                            #     dbc.InputGroupText('Traces'),
                            #     dbc.ListGroup(id="selected-traces-div", flush=True),
                            # ], style={'min-height':'40pt'}, className="mb-2"),
                        ]),
                    ]),
                ]),

                html.Hr(),

                html.H5("Save or Load"),
                dbc.InputGroup([
                    dbc.Input(id="config-name", placeholder="Config name"),
                    dbc.Button("Save Config", id="save-config-btn")
                ],
                className="mb-2"
                ),
                dbc.InputGroup([
                    dbc.Select(id="load-config-dd", placeholder="Select config to load"),
                    dbc.Button("Load Config", id="load-config-btn", color="secondary"),
                    dbc.Button("× Delete Config", id="delete-config-bt", color="danger")
                ],
                className="mb-2"
                ),

            ], fluid=True),
        ],
        id="offcanvas",
        title="Configuration",
        placement="start",
        scrollable=True,
        is_open=True,
        backdrop=False,
        style={'width': SIDEBAR_WIDTH},
    ),

    dcc.Graph(id="graph", style={'right-margin':'0', 'height':'90vh'}, figure=make_empty_figure()),
            #   config = {'editable': True}), # TODO: implement editable and make it work with config
    dcc.Store(
        id="config-store",
        data=make_empty_cfg()
    )
])

# =====================
# Helpers
# =====================
def scan_dirs(path):
    return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))) if os.path.exists(path) else []

def scan_parquet(path):
    if not os.path.exists(path):
        return []
    return [
        {'label': f[:4] + '-' + f[4:6] + '-' + f[6:8] + ' ' + f[9:11] + ':' + f[11:13],
         'value': f}
        for f in sorted(os.listdir(path)) if f.endswith(".parquet")
        ]

####################
# Offcanvas
####################
@app.callback(
    Output('offcanvas', 'backdrop'),
    Output('graph', 'style'),
    Input('offcanvas', 'is_open'),
    Input('pin-offcanvas-btn', 'value'),
    State('graph', 'style'),
)
def pin_unpin_config_offcanvas(is_open, active, style):
    style = style.copy() if style else {}
    style['margin-left']  = SIDEBAR_WIDTH if active and is_open else 0
    return not active, style

@app.callback(
    Output("offcanvas", "is_open"),
    Input("open-offcanvas", "n_clicks"),
    State("offcanvas", "is_open"),
)
def toggle_offcanvas(n, is_open):
    return not is_open if n else is_open


####################
# Scenario Selection
####################
@app.callback(
    Output("scenario-dd", "options"),
    Input("scenario-dd", "id"),
    Input("refresh-data-btn", "n_clicks"),
)
def load_scenarios(_, __):
    return [{"label": s, "value": s} for s in scan_dirs(ROOT_PATH)]

@app.callback(
    Output("subscenario-dd", "options"),
    Input("scenario-dd", "value"),
    Input("refresh-data-btn", "n_clicks"),
    State("scenario-dd", "value"),
)
def load_subscenario(scenario, __, scenario_state):
    scenario = scenario or scenario_state
    return [{"label": s, "value": s}
            for s in scan_dirs(os.path.join(ROOT_PATH, scenario))] if scenario else []

@app.callback(
    Output("timestamp-dd", "options"),
    Input("subscenario-dd", "value"),
    Input("refresh-data-btn", "n_clicks"),
    State("scenario-dd", "value"),
    State("subscenario-dd", "value"),
)
def load_timestamps(sub, __, scenario, sub_state):
    sub = sub or sub_state
    if not scenario or not sub:
        return []
    return scan_parquet(os.path.join(ROOT_PATH, scenario, sub))

@app.callback(
    Output("scenario-name-text", "value"),
    Output("scenario-name-text", "valid"),
    Output("scenario-name-text", "invalid"),
    Output("load_scenario_btn", "disabled"),

    Input("scenario-dd", "value"),
    Input("subscenario-dd", "value"),
    Input("timestamp-dd", "value"),
    Input("config-store", "data"),

    State("scenario-name-text", "value"),
)
def display_path(scen, sub, ts, cfg, path):
    cfg = copy.deepcopy(cfg)
    trig = ctx.triggered_id

    if trig == "config-store":
        new_path = cfg['scenario_path']
        if new_path is not None:
            return new_path, True, False, True
        else:
            return '.../.../...', False, True, True

    pathlist = [
        scen if scen is not None else '...',
        sub if sub is not None else '...',
        ts if ts is not None else '...',
    ]

    new_path = '/'.join(pathlist)
    if all(p != '...' for p in pathlist):
        return new_path, False, False, False
    else:
        return new_path, False, True, True

###################
# Axis Config
###################
@app.callback(Output('tabs-heading-txt', 'children'),
              Input('tabs-axis', 'value'),
              Input('tabs-y-axis', 'value'),
              )
def render_tab_heading(xaxis_name, yaxis_name):
    return f"Edit axis {int(xaxis_name) + 1} - {yaxis_name}"

@app.callback(Output('label-input', 'value'),
            #   Input("load-config-btn", "n_clicks"),
              Input('tabs-axis', 'value'),
              Input('tabs-y-axis', 'value'),
              State("config-store", "data"),
              )
def update_label_input_value_on_tab_change(row, side, cfg):
    row = int(row)
    return cfg["plots"][row][side]['label']

@app.callback(
    Output("model-dd", "options"),
    Output("model-dd", "value"),
    Input("config-store", "data"),
)
def load_models(cfg):
    models = {c[0] for c in cfg['available_cols']} # unique
    return [{"label": c, "value": c} for c in models], None

@app.callback(
    Output("io-dd", "options"),
    Output("io-dd", "value"),
    Input("model-dd", "value"),
    Input("config-store", "data"),
)
def load_io(model, cfg):
    if not model:
        return [], None
    io = {c[1] for c in cfg['available_cols'] if c[0] == model} # unique
    return [{"label": c, "value": c} for c in io], None

@app.callback(
    Output("value-dd", "options"),
    Output("value-dd", "value"),
    Input("model-dd", "value"),
    Input("io-dd", "value"),
    Input("config-store", "data"),
)
def load_values(model, io, cfg):
    if not all([model, io]):
        return [], None
    return [{"label": c[2], "value": c[2]} for c in cfg['available_cols'] if c[0] == model and c[1] == io], None

@app.callback(
    Output("selected-traces-div", "children"),
    Input("config-store", "data"),
    Input("tabs-axis", "value"),
    Input("tabs-y-axis", "value"),
)
def show_traces(cfg, row, side):
    row = int(row)
    return [
        dbc.ListGroupItem([
            '.'.join(c),
            dbc.Button("×", id={"type": "delete-btn", "index": i},
                       size="sm", color="danger")
        ],
        className="d-flex justify-content-between",)
        for i, c in enumerate(cfg['plots'][row][side]["traces"])
    ]


####################
# Config handling
####################
@app.callback(
    Output("config-store", "data"),

    Input("add-trace-btn", "n_clicks"),
    Input({"type": "delete-btn", "index": dash.ALL}, "n_clicks"),
    Input('apply-label_btn', 'n_clicks'),
    Input("load_scenario_btn", "n_clicks"),
    Input("save-config-btn", "n_clicks"),
    Input("load-config-btn", "n_clicks"),


    State("load-config-dd", "value"), # load_conf_name
    State("config-name", "value"), # save_conf_name
    State("scenario-name-text", "value"),  # scen_path
    State("tabs-axis", "value"), # row
    State("tabs-y-axis", "value"), # side
    State('label-input', 'value'), # label
    State("model-dd", "value"), # model
    State("io-dd", "value"), # io
    State("value-dd", "value"), # value
    State("config-store", "data"), # cfg
    prevent_initial_call=True
)
def update_config(
    _, delete_btn_n_clicks, ___, ____, _____, ______,
    load_conf_name, save_conf_name,
    scen_path, row, side,
    label, model, io, value, cfg
):
    cfg = copy.deepcopy(cfg)
    row = int(row)
    trig = ctx.triggered_id
    # CONFIGURE PATH
    if trig == "load_scenario_btn": # can only be clicked if valid path is provided (so no validation here)
        cfg['scenario_path'] = scen_path
        cols = pd.read_parquet(Path(ROOT_PATH + '/'+ cfg["scenario_path"])).columns
        cfg['available_cols'] = cols

    # ADD TRACE
    elif trig == "add-trace-btn":
        if all([model, io, value]):
            col = [model, io, value]
            if col not in cfg["plots"][row][side]['traces'] and col in cfg['available_cols']:
                cfg["plots"][row][side]['traces'].append(col)

    # DELETE TRACE
    elif (isinstance(trig, dict) and trig.get("type") == "delete-btn"
          and delete_btn_n_clicks[trig["index"]] is not None): # prevent calls on creation of button when switching tabs
        idx = trig["index"]
        if idx < len(cfg["plots"][row][side]['traces']):
            cfg["plots"][row][side]['traces'].pop(idx)

    # UPDATE LABEL
    elif trig == 'apply-label_btn':
        cfg["plots"][row][side]['label'] = label

    # SAVE CONFIG
    elif trig == "save-config-btn":
        path = os.path.join(CONFIG_DIR, f"{save_conf_name}.json")
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)

    # LOAD CONFIG
    elif trig == "load-config-btn":
        path = os.path.join(CONFIG_DIR, f"{load_conf_name}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                cfg = json.load(f)

    return cfg

# Populate available configs to load
@app.callback(
    Output("load-config-dd", "options"),
    Input("save-config-btn", "n_clicks"),
    Input("delete-config-bt", "n_clicks"),
)
def populate_load_configs(save_conf, delete_conf):
    if not os.path.exists(CONFIG_DIR):
        return []
    files = [
        f.replace(".json", "")
        for f in os.listdir(CONFIG_DIR)
    ]
    return [{"label": f, "value": f} for f in sorted(files)]

# delete config
@app.callback(
    Output("config-name", "value"),
    Input("delete-config-bt", "n_clicks"),
    State("load-config-dd", "value"),
    prevent_initial_call=True
)
def save_config(_, name):
    if not name:
        return ''
    if os.path.exists(CONFIG_DIR + f"/{name}.json"):
        os.remove(CONFIG_DIR + f"/{name}.json")
    return ''

####################
# Figure updating
####################
@app.callback(
    Output("graph", "figure"),
    Input("config-store", "data"),
)
def update_graph(cfg):
    # --------------------------------------------------
    # Create figure from scratch
    # --------------------------------------------------
    fig = make_empty_figure()

    # --------------------------------------------------
    # Resolve data path
    # --------------------------------------------------
    if not cfg["scenario_path"]:
        return fig  # empty figure if no scenario is selected
    data_path = Path(ROOT_PATH + '/'+ cfg["scenario_path"])

    # --------------------------------------------------
    # Populate subplots
    # --------------------------------------------------
    for row, plot_cfg in enumerate(cfg["plots"], start=1):

        for side in ("left", "right"):
            side_cfg = plot_cfg[side]
            columns = side_cfg["traces"]
            label = side_cfg["label"]

            secondary_y = (side == "right")

            # Axis label
            fig.update_yaxes(
                title_text=label,
                row=row,
                col=1,
                secondary_y=secondary_y,
            )

            # Traces
            for col in columns:
                series = pd.read_parquet(
                    data_path, columns=[str(tuple(col))]
                ).ffill() # TODO: make ffill optional
                fig.add_trace(
                    go.Scatter(
                        x=series.index,
                        y=series.values.T[0],
                        name=str('.'.join(col)),
                        showlegend=True,
                        line_shape='hv',
                        # legendgroup=row,
                    ),
                    row=row,
                    col=1,
                    secondary_y=secondary_y,
                )

    # --------------------------------------------------
    # Global layout tweaks (optional)
    # --------------------------------------------------
    # fig.update_layout(
    #     # margin=dict(l=60, r=60, t=40, b=40),
    #     # hovermode="x unified",
    # )

    return fig


# =====================
# Run
# =====================
if __name__ == "__main__":
    app.run(debug=False)
