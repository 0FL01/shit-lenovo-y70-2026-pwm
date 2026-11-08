#!/usr/bin/env python3
"""Inspect the downloaded AVR CN ZIP's DTBO and BOE DC tables, without device I/O.

Usage: python3 06-tools/inspect_cn_dtbo.py ROM.zip
Prints JSON to stdout. Byte offsets refer to dtbo.img inside the ZIP.
This decodes stock data for offline analysis; it does not send panel commands.
"""

import json
import struct
import sys
import zipfile


def read_fdt(blob):
    header = struct.unpack_from(">10I", blob)
    magic, total, structure, strings = header[:4]
    strings_size, structure_size = header[8:10]
    assert magic == 0xD00DFEED and total <= len(blob)
    assert strings + strings_size <= total
    assert structure + structure_size <= total
    names = blob[strings:strings + strings_size]
    position = structure
    stack = []
    nodes = {}
    while position < structure + structure_size:
        token, = struct.unpack_from(">I", blob, position)
        position += 4
        if token == 1:
            end = blob.index(b"\0", position)
            stack.append(blob[position:end].decode())
            position = (end + 4) & ~3
            nodes["/".join(stack)] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name_offset = struct.unpack_from(">2I", blob, position)
            position += 8
            name = names[name_offset:names.index(b"\0", name_offset)].decode()
            assert position + length <= structure + structure_size
            nodes["/".join(stack)][name] = (position, blob[position:position + length])
            position = (position + length + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            assert not stack
            return nodes
        else:
            raise ValueError(f"Unknown FDT token {token} at {position - 4}")
    raise ValueError("Missing FDT_END")


def packets(data):
    result = []
    position = 0
    page = None
    while position < len(data):
        assert position + 7 <= len(data)
        header = data[position:position + 7]
        length = int.from_bytes(header[5:7], "big")
        end = position + 7 + length
        assert end <= len(data)
        payload = data[position + 7:end]
        if payload[:3] == b"\xff\x5a\xa5" and len(payload) == 4:
            page = payload[3]
        result.append({
            "offset_in_property": position,
            "page": page,
            "header_hex": header.hex(" "),
            "payload_hex": payload.hex(" "),
        })
        position = end
    return result


def inspect(path):
    with zipfile.ZipFile(path) as archive:
        data = archive.read("dtbo.img")
    magic, total, header_size, entry_size, count, entries_offset, page_size, version = struct.unpack_from(">8I", data)
    assert magic == 0xD7B7AB1E and total <= len(data)
    assert header_size == 32 and entry_size == 32 and version == 0
    result = {
        "archive": path,
        "member": "dtbo.img",
        "status": "reported",
        "scope": "Confirmed bytes in CN archive, not the live panel selection or optical PWM frequency",
        "container_bytes": len(data),
        "dt_table_total_size": total,
        "page_size": page_size,
        "entries": [],
    }
    for index in range(count):
        size, offset, entry_id, revision, *custom = struct.unpack_from(">8I", data, entries_offset + index * entry_size)
        assert offset + size <= total
        nodes = read_fdt(data[offset:offset + size])
        panels = []
        for node, properties in nodes.items():
            if "qcom,mdss-dsi-panel-name" not in properties or "mot_boe_ili" not in node:
                continue
            panel = {"node": node, "name": properties["qcom,mdss-dsi-panel-name"][1].rstrip(b"\0").decode()}
            decoded = {}
            for state in ("on", "off"):
                key = f"qcom,mdss-dsi-dc-{state}-command"
                if key not in properties:
                    continue
                relative, raw = properties[key]
                decoded[state] = packets(raw)
                panel[f"dc_{state}"] = {
                    "property": key,
                    "offset_in_dtbo_img": offset + relative,
                    "size_bytes": len(raw),
                    "packet_count": len(decoded[state]),
                    "transfer_state": properties[key + "-state"][1].rstrip(b"\0").decode(),
                    "raw_hex": raw.hex(" "),
                }
            if set(decoded) == {"on", "off"} and len(decoded["on"]) == len(decoded["off"]):
                panel["aligned_packet_differences"] = [
                    {"packet_index": i, "on": on, "off": off}
                    for i, (on, off) in enumerate(zip(decoded["on"], decoded["off"]))
                    if on != off
                ]
            panels.append(panel)
        root = nodes[""]
        result["entries"].append({
            "index": index, "offset": offset, "size_bytes": size,
            "id": entry_id, "revision": revision, "custom": custom,
            "model": root["model"][1].rstrip(b"\0").decode(),
            "compatible": root["compatible"][1].rstrip(b"\0").decode().split("\0"),
            "msm_id_hex": root["qcom,msm-id"][1].hex(" "),
            "board_id_hex": root["qcom,board-id"][1].hex(" "),
            "boe_panels": panels,
        })
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(json.dumps(inspect(sys.argv[1]), indent=2, ensure_ascii=False))
