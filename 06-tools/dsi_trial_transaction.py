"""Offline builders/validators for bounded exact five-block panel transactions."""
import re
import shlex

RANGES = ((0,253),(253,500),(500,754),(754,864),(864,875))


def experiment_marker(experiment_id):
    if not isinstance(experiment_id,str) or not re.fullmatch(r'[a-z][a-z0-9_]{7,63}',experiment_id):
        raise ValueError('Invalid marker experiment ID')
    # IDs are lowercase, while all event suffixes begin with uppercase tokens.
    # Thus an ID that prefixes another cannot alias its complete event marker.
    return 'PWM_A9_REPRODUCTION_' + experiment_id


def ensure_unused_marker(log, experiment_id):
    marker=experiment_marker(experiment_id)
    if re.search(re.escape(marker)+r'_[A-Z]+(?:_|$)',log):
        raise ValueError('Experiment marker already present in retained kernel log')
    return marker


def marker_interval(text, begin, end):
    if text.count(begin)!=1 or text.count(end)!=1 or text.index(begin)>=text.index(end):
        raise ValueError('Missing/ambiguous kernel marker interval')
    return text.split(begin,1)[1].split(end,1)[0]


def native_state(log):
    lines = [line for line in log.splitlines() if 'dsi_display_set_mode' in line and 'fps=' in line]
    if not lines:
        raise ValueError('No retained native mode anchor; software peak120 is insufficient')
    match = re.search(r'hactive=(\d+), vactive=(\d+), fps=(\d+)\(actual=(\d+), group=0x([0-9a-fA-F]+)\), clk_rate=(\d+)', lines[-1])
    if not match:
        raise ValueError('Unrecognized native mode anchor')
    width,height,peak,actual = map(int, match.groups()[:4])
    group,clock = int(match[5],16),int(match[6])
    if (width,height,peak,clock)!=(1440,3168,120,1234000000) or (actual,group) not in ((120,3),(1,8)):
        raise ValueError('Native state is not a pinned 120-family timing')
    return {'width':width,'height':height,'software_peak_hz':peak,
            'native_actual_hz':actual,'native_group':group,'clock_rate':clock,
            'timing_node':'timing@0' if actual==120 else 'timing@7',
            'evidence':'latest retained dsi_display_set_mode anchor, not physical PWM'}


def qualify_quiet(log, begin, end, reference=None):
    if log.count(begin)!=1 or log.count(end)!=1 or log.index(begin)>=log.index(end):
        raise ValueError('Missing/ambiguous quiet interval')
    prefix, rest = log.split(begin, 1)
    section = rest  # Include the short end-marker-to-dump race as well.
    if 'dsi_ctrl_cmd_transfer len=' in section or 'dsi_display_set_mode' in section or 'Command transfer failed' in section:
        raise ValueError('Native writes or mode transition during qualification')
    current=native_state(log)
    if native_state(prefix)!=current:
        raise ValueError('Native mode changed across qualification')
    if reference is not None and current!=reference:
        raise ValueError('Native mode differs from the baseline reference')
    return current


def stock_anchor_settings(hz):
    if hz == 90:
        return 'set -e; settings put system min_refresh_rate 90.0; settings put system peak_refresh_rate 90.0'
    if hz == 120:
        return 'set -e; settings put system peak_refresh_rate 120.0; settings put system min_refresh_rate 120.0'
    raise ValueError('Only qualified stock90→120 anchor is supported')


def refresh_restore_order(original_min, current_peak):
    # When returning90→120 after a failed anchor, raise the ceiling first.
    # Otherwise lower/clear the minimum first, retaining legacy null semantics.
    try:
        raise_ceiling = float(original_min) > float(current_peak)
    except (ValueError, TypeError):
        raise_ceiling = False
    return ('peak_refresh_rate','min_refresh_rate') if raise_ceiling else ('min_refresh_rate','peak_refresh_rate')


def validate_stock_anchor(log, begin, hz, end=None):
    if hz not in (90,120) or log.count(begin)!=1:
        raise ValueError('Missing/ambiguous stock anchor beginning')
    section=log.split(begin,1)[1]
    if end is not None:
        if log.count(end)!=1 or log.index(end)<=log.index(begin):
            raise ValueError('Missing/ambiguous stock anchor ending')
        section=section.split(end,1)[0]
    if 'Command transfer failed' in section:
        raise ValueError('Native transfer failure during stock anchor')
    lines=[line for line in section.splitlines() if 'dsi_display_set_mode' in line and 'fps=' in line]
    if not lines:
        raise ValueError('No fresh native mode inside stock anchor')
    match=re.search(r'hactive=(\d+), vactive=(\d+), fps=(\d+)\(actual=(\d+), group=0x([0-9a-fA-F]+)\), clk_rate=(\d+)',lines[-1])
    if match is None:
        raise ValueError('Unrecognized stock native anchor')
    width,height,peak,actual=map(int,match.groups()[:4])
    group,clock=int(match[5],16),int(match[6])
    accepted=((90,5),) if hz==90 else ((120,3),(1,8))
    if (width,height,peak,clock)!=(1440,3168,hz,1234000000) or (actual,group) not in accepted:
        raise ValueError('Fresh native anchor is not the requested pinned stock mode')
    return {'software_requested_hz':hz,'native_peak_hz':peak,'native_actual_hz':actual,
            'native_group':group,'clock_rate':clock,'width':width,'height':height,
            'timing_node':{5:'timing@2',3:'timing@0',8:'timing@7'}[group],
            'fresh_native_events':len(lines),'begin_marker':begin,'end_marker':end}


def _events(text):
    return [line for line in text.splitlines() if re.search(r'\bmode_(entry|return|ctrl_return):',line)]


def check_snapshot(text, expected_count, pending=None, length=None, flags=None):
    if 'LOST' in text or re.search(r'\brc=-\d+', text):
        raise ValueError('Lost or failed transaction trace')
    entries=[tuple(map(int,m)) for m in re.findall(r'\bmode_entry:.*?pending=(\d+) length=(\d+) flags=(\d+)',text)]
    returns=list(map(int,re.findall(r'\bmode_return:.*?rc=(-?\d+)',text)))
    controls=list(map(int,re.findall(r'\bmode_ctrl_return:.*?rc=(-?\d+)',text)))
    if len(entries)!=expected_count or len(returns)!=expected_count or any(returns):
        raise ValueError('Incomplete/unexpected transaction callbacks')
    if pending is not None and entries[-1]!=(pending,length,flags):
        raise ValueError('Wrong per-block pending/length/flags')
    return controls


def validate_batch_capture(raw, entry_count):
    found=re.findall(r'^BLOCK_TRACE_BEGIN (-?\d+)\n(.*?)^BLOCK_TRACE_END \1$',raw,re.M|re.S)
    if [int(i) for i,_ in found]!=[-1,0,1,2,3,4]:
        raise ValueError('Missing/duplicate transaction evidence')
    previous=found[0][1]
    old_controls=check_snapshot(previous,entry_count)
    for i,(start,end) in enumerate(RANGES):
        text=found[i+1][1]
        if _events(text)[:len(_events(previous))]!=_events(previous):
            raise ValueError('Transaction trace prefix changed')
        controls=check_snapshot(text,entry_count+i+1,start,end-start,64 if i<4 else 0)
        if controls[:len(old_controls)]!=old_controls or controls[len(old_controls):]!=([0]*75 if i==4 else []):
            raise ValueError('Concurrent controller activity during deferred transaction')
        previous,old_controls=text,controls
    return {'chunks_verified':5,'page_callbacks_verified':5,'controller_packets_verified':75,
            'entry_count_after':entry_count+5,'transport':'single bounded device shell'}


def transaction_script(tmp, trace, name, entry_count):
    if not re.fullmatch(r'/data/local/tmp/[a-zA-Z0-9_/-]+',tmp) or trace!='/sys/kernel/tracing/instances/pwm_mode':
        raise ValueError('Unexpected transaction paths')
    if name not in ('stock','a9_only') or type(entry_count) is not int or entry_count<0:
        raise ValueError('Unexpected transaction program/count')
    # Android awk POSIX subset; verify the actual trace after EVERY write, not dd rc alone.
    awk=r'''/LOST/ {bad=1}
/rc=-[0-9]/ {bad=1}
/mode_entry:/ {e++; for(i=1;i<=NF;i++){if($i~/^pending=/){split($i,a,"=");p=a[2]} if($i~/^length=/){split($i,a,"=");l=a[2]} if($i~/^flags=/){split($i,a,"=");f=a[2]}}}
/mode_return:/ {r++; if($NF!="rc=0")bad=1}
/mode_ctrl_return:/ {c++; if(oldc>=0 && c>oldc && $NF!="rc=0")bad=1}
END {if(bad || e!=want || r!=want || (chunk>=0 && (p!=pending || l!=wantlen || f!=flags)) || (oldc>=0 && c!=oldc+added))exit 51; print c}'''
    body=f'''set -eu
mount -o rprivate none /
mount -t debugfs -o nosuid,nodev,noexec debugfs {tmp}/debugfs
trap 'umount {tmp}/debugfs' EXIT
C={tmp}/debugfs/dri/9800000.qcom,mdss_mdp/DSI-1/tx_cmd
S={tmp}/transaction_trace
[ -f "$C" ] && [ -w "$C" ]
cat {trace}/trace > "$S"
printf 'BLOCK_TRACE_BEGIN -1\\n'; cat "$S"; printf 'BLOCK_TRACE_END -1\\n'
oldc=$(awk -v want={entry_count} -v chunk=-1 -v oldc=-1 -v added=0 {shlex.quote(awk)} "$S")
'''
    for i,(start,end) in enumerate(RANGES):
        body+=f'''dd if={tmp}/chunks/{name}_{i}.txt of="$C" bs=4096 count=1 conv=notrunc status=none
cat {trace}/trace > "$S"
printf 'BLOCK_TRACE_BEGIN {i}\\n'; cat "$S"; printf 'BLOCK_TRACE_END {i}\\n'
oldc=$(awk -v want={entry_count+i+1} -v chunk={i} -v pending={start} -v wantlen={end-start} -v flags={64 if i<4 else 0} -v oldc="$oldc" -v added={75 if i==4 else 0} {shlex.quote(awk)} "$S")
'''
    return 'timeout -k 3 20 unshare -m /system/bin/sh -c '+shlex.quote(body)
