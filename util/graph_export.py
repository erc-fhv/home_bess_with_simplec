"""
Export a SimPlEC Simulation graph to a human-readable JSON file.

Uses the ``sim.get_topology()`` public API (SimPlEC >= v1.2) to obtain
a complete, JSON-serializable representation of models and connections.

Usage
-----
>>> from util.graph_export import export_simulation_graph
>>> export_simulation_graph(sim, 'data/graph/my_scenario/sub/20260101_1200.json')
"""

import json
from pathlib import Path

from simplec import Simulation


def export_simulation_graph(sim: Simulation, filepath: str) -> None:
    """Serialize the simulation graph to a JSON file.

    Parameters
    ----------
    sim : Simulation
        A fully wired SimPlEC simulation (after all add_model / connect calls).
    filepath : str
        Destination path for the JSON file.  Parent directories are created
        automatically.
    """
    topology = sim.get_topology()

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(topology, f, indent=2, ensure_ascii=False)
