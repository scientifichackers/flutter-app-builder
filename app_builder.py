import subprocess
from pathlib import Path
from shutil import rmtree
from typing import List
from urllib.parse import ParseResult, urlparse

from decouple import config

GIT_USERNAME = config("GIT_USERNAME")
GIT_PASSWORD = config("GIT_PASSWORD")
GIT_BRANCH = config("GIT_BRANCH")

TMP_DIR = Path.home() / ".tmp" / "flutter-app-builder"
try:
    TMP_DIR.mkdir(parents=True)
except FileExistsError:
    pass


def print_cmd(cmd: List[str]):
    print("$ " + " ".join(map(str, cmd)))


def git_pull(git_url: str, repo_folder: Path):
    url: ParseResult = urlparse(git_url)
    cmd = [
        "git",
        "pull",
        f"{url.scheme}://{GIT_USERNAME}:{GIT_PASSWORD}@{url.netloc}/{url.path}",
        "--branch",
        GIT_BRANCH,
        "--single-branch",
        repo_folder,
    ]
    print(f"$ git pull {git_url} --branch {GIT_BRANCH} --single-branch {repo_folder}")
    return subprocess.check_call(cmd)


def do_build(git_url: str, name: str):
    repo_folder = TMP_DIR / name
    try:
        git_pull(git_url, repo_folder)
    finally:
        try:
            rmtree(repo_folder)
        except FileNotFoundError:
            pass
