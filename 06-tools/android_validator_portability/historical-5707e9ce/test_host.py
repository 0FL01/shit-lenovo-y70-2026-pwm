#!/usr/bin/env python3
"""Execute exact generated shell on this host only; no Android APIs/imports."""
import hashlib,json,os,pathlib,shutil,subprocess,tempfile,time
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parent.parent
def require(ok,why):
    if not ok:raise RuntimeError(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def verify(b,manifest):
    require(set(manifest)=={'schema','status','sources','files','input_bytes','scope','max_concurrent_processes','per_case_timeout_seconds','timeout_kill_grace_seconds','expected_normal_seconds_under','finite_suite_worst_case_seconds','per_file_output_review_cap_bytes','total_output_review_cap_bytes','bounds_are_not_enforced_remote_storage_quotas'},'manifest schema mismatch')
    for name,want in manifest['files'].items():
        p=b/name;require(p.is_file() and not p.is_symlink() and sha(p.read_bytes())==want,'bundle source mismatch: '+name)
    expected=''.join(f'{h}  {n}\n' for n,h in sorted(manifest['files'].items()))
    require((b/'SHA256SUMS').read_text()==expected,'checksum list mismatch')
    for name,want in manifest['sources'].items():require(blob((ROOT/name).read_bytes())==want,'upstream source mismatch')
def observations(w,cases):
    require((w/'OBSERVED').read_bytes()==b'SYNTHETIC_OBSERVATIONS_ONLY\n','missing observations')
    for c in cases:
        n=c['name'];rc=int((w/(n+'.rc')).read_bytes());out=(w/(n+'.stdout')).read_bytes();err=(w/(n+'.stderr')).read_bytes()
        require((rc!=0 if c['nonzero'] else rc==c['rc']),'status '+n)
        if c['observe']:
            if n in ('owner','metadata_owner'):require(out==f'{os.getuid()}\n'.encode() and not err,'owner')
            elif n=='limit_units':
                parts=out.split();require(len(parts)==2 and int(parts[0])!=0 and int(parts[1]) in (512,1024),'unqualified ulimit units')
            else:raise RuntimeError('unknown observation')
        else:
            if c['tokens'] is not None:require(out.split()==[x.encode() for x in c['tokens']],'tokens '+n)
            else:require(out==bytes.fromhex(c['stdout']),'stdout '+n)
            require(bool(err) if c['err_nonempty'] else err==bytes.fromhex(c['stderr']),'stderr '+n)
    expected={'OBSERVED','exclusive','limited','decoded'}
    for c in cases:expected.update(c['name']+ext for ext in ('.rc','.stdout','.stderr'))
    require(set(p.name for p in w.iterdir())==expected,'owned cleanup leftover')
    require(set(p.name for p in (w/'decoded').iterdir())=={'section01','SUCCESS'},'decoded file list')
    require((w/'decoded/section01').read_bytes()==bytes(range(1,128)),'decoded bytes')
    total=0
    for p in w.rglob('*'):
        require(not p.is_symlink(),'unexpected symlink')
        if p.is_file():
            require(p.stat().st_size<=1048576,'file expansion cap')
            require(p.stat().st_mode&0o777==0o600,'file mode')
            total+=p.stat().st_size
    require(total<=16777216,'total expansion cap')
    return total
def main():
    os.umask(0o077);b=HERE/'bundle';manifest=json.loads((HERE/'manifest.json').read_text())
    verify(b,manifest);cases=json.loads((b/'cases.json').read_text())
    results=[];evidence=[];started=time.monotonic()
    # TemporaryDirectory is host-only, created and wholly owned by this test.
    # Device code never recursively deletes anything; retained reports are intentional.
    with tempfile.TemporaryDirectory(prefix='android-portability-host-') as td:
        root=pathlib.Path(td);foreign=root/'foreign';foreign.write_bytes(b'UNTOUCHED\0')
        def run(name,env=None,bundle=b,work=None):
            w=work or root/name
            r=subprocess.run(['sh',str(bundle/'probe.sh'),str(w),str(os.getuid())],capture_output=True,env=env,timeout=60)
            require(foreign.read_bytes()==b'UNTOUCHED\0','foreign changed')
            captured={}
            if w.is_dir():
                for p in sorted(w.iterdir()):
                    if p.is_file() and p.suffix in ('.rc','.stdout','.stderr'):
                        captured[p.name]=p.read_bytes().hex()
            evidence.append(dict(name=name,launcher_rc=r.returncode,stdout_hex=r.stdout.hex(),stderr_hex=r.stderr.hex(),files_hex=captured))
            return w,r
        w,r=run('baseline')
        require(r.returncode==0 and not r.stdout and not r.stderr,'baseline launcher failed')
        total=observations(w,cases);results.append(dict(test='baseline',cases=len(cases),bytes=total))
        # Finite fault stub returns timeout without spawning any process.
        fake=root/'bin_timeout';fake.mkdir()
        stub=fake/'timeout';stub.write_text('#!/bin/sh\nexit 124\n');stub.chmod(0o700)
        w,r=run('timeout_stop',dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH']))
        require(r.returncode==4 and not (w/'OBSERVED').exists(),'timeout did not stop')
        require(set(p.name for p in w.iterdir())=={'arithmetic.rc','arithmetic.stdout','arithmetic.stderr'},'dispatch after timeout')
        results.append(dict(test='timeout_stops_dispatch',passed=True))
        # Match ONLY the outer case deadline: never fake the expected inner timeout.
        prior=[c['name'] for c in cases[:next(i for i,c in enumerate(cases) if c['name']=='finite_timeout')]]
        require(len(prior)==23,'finite timeout position changed; review regression')
        actual_timeout=shutil.which('timeout');require(actual_timeout is not None,'missing timeout')
        for status in (124,137):
            fake=root/('bin_outer_'+str(status));fake.mkdir()
            stub=fake/'timeout'
            stub.write_text('#!/bin/sh\nfor arg do\n case "$arg" in */cases/finite_timeout.sh) exit '+str(status)+';; esac\ndone\nexec '+actual_timeout+' "$@"\n')
            stub.chmod(0o700)
            w,r=run('outer_finite_timeout_'+str(status),dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH']))
            require(r.returncode==4 and not r.stdout and not r.stderr,'outer timeout launcher status')
            require((w/'finite_timeout.rc').read_bytes()==f'{status}\n'.encode(),'outer timeout status lost')
            require((w/'finite_timeout.stdout').read_bytes()==b'' and (w/'finite_timeout.stderr').read_bytes()==b'','inner timeout falsely observed')
            expected={'exclusive','limited'}
            for n in prior+['finite_timeout']:expected.update(n+ext for ext in ('.rc','.stdout','.stderr'))
            require(set(p.name for p in w.iterdir())==expected,'dispatch/OBSERVED after outer timeout')
            rejected=False
            try:observations(w,cases)
            except (RuntimeError,FileNotFoundError):rejected=True
            require(rejected,'oracle accepted outer timeout')
            results.append(dict(test='outer_finite_timeout_'+str(status)+'_stops_after_23',passed=True))
        # Fresh malformed framing must reach decoder parse rc3, not collision rc2.
        base=root/'baseline'
        require((base/'envelope_bad.rc').read_bytes()==b'3\n','malformed envelope did not reach parser')
        require(not (base/'envelope_bad.stdout').read_bytes() and not (base/'envelope_bad.stderr').read_bytes(),'malformed byte contract')
        require(not (base/'decoded_bad').exists() and not (base/'decoded_bad.stage').exists(),'malformed publication/remnant')
        require((base/'envelope_collision.rc').read_bytes()==b'2\n','collision status')
        require((base/'decoded/section01').read_bytes()==bytes(range(1,128)),'collision changed published payload')
        require((base/'decoded/SUCCESS').read_bytes()==b'P85-OFFLINE-ASCII-ENVELOPE-v1\n','collision changed marker')
        results.append(dict(test='malformed_parse_and_separate_collision',passed=True))
        # Independently prove malformed fixture reaches frozen AWK parser and fails there.
        require((b/'fixtures/envelope_bad').read_bytes()==(b/'fixtures/envelope').read_bytes()[:-1], 'truncated fixture bytes')
        require((b/'fixtures/envelope').read_bytes().endswith(b':DONE\n'), 'valid final framing')
        trace=root/'malformed_parser';trace.mkdir()
        fake=root/'bin_parser_trace';fake.mkdir();actual_awk=shutil.which('awk')
        require(actual_awk is not None,'missing awk')
        stub=fake/'awk'
        stub.write_text('#!/bin/sh\n'+actual_awk+' "$@"\nr=$?\ncase "$2" in */components/envelope/decode.awk) printf "%s\\n" "$r" > "$W/parser.rc";; esac\nexit "$r"\n')
        stub.chmod(0o700)
        env=dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH'],B=str(b),W=str(trace),TMPDIR=str(trace))
        parsed=subprocess.run(['sh',str(b/'cases/envelope_bad.sh')],capture_output=True,env=env,timeout=10)
        require(parsed.returncode==3 and not parsed.stdout and not parsed.stderr,'standalone malformed invocation bytes')
        require((trace/'parser.rc').read_bytes()==b'1\n','malformed did not reach/reject in frozen parser')
        require(set(p.name for p in trace.iterdir())=={'parser.rc'},'malformed publication or cleanup leftovers')
        evidence.append(dict(name='malformed_parser_rejection',launcher_rc=parsed.returncode,stdout_hex=parsed.stdout.hex(),stderr_hex=parsed.stderr.hex(),files_hex={'parser.rc':(trace/'parser.rc').read_bytes().hex()}))
        results.append(dict(test='malformed_frozen_parser_rc1',passed=True))
        # Existing launch root is never adopted, changed or removed.

        w=root/'collision';w.mkdir();(w/'foreign').write_bytes(b'KEEP')
        _,r=run('collision',work=w)
        require(r.returncode!=0 and (w/'foreign').read_bytes()==b'KEEP' and len(list(w.iterdir()))==1,'collision adoption')
        results.append(dict(test='launch_collision',passed=True))
        # Expected shell noclobber collision does not truncate its own inode.
        require((root/'baseline/exclusive').read_bytes()==b'','noclobber')
        # Both manifest and component substitutions rejected before launch.
        badmanifest=json.loads(json.dumps(manifest));first=next(iter(badmanifest['files']));badmanifest['files'][first]='0'*64
        try:verify(b,badmanifest)
        except RuntimeError:pass
        else:raise RuntimeError('manifest mismatch accepted')
        altered=root/'altered';shutil.copytree(b,altered)
        (altered/'components/capture/capture.awk').write_text('BEGIN{exit 0}\n')
        try:verify(altered,manifest)
        except RuntimeError:pass
        else:raise RuntimeError('source mismatch accepted')
        w,r=run('source_mismatch',bundle=altered)
        require(r.returncode!=0 and not w.exists(),'shell mismatch did not fail before writes')
        results.append(dict(test='source_and_manifest_mismatch',passed=True))
        # Trusted host-only finite stubs. No system binary modified, no dynamic API in bundle.
        for label,tool,tail in [('status','awk','exit 7'),('lf','awk',"printf '\\012' >&2"),
                ('nul','awk',"printf '\\000' >&2"),('cleanup_status','rmdir','exit 7'),
                ('cleanup_lf','rm',"printf '\\012' >&2"),('cleanup_nul','rm',"printf '\\000' >&2")]:
            fake=root/('bin_'+label);fake.mkdir()
            actual=shutil.which(tool);require(actual is not None,'missing host utility')
            # Delegate first to test valid output followed by failure/diagnostic.
            stub=fake/tool;stub.write_text('#!/bin/sh\n'+actual+' "$@"\nr=$?\n[ "$r" = 0 ] || exit "$r"\n'+tail+'\n');stub.chmod(0o700)
            env=dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH'])
            w,r=run('fault_'+label,env)
            rejected=False
            try:
                require(r.returncode==0 and not r.stdout and not r.stderr,'launcher rejected')
                observations(w,cases)
            except RuntimeError:rejected=True
            require(rejected,'fault accepted '+label)
            # Capture wrapper specifically must not report invocation success.
            if (w/'capture_write.rc').exists():require(int((w/'capture_write.rc').read_bytes())!=0,'capture fault missed '+label)
            results.append(dict(test=label,passed=True))
        # Cleanup non-execution leaves own remnants, never foreign deletion/success.
        fake=root/'bin_cleanup_refuse';fake.mkdir()
        stub=fake/'rmdir';stub.write_text('#!/bin/sh\nexit 7\n');stub.chmod(0o700)
        w,r=run('fault_cleanup_refuse',dict(os.environ,PATH=str(fake)+os.pathsep+os.environ['PATH']))
        require(int((w/'capture_write.rc').read_bytes())!=0,'cleanup refusal accepted')
        require(any(p.name.startswith('.p85-validator-') for p in w.iterdir()),'cleanup uncertainty lost')
        results.append(dict(test='cleanup_remnant_quarantine',passed=True))
    result={'status':'HOST_ONLY_PASS','android_qualified':False,'independent_review':'PENDING',
       'manifest_sha256':sha((HERE/'manifest.json').read_bytes()),'elapsed_seconds':round(time.monotonic()-started,3),
       'tests':results,'runtime_source_blobs_unchanged':None}
    runtime=json.loads((ROOT/'06-tools/offline_local_snapshot_spike/runtime-source-blobs.json').read_text())['source_blob_ids']
    for name,want in runtime.items():require(blob((ROOT/name).read_bytes())==want,'runtime modified')
    result['runtime_source_blobs_unchanged']=len(runtime)
    suffix='optimized' if not __debug__ else 'normal'
    (HERE/('observations-'+suffix+'.json')).write_text(json.dumps(evidence,indent=2)+'\n')
    (HERE/('results-'+suffix+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()

