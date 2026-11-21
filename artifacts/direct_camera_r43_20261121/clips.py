#!/usr/bin/env python3
"""Generate and verify R43's reference pair or one custom neutral stimulus."""

import argparse
import hashlib
import json
import os
import struct
import subprocess
import tempfile
from fractions import Fraction
from math import ceil
from pathlib import Path


W, H, SECONDS = 720, 1584, 40
MASTER = "G(8500,39850)B(6550,2300)R(35400,14600)WP(15635,16450)L(2040000,50)"
XY = {"red": (35400, 14600), "green": (8500, 39850), "blue": (6550, 2300),
      "white_point": (15635, 16450)}


def ffmpeg(*args):
    return subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-y", *args])


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_gop_copies(clip, fps, time_base):
    packets = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_packets", "-show_data_hash", "sha256",
        "-show_entries", "packet=pts,dts,duration,flags,data_hash", "-of", "json", clip
    ]))["packets"]
    step = 1 / (fps * Fraction(time_base))
    require(step.denominator == 1 and len(packets) == fps * SECONDS,
            f"{clip.name}: non-integral packet cadence or wrong packet count")
    for i, p in enumerate(packets):
        require(p["pts"] == p["dts"] == i * step and p["duration"] == step,
                f"{clip.name}: wrong packet timestamp/duration at {i}")
        j = i % fps
        require(("K" in p["flags"]) == (j == 0) and
                p["data_hash"] == packets[j]["data_hash"],
                f"{clip.name}: wrong sync flag or packet payload at {i}")
    return (f"All {len(packets)} coded packets verified: {SECONDS} identical closed GOPs "
            f"by per-packet SHA-256; PTS=DTS from 0 in exact 1/{fps} s steps, "
            f"duration 1/{fps} s each; sync packet every {fps} packets.")


def pq_nits(y):
    """ST 2084 reference luminance for a neutral limited-range 10-bit luma code."""
    p = ((y - 64) / 876) ** (32 / 2523)
    return 10000 * (max(p - 3424/4096, 0) / (2413/128 - 2392/128*p)) ** (16384/2610)


def render(tmp, name, fps, custom_y=None):
    hdr = name == "hdr"
    y = (573 if hdr else 721) if custom_y is None else custom_y
    prim, trc, matrix = ("bt2020", "smpte2084", "bt2020nc") if hdr else ("bt709",) * 3
    n = W * H
    frame = struct.pack("<H", y) * n + struct.pack("<H", 512) * (n // 2)
    raw, gop, clip = tmp / "field.yuv", tmp / "second.mp4", tmp / (name + ".mp4")
    raw.write_bytes(frame)
    params = ("pools=none:frame-threads=1:log-level=error:bframes=0:open-gop=0:"
              f"keyint={fps}:scenecut=0:range=limited:colorprim={prim}:transfer={trc}:"
              f"colormatrix={matrix}")
    if hdr:
        peak = ceil(pq_nits(y))  # A uniform field has the same peak and frame-average light level.
        params += f":hdr10=1:master-display={MASTER}:max-cll={peak},{peak}"
    ffmpeg("-stream_loop", "-1", "-f", "rawvideo", "-pixel_format", "yuv420p10le",
           "-video_size", f"{W}x{H}", "-framerate", str(fps), "-i", raw,
           "-frames:v", str(fps), "-an", "-c:v", "libx265", "-profile:v", "main10",
           "-preset", "ultrafast", "-qp", "8", "-x265-params", params,
           "-color_range", "tv", "-colorspace", matrix, "-color_trc", trc,
           "-color_primaries", prim, "-tag:v", "hvc1", gop)
    # Repeat a closed, exactly one-second GOP without re-encoding or timestamp gaps.
    ffmpeg("-stream_loop", str(SECONDS - 1), "-i", gop, "-map", "0:v:0", "-c", "copy",
           "-tag:v", "hvc1", "-movflags", "+faststart+write_colr", clip)

    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_frames", "-read_intervals",
        "%+#1", "-of", "json", clip]))
    stream, = probe["streams"]  # Exactly one track, including audio/subtitle/data tracks.
    fields = dict(codec_type="video", codec_name="hevc", codec_tag_string="hvc1",
                  profile="Main 10", width=W, height=H, pix_fmt="yuv420p10le",
                  color_range="tv", color_primaries=prim, color_transfer=trc, color_space=matrix,
                  avg_frame_rate=f"{fps}/1", nb_frames=str(fps * SECONDS))
    for key, want in fields.items():
        require(stream.get(key) == want, f"{name}: {key} = {stream.get(key)!r}, want {want!r}")
    require(Fraction(stream["duration"]) == SECONDS, f"{name}: wrong duration")
    side = {s["side_data_type"]: s for s in probe["frames"][0].get("side_data_list", [])}
    master = side.get("Mastering display metadata")
    cll = side.get("Content light level metadata")
    if hdr:
        require(master, "hdr: missing mastering display SEI")
        for color, coords in XY.items():
            for axis, value in zip("xy", coords):
                require(Fraction(master[f"{color}_{axis}"]) == Fraction(value, 50000),
                        f"hdr: unexpected mastering {color}_{axis}")
        require(Fraction(master["max_luminance"]) == 204 and
                Fraction(master["min_luminance"]) == Fraction(50, 10000), "hdr: mastering range")
        # At PQ black, x265 may omit the unspecified (0,0) content-light SEI.
        actual_cll = (cll["max_content"], cll["max_average"]) if cll else None
        require(actual_cll == (peak, peak) or (peak == 0 and cll is None), "hdr: MaxCLL/MaxFALL")
    else:
        require(master is None and cll is None, "sdr: unexpected HDR10 SEI")

    decoded = ffmpeg("-i", clip, "-frames:v", "1", "-pix_fmt", "yuv420p10le",
                     "-f", "rawvideo", "pipe:1")
    require(decoded == frame, f"{name}: first decoded field differs from raw YUV reference")
    codes = [struct.unpack_from("<H", decoded, offset)[0] for offset in (0, 2*n, 5*n//2)]
    digest = hashlib.md5(decoded).hexdigest()
    # Custom stimuli and the 120 fps pair use the closed-GOP proof for quick turnaround.
    gop_proof = custom_y is not None or fps == 120
    decode_count = fps if gop_proof else fps * SECONDS
    hashes = ffmpeg("-i", clip, "-frames:v", str(decode_count), "-fps_mode", "passthrough", "-pix_fmt", "yuv420p10le",
                    "-f", "framemd5", "pipe:1").decode().splitlines()
    rows = [r.split(",") for r in hashes if r and not r.startswith("#")]
    require(f"#tb 0: 1/{fps}" in hashes and len(rows) == decode_count,
            f"{name}: decoded timing or frame count")
    for i, (_, dts, pts, dur, size, md5) in enumerate(rows):
        require((int(dts), int(pts), int(dur), int(size), md5.strip()) ==
                (i, i, 1, len(frame), digest), f"{name}: timestamp or pixel mismatch at frame {i}")

    proof = [f"Identical complete frames verified: {len(rows)}; raw frame MD5: {digest}"]
    if gop_proof:
        proof.append(verify_gop_copies(clip, fps, stream["time_base"]))
    if hdr:
        reference = f"Nominal reference luminance from ST 2084 EOTF: {pq_nits(codes[0]):.3f} cd/m²"
    else:
        field = (codes[0] - 64) / 876
        reference = f"BT.709 non-linear luma: {100*field:g}% of legal excursion above black"
    return "\n".join([f"[{clip.name}] {clip.stat().st_size} bytes",
                      "ffprobe: " + json.dumps({k: stream[k] for k in (*fields, 'duration')}),
                      "first-frame mastering display SEI: " + json.dumps(master),
                      "first-frame content light level SEI: " + json.dumps(cll),
                      f"Decoded full field Y'/Cb/Cr (10-bit): {codes[0]}/{codes[1]}/{codes[2]}",
                      *proof, reference])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path, metavar="OUTDIR")
    parser.add_argument("--fps", type=int, choices=(30, 120), default=30,
                        help="coded frames per second (default: 30)")
    parser.add_argument("--one", choices=("sdr", "hdr"), help="write only this clip (requires --y)")
    parser.add_argument("--y", type=int, metavar="CODE", help="neutral 10-bit luma code, 64..940 (requires --one)")
    args = parser.parse_args()
    if (args.one is None) != (args.y is None):
        parser.error("use --one and --y together")
    if args.y is not None and not 64 <= args.y <= 940:
        parser.error("--y must be in the limited 10-bit range 64..940")
    out = args.outdir
    modes = (args.one,) if args.one else ("sdr", "hdr")
    if args.one and (out / ("hdr.mp4" if args.one == "sdr" else "sdr.mp4")).exists():
        parser.error("use a separate OUTDIR for each single-clip receipt")
    os.umask(0o077)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as d:
        tmp = Path(d)
        sections = ["R43: synthetic neutral full-raster fields; no overlays or patches.\n"
                    "Values describe encoded signals and authored metadata, not panel photometry.",
                    subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0]]
        sections.extend(render(tmp, mode, args.fps, args.y) for mode in modes)
        receipt = "\n\n".join(sections) + "\n"
        (tmp / "manifest.txt").write_text(receipt, encoding="utf-8")
        for name in [*(f"{mode}.mp4" for mode in modes), "manifest.txt"]:
            (tmp / name).replace(out / name)
        print(receipt, end="")


if __name__ == "__main__":
    main()
