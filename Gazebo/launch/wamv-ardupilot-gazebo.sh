#!/bin/bash

set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SITL_MODELS_DIR=${SITL_MODELS_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}

if [ -z "$ARDUPILOT_HOME" ]; then
  if [ -f "$PWD/wscript" ] && [ -d "$PWD/Tools/autotest" ]; then
    ARDUPILOT_HOME=$PWD
  else
    echo "Set ARDUPILOT_HOME to an ArduPilot checkout, or run this script from one." >&2
    exit 1
  fi
fi

ROVER="$ARDUPILOT_HOME/build/sitl/bin/ardurover"
WAMV_WORLD_KIND=${WAMV_WORLD:-calm}
if [ -z "$WORLD" ]; then
  case "$WAMV_WORLD_KIND" in
    calm)
      WORLD="$SITL_MODELS_DIR/Gazebo/worlds/wamv_ardupilot.sdf"
      ;;
    waves)
      WORLD="$SITL_MODELS_DIR/Gazebo/worlds/wamv_ardupilot_waves.sdf"
      ;;
    *)
      echo "Unknown WAMV_WORLD='${WAMV_WORLD}'. Use 'calm' or 'waves'." >&2
      exit 1
      ;;
  esac
fi
if [ -z "$PARAMS" ]; then
  case "$WAMV_WORLD_KIND" in
    waves)
      PARAMS="$SITL_MODELS_DIR/Gazebo/config/wamv_waves.param"
      ;;
    *)
      PARAMS="$SITL_MODELS_DIR/Gazebo/config/wamv.param"
      ;;
  esac
fi
if [ -z "$HOME_LOCATION" ]; then
  case "$WAMV_WORLD_KIND" in
    waves)
      HOME_LOCATION="51.566151,-4.034345,10.0,0"
      ;;
    *)
      HOME_LOCATION="-35.3632621,149.1652374,584,0"
      ;;
  esac
fi
WIPE_EEPROM=${WIPE_EEPROM:-1}

if ! command -v gz >/dev/null 2>&1; then
  echo "Could not find 'gz' on PATH. Source your Gazebo Sim environment first." >&2
  exit 1
fi

if [ ! -x "$ROVER" ]; then
  (
    cd "$ARDUPILOT_HOME"
    ./waf configure --board sitl --debug
    ./waf rover
  )
fi

export GZ_SIM_RESOURCE_PATH="$SITL_MODELS_DIR/Gazebo/models:$SITL_MODELS_DIR/Gazebo/worlds:${GZ_SIM_RESOURCE_PATH:-}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_PARTITION="${GZ_PARTITION:-wamv_ardupilot}"

if [ -n "$GAZEBO_MARITIME_PLUGIN_PATH" ]; then
  export GZ_SIM_SYSTEM_PLUGIN_PATH="$GAZEBO_MARITIME_PLUGIN_PATH:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
  export DYLD_LIBRARY_PATH="$GAZEBO_MARITIME_PLUGIN_PATH:${DYLD_LIBRARY_PATH:-}"
fi

if [ -n "$ASV_WAVE_SIM_PLUGIN_PATH" ]; then
  export GZ_SIM_SYSTEM_PLUGIN_PATH="$ASV_WAVE_SIM_PLUGIN_PATH:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
  export DYLD_LIBRARY_PATH="$ASV_WAVE_SIM_PLUGIN_PATH:${DYLD_LIBRARY_PATH:-}"
fi

if [ -n "$GZ_WAVES_PLUGIN_PATH" ]; then
  export GZ_SIM_SYSTEM_PLUGIN_PATH="$GZ_WAVES_PLUGIN_PATH:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
  export DYLD_LIBRARY_PATH="$GZ_WAVES_PLUGIN_PATH:${DYLD_LIBRARY_PATH:-}"
fi

cleanup()
{
  [ -n "$ROVER_PID" ] && kill "$ROVER_PID" 2>/dev/null || true
  [ -n "$GZ_GUI_PID" ] && kill "$GZ_GUI_PID" 2>/dev/null || true
  [ -n "$GZ_PID" ] && kill "$GZ_PID" 2>/dev/null || true
}
trap cleanup SIGINT SIGTERM EXIT

if [ "$(uname -s)" = "Darwin" ]; then
  gz sim -v4 -s -r "$WORLD" &
  GZ_PID=$!
  sleep 2
  gz sim -v4 -g &
  GZ_GUI_PID=$!
else
  gz sim -v4 -r "$WORLD" &
  GZ_PID=$!
fi

mkdir -p "$ARDUPILOT_HOME/sitl/wamv"
(
  cd "$ARDUPILOT_HOME/sitl/wamv"
  WIPE_ARGS=()
  if [ "$WIPE_EEPROM" != "0" ]; then
    WIPE_ARGS=(--wipe)
  fi
  "$ROVER" "${WIPE_ARGS[@]}" -S --model JSON --home="$HOME_LOCATION" \
    --speedup 1 --slave 0 --instance 0 --sysid 1 --defaults "$PARAMS"
) &
ROVER_PID=$!

wait "$ROVER_PID"
