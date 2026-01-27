import asyncio

import grpc

from mcutils import meshcore_pb2, meshcore_pb2_grpc


async def run():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = meshcore_pb2_grpc.MeshCoreStub(channel)

        response = await stub.get_contacts(meshcore_pb2.GetContactsRequest())
        print(response.contacts[0])


def main():
    asyncio.run(run())
