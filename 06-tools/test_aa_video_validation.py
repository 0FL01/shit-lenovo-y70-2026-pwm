"""Offline synthetic AA admission faults. No devices or real video reads."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import aa_acquisition_validation as v
import aa_video_validation as media
import analyze_aa_threshold_trial as optical
from test_analyze_p85_timed_surrogate import fixture as timing_fixture

def fixture(candidate=False):
    old,pts=timing_fixture()
    names=["baseline","aa10" if candidate else "sham_stock","return_stock"]
    run={k:deepcopy(old[k]) for k in (
        "finished_at_utc","recording_preflight","active_start_monotonic","arm_seconds",
        "return_qualified_monotonic","disarm_seconds","active_G_seconds","active_limit_seconds",
        "host_limit_seconds","recovery_reserve_seconds","timed_watchdog_seconds",
        "timed_watchdog_renewals","candidate_watchdog","host_alarm_restored_before_cleanup")}
    run.update(schema=v.ACQUISITION_SCHEMA,scope=v.SCOPES[int(candidate)],
        candidate_enabled=candidate,candidate_attempts=int(candidate),
        unknown_value_write_attempted=candidate,native_dbv=3600,
        status="awaiting_offline_video_validation",video_validation_status="pending_offline",
        full_table_writes_attempted=names,video_bytes=3,experiment_id="synthetic-aa",
        evidence_kind="acquisition",source_worktree_clean_for_runner=True,
        source_commit="a"*40,source_blob_ids={"runner.py":"b"*40},source_tracked_paths=["runner.py"],
        overall_watchdog_seconds=600,overall_watchdog_renewals=0,
        **{k:True for k in v.CLEAN_FLAGS})
    run['before']={'boot_id':'synthetic-boot'}
    run['redraw_ui_calibration']={'contract':v.REDRAW_SCENE_CONTRACT,'source_commit':'a'*40,
        'boot_id':'synthetic-boot','semantic_xml_verified':True,'returned_xml_equals_ready':True,
        'live_text_or_checked_verification':False,'scene_sha256':{'ready':'d'*64,'opened':'e'*64},
        'tap_xy':[720,1583],'fragments':{'ready':'DisplaySettings','opened':'ScreenTimeoutSettings'},
        'components':{'ready':'com.android.settings/.Settings$DisplaySettingsActivity','opened':'com.android.settings/.SubSettings'},
        'audit':{'method':'native_timeout_chooser_open_cancel','native_dsi_writes':0,'marker_interval_verified':True},
        'completed_monotonic':8.}
    phases={k:.1 for k in ("writer_and_quiet","same_dbv_replay","redraw_audit","selectors_before_hold","c1","selectors_after_hold")}
    phases["hold_and_metadata"]=5.4
    run["prearm_planning_estimate"]={"observed_baseline_phase_seconds":phases,
        "estimated_active_seconds":2*sum(phases.values())-5.4-.1+3,"planning_margin_seconds":3.,
        "status":"observation_not_a_bound","redraw_scene_contract":v.REDRAW_SCENE_CONTRACT}
    run["stages"]=[];run["writes"]=[]
    for i,oldstage in enumerate(old["stages"]):
        stage={k:deepcopy(val) for k,val in oldstage.items() if k not in ("p85","c1","return_prequiet","phase_seconds")}
        name="aa10" if candidate and i==1 else "stock"
        stage.update(label=names[i],program_name=name,program_sha256=v.HASHES[name],
            transaction={"chunks_verified":5,"page_callbacks_verified":5,"controller_packets_verified":75,
                         "entry_count_after":5+22*i},
            wire={"native_packets_matched":75,"program_sha256":v.HASHES[name]},
            c1={"framing_qualified":True,"cleanup_verified":True,"native_dbv":3600,
                "page":"23","opcode":"C1","requested":3,"normalized_count":9,"scratch_allocation":16,
                "single_receive":True,"data":[0,0,17 if candidate and i==1 else 96]})
        for side in ("selectors_before_hold","selectors_after_hold"):
            stage[side]={"values":deepcopy(v.SELECTORS),"page_callbacks_verified":7,
                         "controller_returns":[0,1,0,0,1,0,0,2,0,0]}
        stage["same_dbv_replay"]={"dbv":3600,"exact_wire_verified":True,
            "observed_writes":[{"length":3,"type":57,"mode":"hs","payload":"51 0e 10"}],
            "main_trace":{"page_callbacks_verified":0,"controller_returns":[0],"entry_count_after":5+22*i}}
        stage['phase_seconds']=deepcopy(phases)
        stage["redraw_audit"]={"method":"native_timeout_chooser_open_cancel","native_dsi_writes":0,"marker_interval_verified":True,
            "scene_contract":v.REDRAW_SCENE_CONTRACT,"scene_sha256":['d'*64,'e'*64,'d'*64]}
        stage["selectors_before_hold"]["entry_count_after"]=12+22*i
        stage["c1"]["main_trace"]={"page_callbacks_verified":3,"controller_returns":[0,3,0,0],
                                   "entry_count_after":15+22*i,"background_esd":[]}
        stage["selectors_after_hold"]["entry_count_after"]=22+22*i
        stage["hold_verified_monotonic"]=stage["hold_end_monotonic"]+.3
        timing=({"started_monotonic":9.,"dispatch_monotonic":9.1,"validated_monotonic":9.2}
                if i==0 else old["writes"][i-1])
        run["writes"].append({k:timing[k] for k in ("started_monotonic","dispatch_monotonic","validated_monotonic")})
        run["writes"][-1].update(stage=names[i],program=name,program_sha256=v.HASHES[name],
                                transaction=deepcopy(stage["transaction"]),wire=deepcopy(stage["wire"]))
        stage["quiet_evidence"]={"quiet_seconds":2,"begin_marker":names[i]+"_quiet_begin",
            "end_marker":names[i]+"_quiet_end","native_state":{"native_actual_hz":120,"native_group":3},
            "kernel_marker_bounds":{"clock":"target kernel printk monotonic; not host/camera clock",
                                    "begin_seconds":100+i*10,"end_seconds":102+i*10}}
        run["writes"][-1]["quiet_evidence"]=deepcopy(stage["quiet_evidence"])
        stage["prehold_started_monotonic"]=timing["validated_monotonic"]+.01
        stage["prehold_qualified_monotonic"]=timing["validated_monotonic"]+.02
        stage["postselectors_verified_monotonic"]=stage["hold_verified_monotonic"]+.01
        run["stages"].append(stage)
    return run,pts

def optical_view(run):
    return {**deepcopy(run),"status":"awaiting_optical_review",
            "video_profile":{"codec":"h264","size":[1280,720],"audio_streams":0}}

class AcquisitionTests(unittest.TestCase):
    def test_redraw_contract_and_comparable_timing_required(self):
        changes=[lambda r:r.pop('redraw_ui_calibration'),
            lambda r:r['redraw_ui_calibration'].update(semantic_xml_verified=False),
            lambda r:r['redraw_ui_calibration'].update(returned_xml_equals_ready=False),
            lambda r:r['redraw_ui_calibration'].update(live_text_or_checked_verification=True),
            lambda r:r['redraw_ui_calibration'].update(boot_id='other'),
            lambda r:r['redraw_ui_calibration'].update(source_commit='f'*40),
            lambda r:r['redraw_ui_calibration'].update(completed_monotonic=100),
            lambda r:r['redraw_ui_calibration']['scene_sha256'].update(opened='d'*64),
            lambda r:r['stages'][1]['redraw_audit'].update(scene_sha256=['d'*64]*3),
            lambda r:r['prearm_planning_estimate'].pop('redraw_scene_contract'),
            lambda r:r['stages'][0]['phase_seconds'].update(redraw_audit=.001)]
        for change in changes:
            with self.subTest(change=change):
                run,_=fixture();change(run)
                with self.assertRaises(ValueError):v.validate_acquisition(run)
    def test_stock_and_candidate(self):
        for candidate in (False,True):
            run,pts=fixture(candidate)
            self.assertEqual(len(v.validate_acquisition(run)),3)
            self.assertEqual(len(optical.select_windows(optical_view(run),pts)),3)
    def test_faults_reject_before_window_helper(self):
        mutations=[
            lambda r:r["stages"].reverse(),
            lambda r:r["stages"][1].update(program_sha256="f"*64),
            lambda r:r["stages"][1]["wire"].update(native_packets_matched=74),
            lambda r:r["stages"][1]["transaction"].update(controller_packets_verified=74),
            lambda r:r["stages"][1]["selectors_after_hold"]["controller_returns"].__setitem__(1,0),
            lambda r:r["stages"][1].pop("c1"),
            lambda r:r["stages"][1]["c1"].update(normalized_count=8),
            lambda r:r["stages"][2]["c1"].update(data=[0,0,17]),
            lambda r:r.update(camera_stopped_verified=False),
            lambda r:r.update(error_type="TimeoutError"),
            lambda r:r.update(recovery_reboot_attempted=True),
            lambda r:r.update(active_G_seconds=37),
            lambda r:r.update(candidate_attempts=2),
            lambda r:r["full_table_writes_attempted"].append("aa10"),
            lambda r:r["stages"][1].update(hold_end_monotonic=26.),
            lambda r:r["stages"][1]["camera_start"]["host_capture_bounds"].update(begin_monotonic=2.),
            lambda r:r["writes"][2].update(started_monotonic=24.),
            lambda r:r["writes"][0].update(program_sha256="0"*64),
        ]
        for change in mutations:
            with self.subTest(change=change):
                run,pts=fixture(True);change(run)
                with patch.object(optical.common,"select_windows_from_stages") as helper:
                    with self.assertRaises((ValueError,KeyError,TypeError)):
                        optical.select_windows(optical_view(run),pts)
                    helper.assert_not_called()
    def test_runtime_composition_faults(self):
        mutations=[
            lambda r:r["stages"][1]["same_dbv_replay"]["observed_writes"][0].update(payload="51 0e 11"),
            lambda r:r["stages"][1]["same_dbv_replay"]["main_trace"].update(controller_returns=[1]),
            lambda r:r["stages"][1]["redraw_audit"].update(native_dsi_writes=1),
            lambda r:r["stages"][1]["c1"]["main_trace"].update(controller_returns=[0,2,0,0]),
            lambda r:r["stages"][1]["c1"]["main_trace"].update(entry_count_after=36),
            lambda r:r["stages"][1]["selectors_after_hold"].update(entry_count_after=43),
            lambda r:r.update(return_hold_and_postselectors_verified=False),
            lambda r:r.update(main_trace_removed_verified=False),
            lambda r:r["prearm_planning_estimate"].update(estimated_active_seconds=38),
            lambda r:r["prearm_planning_estimate"].update(planning_margin_seconds=0),
            lambda r:r["recording_preflight"][0].update(session_token="other"),
            lambda r:r["stages"][1]["camera_end"]["result"].update(iso=100),
            lambda r:r["stages"][1].update(observed_sensor_frames=151),
            lambda r:r.update(source_worktree_clean_for_runner=False),
        ]
        for change in mutations:
            with self.subTest(change=change):
                run,_=fixture(True);change(run)
                with self.assertRaises((ValueError,KeyError,TypeError)):v.validate_acquisition(run)
    def test_cross_stage_clock_shift(self):
        from datetime import datetime,timedelta
        run,_=fixture()
        stage=run["stages"][1]
        for key in ("hold_start_utc","hold_end_utc"):
            stage[key]=(datetime.fromisoformat(stage[key])+timedelta(seconds=1)).isoformat()
        for key in ("camera_start","camera_end"):
            for stamp in ("host_call_start_utc","host_call_end_utc"):
                stage[key][stamp]=(datetime.fromisoformat(stage[key][stamp])+timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError,"Clock offset"):v.validate_acquisition(run)
    def test_descriptive_candidate_compares_both_stock_controls(self):
        findings={"measurements":[]}
        for roi in ("main","left","right"):
            for stage,value in (("baseline",[4.,8.]),("aa10",[1.,2.]),("return_stock",[2.,4.])):
                findings["measurements"].append({"roi":roi,"stage":stage,
                    "degrees":{d:{"normalized_rms":value} for d in ("None","1","2","3")}})
        contrasts=optical.aa_contrasts(findings)
        self.assertEqual(len(contrasts),12)
        self.assertEqual(contrasts[0]["over_baseline"],[.25,.25])
        self.assertEqual(contrasts[0]["over_return_stock"],[.5,.5])
    def test_identity_and_session_faults(self):
        mutations=[
            lambda r:r.pop("experiment_id"),lambda r:r.pop("source_commit"),
            lambda r:r.update(source_tracked_paths=[]),lambda r:r.update(evidence_kind="unknown"),
            lambda r:r["recording_preflight"][0].pop("host_capture_bounds"),
            lambda r:r["recording_preflight"][0].update(session_token=True),
            lambda r:[r["recording_preflight"][0][side].pop("request_id") for side in ("request","result")],
        ]
        for change in mutations:
            run,_=fixture();change(run)
            with self.assertRaises((ValueError,KeyError,TypeError)):v.validate_acquisition(run)
    def test_prehold_quiet_and_cleanup_faults(self):
        mutations=[
            lambda r:r["stages"][2].update(prehold_qualified_monotonic=28.),
            lambda r:r["stages"][1].update(postselectors_verified_monotonic=27.),
            lambda r:r["stages"][1]["quiet_evidence"]["kernel_marker_bounds"].update(end_seconds=111.),
            lambda r:r["stages"][1]["c1"]["main_trace"].update(background_esd=[{"return_code":1}]),
            lambda r:r.update(overall_watchdog_seconds=601),
            lambda r:r.update(overall_watchdog_renewals=1),
            lambda r:r.update(chunks_removed_verified=False),
        ]
        for change in mutations:
            run,_=fixture();change(run)
            with self.assertRaises((ValueError,KeyError,TypeError)):v.validate_acquisition(run)
    def test_frozen_stock_qualification(self):
        run,_=fixture();raw=media.canonical(run)
        measurements=[]
        for roi in ("main","left","right"):
            for stage in ("baseline","sham_stock","return_stock"):
                measurements.append({"roi":roi,"stage":stage,"degrees":{"2":{
                    "normalized_rms":[.1,.1,.1,.1,.1],"mean_y":100.}}})
        analysis={"schema":v.SCHEMA,"scope":v.SCOPES[0],"mode":"analysis",
            "source_acquisition_sha256":media.sha(raw),"source_video_bytes":3,
            "timing_assumptions":{"snapshot_max_age_seconds":.25,"encoder_binding_ambiguity_frames":2,
                "minimum_edge_margin_seconds":.25},"windows":[{"encoded_frames":60}]*3,
            "measurements":measurements,"rois_xywh":{"left":[100,100,30,330],"main":[150,100,30,330],
                "right":[200,100,30,330]},"baseline_fine_search_cycles_per_row":[.015,.025]}
        q=optical.stock_qualification(raw,media.canonical(analysis))
        self.assertEqual(v.validate_stock_qualification(run,q,run),q)
        for key,value in (("source_commit","d"*40),("fine_relative_tolerance",.1),
                          ("physical_pwm_hz",2160),("future_latency_bound",True),
                          ("acquisition_canonical_sha256","f"*64)):
            bad=deepcopy(q);bad[key]=value
            with self.assertRaises(ValueError):v.validate_stock_qualification(run,bad,run)
        q["stock_ratios"][0]["normalized_fine_over_baseline"]=1.051
        with self.assertRaises(ValueError):v.validate_stock_qualification(run,q,run)
        analysis["measurements"][1]["degrees"]["2"]["normalized_rms"][2]=.11
        with self.assertRaises(ValueError):optical.stock_qualification(raw,media.canonical(analysis))
    def test_candidate_geometry_never_reselected(self):
        q={"rois_xywh":{"main":[100,100,30,330]},"baseline_fine_search_cycles_per_row":[.015,.025]}
        review={**deepcopy(q),"baseline_geometry_verified":True,"fixed_geometry_verified":True,
                "flat_screen_content_verified":True}
        self.assertTrue(optical.frozen_candidate_geometry(q,review))
        review["rois_xywh"]["main"][0]+=1
        self.assertFalse(optical.frozen_candidate_geometry(q,review))
        review=deepcopy(q);review["baseline_geometry_verified"]=False
        self.assertFalse(optical.frozen_candidate_geometry(q,review))
    def test_schema_not_aliased(self):
        run,_=timing_fixture()
        with self.assertRaises(ValueError):v.validate_acquisition(run)
    def test_fresh_roi_schema(self):
        with self.assertRaises(ValueError):
            optical.validate_review({"schema":"p85-optical-roi-review-v1"},
                run_sha256="x",video_bytes=3,frame_count=1800,windows=[])

class VideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"video"
        self.path.write_bytes(b"abc");self.path.chmod(0o600)
        self.fd=os.open(self.path,os.O_RDONLY)
        self.report,_=fixture();self.raw=media.canonical(self.report)
        st=os.fstat(self.fd)
        self.source=media.source_evidence(self.raw,self.fd,{"created":True,"confirmed_written":3,
            "write_outcome_uncertain":False,"close_outcome":"closed","removed_by_sink":False},
            expected_source_identity=(st.st_dev,st.st_ino,st.st_uid,st.st_mode),no_concurrent_writers=True)
        self.receipt=media.destination_receipt(self.raw,self.source,self.fd,no_concurrent_writers=True)
        self.probe=Mock(return_value=SimpleNamespace(stdout=json.dumps({"streams":[{
            "codec_type":"video","codec_name":"h264","width":1280,"height":720,"avg_frame_rate":"30/1"}],
            "format":{"duration":"20"}}).encode()))
    def tearDown(self):
        os.close(self.fd);self.tmp.cleanup()
    def test_receipt_accept_and_join_preserve_original(self):
        original=deepcopy(self.report)
        result=media.accept(self.report,self.fd,self.receipt,run=self.probe)
        self.assertEqual(result["status"],"awaiting_optical_review")
        result.update(derived_schema="aa-threshold-video-validation-v1",optical_approval=False,
            acquisition_raw_sha256=media.sha(self.raw),evidence_kind="acquisition",
            consumer_source_sha256=media.consumer_sources())
        pins={"acquisition_commit":self.report["source_commit"],
            "acquisition_source_blob_ids":self.report["source_blob_ids"],
            "consumer_source_sha256":media.consumer_sources(),
            "validator_source_sha256":media.VALIDATOR_SNAPSHOT_SHA256}
        view=media.joined_view(self.raw,media.canonical(result),self.fd,
            expected_bindings=pins,no_concurrent_writers=True)
        self.assertEqual(view["status"],"awaiting_optical_review")
        self.assertEqual(self.report,original)
        pins["acquisition_commit"]="c"*40
        with self.assertRaises(RuntimeError):
            media.joined_view(self.raw,media.canonical(result),self.fd,expected_bindings=pins,
                              no_concurrent_writers=True)
    def test_consume_exclusive_private_artifacts(self):
        directory=Path(self.tmp.name)/"result";directory.mkdir(mode=0o700)
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
        try:
            result=media.consume(self.raw,self.fd,self.receipt,fd,no_concurrent_writers=True,run=self.probe)
            self.assertEqual(result["status"],"awaiting_optical_review")
            self.assertEqual((directory/"acquisition.json").read_bytes(),self.raw)
            self.assertEqual(result["derived_schema"],"aa-threshold-video-validation-v1")
            self.assertFalse(result["optical_approval"])
            with self.assertRaises(FileExistsError):
                media.consume(self.raw,self.fd,self.receipt,fd,no_concurrent_writers=True,run=self.probe)
        finally:os.close(fd)
    def test_probe_change_detected(self):
        original=self.probe
        def mutate(*args,**kwargs):
            result=original(*args,**kwargs);self.path.write_bytes(b"abd");return result
        self.assertEqual(media.accept(self.report,self.fd,self.receipt,run=mutate)["status"],"failed")
    def test_bad_receipt_and_cleanup_before_probe(self):
        for key,value in (("source_sha256","f"*64),("run_id","other"),
                          ("acquisition_canonical_sha256","f"*64),("schema","p85")):
            self.probe.reset_mock()
            result=media.accept(self.report,self.fd,{**self.receipt,key:value},run=self.probe)
            self.assertEqual(result["status"],"failed");self.probe.assert_not_called()
        self.report["watchdog_disarmed"]=False
        self.assertEqual(media.accept(self.report,self.fd,self.receipt,run=self.probe)["status"],"failed")
    def test_cli_requires_verified_join_before_probe(self):
        root=Path(self.tmp.name)
        acq=root/"acq.json";derived=root/"derived.json";pinsfile=root/"pins.json"
        acq.write_bytes(self.raw)
        result=media.accept(self.report,self.fd,self.receipt,run=self.probe)
        result.update(derived_schema="aa-threshold-video-validation-v1",optical_approval=False,
            acquisition_raw_sha256=media.sha(self.raw),evidence_kind="acquisition",
            consumer_source_sha256=media.consumer_sources())
        derived.write_bytes(media.canonical(result))
        pins={"acquisition_commit":self.report["source_commit"],
            "acquisition_source_blob_ids":self.report["source_blob_ids"],
            "consumer_source_sha256":media.consumer_sources(),
            "validator_source_sha256":media.VALIDATOR_SNAPSHOT_SHA256}
        pinsfile.write_bytes(media.canonical(pins))
        args=[str(acq),str(self.path),"--derived",str(derived),"--source-bindings",str(pinsfile),
              "--no-concurrent-writers","--plan","--output",str(root/"plan.json")]
        _,pts=fixture()
        probe={"streams":[{"codec_type":"video","codec_name":"h264","width":1280,"height":720,
                           "pix_fmt":"yuv420p","color_range":"tv","nb_frames":str(len(pts))}],
               "frames":[{"best_effort_timestamp_time":str(x)} for x in pts]}
        with patch.object(optical.common,"probe_video",return_value=probe):
            optical.main(args)
        plan=json.loads((root/"plan.json").read_bytes())
        self.assertEqual(plan["source_video_sha256"],media.sha(b"abc"))
        self.path.write_bytes(b"abd")
        args[-1]=str(root/"bad.json")
        with patch.object(optical.common,"probe_video") as before:
            with self.assertRaises(RuntimeError):optical.main(args)
            before.assert_not_called()
    def test_receipt_requires_finite_trusted_facts(self):
        for key in ("trusted_no_concurrent_writers","acquisition_raw_sha256","sink_facts","source_identity"):
            receipt=deepcopy(self.receipt);receipt.pop(key)
            self.probe.reset_mock()
            self.assertEqual(media.accept(self.report,self.fd,receipt,run=self.probe)["status"],"failed")
            self.probe.assert_not_called()
            source=deepcopy(self.source);source.pop(key)
            with self.assertRaises(RuntimeError):
                media.destination_receipt(self.raw,source,self.fd,no_concurrent_writers=True)
    def test_pending_source_missing_finalization_rejected(self):
        with self.assertRaises(RuntimeError):
            media.source_evidence(self.raw,self.fd,{"created":True},expected_source_identity=None,
                                  no_concurrent_writers=True)
    def test_destination_changed(self):
        self.path.write_bytes(b"abd")
        with self.assertRaises(RuntimeError):
            media.destination_receipt(self.raw,self.source,self.fd,no_concurrent_writers=True)
    def test_readwrite_fd_rejected(self):
        fd=os.open(self.path,os.O_RDWR)
        try:
            with self.assertRaises(RuntimeError):
                media.destination_receipt(self.raw,self.source,fd,no_concurrent_writers=True)
        finally:os.close(fd)

if __name__=="__main__":unittest.main()
