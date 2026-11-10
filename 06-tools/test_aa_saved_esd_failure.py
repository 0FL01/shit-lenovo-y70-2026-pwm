"""Offline regression for the exact failed stock-only 65b1139 capture.

Published test data is synthetic: no raw trace/video, serial, address, boot
identity, captured nonce, PID or timestamp is included. The original external
stdout/stderr are read without modification when available. Neither
the child shell nor any Android operation is executed. Removing an event below
is a diagnostic counterfactual, NEVER evidence admission or a recovery recipe.
"""
import hashlib
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
import unittest

import dsi_trial_transaction as tx
import p85_batched_envelope as envelope

SOURCE = Path('/home/opencode/.cache/legion-y70-aa-baseline-envelope-65b1139-01')
NAME = '0096-envelope-baseline-write'
SIZE = 5930
SHA = '3833a0220298d9f913c8686d7f1189d2da5eb58abcff04343f99ce29d2b17e21'
NONCE = '0123456789ab'  # Synthetic framing identity only.


def bounded_regular_read(path, limit):
    """Do not follow a final symlink or block on a FIFO; reject oversized input."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('Not a bounded regular capture')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Capture grew beyond bound')
        return raw
    finally:
        os.close(fd)


def saved_sections(raw, nonce):
    """Independent forensic framing reader; does not confer runtime admission."""
    prefix = ('@P85E:' + nonce + ':').encode()
    if not raw.startswith(prefix + b'START\n'):
        raise ValueError('Wrong saved capture start')
    cursor = len(prefix + b'START\n')
    result = {}
    for label, expected_rc in (
            ('TRACE_OWNER', 0), ('BEGIN', 0), ('TRACE_BEFORE', 0),
            ('PRE_GUARD', 0), ('TRACE_GUARD', 0), ('CHILD', 51)):
        match = re.match(re.escape(prefix) + b'SECTION ' + label.encode() +
                         rb' ([0-9]{1,3}) ([0-9]{1,9}) 0\n', raw[cursor:])
        if match is None or int(match[1]) != expected_rc:
            raise ValueError('Wrong saved section header')
        length = int(match[2])
        if length > SIZE:
            raise ValueError('Oversized saved section')
        cursor += match.end()
        result[label] = raw[cursor:cursor + length]
        cursor += length
        trailer = b'\n' + prefix + f'END {label}\n'.encode()
        if raw[cursor:cursor + len(trailer)] != trailer:
            raise ValueError('Wrong saved section boundary')
        cursor += len(trailer)
    if cursor != len(raw):
        raise ValueError('Unexpected trailing capture bytes')
    return result


def synthetic_capture():
    """Construct the same failure topology without copying any recorded trace."""
    events = ['synthetic_initial: mode_ctrl_return: '
              '(dsi_display_validate_status+0x0) rc=1\n']
    snapshots = [(-1, ''.join(events))]
    for i, (pending, length) in enumerate(((0, 253), (253, 247), (500, 254))):
        if i == 2:
            events.append('synthetic_added: mode_ctrl_return: '
                          '(dsi_display_validate_status+0x0) rc=1\n')
        events.extend((f'synthetic_block_{i}: mode_entry: pending={pending} '
                       f'length={length} flags=64\n',
                       f'synthetic_block_{i}: mode_return: rc=0\n'))
        snapshots.append((i, ''.join(events)))
    child = ''.join(f'BLOCK_TRACE_BEGIN {i}\n{text}BLOCK_TRACE_END {i}\n'
                    for i, text in snapshots)
    sections = (('TRACE_OWNER', ''), ('BEGIN', ''),
                ('TRACE_BEFORE', snapshots[0][1]),
                ('PRE_GUARD', 'SYNTHETIC_GUARD\n'),
                ('TRACE_GUARD', 'TRACE_GUARD_OK\n'), ('CHILD', child))
    prefix = ('@P85E:' + NONCE + ':').encode()
    raw = prefix + b'START\n'
    for label, text in sections:
        payload = text.encode()
        rc = 51 if label == 'CHILD' else 0
        raw += (prefix + f'SECTION {label} {rc} {len(payload)} 0\n'.encode()
                + payload + b'\n' + prefix + f'END {label}\n'.encode())
    return raw


class SavedESDFailureTests(unittest.TestCase):
    def load_capture(self, raw):
        self.raw = raw
        start = re.match(rb'@P85E:([0-9a-f]{12}):START\n', raw)
        self.assertIsNotNone(start)
        self.nonce = start[1].decode('ascii')
        self.sections = saved_sections(raw, self.nonce)
        self.child = self.sections['CHILD'].decode('utf-8', 'strict')
        self.snapshots = re.findall(
            r'^BLOCK_TRACE_BEGIN (-?\d+)\n(.*?)^BLOCK_TRACE_END \1$',
            self.child, re.M | re.S)

    def setUp(self):
        self.load_capture(synthetic_capture())

    def test_external_original_exact_bytes_and_empty_stderr(self):
        if not SOURCE.exists():
            self.skipTest('External historical cache absent; synthetic tests still run')
        raw = bounded_regular_read(SOURCE / (NAME + '.stdout'), SIZE)
        self.assertEqual(len(raw), SIZE)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), SHA)
        self.assertEqual(bounded_regular_read(SOURCE / (NAME + '.stderr'), 0), b'')
        self.load_capture(raw)
        self.assertEqual(len(self.sections['TRACE_BEFORE']), 666)
        self.assertEqual(len(self.sections['PRE_GUARD']), 29)
        self.assertEqual(len(self.sections['CHILD']), 4727)
        self.test_production_envelope_parser_rejects_child_rc51()
        self.test_independent_transaction_capture_remains_rejected()
        self.test_actual_generated_awk_rejects_new_native_esd_at_block2()

    def test_reader_rejects_symlink_fifo_and_oversized_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / 'capture'
            regular.write_bytes(b'ab')
            link = root / 'link'
            link.symlink_to(regular)
            with self.assertRaises(OSError):
                bounded_regular_read(link, 2)
            with self.assertRaises(ValueError):
                bounded_regular_read(regular, 1)
            fifo = root / 'fifo'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                bounded_regular_read(fifo, 2)

    def test_production_envelope_parser_rejects_child_rc51(self):
        # Commands are inert placeholders: parse uses only metadata, never runs them.
        labels = tuple(self.sections)
        parts = tuple(envelope.Part(label, ':', label == 'CHILD', 1024 * 1024)
                      for label in labels)
        plan = envelope.Envelope(self.nonce, parts, 20, child_command=':')
        # rc=0 here intentionally tests embedded CHILD status independently
        # of any outer transport return code.
        with self.assertRaisesRegex(ValueError, 'Failed/oversized section or stderr'):
            envelope.parse(self.raw, plan, returncode=0, stderr=b'')

    def test_independent_transaction_capture_remains_rejected(self):
        self.assertEqual([int(i) for i, _ in self.snapshots], [-1, 0, 1, 2])
        self.assertEqual(self.sections['TRACE_BEFORE'].decode(),
                         self.snapshots[0][1])
        with self.assertRaisesRegex(ValueError, 'Missing/duplicate transaction evidence'):
            tx.validate_batch_capture(self.child, 0)
        self.assertNotIn('BLOCK_TRACE_BEGIN 3', self.child)
        self.assertNotIn('BLOCK_TRACE_BEGIN 4', self.child)

    def test_actual_generated_awk_rejects_new_native_esd_at_block2(self):
        # Extract the actual generated AWK argv, not a reimplementation of its logic.
        # Never execute the containing shell: it includes forbidden live operations.
        body = shlex.split(tx.transaction_script(
            '/data/local/tmp/offline_esd_saved', '/sys/kernel/tracing/instances/pwm_mode',
            'stock', 0))[-1]
        commands = re.findall(r'^oldc=\$\((awk .*?)\)$', body, re.M | re.S)
        self.assertEqual(len(commands), 6)
        oldc = '-1'
        outcomes = []
        for command, (index, snapshot) in zip(commands, self.snapshots):
            argv = shlex.split(command)
            self.assertEqual(argv[0], 'awk')
            self.assertEqual(argv[-1], '$S')
            argv = [arg.replace('$oldc', oldc) for arg in argv[:-1]]
            result = subprocess.run(argv, input=snapshot, text=True,
                                    capture_output=True, timeout=5, check=False)
            self.assertEqual(result.stderr, '')
            outcomes.append(result.returncode)
            if int(index) < 2:
                self.assertEqual(result.stdout, '1\n')
                oldc = result.stdout.strip()
            else:
                self.assertEqual(result.stdout, '')
                before = self.snapshots[2][1]
                new_events = tx._events(snapshot)[len(tx._events(before)):]
                self.assertEqual(len(new_events), 3)
                esd = new_events[0]
                self.assertIn('dsi_display_validate_status+', esd)
                self.assertTrue(esd.endswith(' rc=1'))
                self.assertIn('pending=500 length=254 flags=64', new_events[1])
                self.assertTrue(new_events[2].endswith(' rc=0'))
                self.assertEqual(tx.check_snapshot(before, 2), [1])
                self.assertEqual(tx.check_snapshot(snapshot, 3, 500, 254, 64), [1, 1])
                # Causal diagnostic ONLY: deleting precisely the added ESD event
                # lets this block guard pass, but cannot complete/admit this batch.
                diagnostic = snapshot.replace(esd + '\n', '', 1)
                counterfactual = subprocess.run(
                    argv, input=diagnostic, text=True, capture_output=True,
                    timeout=5, check=False)
                self.assertEqual((counterfactual.returncode, counterfactual.stdout,
                                  counterfactual.stderr), (0, '1\n', ''))
                with self.assertRaises(ValueError):
                    tx.validate_batch_capture(self.child.replace(
                        snapshot, diagnostic, 1), 0)
        self.assertEqual(outcomes, [0, 0, 0, 51])


if __name__ == '__main__':
    unittest.main()
