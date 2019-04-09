import logging
import select
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import List, NamedTuple, Iterable, Callable
from urllib.parse import ParseResult, urlparse

import telegram
import yaml
from decouple import config


def mkdir_p(path: Path):
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        pass


def rm_r(path: Path):
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


class GitProject(NamedTuple):
    name: str
    url: str
    root: Path
    branch: str


GIT_USERNAME = config("GIT_USERNAME")
GIT_PASSWORD = config("GIT_PASSWORD")
FLUTTER_PATH = Path(config("FLUTTER_PATH")).expanduser().absolute()
OUTPUT_DIR = Path.home() / "flutter-app-builder-outputs"
TMP_DIR = Path.home() / ".tmp" / "flutter-app-builder"
LOG_DIR = TMP_DIR / "logs"

rm_r(TMP_DIR)
mkdir_p(TMP_DIR)
mkdir_p(LOG_DIR)
mkdir_p(OUTPUT_DIR)

log = logging.getLogger(__name__)
bot = telegram.Bot(token=config("TELEGRAM_API_TOKEN"))
TELEGRAM_CHAT_ID = f"@{config('TELEGRAM_CHANNEL')}"
ROOT_DOMAIN = config("ROOT_DOMAIN")


def print_cmd(cmd: List[str]):
    log.info("$ " + " ".join(map(str, cmd)))


def pipe_stream_to_fn(stream: Iterable, log_fn: Callable):
    with stream:
        for line in stream:
            log_fn(line)


def run_cmd(cmd: List[str], **kwargs) -> int:
    proc = subprocess.Popen(
        cmd, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8"
    )

    while proc.poll() is None:
        for f in select.select([proc.stdout, proc.stderr], [], [])[0]:
            line = f.readline().strip()
            if not line:
                continue
            if f is proc.stdout:
                log.debug(line)
            elif f is proc.stderr:
                log.error(line)

    retcode = proc.wait()
    if retcode != 0:
        raise subprocess.CalledProcessError(retcode, cmd[0])
    return retcode


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
    log.info(
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


def is_arch_specific(project: GitProject):
    build_gradle = project.root / "android" / "app" / "build.gradle"
    with open(build_gradle) as f:
        content = f.read()
    return "arm64-v8a" in content and "armeabi-v7a" in content


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


def version_to_build_number(version: str, is_x64: bool) -> int:
    major, minor, patch = map(int, version.split("."))
    return major * 10 ** 7 + minor * 10 ** 4 + patch * 10 + int(is_x64)


def build_release_apk(project: GitProject, is_x64: bool):
    with open(project.root / "pubspec.yaml") as f:
        version = yaml.load(f)["version"].split("+")[0]
    build_number = version_to_build_number(version, is_x64)

    cmd = [
        FLUTTER_PATH,
        "build",
        "apk",
        "--release",
        f"--target-platform=android-arm{'64' if is_x64 else ''}",
        f"--build-number={build_number}",
        "--verbose",
    ]
    print_cmd(cmd)
    run_cmd(cmd, cwd=project.root)

    arch = "x64" if is_x64 else "x86"

    src = project.root / "build" / "app" / "outputs" / "apk" / "app.apk"
    output_dir = OUTPUT_DIR / project.name / project.branch
    mkdir_p(output_dir)
    apk_name = f"{project.name}-{arch}-v{version}-{build_number}.apk"
    dest = output_dir / apk_name
    shutil.copy2(src, dest)

    log.info(f"Saved built apk to: {dest}")
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"Built APK ➙ http://{ROOT_DOMAIN}/{dest.relative_to(OUTPUT_DIR)}",
    )


def flutter_packages_get(project: GitProject):
    cmd = [FLUTTER_PATH, "packages", "get"]
    print_cmd(cmd)
    run_cmd(cmd, cwd=project.root)


def flutter_clean(project: GitProject):
    cmd = [FLUTTER_PATH, "clean"]
    print_cmd(cmd)
    run_cmd(cmd, cwd=project.root)


def do_build(name: str, url: str, branch: str):
    root = TMP_DIR / "projects" / name / branch
    rm_r(root)
    mkdir_p(root)

    project = GitProject(name=name, url=url, branch=branch, root=root)

    git_pull(project)
    flutter_packages_get(project)

    if is_arch_specific(project):
        for is_x64 in False, True:
            flutter_clean(project)
            with gradle_arch_mode(project, is_x64):
                build_release_apk(project, is_x64)
    else:
        flutter_clean(project)
        build_release_apk(project, False)
