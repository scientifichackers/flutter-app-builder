from flask import request
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Hello, World!"

@app.route("/on_push", methods=["POST"])
def on_push():
    print("Got push with: {0}".format(request.get_json()))
    return "Hello, World!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
