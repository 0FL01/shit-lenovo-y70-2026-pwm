#!/usr/bin/env python3
"""Bounded offline differential tests; only sanitized counters leave the harness."""
import ast, collections, hashlib, json, os, pathlib, random, re, subprocess, sys, tempfile
sys.dont_write_bytecode=True
os.umask(0o077)
HERE=pathlib.Path(__file__).resolve().parent; ROOT=HERE.parent.parent
sys.path.insert(0,str(HERE.parent))
import p85_batched_envelope as oracle
def require(ok,why):
 if not ok: raise RuntimeError(why)
# Verify the exact current qualified oracle/runtime source set before testing.
for name,expected in json.loads((HERE/'runtime-source-blobs.json').read_text())['source_blob_ids'].items():
 raw=(ROOT/name).read_bytes()
 require(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==expected,'qualified_source_changed')
# Compile ONLY exact four parser statements, never import/execute the live runner.
tree=ast.parse((HERE.parent/'run_p85_timed_stock_trial.py').read_text())
method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='write_stage')
start=next(i for i,n in enumerate(method.body) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='guard_match' for x in n.targets))
guard_code=compile(ast.Module(body=method.body[start:start+4],type_ignores=[]),'frozen-guard-fragment','exec')
def gold(kind,data,boot):
 try:
  if kind=='STATE_ONLY':oracle.validate_state(dict(zip(('FIELDS','DISPLAY','BOOT','OWNER'),(x.decode() for x in data))),3600,boot)
  else:exec(guard_code,{'re':re,'check':require,'data':{'PRE_GUARD':data[0].decode()}})
  return True
 except (ValueError,RuntimeError,OverflowError,UnicodeError):return False
counts=collections.Counter()
boot='00000000-0000-0000-0000-000000000000'
base=[b'3600\n0\n0\nEnforcing\n',b'  mActiveSfDisplayMode=DisplayMode{peakRefreshRate=120.0}\n',boot.encode()+b'\n',b'']
with tempfile.TemporaryDirectory(prefix='pwm-snapshot-test-',dir='/tmp') as d:
 w=pathlib.Path(d);require(w.stat().st_mode&0o777==0o700,'temp_mode')
 def run(kind,data,b=boot,rc=0,err=b'',category='synthetic',expected=None,env=None):
  args=['sh',str(HERE/'validate_snapshot.sh'),kind,b if kind=='STATE_ONLY' else '-',str(w/'stage')]
  for i,raw in enumerate(data):
   f=w/f'input{i}';e=w/f'error{i}';f.write_bytes(raw);e.write_bytes(err)
   require(f.stat().st_mode&0o777==0o600,'file_mode')
   args.extend((str(f),str(e),str(rc)))
  r=subprocess.run(args,capture_output=True,timeout=10,env=env)
  good=r.returncode==0
  oracle_good=gold(kind,data,b) and rc==0 and err==b''
  require(not good or oracle_good,'accepted_oracle_rejection')
  require(not good or (not r.stdout and not r.stderr),'unexpected_success_output')
  require(not (w/'stage').exists(),'cleanup_leftovers')
  if expected is not None: require(good==expected,'unexpected_acceptance_'+category)
  counts[category+('_accepted' if good else '_stricter' if oracle_good else '_reject')]+=1
  return good
 run('STATE_ONLY',base,expected=True)
 numeric_boot='1'*36
 numeric_state=base.copy();numeric_state[2]=numeric_boot.encode()+b'\n'
 run('STATE_ONLY',numeric_state,b=numeric_boot,category='numeric_boot',expected=True)
 numeric_state[2]=('1'*35+'2').encode()+b'\n'
 run('STATE_ONLY',numeric_state,b=numeric_boot,category='numeric_boot',expected=False)
 for i,variants in enumerate((
  [b'',b'3600\n0\nEnforcing\n',b'3600\n0\n0\nEnforcing\nextra\n',b' 3600\n0\n0\nEnforcing\n',b'\n'+base[0],base[0]+b'\n',base[0].replace(b'3600',b'03600'),base[0].replace(b'Enforcing',b'Permissive'),b'0\n3600\n0\nEnforcing\n'],
  [b'',base[1]*2,base[1]+b'mActiveSfDisplayMode=x\n',base[1].replace(b'120.0',b'120.0 peakRefreshRate=120.0'),base[1].replace(b'120.0',b'120.0 mActiveSfDisplayMode=x'),base[1]+b'ESD reg_read\n'],
  [b'',b'wrong\n',base[2]*2,b' '+base[2],base[2]+b'\n'],
  [b'\n',b'owner',b'ESD reg_read\n']
 )):
  for v in variants:
   data=base.copy();data[i]=v;run('STATE_ONLY',data)
 for value in ('119.969999999','119.97','119.970000001','120.029999999','120.03','120.030000001','120.0000000001','0120.0','120','120.','120..0','120.0x','NaN','Inf','1e2','-120.0','9'*310+'.0'):
  data=base.copy();data[1]=base[1].replace(b'120.0',value.encode());run('STATE_ONLY',data,category='refresh')
 for a,b in [('0.0','0.0'),('0.0','8.0'),('0.0','8.000000001'),('0.0','7.999999999'),('1.0','0.999999999'),('999999999.0','999999999.0'),('000.0','008.0'),('1.','2.0'),('.0','1.0'),('-1.0','1.0'),('NaN','Inf'),('9'*310+'.0','9'*310+'.0'),('0.0','8.0000000001')]:
  run('GUARD_TIMING',[f'GUARD_TIMING {a} {b}\n'.encode()],category='guard')
 g=b'GUARD_TIMING 1.0 9.0\n'
 for raw in (b'',g*2,g+b'\n',g.rstrip(),g.replace(b' ',b'\t'),g.replace(b' ',b'  '),g+b'X',g.replace(b'1.0',b'1.0:2.0'),g.replace(b'\n',b'\r\n'),b'GUARD_TIMING\n',b'GUARD_TIMING 8\n'):
  run('GUARD_TIMING',[raw],category='grammar',expected=False)
 for kind,data in [('GUARD_TIMING',[g]),('STATE_ONLY',base)]:
  for i,raw in enumerate(data):
   for bad in (b'\0',b'\r',b'\x01',b'\x7f',b'\xff'):
    m=data.copy();m[i]=raw+bad;run(kind,m,category='bytes',expected=False)
  for rc,err in ((1,b''),(124,b''),(0,b'warning')):
   run(kind,data,rc=rc,err=err,category='producer',expected=False)
 # Deterministic fuzz checks every acceptance, including benign display mutations.
 rng=random.Random(2000)
 for _ in range(100):
  i=rng.randrange(4);raw=base[i];j=rng.randrange(len(raw)+1);m=base.copy()
  m[i]=raw[:j]+bytes([rng.randrange(128)])+raw[j:];run('STATE_ONLY',m,category='mutation')
 for tool in ('wc','tr','cmp','awk','rm','rmdir'):
  fake=w/'bin';fake.mkdir(exist_ok=True)
  real=subprocess.run(['which',tool],capture_output=True,text=True,check=True).stdout.strip()
  for fault in ('exit 9','printf warning >&2'):
   f=fake/tool;f.write_text('#!/bin/sh\n'+real+' "$@"\n'+fault+'\n');f.chmod(0o700)
   run('GUARD_TIMING',[g],category='tool_fault',env=dict(os.environ,PATH=str(fake)+':'+os.environ['PATH']),expected=False)
   f.unlink()
 # Command substitution must not discard newline-only diagnostics.
 for tool in ('mkdir','rm','rmdir'):
  real=subprocess.run(['which',tool],capture_output=True,text=True,check=True).stdout.strip()
  for diagnostic in ('\\n','\\n\\n'):
   f=fake/tool
   # For rm exercise the final cleanup branch specifically, not first-stage rm.
   condition='case "$1" in -f) case "$2" in */clean) printf "'+diagnostic+'" >&2;; esac;; esac' if tool=='rm' else 'printf "'+diagnostic+'" >&2'
   f.write_text('#!/bin/sh\n'+real+' "$@"\n'+condition+'\n');f.chmod(0o700)
   run('GUARD_TIMING',[g],category='newline_diagnostic',env=dict(os.environ,PATH=str(fake)+':'+os.environ['PATH']),expected=False)
   f.unlink()
 # Empty/invalid arguments must not consume stdin or hang.
 for args in ([],['STATE_ONLY','','/tmp/no'],['NO','-','/tmp/no'],['GUARD_TIMING','-','',str(w/'input0'),str(w/'error0'),'0']):
  r=subprocess.run(['sh',str(HERE/'validate_snapshot.sh'),*args],capture_output=True,timeout=2)
  require(r.returncode!=0,'argument_acceptance');counts['argument_reject']+=1
 if '--private' in sys.argv:
  for suffix in ('01','02','03'):
   name='p85_timed_stock_a001_20261108_'+suffix;private=pathlib.Path.home()/'.cache/legion-y70-p85-timed-stock'/name
   manifest=json.loads((private/'envelope-manifest.json').read_text());report=json.loads((ROOT/'artifacts'/name/'run.json').read_text())
   require(len(manifest)==len(report['envelope_timings'])==28,'private_count')
   trusted_boot=None
   for rec,event in zip(manifest,report['envelope_timings']):
    require(rec['label']==event['label'],'private_label')
    label=rec['label'];state=(('FIELDS',1024),('DISPLAY',4194304),('BOOT',128),('OWNER',0))
    if label=='state':parts=state
    elif label.startswith('quiet-'):parts=(('BEGIN',0),('WAIT',0),('END',0),('KERNEL',16777216))+state
    elif label.endswith('-hold-end') or label.endswith('-dispatch-gap'):parts=(('END',0),('KERNEL',16777216))+state
    else:parts=(('BEGIN',0),)+((('PRE_GUARD',128),) if label.endswith('-write') else ())+ (('CHILD',1048576),('END',0),('KERNEL',16777216))+state+(('ESD',128),)
    pp=tuple(oracle.Part(k,'offline-no-execution',k=='CHILD',cap) for k,cap in parts)
    plan=oracle.Envelope(rec['nonce'],pp,20,'offline-no-execution' if any(k=='CHILD' for k,_ in parts) else None)
    stem=event['raw_record'];require('/' not in stem and stem.endswith(label),'private_stem')
    saved=oracle.parse((private/(stem+'.stdout')).read_bytes(),plan,returncode=event['return_code'],stderr=(private/(stem+'.stderr')).read_bytes())
    # Metadata taken ONCE from original state fixture, never from mutations.
    if trusted_boot is None:
     require(label=='state','initial_state_required');trusted_boot=saved['BOOT'].strip()
    data=[saved[k].encode() for k in ('FIELDS','DISPLAY','BOOT','OWNER')]
    run('STATE_ONLY',data,b=trusted_boot,category='private_state',expected=gold('STATE_ONLY',data,trusted_boot))
    for i in range(4):
     m=data.copy();m[i]+=b'wrong\n';run('STATE_ONLY',m,b=trusted_boot,category='private_mutation')
    if 'PRE_GUARD' in saved:run('GUARD_TIMING',[saved['PRE_GUARD'].encode()],category='private_guard',expected=True)
print(json.dumps({'status':'PASS','counts':dict(counts),'snapshot_content_only':True,'universal_subset_proven':False},sort_keys=True))
