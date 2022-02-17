import argparse
import csv
import logging

# import resource
import subprocess

from datetime import datetime
from os import listdir
from sys import exit
from time import sleep, time

# According to documentation, these magic numbers should refer to utime and stime.
# https://www.kernel.org/doc/html/latest/filesystems/proc.html#process-specific-subdirectories
# (As for the moment of writing - see Table 1.4)
#
# Originally I've found misleading legacy information about these actually being
# 12 and 13, but I think thats incorrect
UTIME_COLUMN = 13
STIME_COLUMN = 14
# And these magic numbers refer to virtual memory size and residental set size
VMS_COLUMN = 22
RSS_COLUMN = 23

STATS_PATH = "./stats.csv"

log = logging.getLogger()

log.setLevel(logging.INFO)

formatter = logging.Formatter(
    fmt="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%d.%m.%y %H:%M:%S",
)

terminal_handler = logging.StreamHandler()
terminal_handler.setFormatter(formatter)
log.addHandler(terminal_handler)


def get_stats() -> list:
    """Get magic numbers from /proc/stat"""

    with open(f"/proc/stat", "r") as f:
        values = f.readline().split()[1:]

    return values


def get_total_cpu_usage(info: list) -> int:
    """Calculate cpu usage, based on numbers from get_stats()"""

    total_amount = 0
    for i in info:
        total_amount += int(i)

    return total_amount


def get_stat(pid: int) -> list:
    """Get magic numbers from /proc/{pid}/stat"""

    with open(f"/proc/{pid}/stat", "r") as f:
        stats = f.read().split()

    return stats


def get_process_cpu_usage(pid: int) -> int:
    """Calculate approximate CPU usage (in percents).
    Accuracy is questionable. Will hang execution on same thread for 1 second.
    """

    stats = get_stats()
    stat = get_stat(pid)
    sleep(1)
    new_stats = get_stats()
    new_stat = get_stat(pid)

    time_diff = get_total_cpu_usage(new_stats) - get_total_cpu_usage(stats)

    user_util = (
        100 * (int(new_stat[UTIME_COLUMN]) - int(stat[UTIME_COLUMN])) / time_diff
    )
    sys_util = 100 * (int(new_stat[STIME_COLUMN]) - int(stat[STIME_COLUMN])) / time_diff

    return int(user_util + sys_util)


ap = argparse.ArgumentParser()
ap.add_argument(
    "program_path",
    help="Path to program, you want to launch",
)

ap.add_argument(
    "stats_update_interval",
    help="Length of pause between statistics updating routine",
    type=int,
)

args = ap.parse_args()

try:
    # Existing stats file will be overwritten!
    with open(STATS_PATH, "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            (
                "date",
                "cpu_usage",
                "resident_set_size",
                "virtual_memory_size",
                "file_descriptors",
            )
        )

except Exception as e:
    log.critical(f"Unable to write stats into {STATS_PATH}: {e}")
    exit(2)

try:
    process = subprocess.Popen(args.program_path)
except Exception as e:
    log.critical(f"Unable to execute program: {e}")
    exit(2)

# I could use sleep(), but it would make this utility hang until timer is over,
# even if child process has been already shut down
first_run = True
wait_time = time()
while process.poll() is None:
    # To make it calculate things right away on start
    if not first_run:
        current_time = time()
        if current_time - wait_time < args.stats_update_interval:
            continue
        else:
            wait_time = current_time
    else:
        first_run = False

    log.info("Fetching process info")

    try:
        cpu_usage = get_process_cpu_usage(process.pid)
        log.info(f"CPU usage is approximately {cpu_usage}%")

        stats = get_stat(process.pid)

        # According to proc manual, this should do the trick.
        # Note that, according to manual, reported Resident Set Size is inaccurate
        # - there doesn't seem to be any way to get precise value of it.
        vms = int(stats[VMS_COLUMN])
        log.info(f"Virtual Memory Size is {vms} bytes")
        rss = int(stats[RSS_COLUMN])
        log.info(f"Resident Set Size is {rss}")

        descriptors_amount = len(listdir(f"/proc/{process.pid}/fd"))
        log.info(f"Current descriptors amount: {descriptors_amount}")

    except Exception as e:
        log.warning(f"Unable to fetch process stats: {e}")

        # Not exiting with non-zero there, because this can trigger during legit
        # exit process, if child application has been closed after data fetching
        # loop has been started.
        break

    else:
        with open(STATS_PATH, "a") as f:
            writer = csv.writer(f)
            writer.writerow(
                (
                    datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    cpu_usage,
                    rss,
                    vms,
                    descriptors_amount,
                )
            )

log.info("Closing the handler")
