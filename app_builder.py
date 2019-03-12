import logging
import os
import secrets
import shutil
import stat
import subprocess
import traceback
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from typing import List, NamedTuple
from urllib.parse import ParseResult, urlparse

import yaml
import zproc
from decouple import config
import requests


def mkdir_p(path: Path):
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        pass


class GitProject(NamedTuple):
    name: str
    url: str
    root: Path
    branch: str


GIT_USERNAME = config("GIT_USERNAME")
GIT_PASSWORD = config("GIT_PASSWORD")
FLUTTER_PATH = Path(config("FLUTTER_PATH", default="flutter")).expanduser().absolute()
OUTPUT_DIR = Path.home() / "flutter-app-builder-outputs"
TMP_DIR = Path.home() / ".tmp" / "flutter-app-builder"
LOG_DIR = TMP_DIR / "logs"

mkdir_p(OUTPUT_DIR)
mkdir_p(TMP_DIR)


def print_cmd(cmd: List[str]):
    logging.info("$ " + " ".join(map(str, cmd)))


def pipe_to_logger(stream, log_fn):
    with stream:
        for line in stream:
            log_fn(line)


def run_cmd(cmd: List[str], *args, **kwargs):
    p = subprocess.Popen(
        cmd, *args, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    threads = [
        Thread(target=pipe_to_logger, args=[p.stdout, logging.debug]),
        Thread(target=pipe_to_logger, args=[p.stdout, logging.debug]),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    p.wait()
    assert p.returncode == 0


def git_pull(project: GitProject):
    url: ParseResult = urlparse(project.url)
    cmd = [
        "git",
        "clone",
        f"{url.scheme}://{GIT_USERNAME}:{GIT_PASSWORD}@{url.netloc}/{url.path}",
        "--branch",
        project.branch,
        "--single-branch",
        project.root,
    ]
    logging.info(
        f"$ git clone "
        f"{url.scheme}://{GIT_USERNAME}:*****@{url.netloc}/{url.path} "
        f"--branch {project.branch} "
        f"--single-branch "
        f"{project.root}"
    )
    run_cmd(cmd)


def use_64_bit(line: str) -> str:
    if "arm64-v8a" in line:
        line = line.replace("/", "")
    return line


def use_32_bit(line: str) -> str:
    if "armeabi-v7a" in line:
        line = line.replace("/", "")
    return line


@contextmanager
def gradle_arch_mode(project: GitProject, is_x64: bool):
    build_gradle = project.root / "android" / "app" / "build.gradle"

    if is_x64:
        replace_fn = use_64_bit
    else:
        replace_fn = use_32_bit

    with open(build_gradle) as f:
        lines = f.readlines()
    try:
        with open(build_gradle, "w") as f:
            f.writelines(map(replace_fn, lines))
        yield
    finally:
        with open(build_gradle, "w") as f:
            f.writelines(lines)


def build_release_apk(project: GitProject, is_x64: bool):
    with open(project.root / "pubspec.yaml") as f:
        version = yaml.load(f)["version"]
    with open(project.root / "build_number") as f:
        build_number = int(f.read().strip()) + 1

    cmd = [
        FLUTTER_PATH,
        "build",
        "apk",
        "--release",
        f"--target-platform=android-arm{'64' if is_x64 else ''}",
        f"--build-number={build_number}",
    ]
    print_cmd(cmd)
    run_cmd(cmd, cwd=project.root)

    src = project.root / "build" / "app" / "outputs" / "apk" / "app.apk"
    output_dir = OUTPUT_DIR / project.name / project.branch
    mkdir_p(output_dir)
    apk_name = (
        f"{project.name}-x{'64' if is_x64 else '86'}-v{version}-{build_number}.apk"
    )
    dest = output_dir / apk_name
    shutil.copy2(src, dest)

    logging.info(f"Saved built apk to: {dest}")

    with open(project.root / "build_number", "w") as f:
        f.write(str(build_number))


def flutter_packages_get(project: GitProject):
    cmd = [FLUTTER_PATH, "packages", "get"]
    print_cmd(cmd)
    run_cmd(cmd, cwd=project.root)


def flutter_clean(project: GitProject):
    cmd = [FLUTTER_PATH, "clean"]
    print_cmd(cmd)
    run_cmd(cmd, cwd=project.root)


def do_build(name: str, url: str, branch: str):
    root = TMP_DIR / branch / name
    try:
        shutil.rmtree(root)
    except FileNotFoundError:
        pass
    mkdir_p(root)
    project = GitProject(name=name, url=url, branch=branch, root=root)

    git_pull(project)
    flutter_packages_get(project)

    for is_x64 in False, True:
        flutter_clean(project)
        with gradle_arch_mode(project, is_x64):
            build_release_apk(project, is_x64)


def ensure_fontail():
    latest = next(
        filter(
            lambda x: x["name"] == "frontail-linux",
            requests.get(
                "https://api.github.com/repos/mthenw/frontail/releases/latest"
            ).json()["assets"],
        )
    )

    frontail_path = TMP_DIR / f"frontail_{latest['id']}"
    if not frontail_path.exists():
        download_url = latest["browser_download_url"]
        print(f"downloading latest frontail binary using url: `{download_url}`")
        data = requests.get(download_url).content
        with open(frontail_path, "wb") as f:
            f.write(data)
        os.chmod(frontail_path, stat.ST_MODE | stat.S_IEXEC)
        print(f"downloaded frontail to: `{frontail_path}`")

    return frontail_path


def run(ctx: zproc.Context):
    frontail = ensure_fontail()
    subprocess.Popen([frontail, "--path", OUTPUT_DIR])

    ready_iter = ctx.create_state().when_truthy("is_ready")

    @ctx.spawn
    def build_server(ctx: zproc.Context):
        state: zproc.State = ctx.create_state()
        state["is_ready"] = True

        for snapshot in state.when_change("next_build_request"):
            request = snapshot["next_build_request"]

            build_id = secrets.token_urlsafe(8)
            logfile = LOG_DIR / build_id + ".log"
            logging.basicConfig(filename=logfile)

            print(f"building: {request}, build_id: {build_id}")
            try:
                do_build(*request)
            except Exception:
                print_cmd(f"build failed, build_id: {build_id}")
                traceback.print_exc()
            else:
                print_cmd(f"build successful, build_id: {build_id}")

    next(ready_iter)
