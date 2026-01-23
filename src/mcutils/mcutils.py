#!/usr/bin/env python3
import argparse
import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Any

import folium
import platformdirs
import yaml
from meshcore import MeshCore

default_config_path = platformdirs.user_config_path("mcutils.yaml")
default_serial_device_path = Path("/dev/cu.usbmodem2301")


@dataclasses.dataclass(frozen=True)
class Config:
    serial_device_path: Path = default_serial_device_path
    loglevel: int = logging.INFO

    @staticmethod
    def from_data(data: dict[str, Any]):
        kwargs = data.copy()
        if "serial_device_path" in data:
            kwargs["serial_device_path"] = Path(data["serial_device_path"])
        if "loglevel" in data:
            kwargs["loglevel"] = logging.getLevelName(data["loglevel"])
        return Config(**kwargs)


async def get_meshcore(config: Config):
    return await MeshCore.create_serial(str(config.serial_device_path))


async def create_map(meshcore: MeshCore, *, output_path: Path):
    assert await meshcore.ensure_contacts()
    contacts = meshcore.contacts
    m = folium.Map(zoom_start=4)
    for contact_info in contacts.values():
        adv_name = contact_info["adv_name"]
        adv_lat = contact_info["adv_lat"]
        adv_lon = contact_info["adv_lon"]
        folium.CircleMarker(
            [float(adv_lat), float(adv_lon)],
            popup=adv_name,
            radius=4,
        ).add_to(m)
    m.save(output_path)


async def amain():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", metavar="config_path", type=Path, default=default_config_path)
    parser.add_argument("-d", action="store_true", help="enable debug")
    subparsers = parser.add_subparsers(dest="command")
    subparser = subparsers.add_parser("create-map")
    subparser.add_argument("-o", metavar="output_path", type=Path, help="Output file path", required=True)
    args = parser.parse_args()

    config_data: dict[str, Any]
    try:
        config_data = yaml.safe_load(args.c.read_text())
    except FileNotFoundError:
        config_data = {}
    if args.d:
        config_data["loglevel"] = "DEBUG"
    config = Config.from_data(config_data)
    logging.root.setLevel(config.loglevel)
    logging.debug(config)

    if args.command is None:
        parser.print_help()
    elif args.command == "create-map":
        meshcore = await get_meshcore(config)
        await create_map(meshcore, output_path=args.o)
    else:
        raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(amain())
