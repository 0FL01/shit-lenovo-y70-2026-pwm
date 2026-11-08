#!/usr/bin/env python3
"""OFFLINE preparation only. No ADB import, live CLI, or transport implementation.

Fixed P85 long3 reader and three-callback script builders plus a fail-closed
rehearsal state machine. Scripts require a separately reviewed live coordinator.
Unknown register semantics: damage can precede watchdog; reboot is no guarantee.
"""
import re
import shlex
from dataclasses import dataclass
import stock_c1_sweep as stock
from p85_single_bit_plan import proposal

check = stock.check
DBV = 3600
HOLD_SECONDS = 2
CANDIDATE_BUDGET_SECONDS = 45
CANDIDATE_WATCHDOG_SECONDS = 60
LIVE_ENABLED = False
WRITER_GATE_FILES = ('gate-trace','gate-profile','gate-kernel','gate-events','gate-prefix','gate-previous')


def _freeze_before_esd(body):
    """Snapshot/disable/remove only own probes before native ESD can resume.

    Exact profile counts otherwise race a native ESD receive after trace-off.
    Any freeze/removal failure keeps ESD isolated and requires recovery.
    """
    needle=' if [ "$s" = 0 ] && [ "$mounted" = 1 ] && [ "$touched" = 1 ]; then\n   printf \'%s\\n\' reg_read'
    check(body.count(needle)==1,'Changed ESD cleanup block')
    start=body.index(needle);end=body.index('\n fi\n',start)+len('\n fi\n')
    block=body[start:end];body=body[:start]+body[end:]
    anchor=' if [ "$traced" = 1 ]; then rmdir "$T" || s=39; fi\n'
    check(body.count(anchor)==1,'Changed own-probe cleanup order')
    return body.replace(anchor,block+anchor)


def bounded_c1_reader(nonce, token):
    """Keep shared qualified reader unchanged; bound every text argv locally.

    Reader trace/global profile can grow through unexpected activity. Reject
    >16K shell characters before external printf (at most64KiB UTF-8), preserving the original uncertainty cleanup.
    This is not a log truncation or an activity whitelist.
    """
    parts=shlex.split(stock.guarded_reader(nonce,DBV,token));body=parts[8]
    for variable in ('snapshot','events','profiles'):
        pattern=r'(^ '+variable+r'=.*? \|\| return 43$)'
        body,count=re.subn(pattern,lambda m:m[1]+'\n [ "${#'+variable+'}" -le 16384 ] || return 43',body,flags=re.M)
        check(count==1,'Changed inherited text gate')
    return ' '.join(shlex.quote(x) for x in parts[:8])+' '+shlex.quote(body)


def long3_reader(nonce, token):
    """Fixed read-only85 query, with qualified C1 failure cleanup, NOT short1."""
    parts = shlex.split(bounded_c1_reader(nonce, token))
    body = parts[8]
    for old, new in (("'3 0x06 1 0 1 0 0 1 0xC1'", "'3 0x06 1 0 1 0 0 1 0x85'"),
                     ("printf 'C1 '", "printf 'P85_LONG3 '")):
        check(body.count(old) == 1, 'Changed fixed reader template')
        body = body.replace(old, new)
    # Keep C1 probe/work names deliberately: identical lifetime and cleanup path.
    body = _freeze_before_esd(body)
    return ' '.join(shlex.quote(x) for x in parts[:8]) + ' ' + shlex.quote(body)


def validate_long3(raw, nonce):
    check(re.fullmatch(r'[0-9a-f]{12}', nonce), 'Bad nonce')
    check(len(re.findall(r'^P85_LONG3 ', raw, re.M)) == 1 and
          not re.search(r'^C1 ', raw, re.M), 'Wrong/duplicate observation label')
    for begin, end in (('TRACE_BEGIN', 'TRACE_END'), ('PROFILE_BEGIN', 'PROFILE_END')):
        check(raw.count(begin+'\n') == raw.count(end+'\n') == 1,
              'Ambiguous evidence boundaries')
    check(len(re.findall(r'^STATE ', raw, re.M)) == 1, 'Ambiguous state')
    adapted = re.sub(r'^P85_LONG3 ', 'C1 ', raw, flags=re.M)
    result = stock.validate_adapter_capture(adapted, nonce, DBV)
    trace = raw.split('TRACE_BEGIN\n')[1].split('TRACE_END\n')[0]
    sequence = re.findall(r'\b(entry|ctrl|tx|hardware|header)_'+nonce+r':', trace)
    check(sequence == ['entry','ctrl','tx','hardware','header','ctrl',
                       'entry','ctrl','tx','entry','ctrl','tx'], 'Wrong event order')
    profile = raw.split('PROFILE_BEGIN\n')[1].split('PROFILE_END\n')[0]
    for name, count in (('entry',3),('ctrl',4),('tx',3),('hardware',1),('header',1)):
        check(re.findall(r'^\s*'+name+'_'+nonce+r'\s+(\d+)\s+(\d+)\s*$', profile, re.M)
              == [(str(count),'0')], 'Nonexact probe accounting')
    return {**result, 'opcode':'85', 'response_type':'DCS_long3', 'returned':3,
            'limit':'Read-plane and writable semantics unknown; CRC payload not captured; no Hz claim.'}


def write_script(nonce, token, stage):
    """Build only sham15/candidate14/return15, exactly three standalone packets.

    Native return AND wire-log gates run on device after every callback. No DSI
    in any trap. Uncertain failure leaves ESD isolated for reboot/watchdog.
    This builder does not provide ownership acquisition or arm a watchdog.
    """
    check(stage in ('sham15','candidate14','return15'), 'Unsupported fixed stage')
    packets = proposal('candidate14' if stage == 'candidate14' else 'restore15')
    parts = shlex.split(stock.guarded_reader(nonce, DBV, token))
    body = parts[8]
    start = body.index("previous_events=''")
    end = body.index('cleanup() {', start)
    gate = r'''previous_count=0
MARK=PWM_P85_WRITE_NONCE
printf '<6>%s_BEGIN\n' "$MARK" > /dev/kmsg
gate() {
 [ "$(cat "$T/tracing_on")" = 1 ] || return 43
 cat "$T/trace" > "$W/gate-trace" || return 43
 [ "$(wc -c < "$W/gate-trace")" -le 262144 ] || return 43
 awk -v nonce="NONCE" 'index($0,"_"nonce":") {print}' "$W/gate-trace" > "$W/gate-events" || return 43
 if [ "$1" = 0 ]; then : > "$W/gate-previous" || return 43; fi
 awk -v n="$previous_count" 'NR<=n' "$W/gate-events" > "$W/gate-prefix" || return 43
 cmp -s "$W/gate-prefix" "$W/gate-previous" || return 43
 cat /sys/kernel/tracing/kprobe_profile > "$W/gate-profile" || return 43
 [ "$(wc -c < "$W/gate-profile")" -le 1048576 ] || return 43
 awk -v stage="$1" -v nonce="NONCE" '
 BEGIN {want["entry_"nonce]=stage;want["ctrl_"nonce]=stage;want["tx_"nonce]=stage;want["header_"nonce]=0;want["hardware_"nonce]=0}
 $1 in want {seen[$1]++; if(NF!=3 || $2!=want[$1] || $3!=0)bad=1}
 END {for(n in want)if(seen[n]!=1)bad=1;exit bad?1:0}' "$W/gate-profile" || return 43
 awk -v stage="$1" -v nonce="NONCE" '
 function field(k,i,a){for(i=1;i<=NF;i++){split($i,a,"=");if(a[1]==k)return a[2]}return "MISSING"}
 function pid(t){t=$1;sub(/^.*-/,"",t);return t}
 /LOST/ {bad=1}
 index($0,"entry_"nonce":"){en++;seq=seq"e";ep=pid();if(ep!~/^[0-9]+$/ || field("pending")!="0" || field("flags")!="0" || field("length")!=(en==2?"9":"11"))bad=1}
 index($0,"ctrl_"nonce":"){cn++;seq=seq"c";if(field("rc")!="0" || pid()!=ep)bad=1}
 index($0,"tx_"nonce":"){tn++;seq=seq"t";if(field("rc")!="0" || pid()!=ep)bad=1}
 index($0,"header_"nonce":") || index($0,"hardware_"nonce":") {bad=1}
 END {expected=(stage==0?"":(stage==1?"ect":(stage==2?"ectect":"ectectect")));if(en!=stage || cn!=stage || tn!=stage || seq!=expected)bad=1;exit bad?1:0}' "$W/gate-trace" || return 43
 dmesg > "$W/gate-kernel" || return 43
 [ "$(wc -c < "$W/gate-kernel")" -le 16777216 ] || return 43
 awk -v mark="$MARK" -v stage="$1" '
 index($0,mark"_BEGIN"){seen++;active=1;next}
 active && (/dsi_display_set_mode/ || /Command transfer failed/ || /LOST/) {bad=1}
 active && /dsi_ctrl_cmd_transfer len=/ {
 n++;line=$0;sub(/^.*dsi-ctrl-1: /,"",line)
 expected=(n==1?"dsi_ctrl_cmd_transfer len=4, type=0x39 hs cmds= ff 5a a5 23":(n==2?"dsi_ctrl_cmd_transfer len=2, type=0x39 hs cmds= 85 VALUE":"dsi_ctrl_cmd_transfer len=4, type=0x39 hs cmds= ff 5a a5 00"))
 sub(/[[:space:]]+$/,"",line);if(tolower(line)!=expected)bad=1}
 END {if(seen!=1 || n!=stage)bad=1;exit bad?1:0}' "$W/gate-kernel" || return 43
 cp "$W/gate-events" "$W/gate-previous" || return 43
 previous_count=$(wc -l < "$W/gate-events") || return 43
 printf 'WRITE_GATE_OK %s\n' "$1"
}
'''.replace('NONCE',nonce).replace('VALUE','14' if stage == 'candidate14' else '15')
    body = body[:start]+gate+body[end:]
    cleanup_start = body.index(' if [ "$s" = 0 ] && [ "$mounted" = 1 ] && [ "$touched" = 1 ]; then')
    cleanup_end = body.index(' if [ "$traced" = 1 ]; then printf 0',cleanup_start)
    body = body[:cleanup_start]+body[cleanup_end:]
    old = ' s=$?; trap - EXIT HUP INT TERM; set +e\n'
    check(body.count(old)==1, 'Changed cleanup prologue')
    body = body.replace(old, old + ' if [ "$s" = 0 ] && [ "$traced" = 1 ]; then gate 3 || s=43; fi\n')
    operation_start = body.index('gate 0\n')
    operation_end = body.index('[ "$(cat /sys/class/backlight/panel0-backlight/brightness)" = 3600 ]',operation_start)
    operations='gate 0\n'
    for index, packet in enumerate(packets,1):
        encoded=' '.join('0x%02x'%b for b in packet)
        operations += "printf '%s' "+shlex.quote(encoded)+' > "$C/tx_cmd"\ngate '+str(index)+'\n'
    body = body[:operation_start]+operations+body[operation_end:]
    # Prevent a failed arm/setup caller from accidentally executing this builder.
    body = body.replace('set -eu\n', 'set -eu\n# Caller must verify independent watchdog and held root owner.\n', 1)
    body = _freeze_before_esd(body)
    cleanup=' if [ "$made_work" = 1 ]; then rmdir "$W/dbg" "$W" || s=41; fi'
    check(body.count(cleanup)==1,'Changed owned-work cleanup')
    remove='rm -f '+' '.join('"$W/'+name+'"' for name in WRITER_GATE_FILES)
    body=body.replace(cleanup,' if [ "$made_work" = 1 ]; then '+remove+' || s=41; fi\n'+cleanup)
    return ' '.join(shlex.quote(x) for x in parts[:8])+' '+shlex.quote(body)


def validate_write_capture(raw, nonce, stage):
    check(stage in ('sham15','candidate14','return15'), 'Bad stage')
    check(re.fullmatch(r'[a-f0-9]{12}',nonce), 'Bad nonce')
    check(re.findall(r'^WRITE_GATE_OK (\d+)$',raw,re.M)==['0','1','2','3','3'] and
          raw.count('CLEANUP_OK')==1 and 'RECOVERY_REQUIRED' not in raw and
          'LOST' not in raw, 'Write not clean')
    for begin,end in (('TRACE_BEGIN','TRACE_END'),('PROFILE_BEGIN','PROFILE_END')):
        check(raw.count(begin+'\n')==raw.count(end+'\n')==1,'Ambiguous writer evidence')
    for state,value in (('INITIAL','reg_read'),('ACTIVE','esd_sw_sim_success'),('RESTORED','reg_read')):
        check(re.findall(r'^ESD_'+state+r' (.+)$',raw,re.M)==[value],'Writer ESD unqualified')
    states=re.findall(r'^STATE (\d+) ([0-9.]+)$',raw,re.M)
    check(len(states)==1 and states[0][0]=='3600' and abs(float(states[0][1])-120)<.03, 'Writer state unqualified')
    trace=raw.split('TRACE_BEGIN\n')[1].split('TRACE_END\n')[0]
    events=[]
    for line in trace.splitlines():
        m=re.search(r'\b(entry|ctrl|tx|hardware|header)_'+nonce+r':',line)
        if not m:continue
        pid=re.search(r'-(\d+)\s+(?:\(.*?\)\s+)?\[',line)
        check(pid is not None,'Bad writer PID')
        fields=dict(re.findall(r'(\w+)=(0x[0-9a-fA-F]+|-?\d+)',line))
        events.append((m[1],int(pid[1]),{k:int(v,0) for k,v in fields.items()}))
    check([x[0] for x in events]==['entry','ctrl','tx']*3,'Writer event sequence changed after final gate')
    for i,length in enumerate((11,9,11)):
        entry,ctrl,tx=events[i*3:i*3+3]
        check(entry[2]=={'pending':0,'length':length,'flags':0} and
              ctrl[2]==tx[2]=={'rc':0} and entry[1]==ctrl[1]==tx[1], 'Writer callback not exact')
    profile=raw.split('PROFILE_BEGIN\n')[1].split('PROFILE_END\n')[0]
    for name,count in (('entry',3),('ctrl',3),('tx',3),('hardware',0),('header',0)):
        check(re.findall(r'^\s*'+name+'_'+nonce+r'\s+(\d+)\s+(\d+)\s*$',profile,re.M)
              ==[(str(count),'0')],'Writer probes changed after final gate')
    return {'callbacks':3,'final_trace_qualified':True,'pwm_hz':None}


def validate_write_wire(log, begin, end, stage, reference):
    s=stock.marker_interval(log,begin,end)
    stock.verify_read_interval(log,begin,end,reference)
    rows=re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9a-fA-F ]+)',s)
    packets=proposal('candidate14' if stage=='candidate14' else 'restore15')
    check(len(rows)==len(re.findall(r'dsi_ctrl_cmd_transfer len=',s))==3,'Extra/missing writer wire record')
    for row,packet in zip(rows,packets):
        length,kind,mode,payload=row
        check(int(length)==len(packet)-7 and int(kind,16)==0x39 and mode=='hs' and
              bytes.fromhex(payload)==packet[7:],'Writer wire not exact')
    return True


@dataclass(frozen=True)
class Observation:
    p85: tuple
    c1: tuple
    native: tuple  # width,height,peak,actual,group,clock
    dbv: int
    camera_session: str
    frame_start: int
    frame_end: int
    elapsed: float
    hold_seconds: float
    optical_acceptable: bool
    qualified: bool

    def validate(self, value, previous=None):
        check(self.qualified is True and self.optical_acceptable is True,
              'Unqualified observation or gross optical abnormality')
        check(self.p85 == (value,0,0), 'P85 read plane does not match expected stage')
        check(len(self.c1)==3 and all(type(x) is int and 0<=x<=255 for x in self.c1), 'Invalid C1')
        check(self.native==(1440,3168,120,120,3,1234000000) and self.dbv==DBV,
              'Native120/DBV3600 changed')
        check(self.frame_end>self.frame_start>=0 and self.camera_session and
              self.hold_seconds==HOLD_SECONDS and 0<self.elapsed<20, 'Bad bounded hold/progress')
        if previous:
            check(self.camera_session==previous.camera_session and self.frame_start>previous.frame_end,
                  'Recording continuity/progress lost')


class Rehearsal:
    """Offline deterministic transition model, NOT a live executor.

    Evidence booleans below are mock contracts, not substitutes for live checks.
    In particular no arbitrary plugin/backend can enable physical execution.
    """
    def __init__(self):
        self.stage='new'; self.uncertain=False; self.candidate_attempts=0
        self.baseline=None; self.last=None; self.candidate_may_be_active=False

    def prepare(self, *, fresh_paths, root_owner, identity, bound_serials,
                anchor90_120, watchdog, camera_metadata, lead_roi_review):
        check(self.stage=='new' and all(x is True for x in (fresh_paths,root_owner,identity,
              bound_serials,anchor90_120,watchdog,camera_metadata,lead_roi_review)), 'Incomplete preflight')
        self.stage='baseline'

    def observe(self, observation):
        check(not self.uncertain and self.stage in ('baseline','sham','candidate','return'), 'Wrong observation state')
        # Any validation error latches failure: no candidate/return may be inferred clean.
        self.uncertain=True
        observation.validate(0x14 if self.stage=='candidate' else 0x15, self.last)
        if self.stage=='baseline': self.baseline=observation
        if self.stage in ('sham','return'):
            check(observation.c1==self.baseline.c1, 'Stock observables did not reproduce')
        self.last=observation; self.uncertain=False
        self.stage={'baseline':'ready_sham','sham':'ready_candidate','candidate':'ready_return','return':'ready_cleanup'}[self.stage]

    def begin_write(self, stage, *, watchdog_remaining, elapsed_since_candidate=0):
        check(not self.uncertain, 'No DSI into uncertainty')
        expected={'ready_sham':'sham15','ready_candidate':'candidate14','ready_return':'return15'}
        check(expected.get(self.stage)==stage, 'No retry, reapply, reorder or arbitrary value')
        if self.candidate_may_be_active and (watchdog_remaining<10 or
                (stage=='return15' and not 0<=elapsed_since_candidate<CANDIDATE_BUDGET_SECONDS)):
            self.abort()
            raise ValueError('Candidate budget/watchdog margin exhausted: reboot only')
        check(watchdog_remaining>=10, 'Insufficient watchdog return margin')
        if stage=='candidate14':
            check(self.candidate_attempts==0 and watchdog_remaining==CANDIDATE_WATCHDOG_SECONDS,
                  'Candidate needs fresh bounded independent watchdog')
            check(2*self.last.elapsed+5<CANDIDATE_BUDGET_SECONDS, 'Baseline latency too slow')
            self.candidate_attempts+=1; self.candidate_may_be_active=True
        if stage=='return15':
            check(0<=elapsed_since_candidate<CANDIDATE_BUDGET_SECONDS, 'Candidate budget exceeded: reboot only')
        self.uncertain=True; self.stage='writing_'+stage
        return proposal('candidate14' if stage=='candidate14' else 'restore15')

    def finish_write(self, *, native_returns, wire, prefix, no_misses, pending_flags, state):
        check(self.uncertain and self.stage.startswith('writing_'), 'No write in flight')
        check(all(x is True for x in (native_returns,wire,prefix,no_misses,pending_flags,state)), 'Uncertain transaction')
        stage=self.stage[len('writing_'):]
        self.stage={'sham15':'sham','candidate14':'candidate','return15':'return'}[stage]
        self.uncertain=False
        # Return write alone does NOT certify readback, optics or recovery.

    def abort(self):
        self.uncertain=True; self.stage='reboot_required'
        return 'same_bound_target_reboot_once_or_independent_watchdog; no further DSI'

    def complete(self, *, stock_optics, camera_stopped, originals_restored, esd_restored,
                 watchdog_disarmed, owner_released):
        check(self.stage=='ready_cleanup' and not self.uncertain and
              all(x is True for x in (stock_optics,camera_stopped,originals_restored,esd_restored,
                                     watchdog_disarmed,owner_released)), 'Recovery incomplete')
        self.candidate_may_be_active=False; self.stage='completed'


if __name__ == '__main__':
    raise SystemExit('OFFLINE ONLY: no live entry point; independent review and coordinator integration required')
