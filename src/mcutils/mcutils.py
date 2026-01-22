#!/usr/bin/env python3
import argparse
import asyncio
import dataclasses
from pathlib import Path

from meshcore import MeshCore

default_serial_device_path = Path("/dev/cu.usbmodem2301")


@dataclasses.dataclass(frozen=True)
class Config:
    serial_device_path: Path = default_serial_device_path


async def get_meshcore(config: Config):
    return await MeshCore.create_serial(str(config.serial_device_path))


async def create_map(config: Config, meshcore: MeshCore, *, output_path: Path):
    print(output_path)


async def amain():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparser = subparsers.add_parser("create-map")
    subparser.add_argument("-o", type=Path, help="Output file path", required=True)
    args = parser.parse_args()

    config = Config()

    if args.command is None:
        parser.print_help()
    elif args.command == "create-map":
        meshcore = await get_meshcore(config)
        await create_map(config, meshcore, output_path=args.o)
    else:
        raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(amain())
