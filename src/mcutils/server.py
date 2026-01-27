import argparse
import asyncio
import dataclasses
import logging
from asyncio import Task
from pathlib import Path
from typing import Any

import grpc
import meshcore
import platformdirs
import yaml
from meshcore import EventType, MeshCore
from meshcore.events import Event

from mcutils.meshcore_pb2 import Contact, GetContactsReply, GetContactsRequest
from . import meshcore_pb2_grpc

default_config_path = platformdirs.user_config_path("mcutils.server.yaml")
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


class MeshCoreService(meshcore_pb2_grpc.MeshCoreServicer):
    def __init__(self, meshcore: MeshCore):
        self.meshcore = meshcore

    async def get_contacts(self, request: GetContactsRequest, context: grpc.aio.ServicerContext):
        c = Contact(public_key="drew")
        return GetContactsReply(contacts=[c, c])


# class GreeterService(greeter_pb2_grpc.GreeterServicer):
#     async def SayHello(self, request, context):
#         return greeter_pb2.HelloReply(message=f"Hello, {request.name} (async)!")


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

    server = grpc.aio.server()
    meshcore_pb2_grpc.add_MeshCoreServicer_to_server(MeshCoreService(mc), server)

    server.add_insecure_port("[::]:50051")
    await server.start()
    print("Async gRPC server listening on :50051")

    await server.wait_for_termination()


def main():
    asyncio.run(serve())
