"""Verify the accepted probe transcript and export only register/status fields (no device identifiers)."""
import argparse
import csv
from pathlib import Path
import re
import sys

EXPECTED = {'stock':('0e','0e','50','0002be'), '92':('8e','92','90','000010'),
            '9e':('8e','9e','90','000010'), 'a9':('8e','0e','50','000010')}
RX = re.compile(r'receipt=(entry|result) profile=(\w+) epoch=(\d+) A9=0x(\w{2}) 9D=0x(\w{2}) 80=0x(\w{2}) C1="([0-9a-fx ]+)" 00:52="([0-9a-fx ]+)" page=0')


def collect(path, writer):
    current_epoch = None
    text = path.read_text().strip()
    wake_recovery = False
    for chunk in re.split(r'(?m)(?=^(?:RCPT|REJECT) )', text):
        if not chunk:
            continue
        if chunk.strip() == 'REJECT restorea9 no stable awake epoch':
            # Exact observed rejection at entry (before any I/O). Do not fabricate
            # a result/ESD receipt. The next acceptable operation is a fresh stock check.
            writer.writerow(('cleanup','restorea9','declined_no_awake_epoch','','','','','','','',''))
            wake_recovery = True
            continue
        hdr, label, action, rest = chunk.split(maxsplit=3)
        if hdr!='RCPT' or not re.fullmatch(r'\w+', label):
            raise ValueError('unaccepted or malformed probe result')
        lines = rest.splitlines()
        term = re.fullmatch(r'R34_OK action=([\w-]+) epoch=(\d+)', lines[-1]);
        if not term or term[1]!=action or lines[-2]!='ESD_RESTORED reg_read io_rc=0':
            raise ValueError('missing success or ESD restore')
        epoch = term[2]
        if wake_recovery:
            if (label,action)!=('after_native_wake','stock-check') or current_epoch==epoch:
                raise ValueError('missing independent stock recovery')
            wake_recovery=False
        elif current_epoch is not None and current_epoch!=epoch: raise ValueError('wake changed inside session')
        current_epoch = epoch
        if action=='stock-check': expected=['stock']
        else:
            op,code = re.fullmatch('(apply|check|restore)(92|9e|a9)',action).groups()
            expected={'apply':['stock',code], 'check':[code], 'restore':[code,'stock']}[op]
        if len(lines)-2 != len(expected): raise ValueError('unexpected receipt count')
        for i,(line,profile) in enumerate(zip(lines[:-2],expected)):
            r=RX.fullmatch(line)
            if not r or r[1] != ('entry' if i==0 else 'result') or r[2]!=profile or r[3]!=epoch:
                raise ValueError('entry/result profile mismatch')
            c1=bytes(int(v,16) for v in r[7].split()).hex(); dbv=bytes(int(v,16) for v in r[8].split()).hex()
            if (r[4],r[5],r[6],c1)!=EXPECTED[profile] or dbv!='0200': raise ValueError('register mismatch')
            writer.writerow((label,action,r[1],profile,r[4],r[5],r[6],c1,dbv,0,'reg_read'))
    if wake_recovery: raise ValueError('unverified recovery')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('logs',nargs='+',type=Path);args=p.parse_args()
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow(('checkpoint','action','receipt','profile','a9','9d','80','c1','00_52','page_return','esd_after'))
    for source in args.logs: collect(source,out)
