#!/usr/bin/env python3
"""Build a fixed synthetic-only shell bundle. Never invokes a device or live runner."""
import hashlib, json, os, pathlib, shlex
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent.parent
def require(ok, message):
    if not ok: raise RuntimeError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def blob(data): return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def build():
    os.umask(0o077)
    dest=HERE/'bundle'
    require(not dest.exists(), 'bundle exists; do not replace a frozen bundle')
    dest.mkdir(mode=0o700)
    records={}; sources={}; cases=[]
    def put(name,data):
        if isinstance(data,str):data=data.encode()
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        p.write_bytes(data);p.chmod(0o600);records[name]=sha(data)
    groups={'capture':['validate_capture.sh','capture.awk','state.awk','writer_wire.awk'],
            'interval':['validate.sh','interval.awk'],
            'envelope':['decode.sh','decode.awk'],
            'snapshot':['validate_snapshot.sh','snapshot.awk']}
    for short,names in groups.items():
        source='validator' if short=='capture' else short
        for name in names:
            path=f'06-tools/offline_local_{source}_spike/{name}'
            data=(ROOT/path).read_bytes();sources[path]=blob(data)
            put('components/'+short+'/'+name,data)
    def case(name,script,rc=0,out=b'',err=b'',out_tokens=None,nonzero=False,err_nonempty=False,observe=False):
        put('cases/'+name+'.sh','set -u\numask 077\nLC_ALL=C; export LC_ALL\n'+script+'\n')
        cases.append(dict(name=name,rc=rc,stdout=out.hex(),stderr=err.hex(),tokens=out_tokens,nonzero=nonzero,err_nonempty=err_nonempty,observe=observe))
    fixtures={'bytes':bytes([0,9,10,13,31,32,65,126,127,128]),'ascii':bytes([9,10,32,65,126]),
              'empty':b'','lf':b'\n','nul':b'\0','noLF':b'x','line32768':b'x'*32768+b'\n','line32769':b'x'*32769+b'\n',
              'finite2048':b'x'*2048}
    for n,d in fixtures.items():put('fixtures/'+n,d)
    case('arithmetic','printf "%s\\n" "$((16777216 + 25165824))"',out=b'41943040\n')
    case('read_eof','v=; IFS= read -r v < "$B/fixtures/noLF"; r=$?; printf "%s:%s\\n" "$r" "$v"',out=b'1:x\n')
    case('byte_wc','wc -c < "$B/fixtures/bytes"',out_tokens=['10'])
    case('byte_od','od -An -v -tu1 < "$B/fixtures/bytes"',out_tokens=['0','9','10','13','31','32','65','126','127','128'])
    case('byte_tr',"tr -cd '\\011\\012\\040-\\176' < \"$B/fixtures/bytes\"",out=fixtures['ascii'])
    case('byte_tail','tail -c 1 < "$B/fixtures/bytes"',out=b'\x80')
    case('byte_cmp','cmp -s "$B/fixtures/bytes" "$B/fixtures/ascii"',rc=1)
    case('noclobber','set -C\n: > "$W/exclusive"\n( : > "$W/exclusive" )',nonzero=True,err_nonempty=True)
    case('override','set -C\nprintf old > "$W/override"\nprintf new >| "$W/override"\ncat "$W/override"\nrm "$W/override"',out=b'new')
    for kind,data in [('empty',b''),('lf',b'\n'),('nul',b'\0')]:
        script='set -C\n: > "$W/audit" || exit 2\nexec 8>> "$W/audit" || exit 2\nrm "$W/audit" || exit 2\n[ -f /proc/self/fd/8 ] && [ ! -s /proc/self/fd/8 ] || exit 2\ncat "$B/fixtures/'+kind+'" >&8 || exit 2\n'
        script+=('[ ! -s /proc/self/fd/8 ]' if not data else '[ -s /proc/self/fd/8 ]')+' || exit 2\ncat /proc/self/fd/8 || exit 2\nexec 8>&-'
        case('fd_'+kind,script,out=data)
    case('metadata_mode','stat -c %a \"$B/fixtures/bytes\"',out=b'600\n')
    case('metadata_links','stat -c %h \"$B/fixtures/bytes\"',out=b'1\n')
    case('owner','id -u',observe=True)
    case('metadata_owner','stat -c %u \"$W\"',observe=True)
    for name in ('empty','lf','noLF','line32768','line32769'):
        case('bytes_'+name, 'cat \"$B/fixtures/'+name+'\"',out=fixtures[name])
    case('awk_features',"""awk 'BEGIN {x=999999999*1000000+999999; if(sprintf("%.0f",x)!="999999999999999")exit 1; if(split("12.34",a,".")!=2||a[1]!="12"||a[2]!="34")exit 1; delete a[1]; if(1 in a)exit 1; s="abc"; sub(/b/,"x",s); match(s,/xc/); if(RLENGTH!=2)exit 1; if(ENVIRON["LC_ALL"]!="C")exit 1; printf "%c%c",65,10}'""",out=b'A\n')
    case('limit_units','(ulimit -f 1 || exit 2; cat "$B/fixtures/finite2048" > "$W/limited")\nr=$?\nprintf "%s\\n" "$r"\nwc -c < "$W/limited"',observe=True)
    case('finite_timeout','timeout -k 1 1 sh -c "sleep 2"\nr=$?\nprintf "INNER_TIMEOUT_RC=%s\\n" "$r"\n[ "$r" = 124 ] || exit 3',out=b'INNER_TIMEOUT_RC=124\n')
    nonce='012345abcdef'
    for kind in ('write','85','C1'):
        rows=[]
        def event(name,pid,fields): rows.append(f'printf-{pid} [000] d.... 1.000000: {name}_{nonce}: (symbol) {fields}')
        for i in range(3):
            event('entry',i+1,f'pending=0 length={9 if kind=="write" and i==1 else 11} flags=0')
            event('ctrl',i+1,'rc=0');event('tx',i+1,'rc=0')
            if i==0 and kind!='write':
                event('hardware',9,'hw_status=0x90000 read_bytes=16 mrps=3')
                event('header',9,'header=0x1600031c requested=3 count=9 allocation=16 disp_op=0');event('ctrl',9,'rc=3')
        pre=['STATE 3600 120.00001','ESD_INITIAL reg_read','ESD_ACTIVE esd_sw_sim_success']
        if kind=='write':pre += ['WRITE_GATE_OK '+x for x in '01233']
        else:pre += ['GATE_OK '+x for x in '0123']+[('P85_LONG3 0x15 0x00 0x00' if kind=='85' else 'C1 0x00 0x00 0x60')]+['GATE_OK 3','GATE_OK 4']
        if kind=='C1':pre+=['ESD_RESTORED reg_read']
        pre+=['TRACE_BEGIN',*rows,'TRACE_END','PROFILE_BEGIN']
        pre += [f'{n}_{nonce} {c} 0' for n,c in [('header',0 if kind=='write' else 1),('hardware',0 if kind=='write' else 1),('ctrl',3 if kind=='write' else 4),('tx',3),('entry',3)]]
        pre+=['PROFILE_END']
        if kind!='C1':pre+=['ESD_RESTORED reg_read']
        pre+=['CLEANUP_OK']
        raw=('\n'.join(pre)+'\n').encode()
        put('fixtures/capture_'+kind,raw)
        put('fixtures/capture_'+kind+'_bad',raw[:-1])
        args=f'sh "$B/components/capture/validate_capture.sh" "$B/fixtures/capture_{kind}" "$B/fixtures/empty" {nonce} {kind} 0'
        out=f'kind={kind}\ndata={"" if kind=="write" else ("21,0,0" if kind=="85" else "0,0,96")}\nraw_count={0 if kind=="write" else 9}\nrefresh=120.00001\ncallbacks=3\n'.encode()
        case('capture_'+kind,args,out=out)
        case('capture_'+kind+'_bad',args.replace('capture_'+kind+'"','capture_'+kind+'_bad"'),nonzero=True)
        if kind=='write':
            for label,err,rc in [('rc7','empty',7),('lf','lf',0),('nul','nul',0)]:
                case('capture_'+label,args.replace('fixtures/empty','fixtures/'+err).removesuffix(' 0')+' '+str(rc),nonzero=True)
    native='[ 1.000000] [drm:dsi_display_set_mode [msm_drm]] [msm-dsi-info]: mdp_transfer_time=7465, hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000\n'
    for label,body,good in [('valid',native+'[ 2.000000] PWM_TEST_BEGIN\n[ 4.000000] PWM_TEST_END\n',True),
        ('short',native+'[ 2.000001] PWM_TEST_BEGIN\n[ 4.000000] PWM_TEST_END\n',False),
        ('collision',native+'[ 2.000000] PWM_TEST_BEGIN\n[ 4.000000] PWM_TEST_END\nPWM_P85_WRITE_'+nonce+'\n',False),
        ('tail',native+'[ 2.000000] PWM_TEST_BEGIN\n[ 4.000000] PWM_TEST_END\nLOST\n',False)]:
        put('fixtures/interval_'+label,body)
        case('interval_'+label,f'sh "$B/components/interval/validate.sh" quiet PWM_TEST_BEGIN PWM_TEST_END 120 {nonce} "$B/fixtures/interval_{label}" OFFLINE',out=b'ACCEPT offline interval semantics only\n' if good else b'',nonzero=not good)
    boot='00000000-0000-0000-0000-000000000000'
    for name,data in [('fields','3600\n0\n0\nEnforcing\n'),('display','mActiveSfDisplayMode=x peakRefreshRate=120.0\n'),('boot',boot+'\n')]:put('fixtures/'+name,data)
    state=f'sh "$B/components/snapshot/validate_snapshot.sh" STATE_ONLY {boot} "$W/state"'
    for name in ('fields','display','boot','empty'):state+=f' "$B/fixtures/{name}" "$B/fixtures/empty" 0'
    case('state_valid',state)
    put('fixtures/esd_synthetic','reg_read\n')
    put('fixtures/boot_literal',r'boot\101'+'\n')
    fragment='awk -f "$B/components/capture/state.awk" "$B/fixtures/fields" "$B/fixtures/display" "$B/fixtures/boot_literal" "$B/fixtures/empty" "$B/fixtures/esd_synthetic"'
    case('state_raw_identity',"P85_OFFLINE_EXPECTED_BOOT='boot\\101' "+fragment,out=b'dbv=3600\npower=0\ndc=0\nenforcing=1\nboot_match=1\nowner_output_empty=1\nesd=reg_read\n')
    case('state_escape_alias',"P85_OFFLINE_EXPECTED_BOOT=bootA "+fragment,nonzero=True)
    case('state_missing_identity','unset P85_OFFLINE_EXPECTED_BOOT\n'+fragment,nonzero=True)
    for label,err,rc in [('rc7','empty',7),('lf','lf',0),('nul','nul',0)]:
        case('snapshot_'+label,state.replace('fixtures/empty" 0','fixtures/'+err+'" '+str(rc)),nonzero=True)

    case('state_owner_lf',state.rsplit('"$B/fixtures/empty" "$B/fixtures/empty" 0',1)[0]+'"$B/fixtures/lf" "$B/fixtures/empty" 0',nonzero=True)
    for i,(a,b,good) in enumerate([('0.0','0.0',True),('0.0','8.0',True),('0.0','8.000000001',False),('1.0','0.999999999',False),('999999999.0','999999999.0',True),('000.0','008.0',False)]):
        put('fixtures/guard'+str(i),f'GUARD_TIMING {a} {b}\n')
        case('guard'+str(i),f'sh "$B/components/snapshot/validate_snapshot.sh" GUARD_TIMING - "$W/guard{i}" "$B/fixtures/guard{i}" "$B/fixtures/empty" 0',nonzero=not good)
    payload=bytes(range(1,128));pre=b'@P85E:012345abcdef:'
    raw=pre+b'START\n'+pre+b'SECTION A 0 127 0\n'+payload+b'\n'+pre+b'END A\n'+pre+b'DONE\n'
    put('fixtures/plan','A 256\n');put('fixtures/envelope',raw);put('fixtures/envelope_bad',raw[:-1]);put('fixtures/payload',payload)
    command='sh "$B/components/envelope/decode.sh" "$B/fixtures/envelope" "$B/fixtures/plan" 012345abcdef 0 "$B/fixtures/empty" "$W/decoded"'
    case('envelope_valid',command+' || exit $?\ncmp -s "$W/decoded/section01" "$B/fixtures/payload" || exit 4\ncat "$W/decoded/SUCCESS"',out=b'P85-OFFLINE-ASCII-ENVELOPE-v1\n')
    case('envelope_collision',command,rc=2)
    case('envelope_bad',command.replace('fixtures/envelope"','fixtures/envelope_bad"').replace('$W/decoded', '$W/decoded_bad'),rc=3)
    for label,err,rc in [('rc7','empty',7),('lf','lf',0),('nul','nul',0)]:
        case('envelope_'+label,command.replace('abcdef 0','abcdef '+str(rc)).replace('fixtures/empty','fixtures/'+err).replace('$W/decoded','$W/decoded_'+label),rc=2)
    put('cases.json',json.dumps(cases,indent=2)+'\n')
    # Static command list only: caller cannot supply code, fixture kind or stage.
    script='''#!/bin/sh
# Synthetic userspace ONLY. This does not dispatch any device/trial operation.
set -u
umask 077
LC_ALL=C; export LC_ALL
[ "$#" = 2 ] || exit 2
W=$1; expected_uid=$2
case "$W" in /*) ;; *) exit 2;; esac
case "$expected_uid" in ''|*[!0-9]*) exit 2;; esac
case "$0" in /*) B=${0%/*};; *) exit 2;; esac
export B W
for tool in sh timeout sleep id sha256sum mkdir rm rmdir cat cmp tr od tail wc stat awk mv; do
 command -v \"$tool\" >/dev/null 2>&1 || exit 2
done
[ ! -e "$W" ] && [ ! -L "$W" ] || exit 2
uid=$(id -u) || exit 2
[ "$uid" = "$expected_uid" ] || exit 2
# Outer launcher must already have verified trusted manifest and bundle/source.
(cd "$B" && sha256sum -c SHA256SUMS) >/dev/null || exit 2
mkdir -m 700 "$W" || exit 2
TMPDIR=$W; export TMPDIR
# Input mode/owner and trusted parent are launch obligations. Never fix them here.
run() {
 n=$1
 (ulimit -f 32768 || exit 3; timeout -k 1 4 sh "$B/cases/$n.sh" > "$W/$n.stdout" 2> "$W/$n.stderr")
 r=$?
 printf '%s\\n' "$r" > "$W/$n.rc" || exit 3
 # Timeout/cancellation uncertainty stops dispatch and never creates completion.
 [ "$r" != 124 ] && [ "$r" != 137 ] || exit 4
}
'''
    for c in cases:script+='run '+c['name']+'\n'
    script+='printf "SYNTHETIC_OBSERVATIONS_ONLY\\n" > "$W/OBSERVED"\n'
    put('probe.sh',script)
    total=sum(len((dest/n).read_bytes()) for n in records if n.startswith('fixtures/'))
    require(total<=1048576,'fixture input cap')
    manifest=dict(schema=1,status='OFFLINE_UNREVIEWED',sources=sources,files=records,input_bytes=total,
       scope='synthetic userspace observations only; never admission',max_concurrent_processes=8,
       per_case_timeout_seconds=4,timeout_kill_grace_seconds=1,
       expected_normal_seconds_under=10,finite_suite_worst_case_seconds=len(cases)*5,
       per_file_output_review_cap_bytes=1048576,total_output_review_cap_bytes=16777216,
       bounds_are_not_enforced_remote_storage_quotas=True)
    (dest/'SHA256SUMS').write_text(''.join(f'{h}  {n}\n' for n,h in sorted(records.items())))
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'fixture_bytes':total,'manifest_sha256':sha((HERE/'manifest.json').read_bytes())}))
if __name__=='__main__':build()

