#!/bin/bash

curl --fail http://localhost:80/ || exit 1
celery -A discussions status --json | grep -q '"ok"' || exit 1
# how to check if celery beat is running?
