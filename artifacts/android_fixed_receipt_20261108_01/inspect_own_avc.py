#!/usr/bin/env python3
"""Read-only AVC query restricted to the known owned work inode and device."""
from pathlib import Path
import hashlib,importlib.util,json,re,shlex,sys,time,os
P=Path(__file__).resolve().parent
source=P/'acquire.py'
if hashlib.sha256(source.read_bytes()).hexdigest()!='15a25485992feba95d70bca478fff9777330a252163b22423e08c610b933063c':raise SystemExit('Acquisition changed')
spec=importlib.util.spec_from_file_location('acq',source);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
private=a.PRIVATE
j=json.loads((P/'result.json').read_text());last=j['events'][-1]
a.check(j.get('reserve_accepted') is True and not j.get('capture_accepted') and last['label']=='shell_access_before_capture' and last['rc']==1 and last['transport_complete'] is True,'Not the expected completed pre-capture refusal')
a.check(not (P/'avc_diagnosis.json').exists(),'Diagnosis already recorded')
report={'started_at_utc':a.utc(),'status':'IN_PROGRESS','events':[],'device_mutation':False,'capture_or_seal':False}
def save(): (P/'avc_diagnosis.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
g=a.GuardedADB()
def call(t,label,command,cap=4096):
    event={'label':label,'command_sha256':a.sha(command.encode()),'cap_bytes':cap,'started_at_utc':a.utc(),'transport_complete':False}
    report['events'].append(event);name='avc_'+label
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
    path=a.BASE+'/work'
    raw=read(t,'work_dev_inode',root('test -d '+shlex.quote(path)+' && test ! -L '+shlex.quote(path)+' && /system/bin/stat -c '+shlex.quote('%d:%i')+' '+shlex.quote(path)),cap=128)
    a.check(re.fullmatch(rb'[0-9]+:[0-9]+\n',raw),'Invalid device/inode')
    device,inode=map(int,raw.decode().strip().split(':'))
    uevent=read(t,'device_name',root('/system/bin/cat /sys/dev/block/'+str(os.major(device))+':'+str(os.minor(device))+'/uevent'),cap=2048).decode('ascii')
    names=[x[8:] for x in uevent.splitlines() if x.startswith('DEVNAME=')]
    a.check(len(names)==1 and re.fullmatch(r'[A-Za-z0-9_-]+',names[0]),'Invalid kernel device name')
    devname=names[0]
    pattern='avc: denied.*dev="'+devname+'".*ino='+str(inode)+'([^0-9]|$)'
    command="{ /system/bin/dmesg; rc=$?; printf '__OWN_AVC_DMESG_RC=%s\\n' \"$rc\" >&2; } | /system/bin/grep -E "+shlex.quote(pattern)
    rc,out,err=call(t,'own_inode_avc',root(command),8192)
    a.check(rc in (0,1) and err==b'__OWN_AVC_DMESG_RC=0\n','Log query status/diagnostic not qualified')
    a.check((rc==0 and bool(out)) or (rc==1 and not out),'grep result mismatch')
    lines=out.decode('ascii').splitlines()
    report['matching_lines']=len(lines)
    report['matching_device_and_inode']=True
    report['avc_summaries']=[]
    for line in lines:
        permissions=re.search(r'avc: denied\s+\{([^}]+)\}',line)
        fields={key:(re.search(r'\b'+key+r'=([^ ]+)',line).group(1) if re.search(r'\b'+key+r'=([^ ]+)',line) else None) for key in ('scontext','tcontext','tclass','permissive')}
        report['avc_summaries'].append({'permissions':permissions.group(1).strip().split() if permissions else None,**fields})
    read(t,'boot_after','cat /proc/sys/kernel/random/boot_id',boot)
    read(t,'mutex_after',root('test ! -e '+a.MUTEX+' && test ! -L '+a.MUTEX),b'')
    read(t,'enforcing_after','getenforce',b'Enforcing\n')
    report.update(status='READ_ONLY_AVC_QUERY_COMPLETE',boot_unchanged=True)
except BaseException as exc:report.update(status='STOPPED_REVIEW_REQUIRED',error_type=type(exc).__name__)
finally:report['finished_at_utc']=a.utc();save();print(json.dumps({k:v for k,v in report.items() if k!='events'},sort_keys=True))
sys.exit(0 if report['status']=='READ_ONLY_AVC_QUERY_COMPLETE' else 2)
