from random import randint

from dslabmp import Context, Message, Process


ROUND_TRIP = 1.1
PROCESS_TIME = 0.6
FANOUT = 8


class GroupMember(Process):
    def __init__(self, proc_id: str):
        self._id = proc_id
        self._joined = False
        self._active = dict()
        self._suspect = dict()

    def _choose_random_active(self):
        if len(self._active) == 0 or len(self._active) == 1:
            return self._id

        random = list(self._active.keys())[randint(0, len(self._active) - 1)]
        return random if random != self._id else self._choose_random_active()

    def _choose_random_suspect(self):
        if len(self._suspect) == 0:
            return self._id

        random = list(self._suspect.keys())[randint(0, len(self._suspect) - 1)]
        return random

    def on_local_message(self, msg: Message, ctx: Context):
        if msg.type == "JOIN":
            self._on_local_join(msg["seed"], ctx)
        elif msg.type == "LEAVE":
            self._on_local_leave(ctx)
        elif msg.type == "GET_MEMBERS":
            self._on_get_members(ctx)

    def _on_local_join(self, id: str, ctx: Context):
        self._joined = True
        self._active = dict()
        self._suspect = dict()

        if self._id == id:
            self._active[id] = 1
        else:
            join_message = Message("JOIN", {})
            ctx.send(join_message, id)
            ctx.set_timer_once(f"join_{id}", ROUND_TRIP)

        ctx.set_timer_once("ping_", ROUND_TRIP * 3 + PROCESS_TIME)

    def _on_local_leave(self, ctx: Context):
        random = self._choose_random_active()
        if random != self._id:
            leave_message = Message("LEAVE", {})
            ctx.send(leave_message, random)

        self._joined = False
        self._active = dict()
        self._suspect = dict()

    def _on_get_members(self, ctx: Context):
        ctx.send_local(Message("MEMBERS", {"members": list(self._active.keys())}))

    def _unexpected_init(self):
        if len(self._active) == 0:
            self._joined = True
            self._active = dict()
            self._suspect = dict()
            self._active[self._id] = 1

    def on_message(self, msg: Message, sender: str, ctx: Context):
        if msg.type == "JOIN":
            self._on_join(msg, sender, ctx)
        elif msg.type == "LEAVE":
            self._on_leave(sender)
        elif msg.type == "JOINREQ":
            self._on_joinreq(msg, sender, ctx)
        elif msg.type == "PING":
            self._on_ping(msg, sender, ctx)
        elif msg.type == "ACK":
            self._on_ack(msg, sender, ctx)

    def _on_join(self, msg: Message, sender: str, ctx: Context):
        self._unexpected_init()

        sender_version = 1
        if sender in self._active:
            self._active[sender] += 1
            sender_version = self._active[sender]
        elif sender in self._suspect:
            sender_version = abs(self._suspect.pop(sender)) + 1
            self._active[sender] = sender_version
        else:
            self._active[sender] = sender_version

        join_req_message = Message(
            "JOINREQ", {"active": self._active, "suspect": self._suspect}
        )
        ctx.send(join_req_message, sender)

    def _on_leave(self, sender: str):
        if sender in self._active:
            self._suspect[sender] = -1 * self._active.pop(sender)
        elif sender in self._suspect and self._suspect[sender] > 0:
            self._suspect[sender] *= -1

    def _on_joinreq(self, msg: Message, sender: str, ctx: Context):
        self._active = msg["active"]
        self._suspect = msg["suspect"]
        ctx.cancel_timer(f"join_{sender}")

    def _on_ping(self, msg: Message, sender: str, ctx: Context):
        if not self._joined:
            leave_message = Message("LEAVE", {})
            ctx.send(leave_message, sender)
            return

        self._merge(msg["active"], msg["suspect"])
        if msg["reciever"] == self._id:
            ack_message = Message(
                "ACK",
                {
                    "reciever": msg["sender"],
                    "active": self._active,
                    "suspect": self._suspect,
                },
            )
            ctx.send(ack_message, sender)
        else:
            ctx.send(msg, msg["reciever"])

    def _on_ack(self, msg: Message, sender: str, ctx: Context):
        if not self._joined or (
            sender not in self._active and sender not in self._suspect
        ):
            leave_message = Message("LEAVE", {})
            ctx.send(leave_message, sender)
            return

        self._merge(msg["active"], msg["suspect"])
        if msg["reciever"] == self._id:
            ctx.cancel_timer(f"pingfailed_{sender}")
            ctx.cancel_timer(f"pingthroufailed_{sender}")
        else:
            ctx.send(msg, msg["reciever"])

    def _merge(self, active, suspect):
        self._unexpected_init()

        if self._id in suspect:
            self._active[self._id] += 1

        for id, version in suspect.items():
            if (
                id in self._active
                and self._active[id] <= abs(version)
                and id != self._id
            ):
                self._active.pop(id)
                self._suspect[id] = version
            elif id in self._suspect and abs(self._suspect[id]) < abs(version):
                self._suspect[id] = version
            elif id not in self._active and id not in self._suspect and version > 0:
                self._suspect[id] = version

        for id, version in active.items():
            if id in self._active and self._active[id] < version:
                self._active[id] = version
            elif id in self._suspect and abs(self._suspect[id]) < version:
                self._suspect.pop(id)
                self._active[id] = version
            elif id not in self._active and id not in self._suspect:
                self._active[id] = version

    def on_timer(self, timer_name: str, ctx: Context):
        timer_type, id = timer_name.split("_")
        if timer_type == "join":
            if len(self._active) > 1:
                return
            join_message = Message("JOIN", {})
            ctx.send(join_message, id)
            ctx.set_timer_once(f"join_{id}", ROUND_TRIP)

        elif timer_type == "ping":
            ctx.set_timer_once("ping_", ROUND_TRIP * 3 + PROCESS_TIME)

            active_random = self._choose_random_active()
            if active_random != self._id:
                ping_message = Message(
                    "PING",
                    {
                        "sender": self._id,
                        "reciever": active_random,
                        "active": self._active,
                        "suspect": self._suspect,
                    },
                )
                ctx.send(ping_message, active_random)
                ctx.set_timer_once(f"pingfailed_{active_random}", ROUND_TRIP)

            suspect_random = self._choose_random_suspect()
            if suspect_random != self._id and self._suspect[suspect_random] > 0:
                ping_message = Message(
                    "PING",
                    {
                        "sender": self._id,
                        "reciever": suspect_random,
                        "active": self._active,
                        "suspect": self._suspect,
                    },
                )
                ctx.send(ping_message, suspect_random)

        elif timer_type == "pingfailed":
            for _ in range(min(FANOUT, len(self._active))):
                active_random = self._choose_random_active()
                if active_random != self._id:
                    ping_message = Message(
                        "PING",
                        {
                            "sender": self._id,
                            "reciever": id,
                            "active": self._active,
                            "suspect": self._suspect,
                        },
                    )
                    ctx.send(ping_message, active_random)
            ctx.set_timer_once(f"pingthroufailed_{id}", ROUND_TRIP * 2)

        elif timer_type == "pingthroufailed":
            if id in self._active:
                self._suspect[id] = self._active.pop(id)
