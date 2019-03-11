from multiprocessing import Process

from flask import Flask
from flask import request

import app_builder

app = Flask(__name__)


@app.route("/do_build", methods=["POST"])
def on_push():
    data = request.get_json()

    print(f"Got build request: {data}")

    Process(
        target=app_builder.do_build,
        args=(data["project"]["git_http_url"], data["project"]["name"]),
    ).start()

    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
