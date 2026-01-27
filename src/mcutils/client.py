import argparse
import asyncio
import logging
from typing import Any

import grpc

from mcutils import meshcore_pb2, meshcore_pb2_grpc
from mcutils.common import jdump, jload, jout


async def run():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    subparser = subparsers.add_parser("get-contacts")
    subparser = subparsers.add_parser("subscribe")
    subparser = subparsers.add_parser("get-msg")
    subparser = subparsers.add_parser("get-channel")
    subparser.add_argument("--channel-idx", type=int, required=True)
    subparser = subparsers.add_parser("remove-contact")
    subparser.add_argument("--public-key", required=True)
    args = parser.parse_args()

    def event_to_event(event: meshcore_pb2.Event):
        return jload(event.json)

    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = meshcore_pb2_grpc.MeshCoreStub(channel)

        async def as_command(command: str, *args: Any, **kwargs: Any):
            xargs = jdump(args)
            xkwargs = jdump(kwargs)
            response = await stub.command(meshcore_pb2.CommandRequest(command=command, json_args=xargs, json_kwargs=xkwargs))
            print(jout(event_to_event(response.event)))

        if args.command is None:
            raise Exception("No command specified")
        elif args.command == "subscribe":
            async for event in stub.subscribe(meshcore_pb2.SubscribeRequest()):
                print(jdump(event_to_event(event)))
        elif args.command == "get-contacts":
            await as_command("get_contacts")
        elif args.command == "get-msg":
            await as_command("get_msg")
        elif args.command == "get-channel":
            await as_command("get_channel", args.channel_idx)
        elif args.command == "remove-contact":
            await as_command("remove_contact", args.public_key)
        else:
            raise Exception(f"Unknown command: {args.command}")


def main():
    asyncio.run(run())
