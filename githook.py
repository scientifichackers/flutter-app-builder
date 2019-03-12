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
        data["project"]["name"],
        data["project"]["git_http_url"],
        data["ref"][len("refs/heads/") :],
    )

    return "OK"


if __name__ == "__main__":
    app_builder.run(ctx)
    app.run(host="0.0.0.0", port=80)

x = {
    "object_kind": "push",
    "event_name": "push",
    "before": "c3e171e3d65089d4c311d242daf038527368ba86",
    "after": "f681f08a862968f9ddf10ec952f26cf37ed6f684",
    "ref": "refs/heads/app-builder",
    "checkout_sha": "f681f08a862968f9ddf10ec952f26cf37ed6f684",
    "message": None,
    "user_id": 99,
    "user_name": "Dev Aggarwal",
    "user_username": "devxpy",
    "user_email": "",
    "user_avatar": "https://secure.gravatar.com/avatar/33effa71d7cba1f399da2a9f3b075cbe?s=80&d=identicon",
    "project_id": 165,
    "project": {
        "id": 165,
        "name": "meghshala_app_flutter",
        "description": "",
        "web_url": "https://git.jaaga.in/meghshala/meghshala_app_flutter",
        "avatar_url": None,
        "git_ssh_url": "git@git.jaaga.in:meghshala/meghshala_app_flutter.git",
        "git_http_url": "https://git.jaaga.in/meghshala/meghshala_app_flutter.git",
        "namespace": "Meghshala",
        "visibility_level": 0,
        "path_with_namespace": "meghshala/meghshala_app_flutter",
        "default_branch": "master",
        "ci_config_path": None,
        "homepage": "https://git.jaaga.in/meghshala/meghshala_app_flutter",
        "url": "git@git.jaaga.in:meghshala/meghshala_app_flutter.git",
        "ssh_url": "git@git.jaaga.in:meghshala/meghshala_app_flutter.git",
        "http_url": "https://git.jaaga.in/meghshala/meghshala_app_flutter.git",
    },
    "commits": [
        {
            "id": "f681f08a862968f9ddf10ec952f26cf37ed6f684",
            "message": "zipalign\n",
            "timestamp": "2019-03-12T09:19:34Z",
            "url": "https://git.jaaga.in/meghshala/meghshala_app_flutter/commit/f681f08a862968f9ddf10ec952f26cf37ed6f684",
            "author": {"name": "devxpy", "email": "devxpy@gmail.com"},
            "added": [],
            "modified": ["android/app/build.gradle"],
            "removed": [],
        }
    ],
    "total_commits_count": 1,
    "push_options": [],
    "repository": {
        "name": "meghshala_app_flutter",
        "url": "git@git.jaaga.in:meghshala/meghshala_app_flutter.git",
        "description": "",
        "homepage": "https://git.jaaga.in/meghshala/meghshala_app_flutter",
        "git_http_url": "https://git.jaaga.in/meghshala/meghshala_app_flutter.git",
        "git_ssh_url": "git@git.jaaga.in:meghshala/meghshala_app_flutter.git",
        "visibility_level": 0,
    },
}
