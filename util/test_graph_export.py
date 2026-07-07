"""Tests for util.graph_export — export of SimPlEC graphs to JSON."""

import json
import os
import tempfile

import pytest
from simplec import Simulation, capture_params

from util.graph_export import export_simulation_graph


# ---------------------------------------------------------------------------
# Minimal mock models (duck-typed SimPlEC interface)
# ---------------------------------------------------------------------------

class Source:
    """A source model producing P_out."""
    name = 'source'
    inputs: list[str] = []
    outputs = ['P_out']
    delta_t = 60

    def step(self, time):
        return {'P_out': 1.0}


class Sink:
    """A sink model consuming P_in (single input)."""
    name = 'sink'
    inputs = ['P_in']
    outputs = ['Q_out']
    delta_t = 60

    def step(self, time, P_in=0):
        return {'Q_out': P_in * 2}


class Aggregator:
    """Aggregator with a multi-input P_ (trailing underscore)."""
    name = 'aggregator'
    inputs = ['P_']
    outputs = ['P_total']
    delta_t = 60

    def step(self, time, P_=None):
        return {'P_total': sum(P_ or [])}


class EventModel:
    """Event-based model (delta_t=None)."""
    name = 'event_model'
    inputs = ['trigger']
    outputs = ['result']
    delta_t = None

    def step(self, time, trigger=0):
        return {'result': trigger}


class Isolated:
    """A model with no connections — just sits in the graph."""
    name = 'isolated'
    inputs: list[str] = []
    outputs: list[str] = []
    delta_t = 60

    def step(self, time):
        return {}


@capture_params
class ParamModel:
    """A model using the capture_params decorator."""
    name = 'param_model'
    inputs: list[str] = []
    outputs = ['out']
    delta_t = 60

    def __init__(self, name, capacity=100, efficiency=0.95):
        self.name = name
        self.capacity = capacity
        self.efficiency = efficiency

    def step(self, time):
        return {'out': self.capacity}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _export_and_load(sim) -> dict:
    """Export graph to a temp file, read it back, return parsed JSON."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'sub', 'graph.json')
        export_simulation_graph(sim, path)
        assert os.path.isfile(path)
        with open(path, 'r') as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGraphExport:

    def test_basic_two_models(self):
        """Simple source → sink connection."""
        sim = Simulation()
        src = Source()
        snk = Sink()
        sim.add_model(src)
        sim.add_model(snk)
        sim.connect(src, snk, ('P_out', 'P_in'))

        data = _export_and_load(sim)

        assert len(data['models']) == 2
        names = {m['name'] for m in data['models']}
        assert names == {'source', 'sink'}

        data_conns = [c for c in data['connections']
                      if c['connection_type'] == 'data']
        assert len(data_conns) == 1
        c = data_conns[0]
        assert c['source'] == 'source'
        assert c['target'] == 'sink'
        assert c['attr_out'] == 'P_out'
        assert c['attr_in'] == 'P_in'
        assert c['time_shifted'] is False

    def test_time_shifted_connection(self):
        """Time-shifted connections are flagged correctly."""
        sim = Simulation()
        src = Source()
        snk = Sink()
        sim.add_model(src)
        sim.add_model(snk)
        sim.connect(src, snk, ('P_out', 'P_in'),
                    time_shifted=True, init_values={'P_out': 0.0})

        data = _export_and_load(sim)
        data_conns = [c for c in data['connections']
                      if c['connection_type'] == 'data']
        c = data_conns[0]
        assert c['time_shifted'] is True

    def test_multi_input(self):
        """Multiple sources feeding into a multi-input (P_)."""
        sim = Simulation()
        src1 = Source()
        src1.name = 'source_1'
        src2 = Source()
        src2.name = 'source_2'
        agg = Aggregator()
        sim.add_model(src1)
        sim.add_model(src2)
        sim.add_model(agg)
        sim.connect(src1, agg, ('P_out', 'P_'))
        sim.connect(src2, agg, ('P_out', 'P_'))

        data = _export_and_load(sim)

        data_conns = [c for c in data['connections']
                      if c['connection_type'] == 'data']
        assert len(data_conns) == 2
        sources = {c['source'] for c in data_conns}
        assert sources == {'source_1', 'source_2'}
        for c in data_conns:
            assert c['attr_in'] == 'P_'
            assert c['attr_out'] == 'P_out'

    def test_connect_constant_included(self):
        """connect_constant entries now appear as constant connections."""
        sim = Simulation()
        snk = Sink()
        sim.add_model(snk)
        sim.connect_constant(42.0, snk, 'P_in')

        data = _export_and_load(sim)

        assert len(data['models']) == 1  # only real models
        const_conns = [c for c in data['connections']
                       if c['connection_type'] == 'constant']
        assert len(const_conns) == 1
        c = const_conns[0]
        assert c['target'] == 'sink'
        assert c['attr_in'] == 'P_in'
        assert c['constant_value'] == 42.0

    def test_connect_nothing(self):
        """connect_nothing creates an execution_order connection."""
        sim = Simulation()
        src = Source()
        iso = Isolated()
        sim.add_model(src)
        sim.add_model(iso)
        sim.connect_nothing(src, iso)

        data = _export_and_load(sim)

        exec_conns = [c for c in data['connections']
                      if c['connection_type'] == 'execution_order']
        assert len(exec_conns) == 1
        c = exec_conns[0]
        assert c['source'] == 'source'
        assert c['target'] == 'isolated'

    def test_event_model_delta_t_none(self):
        """Event-based models (delta_t=None) are exported correctly."""
        sim = Simulation()
        em = EventModel()
        sim.add_model(em)

        data = _export_and_load(sim)
        model = data['models'][0]
        assert model['name'] == 'event_model'
        assert model['delta_t'] is None

    def test_model_metadata(self):
        """Model metadata (class, module, docstring) is captured."""
        sim = Simulation()
        src = Source()
        sim.add_model(src)

        data = _export_and_load(sim)
        model = data['models'][0]
        assert model['class'] == 'Source'
        assert 'source model' in model['docstring'].lower()
        assert model['inputs'] == []
        assert model['outputs'] == ['P_out']
        assert model['delta_t'] == 60

    def test_isolated_model(self):
        """A model with no connections is still exported."""
        sim = Simulation()
        iso = Isolated()
        sim.add_model(iso)

        data = _export_and_load(sim)
        assert len(data['models']) == 1
        assert data['models'][0]['name'] == 'isolated'
        assert len(data['connections']) == 0

    def test_json_is_human_readable(self):
        """Exported JSON is indented (human-readable)."""
        sim = Simulation()
        src = Source()
        sim.add_model(src)

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'graph.json')
            export_simulation_graph(sim, path)
            with open(path, 'r') as f:
                raw = f.read()
            assert '\n' in raw  # indented, not single-line
            assert '  ' in raw  # has indentation

    def test_creates_parent_directories(self):
        """Parent directories are created if they don't exist."""
        sim = Simulation()
        sim.add_model(Source())

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a', 'b', 'c', 'graph.json')
            export_simulation_graph(sim, path)
            assert os.path.isfile(path)

    def test_capture_params(self):
        """Models with @capture_params have params in the export."""
        sim = Simulation()
        pm = ParamModel('test_pm', capacity=200, efficiency=0.9)
        sim.add_model(pm)

        data = _export_and_load(sim)
        model = data['models'][0]
        assert model['params'] is not None
        assert model['params']['capacity'] == 200
        assert model['params']['efficiency'] == 0.9
        assert model['params']['name'] == 'test_pm'

    def test_no_capture_params(self):
        """Models without @capture_params have params=None."""
        sim = Simulation()
        src = Source()
        sim.add_model(src)

        data = _export_and_load(sim)
        model = data['models'][0]
        assert model['params'] is None
