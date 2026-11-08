"""Offline ESD shell-byte and fail-closed regression. No ADB, mounts or devices."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from check_ddic_stock_latch import reader


class ESDReaderTests(unittest.TestCase):
    def body(self, restore_only=False):
        return shlex.split(reader(restore_only, mount_dir='/data/local/tmp/offline_esd_test/dbg',
                                 reads=((0x23, 0xa9, 1),)))[-1]

    def test_literal_newline_bytes_for_both_mode_writes(self):
        body = self.body()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mode'
            for mode in ('esd_sw_sim_success', 'reg_read'):
                lines = [line.strip() for line in body.splitlines()
                         if line.strip().startswith("printf '%s\\n' " + mode + ' >')]
                self.assertEqual(len(lines), 1)
                command = lines[0].split(' || ', 1)[0]
                subprocess.run(['sh', '-c', command], env={**os.environ, 'E': str(path)}, check=True)
                self.assertEqual(path.read_bytes(), mode.encode() + b'\n')
        self.assertNotIn('printf reg_read >', body)
        self.assertNotIn('printf esd_sw_sim_success >', body)

    def test_isolation_readback_precedes_first_query(self):
        body = self.body()
        guard = '[ "$(tr -d \'\\000\' < "$E")" = esd_sw_sim_success ]'
        self.assertIn(guard, body)
        self.assertLess(body.index(guard), body.index('> "$C/rx_cmd"'))
        self.assertLess(body.index(guard), body.index('ESD_ISOLATED'))
        self.assertIn('[ "$m" = reg_read ] || s=33', body)

    def test_restore_only_has_no_isolation_or_register_query(self):
        body = self.body(True)
        self.assertIn("printf '%s\\n' reg_read", body)
        self.assertNotIn('esd_sw_sim_success', body)
        self.assertNotIn('rx_cmd', body)

    def simulated(self, directory, ignore_mode):
        # Rewrite only filesystem/mount plumbing into ordinary temporary files.
        # The generated guards, byte writes, traps and ordering remain unchanged.
        lines = []
        for line in self.body().splitlines():
            if line.startswith('mount ') or line.strip().startswith('umount '):
                lines.append(':')
            elif line.startswith('C='):
                lines.append('C=' + shlex.quote(directory))
            elif line.startswith('E='):
                lines.append('E=' + shlex.quote(directory + '/mode'))
            else:
                lines.append(line)
        body = '\n'.join(lines)
        self.assertNotIn('mount ', body)
        # Model a handler accepting a bytecount but not changing the requested mode.
        prefix = "printf() { if [ \"${2-}\" = " + shlex.quote(ignore_mode) + " ]; then return 0; fi; command printf \"$@\"; }\n"
        return subprocess.run(['sh', '-c', prefix + body], capture_output=True, text=True)

    def test_silent_isolation_noop_stops_before_register_read_and_restores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'mode').write_bytes(b'reg_read\x00')
            (root / 'rx_cmd').write_text('untouched')
            result = self.simulated(directory, 'esd_sw_sim_success')
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('ESD_ISOLATED', result.stdout)
            self.assertEqual((root / 'rx_cmd').read_text(), 'untouched')
            self.assertEqual((root / 'mode').read_bytes(), b'reg_read\n')
            self.assertIn('ESD_RESTORED reg_read', result.stdout)

    def test_silent_restore_noop_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'mode').write_bytes(b'reg_read\x00')
            (root / 'rx_cmd').write_text('untouched')
            result = self.simulated(directory, 'reg_read')
            self.assertEqual(result.returncode, 33)
            self.assertIn('ESD_ISOLATED esd_sw_sim_success', result.stdout)
            self.assertNotIn('ESD_RESTORED reg_read', result.stdout)


if __name__ == '__main__':
    unittest.main()
