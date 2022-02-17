import argparse
import filecmp
import logging
import shutil

from os import makedirs, remove
from os.path import join, isdir
from sys import exit
from time import sleep

log = logging.getLogger()

log.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%d.%m.%y %H:%M:%S",
)

terminal_handler = logging.StreamHandler()
terminal_handler.setFormatter(formatter)
log.addHandler(terminal_handler)


def rm(path):
    """Remove provided file or directory.
    RECURSIVE, USE WITH CAUTION!
    """

    log.debug(f"Attempting to remove {path}")
    if isdir(path):
        shutil.rmtree(path)
    else:
        remove(path)
    log.debug(f"Successfully removed {path}")


def cp(source, dest):
    """Recursively copy provided data to provided directory"""

    log.debug(f"Attempting to copy {source} to {dest}")
    if isdir(source):
        shutil.copytree(source, dest, copy_function=shutil.copy2)
    else:
        shutil.copy2(source, dest)

    log.debug(f"Successfully copied {source} to {dest}")


def sync_dirs_recursively(first, second):
    """Recursively synchronize content between two directories."""

    comp_dirs = filecmp.dircmp(first, second)

    for obsolete_file in comp_dirs.right_only:
        log.info(f"{obsolete_file} has been deleted in {first}, removing from {second}")
        rm(join(second, obsolete_file))

    for diff_file in comp_dirs.diff_files:
        log.info(f"{diff_file} has been changed in {first}, updating in {second}")
        diff_path = join(second, diff_file)
        rm(diff_path)
        cp(join(first, diff_file), diff_path)

    for new_file in comp_dirs.left_only:
        log.info(f"{new_file} has been newly added to {first}, copying to {second}")
        cp(join(first, new_file), join(second, new_file))

    # This may be kind of inefficient, but since dircmp doesn't support recursive
    # directory verification, I kinda have to do it manually. I could reimplement
    # the wheel and not rely on dircmp, but since one of requirements was to use
    # solutions of language's standard library where possible, I've had no choice.
    #
    # This *may* also cause issues on large dirs, theoretically leading to stack
    # overflow. But since its highly unlikely for this code to be used on directory
    # with 1000+ layers (and for the sake of simplicity), we pretend like its not
    # a problem, for now.
    # In case of emergence, this could be rewritten with custom implementation of
    # https://www.geeksforgeeks.org/inorder-tree-traversal-without-recursion/
    for d in comp_dirs.common_dirs:
        sync_dirs_recursively(join(first, d), join(second, d))


ap = argparse.ArgumentParser()
ap.add_argument("source", help="Path to directory, you want to copy")

ap.add_argument(
    "destination",
    help="Path to destination, where directory should be copied",
)

ap.add_argument(
    "sync_time",
    help="Pause between synchronization",
    type=int,
)

ap.add_argument("log_path", help="Path to log file")
args = ap.parse_args()

file_handler = logging.FileHandler(args.log_path)
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

for d in (args.source, args.destination):
    try:
        makedirs(d, exist_ok=True)
    except Exception as e:
        log.critical(f"Unable to create directory: {e}")
        exit(2)


while True:
    sync_dirs_recursively(args.source, args.destination)

    log.debug(
        "Successfully finished directory synchronization!\n"
        f"Next sync will be done in {args.sync_time} seconds"
    )
    sleep(args.sync_time)
