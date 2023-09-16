from dslabmp import Context, Message, Process


# AT MOST ONCE ---------------------------------------------------------------------------------------------------------

MESSAGE_ORDER_LIMIT_AMO = 3


class AtMostOnceSender(Process):
    def __init__(self, proc_id: str, receiver_id: str):
        self._id = proc_id
        self._receiver = receiver_id
        self._order = 0

    def on_local_message(self, msg: Message, ctx: Context):
        # receive message for delivery from local user
        msg["order"] = self._order
        ctx.send(msg, self._receiver)
        self._order += 1

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver here
        pass

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        pass


class AtMostOnceReceiver(Process):
    def __init__(self, proc_id: str):
        self._id = proc_id
        self._order_lower_bound = 0
        self._order_store = set()

    def on_local_message(self, msg: Message, ctx: Context):
        # not used in this task
        pass

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver
        # deliver message to local user with ctx.send_local()
        order = msg["order"]
        if order >= self._order_lower_bound and order not in self._order_store:
            self._order_store.add(order)
            msg.remove("order")
            ctx.send_local(msg)
        if all(
            cur_order in self._order_store
            for cur_order in range(order - MESSAGE_ORDER_LIMIT_AMO, order)
        ):
            for order_to_remove in range(self._order_lower_bound, order + 1):
                self._order_store.discard(order_to_remove)
            self._order_lower_bound = order + 1

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        pass


# AT LEAST ONCE --------------------------------------------------------------------------------------------------------

DELAY_ALO = 4


class AtLeastOnceSender(Process):
    def __init__(self, proc_id: str, receiver_id: str):
        self._id = proc_id
        self._receiver = receiver_id
        self._order = 0
        self._message_store = dict()

    def on_local_message(self, msg: Message, ctx: Context):
        # receive message for delivery from local user
        self._message_store[self._order] = msg["text"]
        msg["order"] = self._order
        ctx.send(msg, self._receiver)
        ctx.set_timer(str(self._order), DELAY_ALO)
        self._order += 1

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver here
        self._message_store.pop(msg["order"], None)

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        order = int(timer_name)
        if order in self._message_store:
            msg = Message(
                "MESSAGE", {"text": self._message_store[order], "order": order}
            )
            ctx.send(msg, self._receiver)
            ctx.set_timer(timer_name, DELAY_ALO)


class AtLeastOnceReceiver(Process):
    def __init__(self, proc_id: str):
        self._id = proc_id

    def on_local_message(self, msg: Message, ctx: Context):
        # not used in this task
        pass

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver
        # deliver message to local user with ctx.send_local()
        order = msg["order"]
        msg.remove("order")
        ctx.send_local(msg)
        ack = Message("MESSAGE", {"order": order})
        ctx.send(ack, sender)

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        pass


# EXACTLY ONCE ---------------------------------------------------------------------------------------------------------

DELAY_EO = 4
MESSAGE_ORDER_LIMIT_EO = 21


class ExactlyOnceSender(Process):
    def __init__(self, proc_id: str, receiver_id: str):
        self._id = proc_id
        self._receiver = receiver_id
        self._order = 0
        self._order_lower_bound = 0
        self._message_store = dict()

    def on_local_message(self, msg: Message, ctx: Context):
        # receive message for delivery from local user
        self._message_store[self._order] = msg["text"]
        if self._order <= self._order_lower_bound + MESSAGE_ORDER_LIMIT_EO:
            msg["order"] = self._order
            ctx.send(msg, self._receiver)
        ctx.set_timer(str(self._order), DELAY_EO)
        self._order += 1

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver here
        self._message_store.pop(msg["order"], None)
        self._order_lower_bound = max(self._order_lower_bound, msg["lower_bound"])

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        order = int(timer_name)
        if order not in self._message_store:
            return

        if order <= self._order_lower_bound + MESSAGE_ORDER_LIMIT_EO:
            msg = Message(
                "MESSAGE", {"text": self._message_store[order], "order": order}
            )
            ctx.send(msg, self._receiver)

        ctx.set_timer(timer_name, DELAY_EO)


class ExactlyOnceReceiver(Process):
    def __init__(self, proc_id: str):
        self._id = proc_id
        self._order_lower_bound = 0
        self._order_store = set()

    def on_local_message(self, msg: Message, ctx: Context):
        # not used in this task
        pass

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver
        # deliver message to local user with ctx.send_local()
        order = msg["order"]
        if order >= self._order_lower_bound and order not in self._order_store:
            self._order_store.add(order)
            msg.remove("order")
            ctx.send_local(msg)

        while self._order_lower_bound in self._order_store:
            self._order_store.discard(self._order_lower_bound)
            self._order_lower_bound += 1

        ack = Message(
            "MESSAGE", {"order": order, "lower_bound": self._order_lower_bound}
        )
        ctx.send(ack, sender)

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        pass


# EXACTLY ONCE + ORDERED -----------------------------------------------------------------------------------------------

DELAY_EOO = 4
MESSAGE_ORDER_LIMIT_EOO = 30


class ExactlyOnceOrderedSender(Process):
    def __init__(self, proc_id: str, receiver_id: str):
        self._id = proc_id
        self._receiver = receiver_id
        self._order = 0
        self._order_lower_bound = 0
        self._message_store = dict()

    def on_local_message(self, msg: Message, ctx: Context):
        # receive message for delivery from local user
        self._message_store[self._order] = msg["text"]
        if self._order <= self._order_lower_bound + MESSAGE_ORDER_LIMIT_EOO:
            msg["order"] = self._order
            ctx.send(msg, self._receiver)
        ctx.set_timer(str(self._order), DELAY_EOO)
        self._order += 1

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver here
        self._message_store.pop(msg["order"], None)
        self._order_lower_bound = max(self._order_lower_bound, msg["lower_bound"])

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        order = int(timer_name)
        if order not in self._message_store:
            return

        if order <= self._order_lower_bound + MESSAGE_ORDER_LIMIT_EOO:
            msg = Message(
                "MESSAGE", {"text": self._message_store[order], "order": order}
            )
            ctx.send(msg, self._receiver)

        ctx.set_timer(timer_name, DELAY_EOO)


class ExactlyOnceOrderedReceiver(Process):
    def __init__(self, proc_id: str):
        self._id = proc_id
        self._order_lower_bound = 0
        self._message_store = dict()

    def on_local_message(self, msg: Message, ctx: Context):
        # not used in this task
        pass

    def on_message(self, msg: Message, sender: str, ctx: Context):
        # process messages from receiver
        # deliver message to local user with ctx.send_local()
        order = msg["order"]
        if order >= self._order_lower_bound and order not in self._message_store:
            self._message_store[order] = msg["text"]
            while self._order_lower_bound in self._message_store:
                msg = Message(
                    "MESSAGE", {"text": self._message_store[self._order_lower_bound]}
                )
                ctx.send_local(msg)
                self._message_store.pop(self._order_lower_bound)
                self._order_lower_bound += 1

        ack = Message(
            "MESSAGE", {"order": order, "lower_bound": self._order_lower_bound}
        )
        ctx.send(ack, sender)

    def on_timer(self, timer_name: str, ctx: Context):
        # process fired timers here
        pass
