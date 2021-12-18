#!/bin/bash
#curl --fail http://localhost:80/ > /dev/null || exit 1
wget -q --spider http://localhost:80/ || exit 1
# celery -A discussions status --json -t 30 | grep -q '"ok"' || exit 2
# todo: how to check if celery beat is running?
