import subprocess
from contextlib import contextmanager
from pathlib import Path
from shutil import rmtree
from typing import List, Generator
from urllib.parse import ParseResult, urlparse

import yaml
import zproc
from decouple import config

GIT_USERNAME = config("GIT_USERNAME")
GIT_PASSWORD = config("GIT_PASSWORD")
GIT_BRANCH = config("GIT_BRANCH")
FLUTTER_PATH = Path(config("FLUTTER_PATH", default="flutter")).expanduser().absolute()

OUTPUT_DIR = Path.home() / "app-builder-apks"


TMP_DIR = Path.home() / ".tmp" / "flutter-app-builder"
try:
    TMP_DIR.mkdir(parents=True)
except FileExistsError:
    pass


def print_cmd(cmd: List[str]):
    print("$ " + " ".join(map(str, cmd)))


def git_pull(git_url: str, project_root: Path):
    url: ParseResult = urlparse(git_url)
    cmd = [
        "git",
        "clone",
        f"{url.scheme}://{GIT_USERNAME}:{GIT_PASSWORD}@{url.netloc}/{url.path}",
        "--branch",
        GIT_BRANCH,
        "--single-branch",
        project_root,
    ]
    print(
        f"$ git clone {url.scheme}://{GIT_USERNAME}:*****@{url.netloc}/{url.path} --branch {GIT_BRANCH} --single-branch {project_root}"
    )
    return subprocess.check_call(cmd)


def use_64_bit(line: str) -> str:
    if "arm64-v8a" in line:
        line = line.replace("/", "")
    return line


def use_32_bit(line: str) -> str:
    if "armeabi-v7a" in line:
        line = line.replace("/", "")
    return line


@contextmanager
def gradle_arch_mode(project_root: Path, is_x64: bool):
    build_gradle = project_root / "android" / "app" / "build.gradle"

    if is_x64:
        replace_fn = use_64_bit
    else:
        replace_fn = use_32_bit

    with open(build_gradle) as f:
        backup = f.read()
    try:
        with open(build_gradle, "r+") as f:
            lines = f.readlines()
            f.seek(0)
            f.writelines(map(replace_fn, lines))
        with open(build_gradle) as f:
            print(f.read())
        yield
    finally:
        with open(build_gradle, "w") as f:
            f.write(backup)


@contextmanager
def temp_project_root(repo_name: str) -> Generator[Path, None, None]:
    project_root = TMP_DIR / repo_name
    try:
        rmtree(project_root)
    except FileNotFoundError:
        pass
    try:
        yield project_root
    finally:
        # try:
        #     rmtree(project_root)
        # except FileNotFoundError:
        #     pass
        pass


def build_release_apk(project_root: Path, is_x64: bool):
    release_dir = project_root / "build" / "app" / "outputs" / "apk" / "release"

    suffix = ""
    if is_x64:
        suffix = "64"

    name = "x86"
    if is_x64:
        name = "x64"

    with open(project_root / "pubspec.yaml") as f:
        version = yaml.load(f)["version"]

    with open(project_root / "build_number") as f:
        build_number = int(f.read().strip())

    for cmd in (
        [
            FLUTTER_PATH,
            "build",
            "apk",
            "--release",
            f"--target-platform=android-arm{suffix}",
            f"--build-number={build_number}",
        ],
        [
            "zipalign",
            "-v",
            "-p",
            "4",
            release_dir / "app-release.apk",
            release_dir / "app-release-aligned.apk",
        ],
        [
            "apksigner",
            "sign",
            "--ks",
            "meghshala-key.jks",
            "--out",
            OUTPUT_DIR / f"meghshala-prod-flutter-{name}-v{version}-{build_number}.apk",
            release_dir / "app-release-aligned.apk",
        ],
    ):
        print_cmd(cmd)
        subprocess.check_call(cmd, cwd=project_root)

    with open(project_root / "build_number", "w") as f:
        f.write(str(build_number + 1))


def flutter_packages_get(project_root: Path):
    cmd = [FLUTTER_PATH, "packages", "get"]
    print_cmd(cmd)
    return subprocess.check_call(cmd, cwd=project_root)


def do_build(repo_url: str, repo_name: str):
    with temp_project_root(repo_name) as project_root:
        git_pull(repo_url, project_root)
        flutter_packages_get(project_root)
        for is_x64 in False, True:
            with gradle_arch_mode(project_root, is_x64):
                build_release_apk(project_root, is_x64)


def run(ctx: zproc.Context):

    ready_iter = ctx.create_state().when_truthy("is_ready")

    @ctx.spawn
    def build_server(ctx: zproc.Context):
        state: zproc.State = ctx.create_state()
        state["is_ready"] = True
        for snapshot in state.when_change("next_build_request"):
            request = snapshot["next_build_request"]
            print(f"building: {request}")
            do_build(*request)

    next(ready_iter)
