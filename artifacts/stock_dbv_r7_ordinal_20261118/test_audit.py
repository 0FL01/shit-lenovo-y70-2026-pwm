"""Integration/rejection tests against the designated frozen private capture, no writes to it."""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent

def run_tests(src):
    csv_file=HERE/"results"/"ordinal_pairs.csv"
    expected=(HERE/"audit.json").read_bytes()
    log=(src/"oc.log").read_text().splitlines()
    events=[json.loads(line) for line in log]
    idx=next(i for i,e in enumerate(events) if e[1]=="P00_s0_manifest")
    corrupt=events[idx][:]; corrupt[2]={**corrupt[2],"phase":-1}
    shaped_bad=events[idx][:]; shaped_bad[2]={"tag":"P00_s0"}
    csv_lines=csv_file.read_text().splitlines()
    head=csv_lines[0].split(",")
    vals=csv_lines[1].split(","); vals[head.index("Dmax")]="0.9"
    foreign=csv_lines[1].split(","); foreign[head.index("b")]="P99"
    cases=[
        ("positive",None,None,None),
        ("wrong D","D mismatch",None,[csv_lines[0],",".join(vals),*csv_lines[2:]]),
        ("duplicate CSV","duplicate pair/variant",None,[*csv_lines,csv_lines[1]]),
        ("missing CSV","incomplete ordinal CSV",None,csv_lines[:-1]),
        ("foreign pair","unexpected pair/variant",None,[csv_lines[0],",".join(foreign),*csv_lines[2:]]),
        ("duplicate event","duplicate phase event",[*log,log[idx]],None),
        ("missing event","missing or misordered phase event",log[:idx]+log[idx+1:],None),
        ("malformed JSON","invalid log line",[*log,"{"],None),
        ("corrupt phase","manifest identity mismatch",log[:idx]+[json.dumps(corrupt)]+log[idx+1:],None),
        ("malformed payload","QC/manifest mismatch",log[:idx]+[json.dumps(shaped_bad)]+log[idx+1:],None)]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for pat in ("P*_s*.png","P*_s*_qc.json"):
            for file in src.glob(pat):
                (root/file.name).symlink_to(file.resolve())
        for mode in ([],["-O"]):
            for name,err,ls,cs in cases:
                (root/"oc.log").write_text("\n".join(ls if ls is not None else log)+"\n")
                output=root/"pairs.csv"
                output.write_text("\n".join(cs if cs is not None else csv_lines)+"\n")
                c=subprocess.run([sys.executable,*mode,"-B",str(HERE/"audit.py"),str(root),str(output)],
                                 capture_output=True)
                if err is None:
                    if c.returncode!=0 or c.stdout!=expected:
                        raise RuntimeError(f"{mode} {name}: output differs")
                elif c.returncode==0 or c.stdout or "ValueError:" not in c.stderr.decode() or err not in c.stderr.decode():
                    raise RuntimeError(f"{mode} {name}: wrong rejection: "+c.stderr.decode()[-500:])
            print(f"{mode or ['normal']}: 1 byte-identical positive + {len(cases)-1} expected failures")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("private_capture",type=Path)
    run_tests(p.parse_args().private_capture)
