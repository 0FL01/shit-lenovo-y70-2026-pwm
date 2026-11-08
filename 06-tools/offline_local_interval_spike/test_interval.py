"""Offline differential tests. Python is a test oracle, not the proposed decoder.

Private payloads are never printed or retained. Private temporary files live
outside Git and are removed. No controller CLI is invoked.
"""
import ast
import copy
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import dsi_trial_transaction as d
import stock_c1_sweep as s
import run_p85_timed_stock_trial as t

B = 'PWM_TEST_BEGIN'
E = 'PWM_TEST_END'
N = 'abcdef012345'
PREFIX = '[drm:dsi_display_set_mode [msm_drm]] [msm-dsi-info]: mdp_transfer_time=7465, '
TUPLE = 'hactive=1440, vactive=3168, fps=120(actual=120, group=0x3), clk_rate=1234000000'
A = '[ 1.000000] ' + PREFIX + TUPLE + '\n'
BR = '[ 2.000000] ' + B + '\n'
ER = '[ 4.000000] ' + E + '\n'
TX = '[ 3.000000] dsi-ctrl-1: dsi_ctrl_cmd_transfer len=1, type=0x06 lp cmds= C1\n'
BASE = A + BR + ER
REF = d.native_state(A)

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def frozen():
    rows = (HERE/'runtime-before.blobs').read_text().splitlines()
    for row in rows:
        blob, path = row.split(' ', 1)
        actual = subprocess.check_output(['git', 'hash-object', path], cwd=ROOT, text=True).strip()
        require(actual == blob, 'Frozen runtime changed: ' + path)
    return len(rows)

# Compile the exact read tail-check AST, including marker derivation, from the
# current production caller. No textual restatement of its rejection predicate.
tree = ast.parse((HERE.parent/'run_p85_timed_stock_trial.py').read_text())
cls = next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='TimedStockTrial')
method = next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='envelope')
tail_node = next(x for x in ast.walk(method) if isinstance(x,ast.If)
                 and ast.unparse(x.test)=='plan.child_command')
tail_code = compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(tail_node)], type_ignores=[])),
                    str(HERE.parent/'run_p85_timed_stock_trial.py'), 'exec')

# Extract only the unchanged embedded AWK from guard_command. Never execute its
# surrounding shell, which acquires kernel state and touches the device.
guard_fn = next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='guard_command')
guard_awk = next(x.value.value for x in guard_fn.body if isinstance(x,ast.Assign)
                 and any(isinstance(y,ast.Name) and y.id=='awk' for y in x.targets))

def oracle(log, op, begin=B, end=E, ref='120', nonce=N):
    reference = REF if ref=='120' else d.native_state(A.replace('actual=120, group=0x3','actual=1, group=0x8'))
    try:
        if op=='read':
            s.verify_read_interval(log,begin,end,reference)
            plan=SimpleNamespace(child_command=True,parts=[SimpleNamespace(label='END',command='<6>'+end+'\\n')])
            exec(tail_code, {'plan':plan,'data':{'KERNEL':log},'check':s.check})
        elif op in ('quiet','dispatch'):
            d.qualify_quiet(log,begin,end,reference)
            if nonce!='-':
                s.check('PWM_P85_WRITE_'+nonce not in log,'Writer collision')
            if op=='quiet':
                obj=object.__new__(t.TimedStockTrial)
                obj._last_quiet_kernel=log
                with patch.object(t.batch.BatchedTrial,'quiet',return_value={'begin_marker':begin,'end_marker':end}):
                    t.TimedStockTrial.quiet(obj,'OFFLINE',3600)
        if op in ('dispatch','guard'):
            result=subprocess.run(['awk','-v','mark='+begin,'-v','collision=PWM_P85_WRITE_'+nonce,guard_awk],
                                  input=log,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            require(result.returncode in (0,1),'Guard oracle execution error')
            return result.returncode==0
        return True
    except (ValueError,RuntimeError):
        return False

def port(log, op, begin=B, end=E, ref='120', nonce=N):
    if op=='guard': end='-'
    with tempfile.TemporaryDirectory(prefix='pwm-offline-interval-') as tmp, tempfile.NamedTemporaryFile(dir=tmp) as f:
        f.write(log.encode('utf-8')); f.flush()
        p=subprocess.run(['sh',str(HERE/'validate.sh'),op,begin,end,ref,nonce,f.name,'OFFLINE'],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
    require(p.returncode in (0,1), 'Decoder invocation error')
    return p.returncode==0

def invocation_regressions():
    stats={'invalid_arguments':0,'producer_failures':0,'cleanup_verified':0}
    valid=['quiet',B,E,'120',N]
    invalid=[]
    for index,values in ((0,('', 'unknown')), (1,('', 'short', 'x'*181, 'bad marker', 'bad\\marker')),
                         (2,('', 'short', B, B+'suffix')), (3,('', '90')),
                         (4,('', 'ABCDEF012345', 'x'*12, 'abc'))):
        for value in values:
            args=valid.copy(); args[index]=value; invalid.append(args)
    invalid.extend([['guard',B,'','120',N],['guard',B,E,'120',N],
                    ['guard',B,'-','1',N],['dispatch',B,E,'120','-']])
    with tempfile.TemporaryDirectory(prefix='pwm-offline-invocation-') as tmp:
        root=Path(tmp); log=root/'synthetic.log'; log.write_text(BASE)
        for args in invalid:
            commands=[['sh',str(HERE/'validate.sh'),*args,str(log),'OFFLINE'],
                      ['awk',*[item for key,value in zip(('op','begin','end','ref','nonce'),args)
                               for item in ('-v',key+'='+value)],'-f',str(HERE/'interval.awk')]]
            for command in commands:
                result=subprocess.run(command,input=BASE,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=2)
                require(result.returncode==2,'Invalid arguments must terminate with2')
                require('ACCEPT' not in result.stdout,'Invalid arguments emitted ACCEPT')
                stats['invalid_arguments']+=1
        for tool,occurrence in [('wc',1),('wc',2),('tail',1),('od',1),('tr',1),('awk',1)]:
            actual=shutil.which(tool);require(actual is not None,'Missing test executable')
            for fault in ('nonzero','stderr','empty','truncated'):
                bindir=root/'bin';bindir.mkdir(exist_ok=True)
                counter=root/'counter'
                if counter.exists(): counter.unlink()
                script=bindir/tool
                script.write_text('#!'+sys.executable+'\n'+
                    'import pathlib,subprocess,sys\n'+
                    'counter=pathlib.Path('+repr(str(counter))+')\n'+
                    'count=int(counter.read_text())+1 if counter.exists() else 1\n'+
                    'counter.write_text(str(count))\n'+
                    'p=subprocess.run(['+repr(actual)+']+sys.argv[1:],input=sys.stdin.buffer.read(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)\n'+
                    'out=p.stdout; err=p.stderr; rc=p.returncode\n'+
                    'if count=='+str(occurrence)+':\n'+
                    {'nonzero':' rc=7\n','stderr':" err+=b'injected producer warning\\n'\n",
                     'empty':" out=b''\n",'truncated':' out=out[:-1]\n'}[fault]+
                    'sys.stdout.buffer.write(out);sys.stderr.buffer.write(err);sys.exit(rc)\n')
                script.chmod(0o700)
                scratch=root/'scratch';scratch.mkdir(exist_ok=True)
                env=os.environ.copy();env.update(PATH=str(bindir)+os.pathsep+env.get('PATH',''),TMPDIR=str(scratch))
                result=subprocess.run(['sh',str(HERE/'validate.sh'),*valid,str(log),'OFFLINE'],
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,env=env)
                require(result.returncode!=0,'Producer failure accepted: '+tool+'/'+fault)
                require(b'ACCEPT' not in result.stdout,'Producer failure emitted ACCEPT')
                require(not list(scratch.iterdir()),'Owned scratch not cleaned')
                stats['producer_failures']+=1;stats['cleanup_verified']+=1
                script.unlink()
    return stats

def synthetic():
    stats={'cases':0,'accepted':0,'strict_rejections':0,'oracle_rejections':0}
    def case(name, log, op, wanted=None, **kw):
        p=port(log,op,**kw); o=oracle(log,op,**kw)
        require(not p or o, 'UNSAFE acceptance: '+name+'/'+op)
        if wanted is not None:
            require(p==wanted,'Unexpected port verdict: '+name+'/'+op)
        stats['cases']+=1; stats['accepted']+=int(p)
        stats['strict_rejections']+=int(not p and o)
        stats['oracle_rejections']+=int(not o)
    for op in ('read','quiet','dispatch','guard'):
        case('valid',BASE,op,True)
        case('historical90',A.replace('fps=120(actual=120, group=0x3)','fps=90(actual=90, group=0x5)')+BASE,op,True)
        case('inert-tail',BASE+'[ 5.000000] unrelated ordinary kernel notice\n',op,True)
        mutations={
            'missing-begin':BASE.replace(BR,''),
            'duplicate-begin':BASE+BR,
            'embedded-begin':BASE.replace(B,'prefix'+B),
            'same-line-markers':A+BR.rstrip()+' '+E+'\n',
            'truncated-last-byte':BASE[:-1],
            'nul':BASE+'\x00\n',
            'lost-before': 'LOST\n'+BASE,
            'lost-after': BASE+'LOST\n',
            'failure-before': 'Command transfer failed\n'+BASE,
            'failure-inside': A+BR+'Command transfer failed\n'+ER,
            'tail-mode':BASE+A,
            'tail-transfer':BASE+TX,
            'collision-before':'PWM_P85_WRITE_'+N+'\n'+BASE,
            'collision-after':BASE+'PWM_P85_WRITE_'+N+'\n',
            'malformed-latest':A+'[ 1.500000] dsi_display_set_mode broken\n'+BR+ER,
            'malformed-fps':A+'[ 1.500000] dsi_display_set_mode fps=broken\n'+BR+ER,
            'no-anchor':BR+ER,
            'two-tuples':A.rstrip()+', '+TUPLE+'\n'+BR+ER,
            'conflicting-first-tuple':A.replace(TUPLE,TUPLE.replace('hactive=1440','hactive=1')+' '+TUPLE)+BR+ER,
            'two-mode-tokens':A.replace(PREFIX,PREFIX+'dsi_display_set_mode ')+BR+ER,
            'numeric-clock-suffix':BASE.replace('1234000000','12340000000'),
            'numeric-leading-zero':BASE.replace('hactive=1440','hactive=01440'),
            'field-order':BASE.replace('hactive=1440, vactive=3168','vactive=3168, hactive=1440'),
            'whitespace':BASE.replace('hactive=1440, vactive','hactive=1440,  vactive'),
            'transient-return':A+BR+A.replace('fps=120','fps=90')+A+ER,
            'ambiguous-timestamp':A+'[ 9.000000] '+BR+ER,
            'short-timestamp':BASE.replace('[ 2.000000]','[ 2.0]'),
            'two-transfers':A+BR+TX.rstrip()+' '+TX+ER,
        }
        if op!='guard':
            mutations.update({'missing-end':A+BR,'duplicate-end':BASE+ER,
                'reordered':A+ER+BR,'embedded-end':BASE.replace(E,E+'suffix'),
                'time-reversed':BASE.replace('[ 4.000000]','[ 1.500000]')})
        for name, log in mutations.items():
            case(name,log,op,False)
        case('short-gap',BASE.replace('[ 4.000000]','[ 2.100000]'),op,op!='quiet')
        case('one-microsecond-short',BASE.replace('[ 4.000000]','[ 3.999999]'),op,op!='quiet')
        case('transfer-inside',A+BR+TX+ER,op,op=='read')
    case('actual1-read',BASE.replace('actual=120, group=0x3','actual=1, group=0x8'),'read',True,ref='1')
    case('actual1-quiet',BASE.replace('actual=120, group=0x3','actual=1, group=0x8'),'quiet',True,ref='1')
    for start in ('1.999999','2.000001','7.999999','99999997.999999','999999997.999999'):
        for offset in (-1,0,1):
            micros=int(start.replace('.',''))+2000000+offset
            stop=str(micros//1000000)+'.'+str(micros%1000000).zfill(6)
            case('floating-boundary',BASE.replace('2.000000',start).replace('4.000000',stop),'quiet')
    # Deterministic accepted/rejected mutation cross-product, oracle checked even
    # when no expected verdict is supplied. Never infer equivalence from counts.
    for op in ('read','quiet','dispatch','guard'):
        for prefix in ('',A,'[ 0.000000] inert\n'):
            for spacing in ('[ ','[','[  '):
                for endtime in ('3.999999','4.000000','4.000001','5.000000'):
                    log=(prefix+BASE).replace('[ ',spacing).replace('4.000000',endtime)
                    case('generated',log,op)
    return stats

def saved_sections(raw):
    """Cache-fixture extraction only; NOT a proposed production envelope parser."""
    first,sep,_=raw.partition(b'\n')
    require(sep and re.fullmatch(rb'@P85E:[0-9a-f]{12}:START',first), 'Saved fixture header')
    prefix=first[:-5]; cursor=len(first)+1; sections={}
    while not raw[cursor:].startswith(prefix+b'DONE\n'):
        stop=raw.find(b'\n',cursor); require(stop>=0,'Saved fixture line')
        m=re.fullmatch(re.escape(prefix)+rb'SECTION ([A-Z0-9_]+) 0 ([0-9]+) 0',raw[cursor:stop])
        require(m is not None,'Saved fixture section')
        label=m[1].decode(); n=int(m[2]); cursor=stop+1
        require(label not in sections,'Saved duplicate fixture')
        sections[label]=raw[cursor:cursor+n].decode('ascii'); cursor+=n
        boundary=b'\n'+prefix+b'END '+m[1]+b'\n'
        require(raw[cursor:cursor+len(boundary)]==boundary,'Saved fixture boundary');cursor+=len(boundary)
    require(raw[cursor:]==prefix+b'DONE\n','Saved fixture tail')
    return sections,first.split(b':')[1].decode()

def corpus():
    stats={'snapshots':0,'accepted':0,'strict_rejections':0,'oracle_rejections':0,
           'mutation_cases':0,'mutation_accepted':0,'guard_snapshot_rechecks':0}
    for run in ('01','02','03'):
        root=Path.home()/('.cache/legion-y70-p85-timed-stock/p85_timed_stock_a001_20261108_'+run)
        require(root.is_dir(),'Missing private corpus run '+run)
        files=sorted(root.glob('*envelope-*.stdout'))
        for f in files:
            label=f.name.split('-envelope-',1)[1][:-7]
            if not (label.startswith('quiet-') or label.endswith(('-p85','-c1','-dispatch-gap'))):
                continue
            data,_=saved_sections(f.read_bytes()); log=data['KERNEL']
            marks=re.findall(r'^\[ *[0-9]+\.[0-9]+\] (PWM_P85_[A-Za-z0-9_]+)$',log,re.M)
            require(len(marks)>=2,'Saved marker discovery')
            end=marks[-1]; nonce='-'
            if label.startswith('quiet-'):
                op='quiet'; begin=marks[-2]
                if label.endswith('_PRE'):
                    stage=label[6:-4]
                    write=next(x for x in files if x.name.endswith('-envelope-'+stage+'-write.stdout'))
                    _,nonce=saved_sections(write.read_bytes())
            elif label.endswith('-dispatch-gap'):
                op='dispatch'; stage=label[:-13]
                suffix='_SHAM15_HOLD_BEGIN' if stage=='return15' else '_QUIET_BEGIN_sham15_PRE_0'
                run_prefix=end.rsplit('_'+stage.upper()+'_PRE_DISPATCH',1)[0]
                origins=[m for m in marks if m==run_prefix+suffix]
                require(len(origins)==1,'Protected origin discovery')
                begin=origins[0]
                write=next(x for x in files if x.name.endswith('-envelope-'+stage+'-write.stdout'))
                _,nonce=saved_sections(write.read_bytes())
            else:
                op='read'; begin=marks[-2]
            kw={'begin':begin,'end':end,'nonce':nonce}
            p=port(log,op,**kw); o=oracle(log,op,**kw)
            require(not p or o,'Saved corpus unsafe acceptance')
            stats['snapshots']+=1; stats['accepted']+=int(p)
            stats['strict_rejections']+=int(not p and o); stats['oracle_rejections']+=int(not o)
            # Accepted mutations are checked against combined oracle too.
            variants=[log+'[ 99999.000000] inert tail\n',log.replace('[ ','[  '),
                log+'LOST\n',log+TX,log.replace(begin,'prefix'+begin),
                log.replace(end,end+'suffix'),log+'[ 99999.000000] dsi_display_set_mode broken\n',
                log.replace(begin,begin+' '+begin)]
            if nonce!='-': variants.append('PWM_P85_WRITE_'+nonce+'\n'+log)
            for variant in variants:
                p=port(variant,op,**kw); o=oracle(variant,op,**kw)
                require(not p or o,'Saved mutation unsafe acceptance')
                stats['mutation_cases']+=1;stats['mutation_accepted']+=int(p)
            if op=='dispatch':
                p=port(log,'guard',**kw);o=oracle(log,'guard',**kw)
                require(not p or o,'Saved guard recheck unsafe acceptance')
                stats['guard_snapshot_rechecks']+=1
    require(stats['snapshots']==39,'Unexpected saved corpus coverage')
    return stats

if __name__=='__main__':
    result={'frozen_runtime_files':frozen(),'synthetic':synthetic(),'invocation':invocation_regressions(),
            'python_optimized':bool(sys.flags.optimize),'scope':'OFFLINE ONLY'}
    if '--corpus' in sys.argv: result['saved_corpus']=corpus()
    frozen()
    print(json.dumps(result,sort_keys=True,indent=2))
