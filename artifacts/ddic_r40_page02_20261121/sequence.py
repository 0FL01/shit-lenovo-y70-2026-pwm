"""R40: fixed, non-retriable page-02 observation; no device I/O at import.

The bench callback returns only after both boundaries (mode, epoch, native TX
page return, ESD and cleanup) are verified. A transport exception aborts without
issuing any further commands. A stable wrong format is different: don't revisit
02, but still do the authorized final control. Decimal values below denote bytes.
"""


def walk(known, candidate):
    """candidate(action) -> (qualified short1 value or None, rejection reason).

    None is allowed only for a completed transaction, never an ambiguous send.
    known(slot, action) verifies canonical values in the same admitted state.
    """
    known('initial', 'ctrl')
    out = {'page': '02', 'reads': [], 'signature': None}

    def observe(action, opcode):
        value, reason = candidate(action)
        if value is not None and (type(value) is not int or not 0 <= value <= 255):
            raise ValueError('invalid qualified byte')
        out['reads'].append(dict(action=action, opcode=opcode, short1=value, rejection=reason))
        return value

    fe = observe('fe', 'FE')
    if fe != 2:
        out['stop'] = 'unqualified_FE' if fe is None else 'FE_does_not_equal_selector'
    else:
        signature = []
        for opcode in ('80', '82', 'BA'):
            values = []
            for pass_, anchor in (('a', 'kfe'), ('b', 'k80')):
                action = pass_ + opcode.lower()
                known('anchor_' + action, anchor)
                val = observe(action, opcode)
                if val is None:
                    out['stop'] = 'unqualified_' + opcode
                    break
                values.append(val)
            if len(values) != 2:
                break
            if values[0] != values[1]:
                out['stop'] = 'nonrepeatable_' + opcode
                break
            signature.append(values[0])
        else:
            out.update(stop='complete', signature=signature)
    known('final', 'ctrl')
    return out
