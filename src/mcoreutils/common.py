import json
from typing import Any

from meshcore.events import Event, EventType


def object_hook(data: Any):
    if "_type" in data:
        _type = data["_type"]
        if _type == "Event":
            event_type = data["value"]["type"]
            event_payload = data["value"]["payload"]
            event_attributes = data["value"].get("attributes", None)
            return Event(event_type, event_payload, event_attributes)
        elif _type == "EventType":
            return getattr(EventType, data["value"])
        elif _type == "bytes":
            return bytes.fromhex(data["value"])
        else:
            raise Exception(f"Unknown event type: {_type}")
    return data


class JSONEncoder(json.JSONEncoder):
    def default(self, o: Any):
        if isinstance(o, Event):
            data = {
                "type": o.type,
                "payload": o.payload,
                "attributes": o.attributes,
            }
            return {"_type": "Event", "value": data}
        elif isinstance(o, EventType):
            return {"_type": "EventType", "value": o.name}
        elif isinstance(o, bytes):
            return {"_type": "bytes", "value": o.hex()}
        return super().default(o)


class PrettyJSONEncoder(json.JSONEncoder):
    def default(self, o: Any):
        if isinstance(o, Event):
            data = {
                "type": o.type,
                "payload": o.payload,
                "attributes": o.attributes,
            }
            return data
        elif isinstance(o, EventType):
            return o.name
        elif isinstance(o, bytes):
            return o.hex()
        return super().default(o)


def jdump(o: Any):
    return json.dumps(o, cls=JSONEncoder)


def jout(o: Any):
    print(json.dumps(o, cls=PrettyJSONEncoder, indent=2))


def jload(o: Any):
    return json.loads(o, object_hook=object_hook)
