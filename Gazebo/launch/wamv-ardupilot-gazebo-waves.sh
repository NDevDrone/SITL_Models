#!/bin/bash

set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

WAMV_WORLD=waves exec "$SCRIPT_DIR/wamv-ardupilot-gazebo.sh" "$@"
