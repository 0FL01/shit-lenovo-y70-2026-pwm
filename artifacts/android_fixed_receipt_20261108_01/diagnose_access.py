#!/usr/bin/env python3
"""Fixed read-only localization of the completed pre-capture access refusal."""
from pathlib import Path
import hashlib,importlib.util,json,re,shlex,sys,time
P=Path(__file__).resolve().parent
source=P/'acquire.py'
if hashlib.sha256(source.read_bytes()).hexdigest()!='15a25485992feba95d70bca478fff9777330a252163b22423e08c610b933063c':raise SystemExit('Acquisition changed')
spec=importlib.util.spec_from_file_location('acq',source);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
private=a.PRIVATE
j=json.loads((P/'result.json').read_text());last=j['events'][-1]
a.check(j.get('reserve_accepted') is True and not j.get('capture_accepted') and last['label']=='shell_access_before_capture' and last['rc']==1 and last['transport_complete'] is True,'Not the expected completed pre-capture refusal')
a.check(not (P/'access_diagnosis.json').exists(),'Diagnosis already recorded')
report={'started_at_utc':a.utc(),'status':'IN_PROGRESS','events':[],'device_mutation':False,'capture_or_seal':False}
def save(): (P/'access_diagnosis.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
g=a.GuardedADB()
def call(t,label,command,cap=4096):
    event={'label':label,'command_sha256':a.sha(command.encode()),'cap_bytes':cap,'started_at_utc':a.utc(),'transport_complete':False}
    report['events'].append(event);name='diag_'+label
    (private/(name+'.command.txt')).write_text(command);save();start=time.monotonic()
    try:
        rc,out,err=a.bounded_shell(g,t,command,cap=cap)
        for suffix,value in (('stdout',out),('stderr',err)):(private/(name+'.'+suffix)).write_bytes(value)
        event.update(rc=rc,stdout_bytes=len(out),stderr_bytes=len(err),transport_complete=True)
        return rc,out,err
    finally:event['finished_at_utc']=a.utc();event['elapsed_seconds']=time.monotonic()-start;save()
def read(t,label,command,expected=None,cap=4096):
    rc,out,err=call(t,label,command,cap)
    a.check(rc==0 and not err,'Read failed')
    if expected is not None:a.check(out==expected,'Read mismatch')
    return out
def root(command):return 'su -c '+shlex.quote(command)
try:
    g.preflight();report['preflight']=True
    rows=[r.split() for r in g.host('host:devices-l').decode().splitlines()]
    def select(device):
        hits=[r for r in rows if len(r)>2 and r[1]=='device' and 'device:'+device in r];a.check(len(hits)==1,'Not unique')
        ids=[x.split(':',1)[1] for x in hits[0] if x.startswith('transport_id:')];a.check(len(ids)==1 and re.fullmatch('[1-9][0-9]*',ids[0]),'Invalid transport')
        t=int(ids[0]);g.bind(t);return t
    t,c=select('avr'),select('Galaga');a.check(g.identities[str(t)]!=g.identities[str(c)],'Collision')
    read(c,'camera','getprop ro.product.device; getprop ro.boot.hardware.sku; getprop ro.product.model',b'Galaga\nROW\nA001\n')
    read(t,'target','getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce; getprop ro.product.device',b'XT2611-1\nW3WWS36.65-64-4-1\n_b\n6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k\nEnforcing\navr\n')
    read(t,'root_uid',root('id -u'),b'0\n');read(t,'shell_uid','id -u',b'2000\n')
    read(t,'module',root('sha256sum /vendor/lib/modules/msm_drm.ko'),(a.MODULE+'  /vendor/lib/modules/msm_drm.ko\n').encode())
    read(t,'panel',root('cat /sys/class/drm/card0-DSI-1/panelName'),b'boe_ili97701A_682_1440x3168_dsc_cmd_v4\n')
    boot=(private/'boot_before.stdout').read_bytes();read(t,'boot_before','cat /proc/sys/kernel/random/boot_id',boot)
    read(t,'mutex_before',root('test ! -e '+a.MUTEX+' && test ! -L '+a.MUTEX),b'')
    report['conditions']=[]
    tests=[('base_x','-x',''),('source_x','-x','source'),('work_x','-x','work'),('producer_r','-r','source/producer.sh'),('manifest_r','-r','source/manifest'),('work_w','-w','work'),('control_not_r','! -r','control'),('control_not_w','! -w','control')]
    for label,op,rel in tests:
        path=a.BASE+('/'+rel if rel else '')
        rc,out,err=call(t,label,'test '+op+' '+shlex.quote(path),16)
        a.check(rc in (0,1) and not out and not err,'Unexpected access-test outcome')
        report['conditions'].append({'condition':label,'predicate_passed':rc==0})
    report['metadata']=[]
    for i,path in enumerate(('/data','/data/local',a.BASE,a.BASE+'/source',a.BASE+'/control',a.BASE+'/work',a.BASE+'/source/producer.sh',a.BASE+'/source/manifest')):
        q=shlex.quote(path)
        raw=read(t,'stat_'+str(i),root('test ! -L '+q+' && /system/bin/stat -c '+shlex.quote('%u %g %a %f')+' '+q),cap=256)
        a.check(re.fullmatch(rb'[0-9]+ [0-9]+ [0-7]{3,4} [0-9a-f]+\n',raw),'Metadata grammar')
        uid,gid,mode,kind=raw.decode().split()
        context=read(t,'context_'+str(i),root('/system/bin/ls -Zd '+q),cap=1024).decode('ascii').split()[0]
        a.check(re.fullmatch(r'[A-Za-z0-9_:,]+',context),'Context grammar')
        report['metadata'].append({'path':path,'uid':int(uid),'gid':int(gid),'mode':mode,'type_hex':kind,'selinux_context':context})
    read(t,'boot_after','cat /proc/sys/kernel/random/boot_id',boot)
    read(t,'mutex_after',root('test ! -e '+a.MUTEX+' && test ! -L '+a.MUTEX),b'')
    read(t,'enforcing_after','getenforce',b'Enforcing\n')
    report.update(status='READ_ONLY_DIAGNOSIS_COMPLETE',boot_unchanged=True)
except BaseException as exc:report.update(status='STOPPED_REVIEW_REQUIRED',error_type=type(exc).__name__)
finally:report['finished_at_utc']=a.utc();save();print(json.dumps({k:v for k,v in report.items() if k!='events'},sort_keys=True))
sys.exit(0 if report['status']=='READ_ONLY_DIAGNOSIS_COMPLETE' else 2)
