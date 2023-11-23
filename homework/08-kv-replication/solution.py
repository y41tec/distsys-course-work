import hashlib
import uuid
from dslabmp import Context, Message, Process
from typing import List

ROUND_TRIP = 2
N = 3


class StorageNode(Process):
    def __init__(self, node_id: str, nodes: List[str]):
        self._id = node_id
        self._nodes = nodes
        self._data = {}
        self._events = {}

    def on_local_message(self, msg: Message, ctx: Context):
        if msg.type == "GET" or msg.type == "PUT" or msg.type == "DELETE":
            replicas = get_key_replicas(msg["key"], len(self._nodes))
            id = str(uuid.uuid4())
            time = ctx.time()

            msg["id"] = id
            msg["time"] = time
            quorum = msg["quorum"]
            msg.remove("quorum")

            self._events[id] = {
                "type": msg.type,
                "data": msg._data,
                "quorum": quorum,
                "local_send": False,
                "resp": {},
                "handoff": get_next_replica(int(replicas[-1]), len(self._nodes))
            }
            for replica in replicas:
                ctx.send(msg, replica)
            ctx.set_timer(id, ROUND_TRIP)

    def on_message(self, msg: Message, sender: str, ctx: Context):
        if msg.type == "UPDATE":
            for key, (time, value) in msg["data"].items():
                if self._data.get(key, (float("-inf"), "")) < (time, value):
                    self._data[key] = (time, value)
            resp_msg = Message("ACK", {"id": msg["id"]})
            ctx.send(resp_msg, sender)
        
        elif msg.type == "ACK":
            self._events[msg["id"]]["update"].remove(sender)

        elif msg.type in ["GET_RESP", "PUT_RESP", "DELETE_RESP"]:
            event = self._events[msg["id"]]
            if event["resp"].get(sender, (float("-inf"), "")) <= (msg["time"], msg["value"]):
                event["resp"][sender] = (msg["time"], msg["value"])
            sorted_resps = sorted(list(event["resp"].items()), key=lambda x: (x[1], x[0]), reverse=True)
            _, actual_item = sorted_resps[0]
            for resp_id, resp_item in sorted_resps:
                if resp_item < actual_item:
                    event["resp"].pop(resp_id)
                    if msg.type == "GET_RESP" or msg.type == "PUT_RESP":
                        resp_msg = Message("PUT", msg._data)
                        resp_msg["time"], resp_msg["value"] = actual_item
                    else:
                        resp_msg = Message("DELETE", msg._data)
                    ctx.send(resp_msg, resp_id)      
            if len(event["resp"]) >= event["quorum"] and not event["local_send"]:
                actual_time, actual_value = actual_item
                ctx.send_local(Message(f"{event['type']}_RESP", {"key": msg["key"], "value": actual_value if actual_value else None}))
                event["local_send"] = True

        elif msg.type in ["GET", "PUT", "DELETE"]:
            replicas = get_key_replicas(msg["key"], len(self._nodes))
            if self._id in replicas:
                data = self._data
            else:
                id = str(hash("".join(replicas)))
                if id not in self._events:
                    self._events[id] = {
                        "type": "UPDATE",
                        "data": {},
                        "update": set(replicas)
                    }
                data = self._events[id]["data"]
                ctx.set_timer(id, ROUND_TRIP)

            if msg.type == "GET":
                resp_msg = Message("GET_RESP", msg._data)
                resp_msg["time"], resp_msg["value"] = data.get(msg["key"], (float("-inf"), ""))
                ctx.send(resp_msg, sender)

            elif msg.type == "PUT":
                resp_msg = Message("PUT_RESP", msg._data)
                if data.get(msg["key"], (float("-inf"), "")) < (msg["time"], msg["value"]):
                    data[msg["key"]] = (msg["time"], msg["value"])
                resp_msg["time"], resp_msg["value"] = data[msg["key"]]
                ctx.send(resp_msg, sender)

            elif msg.type == "DELETE":
                resp_msg = Message("DELETE_RESP", msg._data)
                time, value = data.get(msg["key"], (float("-inf"), ""))
                if time < msg["time"]:
                    data[msg["key"]] = (msg["time"], "")
                    resp_msg["value"] = value
                ctx.send(resp_msg, sender)

    def on_timer(self, timer_name: str, ctx: Context):
        event = self._events[timer_name]
        if event["type"] in ["GET", "PUT", "DELETE"]:
            if len(event["resp"]) == N:
                self._events.pop(timer_name)
                return

            resp_msg = Message(event["type"], event["data"])
            ctx.send(resp_msg, str(event["handoff"]))
            event["handoff"] = get_next_replica(event["handoff"], len(self._nodes))

        elif event["type"] == "UPDATE":
            if len(event["update"]) == 0:
                self._events.pop(timer_name)
                return

            for update_id in event["update"]:
                resp_msg = Message(event["type"], {"id": timer_name, "data": event["data"]})
                ctx.send(resp_msg, update_id)

        ctx.set_timer(timer_name, ROUND_TRIP)


def get_key_replicas(key: str, node_count: int):
    replicas = []
    key_hash = int.from_bytes(hashlib.md5(key.encode("utf8")).digest(), "little", signed=False)
    cur = key_hash % node_count
    for _ in range(N):
        replicas.append(str(cur))
        cur = get_next_replica(cur, node_count)
    return replicas


def get_next_replica(i: int, node_count: int):
    return (i + 1) % node_count
