import logging

import zproc
from flask import Flask, Response
from flask import request

import build_server

app = Flask(__name__)
ctx = zproc.Context()


@app.route("/do_build", methods=["POST"])
def on_push():
    data = request.get_json()

    print(f"got build request: {data}")

    state = ctx.create_state()
    state["next_build_request"] = (
        data["project"]["name"],
        data["project"]["git_http_url"],
        data["ref"][len("refs/heads/") :],
    )

    return "OK"


def fmt_log(levelno: int, msg: str) -> str:
    color = "black"
    if levelno == logging.DEBUG:
        color = "purple"
    elif levelno == logging.ERROR:
        color = "red"
    return f"<span style='color: {color};'>{msg}</span><br>"


@app.route("/build_logs/<string:build_id>")
def build_logs(build_id: str):
    print(build_id)

    def _():
        state = ctx.create_state()
        state.namespace = build_id

        print(state)
        if "logs" in state:
            logs = state["logs"]
        else:
            logs = next(state.when_available("logs"))
        print(logs)
        yield from (fmt_log(*it) for it in logs)
        last_len = len(logs)

        for snapshot in state.when(lambda it: len(it["logs"]) > last_len):
            logs = snapshot["logs"]
            yield from (fmt_log(*it) for it in logs[last_len:])
            last_len = len(logs[last_len:])

    return Response(_(), mimetype="text/html")


if __name__ == "__main__":
    build_server.run(ctx)
    app.run(host="0.0.0.0", port=80)
