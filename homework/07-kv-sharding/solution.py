from collections import deque
from dslabmp import Context, Message, Process
from typing import Dict, List


class KeyStore:
    def __init__(self, keys: List[str], mod: int = 10000007):
        self._m = mod
        self._d = deque(sorted(list((self._get_hash(key), key) for key in keys)))

    def _get_hash(self, key: str):
        return hash(key) % self._m

    def _bin_search(self, key_hash: int, l: int, r: int):
        if r == l:
            return r
        m = (l + r) // 2 + 1
        if self._d[m][0] > key_hash:
            return self._bin_search(key_hash, l, m - 1)
        return self._bin_search(key_hash, m, r)

    def get_index_by_key(self, key: str, key_add: bool = False):
        key_hash = self._get_hash(key)
        if key_hash < self._d[0][0]:
            if key_add:
                return -1
            else:
                return len(self._d) - 1
        l = 0
        r = len(self._d) - 1
        return self._bin_search(key_hash, l, r)

    def get_closest_key(self, key: str):
        index = self.get_index_by_key(key)
        return self._d[index][1]

    def add_key(self, key: str):
        el = (self._get_hash(key), key)
        index = self.get_index_by_key(key, key_add=True)
        self._d.insert(index + 1, el)

    def remove_key(self, key: str):
        el = (self._get_hash(key), key)
        index = self.get_index_by_key(key)
        if self._d[index] != el:
            return
        self._d.remove(el)

    def split_by_key(self, data: Dict[str, str], from_key: str, split_key: str):
        split_key_hash = self._get_hash(split_key)
        from_key_hash = self._get_hash(from_key)
        l = {}
        r = {}
        for key, value in data.items():
            key_hash = self._get_hash(key)
            if from_key_hash <= key_hash and key_hash < split_key_hash:
                l[key] = value
            elif from_key == self._d[-1][1] and (key_hash >= from_key_hash or key_hash < split_key_hash):
                l[key] = value
            else:
                r[key] = value
        return l, r


class StorageNode(Process):
    def __init__(self, node_id: str, nodes: List[str]):
        self._id = node_id
        self._nodes = KeyStore(nodes)
        self._data = dict()

    def on_local_message(self, msg: Message, ctx: Context):
        if msg.type == "GET" or msg.type == "PUT" or msg.type == "DELETE":
            reciever = self._nodes.get_closest_key(msg["key"])
            ctx.send(msg, reciever)
        elif msg.type == "NODE_ADDED":
            add_id = msg["id"]
            if self._id == add_id:
                return
            prev_add_id = self._nodes.get_closest_key(add_id)
            self._nodes.add_key(add_id)
            if self._id == prev_add_id:
                self._data, update_data = self._nodes.split_by_key(self._data, self._id, add_id)
                response = Message("UPDATE", {"data": update_data})
                ctx.send(response, add_id)
        elif msg.type == "NODE_REMOVED":
            remove_id = msg["id"]
            self._nodes.remove_key(remove_id)
            if self._id == remove_id:
                response = Message("UPDATE", {"data": self._data})
                ctx.send(response, self._nodes.get_closest_key(remove_id))
        elif msg.type == "COUNT_RECORDS":
            resp = Message("COUNT_RECORDS_RESP", {"count": len(self._data)})
            ctx.send_local(resp)
        elif msg.type == "DUMP_KEYS":
            resp = Message("DUMP_KEYS_RESP", {"keys": list(self._data.keys())})
            ctx.send_local(resp)

    def on_message(self, msg: Message, sender: str, ctx: Context):
        if msg.type == "GET":
            key = msg["key"]
            value = self._data.get(key, None)
            response = Message("GET_RESP", {"key": key, "value": value})
            ctx.send(response, sender)
        elif msg.type == "PUT":
            key = msg["key"]
            value = msg["value"]
            self._data[key] = value
            response = Message("PUT_RESP", {"key": key, "value": value})
            ctx.send(response, sender)
        elif msg.type == "DELETE":
            key = msg["key"]
            value = self._data.pop(key, None)
            response = Message("DELETE_RESP", {"key": key, "value": value})
            ctx.send(response, sender)
        elif (
            msg.type == "GET_RESP"
            or msg.type == "PUT_RESP"
            or msg.type == "DELETE_RESP"
        ):
            ctx.send_local(msg)
        elif msg.type == "UPDATE":
            self._data.update(msg["data"])

    def on_timer(self, timer_name: str, ctx: Context):
        pass
