from collections import defaultdict
from dslabmp import Context, Message, Process
from typing import List


class BroadcastProcess(Process):
    def __init__(self, proc_id: str, processes: List[str]):
        self._processes = {processes[id]: id for id in range(len(processes))}
        self._id = self._processes[proc_id]
        self._counter = 0

        self._state = [0 for _ in range(len(processes))]
        self._messages_deliver = set()
        self._messages_buffer = defaultdict()
        self._messages_broadcasters = defaultdict(set)

    def on_local_message(self, msg: Message, ctx: Context):
        if msg.type == "SEND":
            bcast_msg = Message(
                "BCAST",
                {
                    "text": msg["text"],
                    "sender": self._id,
                    "counter": self._counter,
                    "state": self._state,
                },
            )
            self.best_effort_broadcast(bcast_msg, ctx)
            self._counter += 1

    def best_effort_broadcast(self, msg: Message, ctx: Context):
        for proc in self._processes.keys():
            ctx.send(msg, proc)

    def on_message(self, msg: Message, sender: str, ctx: Context):
        if msg.type == "BCAST":
            message_hash = (msg["sender"], msg["counter"])
            self._messages_broadcasters[message_hash].add(self._processes[sender])
            if self._id not in self._messages_broadcasters[message_hash]:
                self.best_effort_broadcast(msg, ctx)
                self._messages_broadcasters[message_hash].add(self._id)

            if message_hash not in self._messages_deliver and len(
                self._messages_broadcasters[message_hash]
            ) * 2 >= len(self._processes):
                if self.is_casually_ordered(msg):
                    self.deliver_message(msg, ctx)
                    self.update_deliver(ctx)
                else:
                    self._messages_buffer[message_hash] = msg

    def is_casually_ordered(self, msg: Message):
        sender = msg["sender"]
        counter = msg["counter"]
        state = msg["state"]
        return counter == self._state[sender] and all(
            state[i] <= self._state[i] for i in range(len(self._state))
        )

    def deliver_message(self, msg: Message, ctx: Context):
        message_hash = (msg["sender"], msg["counter"])
        self._state[msg["sender"]] = msg["counter"] + 1
        self._messages_deliver.add(message_hash)
        self._messages_broadcasters.pop(message_hash)
        deliver_msg = Message("DELIVER", {"text": msg["text"]})
        ctx.send_local(deliver_msg)

    def update_deliver(self, ctx):
        is_update = True
        while is_update:
            is_update = False
            delivered = []
            for message_hash, msg in self._messages_buffer.items():
                if self.is_casually_ordered(msg):
                    delivered.append(message_hash)
                    self.deliver_message(msg, ctx)
                    is_update = True
            for message_hash in delivered:
                self._messages_buffer.pop(message_hash)

    def on_timer(self, timer_name: str, ctx: Context):
        pass
