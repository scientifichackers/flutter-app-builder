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


@app.route("/build_logs/<string:build_id>")
def build_logs(build_id):
    state = ctx.create_state()
    state.namespace = build_id

    def _():
        last_len = 0
        for snapshot in state.when_change("logs"):
            logs = snapshot["logs"]
            if last_len >= len(logs):
                continue

            for levelno, msg in logs[last_len:]:
                color = "black"
                if levelno == logging.DEBUG:
                    color = "purple"
                elif levelno == logging.ERROR:
                    color = "red"
                yield f"<span style='color: {color};'>{msg}</span><br>"

            last_len = len(logs)

    return Response(_(), mimetype="text/html")


if __name__ == "__main__":
    build_server.run(ctx)
    app.run(host="0.0.0.0", port=80)
