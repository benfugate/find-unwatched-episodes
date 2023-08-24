#!/bin/bash
python3 /usr/src/app/src/docker_setup.py
# Run once at startup
python3 /usr/src/app/src/find_unwatched_requests.py
cron
tail -f /dev/null