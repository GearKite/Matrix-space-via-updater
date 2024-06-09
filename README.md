# Matrix space via updater

[![Built with matrix-nio](https://img.shields.io/badge/built%20with-matrix--nio-brightgreen)](https://github.com/poljar/matrix-nio)
[![license](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](https://github.com/matrix-nio/matrix-nio/blob/master/LICENSE.md)

Updates the [`via`](https://spec.matrix.org/v1.10/client-server-api/#mspacechild) server list for each room in a space.

Temporary™ solution to [one of the _potential_ issues](https://github.com/matrix-org/matrix-spec-proposals/blob/matthew/msc1772/proposals/1772-groups-as-rooms.md#potential-issues) of [MSC1772: Matrix spaces](https://github.com/matrix-org/matrix-spec-proposals/pull/1772).

## Prerequisites

- `Python >= 3.11`
- [Python Poetry](https://python-poetry.org/)

## Installation

1. Clone the git repository  
   `git clone https://github.com/GearKite/Matrix-space-via-updater.git`
2. Install dependencies:  
   `poetry install`

## Usage

1. Copy the configuration file  
   `cp config.toml.sample config.toml`
2. Modify the configuration to your liking
3. Run the script  
   `poetry run python3 main.py`
