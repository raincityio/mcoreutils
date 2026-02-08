#!/usr/bin/env python3
import argparse
import asyncio
import dataclasses
import enum
import logging
from pathlib import Path
from typing import Any, Optional

import folium
import platformdirs
import yaml
from meshcore import MeshCore, EventType
from meshcore.events import Event

from mcoreutils.common import jout

default_config_path = platformdirs.user_config_path("mcoreutils.yaml")
default_mc_endpoint = (
    "localhost",
    1234,
)
MAX_CHANNEL_IDX = 40


class MeshCoreDriver(enum.Enum):
    TCP = "tcp"
    SERIAL = "serial"


@dataclasses.dataclass(frozen=True)
class Config:
    driver: MeshCoreDriver = MeshCoreDriver.TCP
    serial_device_path: Optional[Path] = None
    mc_endpoint: tuple[str, int] = default_mc_endpoint
    loglevel: int = logging.INFO
    subscribe_resolve_event: bool = True

    @staticmethod
    def from_data(data: dict[str, Any]):
        kwargs = data.copy()
        if "loglevel" in data:
            kwargs["loglevel"] = logging.getLevelName(data["loglevel"])  # pyright: ignore [reportDeprecated]
        if "mc_endpoint" in data:
            kwargs["mc_endpoint"] = tuple(data["mc_endpoint"])
        if "serial_device_path" in data:
            kwargs["serial_device_path"] = Path(data["serial_device_path"])
        if "driver" in data:
            kwargs["driver"] = MeshCoreDriver(data["driver"])
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


async def subscribe(config: Config, meshcore: MeshCore, *, xfilter: Optional[str] = None):
    event_q = asyncio.Queue[Event]()

    def callback(_event: Event):
        event_q.put_nowait(_event)

    subscription = meshcore.dispatcher.subscribe(None, callback)  # pyright: ignore [reportUnknownMemberType]
    try:
        while True:
            event = await event_q.get()
            if config.subscribe_resolve_event:
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


async def resolve_public_key(meshcore: MeshCore, *, public_key: Optional[str] = None, name: Optional[str] = None):
    if name is not None:
        await meshcore.ensure_contacts()
        contact = meshcore.get_contact_by_name(name)
        if contact is None:
            raise Exception(f"Unknown contact: {name}")
        public_key = contact["public_key"]
        assert public_key is not None
        return public_key
    if public_key is not None:
        return public_key
    raise Exception("Missing destination key")


async def resolve_channel_idx(meshcore: MeshCore, *, channel_idx: Optional[int] = None, channel_name: Optional[str] = None):
    if channel_idx is not None:
        return channel_idx
    assert channel_name is not None
    i = 0
    while i <= MAX_CHANNEL_IDX:
        channel = await meshcore.commands.get_channel(i)
        test_channel_name = channel.payload["channel_name"]
        if test_channel_name == "":
            break
        if test_channel_name == channel_name:
            return channel.payload["channel_idx"]
        i += 1
    return None


async def send_msg(meshcore: MeshCore, message: str, *, public_key: Optional[str] = None, name: Optional[str] = None):
    public_key = await resolve_public_key(meshcore, public_key=public_key, name=name)
    return await meshcore.commands.send_msg(public_key, message)


async def remove_contact(meshcore: MeshCore, *, public_key: Optional[str] = None, name: Optional[str] = None):
    public_key = await resolve_public_key(meshcore, public_key=public_key, name=name)
    return await meshcore.commands.remove_contact(public_key)


async def amain():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", metavar="config_path", type=Path, default=default_config_path)
    parser.add_argument("-d", action="store_true", help="enable debug")
    subparsers = parser.add_subparsers(dest="command")
    subparser = subparsers.add_parser("create-map", help="Create an html map of device contact locations")
    subparser.add_argument("-o", metavar="output_path", type=Path, help="Output file path", required=True)
    subparser = subparsers.add_parser("subscribe", help="Subscribe to device events")
    subparser.add_argument("--xfilter")
    subparser = subparsers.add_parser("remove-contact", help="Remove a contact from the device")
    subparser.add_argument("-n", metavar="name")
    subparser.add_argument("--public-key")
    subparsers.add_parser("self-info", help="Show information about the device")
    subparsers.add_parser("reboot")
    subparsers.add_parser("get-contacts", help="Get device contacts")
    subparser = subparsers.add_parser("send-msg", help="Send a message")
    subparser.add_argument("-n", metavar="name")
    subparser.add_argument("--public-key")
    subparser.add_argument("-m", metavar="message", required=True)
    subparsers.add_parser("get-msg", help="Get a message")
    subparser = subparsers.add_parser("get-channel", help="Get channel info")
    subparser.add_argument("--channel-name", metavar="channel_name", type=str)
    subparser.add_argument("--channel-idx", metavar="channel_index", type=int)
    subparser = subparsers.add_parser("send-chan-msg", help="Send a channel message")
    subparser.add_argument("--channel-name", metavar="channel_name", type=str)
    subparser.add_argument("--channel-idx", metavar="channel_index", type=int)
    subparser.add_argument("-m", metavar="message", required=True)
    subparser = subparsers.add_parser("set-channel", help="Set channel")
    subparser.add_argument("--channel-idx", metavar="channel_index", type=int, required=True)
    subparser.add_argument("--channel-name", metavar="channel_name", type=str, required=True)
    subparser = subparsers.add_parser("remove-channel", help="Remove channel")
    subparser.add_argument("--channel-name", metavar="channel_name", type=str)
    subparser.add_argument("--channel-idx", metavar="channel_index", type=int)
    subparsers.add_parser("get-channels", help="Get channels")
    subparser = subparsers.add_parser("export-contact", help="Export contact information")
    subparser.add_argument("-n", metavar="name")
    subparser.add_argument("--public-key")
    subparser = subparsers.add_parser("import-contact", help="Import contact information")
    subparser.add_argument("--uri", required=True)
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
        if config.driver == MeshCoreDriver.TCP:
            return await MeshCore.create_tcp(  # pyright: ignore [reportUnknownMemberType]
                config.mc_endpoint[0], config.mc_endpoint[1], auto_reconnect=True, max_reconnect_attempts=999
            )
        elif config.driver == MeshCoreDriver.SERIAL:
            return await MeshCore.create_serial(str(config.serial_device_path))  # pyright: ignore [reportUnknownMemberType]
        else:
            raise Exception(f"Unknown driver {config.driver}")

    if args.command is None:
        parser.print_help()
    elif args.command == "create-map":
        meshcore = await get_meshcore()
        await create_map(meshcore, output_path=args.o)
    elif args.command == "subscribe":
        meshcore = await get_meshcore()
        await subscribe(config, meshcore, xfilter=args.xfilter)
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
    elif args.command == "send-msg":
        meshcore = await get_meshcore()
        jout(await send_msg(meshcore, message=args.m, public_key=args.public_key, name=args.n))
    elif args.command == "get-msg":
        meshcore = await get_meshcore()
        jout(await meshcore.commands.get_msg())
    elif args.command == "send-chan-msg":
        meshcore = await get_meshcore()
        channel_idx = await resolve_channel_idx(meshcore, channel_name=args.channel_name, channel_idx=args.channel_idx)
        if channel_idx is None:
            raise Exception(f"Channel not found")
        jout(await meshcore.commands.send_chan_msg(channel_idx, args.m))  # pyright: ignore [reportUnknownMemberType]
    elif args.command == "set-channel":
        meshcore = await get_meshcore()
        jout(await meshcore.commands.set_channel(args.channel_idx, args.channel_name))
    elif args.command == "get-channel":
        meshcore = await get_meshcore()
        channel_idx = await resolve_channel_idx(meshcore, channel_name=args.channel_name, channel_idx=args.channel_idx)
        if channel_idx is None:
            raise Exception(f"Channel not found")
        jout(await meshcore.commands.get_channel(channel_idx))
    elif args.command == "get-channels":
        meshcore = await get_meshcore()
        channels: list[Event] = []
        for i in range(MAX_CHANNEL_IDX):
            channel = await meshcore.commands.get_channel(i)
            if channel.payload["channel_name"] != "":
                channels.append(channel)
        jout(channels)
    elif args.command == "remove-channel":
        meshcore = await get_meshcore()
        channel_idx = await resolve_channel_idx(meshcore, channel_name=args.channel_name, channel_idx=args.channel_idx)
        if channel_idx is None:
            raise Exception(f"Channel not found")
        await meshcore.commands.set_channel(channel_idx, "", bytes.fromhex(16 * "00"))
    elif args.command == "export-contact":
        meshcore = await get_meshcore()
        if args.public_key or args.n:
            public_key = await resolve_public_key(meshcore, public_key=args.public_key, name=args.n)
        else:
            public_key = None
        contact = await meshcore.commands.export_contact(key=public_key)
        jout(contact)
    elif args.command == "import-contact":
        meshcore = await get_meshcore()
        uri = args.uri
        meshcore_uri_prefix = "meshcore://"
        if uri.startswith(meshcore_uri_prefix):
            card_data = bytes.fromhex(uri[len(meshcore_uri_prefix) :])
            result = await meshcore.commands.import_contact(card_data)  # pyright: ignore [reportUnknownMemberType]
            jout(result)
        else:
            raise Exception()
    else:
        raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(amain())
