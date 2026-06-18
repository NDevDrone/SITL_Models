# WAM-V ArduPilot Gazebo SITL

This is a minimal WAM-V surface vehicle for ArduPilot Rover / Boat SITL in
Gazebo Sim 8 / Harmonic. It keeps the model description tied to the WAM-V from
the Gazebo Sim surface-vehicle tutorial, then adds the smallest practical SITL
plumbing for the ArduPilot Gazebo plugin, differential thrust, and optional wave
hydrodynamics.

Original WAM-V source:

- Gazebo tutorial: <https://gazebosim.org/api/sim/8/surface_vehicles.html>
- Tutorial source archive: <https://github.com/gazebosim/gz-sim/blob/gz-sim8/tutorials/files/surface_vehicles/gz_maritime_ws.zip>
- Gazebo Sim repository: <https://github.com/gazebosim/gz-sim>

The original Gazebo Sim assets are Apache-2.0; a copy is included at
`Gazebo/models/wamv/LICENSE`. The wave assets in `Gazebo/models/waves_gentle`
come from [`srmainwaring/asv_wave_sim`](https://github.com/srmainwaring/asv_wave_sim)
and are GPL-3.0; the license and attribution are included in that directory.

## What Is Included

- `Gazebo/models/wamv/model.sdf`: calm-water WAM-V adapted for stock Gazebo
  buoyancy and ArduPilot JSON SITL.
- `Gazebo/models/wamv/model_waves.sdf`: wave-world WAM-V variant. It keeps the
  tutorial-derived WAM-V geometry where practical and uses ASV `gz-waves`
  hydrodynamics.
- `Gazebo/models/waves_gentle`: a local copy of the `asv_wave_sim` `waves`
  model with a stronger WAM-V validation preset. It uses the same wave-plugin
  family already used by this repo's Catamaran and BlueBoat models, but is
  renamed so it can coexist with a user's upstream `model://waves`.
- `Gazebo/worlds/wamv_ardupilot.sdf`: calm-water world.
- `Gazebo/worlds/wamv_ardupilot_waves.sdf`: WAM-V plus `waves_gentle`.
- `Gazebo/config/wamv.param` and `Gazebo/config/wamv_waves.param`: starting
  AUTO mission parameter files.
- `Gazebo/launch/wamv-ardupilot-gazebo.sh`: GUI launcher for the calm world.
- `Gazebo/launch/wamv-ardupilot-gazebo-waves.sh`: GUI launcher for the wave
  world.
- `Gazebo/scripts/wamv_square_mission.py`: mission upload / AUTO validation
  helper.

## Environment Setup

Install ArduPilot SITL, Gazebo Sim Harmonic, and the ArduPilot Gazebo plugin
before launching this model. The commands below use environment variables so no
personal paths are required.

Reference install docs: [ArduPilot Gazebo Plugin](https://github.com/ArduPilot/ardupilot_gazebo),
[ArduPilot SITL with Gazebo](https://ardupilot.org/dev/docs/sitl-with-gazebo.html),
and [`asv_wave_sim`](https://github.com/srmainwaring/asv_wave_sim).

If you manage Gazebo with pixi, enter that environment first. The exact package
set depends on your platform, but the shell needs Gazebo Sim 8 / Harmonic,
`cmake`, a compiler, `rapidjson`, OpenCV / GStreamer dependencies for the
ArduPilot plugin, and `colcon` plus CGAL / FFTW for the optional wave stack.
Otherwise use system packages following the official install guides.

```bash
# Optional, only if your Gazebo toolchain is managed by pixi.
pixi shell

export ARDUPILOT_HOME=$HOME/ardupilot
export SITL_MODELS_DIR=$HOME/SITL_Models
export GZ_VERSION=harmonic
```

### Wave Rendering Fix

The dynamic water visual depends on Gazebo Sim 8's `EventManager` working
across shared-library boundaries. On macOS / pixi / conda environments, older
`gz-sim8` builds can load `WavesModel` while the rendered water surface is
missing, frozen, or looking like a shader texture sliding over the water instead
of a live wave mesh. Use a Gazebo Sim 8 build that includes
[`gazebosim/gz-sim#3543`](https://github.com/gazebosim/gz-sim/pull/3543), the
`gz-sim8` backport of
[`gazebosim/gz-sim#3459`](https://github.com/gazebosim/gz-sim/pull/3459).

For the pixi setup used during validation, the working fix was:

1. Patch or update `gz-sim8` so `EventManager` hashes and compares event types
   by stable `type_info::name()` strings, matching the upstream fix.
2. Rebuild and install all of `gz-sim8` into the active pixi environment. A
   header-only update or single-library swap can still leave stale template
   instantiations in Gazebo plugins.
3. When building `gz-sim8_8.9.0` against newer pixi / conda Gazebo
   dependencies, use `-DSKIP_PYBIND11=ON` if the Python bindings fail on a
   protobuf / pybind mismatch. The validation build also needed small
   `std::string(...)` compatibility casts in Gazebo's log and triggered
   publisher systems for newer `gz-transport` headers.
4. Rebuild `asv_wave_sim/gz-waves` against that same pixi Gazebo install. Check
   that `libgz-waves1-rendering-ogre2` links to the pixi `libOgreNext*.2.3.x`
   libraries, not a Homebrew Ogre install.
5. Run Gazebo with the ASV wave plugin install directory on the plugin path.

Example environment checks:

```bash
pixi shell

export PIXI_GZ_PREFIX=${PIXI_GZ_PREFIX:-"$CONDA_PREFIX"}
export ASV_WAVE_SIM_SRC=${ASV_WAVE_SIM_SRC:-"$HOME/gz_ws/src/asv_wave_sim"}
export ASV_WAVE_SIM_BUILD=${ASV_WAVE_SIM_BUILD:-"$HOME/gz_ws/build/gz-waves"}
export ASV_WAVE_SIM_INSTALL=${ASV_WAVE_SIM_INSTALL:-"$HOME/gz_ws/install"}
export GZ_VERSION=harmonic

cmake -S "$ASV_WAVE_SIM_SRC/gz-waves" -B "$ASV_WAVE_SIM_BUILD" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_PREFIX_PATH="$PIXI_GZ_PREFIX" \
  -DCMAKE_INSTALL_PREFIX="$ASV_WAVE_SIM_INSTALL" \
  -DBUILD_TESTING=OFF
cmake --build "$ASV_WAVE_SIM_BUILD" --target install -j"$(sysctl -n hw.ncpu)"

export GZ_WAVES_PLUGIN_PATH="$ASV_WAVE_SIM_INSTALL/lib"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$GZ_WAVES_PLUGIN_PATH:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
export DYLD_LIBRARY_PATH="$GZ_WAVES_PLUGIN_PATH:$PIXI_GZ_PREFIX/lib:${DYLD_LIBRARY_PATH:-}"

otool -L "$GZ_WAVES_PLUGIN_PATH/libgz-waves1-rendering-ogre2.1.0.0.dylib" | grep Ogre
```

That `otool` check should show Ogre libraries from the pixi Gazebo environment
or `@rpath` entries resolved by it. If it shows Homebrew's Ogre path while
Gazebo is running from pixi, rebuild `asv_wave_sim` before debugging the WAM-V
model.

If the water renders but looks too flat or dull, also confirm that this repo's
current `waves_gentle` model is being loaded; the validation runs use the
stronger `wind_speed=5.0`, `steepness=2.0`, `cell_count=256` preset plus the
glossier PBS material in that model. The wave world also uses a lower ambient
light, a warm sun, and a weak sky-fill light so shadows, hull shading, and water
highlights remain visible in the Gazebo GUI.

Build ArduPilot Rover SITL:

```bash
git clone https://github.com/ArduPilot/ardupilot.git "$ARDUPILOT_HOME"
cd "$ARDUPILOT_HOME"
git submodule update --init --recursive
./waf configure --board sitl --debug
./waf rover
```

Build the ArduPilot Gazebo plugin:

```bash
git clone https://github.com/ArduPilot/ardupilot_gazebo.git "$HOME/ardupilot_gazebo"
cd "$HOME/ardupilot_gazebo"
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build . -j4

export GZ_SIM_SYSTEM_PLUGIN_PATH="$HOME/ardupilot_gazebo/build:${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
```

Clone this repository, or your fork of it:

```bash
git clone https://github.com/ArduPilot/SITL_Models.git "$SITL_MODELS_DIR"
```

For the wave world, also build `asv_wave_sim`:

```bash
mkdir -p "$HOME/gz_ws/src"
cd "$HOME/gz_ws/src"
git clone https://github.com/srmainwaring/asv_wave_sim.git

export PIXI_GZ_PREFIX=${PIXI_GZ_PREFIX:-"$CONDA_PREFIX"}
cmake -S "$HOME/gz_ws/src/asv_wave_sim/gz-waves" -B "$HOME/gz_ws/build/gz-waves" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_PREFIX_PATH="$PIXI_GZ_PREFIX" \
  -DCMAKE_INSTALL_PREFIX="$HOME/gz_ws/install" \
  -DBUILD_TESTING=OFF
cmake --build "$HOME/gz_ws/build/gz-waves" --target install -j"$(sysctl -n hw.ncpu)"

export GZ_WAVES_PLUGIN_PATH="$HOME/gz_ws/install/lib"
```

## Launch

From any terminal where `gz` and the plugin paths are available:

```bash
export ARDUPILOT_HOME=$HOME/ardupilot
export SITL_MODELS_DIR=$HOME/SITL_Models

"$SITL_MODELS_DIR/Gazebo/launch/wamv-ardupilot-gazebo.sh"
```

For the wave world:

```bash
export ARDUPILOT_HOME=$HOME/ardupilot
export SITL_MODELS_DIR=$HOME/SITL_Models
export GZ_WAVES_PLUGIN_PATH=$HOME/gz_ws/install/lib

"$SITL_MODELS_DIR/Gazebo/launch/wamv-ardupilot-gazebo-waves.sh"
```

The launch scripts add this repo's models and worlds to `GZ_SIM_RESOURCE_PATH`,
start Gazebo with the GUI, build `ardurover` if needed, then run SITL with
`--model JSON` and the matching parameter file. They use `--wipe` by default so
the included params are applied; set `WIPE_EEPROM=0` to preserve local changes.
`WORLD`, `PARAMS`, `HOME_LOCATION`, and `GZ_PARTITION` may be overridden for
experiments.

## AUTO Mission Demo

After either launch script is running, upload and run the default square mission:

```bash
cd "$SITL_MODELS_DIR"
python3 Gazebo/scripts/wamv_square_mission.py
```

The 60 m wave-circuit validation used the `waves_gentle` preset
`wind_speed=5.0`, `steepness=2.0`, and `wind_angle_deg=135`:

```bash
python3 Gazebo/scripts/wamv_square_mission.py \
  --pattern square \
  --leg-m 60 \
  --acceptance-radius-m 8 \
  --settle-s 8
```

The mission helper connects to `tcp:127.0.0.1:5760`, uploads waypoints, arms,
switches to AUTO, waits for `Mission Complete`, then switches to HOLD and
disarms. It writes CSV and plot outputs under `Gazebo/missions/wamv` unless an
`--output-dir` is provided.

The validation run completed the 60 m circuit in `378.7 s`, ending at
`north=0.7 m`, `east=-1.0 m` in the start frame. The sampled track stayed within
about `-0.4..60.6 m` north and `-1.2..60.7 m` east. Mean track speed was
`0.67 m/s`, 95th percentile speed was `0.98 m/s`, and the SITL attitude log saw
`8.55 deg` max absolute roll and `6.48 deg` max absolute pitch.

## ArduPilot Changes

The tutorial WAM-V does not run ArduPilot SITL out of the box. These changes
were added for the JSON Rover setup:

- Added `imu_link::imu_sensor` and an `ArduPilotPlugin` block using
  `fdm_port_in=9002`, `fdm_addr=127.0.0.1`, `lock_step=1`, and the IMU name.
- Mapped ArduPilot `SERVO1_FUNCTION=73` to the left thruster and
  `SERVO3_FUNCTION=74` to the right thruster.
- Fixed both outboards straight ahead and use differential thrust for steering.
- Added world spherical coordinates matching the SITL home locations.
- Increased the wave-model plugin connection timeout so scripted launch is less
  sensitive to startup order.
- Left out `fdm_port_out` and `use_mavlink_api`; they are not needed for this
  Rover JSON path.

Model changes from the original tutorial reference:

- The calm `model.sdf` replaces the tutorial's custom `libSurface.so` path with
  stock Gazebo buoyancy and hydrodynamic damping.
- The calm model uses simplified box pontoon volumes because Gazebo graded
  buoyancy is more predictable with boxes and spheres.
- Non-hull `base_link` collisions were removed from the buoyant calm model so
  the deck does not generate lift if the boat tips.
- The base-link center of mass and spawn pose were adjusted so SITL starts
  level at a reasonable draft.
- The wave `model_waves.sdf` restores the tutorial-style cylinder pontoon
  collision geometry where practical, then replaces stock hydrodynamics with
  `gz-waves1-hydrodynamics-system`.
- A body-fixed chase camera was added to the wave model for Gazebo recordings.
- The imported WAM-V mesh materials keep their original texture map, but their
  specular and shininess values were raised from the tutorial defaults so the
  dark hull responds to the wave world's directional lighting.

## Starting Parameters

Use the full files in `Gazebo/config`; the most important wave-demo values are:

```text
FRAME_CLASS      2
SERVO1_FUNCTION  73     # left throttle
SERVO3_FUNCTION  74     # right throttle
CRUISE_SPEED     0.75
WP_SPEED         0.75
WP_RADIUS        6.0
WP_ACCEL         0.25
WP_JERK          0.30
WP_PIVOT_ANGLE   0      # carve turns instead of pivoting at square corners
TURN_RADIUS      6.0
ATC_STR_RAT_FF   0.35
ATC_STR_RAT_P    0.12
ATC_STR_RAT_I    0.12
ATC_SPEED_FF     0.16
ATC_SPEED_P      0.45
ATC_SPEED_I      0.18
ATC_SPEED_D      0.03
```

For initial tuning, adjust steering-rate feed-forward first
(`ATC_STR_RAT_FF`), then keep `ATC_STR_RAT_P` and `ATC_STR_RAT_I` lower than FF
to avoid cross-track weave. For wave circuits, `WP_PIVOT_ANGLE=0` was the key
navigation change; pivoting at 90 degree corners made the fixed-thruster boat
stall and spin.

## Wave Tuning

The water surface is `Gazebo/models/waves_gentle/model.sdf`, adapted from the
`asv_wave_sim` `waves` model. To change the sea state, edit both `<wave>`
blocks in that file:

```xml
<wind_speed>5.0</wind_speed>
<wind_angle_deg>135</wind_angle_deg>
<steepness>2.0</steepness>
<cell_count>256</cell_count>
```

Raise `wind_speed` or `steepness` for stronger waves, lower them for calmer
testing, change `wind_angle_deg` to make the wave train hit the hull from a
different direction, and lower `cell_count` if the wave simulation is too
expensive. This model uses the stable `DYNAMIC_GEOMETRY` wave renderer with a
single 256 m wave tile and a glossier PBS water material. The upstream ASV
`ocean_waves` model also has a larger tiled `DYNAMIC_TEXTURE` shader path, but
that path can look like an animated texture layer when the Gazebo EventManager
fix above is missing, and it rendered nearly white in the headless camera
capture used for this demo on the tested macOS Gazebo Sim 8 environment.
