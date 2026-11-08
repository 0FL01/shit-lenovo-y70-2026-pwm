"""Host-only tests. No device transport or executable supplied by the caller."""
import os
from pathlib import Path
import secrets
import subprocess
import unittest
from probe import HOST_TOOLS, parse, render

def fixture():
    result = b"FDMB1\n"
    for name, data in ((b"lf", b"\n"), (b"both", b"\n\0"), (b"sub-lf", b""),
                       (b"sub-nul", b""), (b"sub-err", b"")):
        result += name + b"\n" + str(len(data)).encode() + b"\n" + data
    return result + b"END\n"

class ProbeTests(unittest.TestCase):
    def test_fixed_maps_and_real_host(self):
        self.assertEqual(HOST_TOOLS, {n: "/usr/bin/" + n.lower()
            for n in ("MKDIR", "RM", "RMDIR", "CAT", "CMP", "WC")})
        argv, path = render(secrets.token_hex(12), host=True)
        completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   check=False, timeout=10, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        # Timeout deliberately has no cleanup handler: retain, do not guess/adopt.
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertEqual(completed.stdout, fixture())
        self.assertFalse(os.path.lexists(path))
        self.assertEqual(parse(completed.stdout, completed.stderr, completed.returncode,
                               post_absent=not os.path.lexists(path))["cleanup"],
                         "independently absent")

    def test_real_host_bash_substitution_warning(self):
        argv, path = render(secrets.token_hex(12), host=True)
        # Fixed trusted alternate shell only in host regression, not render API.
        argv[0] = "/bin/bash"
        completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   check=False, timeout=10, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, b"")
        self.assertFalse(os.path.lexists(path))
        result = parse(completed.stdout, completed.stderr, completed.returncode,
                       post_absent=not os.path.lexists(path))
        self.assertEqual(result["command_substitution_nul"], "lost NUL")
        self.assertIn(b"ignored null byte in input", result["substitution_stderr"])
        self.assertEqual(result["cleanup"], "independently absent")

    def test_all_truncations_and_extra(self):
        good = fixture()
        for n in range(len(good)):
            with self.assertRaises(ValueError):
                parse(good[:n], b"", 0)
        for extra in (b"\n", b"\0", b"x"):
            with self.assertRaises(ValueError):
                parse(good + extra, b"", 0)

    def test_boundaries_and_binary_corruption(self):
        good = fixture()
        for out, err, rc in ((good, b"\n", 0), (good, b"\0", 0), (good, b"", 90),
                             (good, b"", True), (good.replace(b"\n\0", b"\nX"), b"", 0),
                             (good.replace(b"both\n2\n", b"both\n1\n"), b"", 0),
                             (good.replace(b"lf\n1\n", b"lf\n01\n"), b"", 0),
                             (b"x" * 4097, b"", 0)):
            with self.assertRaises(ValueError):
                parse(out, err, rc)

    def test_existing_directory_is_not_adopted(self):
        argv, path = render(secrets.token_hex(12), host=True)
        directory = Path(path)
        directory.mkdir(mode=0o700)
        marker = directory / "test-owned-marker"
        marker.write_bytes(b"collision fixture\n")
        completed = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   check=False, timeout=10, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        self.assertEqual(completed.returncode, 90)
        self.assertEqual(completed.stdout, b"")
        self.assertNotEqual(completed.stderr, b"")
        self.assertEqual(marker.read_bytes(), b"collision fixture\n")
        self.assertEqual(list(directory.iterdir()), [marker])
        # Only these two exact paths were created by this test.
        marker.unlink()
        directory.rmdir()

    def test_cleanup_not_claimed(self):
        self.assertTrue(parse(fixture(), b"", 0)["cleanup"].startswith("unverified"))
        self.assertTrue(parse(fixture(), b"", 0, post_absent=False)["cleanup"].startswith("contradicted"))

    def test_nonce_and_android_render_only(self):
        for nonce in ("../x", "A" * 24, "0" * 23, "0" * 25, "x\n"):
            with self.assertRaises(ValueError):
                render(nonce)
        argv, path = render("0123456789abcdef01234567")
        self.assertEqual(argv[0], "/system/bin/sh")
        self.assertEqual(path, "/data/local/tmp/fdbyte-0123456789abcdef01234567")
        self.assertNotIn("/usr/bin/", argv[2])
        self.assertNotIn("@", argv[2])

if __name__ == "__main__":
    unittest.main()
