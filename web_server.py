import logging

import zproc
from flask import Flask, Response, abort
from flask import request
from flask_autoindex import AutoIndex

import build_server
from app_builder import OUTPUT_DIR

app = Flask(__name__)
ctx = zproc.Context()
ax = AutoIndex(app, browse_root=OUTPUT_DIR)


@app.route("/do_build/", methods=["POST"])
def on_push():
    data = request.get_json()

    print(f"got build request: {data}")

    state = ctx.create_state()
    state["next_build_request"] = (
        data["project"]["name"],
        data["project"]["git_http_url"],
        data["ref"][len("refs/heads/") :],
        data["checkout_sha"],
    )

    return "OK"


def fmt_log(levelno: int, msg: str) -> str:
    color = "black"
    if levelno == logging.DEBUG:
        color = "MediumOrchid"
    elif levelno == logging.ERROR:
        color = "red"
    return f"<span style='color: {color};'>{msg}</span><br>"


def stream_build_logs(state: zproc.State, name: str, branch: str, url: str):
    yield f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>
        <h3>Project: {name}</h3>
        <h3>Branch: {branch}</h3>
        <h3>Url: {url}</h3>
        <pre>
    """
    footer = "</pre></body></html>"

    if "logs" in state:
        logs = state["logs"]
    else:
        logs = next(state.when_available("logs"))
    yield from (fmt_log(*it) for it in logs)
    last_len = len(logs)

    if state["completed"]:
        yield footer
        return

    for snapshot in state.when(
        lambda it: len(it["logs"]) > last_len or it["completed"]
    ):
        logs = snapshot["logs"]
        yield from (fmt_log(*it) for it in logs[last_len:])
        last_len = len(logs)
        if snapshot["completed"]:
            break

    yield footer


@app.route("/build_logs/<string:git_hash>/")
def build_logs(git_hash: str):
    state = ctx.create_state()

    state.namespace = "request_history"
    try:
        build_info = state[git_hash]
    except KeyError:
        return abort(404)

    state.namespace = git_hash
    return Response(stream_build_logs(state, *build_info))


if __name__ == "__main__":
    build_server.run(ctx)
    try:
        app.run(host="0.0.0.0", port=80)
    except PermissionError:
        print("Permission denied on port 80! Falling back to 8000...")
        app.run(host="0.0.0.0", port=8000)
