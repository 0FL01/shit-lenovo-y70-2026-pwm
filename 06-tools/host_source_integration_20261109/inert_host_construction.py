"""Inactive explicit dependency construction. No CLI, imports, or automatic I/O.

Requires byte-bound project modules and exact fixed source closure from launcher.
Original source guard runs BEFORE association/adapter/sink construction.
"""
from dataclasses import dataclass

HARDWARE_NAMES=(
'a9_reproduction','capture_ddic_c1','dsi_trial_transaction','p85_single_bit_plan',
'camera_capture_metadata','run_dsi_mode_trial','guarded_adb_socket','stock_c1_sweep',
'p85_guarded_trial','run_p85_guarded_trial','p85_batched_envelope',
'run_p85_batched_trial','run_p85_timed_stock_trial','offline_baseline_adb',
'linux_adb_probe_dependencies','private_video_sink')
BASELINE=tuple('06-tools/'+n+'.py' for n in (
'run_p85_guarded_trial','p85_guarded_trial','stock_c1_sweep','capture_ddic_c1',
'p85_single_bit_plan','dsi_trial_transaction','a9_reproduction',
'camera_capture_metadata','run_dsi_mode_trial','guarded_adb_socket',
'p85_batched_envelope','run_p85_batched_trial','run_p85_timed_stock_trial'))
HARDWARE_PATHS=BASELINE+(
'06-tools/host_adb_full_api_spike/offline_baseline_adb.py',
'06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py',
'06-tools/host_private_sink_20261109/private_video_sink.py',
'06-tools/host_source_integration_20261109/inert_source_loader.py',
'06-tools/host_source_integration_20261109/inert_host_construction.py',
'06-tools/host_source_integration_20261109/fresh_private_directory.py',
'06-tools/host_source_integration_20261109/host_entrypoint.py')
FINALIZER_PATHS=HARDWARE_PATHS+tuple('06-tools/video_validation_split_20261109/'+n+'.py'
                                  for n in ('offline_acceptance','host_evidence'))
VALIDATION_PATHS=tuple('06-tools/video_validation_split_20261109/'+n+'.py'
    for n in ('offline_acceptance','host_evidence','analyzer_join','video_validator_snapshot'))+(
'06-tools/run_p85_guarded_trial.py',
'06-tools/analyze_p85_timed_surrogate.py','06-tools/analyze_p85_optical.py')

class RetainedSink:
    def __init__(self):
        self.attempted=False;self.sink=None;self.created_identity=None
        self.failure_facts=None
    def facts(self):
        return self.sink.facts if self.sink is not None else self.failure_facts

@dataclass
class Construction:
    adapter: object
    association: object
    retained: RetainedSink
    source: dict

def construct(*,modules,root,pin,serials,limits,proc,parent_pin,capacity,
              exact_capture_path,host_uid,os_api,socket_factory,monotonic,sleep):
    # Exact known paths, not caller-supplied arbitrary subset or cleanliness flag.
    source=modules['run_p85_guarded_trial'].source_provenance(
        root=root,paths=HARDWARE_PATHS,require_clean=True)
    if source.get('source_worktree_clean_for_runner') is not True:
        raise RuntimeError('Original source gate did not admit')
    if set(modules)!=set(HARDWARE_NAMES):
        raise RuntimeError('Exact byte-bound hardware modules required')
    if parent_pin.uid!=host_uid:
        raise ValueError('Host owner binding mismatch')
    dep=modules['linux_adb_probe_dependencies']
    sinkmod=modules['private_video_sink']
    association=dep.LinuxAssociation(pin=pin,limits=limits,proc=proc,monotonic=monotonic)
    make_socket=dep.make_socket_factory(socket_factory=socket_factory,monotonic=monotonic)
    retained=RetainedSink()
    def create_sink(path,deadline,*,observed_size):
        if retained.attempted:raise RuntimeError('Sink attempt already spent')
        retained.attempted=True
        if path!=exact_capture_path:raise ValueError('Exact sink destination required')
        factory=sinkmod.PrivateSinkFactory(exact_path=exact_capture_path,
            parent_pin=parent_pin,observed_size=observed_size,capacity=capacity,
            os_api=os_api,monotonic=monotonic)
        try:
            sink=factory(path,deadline)
        except BaseException as error:
            retained.failure_facts=getattr(error,'facts',None)
            raise
        retained.sink=sink
        # Reviewed _Sink.file_meta is the held-created FD tuple, not a reopen stat.
        # Preserve its value now, before caller cleanup closes all owned FDs.
        retained.created_identity=tuple(sink.file_meta)
        return sink
    adapter=modules['offline_baseline_adb'].OfflineBaselineADB(
        expected_process=pin.process,expected_serials=serials,
        acquire=association.acquire_process,make_socket=make_socket,
        create_sink=create_sink,expected_destination=exact_capture_path,
        expected_uid=host_uid,monotonic=monotonic,sleep=sleep)
    return Construction(adapter,association,retained,source)
