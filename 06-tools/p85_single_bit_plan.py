"""OFFLINE ONLY: reviewed-shape proposal, not a device runner or safety proof.

No CLI, shell generation, I/O, imports, or arbitrary-value setter. Byte arrays
are proposed standalone debugfs packet descriptors, never execution approval.
"""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _packet(payload):
    return bytes((0x39, 0, 0, 0, 0, 0, len(payload))) + bytes(payload)


def proposal(stage):
    _require(type(stage) is str and stage in ('candidate14', 'restore15'),
             'Only candidate14 and explicit restore15 are proposed')
    value = 0x14 if stage == 'candidate14' else 0x15
    return (_packet((0xff, 0x5a, 0xa5, 0x23)),
            _packet((0x85, value)),
            _packet((0xff, 0x5a, 0xa5, 0)))


def validate_program(packets, stage):
    _require(type(packets) is tuple and all(type(p) is bytes for p in packets),
             'Immutable exact packet tuple required')
    _require(packets == proposal(stage), 'Not the exact three-packet proposal')
    return {'packets': 3, 'bytes_per_callback': [11, 9, 11],
            'standalone_flags': 0, 'execution_approved': False}


def validate_init(init):
    """Strict offline packet parser, requiring the single known pre-sleep write."""
    _require(type(init) is bytes, 'Expected immutable init bytes')
    position, page = 0, None
    writes, sleepouts = [], []
    while position < len(init):
        _require(position + 7 <= len(init), 'Truncated header')
        header = init[position:position + 7]
        length = int.from_bytes(header[5:7], 'big')
        end = position + 7 + length
        _require(end <= len(init), 'Truncated payload')
        payload = init[position + 7:end]
        if len(payload) == 4 and payload[:3] == b'\xff\x5a\xa5':
            page = payload[3]
        if page == 0x23 and payload[:1] == b'\x85':
            writes.append((position, header, payload))
        if header[0] == 0x05 and payload == b'\x11':
            sleepouts.append(position)
        position = end
    _require(len(writes) == len(sleepouts) == 1, 'Ambiguous85 or sleep-out')
    offset, header, payload = writes[0]
    _require(header == bytes.fromhex('39 00 00 40 00 00 02') and
             payload == b'\x85\x15' and offset < sleepouts[0],
             'Known pre-sleep-out stock85 provenance changed')
    return {'write_offset': offset, 'sleepout_offset': sleepouts[0],
            'value': 0x15, 'live_write_semantics': 'unknown'}


def validate_callback_delta(entries, returns, controllers):
    """Only parsed delta shape; caller must prove prefix, ownership, wire bytes.

    Not a raw trace validator and not enough to establish an empty queue.
    """
    _require(entries == [(0, 11, 0), (0, 9, 0), (0, 11, 0)] and
             returns == [0, 0, 0] and controllers == [0, 0, 0],
             'Unqualified standalone transaction delta')
    return True
