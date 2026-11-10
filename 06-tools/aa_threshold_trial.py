"""Fixed AA11->10 full-table builders/validators. No transport or live entrypoint.

The only candidate changes raw offset77. Shell generation is not admission.
A failed transaction/selector operation never appends a page or stock return.
"""
import hashlib
from pathlib import Path
import re
import shlex

import dsi_trial_transaction as tx
from a9_reproduction import lock_commands

STOCK_SHA='b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193'
ON_SHA='4c1fc1807aadb63b54efab3cc7baa2c81f7a0107e81bd85dd35db16190fe7c33'
AA_SHA='65846e9320d4a39fd6a677fe9689d08409e80bac050c7cbb1dc12ca276245902'
HASHES={'stock':STOCK_SHA,'aa10':AA_SHA}
TRACE='/sys/kernel/tracing/instances/pwm_mode'
SELECTORS={'23:A9':[14],'24:9D':[14],'00:52':[14,16]}
SELECTOR_CONTROLS=[0,1,0,0,1,0,0,2,0,0]
SCHEMA='aa-threshold-acquisition-v1'
PROBES={
 'mode_entry':'p:pwm_mode/mode_entry msm_drm:dsi_display_cmd_transfer pending=+0x694($arg2):u32 length=$arg4:u32 flags=+3($arg3):u8',
 'mode_return':'r:pwm_mode/mode_return msm_drm:dsi_display_cmd_transfer rc=$retval:s32',
 'mode_ctrl_return':'r:pwm_mode/mode_ctrl_return msm_drm:dsi_ctrl_cmd_transfer rc=$retval:s32',
}

def require(ok,message):
    if not ok: raise ValueError(message)

def digest(data):return hashlib.sha256(data).hexdigest()

def packets(data):
    rows=[];offset=0;page=None
    while offset<len(data):
        require(len(data)-offset>=7,'Truncated header')
        header=data[offset:offset+7];n=int.from_bytes(header[5:7],'big')
        require(n>0 and offset+7+n<=len(data),'Truncated/empty payload')
        payload=data[offset+7:offset+7+n]
        if payload[:3]==b'\xff\x5a\xa5':
            require(len(payload)==4,'Malformed selector');page=payload[3]
        rows.append((offset,header,page,payload));offset+=7+n
    return rows

def validate_program(data,name):
    require(name in HASHES and type(data) is bytes,'Fixed program only')
    require(len(data)==875 and digest(data)==HASHES[name],'Exact program hash required')
    rows=packets(data)
    require(len(rows)==75 and [r[1][3] for r in rows]==[64]*74+[0],'Packet flags changed')
    require(rows[7][0]==69 and rows[7][2:]==(35,b'\xaa'+bytes([17 if name=='stock' else 16])),'AA identity')
    require(rows[6][2:]==(35,b'\xa9\x0e') and rows[9][2:]==(36,b'\x9d\x0e') and rows[10][2:]==(36,b'\x9e\x11'),'Other boundary changed')
    for start,end in tx.RANGES:require(bool(packets(data[start:end])),'Chunk boundary')
    return rows

def programs(root):
    panel=Path(root)/'artifacts/device_tree/selected_boe_v4'
    stock=(panel/'qcom,mdss-dsi-dc-off-command').read_bytes()
    require(digest((panel/'qcom,mdss-dsi-dc-on-command').read_bytes())==ON_SHA,'ON provenance')
    require((panel/'qcom,mdss-dsi-dc-off-command-state').read_bytes()==b'dsi_hs_mode\0','HS state')
    validate_program(stock,'stock');candidate=bytearray(stock);candidate[77]=16
    candidate=bytes(candidate);validate_program(candidate,'aa10')
    require([i for i,(a,b) in enumerate(zip(stock,candidate)) if a!=b]==[77],'One byte only')
    return {'stock':stock,'aa10':candidate}

def chunk_files(data,name):
    validate_program(data,name)
    return {f'{name}_{i}.txt':' '.join(f'0x{x:02x}' for x in data[a:b]).encode('ascii') for i,(a,b) in enumerate(tx.RANGES)}

def _path(tmp):
    require(type(tmp) is str and re.fullmatch(r'/data/local/tmp/[A-Za-z0-9_-]{8,100}',tmp),'Exact single work directory')

def file_guards(tmp,data,name):
    _path(tmp)
    lines=[]
    for path in (tmp,tmp+'/chunks',tmp+'/debugfs'):
        lines.extend((f'test ! -L {path}',f'test -d {path}',f'test "$(stat -c %u {path})" = 0',f'test "$(stat -c %a {path})" = 700'))
    for filename,contents in chunk_files(data,name).items():
        path=tmp+'/chunks/'+filename
        lines.extend((f'test ! -L {path}',f'test -f {path}',f'test "$(stat -c %u {path})" = 0',f'test "$(stat -c %a {path})" = 600',f'test "$(wc -c < {path})" -eq {len(contents)}',f'test "$(sha256sum {path} | cut -d " " -f 1)" = {digest(contents)}'))
    return '\n'.join(lines)

def scratch_guards(tmp,names):
    _path(tmp)
    allowed={'transaction_trace','transaction-previous','transaction-events','transaction-prefix','selector-trace','selector-previous','selector-events','selector-prefix'}
    require(type(names) is tuple and set(names)<=allowed and len(set(names))==len(names),'Fixed scratch names only')
    lines=['umask 077']
    for path in (tmp,tmp+'/debugfs'):
        lines.extend((f'test ! -L {path}',f'test -d {path}',f'test "$(stat -c %u {path})" = 0',f'test "$(stat -c %a {path})" = 700'))
    for name in names:
        path=tmp+'/'+name
        lines.extend((f'test ! -L {path}',f'test ! -e {path}',f'(set -C; : > {path})',f'test "$(stat -c %u {path})" = 0',f'test "$(stat -c %a {path})" = 600'))
    return '\n'.join(lines)

# Retain the existing NUL-normalizing debugfs read contract. Check tr's
# status separately so a read error cannot be hidden
# by a successful comparison. The setter itself requires one trailing LF.
ESD_MODE_PATH = 'qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode'


def esd_mode_guard(mode):
    require(mode in ('reg_read', 'esd_sw_sim_success'), 'Fixed ESD modes only')
    return "esd_mode=$(tr -d '\\000' < \"$E\")\n" + f'test "$esd_mode" = {mode}'


def writer_esd_script(tmp, token, *, restore=False):
    """Fixed mode transition only. Failure never restores ESD in an exit trap.

    Mode 5 prevents future hardware checks, but does not cancel an old check.
    The caller must observe quiet and keep every native/wire transaction gate.
    """
    _path(tmp)
    require(type(restore) is bool, 'Fixed ESD transition only')
    before, after = ('esd_sw_sim_success', 'reg_read') if restore else ('reg_read', 'esd_sw_sim_success')
    marker = 'WRITER_ESD_RESTORED reg_read' if restore else 'WRITER_ESD_ISOLATED esd_sw_sim_success'
    body = f'''set -eu
{lock_commands(token)['verify']}
{scratch_guards(tmp, ())}
mounted=0
trap 'status=$?; trap - EXIT; if [ "$mounted" = 1 ]; then umount {tmp}/debugfs || status=1; fi; exit "$status"' EXIT
trap 'exit 30' HUP INT TERM
mount -o rprivate none /
mount -t debugfs -o nosuid,nodev,noexec debugfs {tmp}/debugfs
mounted=1
E={tmp}/debugfs/{ESD_MODE_PATH}
{esd_mode_guard(before)}
printf '%s\\n' {after} > "$E"
{esd_mode_guard(after)}
printf '%s\\n' '{marker}'
'''
    return 'timeout -k 3 15 unshare -m /system/bin/sh -c ' + shlex.quote(body)


def writer_script(tmp,token,data,name,entry_count):
    """Reuse shared five-block transaction; this wrapper pins complete bytes."""
    _path(tmp);validate_program(data,name)
    command=tx.transaction_script(tmp,TRACE,name,entry_count)
    parts=shlex.split(command);body=parts[-1]
    require(body.startswith('set -eu\n'),'Transaction prologue changed')
    body=body.replace('set -eu\n','set -eu\n'+lock_commands(token)['verify']+'\n'+file_guards(tmp,data,name)+'\n'+scratch_guards(tmp,('transaction_trace','transaction-previous','transaction-events','transaction-prefix'))+'\n',1)
    # Recheck mode 5 in the mounted writer immediately before its first trace
    # snapshot. Restoration is a separate success-only host step, never here.
    ready = f'E={tmp}/debugfs/{ESD_MODE_PATH}\n' + esd_mode_guard('esd_sw_sim_success')
    ready += "\nprintf '%s\\n' 'WRITER_ESD_ISOLATED esd_sw_sim_success'\n"
    snapshot=f'cat {TRACE}/trace > "$S"'
    body = body.replace(snapshot, ready + snapshot, 1)
    require(body.count(snapshot)==6,'Changed transaction snapshot count')
    initial=snapshot+f'''\nif grep -E 'mode_(entry|return|ctrl_return):' "$S" > {tmp}/transaction-previous; then :; else grep_rc=$?; test "$grep_rc" = 1; test ! -s {tmp}/transaction-previous; fi'''
    subsequent=snapshot+f'''\ngrep -E 'mode_(entry|return|ctrl_return):' "$S" > {tmp}/transaction-events
head -n "$(wc -l < {tmp}/transaction-previous)" {tmp}/transaction-events > {tmp}/transaction-prefix
cmp {tmp}/transaction-prefix {tmp}/transaction-previous
cp {tmp}/transaction-events {tmp}/transaction-previous'''
    head,*tail=body.split(snapshot)
    body=head+initial+subsequent.join(tail)
    body+='rm '+tmp+'/transaction_trace '+tmp+'/transaction-previous '+tmp+'/transaction-events '+tmp+'/transaction-prefix\n'
    return ' '.join(shlex.quote(p) for p in parts[:-1])+' '+shlex.quote(body)

def validate_wire(log,begin,end,data,name,reference):
    validate_program(data,name)
    require(tx.native_state(log)==reference and reference['native_actual_hz']==120 and reference['native_group']==3,'Native120 required')
    section=tx.marker_interval(log,begin,end)
    require(not any(s in section for s in ('dsi_display_set_mode','Command transfer failed','LOST')),'Native change/failure')
    rows=re.findall(r'dsi-ctrl-1: dsi_ctrl_cmd_transfer len=(\d+), type=0x([0-9a-fA-F]+) (hs|lp) cmds= ([0-9A-Fa-f ]+)',section)
    actual=[(int(n),int(k,16),mode,bytes.fromhex(payload)) for n,k,mode,payload in rows]
    expected=[(len(p),h[0],'hs',p) for _,h,_,p in packets(data)]
    require(section.count('dsi_ctrl_cmd_transfer len=')==75 and actual==expected,'Exact full-table wire required')
    return {'native_packets_matched':75,'program_sha256':HASHES[name]}

def trace_delta(before,after,entry_count,entries,controls):
    old=tx.check_snapshot(before,entry_count);new=tx.check_snapshot(after,entry_count+len(entries))
    require(tx._events(after)[:len(tx._events(before))]==tx._events(before),'Trace prefix changed')
    found=[tuple(map(int,m)) for m in re.findall(r'\bmode_entry:.*?pending=(\d+) length=(\d+) flags=(\d+)',after)]
    require(found[entry_count:]==entries and new==old+controls,'Unexpected callback/control delta')
    return {'page_callbacks_verified':len(entries),'controller_returns':controls,'entry_count_after':entry_count+len(entries)}

def validate_selectors(raw,before,after,entry_count):
    require(raw.count('ESD_ISOLATED esd_sw_sim_success')==1 and raw.count('ESD_HELD esd_sw_sim_success')==1,'ESD lifecycle')
    lines=[line for line in raw.splitlines() if line]
    require(len(lines)==5 and lines[0]=='ESD_ISOLATED esd_sw_sim_success' and lines[-1]=='ESD_HELD esd_sw_sim_success','Unexpected selector framing')
    require([line.split(' ',2)[:2] for line in lines[1:4]]==[['R','23:A9'],['R','24:9D'],['R','00:52']],'Selector read order')
    values={}
    for line in lines:
        if line.startswith('R '):
            # Native debugfs appends one ASCII space after the final byte.
            m=re.fullmatch(r'R ([0-9A-F]{2}:[0-9A-F]{2}) ((?:0x)?[0-9a-fA-F]{2}(?: (?:0x)?[0-9a-fA-F]{2})*) ?',line)
            require(m is not None and m[1] not in values,'Malformed/duplicate selector')
            values[m[1]]=[int(v,16) for v in m[2].split()]
    require(values==SELECTORS,'Selector/DBV differs from exact3600 stock context')
    return {'values':values,**trace_delta(before,after,entry_count,[(0,11,0)]*7,SELECTOR_CONTROLS)}

def selector_script(tmp,token,entry_count):
    """Fixed three reads. Every operation's native returns gate the next one.

    Only unmount is attempted on error. In particular no EXIT page0/ESD write.
    A caller must use recovery after failure, not call this child again.
    """
    _path(tmp);require(type(entry_count) is int and entry_count>=0,'Invalid entry count')
    awk=r'''/LOST/ {bad=1}
/rc=-[0-9]/ {bad=1}
/mode_entry:/ {e++;for(i=1;i<=NF;i++){if($i~/^pending=/){split($i,a,"=");p=a[2]} if($i~/^length=/){split($i,a,"=");l=a[2]} if($i~/^flags=/){split($i,a,"=");f=a[2]}}}
/mode_return:/ {r++;if($NF!="rc=0")bad=1}
/mode_ctrl_return:/ {c++;if(oldc>=0 && c>oldc && $NF!="rc="want_rc)bad=1}
END {if(bad || e!=want || r!=want || (page && (p!=0 || l!=11 || f!=0)) || (oldc>=0 && c!=oldc+1))exit 51;print c}'''
    body=f'''set -eu
{lock_commands(token)['verify']}
{scratch_guards(tmp,('selector-trace','selector-previous','selector-events','selector-prefix'))}
mount -o rprivate none /
mount -t debugfs -o nosuid,nodev,noexec debugfs {tmp}/debugfs
trap 'umount {tmp}/debugfs' EXIT
trap 'exit 30' HUP INT TERM
C={tmp}/debugfs/dri/9800000.qcom,mdss_mdp/DSI-1
E={tmp}/debugfs/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode
S={tmp}/selector-trace
V={tmp}/selector-previous
N={tmp}/selector-events
P0='0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0'
cat {TRACE}/trace > "$S"
oldc=$(awk -v want={entry_count} -v oldc=-1 {shlex.quote(awk)} "$S")
if grep -E 'mode_(entry|return|ctrl_return):' "$S" > "$V"; then :; else grep_rc=$?; test "$grep_rc" = 1; test ! -s "$V"; fi
[ "$(tr -d '\\000' < "$E")" = reg_read ]
printf '%s\\n' esd_sw_sim_success > "$E"
[ "$(tr -d '\\000' < "$E")" = esd_sw_sim_success ]
printf 'ESD_ISOLATED esd_sw_sim_success\\n'
'''
    count=entry_count
    operations=[]
    for page,reg,length in ((35,169,1),(36,157,1),(0,82,2)):
        operations.extend(((f"printf '%s' '0x39 0 0 0 0 0 4 0xFF 0x5A 0xA5 0x{page:02X}' > \"$C/tx_cmd\"",True,0,None),
            (f"printf '%s' '{length} 0x06 1 0 1 0 0 1 0x{reg:02X}' > \"$C/rx_cmd\"",False,length,f"printf 'R {page:02X}:{reg:02X} '; cat \"$C/rx_cmd\"; printf '\\n'"),
            ('printf %s "$P0" > "$C/tx_cmd"',True,0,None)))
    operations.append(('printf %s "$P0" > "$C/tx_cmd"',True,0,None))
    for command,page,rc,read in operations:
        count+=int(page)
        body+=command+'\n'+f'''cat {TRACE}/trace > "$S"
grep -E 'mode_(entry|return|ctrl_return):' "$S" > "$N"
head -n "$(wc -l < "$V")" "$N" > {tmp}/selector-prefix
cmp {tmp}/selector-prefix "$V"
oldc=$(awk -v want={count} -v page={int(page)} -v oldc="$oldc" -v want_rc={rc} {shlex.quote(awk)} "$S")
cp "$N" "$V"
'''
        if read:body+=read+'\n'
    body+=esd_mode_guard('esd_sw_sim_success')+"\nprintf 'ESD_HELD esd_sw_sim_success\\n'\n"
    body+='rm '+tmp+'/selector-trace '+tmp+'/selector-previous '+tmp+'/selector-events '+tmp+'/selector-prefix\n'
    return 'timeout -k 3 20 unshare -m /system/bin/sh -c '+shlex.quote(body)

# Source-bound bytes from selected cmd_v4 DT OFF property; verified by STOCK_SHA.
STOCK_HEX=(
    '39000040000004ff5aa50839000040000002980239000040000004ff5aa54f39000040000002811039000040000002887839'
    '000040000004ff5aa52339000040000002a90e39000040000002aa1139000040000004ff5aa524390000400000029d0e3900'
    '00400000029e1139000040000004ff5aa52339000040000002805039000040000002a6fc39000040000002a7003900004000'
    '0004ff5aa553390000400000039500a03900004000001fa210101010481010104b4b10101010481010104b4b101010104810'
    '10104b4b39000040000004ff5aa50039000040000002000039000040000002000039000040000004ff5aa553390000400000'
    '02f00139000040000004ff5aa50039000040000002000039000040000004ff5aa56339000040000011f11010101010000000'
    '000000000000000039000040000011f20000000000000000000000000000000039000040000011f300000000002020202020'
    '00000000000039000040000011f40000000000f0f0f0f0f000000000000039000040000004ff5aa55339000040000002f000'
    '39000040000004ff5aa50039000040000002000039000040000002000039000040000004ff5aa5083900004000000298a639'
    '000040000004ff5aa50039000040000002000039000040000004ff5aa54f390000400000028b7839000040000004ff5aa551'
    '39000040000007a14444797b222239000040000007a27e7e8585222239000040000004ff5aa5523900004000000781464748'
    '4b000039000040000007824e4e5050000039000040000004ff5aa50039000040000004ff5aa55a39000040000004860a1e04'
    '390000400000048a122e0f390000400000048f273e2339000040000004900a09013900004000000491090600390000400000'
    '0492070500390000400000049304020039000040000004940000003900004000000495262416390000400000049b00000039'
    '0000400000049c343e3c39000040000004ae102d0739000040000004b31c212239000040000004b9241c2039000040000004'
    'bf09000039000040000004c03a393e39000040000004d71a201d39000040000004dd2a273339000040000004e432303d3900'
    '0040000004ff5aa55b39000040000004dd393a4239000040000004ff5aa55c39000040000004c808040639000040000004c9'
    '08040639000040000004ca00000039000000000004ff5aa500'
)

def fixed_programs():
    stock=bytes.fromhex(STOCK_HEX);validate_program(stock,"stock")
    candidate=stock[:77]+b"\x10"+stock[78:];validate_program(candidate,"aa10")
    return {"stock":stock,"aa10":candidate}
