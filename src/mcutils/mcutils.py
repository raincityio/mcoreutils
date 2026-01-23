#!/usr/bin/env python3
import argparse
import asyncio
import dataclasses
import json
import logging
from asyncio import Task
from pathlib import Path
from typing import Any, Optional

import folium
import platformdirs
import yaml
from meshcore import MeshCore, EventType
from meshcore.events import Event

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


async def get_meshcore(config: Config, task: Task):
    meshcore = await MeshCore.create_serial(str(config.serial_device_path))

    async def disconnect_cb(_event: Event):
        logging.info(f"Serial Disconnected: {_event}")
        task.cancel()

    meshcore.subscribe(EventType.DISCONNECTED, disconnect_cb)

    return meshcore


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


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Event):
            data = {
                "type": o.type,
                "payload": o.payload,
                "attributes": o.attributes,
            }
            return data
        elif isinstance(o, EventType):
            return o.name
        super().default(o)


async def subscribe(meshcore: MeshCore, *, xfilter: Optional[str] = None):
    subscribe_task = asyncio.current_task(asyncio.get_event_loop())
    assert subscribe_task is not None

    def callback(_event: Event):
        if xfilter:
            _env = {"event": _event, "EventType": EventType}
            _valid = eval(xfilter, None, _env)
        else:
            _valid = True
        if _valid:
            print(json.dumps(_event, cls=JSONEncoder, indent=2))

    subscription = meshcore.dispatcher.subscribe(None, callback)
    try:
        await asyncio.Event().wait()
    finally:
        subscription.unsubscribe()


async def samf(meshcore: MeshCore):
    try:

        async def callback(_event: Event):
            print(json.dumps(_event, cls=JSONEncoder, indent=2))

        meshcore.subscribe(EventType.CHANNEL_MSG_RECV, callback)
        meshcore.subscribe(EventType.CONTACT_MSG_RECV, callback)
        await meshcore.start_auto_message_fetching()
        await asyncio.Event().wait()
    finally:
        await meshcore.stop_auto_message_fetching()


async def amain():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", metavar="config_path", type=Path, default=default_config_path)
    parser.add_argument("-d", action="store_true", help="enable debug")
    subparsers = parser.add_subparsers(dest="command")
    subparser = subparsers.add_parser("create-map")
    subparser.add_argument("-o", metavar="output_path", type=Path, help="Output file path", required=True)
    subparser = subparsers.add_parser("subscribe")
    subparser.add_argument("--xfilter")
    subparser = subparsers.add_parser("samf")

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

    main_task = asyncio.current_task(asyncio.get_event_loop())
    assert main_task is not None

    if args.command is None:
        parser.print_help()
    elif args.command == "samf":
        meshcore = await get_meshcore(config, main_task)
        await samf(meshcore)
    elif args.command == "create-map":
        meshcore = await get_meshcore(config, main_task)
        await create_map(meshcore, output_path=args.o)
    elif args.command == "subscribe":
        meshcore = await get_meshcore(config, main_task)
        await subscribe(meshcore, xfilter=args.xfilter)
    else:
        raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(amain())
