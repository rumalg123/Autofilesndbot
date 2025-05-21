from os import path as opath, getenv
from subprocess import run as srun
from dotenv import load_dotenv
from os import path as ospath
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# if ospath.exists('Logs.txt'):
#     with open('Logs.txt', 'r+') as f:
#         f.truncate(0)

load_dotenv(override=True)

UPSTREAM_REPO = getenv('UPSTREAM_REPO', "https://github.com/rumalg123/Autofilesndbot")
UPSTREAM_BRANCH = getenv('UPSTREAM_BRANCH', "master")

if UPSTREAM_REPO is not None:
    if opath.exists('.git'):
        srun(["rm", "-rf", ".git"])

    update = srun([f"git init -q \
                     && git config --global user.email pachax001@gmail.com \
                     && git config --global user.name pachax001 \
                     && git add . \
                     && git commit -sm update -q \
                     && git remote add origin {UPSTREAM_REPO} \
                     && git fetch origin -q \
                     && git reset --hard origin/{UPSTREAM_BRANCH} -q"], shell=True)

    if update.returncode == 0:
        logger.info('Successfully updated with latest commit from UPSTREAM_REPO')

    else:
        logger.error('Something went wrong while updating, check UPSTREAM_REPO if valid or not!')