#!/usr/bin/env python3
import argparse
import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import Any, Optional

import folium
import platformdirs
import yaml
from meshcore import MeshCore, EventType
from meshcore.events import Event

from mcutils.common import jout

default_config_path = platformdirs.user_config_path("mcutils.yaml")
default_mc_endpoint = (
    "localhost",
    1234,
)


@dataclasses.dataclass(frozen=True)
class Config:
    mc_endpoint: tuple[str, int] = default_mc_endpoint
    loglevel: int = logging.INFO

    @staticmethod
    def from_data(data: dict[str, Any]):
        kwargs = data.copy()
        if "loglevel" in data:
            kwargs["loglevel"] = logging.getLevelName(data["loglevel"])  # pyright: ignore [reportDeprecated]
        if "mc_endpoint" in data:
            kwargs["mc_endpoint"] = tuple(data["mc_endpoint"])
        return Config(**kwargs)


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
    m.save(output_path)  # pyright: ignore [reportUnknownMemberType]


# this is silly, but connected has a future in it, so...
async def resolve_event(event: Event):
    if event.type == EventType.CONNECTED:
        connection_info = event.payload["connection_info"]
        if type(connection_info) is asyncio.Future:
            event.payload["connection_info"] = await connection_info
    return event


async def subscribe(meshcore: MeshCore, *, xfilter: Optional[str] = None):
    event_q = asyncio.Queue[Event]()

    def callback(_event: Event):
        event_q.put_nowait(_event)

    subscription = meshcore.dispatcher.subscribe(None, callback)  # pyright: ignore [reportUnknownMemberType]
    try:
        while True:
            event = await event_q.get()
            event = await resolve_event(event)
            if xfilter:
                env = {"event": event, "EventType": EventType}
                valid = eval(xfilter, None, env)
            else:
                valid = True
            if valid:
                jout(event)
    finally:
        subscription.unsubscribe()


async def remove_contact(meshcore: MeshCore, *, public_key: Optional[str] = None, name: Optional[str] = None):
    if name is not None:
        await meshcore.ensure_contacts()
        contact = meshcore.get_contact_by_name(name)
        if contact is None:
            raise Exception(f"Unknown contact: {name}")
        public_key = contact["public_key"]
        assert public_key is not None
        return await meshcore.commands.remove_contact(public_key)
    if public_key is not None:
        return await meshcore.commands.remove_contact(public_key)
    raise Exception("Missing contact key")


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
    subparser = subparsers.add_parser("remove-contact")
    subparser.add_argument("-n", metavar="name")
    subparser.add_argument("--public-key")
    subparsers.add_parser("self-info")
    subparsers.add_parser("reboot")
    subparsers.add_parser("get-contacts")
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

    async def get_meshcore():
        return await MeshCore.create_tcp(  # pyright: ignore [reportUnknownMemberType]
            config.mc_endpoint[0], config.mc_endpoint[1], auto_reconnect=True, max_reconnect_attempts=999
        )

    if args.command is None:
        parser.print_help()
    elif args.command == "create-map":
        meshcore = await get_meshcore()
        await create_map(meshcore, output_path=args.o)
    elif args.command == "subscribe":
        meshcore = await get_meshcore()
        await subscribe(meshcore, xfilter=args.xfilter)
    elif args.command == "remove-contact":
        meshcore = await get_meshcore()
        jout(await remove_contact(meshcore, public_key=args.public_key, name=args.n))
    elif args.command == "self-info":
        meshcore = await get_meshcore()
        jout(meshcore.self_info)
    elif args.command == "reboot":
        meshcore = await get_meshcore()
        jout(await meshcore.commands.reboot())
    elif args.command == "get-contacts":
        meshcore = await get_meshcore()
        jout(await meshcore.commands.get_contacts())
    else:
        raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(amain())
