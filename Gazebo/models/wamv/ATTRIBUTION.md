# WAM-V Attribution

This model is based on the WAM-V example from the Gazebo Sim 8 surface
vehicles tutorial:

- Tutorial: https://gazebosim.org/api/sim/8/surface_vehicles.html
- Source archive: https://github.com/gazebosim/gz-sim/blob/gz-sim8/tutorials/files/surface_vehicles/gz_maritime_ws.zip
- Source repository: https://github.com/gazebosim/gz-sim

The original Gazebo Sim repository is licensed under Apache-2.0. A copy of the
Apache-2.0 license is included as `LICENSE` in this directory.

The SDF in this directory was reduced and adapted for ArduPilot Gazebo SITL.
Those changes add the ArduPilot JSON plugin, an IMU, stock Gazebo buoyancy and
hydrodynamics, and a differential-thrust Rover control mapping.

`model_waves.sdf` is a wave-world variant of the same tutorial-derived WAM-V.
It keeps the tutorial collision geometry where practical and adds ASV
`gz-waves` hydrodynamics plus a chase camera for SITL demos.
