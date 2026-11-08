#!/usr/bin/env python3
"""Exact verified-own-file cleanup after a completed failed finite microprobe."""
from pathlib import Path
import hashlib,importlib.util,json,re,shlex,sys,time
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
source=P/'acquire.py'
if hashlib.sha256(source.read_bytes()).hexdigest()!='d23f545f31febfa01194975419d4131ddcc94788b53b2c5f8e05380d9a367573':raise SystemExit('Acquisition changed')
spec=importlib.util.spec_from_file_location('acq',source);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
private=a.PRIVATE
ctx=json.loads((private/'owned-context.json').read_text());nonce=ctx['nonce'];d=ctx['directory']
a.check(re.fullmatch('[0-9a-f]{24}',nonce) and d=='/data/local/tmp/fdbyte-'+nonce,'Invalid owned context')
a.check(not (P/'cleanup.json').exists(),'Cleanup already recorded')
j=json.loads((P/'result.json').read_text());last=j['events'][-1]
a.check(last['label']=='fd_byte_microprobe' and last['transport_complete'] is True and last['rc']==90,'No complete expected failure')
report={'started_at_utc':a.utc(),'events':[],'device_mutation':True, 'cleanup_attempted':False,'status':'IN_PROGRESS'}
def save(): (P/'cleanup.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
def call(t,label,cmd,cap=4096):
    name='cleanup_'+label;(private/(name+'.command.txt')).write_text(cmd)
    event={'label':label,'command_sha256':hashlib.sha256(cmd.encode()).hexdigest(),'started_at_utc':a.utc(),'transport_complete':False,'cap_bytes':cap};report['events'].append(event);save()
    start=time.monotonic()
    try:
        rc,out,err=a.bounded_shell(g,t,cmd,cap=cap)
        for suffix,value in (('stdout',out),('stderr',err)):(private/(name+'.'+suffix)).write_bytes(value)
        event.update(rc=rc,stdout_bytes=len(out),stderr_bytes=len(err),transport_complete=True)
        a.check(rc==0 and not err,'Read-only inventory failed');return out
    finally:event['elapsed_seconds']=time.monotonic()-start;event['finished_at_utc']=a.utc();save()
def read(t,label,cmd,expected,cap=4096):a.check(call(t,label,cmd,cap)==expected,'Read-only guard mismatch')
def root(c):return 'su -c '+shlex.quote(c)
g=a.GuardedADB()
try:
    g.preflight();report['preflight']=True
    rows=[r.split() for r in g.host('host:devices-l').decode().splitlines()]
    def select(device):
        hits=[r for r in rows if len(r)>2 and r[1]=='device' and 'device:'+device in r];a.check(len(hits)==1,'Identity not unique')
        ids=[x.split(':',1)[1] for x in hits[0] if x.startswith('transport_id:')];a.check(len(ids)==1 and re.fullmatch('[1-9][0-9]*',ids[0]),'Invalid transport')
        t=int(ids[0]);g.bind(t);return t
    t,c=select('avr'),select('Galaga');a.check(g.identities[str(t)]!=g.identities[str(c)],'Device collision')
    read(c,'camera','getprop ro.product.device; getprop ro.boot.hardware.sku; getprop ro.product.model',b'Galaga\nROW\nA001\n')
    read(t,'target','getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce; getprop ro.product.device',b'XT2611-1\nW3WWS36.65-64-4-1\n_b\n6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k\nEnforcing\navr\n')
    read(t,'root',root('id -u'),b'0\n')
    read(t,'module',root('sha256sum /vendor/lib/modules/msm_drm.ko'),(a.MODULE+'  /vendor/lib/modules/msm_drm.ko\n').encode())
    read(t,'panel',root('cat /sys/class/drm/card0-DSI-1/panelName'),b'boe_ili97701A_682_1440x3168_dsc_cmd_v4\n')
    boot=(private/'boot_before.stdout').read_bytes();read(t,'boot_before','cat /proc/sys/kernel/random/boot_id',boot)
    read(t,'mutex_before',root('test ! -e '+a.MUTEX+' && test ! -L '+a.MUTEX),b'')
    read(t,'uid','id -u',b'2000\n')
    q=shlex.quote
    raw=call(t,'directory','test -d '+q(d)+' && test ! -L '+q(d)+' && /system/bin/stat -c '+q('%u %a %h %s %f')+' '+q(d))
    fields=raw.decode().strip().split();a.check(len(fields)==5 and fields[0]=='2000' and fields[1]=='700' and int(fields[4],16)&0xf000==0x4000,'Directory ownership/type mismatch')
    names=call(t,'names','/system/bin/ls -A -1 '+q(d)).decode().splitlines()
    first=['expected-both','expected-lf','lf','owner','owner.ref'];second=sorted(first+['both'])
    a.check(sorted(names) in (first,second) and len(set(names))==len(names),'Unexpected entries')
    expected={'owner':('fdbyte-owner-'+nonce+'\n').encode(),'owner.ref':('fdbyte-owner-'+nonce+'\n').encode(),'expected-lf':b'\n','expected-both':b'\n\0','lf':b'' if sorted(names)==first else b'\n'}
    if 'both' in names:expected['both']=b''
    report['entries']=[]
    for name in sorted(names):
        path=d+'/'+name
        raw=call(t,'stat_'+name,'test -f '+q(path)+' && test ! -L '+q(path)+' && /system/bin/stat -c '+q('%u %a %h %s %f')+' '+q(path))
        f=raw.decode().strip().split();a.check(len(f)==5 and f[:3]==['2000','600','1'] and int(f[3])==len(expected[name]) and int(f[4],16)&0xf000==0x8000,'File metadata mismatch')
        read(t,'bytes_'+name,'/system/bin/cat '+q(path),expected[name])
        report['entries'].append({'name':name,'bytes':len(expected[name]),'uid':2000,'mode':'600','nlink':1,'regular_non_symlink':True})
    check_record=json.loads((P/'inspection.json').read_text())
    a.check(check_record['status']=='EXACT_OWNED_REMNANTS_VERIFIED' and check_record['failed_cat']=='first','No prior first-cat inspection')
    a.check(sorted(names)==first,'Changed remnant classification')
    report['cleanup_attempted']=True;save()
    removal='/system/bin/rm '+ ' '.join(q(d+'/'+name) for name in ('expected-both','expected-lf','lf','owner.ref'))
    removal+=' && /system/bin/rm '+q(d+'/owner')+' && /system/bin/rmdir '+q(d)
    read(t,'remove_exact_owned_names',removal,b'')
    read(t,'independent_absence','test ! -e '+q(d)+' && test ! -L '+q(d),b'')
    read(t,'boot_after','cat /proc/sys/kernel/random/boot_id',boot)
    read(t,'mutex_after',root('test ! -e '+a.MUTEX+' && test ! -L '+a.MUTEX),b'')
    report.update(status='EXACT_OWNED_CLEANUP_VERIFIED',failed_cat='first',boot_unchanged=True,cleanup_performed=True)
except BaseException as exc:report.update(status='STOPPED_REVIEW_REQUIRED',error_type=type(exc).__name__)
finally:report['finished_at_utc']=a.utc();save();print(json.dumps({k:v for k,v in report.items() if k!='events'},sort_keys=True))
sys.exit(0 if report['status']=='EXACT_OWNED_CLEANUP_VERIFIED' else 2)
