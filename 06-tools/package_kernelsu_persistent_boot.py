#!/usr/bin/env python3
"""Wrap the RAM-tested payload with this handset's boot AVB metadata; no device I/O."""
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from package_kernelsu_ram_boot import BASE, ROOT, header

AVB_DIR = ROOT / "sources/gki-15950084/external/avb"
AVB_PIN = "a7c15a79ae2a19e60457adf77e2b0bc89266f163"


def main():
    assert subprocess.check_output(
        ["git", "-C", str(AVB_DIR), "rev-parse", "HEAD"], text=True
    ).strip() == AVB_PIN
    subprocess.run(["git", "-C", str(AVB_DIR), "diff", "--quiet", "HEAD"], check=True)
    tool = AVB_DIR / "avbtool.py"
    spec = importlib.util.spec_from_file_location("avbtool", tool)
    avb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(avb)
    trial = json.loads((BASE / "kernelsu_next/ram_trial.json").read_text())
    assert trial["ram_experiment_pass"] and trial["stock_return_verified"]
    original = ROOT / trial["original_boot"]["path"]
    stock = original.read_bytes()
    assert hashlib.sha256(stock).hexdigest() == trial["original_boot"]["sha256"]
    ram_proof = json.loads((BASE / "kernelsu_next/ram_boot_validation.json").read_text())
    ram = ROOT / ram_proof["image"]
    payload = ram.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == trial["image_sha256"]
    expected_page = bytearray(stock[:4096])
    struct.pack_into("<I", expected_page, 8, header(payload)["kernel_bytes"])
    assert payload[:4096] == expected_page, "Only kernel size may change in boot header"
    _, old_meta, descriptors, partition_size = avb.Avb()._parse_image(
        avb.ImageHandler(str(original), read_only=True)
    )
    hashes = [d for d in descriptors if isinstance(d, avb.AvbHashDescriptor)]
    props = {d.key: d.value for d in descriptors if isinstance(d, avb.AvbPropertyDescriptor)}
    assert len(hashes) == 1 and len(descriptors) == 1 + len(props)
    descriptor = hashes[0]
    assert old_meta.algorithm_type == 0 and old_meta.flags == 0
    assert old_meta.rollback_index == 0 and old_meta.rollback_index_location == 0
    assert descriptor.partition_name == "boot" and descriptor.flags == 0
    assert descriptor.hash_algorithm == "sha256" and partition_size == 100663296
    directory = BASE / "kernelsu_next/persistent"
    directory.mkdir(exist_ok=True)
    output = directory / "boot.img"
    shutil.copyfile(ram, output)
    command = ["python3", str(tool), "add_hash_footer", "--image", str(output),
               "--partition_name", "boot", "--partition_size", str(partition_size),
               "--algorithm", "NONE", "--hash_algorithm", descriptor.hash_algorithm,
               "--salt", descriptor.salt.hex(), "--flags", "0",
               "--rollback_index", "0", "--rollback_index_location", "0"]
    for key, value in props.items():
        command += ["--prop", key + ":" + value.decode("utf-8")]
    subprocess.run(command, check=True)
    # Native verification resolves partition_name to boot.img in the same directory.
    with tempfile.TemporaryDirectory(
        prefix="ksu-original-verify-", dir="/home/stfu/.cache/opencode-tmp/opencode"
    ) as temp:
        link = Path(temp) / "boot.img"
        link.symlink_to(original)
        subprocess.run(["python3", str(tool), "verify_image", "--image", str(link)], check=True)
    subprocess.run(["python3", str(tool), "verify_image", "--image", str(output)], check=True)
    data = output.read_bytes()
    assert len(data) == partition_size and data[:len(payload)] == payload
    footer, new_meta, new_desc, _ = avb.Avb()._parse_image(
        avb.ImageHandler(str(output), read_only=True)
    )
    new_props = {d.key: d.value for d in new_desc if isinstance(d, avb.AvbPropertyDescriptor)}
    assert new_props == props and new_meta.algorithm_type == old_meta.algorithm_type
    assert new_meta.flags == old_meta.flags and footer.original_image_size == len(payload)
    report = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "image": str(output.relative_to(ROOT)), "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(), "target_partition": "boot_b",
        "original": trial["original_boot"], "header": header(data),
        "executable_payload_byte_equal_successful_ram_image": True,
        "avbtool_commit": AVB_PIN, "avb_algorithm_stock_and_new": "NONE",
        "avb_flags_stock_and_new": 0, "rollback_index_stock_and_new": 0,
        "avb_properties_preserved": {k: v.decode("utf-8") for k, v in props.items()},
        "stock_and_candidate_native_avb_hash_verification_pass": True,
        "old_signed_certification_trailers_reused": False,
        "oem_signature_claimed": False, "offline_packaging_pass": True,
        "on_target_persistent_flash_tested": False,
    }
    (directory / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
