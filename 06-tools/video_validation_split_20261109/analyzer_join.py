"""INACTIVE, read-only admission join. No decode, probe, device or report writes.
External reviewed source expectations are mandatory, never auto-approved here.
Returned view is ephemeral; it is NOT an optical review or candidate admission.
"""
import ast
import copy
from datetime import datetime
import math
from types import SimpleNamespace
import json
import host_evidence as h
from pathlib import Path
HERE=Path(__file__).resolve().parent

ANALYZER_PINS={'analyze_p85_timed_surrogate.py':'aeb2436b1c2e72b9476d676de915bbb18667b83cb6f59a00084816ea116b092f',
              'analyze_p85_optical.py':'60023bb5ff44339efd4db04c96815e869e8edbd3298175a82df98629ca22a3c6'}

def validators():
    texts={name:(HERE.parent/name).read_text() for name in ANALYZER_PINS}
    h.a.check(all(h.sha(text.encode())==ANALYZER_PINS[name] for name,text in texts.items()),'Analyzer source changed')
    common_tree=ast.parse(texts['analyze_p85_optical.py'])
    ns={'datetime':datetime,'math':math}
    names={'OpticalError','require','utc','finite','validate_snapshot'}
    nodes=[n for n in common_tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    nodes += [n for n in common_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('PROFILE','CLEAN_FLAGS') for t in n.targets)]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<pinned-common-validators>','exec'),ns)
    # Exact existing pure session/continuity prefix, before any PTS/window math.
    window=next(n for n in common_tree.body if isinstance(n,ast.FunctionDef) and n.name=='select_windows_from_stages')
    begin=next(i for i,n in enumerate(window.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='snapshots')
    end=next(i for i,n in enumerate(window.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='windows')
    prefix=ast.parse('def validate_session(stages,recording_preflight,binding_frames=2):\n    pass\n').body[0]
    prefix.body=copy.deepcopy(window.body[begin:end])
    # Preserve the existing per-stage observed-count consistency gate as well.
    stage_loop=next(n for n in window.body[end:] if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='stage')
    counts=copy.deepcopy(stage_loop);counts.body=counts.body[:2]
    prefix.body.append(counts)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix],type_ignores=[])),'<pinned-session-prefix>','exec'),ns)
    common=SimpleNamespace(**ns)
    timed_tree=ast.parse(texts['analyze_p85_timed_surrogate.py'])
    timed_nodes=[n for n in timed_tree.body if isinstance(n,ast.FunctionDef) and n.name in ('bounds','validate_run')]
    timed_nodes += [n for n in timed_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('SCOPE','C1_NOT_MEASURED') for t in n.targets)]
    timed={'common':common,'require':ns['require']}
    exec(compile(ast.Module(body=timed_nodes,type_ignores=[]),'<full-pinned-timed-validator>','exec'),timed)
    return timed['validate_run'],ns['validate_session']

def joined_view(acquisition_raw,derived_raw,fd,*,expected_bindings,no_concurrent_writers):
    report=json.loads(acquisition_raw);derived=json.loads(derived_raw)
    h.a.check(report.get('evidence_kind')=='acquisition' and derived.get('evidence_kind')=='acquisition',
              'Synthetic or unknown evidence is not admissible')
    h.a.check(report.get('video_acquisition_schema')=='p85-deferred-acquisition-v1' and
              report.get('video_acquisition_origin')=='timed_stock_caller','Missing acquisition schema/origin')
    h.a.check(derived.get('derived_schema')=='p85-deferred-video-validation-v2','Missing derived schema')
    h.a.check_acquisition(report)
    h.a.check('video_profile' not in report,'Pending acquisition must not carry qualified profile')
    h.a.check(derived.get('status')=='awaiting_optical_review' and derived.get('optical_approval') is False
              and not derived.get('error_type'),'Video validation incomplete')
    h.a.check(derived.get('acquisition_raw_sha256')==h.sha(acquisition_raw) and
              derived.get('acquisition_canonical_sha256')==h.sha(h.canonical(report)),'Derived/report binding mismatch')
    # Expectations must come from a separately reviewed manifest, not these inputs.
    h.a.check(isinstance(expected_bindings,dict) and set(expected_bindings)==
              {'acquisition_commit','acquisition_source_blob_ids','consumer_source_sha256','validator_source_sha256','analyzer_source_sha256','join_source_sha256'},'Incomplete external source expectations')
    expected=expected_bindings['acquisition_source_blob_ids']
    h.a.check(isinstance(expected,dict) and bool(expected) and report.get('source_blob_ids')==expected and
              set(report.get('source_tracked_paths',[]))==set(expected) and
              report.get('source_commit')==expected_bindings['acquisition_commit'],'Acquisition source mismatch')
    h.a.check(derived.get('consumer_source_sha256')==expected_bindings['consumer_source_sha256'] and
              expected_bindings['consumer_source_sha256']==h.consumer_sources(),'Consumer source mismatch')
    h.a.check(derived.get('validator_source_sha256')==expected_bindings['validator_source_sha256'] and
              expected_bindings['validator_source_sha256']==h.a.VALIDATOR_SNAPSHOT_SHA256,'Video validator source mismatch')
    h.a.check(expected_bindings['analyzer_source_sha256']==ANALYZER_PINS and
              expected_bindings['join_source_sha256']==h.sha((HERE/'analyzer_join.py').read_bytes()),'Analyzer/join source mismatch')
    h.a.validator()  # verify actual pinned snapshot bytes, not only advertised digest
    view=copy.deepcopy(report)
    view['status']='awaiting_optical_review';view['video_profile']=copy.deepcopy(derived.get('video_profile'))
    validate_run,validate_session=validators()
    stages=validate_run(view)  # FULL unchanged validator before destination-byte reads.
    validate_session(stages,view.get('recording_preflight',[]))
    # Full later PTS/window/ROI validation remains required before optical conclusions.
    size,digest=h.snapshot(fd,no_concurrent_writers=no_concurrent_writers)
    h.a.check(size==report.get('video_bytes') and digest==derived.get('video_sha256'),'Destination bytes mismatch')
    return view
