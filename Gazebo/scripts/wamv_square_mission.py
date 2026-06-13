#!/usr/bin/env python3
"""Upload and run a square AUTO mission for the Gazebo WAM-V SITL model."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import statistics
import time

from pymavlink import mavutil

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - plotting is optional
    plt = None


EARTH_RADIUS_M = 6378137.0


def ll_from_ne(lat0: float, lon0: float, north_m: float, east_m: float) -> tuple[float, float]:
    lat = lat0 + north_m / EARTH_RADIUS_M * 180.0 / math.pi
    lon = lon0 + east_m / (EARTH_RADIUS_M * math.cos(math.radians(lat0))) * 180.0 / math.pi
    return lat, lon


def ne_from_ll(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    north = math.radians(lat - lat0) * EARTH_RADIUS_M
    east = math.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    return north, east


def set_message_interval(master: mavutil.mavfile, msg_id: int, hz: float) -> None:
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        0,
        msg_id,
        1_000_000.0 / hz,
        0,
        0,
        0,
        0,
        0,
    )


def set_mode(master: mavutil.mavfile, mode_name: str, timeout_s: float = 10.0) -> bool:
    modes = master.mode_mapping()
    if mode_name not in modes:
        raise RuntimeError(f"Mode {mode_name!r} is not available; modes are {sorted(modes)}")
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        modes[mode_name],
    )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        heartbeat = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if heartbeat and mavutil.mode_string_v10(heartbeat) == mode_name:
            return True
    return False


def wait_for_position(master: mavutil.mavfile, timeout_s: float) -> mavutil.mavlink.MAVLink_global_position_int_message:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if msg and msg.lat and msg.lon:
            return msg
    raise RuntimeError("Timed out waiting for GLOBAL_POSITION_INT")


def upload_mission(
    master: mavutil.mavfile,
    lat0: float,
    lon0: float,
    relative_alt_m: float,
    waypoints_ne: list[tuple[float, float]],
    waypoint_acceptance_m: float,
) -> list[tuple[float, float]]:
    waypoints_ll = [ll_from_ne(lat0, lon0, north, east) for north, east in waypoints_ne]

    master.mav.mission_clear_all_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_MISSION_TYPE_MISSION,
    )
    time.sleep(0.5)
    master.mav.mission_count_send(
        master.target_system,
        master.target_component,
        len(waypoints_ll),
        mavutil.mavlink.MAV_MISSION_TYPE_MISSION,
    )

    sent: set[int] = set()
    while len(sent) < len(waypoints_ll):
        req = master.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST"], blocking=True, timeout=10)
        if req is None:
            raise RuntimeError(f"Timed out during mission upload after sending {sorted(sent)}")
        seq = int(req.seq)
        lat, lon = waypoints_ll[seq]
        master.mav.mission_item_int_send(
            master.target_system,
            master.target_component,
            seq,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            1 if seq == 0 else 0,
            1,
            0.0,
            waypoint_acceptance_m,
            0.0,
            float("nan"),
            int(round(lat * 1e7)),
            int(round(lon * 1e7)),
            relative_alt_m,
            mavutil.mavlink.MAV_MISSION_TYPE_MISSION,
        )
        sent.add(seq)
        print(f"sent_wp {seq} north={waypoints_ne[seq][0]:.1f} east={waypoints_ne[seq][1]:.1f}")

    ack = master.recv_match(type="MISSION_ACK", blocking=True, timeout=10)
    if ack is None or ack.type != mavutil.mavlink.MAV_MISSION_ACCEPTED:
        raise RuntimeError(f"Mission upload failed: {ack}")
    return waypoints_ne


def build_waypoints(pattern: str, leg_m: float) -> list[tuple[float, float]]:
    if pattern == "square":
        return [
            (0.0, 0.0),
            (0.0, leg_m),
            (leg_m, leg_m),
            (leg_m, 0.0),
            (0.0, 0.0),
        ]
    if pattern == "arc":
        return [
            (0.0, 0.0),
            (0.0, leg_m),
            (0.45 * leg_m, 1.65 * leg_m),
            (1.05 * leg_m, 2.15 * leg_m),
            (1.70 * leg_m, 2.45 * leg_m),
        ]
    raise ValueError(f"Unknown mission pattern {pattern!r}")


def arm(master: mavutil.mavfile, force: bool, timeout_s: float = 15.0) -> bool:
    magic_force = 21196 if force else 0
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1,
        magic_force,
        0,
        0,
        0,
        0,
        0,
    )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        heartbeat = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if heartbeat and heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            return True
    return False


def disarm(master: mavutil.mavfile) -> None:
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def write_plot(
    png_path: Path,
    rows: list[dict[str, float | int | None]],
    waypoints_ne: list[tuple[float, float]],
    title: str,
) -> None:
    if plt is None:
        print("matplotlib not available; skipping plot")
        return

    fig, ax = plt.subplots(figsize=(8, 7), dpi=150)
    ax.plot([r["east_m"] for r in rows], [r["north_m"] for r in rows], lw=2, label="WAM-V track")
    ax.plot([east for north, east in waypoints_ne], [north for north, east in waypoints_ne], "--", color="#444", label="Mission legs")
    ax.scatter([east for north, east in waypoints_ne], [north for north, east in waypoints_ne], s=60, color="#d62728", zorder=5, label="Waypoints")
    for idx, (north, east) in enumerate(waypoints_ne):
        ax.annotate(f"WP{idx}", (east, north), textcoords="offset points", xytext=(6, 6), fontsize=9)
    ax.scatter([rows[0]["east_m"]], [rows[0]["north_m"]], s=70, color="#2ca02c", label="Start", zorder=6)
    ax.scatter([rows[-1]["east_m"]], [rows[-1]["north_m"]], s=70, marker="x", color="#000", label="End", zorder=6)
    ax.set_title(title)
    ax.set_xlabel("East from start (m)")
    ax.set_ylabel("North from start (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="center")
    fig.tight_layout()
    fig.savefig(png_path)
    print(f"png {png_path}")


def print_summary(rows: list[dict[str, float | int | None]]) -> None:
    if len(rows) < 2:
        return
    speeds = []
    for first, second in zip(rows, rows[1:]):
        dt = float(second["t_s"]) - float(first["t_s"])
        if dt <= 0:
            continue
        dn = float(second["north_m"]) - float(first["north_m"])
        de = float(second["east_m"]) - float(first["east_m"])
        speeds.append(math.hypot(dn, de) / dt)

    pitch = [float(r["pitch_deg"]) for r in rows if r["pitch_deg"] is not None]
    roll = [float(r["roll_deg"]) for r in rows if r["roll_deg"] is not None]
    speed_p95 = sorted(speeds)[int(0.95 * (len(speeds) - 1))] if speeds else 0.0

    print(
        "end north={:.1f} east={:.1f} range_north={:.1f}..{:.1f} range_east={:.1f}..{:.1f}".format(
            float(rows[-1]["north_m"]),
            float(rows[-1]["east_m"]),
            min(float(r["north_m"]) for r in rows),
            max(float(r["north_m"]) for r in rows),
            min(float(r["east_m"]) for r in rows),
            max(float(r["east_m"]) for r in rows),
        )
    )
    if speeds:
        print(f"track_speed mean={statistics.mean(speeds):.2f} p95={speed_p95:.2f} max={max(speeds):.2f}")
    if pitch:
        print(f"pitch mean={statistics.mean(pitch):.2f} max_abs={max(abs(value) for value in pitch):.2f}")
    if roll:
        print(f"roll mean={statistics.mean(roll):.2f} max_abs={max(abs(value) for value in roll):.2f}")


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / args.csv
    png_path = out_dir / args.png

    master = mavutil.mavlink_connection(args.connection, autoreconnect=False)
    heartbeat = master.wait_heartbeat(timeout=args.heartbeat_timeout)
    print(f"heartbeat_ok type={heartbeat.get_type()} sys={master.target_system} comp={master.target_component}")

    for msg_id, hz in [
        (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 5),
        (mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD, 2),
        (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 2),
        (mavutil.mavlink.MAVLINK_MSG_ID_MISSION_CURRENT, 2),
    ]:
        set_message_interval(master, msg_id, hz)

    if args.settle_s > 0:
        print(f"settle {args.settle_s:.1f}s")
        time.sleep(args.settle_s)

    start_msg = wait_for_position(master, args.position_timeout)
    lat0 = start_msg.lat / 1e7
    lon0 = start_msg.lon / 1e7
    relative_alt_m = max(0.0, start_msg.relative_alt / 1000.0)
    print(f"start lat={lat0:.7f} lon={lon0:.7f} rel_alt={relative_alt_m:.2f}")

    waypoints_ne = build_waypoints(args.pattern, args.leg_m)
    waypoints_ne = upload_mission(master, lat0, lon0, relative_alt_m, waypoints_ne, args.acceptance_radius_m)
    master.mav.mission_set_current_send(master.target_system, master.target_component, 0)
    time.sleep(0.3)

    if not arm(master, args.force_arm):
        raise RuntimeError("Failed to arm")
    print("armed True")
    print(f"auto_mode {set_mode(master, 'AUTO')}")

    rows: list[dict[str, float | int | None]] = []
    current_seq = -1
    latest_speed = None
    latest_attitude = (None, None, None)
    mission_complete = False
    complete_time = None
    last_print = 0.0
    start_time = time.time()

    while time.time() - start_time < args.max_time_s:
        msg = master.recv_match(
            type=["GLOBAL_POSITION_INT", "MISSION_CURRENT", "MISSION_ITEM_REACHED", "STATUSTEXT", "VFR_HUD", "ATTITUDE"],
            blocking=True,
            timeout=1,
        )
        now = time.time()
        if msg is None:
            continue

        msg_type = msg.get_type()
        if msg_type == "MISSION_CURRENT":
            current_seq = int(msg.seq)
        elif msg_type == "MISSION_ITEM_REACHED":
            print(f"reached_wp {int(msg.seq)} t={now - start_time:.1f}")
        elif msg_type == "STATUSTEXT":
            text = msg.text.strip("\x00")
            if text and (args.verbose_statustext or "DDS" not in text):
                print(f"statustext {text}")
            if "Mission Complete" in text or "Mission complete" in text:
                mission_complete = True
                complete_time = now
        elif msg_type == "VFR_HUD":
            latest_speed = float(msg.groundspeed)
        elif msg_type == "ATTITUDE":
            latest_attitude = (
                math.degrees(msg.roll),
                math.degrees(msg.pitch),
                math.degrees(msg.yaw),
            )
        elif msg_type == "GLOBAL_POSITION_INT":
            north, east = ne_from_ll(lat0, lon0, msg.lat / 1e7, msg.lon / 1e7)
            rows.append(
                {
                    "t_s": now - start_time,
                    "lat": msg.lat / 1e7,
                    "lon": msg.lon / 1e7,
                    "north_m": north,
                    "east_m": east,
                    "mission_seq": current_seq,
                    "groundspeed_m_s": latest_speed,
                    "roll_deg": latest_attitude[0],
                    "pitch_deg": latest_attitude[1],
                    "yaw_deg": latest_attitude[2],
                }
            )
            if now - last_print > args.print_interval_s:
                print(f"track t={now - start_time:.1f} north={north:.1f} east={east:.1f} seq={current_seq} speed={latest_speed}")
                last_print = now

        if mission_complete and complete_time and now - complete_time > 2:
            break

    try:
        set_mode(master, "HOLD")
    except Exception as exc:
        print(f"warning: failed to switch to HOLD: {exc}")
    disarm(master)

    if not rows:
        raise RuntimeError("No track rows captured")

    with csv_path.open("w", newline="") as f:
        fieldnames = ["t_s", "lat", "lon", "north_m", "east_m", "mission_seq", "groundspeed_m_s", "roll_deg", "pitch_deg", "yaw_deg"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"rows {len(rows)}")
    print(f"csv {csv_path}")
    print_summary(rows)
    write_plot(png_path, rows, waypoints_ne, f"WAM-V AUTO Mission Track ({args.pattern}, {args.leg_m:.0f} m scale)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", default="tcp:127.0.0.1:5760", help="MAVLink connection string")
    parser.add_argument("--leg-m", type=float, default=40.0, help="Square side length in meters")
    parser.add_argument("--pattern", choices=["square", "arc"], default="square", help="Mission waypoint pattern")
    parser.add_argument("--acceptance-radius-m", type=float, default=2.0, help="MISSION_ITEM waypoint acceptance radius")
    parser.add_argument("--max-time-s", type=float, default=450.0, help="Mission timeout")
    parser.add_argument("--output-dir", default="Gazebo/missions/wamv", help="Directory for CSV and PNG outputs")
    parser.add_argument("--csv", default="wamv_square_mission.csv", help="CSV output filename")
    parser.add_argument("--png", default="wamv_square_mission.png", help="Plot output filename")
    parser.add_argument("--heartbeat-timeout", type=float, default=30.0)
    parser.add_argument("--position-timeout", type=float, default=30.0)
    parser.add_argument("--settle-s", type=float, default=0.0, help="Delay after MAVLink connection before mission upload")
    parser.add_argument("--print-interval-s", type=float, default=10.0)
    parser.add_argument("--force-arm", dest="force_arm", action="store_true", default=True, help="Use SITL force-arm magic")
    parser.add_argument("--no-force-arm", dest="force_arm", action="store_false", help="Disable SITL force-arm magic")
    parser.add_argument("--verbose-statustext", action="store_true", help="Print all STATUSTEXT messages")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
