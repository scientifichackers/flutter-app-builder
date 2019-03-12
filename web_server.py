import zproc
from flask import Flask, Response, abort
from flask import request

import app_builder

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
    filename = build_id + ".log"
    try:
        logfile = next(
            filter(lambda it: it.name == filename, app_builder.LOG_DIR.glob("*.log"))
        )
    except StopIteration:
        abort(404)

    def _():
        with logfile.open() as f:
            for line in f:
                yield line + "<br/>"

    return Response(_())


if __name__ == "__main__":
    app_builder.run(ctx)
    app.run(host="0.0.0.0", port=80)
