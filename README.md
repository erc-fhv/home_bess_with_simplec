# FlECs-Framework

This Framework can be used to simulate and assess different control strategies for flexibilities in energy systems in particular energy communities. It is written in python.
The underlying framework for the cosimulation is [SimPlEC](https://github.com/erc-fhv/SimPlEC/).

# Overview
The following figure shows the structure of the framework based on some example models and scenarios.
![Overview](doc/Overview.svg?raw=true "Overview")

# Getting startet
- create a venv with python 3.13
- install the requirements.txt
- execute one of the scenarios from the scenario directory

# File Structure

```
FlECs-Framework\
├── data (data for the models)\
├── doc (supplementary documentation of the framework)\
├── models (model directory)\
│   └── foo (a model directory)\
│       ├── foo.py (model logic)\
│       ├── foo_params.txt (parameter files of model foo, if required)\
│       ├── README.md (documentation of the model, optional)\
│       └── test_foo.py (pytests / unittests of the model, reccomended)\
├── output (output of the simulation)\
├── post (postprocessing and analysis)\
├── prep (preprocessing of data)\
├── scenarios (scenario directory)\
│   ├── scenario_bar.py\
│   └── scenario_baz.py\
└── util (utility files)\
```

# Naming Convention
All variable representing physical properties should be called with a physical, LaTex like, style. For example: P_el, E_bes, Q_dot_hp, ...
Other variables should be named descriptive according to python guidelines.
Model Classes should be named in camel case, instances can have the same name but lowercase. For Example
building = Building(...). Avoid appending 'Model' to the name.

# Unit Convention
All physical units which are passed in between models should be in their base SI unit with the exception of temperatures, which should be in °C. If this is for some reason impractical, the unit should be appended to the name such as P_el_in_kW or v_in_km_per_h.

# Sign Convention
All consumption from the grid (heat network, ... ) as seen form a component is positive (egoistic sign convention)...

# Git
Git LFS is used to track changes in the data/ folder, so it needs to be configured. See the docs https://git-lfs.com/
On Windows, git lfs should come with the standard git installation, on linux it can be installed via package manager (e.g. apt).

