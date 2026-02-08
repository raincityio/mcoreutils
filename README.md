# mcutils

Collection of utilities for meshcore.

## Overview

I started the utilities here because I originally wanted a way of creating maps with locations for meshcore
endpoints from the CLI. I continued to expand that utility for no particularly good reason to take on more
commands.

## Features

- mcutils: CLI utility for basic meshcore commands and map creator.
- mc-serial-tcp-server: tcp server for proxying meshcore serial devices.
    - I wrote this so I could use a serial meshcore device amongst multiple processes.

## Installation

### Requirements

- python >= 3.13

### Install

```bash
python3 -mvenv ~/mcutils
~/mcutils/bin/pip install .
```

## Configuration

See examples for example configurations.

## Example

To run mcutils against a specific device

```bash
~/mcutils/bin/mcutils -c ~/mcutils-heltec.yml self-info
```

To run a tcpserver over a serial device

```bash
~/mcutils/bin/mc-serial-tcp-server -c ~/tcpserver.yml
```