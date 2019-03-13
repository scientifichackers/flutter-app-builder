import logging
import traceback
from textwrap import dedent

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

    def set_git_hash(self, git_hash: str):
        self._state.namespace = git_hash
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

            name, url, branch, git_hash = request

            handler.set_git_hash(git_hash)
            request_history[git_hash] = name, url, branch

            logs_url = f"http://{ IP_ADDR }/build_logs/{git_hash}"

            print(f"stared build: {request} | build_id: {git_hash} | logs: {logs_url}")
            bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=dedent(
                    f"""
                    Started new build! (`{git_hash}`)
                    
                    Project ➙ {name}
                    Branch ➙ {branch}
                    Url ➙ {url}
                    
                    [See logs]({logs_url})
                    """
                ),
                parse_mode=telegram.ParseMode.MARKDOWN,
            )

            try:
                do_build(name, url, branch)
            except Exception:
                tb = traceback.format_exc()
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=dedent(
                        f"""
                        Build failed! (`{git_hash}`)
                        
                        ```
                        {tb}
                        ```
                        """
                    ),
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )
                log.error(f"Build failed! ({git_hash})\n" + tb)
                print(f"Build failed! ({git_hash})\n" + tb)
            else:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"Build successful! (`{git_hash}`)",
                    parse_mode=telegram.ParseMode.MARKDOWN,
                )
                log.info(f"Build successful! ({git_hash})")
                print(f"Build successful! ({git_hash})")
            finally:
                handler.mark_complete()

    next(ready_iter)
