from pathlib import Path
from shutil import rmtree
from typing import List

import pexpect
from decouple import config

GIT_USERNAME = config("GIT_USERNAME")
GIT_PASSWORD = config("GIT_PASSWORD")
GIT_BRANCH = config("GIT_BRANCH")

TMP_DIR = Path.home() / ".tmp" / "flutter-app-builder"


def print_cmd(cmd: List[str]):
    print("$ " + " ".join(map(str, cmd)))


def git_pull(git_url: str, repo_folder: Path):
    cmd = [
        "git",
        "clone",
        git_url,
        "--branch",
        GIT_BRANCH,
        "--single-branch",
        repo_folder,
    ]
    cmd = list(map(str, cmd))
    print_cmd(cmd)

    child = pexpect.spawn(cmd[0], args=cmd[1:])

    child.expect("Username for '*':")
    child.sendline(GIT_USERNAME)
    child.expect("Password for '*':")
    child.sendline(GIT_PASSWORD)

    child.wait()


def do_build(git_url: str, name: str):
    repo_folder = TMP_DIR / name
    try:
        git_pull(git_url, repo_folder)
    finally:
        try:
            rmtree(repo_folder)
        except FileNotFoundError:
            pass
