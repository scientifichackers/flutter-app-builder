import zproc
from flask import Flask
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
        data["project"]["git_http_url"],
        data["project"]["name"],
    )

    return "OK"


if __name__ == "__main__":
    app_builder.run(ctx)
    app.run(host="0.0.0.0", port=80)
