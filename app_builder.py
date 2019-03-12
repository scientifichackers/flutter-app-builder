import subprocess
from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import List, Generator, NamedTuple
from urllib.parse import ParseResult, urlparse

import yaml
import zproc
from decouple import config


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

OUTPUT_DIR = Path.home() / "flutter-app-builder"
TMP_DIR = Path.home() / ".tmp" / "flutter-app-builder"

mkdir_p(OUTPUT_DIR)
mkdir_p(TMP_DIR)


def print_cmd(cmd: List[str]):
    print("$ " + " ".join(map(str, cmd)))


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
    print(
        f"$ git clone "
        f"{url.scheme}://{GIT_USERNAME}:*****@{url.netloc}/{url.path} "
        f"--branch {project.branch} "
        f"--single-branch "
        f"{project.root}"
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
    build_dir = project.root / "build" / "app" / "outputs" / "apk"

    output_dir = OUTPUT_DIR / project.branch
    mkdir_p(output_dir)

    suffix = ""
    if is_x64:
        suffix = "64"

    name = "x86"
    if is_x64:
        name = "x64"

    with open(project.root / "pubspec.yaml") as f:
        version = yaml.load(f)["version"]

    with open(project.root / "build_number") as f:
        build_number = int(f.read().strip()) + 1

    for cmd in (
        [
            FLUTTER_PATH,
            "build",
            "apk",
            "--release",
            f"--target-platform=android-arm{suffix}",
            f"--build-number={build_number}",
        ],
        # [
        #     "zipalign",
        #     "-v",
        #     "-p",
        #     "4",
        #     release_dir / "app-release.apk",
        #     release_dir / "app-release-aligned.apk",
        # ],
        # [
        #     "apksigner",
        #     "sign",
        #     "--ks",
        #     "meghshala-key.jks",
        #     "--out",
        #     OUTPUT_DIR / f"meghshala-prod-flutter-{name}-v{version}-{build_number}.apk",
        #     release_dir / "app-release-aligned.apk",
        # ],
    ):
        print_cmd(cmd)
        subprocess.check_call(cmd, cwd=project.root)

    apk_name = f"{project.name}-{name}-v{version}-{build_number}.apk"
    shutil.copy2(build_dir / "app.apk", output_dir / apk_name)

    with open(project.root / "build_number", "w") as f:
        f.write(str(build_number))


def flutter_packages_get(project: GitProject):
    cmd = [FLUTTER_PATH, "packages", "get"]
    print_cmd(cmd)
    return subprocess.check_call(cmd, cwd=project.root)


def flutter_clean(project: GitProject):
    cmd = [FLUTTER_PATH, "clean"]
    print_cmd(cmd)
    return subprocess.check_call(cmd, cwd=project.root)


@contextmanager
def temp_project_root(name: str) -> Generator[Path, None, None]:
    project_root = TMP_DIR / name
    try:
        shutil.rmtree(project_root)
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


def do_build(name: str, url: str, branch: str):
    with temp_project_root(name) as project_root:
        project = GitProject(name=name, url=url, branch=branch, root=project_root)
        git_pull(project)
        flutter_packages_get(project)
        for is_x64 in False, True:
            flutter_clean(project)
            with gradle_arch_mode(project, is_x64):
                build_release_apk(project, is_x64)


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
