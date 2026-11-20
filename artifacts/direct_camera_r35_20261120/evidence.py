"""Bind accepted R35 files to both SurfaceFlinger snapshots and stock/BL window receipts.

Only link* windows are also bracketed by native DDIC reads. Do not attach a read
from a separate application or mode change to an earlier optical-only window.
"""
import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct_camera_r33_20261120'))
from windows import sf

MODES={90:('4','0x5'),120:('0','0x3'),144:('1','0x1')}
SNAP=re.compile(r'SNAP (\w+) (before|after) hw=(\d+) R35_OK bl=(\d+) epoch=(\d+) FE=(23) sig=(500000) A4=([a-f0-9]{2}) AD=([a-f0-9]{2}) B4=([a-f0-9]{2}) A9=(0e) C1=([a-f0-9]{6}) C2=([a-f0-9]{6}) DBV=([a-f0-9]{4}) page=(0) esd=(reg_read)')


def mode(path,hz):
    hw,color=sf(path)
    modes=set(re.findall(r'activeMode=\{[^\n}]*?vsyncRate=([\d.]+) Hz,[^\n}]*?group=(0x[\da-f]+),',path.read_text()))
    if len(modes)!=1:raise ValueError('ambiguous refresh/group in SF')
    rate,group=modes.pop()
    if (hw,group)!=MODES[hz] or abs(float(rate)-hz)>.05:raise ValueError(f'unexpected mode in {path.name}')
    return hw,rate,group,color


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('archive',type=Path);ap.add_argument('frames_csv',type=Path);ap.add_argument('log',nargs='+');ap.add_argument('--windows',required=True,type=Path);ap.add_argument('--readbacks',required=True,type=Path);a=ap.parse_args()
    e=a.archive
    with a.frames_csv.open() as f: frames=list(csv.DictReader(f))
    ok={};w=[];registers=[];seen=set()
    for line in (e/'windows.log').read_text().splitlines():
        marker,tag,hw,hz,b,ns,n=line.split();assert marker=='WINDOW_OK' and tag not in ok
        ok[tag]=(hw,int(hz),b,int(ns),int(n))
    for log in a.log:
        color=prev=None;snaps={};winlog=(e/log).read_text().splitlines()
        for line in winlog:
            if line.startswith('scene '):color=line.split()[1]
            if line.startswith('SNAP '):
                m=SNAP.fullmatch(line);assert m and prev=='AUDIT esd=reg_read',line
                tag,pos,hw,b=m.group(1,2,3,4);assert (tag,pos) not in snaps and tag in ok and ok[tag][0]==hw and ok[tag][2]==b and int(m[14],16)==int(b)
                assert mode(e/f'{tag}-{pos}-snap.sf',ok[tag][1])[0]==hw
                snaps[tag,pos]=m.groups()[4:];registers.append(m.groups())
            if m:=re.fullmatch(r'WINDOW (\w+) stock BL=(\d+) hwcId=(\d+) count=(\d+)',line):
                tag,b,hw,n=m.groups();expected,hz,dbv,ns,count=ok[tag];assert tag not in seen and (b,hw,int(n))==(dbv,expected,count) and color=='ffffff'
                pre=mode(e/f'{tag}-pre.sf',hz);post=mode(e/f'{tag}-post.sf',hz);assert pre==post and pre[0]==hw
                rows=[r for r in frames if r['phase']==tag];assert sorted(int(r['frame_n']) for r in rows)==list(range(1,count+1))
                for r in rows:
                    assert (r['width'],r['height'],r['iso'],r['focal_mm'],r['orientation'],r['cfa'])==('4080','3072','6400','5.56','1','GBRG')
                    assert abs(float(r['exposure_us'])*1000-ns)<=1,tag
                seen.add(tag);w.append((tag,'stock',color,b,*pre,ns,n,'before+after' if tag.startswith('link') else ''))
            prev=line
        for tag in {k[0] for k in snaps}:
            assert tag.startswith('link') and tag in seen and snaps[tag,'before']==snaps[tag,'after'],tag
    assert seen==set(ok)=={r['phase'] for r in frames}-{'pilot'} and sum(r['phase']=='pilot' for r in frames)==1
    assert {r[0] for r in registers}=={t for t in seen if t.startswith('link')}
    with a.windows.open('w') as f:
        out=csv.writer(f,lineterminator='\n');out.writerow('phase profile scene sysfs_bl hwc_both refresh_both group_both rgb_both exposure_ns frames native_readbacks'.split());out.writerows(w)
    with a.readbacks.open('w') as f:
        out=csv.writer(f,lineterminator='\n');out.writerow('phase position hwc sysfs_bl wake_epoch FE sig_80_82_BA A4 AD B4 A9 C1 C2 DBV return_page_tx esd'.split());out.writerows(registers)


if __name__=='__main__': main()
