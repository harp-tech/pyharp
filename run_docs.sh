#!/bin/bash

# Find all subdirectories of harp.devices and join them with ':'
HARP_DEVICES_PATHS=$(find -L ./harp.devices -mindepth 1 -maxdepth 1 -type d | paste -sd ":" -)

# Prepend to PYTHONPATH (preserve existing PYTHONPATH)
export PYTHONPATH="$HARP_DEVICES_PATHS:$PYTHONPATH"

# Optionally print for debugging
echo "PYTHONPATH set to: $PYTHONPATH"

# Launch mkdocs build or serve
if [ "$1" = "build" ]; then
    uv run mkdocs build
elif [ "$1" = "deploy" ]; then
    uv run mkdocs gh-deploy
else
    uv run mkdocs serve
fi
