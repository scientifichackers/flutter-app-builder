import logging
import subprocess
import sys

import zproc
from flask import Flask, Response, abort
from flask import request

import app_builder
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
        color = "MediumOrchid"
    elif levelno == logging.ERROR:
        color = "red"
    return f"<span style='color: {color};'>{msg}</span><br>"


@app.route("/build_logs/<string:build_id>")
def build_logs(build_id: str):
    state = ctx.create_state()

    state.namespace = "request_history"
    try:
        request = state[build_id]
    except KeyError:
        abort(404)
    name, url, branch = request

    def _():
        yield f"<h3>Project: {name}</h3><h3>Branch: {branch}</h3><h3>Url: {url}</h3>"
        yield "<pre>"

        state.namespace = build_id

        if "logs" in state:
            logs = state["logs"]
        else:
            logs = next(state.when_available("logs"))
        yield from (fmt_log(*it) for it in logs)
        last_len = len(logs)

        for snapshot in state.when(
            lambda it: len(it["logs"]) > last_len or it["completed"]
        ):
            logs = snapshot["logs"]
            yield from (fmt_log(*it) for it in logs[last_len:])
            last_len = len(logs)
            if snapshot["completed"]:
                break

        yield "</pre>"

    return Response(_())


if __name__ == "__main__":
    build_server.run(ctx)
    subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000"], cwd=app_builder.OUTPUT_DIR
    )
    app.run(host="0.0.0.0", port=80)
