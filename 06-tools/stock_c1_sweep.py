#!/usr/bin/env python3
"""One stock brightness/C1 sweep; camera and unknown panel registers untouched.

Offline planning/import performs no transport I/O. Live execution is for the
coordinator only, with ordinary same-target reboot/watchdog recovery authorized.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import time
import uuid

import capture_ddic_c1 as c1
from a9_reproduction import lock_commands
from dsi_trial_transaction import (marker_interval, native_state, qualify_quiet,
                                   refresh_restore_order, stock_anchor_settings,
                                   validate_stock_anchor)

POINTS = (828,460,2048,3000,3600,828)
BL = '/sys/class/backlight/panel0-backlight/'
CON = '/sys/class/drm/card0-DSI-1/'
KEYS = ('screen_brightness','screen_brightness_mode','min_refresh_rate',
        'peak_refresh_rate','screen_off_timeout')
MODULE_SHA = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
check = c1.check
q = shlex.quote


def now(): return datetime.now(timezone.utc).isoformat()


def plan(experiment_id):
    check(re.fullmatch(r'[a-z][a-z0-9_]{7,63}', experiment_id), 'Invalid experiment ID')
    return {'experiment_id':experiment_id, 'points':list(POINTS),
            'marker':'PWM_STOCK_C1_' + experiment_id, 'module_sha256':MODULE_SHA,
            'stock_dc':0, 'software_refresh_hz':120, 'anchor':[90,120],
            'camera_touched':False, 'unknown_register_writes':False,
            'recovery':'same-target ordinary reboot; device watchdog600s',
            'pwm_hz':None, 'scope':'Stock brightness mapping and qualified C1 observations only'}


def guarded_reader(nonce, dbv, token):
    """Preserve successful C1 trace, but do not append DSI after shell failure.

    The original standalone reader is unchanged. Failure cleanup may stop own
    tracing/unmount/remove probes, but leaves ESD isolated for reboot recovery.
    This cannot undo commands already accepted before a transport failure.
    """
    check(c1.MODULE_SHA == MODULE_SHA, 'Re-audit changed C1 module')
    parts = shlex.split(c1.reader_script(nonce, dbv, 120, held_token=token))
    check(len(parts)==9 and parts[:8]==['timeout','-k','3','30','unshare','-m','/system/bin/sh','-c'],
          'Changed C1 wrapper')
    body = parts[8]
    # TX debugfs returns input bytecount even when its native callback fails.
    # Inspect actual returns before sending the next DSI operation, not just
    # the printf exit code. This extra entry probe also catches queued flags.
    group='pwm_c1_'+nonce
    add='added="$added tx_'+nonce+'"'
    check(body.count(add)==1,'Changed probe installation')
    entry=('p:'+group+'/entry_'+nonce+' msm_drm:dsi_display_cmd_transfer '
           'pending=+0x694($arg2):u32 length=$arg4:u32 flags=+3($arg3):u8')
    body=body.replace(add,add+"\nprintf '%s\\n' "+q(entry)+
                      ' >> /sys/kernel/tracing/kprobe_events\nadded="$added entry_'+nonce+'"')
    gate = r'''previous_events=''; previous_count=0
gate() {
 [ "$(cat "$T/tracing_on")" = 1 ] || return 43
 snapshot=$(cat "$T/trace") || return 43
 events=$(printf '%s\n' "$snapshot" | awk -v nonce="NONCE" 'index($0,"_" nonce ":") {print}') || return 43
 prefix=$(printf '%s\n' "$events" | awk -v n="$previous_count" 'NR<=n') || return 43
 [ "$prefix" = "$previous_events" ] || return 43
 profiles=$(cat /sys/kernel/tracing/kprobe_profile) || return 43
 printf '%s\n' "$profiles" | awk -v stage="$1" -v nonce="NONCE" '
 BEGIN {pages=(stage==0?0:(stage==1?1:stage-1)); reads=(stage>=2?1:0);
        want["ctrl_"nonce]=stage;want["tx_"nonce]=pages;want["entry_"nonce]=pages;
        want["header_"nonce]=reads;want["hardware_"nonce]=reads}
 $1 in want {seen[$1]++; if(NF!=3 || $2!=want[$1] || $3!=0)bad=1}
 END {for(name in want)if(seen[name]!=1)bad=1; exit bad?1:0}' || return 43
 printf '%s\n' "$snapshot" | awk -v stage="$1" -v nonce="NONCE" '
 function field(key, i,a) { for(i=1;i<=NF;i++) {split($i,a,"="); if(a[1]==key)return a[2]} return "MISSING" }
 function pid(t) {t=$1; sub(/^.*-/,"",t); return t}
 /LOST/ {bad=1}
 index($0,"entry_" nonce ":") {en++; seq=seq "e"; ep=pid(); if(field("pending")!="0" || field("length")!="11" || field("flags")!="0")bad=1}
 index($0,"ctrl_" nonce ":") {cn++; seq=seq "c"; cp=pid(); want=(cn==2 ? "3" : "0"); if(field("rc")!=want)bad=1; if(cn==2)rp=cp; else if(cp!=ep)bad=1}
 index($0,"tx_" nonce ":") {tn++; seq=seq "t"; if(field("rc")!="0" || pid()!=ep || pid()!=cp)bad=1}
 index($0,"header_" nonce ":") {hn++; seq=seq "h"; hp=pid(); if(field("header")!="0x1600031c" || field("requested")!="3" || field("count")!="9" || field("allocation")!="16" || field("disp_op")!="0")bad=1}
 index($0,"hardware_" nonce ":") {wn++; seq=seq "w"; wp=pid(); status=field("hw_status"); if((status!="0x90000" && status!="0xd0000") || field("read_bytes")!="16" || field("mrps")!="3")bad=1}
 END {pages=(stage==0?0:(stage==1?1:stage-1)); reads=(stage>=2?1:0);
      expected=(stage==0?"":(stage==1?"ect":(stage==2?"ectwhc":(stage==3?"ectwhcect":"ectwhcectect")))); if(seq!=expected)bad=1;
      if(cn!=stage || tn!=pages || en!=pages || hn!=reads || wn!=reads)bad=1;
      if(reads && (hp!=wp || hp!=rp || hp !~ /^[0-9]+$/))bad=1; exit bad?1:0}' || return 43
 previous_events=$events
 previous_count=$(printf '%s\n' "$events" | awk 'NF {n++} END {print n+0}') || return 43
 printf 'GATE_OK %s\n' "$1"
}
'''.replace('NONCE',nonce)
    body=body.replace('cleanup() {',gate+'cleanup() {',1)
    condition = 'if [ "$mounted" = 1 ] && [ "$touched" = 1 ]; then'
    check(body.count(condition)==2, 'Changed C1 cleanup contract')
    body = body.replace(condition, 'if [ "$s" = 0 ] && [ "$mounted" = 1 ] && [ "$touched" = 1 ]; then')
    cleanup_write='   printf \'%s\' "$P0" > "$C/tx_cmd" || s=31'
    check(body.count(cleanup_write)==1,'Changed cleanup page0 write')
    body=body.replace(cleanup_write,'   gate 3 || s=43\n   if [ "$s" = 0 ]; then\n'+
                      cleanup_write+'\n     if [ "$s" = 0 ]; then gate 4 || s=44; fi\n   fi')
    page23="printf '%s' '0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0x23' > \"$C/tx_cmd\""
    query="printf '%s' '3 0x06 1 0 1 0 0 1 0xC1' > \"$C/rx_cmd\""
    page0="\nprintf '%s' \"$P0\" > \"$C/tx_cmd\"\n"
    for old,new in [(page23,'gate 0\n'+page23+'\ngate 1'),
                    (query,query+'\ngate 2'),(page0,page0+'gate 3\n')]:
        check(body.count(old)==1,'Changed C1 operation boundary')
        body=body.replace(old,new)
    check(body.count("'3 0x06 1 0 1 0 0 1 0xC1'")==1, 'Changed fixed C1 request')
    return ' '.join(q(x) for x in parts[:8]) + ' ' + q(body)


def validate_adapter_capture(raw,nonce,dbv):
    data=c1.validate_capture(raw,nonce,dbv,120)
    check(re.findall(r'^GATE_OK (\d+)$',raw,re.M)==['0','1','2','3','3','4'],
          'Missing in-device return gate')
    entries=re.findall(r'\bentry_'+nonce+r':.*?pending=(\d+) length=(\d+) flags=(\d+)',raw)
    check(entries==[('0','11','0')]*3,'Unexpected pending/queued page entry')
    rows=re.findall(r'^\s*entry_'+nonce+r'\s+(\d+)\s+(\d+)\s*$',raw,re.M)
    check(len(rows)==1 and int(rows[0][0])>=3 and rows[0][1]=='0','Extra entry probe misses')
    return {**data,'in_device_return_gates_verified':True,'page_entries_standalone':True}


def software_hz(text):
    matches = re.findall(r'mActiveSfDisplayMode=[^\n]*peakRefreshRate=([0-9.]+)', text)
    check(len(matches)==1, 'Missing/ambiguous active display mode')
    return float(matches[0])


def logger_value(text):
    m = re.fullmatch(r'[^\n]*:\s*([01])', text.strip())
    check(m is not None, 'Unknown logger state')
    return int(m[1])


def setup_timeout(value):
    if value=='null':return 600000
    check(value.isdigit() and int(value)>0,'Unknown original timeout')
    return max(600000,int(value))


def verify_read_interval(log, begin, end, reference):
    section = marker_interval(log,begin,end)
    check('dsi_display_set_mode' not in section and 'Command transfer failed' not in section,
          'Native mode/failure during C1')
    check(native_state(log.split(begin,1)[0])==reference and native_state(log)==reference,
          'Native timing changed around C1')


def verify_brightness_dispatch(log, begin, end, dbv, previous, reference=None):
    section=marker_interval(log,begin,end)
    check('Command transfer failed' not in section,'Native brightness transfer failure')
    check('dsi_display_set_mode' not in section,'Native timing transition during brightness dispatch')
    if reference is not None:
        check(native_state(log.split(begin,1)[0])==reference and native_state(log)==reference,
              'Native timing differs around brightness dispatch')
    packets=re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)',section)
    brightness=[]
    for length,kind,mode,payload in packets:
        data=bytes.fromhex(payload)
        if data[:1]==b'\x51':
            check(int(length)==len(data)==3 and int(kind,16)==0x39 and mode=='hs',
                  'Unexpected brightness packet format')
            brightness.append(int.from_bytes(data[1:],'big'))
    check(all(value==dbv for value in brightness),'Conflicting native brightness dispatch')
    check(bool(brightness) or dbv==previous,'No native dispatch for changed DBV')
    return {'requested_dbv':dbv,'native_logged_values':brightness,
            'same_value_cached_allowed':dbv==previous}


def esd_read_script(tmp):
    body = (f'set -eu; mounted=0; trap \'s=$?; trap - EXIT; if [ "$mounted" = 1 ]; then umount {tmp}/debugfs || s=1; fi; exit "$s"\' EXIT; '
            'mount -o rprivate none /; '
            f'mount -t debugfs -o ro,nosuid,nodev,noexec debugfs {tmp}/debugfs; mounted=1; '
            f"tr -d '\\000' < {tmp}/debugfs/qcom,mdss_dsi_mot_{c1.PANEL}/esd_check_mode")
    return 'timeout -k 3 15 unshare -m /system/bin/sh -c '+q(body)


def watchdog_command(tmp, token, boot):
    check(re.fullmatch(r'[0-9a-f-]{36}',boot), 'Invalid boot identity')
    check(re.fullmatch(r'[A-Za-z0-9_.-]{8,128}',token), 'Invalid owner token')
    body = (f'sleep 600; if test -d {tmp}/armed && '
            f'test "$(cat {c1.LOCK}/owner)" = {q(token)} && '
            f'test "$(cat /proc/sys/kernel/random/boot_id)" = {q(boot)}; '
            'then /system/bin/reboot; fi')
    return (f'set -eu; umask 077; mkdir {tmp}/armed; '
            f'nohup /system/bin/sh -c {q(body)} >{tmp}/watchdog.log 2>&1 </dev/null & '
            f'pid=$!; printf "%s\\n" "$pid" >{tmp}/watchdog.pid; kill -0 "$pid"')


class Sweep:
    def __init__(self, adb, target, experiment_id, out, private, *, sleep=time.sleep, monotonic=time.monotonic):
        self.g,self.target = adb,target
        self.plan = plan(experiment_id)
        self.out,self.private = Path(out),Path(private)
        self.sleep,self.monotonic = sleep,monotonic
        self.token = experiment_id+'_'+uuid.uuid4().hex[:12]
        self.ops = lock_commands(self.token)
        self.tmp = '/data/local/tmp/'+experiment_id
        self.marker = self.plan['marker']
        self.serial = None
        self.before = None
        self.reference = None
        self.locked = self.temp = self.armed = self.changed = False
        self.inflight = self.pending_read = self.recovery_failed = False
        self.nonces = []
        self.event = 0
        self.report = {**self.plan,'started_at_utc':now(),'status':'active','captures':[],
                       'events':[],'physical_operation_attempted':False}

    def save(self):
        self.out.joinpath('run.json').write_text(json.dumps(self.report,indent=2)+'\n')

    def shell(self, command, *, root=False, label='shell', timeout=25, mutation=False):
        check(not self.recovery_failed, 'Recovery unverified: no further device commands')
        self.event += 1
        stem=f'{self.event:04d}-{label}'
        remote='su -c '+q(command) if root else command
        if mutation: self.inflight=True
        event={'label':label,'at_utc':now(),'raw_record':stem,'mutation':mutation}
        self.report['events'].append(event); self.save()
        try:
            rc,out,err=self.g.shell(self.target,remote,timeout)
            for name,data in [('stdout',out),('stderr',err)]:
                path=self.private/(stem+'.'+name)
                with path.open('xb') as f: f.write(data)
                path.chmod(0o600)
            event['return_code']=rc
            check(rc==0, 'Device command failed; inspect private evidence')
            if mutation: self.inflight=False
            return out.decode(errors='replace').strip()
        except BaseException as e:
            event['error_type']=type(e).__name__
            raise
        finally: self.save()

    def identity(self):
        expected=['XT2611-1','W3WWS36.65-64-4-1','_b',
                  '6.12.58-android16-6-g09eda8c8505a-dirty-ab15950084-4k','Enforcing','avr']
        value=self.shell('getprop ro.boot.hardware.sku; getprop ro.build.display.id; getprop ro.boot.slot_suffix; uname -r; getenforce; getprop ro.product.device',label='identity')
        check(value.splitlines()==expected,'Target identity changed')
        check(self.shell('id -u',root=True,label='root')=='0','Root required')
        check(self.shell('cat '+CON+'panelName',root=True,label='panel')==c1.PANEL,'Panel changed')
        check(self.shell('sha256sum /vendor/lib/modules/msm_drm.ko',root=True,label='module').split()[0]==MODULE_SHA,'Module changed')

    def mark(self,suffix):
        marker=self.marker+'_'+suffix
        check(re.fullmatch(r'[A-Za-z0-9_]+',marker),'Bad marker')
        self.shell("printf '<6>"+marker+"\\n' > /dev/kmsg",root=True,label='marker')
        return marker

    def state(self,dbv):
        value=self.shell('cat '+BL+'brightness; cat '+BL+'bl_power; cat '+CON+'panelDC; getenforce',root=True,label='state')
        check(value.splitlines()==[str(dbv),'0','0','Enforcing'],'Display state changed')
        check(abs(software_hz(self.shell('dumpsys display',label='display'))-120)<.03,'Software refresh changed')
        check(self.shell('cat /proc/sys/kernel/random/boot_id',label='boot')==self.before['boot_id'],'Unexpected reboot')
        self.shell(self.ops['verify'],root=True,label='owner')

    def wait_value(self,command,expected,seconds=8):
        deadline=self.monotonic()+seconds
        while True:
            if self.shell(command,root=True,label='poll')==expected:return
            check(self.monotonic()<deadline,'State did not settle; no mutation retry')
            self.sleep(.2)

    def quiet(self,label,dbv,initial=False):
        deadline=self.monotonic()+15
        for attempt in range(8):
            self.state(dbv)
            begin=self.mark('QUIET_BEGIN_'+label+'_'+str(attempt))
            self.sleep(2)
            end=self.mark('QUIET_END_'+label+'_'+str(attempt))
            log=self.shell('dmesg',root=True,label='quiet-kernel')
            try: current=qualify_quiet(log,begin,end,self.reference)
            except ValueError:
                if not initial or self.monotonic()>=deadline:raise
                continue
            self.reference=current
            self.state(dbv)
            return {'begin_marker':begin,'end_marker':end,'native_state':current,
                    'quiet_seconds':2,'race_limit':'not an atomic compositor lock'}
        raise ValueError('Initial stock did not become quiet')

    def anchor(self,dbv):
        anchors=[]
        for hz in (90,120):
            begin=self.mark('ANCHOR_BEGIN_'+str(hz))
            self.pending_read=True  # Native settings transport must be qualified too.
            self.shell(stock_anchor_settings(hz),label='stock-anchor',mutation=True)
            deadline=self.monotonic()+15
            while True:
                display=self.shell('dumpsys display',label='anchor-display')
                log=self.shell('dmesg',root=True,label='anchor-kernel')
                try:
                    check(abs(software_hz(display)-hz)<.03,'Software anchor not ready')
                    validate_stock_anchor(log,begin,hz)
                    break
                except ValueError:
                    check(self.monotonic()<deadline,'Native anchor absent; no settings retry')
                    self.sleep(.2)
            end=self.mark('ANCHOR_END_'+str(hz))
            anchors.append(validate_stock_anchor(self.shell('dmesg',root=True,label='anchor-final'),begin,hz,end))
            self.pending_read=False
        self.report['fresh_native_anchor']=anchors
        # HOME/Settings may reinstate framework brightness. Re-establish the
        # captured raw DBV before choosing the initial quiet reference.
        self.report['setup_brightness']=self.apply_native_dbv('SETUP',dbv)
        self.state(dbv)
        self.report['initial_quiet']=self.quiet('INITIAL',dbv,initial=True)
        self.save()

    def apply_native_dbv(self,label,dbv):
        # One native brightness request, never a retry to force a failed read.
        previous=int(self.shell('cat '+BL+'brightness',root=True,label='previous-dbv'))
        bbegin=self.mark('BRIGHTNESS_BEGIN_'+label)
        self.pending_read=True  # Also latch native-brightness transport uncertainty.
        self.shell(f"printf '%s\\n' {dbv} > {BL}brightness",root=True,label='native-brightness',mutation=True)
        self.wait_value('cat '+BL+'brightness',str(dbv))
        bend=self.mark('BRIGHTNESS_END_'+label)
        dispatch=verify_brightness_dispatch(self.shell('dmesg',root=True,label='brightness-kernel'),bbegin,bend,dbv,previous,self.reference)
        self.pending_read=False
        return dispatch

    def observe(self,index,dbv):
        label=f'P{index}_{dbv}'
        dispatch=self.apply_native_dbv(label,dbv)
        quiet=self.quiet(label,dbv)
        nonce=uuid.uuid4().hex[:12]; self.nonces.append(nonce)
        record={'index':index,'native_dbv':dbv,'nonce':nonce,'started_at_utc':now(),
                'status':'reserved','quiet':quiet,'native_dispatch':dispatch,'pwm_hz':None}
        path=self.out/(label+'.json')
        with path.open('x') as f:json.dump(record,f,indent=2)
        self.pending_read=True
        begin=self.mark('READ_BEGIN_'+label)
        try:
            raw=self.shell(guarded_reader(nonce,dbv,self.token),root=True,label=label+'-capture',timeout=40)
            data=validate_adapter_capture(raw+'\n',nonce,dbv)
            end=self.mark('READ_END_'+label)
            verify_read_interval(self.shell('dmesg',root=True,label=label+'-kernel'),begin,end,self.reference)
            self.state(dbv)
            check(self.shell(esd_read_script(self.tmp),root=True,label='esd-after')=='reg_read','ESD restoration absent')
            record.update(data,status='qualified',read_markers={'begin':begin,'end':end})
            self.pending_read=False
            self.report['captures'].append(record)
        except BaseException as e:
            record.update(status='failed_or_uncertain; no retry',error_type=type(e).__name__)
            raise
        finally:
            record['finished_at_utc']=now()
            path.write_text(json.dumps(record,indent=2)+'\n');self.save()

    def recover(self):
        """Only reboot transport + read-only identity checks before clearing uncertainty."""
        self.report['recovery_reboot_attempted']=True;self.save()
        try:
            # Exactly one reboot request. A disconnected reply is not success.
            try:
                r=self.g.run(['adb','-t',str(self.target),'reboot'],capture_output=True,timeout=15)
                self.report['reboot_request_accepted']=r.returncode==0
            except Exception as e:self.report['reboot_request_error']=type(e).__name__
            self.g.wait_target(self.serial.decode(),timeout=90)
            deadline=self.monotonic()+90
            while True:
                try:
                    boot=self.shell('cat /proc/sys/kernel/random/boot_id',label='recovery-boot')
                    complete=self.shell('getprop sys.boot_completed',label='recovery-complete')
                    if boot!=self.before['boot_id'] and complete=='1':break
                except (OSError,RuntimeError,ValueError):
                    pass  # Read-only polling, never repeat reboot or the uncertain query.
                check(self.monotonic()<deadline,'New boot not verified')
                self.sleep(1)
            self.identity()
            self.shell(self.ops['verify'],root=True,label='recovery-owner')
            check(self.shell('cat '+CON+'panelDC',root=True,label='recovery-dc')=='0','Stock DC not restored')
            check(self.shell(esd_read_script(self.tmp),root=True,label='recovery-esd')=='reg_read','Reboot ESD not stock')
            self.before['boot_id']=boot
            self.pending_read=self.inflight=False
            self.report['recovery_reboot_verified']=True
            self.report['watchdog_state']='inactive_after_verified_reboot'
        except BaseException as e:
            self.recovery_failed=True
            self.report['recovery_error_type']=type(e).__name__
            raise
        finally:self.save()

    def restore(self):
        check(not self.pending_read and not self.inflight and not self.recovery_failed,
              'No cleanup writes into uncertain display state')
        if self.changed:
            if self.shell('cat '+BL+'bl_power',root=True,label='restore-power')!='0':
                self.shell('input keyevent 224',label='restore-awake',mutation=True)
                self.wait_value('cat '+BL+'bl_power','0')
            rates=refresh_restore_order(self.before['min_refresh_rate'],self.shell('settings get system peak_refresh_rate',label='restore-peak'))
            for key in ('screen_brightness',*rates,'screen_off_timeout','screen_brightness_mode'):
                value=self.before[key]
                command='settings delete system '+key if value=='null' else 'settings put system '+key+' '+q(value)
                self.shell(command,label='restore-setting',mutation=True)
            self.shell(f"printf '%s\\n' {self.before['native_dbv']} > {BL}brightness",root=True,label='restore-dbv',mutation=True)
            self.wait_value('cat '+BL+'brightness',str(self.before['native_dbv']))
            self.sleep(1)
            self.wait_value('cat '+BL+'brightness',str(self.before['native_dbv']))
            for key in KEYS:
                check(self.shell('settings get system '+key,label='verify-setting')==self.before[key],'Settings not restored')
            self.state(self.before['native_dbv'])
            self.shell(f"printf '%s\\n' {self.before['logger']} > {CON}mipi_cmd_log_en",root=True,label='restore-logger',mutation=True)
            check(logger_value(self.shell('cat '+CON+'mipi_cmd_log_en',root=True,label='verify-logger'))==self.before['logger'],'Logger not restored')
            check(self.shell(esd_read_script(self.tmp),root=True,label='final-esd')=='reg_read','ESD not restored')
            self.report['original_settings_dbv_logger_restored']=True
        if self.armed:
            # Disarm by exact owned path before terminating the known sleeper.
            self.report['watchdog_state']='disarm_outcome_uncertain'
            self.save()
            cmd=(self.ops['verify']+f'; if test -d {self.tmp}/armed; then rmdir {self.tmp}/armed; fi; '
                 f'test ! -e {self.tmp}/armed; pid=$(cat {self.tmp}/watchdog.pid); '
                 f'if test -r /proc/$pid/cmdline && tr "\\000" " " </proc/$pid/cmdline | grep -Fq {q(self.token)}; '
                 'then kill "$pid"; fi')
            self.shell(cmd,root=True,label='disarm-watchdog')
            self.report['watchdog_disarmed']=True
            self.report['watchdog_state']='disarmed_verified'
        if self.temp:
            # A verified reboot removes probes/mounts but may leave known empty dirs.
            for nonce in self.nonces:
                work='/data/local/tmp/pwm-c1-'+nonce
                self.shell(f'set -e; if test -d {work}; then rmdir {work}/dbg {work}; fi; test ! -e /sys/kernel/tracing/instances/pwm_c1_{nonce}; ! grep -Fq pwm_c1_{nonce}/ /sys/kernel/tracing/kprobe_events',root=True,label='verify-child-cleanup')
            self.shell(f'set -e; rm -f {self.tmp}/watchdog.pid {self.tmp}/watchdog.log; rmdir {self.tmp}/debugfs {self.tmp}',root=True,label='remove-owned-temp')
        if self.locked:
            self.shell(self.ops['release'],root=True,label='release-owner')
            self.report['mutex_released']=True
        self.save()

    def execute(self):
        error=None
        try:
            self.g.preflight();self.serial=self.g.bind(self.target)
            self.report['physical_operation_attempted']=True
            self.identity()
            log=self.shell('dmesg',root=True,label='prior-kernel')
            check(not re.search(re.escape(self.marker)+r'_[A-Z]+(?:_|$)',log),'Marker already used')
            self.shell(self.ops['acquire'],root=True,label='acquire-owner');self.locked=True
            self.before={key:self.shell('settings get system '+key,label='before-setting') for key in KEYS}
            check(self.before['screen_brightness_mode']=='0','Require pre-existing manual brightness')
            self.before['native_dbv']=int(self.shell('cat '+BL+'brightness',root=True,label='before-dbv'))
            check(460<=self.before['native_dbv']<=16180,'Unexpected original native brightness')
            self.before['logger']=logger_value(self.shell('cat '+CON+'mipi_cmd_log_en',root=True,label='before-logger'))
            self.before['boot_id']=self.shell('cat /proc/sys/kernel/random/boot_id',label='before-boot')
            self.state(self.before['native_dbv'])
            self.report['before']={k:v for k,v in self.before.items() if k!='boot_id'}
            self.shell(f'test ! -e {self.tmp}',root=True,label='fresh-temp')
            self.temp=True
            self.shell(f'set -eu; umask 077; mkdir -m 700 {self.tmp}; mkdir -m 700 {self.tmp}/debugfs',root=True,label='create-temp')
            check(self.shell(esd_read_script(self.tmp),root=True,label='initial-esd')=='reg_read','Pre-existing ESD state not stock')
            self.armed=True  # Preserve/disarm evidence even if launch outcome is uncertain.
            self.report['watchdog_state']='arm_outcome_uncertain';self.save()
            self.shell(watchdog_command(self.tmp,self.token,self.before['boot_id']),root=True,label='arm-watchdog')
            self.shell(f'test -d {self.tmp}/armed; kill -0 $(cat {self.tmp}/watchdog.pid)',root=True,label='verify-watchdog')
            self.report['watchdog_state']='armed_verified';self.save()
            self.changed=True
            self.shell("printf '1\\n' > "+CON+'mipi_cmd_log_en',root=True,label='enable-logger',mutation=True)
            self.shell('settings put system screen_off_timeout '+str(setup_timeout(self.before['screen_off_timeout'])),label='extend-timeout',mutation=True)
            # Already-awake WAKEUP did not reset a dimmed timer in earlier runs.
            # This known stock UI path establishes activity without blind taps.
            self.shell('input keyevent 3',label='setup-home',mutation=True)
            self.shell('am start -W --activity-clear-top -n '+q('com.android.settings/.Settings$DisplaySettingsActivity'),label='setup-display-settings',mutation=True)
            window=self.shell('dumpsys window policy',label='setup-awake')
            for required in ('screenState=SCREEN_STATE_ON','interactiveState=INTERACTIVE_STATE_AWAKE','mIsShowing=false'):
                check(required in window,'Stock Settings screen is not awake/unlocked')
            self.anchor(self.before['native_dbv'])
            for index,dbv in enumerate(POINTS):self.observe(index,dbv)
            check(self.report['captures'][0]['data']==self.report['captures'][-1]['data'],
                  'Stock828 return did not reproduce the initial C1 value')
            self.report['stock828_reference_reproduced']=True
            self.report['status']='completed'
        except BaseException as e:
            error=e;self.report.update(status='failed',error_type=type(e).__name__)
            if self.pending_read or self.inflight:
                try:self.recover()
                except BaseException:pass
        finally:
            if not self.recovery_failed:
                try:self.restore()
                except BaseException as e:
                    self.report['cleanup_error_type']=type(e).__name__
                    self.report['status']='failed_cleanup; preserve owned lock; inspect watchdog_state'
                    if error is None:error=e
            else:self.report['status']='recovery_unverified; preserve owned lock; watchdog outcome uncertain'
            self.report['finished_at_utc']=now();self.save()
        if error is not None:raise RuntimeError('Sweep incomplete; inspect run.json/private evidence; do not retry') from error
        return self.report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('target',type=int)
    p.add_argument('--experiment-id',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--offline-check',action='store_true')
    a=p.parse_args();check(a.target>0,'Positive target transport required')
    scope=plan(a.experiment_id)
    private=Path.home()/'.cache/legion-y70-stock-c1'/a.experiment_id
    check(not a.output.exists() and not private.exists(),'Fresh output/private identity required')
    guarded_reader('aabbccddeeff',828,a.experiment_id+'_offline')
    if a.offline_check:
        print(json.dumps({**scope,'offline_only':True},indent=2));return
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.mkdir()
    private.parent.mkdir(parents=True,exist_ok=True,mode=0o700);private.mkdir(mode=0o700)
    os.chmod(private,0o700)
    from guarded_adb_socket import GuardedADB
    run=Sweep(GuardedADB(),a.target,a.experiment_id,a.output,private)
    owner=private/'lock-owner.txt'
    with owner.open('x') as f:f.write(run.token+'\n')
    owner.chmod(0o600)
    run.save()
    run.execute()
    print(json.dumps({'status':run.report['status'],'captures':len(run.report['captures']),
                      'output':str(a.output/'run.json'),'pwm_hz':None},indent=2))


if __name__=='__main__':main()
