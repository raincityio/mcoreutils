# mcoreutils

Collection of utilities for meshcore.

## Overview

I started the utilities here because I originally wanted a way of creating maps with locations for meshcore
endpoints from the CLI. I continued to expand that utility for no particularly good reason to take on more
commands.

## Features

- mcore-cli: CLI utility for basic meshcore commands and map creator.
- mcore-tcp-bridge: tcp server for proxying meshcore serial devices.
    - I wrote this so I could use a serial meshcore device amongst multiple processes.

## Installation

### Requirements

- python >= 3.13

### Install

```bash
python3 -mvenv ~/mcoreutils
~/mcoreutils/bin/pip install .
```

## Configuration

See examples for example configurations.

## Example

To run mcore-cli against a specific device

```bash
~/mcoreutils/bin/mcore-cli -c ~/mcoreutils-heltec.yml self-info
```

Create a map from the contacts on your device

```bash
~/mcoreutils/bin/mcore-cli create-map -o /tmp/map.html
```

To run a tcpserver over a serial device

```bash
~/mcoreutils/bin/mcore-tcp-bridge -c ~/tcpserver.yml
```