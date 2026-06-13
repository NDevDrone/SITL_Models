# ASV FFT Waves Attribution

This model is adapted from the `waves` world model in
[`srmainwaring/asv_wave_sim`](https://github.com/srmainwaring/asv_wave_sim).

The upstream `asv_wave_sim` repository is licensed GPL-3.0; a copy of that
license is included in this directory as `LICENSE`.

Changes made for this SITL_Models variant:

- Renamed the model to `waves_gentle` so it can coexist with a user's upstream
  `model://waves` installation.
- Kept the upstream-strength FFT starter preset (`wind_speed=5.0`,
  `wind_angle_deg=135`, `steepness=2.0`, `cell_count=256`) for more visible
  wave motion in the WAM-V demo.
- Tuned the PBS water material used by the stable `DYNAMIC_GEOMETRY` renderer
  to reduce roughness and make the captured surface glossier without relying on
  the tiled `DYNAMIC_TEXTURE` shader path.
- Tuned the WAM-V wave world lighting around this water material: lower global
  ambient than the upstream examples, one warm shadow-casting sun, and a weak
  non-shadowing sky fill for hull readability.
