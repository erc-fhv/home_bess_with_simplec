# Home BESS Simulation with the SimPlEC Framework

## Overview

This repository contains the code for the co-simulation of a residential energy system consisting of a battery energy storage system (BESS) and a photovoltaic (PV) system. The simulation is built on top of the [SimPlEC](https://github.com/erc-fhv/SimPlEC/) framework and serves as the simulation environment used in our research on model predictive control (MPC) for residential battery systems.

## Related Paper and Citation

More information about the simulation models and the underlying framework can be found in our paper (currently available on arXiv):

> https://arxiv.org/abs/XXXX

If you use this repository in your research, or find it useful, please cite:

```bibtex
@article{moosbrugger2026real,
  title={Real-World Model Predictive Control for Home Battery Systems: Towards Closing the Simulation-to-Reality Gap},
  author={Moosbrugger, Lukas and Seiler, Valentin and Wohlgenannt, Philipp and Ristov, Sashko and Kepplinger, Peter},
  journal={arXiv preprint},
  year={2026},
  doi={10.48550/arXiv.XXX}
}
```

## Getting Started

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

## Running the Simulation

Start the home BESS co-simulation with:

```bash
python scenarios/home_bess_simulation.py
```

## Reproducing the Paper Figures

To recreate the figures presented in the paper, activate the virtual environment and execute the notebook:

```
post/paper_plots.ipynb
```

## License

This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file for details.

## Acknowledgments

<a href="https://projekte.ffg.at/projekt/4597880">
  <img src="FFG_Logo.png" alt="FFG Logo" width="180" align="right">
</a>

This work was supported by the **Austrian Research Promotion Agency (FFG)** through the **Hub4FlECs** project (COIN FFG 898053).

We gratefully acknowledge the financial support provided by the FFG, which enabled the development of the software contained in this repository.

Project page:
https://projekte.ffg.at/projekt/4597880