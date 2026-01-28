#!/usr/bin/env python3
import argparse
import asyncio
import dataclasses
import logging
from asyncio import Task
from pathlib import Path
from typing import Any, Optional

import folium
import platformdirs
import yaml
from meshcore import MeshCore, EventType
from meshcore.events import Event

from mcutils.common import jout

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


async def get_meshcore(config: Config, task: Task[Any]):
    # meshcore = await MeshCore.create_serial(str(config.serial_device_path))
    meshcore = await MeshCore.create_tcp("localhost", 1234, auto_reconnect=True, max_reconnect_attempts=999)

    # async def disconnect_cb(_event: Event):
    #     logging.info(f"Serial Disconnected: {_event}")
    #     task.cancel()
    #
    # meshcore.subscribe(EventType.DISCONNECTED, disconnect_cb)

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


async def subscribe(meshcore: MeshCore, *, xfilter: Optional[str] = None):
    callback_f = asyncio.Future[None]()

    def callback(_event: Event):
        try:
            if xfilter:
                _env = {"event": _event, "EventType": EventType}
                _valid = eval(xfilter, None, _env)
            else:
                _valid = True
            # print(_event)
            # print(type(_event))
            if _valid:
                print(_event)
                jout(_event)
        except Exception as e:
            if callback_f.done():
                logging.exception(e)
            else:
                callback_f.set_exception(e)

    subscription = meshcore.dispatcher.subscribe(None, callback)
    try:
        await callback_f
    finally:
        subscription.unsubscribe()


async def samf(meshcore: MeshCore):
    try:

        async def callback(_event: Event):
            jout(_event)

        meshcore.subscribe(EventType.CHANNEL_MSG_RECV, callback)
        meshcore.subscribe(EventType.CONTACT_MSG_RECV, callback)
        await meshcore.start_auto_message_fetching()
        await asyncio.Event().wait()
    finally:
        await meshcore.stop_auto_message_fetching()


async def remove_contact(meshcore: MeshCore, *, name: str):
    await meshcore.ensure_contacts()
    contact = meshcore.get_contact_by_name(name)
    print(contact)


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
    subparser = subparsers.add_parser("remove-contact")
    subparser.add_argument("-n", metavar="name")
    subparser = subparsers.add_parser("self-info")
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
    elif args.command == "remove-contact":
        meshcore = await get_meshcore(config, main_task)
        await remove_contact(meshcore, name=args.n)
    elif args.command == "self-info":
        meshcore = await get_meshcore(config, main_task)
        jout(meshcore.self_info)
    else:
        raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(amain())
