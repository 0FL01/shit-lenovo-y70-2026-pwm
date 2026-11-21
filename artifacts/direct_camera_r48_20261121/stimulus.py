#!/usr/bin/env python3
"""Generate and verify R48's 2400-second SDR white clip; write a JSON receipt to stdout."""

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


FPS, SECONDS, Y, C = 120, 2400, 940, 512
R43 = Path(__file__).resolve().parent.parent / "direct_camera_r43_20261121" / "clips.py"


def load_r43():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("r43_clips", R43)
    clips = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(clips)
    return clips


def probe(path, *args):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", *args, "-of", "json", path,
    ]))


def verify_frames(clips, path, time_base):
    n = clips.W * clips.H
    reference = struct.pack("<H", Y) * n + struct.pack("<H", C) * (n // 2)
    frames = probe(path, "-show_frames", "-read_intervals", f"%+#{FPS}")["frames"]
    step = 1 / (FPS * time_base)
    clips.require(len(frames) == FPS, "expected exactly one decoded GOP")
    allowed_side_data = {"H.26[45] User Data Unregistered SEI message"}
    for i, frame in enumerate(frames):
        clips.require(frame["pts"] == frame["best_effort_timestamp"] == i * step,
                      f"wrong decoded timestamp at frame {i}")
        for key in ("color_primaries", "color_transfer", "color_space"):
            clips.require(frame.get(key) == "bt709", f"wrong decoded {key} at frame {i}")
        clips.require(frame.get("color_range") == "tv", f"wrong decoded range at frame {i}")
        sides = {side["side_data_type"] for side in frame.get("side_data_list", [])}
        clips.require(sides <= allowed_side_data, f"unexpected decoded side data at {i}: {sides}")

    with subprocess.Popen([
        "ffmpeg", "-nostdin", "-v", "error", "-i", path, "-map", "0:v:0", "-frames:v", str(FPS),
        "-fps_mode", "passthrough", "-pix_fmt", "yuv420p10le", "-f", "rawvideo", "pipe:1",
    ], stdout=subprocess.PIPE) as proc:
        with proc.stdout as pipe:
            for i in range(FPS):
                clips.require(pipe.read(len(reference)) == reference, f"pixel mismatch at frame {i}")
            clips.require(not pipe.read(1), "unexpected extra decoded bytes")
        clips.require(proc.wait() == 0, "ffmpeg decode failed")
    return hashlib.sha256(reference).hexdigest()


def verify_packets(clips, path, time_base, gop):
    step = 1 / (FPS * time_base)
    clips.require(step.denominator == 1, "nonintegral packet cadence")
    count = 0
    actual_gop = []
    with subprocess.Popen([
        "ffprobe", "-v", "error", "-show_packets", "-show_data_hash", "sha256",
        "-show_entries", "packet=pts,dts,duration,flags,data_hash", "-of", "csv=p=0", path,
    ], stdout=subprocess.PIPE, text=True) as proc:
        with proc.stdout as pipe:
            for i, line in enumerate(pipe):
                pts, dts, duration, flags, digest = line.strip().split(",")
                j = i % FPS
                clips.require(int(pts) == int(dts) == i * step and int(duration) == step,
                              f"wrong PTS/DTS/duration at packet {i}")
                clips.require(("K" in flags) == (j == 0), f"wrong sync flag at packet {i}")
                if i < FPS:
                    actual_gop.append(digest)
                clips.require(digest == (gop if gop is not None else actual_gop)[j],
                              f"packet {i} differs from source GOP")
                count += 1
        clips.require(proc.wait() == 0, "ffprobe packet check failed")
    return count, actual_gop


def generate(clips, tmp):
    source_proof = clips.render(tmp, "sdr", FPS, custom_y=Y)
    source, output = tmp / "sdr.mp4", tmp / "white.mp4"
    repeats, remainder = divmod(SECONDS, clips.SECONDS)
    clips.require(remainder == 0, "output is not a whole number of source copies")
    clips.ffmpeg("-stream_loop", str(repeats - 1), "-i", source, "-map", "0:v:0", "-c", "copy",
                 "-tag:v", "hvc1", "-movflags", "+faststart+write_colr", output)

    original, = probe(source, "-show_streams", "-show_data_hash", "sha256")["streams"]
    final = probe(output, "-show_format", "-show_streams", "-show_data_hash", "sha256")
    stream, = final["streams"]
    keys = ("codec_type", "codec_name", "codec_tag_string", "profile", "width", "height", "pix_fmt",
            "color_range", "color_primaries", "color_transfer", "color_space", "extradata_hash")
    for key in keys:
        clips.require(stream[key] == original[key], f"stream copy changed {key}")
    for key in ("avg_frame_rate", "r_frame_rate"):
        clips.require(Fraction(stream[key]) == FPS, f"wrong {key}")
    time_base = Fraction(stream["time_base"])
    clips.require(Fraction(stream["start_time"]) == Fraction(final["format"]["start_time"]) == 0,
                  "nonzero stream or container start time")
    clips.require(Fraction(stream["duration"]) == Fraction(final["format"]["duration"]) == SECONDS
                  and stream["duration_ts"] * time_base == SECONDS
                  and int(stream["nb_frames"]) == FPS * SECONDS, "wrong clip duration or frame count")
    clips.require(not stream.get("side_data_list"), "unexpected stream side data")

    source_count, gop = verify_packets(clips, source, Fraction(original["time_base"]), None)
    count, _ = verify_packets(clips, output, time_base, gop)
    clips.require(source_count == FPS * clips.SECONDS and count == FPS * SECONDS, "wrong packet count")
    frame_sha256 = verify_frames(clips, output, time_base)
    with output.open("rb") as f:
        file_sha256 = hashlib.file_digest(f, "sha256").hexdigest()
    return output, {
        "file": output.name,
        "bytes": output.stat().st_size,
        "sha256": file_sha256,
        "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        "source": {"render": "direct_camera_r43_20261121/clips.py:render",
                   "duration_seconds": clips.SECONDS, "copies_without_reencoding": repeats,
                   "verification": source_proof.splitlines()},
        "stream": {k: stream[k] for k in (*keys, "avg_frame_rate", "r_frame_rate", "time_base")},
        "duration_seconds": SECONDS,
        "video_tracks": 1,
        "other_tracks": 0,
        "decoded_full_field_y_cb_cr": [Y, C, C],
        "decoded_frames_compared_byte_for_byte": FPS,
        "decoded_frame_sha256": frame_sha256,
        "packet_proof": {"verified_packets": count, "closed_gop_frames": FPS,
                         "identical_closed_gops": SECONDS, "pts_equals_dts": True,
                         "first_pts_seconds": "0", "step_and_packet_duration_seconds": f"1/{FPS}",
                         "last_pts_seconds": str(Fraction(count - 1, FPS))},
        "hdr_metadata": {"mastering_display": None, "content_light_level": None,
                         "unexpected_stream_or_decoded_gop_side_data": False},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path, help="private directory for white.mp4 and scratch")
    args = parser.parse_args()
    os.umask(0o077)
    args.outdir.mkdir(parents=True, exist_ok=True)
    if (args.outdir / "white.mp4").exists():
        parser.error("white.mp4 already exists")
    with tempfile.TemporaryDirectory(prefix="white-build-", dir=args.outdir) as d:
        output, receipt = generate(load_r43(), Path(d))
        # Publish only after verification; link refuses to replace concurrent output.
        os.link(output, args.outdir / output.name)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
