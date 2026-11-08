#!/usr/bin/python3
"""Offline STK6A2X table/merge evidence; no firmware execution or device access."""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path('/home/stfu/.cache/opencode-tmp/opencode/factory-native-recon-20261107')
RANGES = {
    'initial_table_merge': (0xb231daf8, 0xb231db7c),
    'watchdog': (0xb231d314, 0xb231d578),
    'mode_writer': (0xb231d63c, 0xb231d700),
    'flicker_enable': (0xb231f288, 0xb231f468),
    'als_enable': (0xb231f468, 0xb231f5c8),
    'other_enable': (0xb231f680, 0xb231f7e4),
}
REGISTRY_RANGES = {
    'private_field_callback': (0xb231adb4, 0xb231af90),
    'private_group_decode_and_synthesis': (0xb231b678, 0xb231b830),
    'client_calibration_tail': (0xb2319e10, 0xb2319e70),
}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify(registry=False):
    mdt = (CACHE/'target-adsp/adsp.mdt').read_bytes()
    h = struct.unpack_from('<16sHHIIIIIHHHHHH', mdt)
    check(h[0][:5] == b'\x7fELF\x01' and h[2] == 164, 'Not ELF32 Hexagon')
    segments, data = {}, {}
    for index in (21, 22, 27):
        p = struct.unpack_from('<IIIIIIII', mdt, h[5] + index*h[9])
        data[index] = (CACHE/f'target-adsp/adsp.b{index}').read_bytes()
        check(p[0] == 1 and len(data[index]) == p[4], 'Segment size/type mismatch')
        segments[index] = {'vaddr': p[2], 'filesz': p[4], 'flags': hex(p[6])}
    check(segments[22]['flags'] == '0x8000006', 'Table segment flags changed')
    offset = 0xb259dde0 - segments[22]['vaddr']
    initial = data[22][offset:offset+24]
    mode2 = data[22][offset+32:offset+44]
    mode1 = data[22][offset+48:offset+60]
    check(initial.hex() == '0144770240700500ff0600ff600b3fdb003f6a0bff6b70ff', 'Initial table changed')
    check(mode2.hex() == '03003f041eff0e1737001010', 'Mode2 changed')
    check(mode1.hex() == '03053f04a6ff0e00ff001010', 'Mode1 changed')
    listings = {}
    for index in (21, 27):
        text = (CACHE/f'target-adsp-b{index}-disassembly.txt').read_text()
        listings[index] = {int(m[1], 16): m[2] for m in re.finditer(r'^([0-9a-f]{8}): (.*)$', text, re.M)}
    lib = C.CDLL('/usr/lib64/libLLVM.so.23.1')
    for name in ('LLVMInitializeHexagonTargetInfo', 'LLVMInitializeHexagonTarget',
                 'LLVMInitializeHexagonTargetMC', 'LLVMInitializeHexagonDisassembler'):
        getattr(lib, name)()
    lib.LLVMCreateDisasmCPU.argtypes = [C.c_char_p, C.c_char_p, C.c_void_p, C.c_int, C.c_void_p, C.c_void_p]
    lib.LLVMCreateDisasmCPU.restype = C.c_void_p
    lib.LLVMDisasmInstruction.argtypes = [C.c_void_p, C.c_void_p, C.c_uint64, C.c_uint64, C.c_void_p, C.c_size_t]
    lib.LLVMDisasmInstruction.restype = C.c_size_t
    lib.LLVMDisasmDispose.argtypes = [C.c_void_p]
    context = lib.LLVMCreateDisasmCPU(b'hexagon', b'hexagonv79', None, 0, None, None)
    check(context, 'No Hexagon decoder')
    verified = {}
    try:
        for name, (start, end) in (REGISTRY_RANGES if registry else RANGES).items():
            blob = data[21][start-segments[21]['vaddr']:end-segments[21]['vaddr']]
            buf, out, pos, rows = C.create_string_buffer(blob), C.create_string_buffer(2048), 0, []
            while pos < len(blob):
                size = lib.LLVMDisasmInstruction(context, C.byref(buf, pos), len(blob)-pos, start+pos, out, len(out))
                check(size > 0 and pos+size <= len(blob), f'Undecoded/end at {start+pos:#x}')
                decoded = out.value.decode()
                check(decoded == listings[21].get(start+pos), f'Listing mismatch at {start+pos:#x}')
                rows.append({'va': hex(start+pos), 'bytes': blob[pos:pos+size].hex(), 'decoded': decoded})
                pos += size
            verified[name] = rows
    finally:
        lib.LLVMDisasmDispose(context)
    calls = [hex(a) for index in (21, 27) for a, line in listings[index].items()
             if re.search(r'\b(?:call|jump)(?::\w+)?\s+0xb231d63c\b', line)]
    check(calls == ['0xb231d49c', '0xb231d4c8', '0xb231f330', '0xb231f408', '0xb231f508', '0xb231f744'], 'Direct callers changed')
    # Model ONLY the bounded table merge at daf8..db7c, not the registry decoder.
    # Packet db1c..db28 uses old r6 for its load; it does NOT add base twice.
    allowed = list(initial[::3])
    changed_registers = []
    for register in range(256):
        memory = bytearray(data[22][offset:offset+60])
        for i in range(8):
            j = i*3
            if memory[j] == register:
                memory[j+1] = 0xff  # input value=mask=ff
                memory[j+2] |= 0xff
        check(memory[24:] == data[22][offset+24:offset+60], 'Merge escaped initial table')
        if memory[:24] != initial:
            changed_registers.append(register)
    check(set(changed_registers) == set(allowed), 'Address model mismatch')
    check(not set(allowed) & {3, 4, 14}, 'Timing register unexpectedly admitted')
    config = ROOT/'extracted/XT2611-1/W3WWL36.65-11-18/filesystems/vendor_a/etc/sensors/config/stk6a2x_0.json'
    private = json.loads(config.read_text())['stk6a2x_0_private']['.config']
    result = {'scope': 'Target binary static evidence plus bounded merge model; not live ADC qualification',
            'segments': segments, 'verified_ranges': verified, 'direct_mode_writer_calls_in_saved_b21_b27': calls,
            'initial_table_hex': initial.hex(' '), 'mode2_hex': mode2.hex(' '), 'mode1_hex': mode1.hex(' '),
            'merge_model_register_cases': 256, 'merge_allowed_registers': [hex(x) for x in allowed],
            'maximum_merge_write_va': hex(0xb259dde0+23),
            'reference_config': str(config.relative_to(ROOT)),
            'reference_private_config_not_target_identity': {k: v['data'] for k, v in private.items() if k != 'owner'},
            'limits': ['Direct-call search is not all indirect callsites or unsaved segments',
                       'b22 is writable; bounded merge evidence does not prove no other table writer',
                       'Model tests address bounds, not firmware execution, physical sample timing or Hz'],
            'device_io': False, 'physical_pwm_hz': None}
    if registry:
        # Callback masks/stores are decoded at adb4..af90, not inferred from JSON.
        signed_names = [-1304383281, -1304383270, -1304383259, -1304383248,
                        -1304383237, -1304383231, -1304383225, -1304383216,
                        -1304383206, -1304383196]
        keys = ['als0_dgain', 'als1_dgain', 'als0_again', 'als1_again', 'wait1',
                'wait2', 'autogain', 'autogain0', 'autogain1', 'max_dgain']
        masks = [7, 7, 3, 3, 255, 255, 1, 1, 1, 7]
        fields = []
        for i, (key, signed, mask) in enumerate(zip(keys, signed_names, masks)):
            va = signed & 0xffffffff
            off = va-segments[21]['vaddr']
            name = data[21][off:off+64].split(b'\0', 1)[0].decode()
            check(name == key, 'Target callback name mismatch')
            fields.append({'name': name, 'name_va': hex(va), 'state_offset': 557+i, 'mask': mask})
        packets = []
        for start, end, bits in [(0xb231b678, 0xb231b688, [1, 1, 1, 3]),
                                 (0xb231b80c, 0xb231b818, [1, 1, 3])]:
            offset = start-segments[21]['vaddr']
            words = struct.unpack_from('<'+'I'*((end-start)//4), data[21], offset)
            actual_bits = [(w>>14)&3 for w in words]
            check(actual_bits == bits, 'Call/arguments packet changed')
            packets.append({'start': hex(start), 'end_exclusive': hex(end), 'parse_bits': actual_bits})
        b = [int(private[k]['data']) & mask for k, mask in zip(keys, masks)]
        triples = [(1, (b[0]<<4)|b[1], 0x77), (0xdb, (b[2]<<4)|(b[3]<<2), 0x3c),
                   (5, b[4], 0xff), (6, b[5], 0xff),
                   (0x6a, (b[6]<<3)|(b[8]<<1)|b[7], 0xfb), (0x6b, b[9]<<4, 0x70)]
        merged = bytearray(initial)
        for reg, value, mask in triples:
            for j in range(0, 24, 3):
                if merged[j] == reg:
                    merged[j+1] = (merged[j+1] & (~mask & 255)) | (value & mask)
                    merged[j+2] |= mask
        check(merged == initial, 'CN reference defaults no longer reproduce initial table')
        result['registry_followup'] = {
            'callback': '0xb231adb4', 'callback_literal_in_consumer': '0xb231b6b0',
            'field_names_from_target_bytes': fields, 'verified_call_packets': packets,
            'reference_default_triples_not_live_config': [list(t) for t in triples],
            'reference_default_merge_equals_initial': True,
            'wire_schema_field_ids': 'unknown; generic decoder outside saved target segments',
            'wait05_06_physical_sampling_effect': 'unknown; not inferred from names',
            'calibration_tail_indirect_side_effects': 'not fully resolved',
        }
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--registry', action='store_true', help='Verify the new callback/synthesis/tail ranges')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve existing evidence')
    result = verify(args.registry)
    with args.output.open('x') as handle:
        handle.write(json.dumps(result, indent=2) + '\n')
    print('PASS:', sum(map(len, result['verified_ranges'].values())), 'target records;6direct callers;256bounded-merge cases;no device I/O')
