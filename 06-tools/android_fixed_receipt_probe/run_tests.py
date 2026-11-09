#!/usr/bin/env python3
"""Host-only real shell/filesystem tests, never an Android transport."""
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE_SHA = '922bdfee53feef548d1b5509e682617dbaf49aa7c40e082bbe610b1b5f96d2a4'
MANIFEST = (b'scope=SYNTHETIC_ONLY\nepoch=synthetic_fixed_20261108_01\n'
            b'nonce=synthetic_fixed_nonce_01\nphase=SYNTHETIC_BINARY_01\n'
            b'source=' + SOURCE_SHA.encode() + b'\nstdout_bytes=2\nstderr_bytes=12\nexpected_rc=7\n')
OUT, ERR = b'\n\x00', b'diagnostic\n\x00'
def sha(data):
    return hashlib.sha256(data).hexdigest()

class ProbeTests(unittest.TestCase):
    def setUp(self):
        # No recursive cleanup. Evidence retained in this new directory only.
        self.env = dict(os.environ)
        self.parent = Path(tempfile.mkdtemp(prefix='host-case-', dir=HERE))
        self.base = self.parent / 'fixed-epoch'
        self.boot = self.parent / 'boot.fixture'
        self.boot.write_text('synthetic_boot_01\n')
        values = {'BASE': str(self.base), 'PARENT': str(self.parent),
                  'ROOT_UID': str(os.getuid()), 'SHELL_UID': str(os.getuid()),
                  'PARENT_MODE': '700', 'BOOT': 'synthetic_boot_01',
                  'BOOT_FILE': str(self.boot), 'SH': '/bin/sh',
                  'MANIFEST_SHA': sha(MANIFEST), 'STDOUT_SHA': sha(OUT),
                  'STDERR_SHA': sha(ERR)}
        for phase in ('reserve', 'capture', 'seal'):
            text = (HERE / (phase + '.sh.in')).read_text()
            text = (HERE / 'common.sh.in').read_text() + text
            # Explicit host dialect mapping, never inherited from caller PATH.
            self.assertEqual(text.count('PATH=/system/bin\n'), 1)
            text = text.replace('PATH=/system/bin\n', 'PATH=/usr/bin:/bin\n')
            for key, value in values.items():
                text = text.replace('@' + key + '@', value)
            if '@' in text:
                raise RuntimeError('unresolved placeholder')
            (self.parent / (phase + '.sh')).write_text(text)

    def call(self, phase, *args):
        # Only three fixed scripts, no shell=True or user command API.
        if phase not in ('reserve', 'capture', 'seal'):
            raise ValueError('fixed phase required')
        return subprocess.run(['/bin/sh', str(self.parent / (phase + '.sh')), *args],
                              capture_output=True, check=False, timeout=5, env=self.env)

    def prepared(self):
        self.assertEqual(self.call('reserve').returncode, 0)
        result = self.call('capture')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')
        self.assertEqual((self.base / 'work/stdout').read_bytes(), OUT)
        self.assertEqual((self.base / 'work/stderr').read_bytes(), ERR)
        return result

    def reject(self, *args):
        result = self.call('seal', *args)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'control/complete').exists())

    def test_actual_negative_binary_and_receipt(self):
        result = self.prepared()
        self.assertEqual(self.call('seal', str(result.returncode)).returncode, 0)
        self.assertEqual((self.base / 'control/stdout').read_bytes(), OUT)
        self.assertEqual((self.base / 'control/stderr').read_bytes(), ERR)
        receipt = (self.base / 'control/receipt').read_text()
        for field in ('actual_rc=7', 'producer_outcome=EXPECTED_NEGATIVE',
                      'structure=COMPLETE', 'boot=synthetic_boot_01',
                      'epoch=synthetic_fixed_20261108_01', 'phase=SYNTHETIC_BINARY_01',
                      'nonce=synthetic_fixed_nonce_01', 'source=' + SOURCE_SHA,
                      'manifest=' + sha(MANIFEST), 'stdout=2:' + sha(OUT),
                      'stderr=12:' + sha(ERR)):
            self.assertIn(field + '\n', receipt)
        self.assertEqual((self.base / 'control/receipt').stat().st_mode & 0o777, 0o400)
        self.assertNotEqual(self.call('seal', '7').returncode, 0)

    def test_source_manifest_pins(self):
        self.assertEqual(sha((HERE / 'producer.sh').read_bytes()), SOURCE_SHA)
        self.assertEqual(self.call('reserve').returncode, 0)
        self.assertEqual((self.base / 'source/manifest').read_bytes(), MANIFEST)

    def test_reused_epoch_and_nonce(self):
        self.prepared()
        self.assertNotEqual(self.call('reserve').returncode, 0)
        self.assertNotEqual(self.call('capture').returncode, 0)

    def test_stale_valid_bytes_cannot_dispatch(self):
        self.assertEqual(self.call('reserve').returncode, 0)
        (self.base / 'work/stdout').write_bytes(OUT)
        (self.base / 'work/stderr').write_bytes(ERR)
        result = self.call('capture')
        self.assertNotEqual(result.returncode, 7)
        self.reject(str(result.returncode))

    def test_status_loss(self):
        self.prepared()
        self.reject()

    def test_status_changed_to_success(self):
        self.prepared()
        self.reject('0')

    def test_missing_producer(self):
        self.assertEqual(self.call('reserve').returncode, 0)
        self.reject('7')

    def test_source_substitution(self):
        self.prepared()
        path = self.base / 'source/producer.sh'
        path.chmod(0o600); path.write_bytes(b'exit 7\n'); path.chmod(0o444)
        self.reject('7')

    def test_manifest_substitution(self):
        self.prepared()
        path = self.base / 'source/manifest'
        path.chmod(0o600); path.write_bytes(b'other\n'); path.chmod(0o444)
        self.reject('7')

    def test_wrong_boot(self):
        self.prepared()
        self.boot.write_text('other_boot\n')
        self.reject('7')

    def test_wrong_state(self):
        self.prepared()
        (self.base / 'control/state').write_text('COMPLETE\n')
        self.reject('7')

    def test_wrong_mode(self):
        self.prepared()
        (self.base / 'work/stdout').chmod(0o644)
        self.reject('7')

    def test_wrong_uid_expectation(self):
        self.prepared()
        path = self.parent / 'seal.sh'
        path.write_text(path.read_text().replace('SHELL_UID=' + str(os.getuid()),
                                               'SHELL_UID=' + str(os.getuid() + 1)))
        self.reject('7')

    def test_wrong_type(self):
        self.prepared()
        path = self.base / 'work/stdout'; path.unlink(); path.mkdir(mode=0o600)
        self.reject('7')

    def test_symlink(self):
        self.prepared()
        path = self.base / 'work/stdout'; path.unlink(); path.symlink_to('stderr')
        self.reject('7')

    def test_hardlink(self):
        self.prepared()
        os.link(self.base / 'work/stdout', self.parent / 'owned-alias')
        self.reject('7')

    def test_missing_output(self):
        self.prepared()
        (self.base / 'work/stderr').unlink()
        self.reject('7')

    def test_extra_hidden_output(self):
        self.prepared()
        (self.base / 'work/.extra').write_bytes(b'')
        self.reject('7')

    def test_nonempty_dispatch_claim(self):
        self.prepared()
        extra = self.base / 'work/dispatched/extra'
        extra.write_bytes(b'finite foreign entry')
        self.reject('7')
        self.assertEqual(extra.read_bytes(), b'finite foreign entry')

    def test_lf_nul_diagnostics_corrupted(self):
        self.prepared()
        (self.base / 'work/stderr').write_bytes(b'diagnostic\n\n')
        self.reject('7')

    def test_incomplete_publication_no_retry(self):
        self.prepared()
        (self.base / 'control/stdout').write_bytes(OUT)
        self.reject('7')
        self.assertTrue((self.base / 'control/seal_attempt').is_dir())
        self.reject('7')

    def test_cleanup_uncertainty_retains_everything(self):
        self.prepared()
        (self.base / 'work/foreign').write_bytes(b'unknown')
        self.reject('7')
        self.assertEqual((self.base / 'work/foreign').read_bytes(), b'unknown')
        self.assertTrue((self.base / 'control/state').is_file())
        self.assertTrue(self.base.is_dir())

    def utility_fault(self, name):
        self.prepared()
        binary = shutil.which(name, path='/usr/bin:/bin')
        self.assertIsNotNone(binary)
        folder = self.parent / 'fault-bin'; folder.mkdir(mode=0o700)
        wrapper = folder / name
        wrapper.write_text('#!/bin/sh\n' + binary + ' "$@"\nexit 9\n')
        wrapper.chmod(0o700)
        # Fault injection changes only this private rendered host seal.
        script = self.parent / 'seal.sh'
        script.write_text(script.read_text().replace(
            'PATH=/usr/bin:/bin\n', 'PATH=' + str(folder) + ':/usr/bin:/bin\n'))
        self.reject('7')

    def test_id_valid_stdout_failed_status(self):
        self.utility_fault('id')

    def test_stat_valid_stdout_failed_status(self):
        self.utility_fault('stat')

    def test_cat_valid_stdout_failed_status(self):
        self.utility_fault('cat')

    def test_hash_valid_stdout_failed_status(self):
        self.utility_fault('sha256sum')

    def test_wc_valid_stdout_failed_status(self):
        self.utility_fault('wc')

if __name__ == '__main__':
    unittest.main(verbosity=2)
