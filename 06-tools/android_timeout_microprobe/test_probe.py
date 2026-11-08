import dataclasses
import subprocess
import unittest
import probe

def stat(pid=123, start=456):
    f = ["0"] * 49
    f[18] = str(start)
    return f"{pid} (sh) S " + " ".join(f)

def transcript(rc="124", s=None):
    return ("M1 PID 123\nM1 STAT " + (s or stat()) + "\nM1 TIMEOUT_RC " + rc + "\nM1 END\n").encode()

class ProbeTests(unittest.TestCase):
    def parse(self, raw=None, **kw):
        args = dict(stdout=transcript() if raw is None else raw, stderr=b"", wrapper_rc=0, transport_complete=True)
        args.update(kw)
        return probe.parse_probe(**args)

    def test_fixed(self):
        self.assertIn("/system/bin/timeout -k 1s 1s", probe.ANDROID_COMMAND)
        self.assertEqual(len(probe.COMMAND_SHA256), 64)
        self.assertLess(len(probe.ANDROID_COMMAND), 4096)
        o = self.parse()
        self.assertEqual(o.identity, probe.Identity(123,456))
        self.assertFalse(o.authorizes_next_test)

    def test_bad_transcripts(self):
        raw = transcript()
        bad = [b"", raw[:-1], raw.replace(b"M1 END\n",b""), raw+raw,
               raw.replace(b"PID 123",b"PID 0123"), raw.replace(b"PID 123",b"PID 123;id"),
               transcript(s=stat(124)), transcript(s="broken"), raw.replace(b" S ",b" ? "),
               raw.replace(b" 456 ",b" 0456 "), raw.replace(b"M1 STAT ",b"M1 PID "),
               b"x"*4097+b"\n"]
        for rc in ["0124","+124","124 ","256","-1","TERM","true","124\n"]:
            bad.append(transcript(rc))
        for raw in bad:
            with self.subTest(raw=raw[:40]):
                self.assertRaises(probe.Invalid,self.parse,raw)

    def test_status_separation(self):
        for kw in [dict(wrapper_rc=124),dict(wrapper_rc=False),dict(transport_complete=False),dict(transport_complete=1),dict(stderr=b"warning")]:
            self.assertRaises(probe.Invalid,self.parse,**kw)
        for rc in ["0","1","125","126","127","137","143"]:
            o = self.parse(transcript(rc))
            self.assertEqual(o.meaning,"UNKNOWN")
            self.assertFalse(o.authorizes_next_test)
            self.assertRaises(probe.Invalid,probe.reconciliation_command,o)

    def test_reconcile(self):
        o = self.parse()
        def parse(record, **kw):
            args = dict(raw=("R1 PID 123\n"+record+"\nR1 END\n").encode(),stderr=b"",wrapper_rc=0,transport_complete=True,observation=o)
            args.update(kw)
            return probe.parse_reconciliation(**args)
        self.assertEqual(parse("R1 STAT "+stat()),"ORIGINAL_IDENTITY_PRESENT")
        self.assertEqual(parse("R1 STAT "+stat(start=457)),"PID_REUSED_OBSERVATION_ONLY")
        self.assertEqual(parse("R1 NOT_VISIBLE"),"NOT_VISIBLE_OBSERVATION_ONLY")
        self.assertEqual(parse("R1 READ_FAILED"),"UNKNOWN_READ_FAILED")
        for record in ["R1 STAT "+stat(124),"R1 STAT broken","R1 NOT_VISIBLE\nR1 NOT_VISIBLE","R1 UNKNOWN"]:
            self.assertRaises(probe.Invalid,parse,record)
        self.assertRaises(probe.Invalid,parse,"R1 NOT_VISIBLE",transport_complete=False)
        self.assertRaises(probe.Invalid,parse,"R1 NOT_VISIBLE",raw=b"R1 PID 123\nR1 NOT_VISIBLE\nR1 END")
        for pid in ["123;id",True,0,-1,2147483648]:
            self.assertRaises(probe.Invalid,probe.reconciliation_command,dataclasses.replace(o,identity=probe.Identity(pid,456)))

    def test_actual_fixed_host_only(self):
        # Explicit host-only path substitution, never used to emit Android command.
        command = probe.ANDROID_COMMAND.replace("/system/bin/timeout","/usr/bin/timeout").replace("/system/bin/sh","/bin/sh").replace("/system/bin/sleep","/usr/bin/sleep")
        completed = subprocess.run(["/bin/sh","-c",command],capture_output=True,timeout=8,check=False)
        o = probe.parse_probe(completed.stdout,completed.stderr,completed.returncode,True)
        self.assertEqual(o.timeout_rc,124)
        self.assertFalse(o.authorizes_next_test)
        command = probe.reconciliation_command(o).replace("/system/bin/sh","/bin/sh")
        r = subprocess.run(["/bin/sh","-c",command],capture_output=True,timeout=3,check=False)
        verdict = probe.parse_reconciliation(r.stdout,r.stderr,r.returncode,True,o)
        self.assertIn(verdict,["NOT_VISIBLE_OBSERVATION_ONLY","PID_REUSED_OBSERVATION_ONLY"])

if __name__ == "__main__":
    unittest.main()
