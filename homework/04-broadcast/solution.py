from collections import defaultdict
from dslabmp import Context, Message, Process
from typing import Dict, List, Set


class BroadcastProcess(Process):
    def __init__(self, proc_id: str, processes: List[str]):
        self._id = proc_id
        self._processes = processes
        self._messages_bc = defaultdict(set)
        self._messages_d = set()

    def on_local_message(self, msg: Message, ctx: Context):
        if msg.type == 'SEND':
            bcast_msg = Message('BCAST', {
                'text': msg['text']
            })
            self.best_effort_broadcast(bcast_msg, ctx)
            self._messages_bc[msg['text']].add(self._id)
    
    def best_effort_broadcast(self, msg: Message, ctx: Context):
        for proc in self._processes:
            ctx.send(msg, proc)

    def on_message(self, msg: Message, sender: str, ctx: Context):
        if msg.type == 'BCAST':
            self._messages_bc[msg['text']].add(sender)
            if self._id not in self._messages_bc[msg['text']]:
                self.best_effort_broadcast(msg, ctx)
                self._messages_bc[msg['text']].add(self._id)

            if msg['text'] not in self._messages_d and len(self._messages_bc[msg['text']]) * 2 >= len(self._processes):
                deliver_msg = Message('DELIVER', {
                    'text': msg['text']
                })
                ctx.send_local(deliver_msg)
                self._messages_d.add(msg['text'])

    def on_timer(self, timer_name: str, ctx: Context):
        pass
