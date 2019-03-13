import logging

import zproc
from flask import Flask, Response, abort
from flask import request
from twisted.internet import reactor
from twisted.web.server import Site
from twisted.web.static import File

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


@app.route("/build_logs/<string:git_hash>")
def build_logs(git_hash: str):
    state = ctx.create_state()

    state.namespace = "request_history"
    try:
        request = state[git_hash]
    except KeyError:
        abort(404)
    name, url, branch = request

    state.namespace = git_hash

    def _():
        yield """<html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body>"""
        yield f"<h3>Project: {name}</h3><h3>Branch: {branch}</h3><h3>Url: {url}</h3>"
        yield "<pre>"

        if "logs" in state:
            logs = state["logs"]
        else:
            logs = next(state.when_available("logs"))
        yield from (fmt_log(*it) for it in logs)
        last_len = len(logs)

        if not state["completed"]:
            for snapshot in state.when(
                lambda it: len(it["logs"]) > last_len or it["completed"]
            ):
                logs = snapshot["logs"]
                yield from (fmt_log(*it) for it in logs[last_len:])
                last_len = len(logs)
                if snapshot["completed"]:
                    break

        yield "</pre></body></html>"

    return Response(_())


if __name__ == "__main__":
    build_server.run(ctx)

    @ctx.spawn(pass_context=False)
    def file_server():
        reactor.listenTCP(8000, Site(File(app_builder.OUTPUT_DIR)))
        reactor.run()

    app.run(host="0.0.0.0", port=80)
