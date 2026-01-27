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
from meshcore import SerialConnection
from meshcore.events import Event

default_config_path = platformdirs.user_config_path("mcutils.tcp_server.yaml")
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
    mc = await meshcore.MeshCore.create_serial(str(config.serial_device_path))

    async def disconnect_cb(_event: Event):
        logging.info(f"Serial Disconnected: {_event}")
        task.cancel()

    mc.subscribe(EventType.DISCONNECTED, disconnect_cb)

    return mc


async def serve():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", metavar="config_path", type=Path, default=default_config_path)
    parser.add_argument("-d", action="store_true", help="debug")
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
    mc = await get_meshcore(config, main_task)

    # @classmethod
    # async def create_serial(
    #     cls,
    #     port: str,
    #     baudrate: int = 115200,
    #     debug: bool = False,
    #     only_error: bool = False,
    #     default_timeout=None,
    #     auto_reconnect: bool = False,
    #     max_reconnect_attempts: int = 3,
    #     cx_dly: float = 0.1,
    # ) -> "MeshCore":
    #     """Create and connect a MeshCore instance using serial connection"""
    port = str(config.serial_device_path)
    baudrate: int = 115200
    cx_dly: float = 0.1
    connection = SerialConnection(port, baudrate, cx_dly=cx_dly)

    frame_q = asyncio.Queue[bytes]()

    class Reader:
        async def handle_rx(self, frame: bytes):
            frame_q.put_nowait(frame)

    connection.set_reader(Reader())
    await connection.connect()

    while True:
        frame = await frame_q.get()
        print(frame)


def main():
    asyncio.run(serve())
