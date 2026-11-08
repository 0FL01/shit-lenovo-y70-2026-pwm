#!/usr/bin/env python3
"""Package the validated r59 KernelSU kernel for a RAM-only experiment; no device I/O."""
import hashlib
import json
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/kernel/gki_r59"
TOOLS = ROOT / "sources/gki-15950084/tools/mkbootimg"
PIN = "167f905b0c2bf311fedb039e8b30840176750ae8"


def header(data):
    assert data[:8] == b"ANDROID!", "Not an Android boot image"
    kernel, ramdisk, os_version, size = struct.unpack_from("<4I", data, 8)
    return {
        "version": struct.unpack_from("<I", data, 40)[0],
        "header_bytes": size,
        "kernel_bytes": kernel,
        "ramdisk_bytes": ramdisk,
        "os_version_patch_packed": os_version,
        "cmdline": data[44:1580].split(b"\0")[0].decode("ascii"),
        "signature_bytes": struct.unpack_from("<I", data, 1580)[0],
    }


def main():
    assert subprocess.check_output(
        ["git", "-C", str(TOOLS), "rev-parse", "HEAD"], text=True
    ).strip() == PIN
    subprocess.run(["git", "-C", str(TOOLS), "diff", "--quiet", "HEAD"], check=True)
    proof = json.loads((BASE / "kernelsu_next_validation.json").read_text())
    assert proof["root_kernel_offline_validation_pass"]
    kernel = ROOT / proof["image_path"]
    payload = kernel.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == proof["image_sha256"]
    with (BASE / "google_certified_boot.img").open("rb") as source:
        reference = header(source.read(4096))
    expected = dict(version=4, header_bytes=1584, ramdisk_bytes=0,
                    os_version_patch_packed=0, cmdline="", signature_bytes=0)
    assert {k: reference[k] for k in expected} == expected
    output = BASE / "kernelsu_next/boot-ram-test.img"
    command = ["python3", str(TOOLS / "mkbootimg.py"), "--header_version", "4",
               "--kernel", str(kernel), "--output", str(output)]
    subprocess.run(command, check=True)
    image = output.read_bytes()
    actual = header(image)
    assert {k: actual[k] for k in expected} == expected
    assert actual["kernel_bytes"] == len(payload)
    assert image[4096:4096 + len(payload)] == payload
    assert len(image) == 4096 + ((len(payload) + 4095) // 4096) * 4096
    assert not any(image[4096 + len(payload):]), "Unexpected trailer"
    report = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "image": str(output.relative_to(ROOT)),
        "bytes": len(image), "sha256": hashlib.sha256(image).hexdigest(),
        "header": actual, "mkbootimg_commit": PIN,
        "kernel_proof": "artifacts/kernel/gki_r59/kernelsu_next_validation.json",
        "kernel_sha256": proof["image_sha256"],
        "layout_reference": "Google r59 v4 header; no Motorola/cross-SKU payload used",
        "avb_footer_present": False, "oem_signature_claimed": False,
        "offline_packaging_pass": True,
        "allowed_proposal": "fastboot boot only; NEVER flash this experimental image",
        "on_target_boot_or_vendor_compatibility_verified": False,
        "ramdisk_dependency": "Existing active-slot init_boot/vendor_boot; target RAM path untested",
    }
    (BASE / "kernelsu_next/ram_boot_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
