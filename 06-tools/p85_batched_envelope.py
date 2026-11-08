"""Strict offline builders/parser for one-child P85 stock batching envelopes.

No device I/O here. Children are supplied by the unchanged qualified builders.
A compound snapshot is not atomic. Host validation MUST precede any next child.
"""
from dataclasses import dataclass
import hashlib
import re
import shlex

import p85_guarded_trial as p85
import stock_c1_sweep as stock

check=stock.check
q=shlex.quote
MAX_TOTAL=24*1024*1024
ENV_FILES=('stdout','stderr','owner')


@dataclass(frozen=True)
class Part:
    label: str
    command: str
    root: bool=False
    limit: int=1024
    seconds: int=8


@dataclass(frozen=True)
class Envelope:
    nonce: str
    parts: tuple
    seconds: int
    child_command: str|None=None
    owner_digest: str="0"*64

    @property
    def work(self):return '/data/local/tmp/p85-envelope-'+self.nonce


def _validate(plan):
    check(re.fullmatch(r'[0-9a-f]{12}',plan.nonce),'Invalid envelope nonce')
    check(re.fullmatch(r'[0-9a-f]{64}',plan.owner_digest),'Invalid owner binding')
    check(type(plan.parts) is tuple and 1<=len(plan.parts)<=16,'Invalid envelope parts')
    check(len({p.label for p in plan.parts})==len(plan.parts),'Duplicate part label')
    check(type(plan.seconds) is int and 1<=plan.seconds<=45,'Invalid outer bound')
    for part in plan.parts:
        check(re.fullmatch(r'[A-Z][A-Z0-9_]{0,39}',part.label),'Invalid section label')
        check(type(part.root) is bool and 0<=part.limit<=16*1024*1024,'Invalid section cap')
        check(type(part.seconds) is int and 1<=part.seconds<=38,'Invalid section bound')
        check(type(part.command) is str and '\x00' not in part.command and len(part.command)<40000,'Invalid bounded command')
    children=[part for part in plan.parts if part.label=='CHILD']
    check(len(children)==(1 if plan.child_command is not None else 0),'Ambiguous child')
    if children:check(children[0].command==plan.child_command and children[0].root,'Changed child/privilege')


def state_parts(owner, prefix=''):
    return (
        Part(prefix+'FIELDS','cat '+stock.BL+'brightness; cat '+stock.BL+'bl_power; cat '+stock.CON+'panelDC; getenforce',True,1024),
        Part(prefix+'DISPLAY','dumpsys display',False,4*1024*1024),
        Part(prefix+'BOOT','cat /proc/sys/kernel/random/boot_id',False,128),
        Part(prefix+'OWNER',owner,True,0),
    )


def marker_part(label,marker):
    check(re.fullmatch(r'[A-Za-z0-9_]{8,180}',marker),'Invalid marker')
    return Part(label,"printf '<6>"+marker+"\\n' > /dev/kmsg",True,0)


def _owner(owner):return hashlib.sha256(owner.encode()).hexdigest()


def state_envelope(nonce,owner):return Envelope(nonce,state_parts(owner),20,owner_digest=_owner(owner))


def quiet_envelope(nonce,owner,begin,end):
    # Caller validates separate pre-state BEFORE this readonly/marker envelope.
    return Envelope(nonce,(marker_part('BEGIN',begin),Part('WAIT','sleep 2',False,0,4),
        marker_part('END',end),Part('KERNEL','dmesg',True,16*1024*1024),*state_parts(owner)),25,owner_digest=_owner(owner))


def child_envelope(nonce,owner,token,kind,begin,end,tmp):
    check(kind in ('p85','c1','sham15','return15'),'Stock-only child kind; no14')
    if kind=='p85':child=p85.long3_reader(nonce,token)
    elif kind=='c1':child=p85.bounded_c1_reader(nonce,token)
    else:child=p85.write_script(nonce,token,kind)
    return Envelope(nonce,(marker_part('BEGIN',begin),Part('CHILD',child,True,1024*1024,38),
        marker_part('END',end),Part('KERNEL','dmesg',True,16*1024*1024),*state_parts(owner),
        Part('ESD',stock.esd_read_script(tmp),True,128,18)),45,child,_owner(owner))


def hold_end_envelope(nonce,owner,end):
    return Envelope(nonce,(marker_part('END',end),Part('KERNEL','dmesg',True,16*1024*1024),*state_parts(owner)),20,owner_digest=_owner(owner))


def script(plan):
    _validate(plan)
    magic='@P85E:'+plan.nonce+':'
    # Shell UID owns the fresh0700 envelope dir. Root components use su exactly
    # as before; display/boot retain their original shell UID context.
    body=f'''set -eu
umask 077
W={q(plan.work)}
M={q(magic)}
made=0
cleanup() {{
 s=$?; trap - EXIT HUP INT TERM; set +e
 if [ "$made" = 1 ]; then
  rm -f "$W/stdout" "$W/stderr" "$W/owner" || s=71
  rmdir "$W" || s=72
 fi
 exit "$s"
}}
trap cleanup EXIT
trap 'exit 73' HUP INT TERM
[ "$(id -u)" = 2000 ]
[ ! -e "$W" ] && [ ! -L "$W" ]
mkdir -m 700 "$W"; made=1
printf %s {q(plan.nonce+":"+plan.owner_digest)} > "$W/owner"
printf '%sSTART\\n' "$M"
part() {{
 label=$1; cap=$2; bound=$3; command=$4
 if timeout -k 1 "$bound" /system/bin/sh -c "$command" > "$W/stdout" 2> "$W/stderr"; then rc=0; else rc=$?; fi
 out=$(wc -c < "$W/stdout")
 err=$(wc -c < "$W/stderr")
 out=$((out + 0)); err=$((err + 0))
 [ "$out" -le "$cap" ] && [ "$err" -le 16384 ] || {{ printf '%sERROR %s oversize\\n' "$M" "$label"; return 74; }}
 printf '%sSECTION %s %s %s %s\\n' "$M" "$label" "$rc" "$out" "$err"
 cat "$W/stdout"; cat "$W/stderr"
 printf '\\n%sEND %s\\n' "$M" "$label"
 if [ "$rc" != 0 ]; then return "$rc"; fi
 [ "$err" = 0 ] || return 75
}}
'''
    for part in plan.parts:
        # set-e makes every subcommand failure fatal, not just the last cat.
        command=part.command if part.label=='CHILD' else 'set -eu; '+part.command
        if part.root:command='su -c '+q(command)
        body+='part '+q(part.label)+' '+str(part.limit)+' '+str(part.seconds)+' '+q(command)+'\n'
    body+='rm -f "$W/stdout" "$W/stderr" "$W/owner"\nrmdir "$W"\nmade=0\nprintf \'%sDONE\\n\' "$M"\n'
    command='timeout -k 3 '+str(plan.seconds)+' /system/bin/sh -c '+q(body)
    command_sizes(command)
    return command


def parse(raw,plan,*,returncode=0,stderr=b''):
    """Exact length framing. Never truncate, decode-replace, or accept stderr."""
    _validate(plan)
    check(type(raw) is bytes and type(stderr) is bytes,'Raw bytes required')
    check(returncode==0 and not stderr,'Transport/component failure or stderr')
    check(len(raw)<=MAX_TOTAL,'Oversized envelope')
    prefix=('@P85E:'+plan.nonce+':').encode();cursor=0
    def line():
        nonlocal cursor
        end=raw.find(b'\n',cursor)
        check(end>=0 and end-cursor<=160,'Truncated/oversized framing line')
        value=raw[cursor:end];cursor=end+1;return value
    check(line()==prefix+b'START','Missing envelope start')
    result={}
    for part in plan.parts:
        header=line()
        match=re.fullmatch(re.escape(prefix)+b'SECTION '+part.label.encode()+rb' ([0-9]{1,3}) ([0-9]{1,9}) ([0-9]{1,5})',header)
        check(match is not None,'Missing/duplicate/reordered section')
        rc,n,e=map(int,match.groups())
        check(rc==0 and e==0 and n<=part.limit,'Failed/oversized section or stderr')
        check(cursor+n+e<len(raw),'Truncated section payload')
        payload=raw[cursor:cursor+n];cursor+=n+e
        check(prefix not in payload and b'\x00' not in payload,'Embedded delimiter or NUL')
        check(raw[cursor:cursor+1]==b'\n','Missing payload boundary');cursor+=1
        check(line()==prefix+b'END '+part.label.encode(),'Missing/mismatched section end')
        try:result[part.label]=payload.decode('utf-8','strict')
        except UnicodeDecodeError as error:raise ValueError('Invalid UTF-8 evidence') from error
    check(line()==prefix+b'DONE' and cursor==len(raw),'Missing completion or trailing evidence')
    return result


def validate_state(sections,dbv,boot):
    check(sections['FIELDS'].strip().splitlines()==[str(dbv),'0','0','Enforcing'],'Display state changed')
    check(abs(stock.software_hz(sections['DISPLAY'])-120)<.03,'Software refresh changed')
    check(sections['BOOT'].strip()==boot,'Unexpected boot identity')
    check(sections['OWNER']=='','Owner check emitted unexpected data')
    return True


def remnant_cleanup(work,owner_digest):
    check(re.fullmatch(r'/data/local/tmp/p85-envelope-[0-9a-f]{12}',work),'Unknown envelope workdir')
    check(re.fullmatch(r'[0-9a-f]{64}',owner_digest),'Unknown envelope owner')
    nonce=work.rsplit('-',1)[1]
    return (f'set -eu; test "$(id -u)" = 2000; test ! -L {work}; if test -e {work}; then test -d {work}; '
        f'test "$(stat -c %u {work})" = 2000; test "$(stat -c %a {work})" = 700; '
        f'test ! -L {work}/owner; test -f {work}/owner; '
        f'test "$(stat -c %u {work}/owner)" = 2000; test "$(stat -c %a {work}/owner)" = 600; '
        f'test "$(cat {work}/owner)" = {q(nonce+":"+owner_digest)}; '
        f'rm -f {work}/stdout {work}/stderr {work}/owner; rmdir {work}; fi; test ! -e {work}')


def command_sizes(command):
    """Check encoded final service and the dominating outer shell argv before I/O.

    ADB's 65535-byte service cap is stricter than conservative Linux/Android
    4KiB-page MAX_ARG_STRLEN (131072 incl NUL). No log payload enters argv.
    """
    service=len(('shell,v2,raw:'+command).encode('utf-8'))
    check(service<=65535,'Envelope exceeds ADB service-frame limit')
    maximum=len(command.encode('utf-8'))+1
    check(maximum<=131072,'Envelope exceeds conservative Android argv limit')
    return {'service_bytes':service,'shell_argv_bytes_including_nul':maximum,
            'service_limit_bytes':65535,'argv_limit_bytes':131072}


def size_preflight():
    # Largest accepted owner token and marker, not merely today's UUID/ID.
    token='x'*128;marker='X'*180;nonce='f'*12
    owner=stock.lock_commands(token)['verify'];tmp='/data/local/tmp/'+'x'*64
    plans={'state':state_envelope(nonce,owner),
           'quiet':quiet_envelope(nonce,owner,marker,marker),
           'hold_end':hold_end_envelope(nonce,owner,marker)}
    for kind in ('p85','c1','sham15','return15'):
        plans[kind]=child_envelope(nonce,owner,token,kind,marker,marker,tmp)
    return {kind:command_sizes(script(plan)) for kind,plan in plans.items()}
