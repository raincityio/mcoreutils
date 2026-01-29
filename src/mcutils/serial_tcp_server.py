import argparse
import asyncio
import dataclasses
import logging
from asyncio import StreamReader, StreamWriter, TaskGroup
from pathlib import Path
from typing import Any

import platformdirs
import yaml
from meshcore import SerialConnection

default_config_path = platformdirs.user_config_path("mcutils.tcp_server.yaml")
default_host = "localhost"
default_port = 1234
SIGNATURE = b"\x01\x03      mccli"


@dataclasses.dataclass(frozen=True)
class Config:
    serial_device_path: Path
    host: str = default_host
    port: int = default_port
    baudrate: int = 115200
    loglevel: int = logging.INFO
    check_signature: bool = True

    @staticmethod
    def from_data(data: dict[str, Any]):
        kwargs = data.copy()
        if "serial_device_path" in data:
            kwargs["serial_device_path"] = Path(data["serial_device_path"])
        if "loglevel" in data:
            kwargs["loglevel"] = logging.getLevelName(data["loglevel"])  # pyright: ignore [reportDeprecated]
        if "listen" in data:
            kwargs["listen"] = tuple(data["listen"])
        return Config(**kwargs)


async def read_frame(reader: StreamReader):
    byte0 = await reader.read(1)
    if not byte0:
        return None
    data_sz_bytes = await reader.read(2)
    if not data_sz_bytes:
        return None
    data_sz = int.from_bytes(data_sz_bytes, byteorder="little")
    data = await reader.read(data_sz)
    if not data:
        return None
    return data


class Fanout:
    def __init__(self):
        self.writers = dict[str, asyncio.StreamWriter]()

    def write(self, data: bytes):
        for writer in self.writers.values():
            writer.write(data)

    def add(self, addr: str, writer: asyncio.StreamWriter):
        self.writers[addr] = writer

    def remove(self, addr: str):
        self.writers.pop(addr)


async def run_server(config: Config, connection: SerialConnection, fanout: Fanout):
    async def handler(reader: StreamReader, writer: StreamWriter):
        addr = writer.get_extra_info("peername")
        fanout.add(addr, writer)
        try:
            if config.check_signature:
                sig_test = await read_frame(reader)
                if sig_test != SIGNATURE:
                    raise Exception(f"Invalid signature: {sig_test}")
                await connection.send(sig_test)  # pyright: ignore [reportUnknownMemberType]
            while True:
                data = await read_frame(reader)
                if not data:
                    break
                await connection.send(data)  # pyright: ignore [reportUnknownMemberType]
        except Exception as e:
            logging.error(e)
        finally:
            fanout.remove(addr)
            writer.close()

    server = await asyncio.start_server(handler, host=config.host, port=config.port)
    await server.serve_forever()


async def process_frames(frame_q: asyncio.Queue[bytes], fanout: Fanout):
    while True:
        frame = await frame_q.get()
        logging.debug(f"frame: {frame}")
        # TODO I don't know what the first byte is, does it matter?
        fanout.write(b"?")
        data_sz = len(frame).to_bytes(2, byteorder="little")
        fanout.write(data_sz)
        fanout.write(frame)


async def amain():
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

    frame_q = asyncio.Queue[bytes]()
    fanout = Fanout()

    port = str(config.serial_device_path)
    connection = SerialConnection(port, baudrate=config.baudrate)
    try:

        async def disconnect_handler(reason: str):
            logging.info(f"Serial Disconnected: {reason}")
            main_task.cancel()

        connection.set_disconnect_callback(disconnect_handler)  # pyright: ignore [reportUnknownMemberType]

        class Reader:
            @staticmethod
            async def handle_rx(_frame: bytes):
                frame_q.put_nowait(_frame)

        connection.set_reader(Reader())  # pyright: ignore [reportUnknownMemberType]
        await connection.connect()

        async with TaskGroup() as g:
            g.create_task(run_server(config, connection, fanout))
            g.create_task(process_frames(frame_q, fanout))
    finally:
        await connection.disconnect()


def main():
    asyncio.run(amain())
