import numpy as np
import pandas as pd
from model_archive.electricity_grid.electricity_grid_simple import Grid


def test_grid_initialization():
    grid = Grid('name')
    assert grid.name == 'name'
    assert grid.inputs == ['P_']
    assert grid.outputs == ['P_substation']
    assert grid.delta_t == 60

def test_grid_step():
    grid = Grid('name')
    inputs = {'P_': [2., 3.]}
    assert grid.step(1, **inputs)['P_substation'] == 5.