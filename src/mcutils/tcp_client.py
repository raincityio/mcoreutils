import argparse
import asyncio
import dataclasses
import logging
from asyncio import Task
from pathlib import Path
from typing import Any

import meshcore
import platformdirs
import yaml
from meshcore.events import Event, EventType

from mcutils.common import jout

default_config_path = platformdirs.user_config_path("mcutils.tcp_client.yaml")


@dataclasses.dataclass(frozen=True)
class Config:
    # serial_device_path: Path = default_serial_device_path
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
    # mc = await meshcore.MeshCore.create_serial(str(config.serial_device_path))
    mc = await meshcore.MeshCore.create_tcp("localhost", 1234)

    async def disconnect_cb(_event: Event):
        logging.info(f"TCP Disconnected: {_event}")
        task.cancel()

    mc.subscribe(EventType.DISCONNECTED, disconnect_cb)

    return mc


async def serve():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", metavar="config_path", type=Path, default=default_config_path)
    parser.add_argument("-d", action="store_true", help="debug")
    subparsers = parser.add_subparsers(action="command")
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
    logging.debug(f"config_data: {config_data}")

    main_task = asyncio.current_task()
    assert main_task is not None
    meshcore = await get_meshcore(config, task=main_task)

    print(meshcore)
    ev = await meshcore.commands.get_contacts()
    jout(ev)


def main():
    asyncio.run(serve())
