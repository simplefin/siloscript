#!/bin/bash

set -e
MISSING=$(grep -Lr \
    --exclude='*.js' \
    --exclude='*.pyc' \
    --exclude='tox.ini' \
    --exclude='*.egg-info/*' \
    --exclude='_trial_temp/*' \
    --exclude='requirements.txt' \
    "Copyright (c) The SimpleFIN Team" \
    *)

if [ ! -z "$MISSING" ]; then
    echo "Missing copyright on:"
    echo "$MISSING"
    exit 1
fi