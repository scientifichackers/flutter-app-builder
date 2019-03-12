import logging
import secrets
import traceback

import telegram
import zproc

from app_builder import log, bot, TELEGRAM_CHAT_ID, IP_ADDR, do_build


@zproc.atomic
def add_log_recrod(state: dict, levelno: int, msg: str):
    state["logs"].append((levelno, msg))


class ZProcHandler(logging.Handler):
    def __init__(self, ctx: zproc.Context):
        self._state = ctx.create_state()
        super().__init__()

    def set_build_id(self, build_id: str):
        self._state.namespace = build_id
        self._state.update({"logs": [], "completed": False})

    def mark_complete(self):
        self._state["completed"] = True

    def emit(self, record: logging.LogRecord):
        add_log_recrod(self._state, record.levelno, self.format(record))


def run(ctx: zproc.Context):
    ready_iter = ctx.create_state().when_truthy("is_ready")

    @ctx.spawn
    def build_server(ctx: zproc.Context):
        state: zproc.State = ctx.create_state()
        request_history = state.fork(namespace="request_history")

        handler = ZProcHandler(ctx)
        formatter = logging.Formatter("[%(levelname)s] [%(asctime)s] %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)

        state["is_ready"] = True

        for snapshot in state.when_change("next_build_request"):
            request = snapshot["next_build_request"]

            build_id = secrets.token_urlsafe(8)
            handler.set_build_id(build_id)
            request_history[build_id] = request

            name, url, branch = request
            logs_url = f"http://{ IP_ADDR }/build_logs/{build_id}"

            print(f"building: {request} | build_id: {build_id} | logs: {logs_url}")

            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"Started new build! ({build_id})\n\n"
                f"Project ➙ {name}\n"
                f"Branch ➙ {branch}\n"
                f"Url ➙ {url}\n\n"
                f"Logs ➙ {logs_url}\n\n",
            )

            try:
                do_build(*request)
            except Exception:
                tb = traceback.format_exc()
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"Build failed! ({build_id})\n\n```\n" + tb + "\n```",
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )
                log.error(tb)
            else:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="Build successful!")
                log.info(f"Build successful! ({build_id})")
            finally:
                handler.mark_complete()

    next(ready_iter)
