import logging
import secrets
import socket
import traceback

import zproc

import app_builder


@zproc.atomic
def add_log_recrod(state: dict, levelno: int, msg: str):
    state["logs"].append((levelno, msg))


class ZProcHandler(logging.Handler):
    def __init__(self, ctx: zproc.Context):
        self._state = ctx.create_state()
        super().__init__()

    def set_build_id(self, build_id: str):
        self._state.namespace = build_id
        self._state["logs"] = []

    def emit(self, record: logging.LogRecord):
        add_log_recrod(self._state, record.levelno, self.format(record))


with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.connect(("1.1.1.1", 80))
    IP_ADDR = sock.getsockname()[0]


def run(ctx: zproc.Context):
    ready_iter = ctx.create_state().when_truthy("is_ready")

    @ctx.spawn
    def build_server(ctx: zproc.Context):
        state: zproc.State = ctx.create_state()

        handler = ZProcHandler(ctx)
        formatter = logging.Formatter("[%(levelname)s] [%(asctime)s] %(message)s")
        handler.setFormatter(formatter)
        app_builder.log.addHandler(handler)
        app_builder.log.setLevel(logging.DEBUG)

        state["is_ready"] = True

        for snapshot in state.when_change("next_build_request"):
            request = snapshot["next_build_request"]

            build_id = secrets.token_urlsafe(8)
            handler.set_build_id(build_id)

            print(
                f"building: {request}, build_id: {build_id}, logs: `http://{IP_ADDR}/build_logs/{build_id}`"
            )
            try:
                app_builder.do_build(*request)
            except Exception:
                print(f"build failed, build_id: {build_id}")
                traceback.print_exc()
            else:
                print(f"build successful, build_id: {build_id}")

    next(ready_iter)
