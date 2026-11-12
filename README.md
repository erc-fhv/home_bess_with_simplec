
# Overview

This repository contains the code for the co-simulation of a residential energy system consisting of a battery energy storage system (BESS) and a photovoltaic (PV) system. The simulation is built on top of the [SimPlEC](https://github.com/erc-fhv/SimPlEC/) framework and serves as the simulation environment used in our research on model predictive control (MPC) for residential battery systems.

# Related Paper and Citation

More information about the simulation models and the underlying framework can be found in our paper:

> [Real-World Model Predictive Control for Home Battery Systems: Towards Closing the Simulation-to-Reality Gap](https://dl.acm.org/doi/10.1145/3861130.3861140)

If you use this repository in your research, please cite:

```bibtex
@article{Moosbrugger2026,
  author = {Moosbrugger, Lukas and Seiler, Valentin and Wohlgenannt, Philipp and Kepplinger, Peter and Ristov, Sashko},
  title = {Real-World Model Predictive Control for Home Battery Systems: Towards Closing the Simulation-to-Reality Gap},
  year = {2026},
  issue_date = {September 2026},
  publisher = {Association for Computing Machinery},
  address = {New York, NY, USA},
  volume = {6},
  number = {3},
  doi = {10.1145/3861130.3861140},
}
````

# Getting Started

### Prerequisites

The following software must be installed:

- Git
- Git LFS
- Python 3.11
- A Python virtual environment (e.g. `venv`)

### Clone the Repository

```bash
git clone https://github.com/erc-fhv/home_bess_with_simplec.git
cd home_bess_with_simplec
```

### Install the Dependencies

Activate your virtual python 3.11 environment and then install:

```bash
pip install -e .
```

### Running the Simulation

Start the home BESS co-simulation with:

```bash
python scenarios/home_bess_simulation.py
```

### Reproducing the Paper Figures

To recreate the figures presented in the paper, activate the virtual environment and execute the notebook:

```
post/paper_plots.ipynb
```

# License

This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file for details.

# Acknowledgments

<a href="https://projekte.ffg.at/projekt/4597880">
  <img src="doc/FFG_Logo.png" alt="FFG Logo" width="180" align="right">
</a>

This work was supported by the **Austrian Research Promotion Agency (FFG)** through the **Hub4FlECs** project (COIN FFG 898053).

We gratefully acknowledge the financial support provided by the FFG, which enabled the development of the software contained in this repository.

Project page:
https://projekte.ffg.at/projekt/4597880
