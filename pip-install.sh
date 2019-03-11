#!/usr/bin/env bash

printf "\n\n$ pip-compile -v requirements.in\n\n"
pip-compile -v requirements.in

printf "\n\n$ pip-compile -v dev-requirements.in\n\n"
pip-compile -v dev-requirements.in

printf "\n\n$ pip-sync requirements.txt dev-requirements.txt\n\n"
pip-sync requirements.txt dev-requirements.txt