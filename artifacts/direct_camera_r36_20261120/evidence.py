"""Join R36 optical windows to pre/post SF, camera tags and the surrounding native stock snapshots."""
import argparse
import csv
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'direct_camera_r35_20261120'))
from evidence import mode,need


def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('archive',type=Path);cli.add_argument('frames',type=Path);cli.add_argument('logs',nargs='+');cli.add_argument('--snapshots',required=True,type=Path);a=cli.parse_args()
    with a.frames.open() as f:rr=list(csv.DictReader(f))
    e=a.archive; ws=[];ss=[];seen=set()
    receipts={}
    for line in (e/'windows.log').read_text().splitlines():
        marker,ph,b,ns,n,hw,rgb=line.split();need(marker=='W36' and ph not in receipts,'bad window receipt');receipts[ph]=(b,int(ns),int(n),hw,rgb)
    for log in a.logs:
        tag=values=color=None;captures=[]
        for line in (e/log).read_text().splitlines():
            if m:=re.fullmatch(r'scene (\w{6}) \(.*\)',line):color=m[1]
            if line.startswith('R36_SNAP'):
                m=re.fullmatch(r'R36_SNAP (\w+)_(pre|post) R35_OK bl=(\d+) epoch=(\d+) FE=23 sig=500000 A4=10 AD=10 B4=10 A9=0e C1=([a-f0-9]{6}) C2=(000384) DBV=([a-f0-9]{4}) page=0 esd=reg_read',line)
                need(m and int(m[3])==int(m[7],16) and not captures,'bad native receipt')
                if m[2]=='pre':need(tag is None,'nested native group');tag,values=m[1],m.groups()[2:]
                else:need(tag==m[1] and values==m.groups()[2:],'native profile changed');tag=values=None
                ss.append(m.groups())
            if m:=re.fullmatch(r'frame (\w+)__(\d+) (\d+)',line):
                need(tag is not None and (e/'frames'/f'{m[1]}__{m[2]}.dng').stat().st_size==int(m[3]),'frame outside group or wrong size');captures.append((m[1],int(m[2])))
            if m:=re.fullmatch(r'WINDOW (\w+) stock BL=(\d+) hwcId=(\d+) count=(\d+)',line):
                ph,b,hw,n=m.groups();need(tag is not None and b==values[0] and ph not in seen and ph.startswith(tag),'unbound window');bl,ns,count,h,rgb=receipts[ph];need((b,hw,int(n),color)==(bl,h,count,rgb) and captures==[(ph,j+1) for j in range(count)],'frame order or scene mismatch')
                pre=mode(e/f'{ph}-pre.sf',120);post=mode(e/f'{ph}-post.sf',120);need(pre==post and pre[0]==hw,'mode changed')
                rows=[z for z in rr if z['phase']==ph];need(sorted(int(z['frame_n']) for z in rows)==list(range(1,count+1)) and all(abs(float(z['exposure_us'])*1000-ns)<=1 and (z['iso'],z['focal_mm'],z['cfa'],z['width'],z['height'])==('6400','5.56','GBRG','4080','3072') for z in rows),'DNG tag mismatch')
                ws.append((ph,tag,b,values[-1],rgb,*pre,ns,count));seen.add(ph);captures=[]
        need(not captures and tag is None,'unclosed native or frame group')
    need(seen=={r['phase'] for r in rr}-{'pilot'} and sum(r['phase']=='pilot' for r in rr)==1,'unbound frames')
    out=csv.writer(sys.stdout,lineterminator='\n');out.writerow('phase native_group sysfs_bl DBV scene hwc_both refresh_both group_both matrix_both exposure_ns frames'.split());out.writerows(ws)
    with a.snapshots.open('w') as f:
        out=csv.writer(f,lineterminator='\n');out.writerow('native_group side sysfs_bl wake_epoch C1 C2 DBV'.split());out.writerows(ss)


if __name__=='__main__': main()
