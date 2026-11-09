"""Pure AA acquisition contract. Standard library only; no hardware or media I/O."""
from datetime import datetime
import math
import hashlib
import json
import re

def require(ok,message):
    if not ok: raise ValueError(message)

def finite(value):
    return type(value) in (int,float) and math.isfinite(value)

def utc(value):
    require(isinstance(value,str),"UTC timestamp required")
    parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds()==0,"UTC timezone required")
    return parsed.timestamp()

def bounds(snapshot):
    data = snapshot.get("host_capture_bounds", {})
    start, end = data.get("begin_monotonic"), data.get("end_monotonic")
    require(finite(start) and finite(end) and end >= start,
            "Missing/invalid monotonic camera call bounds")
    require(abs((utc(snapshot.get("host_call_end_utc")) -
                 utc(snapshot.get("host_call_start_utc"))) - (end-start)) < .05,
            "UTC/monotonic camera call disagreement")
    return start, end


SCHEMA = "aa-threshold-optical-v1"
ACQUISITION_SCHEMA = "aa-threshold-acquisition-v1"
SCOPES = ("aa-threshold-stock-surrogate-v1", "aa-threshold-candidate-v1")
HASHES = {"stock":"b5ed66ba69e6221de5fdeaf4d003c9628602d743880acd1c8e2cf7198facd193",
          "aa10":"65846e9320d4a39fd6a677fe9689d08409e80bac050c7cbb1dc12ca276245902"}
SELECTORS = {"23:A9":[14],"24:9D":[14],"00:52":[14,16]}
CLEAN_FLAGS = ("camera_stopped_verified","original_settings_dbv_logger_restored",
               "watchdog_disarmed","mutex_released","explicit_full_stock_return_verified",
               "camera_ui_temp_removed","video_transfer_verified","video_lifecycle_complete",
               "return_hold_and_postselectors_verified","main_trace_removed_verified","chunks_removed_verified")

PROFILE = {"exposure_ns": 100000, "iso": 6400, "focus_diopters": 2.03874850,
           "crop": [0, 0, 4080, 3072], "zoom": 1.0, "ae_mode": "OFF",
           "af_mode": "OFF", "eis_mode": "OFF", "ois_mode": "OFF",
           "capture_intent": "VIDEO_RECORD"}

def validate_snapshot(snapshot):
    require(isinstance(snapshot.get("session_token"),str) and bool(snapshot["session_token"]) and
            type(snapshot.get("encoder_stream_id")) is int and snapshot["encoder_stream_id"]>=0,
            "Typed camera/session identity required")
    require(all(type(snapshot.get(which,{}).get("request_id")) is int and
                snapshot[which]["request_id"]>=0 for which in ("request","result")),
            "Typed camera request identity required")
    require(snapshot.get("recording_verified") is True and snapshot.get("session_token"),
            "Unqualified recording snapshot")
    for which in ("request", "result"):
        values = snapshot.get(which, {})
        for key, expected in PROFILE.items():
            require(values.get(key) == expected, "Camera profile changed: " + which + "." + key)
    result = snapshot["result"]
    require(snapshot.get("rolling_shutter_skew_ns") == 15047630 and
            result.get("rolling_shutter_skew_ns") == 15047630, "Recording geometry/skew changed")
    require(result.get("frame_count") == snapshot.get("frame_count") and
            result.get("timestamp_ns") == snapshot.get("timestamp_ns"), "Inconsistent snapshot counters")
    require(snapshot["request"].get("request_id") == result.get("request_id"),
            "Request/result mismatch")
    for key in ("frame_count", "timestamp_ns"):
        require(isinstance(snapshot.get(key), int) and snapshot[key] > 0, "Invalid camera counter")
    for which in ("request", "result"):
        duration = snapshot[which].get("frame_duration_ns")
        require(finite(duration) and 32_000_000 <= duration <= 35_000_000, "Non-30 fps camera settings")
    encoders = [s for s in snapshot.get("streams", [])
                if s.get("id") == snapshot.get("encoder_stream_id")]
    require(len(encoders) == 1, "Missing/ambiguous encoder stream")
    encoder = encoders[0]
    require((encoder.get("width"), encoder.get("height")) == (1280, 720) and
            encoder.get("consumer_kind") == "GraphicBufferSource" and
            encoder.get("requested") is True and encoder.get("state") == 4,
            "Inactive or changed encoder")
    require(all(isinstance(encoder.get(k), int) and encoder[k] > 0
                for k in ("frames_produced", "last_timestamp_ns")), "Empty encoder snapshot")
    begin, end = utc(snapshot.get("host_call_start_utc")), utc(snapshot.get("host_call_end_utc"))
    elapsed = snapshot.get("host_call_elapsed_seconds")
    require(finite(elapsed) and 0 <= elapsed <= 3 and 0 <= end - begin <= 3 and
            abs(end - begin - elapsed) < .05, "Host clock jump or missing call envelope")
    return encoder


def validate_session(stages,recording_preflight,binding_frames=2):
    snapshots = recording_preflight
    require(isinstance(snapshots, list) and len(snapshots) >= 2, "Missing recording preflight")
    snapshots = snapshots + [s[side] for s in stages for side in ("camera_start", "camera_end")]
    encoders = [validate_snapshot(s) for s in snapshots]
    require(len({s["session_token"] for s in snapshots}) == 1 and
            len({s["encoder_stream_id"] for s in snapshots}) == 1, "Recording session changed")
    offsets = [s["frame_count"] - e["frames_produced"] for s, e in zip(snapshots, encoders)
               if s["timestamp_ns"] == e["last_timestamp_ns"]]
    require(len(offsets) >= 3 and len(set(offsets)) == 1,
            "No unique timestamp-matched camera/encoder count offset")
    offset = offsets[0]
    for previous, current in zip(snapshots, snapshots[1:]):
        require(current["frame_count"] > previous["frame_count"] and
                current["timestamp_ns"] > previous["timestamp_ns"], "Camera snapshots did not advance")
        require(utc(current["host_call_start_utc"]) >= utc(previous["host_call_end_utc"]),
                "Overlapping/reordered host snapshot calls")
        fps = (current["frame_count"] - previous["frame_count"]) * 1e9 / (
            current["timestamp_ns"] - previous["timestamp_ns"])
        require(29.5 < fps < 30.5, "Sensor counter/timestamp cadence changed")
    for snapshot, encoder in zip(snapshots, encoders):
        require(abs(snapshot["frame_count"] - offset - encoder["frames_produced"]) <= binding_frames and
                abs(snapshot["timestamp_ns"] - encoder["last_timestamp_ns"]) <= binding_frames * 35_000_000,
                "Encoder/result discrepancy exceeds declared binding budget")
    for stage in stages:
        require(stage["camera_end"]["frame_count"]-stage["camera_start"]["frame_count"]==
                stage["observed_sensor_frames"],"Stage continuity count disagrees")

def validate_acquisition(run):
    require(isinstance(run,dict) and run.get("schema")==ACQUISITION_SCHEMA and run.get("scope") in SCOPES,
            "Exact AA acquisition schema/scope required")
    require(isinstance(run.get("experiment_id"),str) and
            re.fullmatch(r"[A-Za-z0-9_-]{1,128}",run["experiment_id"]) is not None and
            run.get("evidence_kind")=="acquisition","Missing acquisition identity/kind")
    require(isinstance(run.get("source_commit"),str) and re.fullmatch(r"[0-9a-f]{40}",run["source_commit"]) is not None,
            "Invalid acquisition commit")
    blobs=run.get("source_blob_ids")
    paths=run.get("source_tracked_paths")
    require(isinstance(blobs,dict) and bool(blobs) and
            all(isinstance(k,str) and k and not k.startswith("/") and ".." not in k.split("/") and
                isinstance(v,str) and re.fullmatch(r"[0-9a-f]{40}",v) is not None for k,v in blobs.items()) and
            isinstance(paths,list) and len(paths)==len(blobs) and set(paths)==set(blobs),
            "Incomplete exact source manifest")
    candidate = run["scope"] == SCOPES[1]
    labels = ["baseline","aa10" if candidate else "sham_stock","return_stock"]
    require(run.get("candidate_enabled") is candidate and
            type(run.get("candidate_attempts")) is int and run["candidate_attempts"]==int(candidate) and
            run.get("unknown_value_write_attempted") is candidate and run.get("native_dbv")==3600,
            "Wrong candidate attempts or native context")
    require(run.get("status")=="awaiting_offline_video_validation" and
            run.get("video_validation_status")=="pending_offline" and "video_profile" not in run,
            "Only original pending AA acquisition accepted")
    utc(run.get("finished_at_utc"))
    require(run.get("source_worktree_clean_for_runner") is True,"Unclean acquisition source")
    require(all(run.get(k) is True for k in CLEAN_FLAGS),"Incomplete AA cleanup/return")
    require(not any(run.get(k) for k in ("error","error_type","cleanup_error_type",
            "camera_cleanup_error_type","camera_ui_cleanup_pending","recovery_reboot_attempted",
            "physical_ddic_recovery_unverified")) and run.get("cleanup_errors",[])==[],
            "Failed/recovered run cannot qualify")
    stages=run.get("stages",[])
    require([s.get("label") for s in stages]==labels,"Wrong AA sequence")
    require(run.get("full_table_writes_attempted")==labels,"Repeated/missing full-table attempt")
    entry_count=0
    for i,stage in enumerate(stages):
        name="aa10" if candidate and i==1 else "stock"
        require(stage.get("program_name")==name and stage.get("program_sha256")==HASHES[name],
                "Wrong full program identity/byte delta")
        transaction=stage.get("transaction",{})
        require(all(type(transaction.get(k)) is int and transaction[k]==v for k,v in
                (("chunks_verified",5),("page_callbacks_verified",5),("controller_packets_verified",75))) and
                type(transaction.get("entry_count_after")) is int and transaction["entry_count_after"]>=5,
                "Unqualified full table")
        wire=stage.get("wire",{})
        require(type(wire.get("native_packets_matched")) is int and wire["native_packets_matched"]==75 and
                wire.get("program_sha256")==HASHES[name],"Missing exact wire match")
        for side in ("selectors_before_hold","selectors_after_hold"):
            selectors=stage.get(side,{})
            require(selectors.get("values")==SELECTORS and selectors.get("page_callbacks_verified")==7 and
                    selectors.get("controller_returns")==[0,1,0,0,1,0,0,2,0,0],
                    "Selectors/controller returns not qualified")
        require(transaction["entry_count_after"]==entry_count+5,"Transaction callback count discontinuity")
        entry_count+=5
        replay=stage.get("same_dbv_replay",{})
        require(replay.get("dbv")==3600 and replay.get("exact_wire_verified") is True and
                replay.get("observed_writes")==[{"length":3,"type":57,"mode":"hs","payload":"51 0e 10"}] and
                replay.get("main_trace")=={"page_callbacks_verified":0,"controller_returns":[0],
                                          "entry_count_after":entry_count},
                "Replay was not exact same-DBV packet")
        redraw=stage.get("redraw_audit",{})
        require(redraw.get("method")=="native_timeout_chooser_open_cancel" and
                type(redraw.get("native_dsi_writes")) is int and redraw["native_dsi_writes"]==0 and
                redraw.get("marker_interval_verified") is True,"Missing frame-only redraw audit")
        require(stage["selectors_before_hold"].get("entry_count_after")==entry_count+7,
                "Prehold selector count discontinuity")
        entry_count+=7
        c1=stage.get("c1",{})
        data=c1.get("data")
        require(c1.get("framing_qualified") is True and c1.get("cleanup_verified") is True and
                c1.get("native_dbv")==3600 and c1.get("page")=="23" and c1.get("opcode")=="C1" and
                c1.get("requested")==3 and c1.get("normalized_count")==9 and
                c1.get("scratch_allocation")==16 and c1.get("single_receive") is True and
                isinstance(data,list) and len(data)==3 and all(type(x) is int and 0<=x<=255 for x in data),
                "Missing qualified measured C1 long3")
        trace=c1.get("main_trace",{})
        require(trace.get("page_callbacks_verified")==3 and trace.get("controller_returns")==[0,3,0,0] and
                trace.get("entry_count_after")==entry_count+3 and isinstance(trace.get("background_esd"),list),
                "Missing main C1 trace evidence")
        require(trace["background_esd"]==[],"No background ESD inside C1 operation envelope")
        entry_count+=3
        require(stage["selectors_after_hold"].get("entry_count_after")==entry_count+7,
                "Posthold selector count discontinuity")
        entry_count+=7
        require(name=="aa10" or data==[0,0,96],"Stock C1 differs")
        require(stage.get("qualified") is True and stage.get("hold_seconds")==4.5 and
                type(stage.get("observed_sensor_frames")) is int and stage["observed_sensor_frames"]>=120,
                "Missing full hold")
        markers = stage.get("hold_markers", {})
        require(isinstance(markers.get("begin"), str) and isinstance(markers.get("end"), str)
                and markers["begin"] != markers["end"], "Missing distinct hold markers")
        h0, h1 = stage.get("hold_start_monotonic"), stage.get("hold_end_monotonic")
        require(finite(h0) and finite(h1) and h1 > h0,
                "Missing monotonic hold bounds")
        start0, start1 = bounds(stage.get("camera_start", {}))
        end0, end1 = bounds(stage.get("camera_end", {}))
        require(h0 <= start0 <= start1 <= end0 <= end1 <= h1 and end0-start1 >= 4.5,
                "Camera/end metadata shortened the full optical wait")
        require(abs((utc(stage.get("hold_end_utc")) -
                     utc(stage.get("hold_start_utc"))) - (h1-h0)) < .05,
                "UTC/monotonic hold disagreement")
        offsets = [utc(stage["hold_start_utc"])-h0,
                   utc(stage["hold_end_utc"])-h1,
                   utc(stage["camera_start"]["host_call_start_utc"])-start0,
                   utc(stage["camera_start"]["host_call_end_utc"])-start1,
                   utc(stage["camera_end"]["host_call_start_utc"])-end0,
                   utc(stage["camera_end"]["host_call_end_utc"])-end1]
        require(max(offsets)-min(offsets) < .05,
                "UTC/monotonic offset changed across hold/camera boundaries")
    require(run.get("active_limit_seconds")==37 and run.get("host_limit_seconds")==45 and
            run.get("recovery_reserve_seconds")==8 and run.get("timed_watchdog_seconds")==60 and
            run.get("timed_watchdog_renewals")==0 and
            run.get("candidate_watchdog")=="disarmed_after_verified_return_or_boot" and
            run.get("host_alarm_restored_before_cleanup") is True,"Missing bounded watchdog lifecycle")
    estimate=run.get("prearm_planning_estimate",{})
    phases=estimate.get("observed_baseline_phase_seconds",{})
    phase_keys={"writer_and_quiet","same_dbv_replay","redraw_audit","selectors_before_hold",
                "c1","hold_and_metadata","selectors_after_hold"}
    require(set(phases)==phase_keys and all(finite(x) and x>0 for x in phases.values()),
            "Missing observed full-composition planning phases")
    predicted=2*sum(phases.values())-phases["hold_and_metadata"]-phases["selectors_after_hold"]+3
    require(estimate.get("status")=="observation_not_a_bound" and estimate.get("planning_margin_seconds")==3 and
            finite(estimate.get("estimated_active_seconds")) and
            abs(estimate["estimated_active_seconds"]-predicted)<.01 and predicted<37,
            "Prearm observation does not fit exact37; never a future bound")
    require(run.get("overall_watchdog_seconds")==600 and run.get("overall_watchdog_renewals")==0,
            "Unchanged overall600 watchdog required")
    writes=run.get("writes",[])
    require([w.get("stage") for w in writes]==labels,"Missing exact writer records")
    clock_keys = ("active_start_monotonic", "arm_seconds", "return_qualified_monotonic",
                  "disarm_seconds", "active_G_seconds")
    require(all(finite(run.get(k)) for k in clock_keys), "Missing active-window clock evidence")
    active, arm, returned, disarm, total = [run[k] for k in clock_keys]
    require(active >= 0 and 0 < arm < total < 37 and disarm > 0 and
            returned > active + arm and abs(total-(returned-active+disarm)) < .01,
            "Timed arm/return/disarm interval inconsistent or late")
    for write in writes[1:]:
        keys = ("started_monotonic", "dispatch_monotonic", "validated_monotonic")
        require(all(finite(write.get(k)) for k in keys), "Missing writer timing evidence")
        start, dispatch, validated = [write[k] for k in keys]
        require(active+arm <= start <= dispatch <= validated <= returned,
                "Writer outside verified armed-to-return interval")
    require(stages[0]["hold_end_monotonic"] <= active and
            active+arm <= stages[1]["hold_start_monotonic"] < returned and
            stages[2]["hold_start_monotonic"] >= active+total,
            "Baseline/middle/return holds contradict the active interval")
    middle = stages[1]
    end_camera_begin, end_camera_end = bounds(middle["camera_end"])
    verified = middle.get("hold_verified_monotonic")
    return_started = writes[2].get("started_monotonic")
    require(finite(verified) and finite(return_started) and
            middle["hold_end_monotonic"] >= end_camera_end and
            return_started >= verified >= middle["hold_end_monotonic"],
            "Return DSI started before completed hold verification")
    offsets=[]
    for index,stage in enumerate(stages):
        h0,h1=stage["hold_start_monotonic"],stage["hold_end_monotonic"]
        offsets.extend([utc(stage["hold_start_utc"])-h0,utc(stage["hold_end_utc"])-h1])
        write=writes[index]
        quiet=stage.get("quiet_evidence",{})
        kernel=quiet.get("kernel_marker_bounds",{})
        require(quiet.get("quiet_seconds")==2 and isinstance(quiet.get("begin_marker"),str) and
                isinstance(quiet.get("end_marker"),str) and quiet["begin_marker"]!=quiet["end_marker"] and
                quiet.get("native_state",{}).get("native_actual_hz")==120 and
                quiet.get("native_state",{}).get("native_group")==3 and
                kernel.get("clock")=="target kernel printk monotonic; not host/camera clock" and
                finite(kernel.get("begin_seconds")) and finite(kernel.get("end_seconds")) and
                kernel["end_seconds"]-kernel["begin_seconds"]>=2 and write.get("quiet_evidence")==quiet,
                "Missing exact real2s prewriter quiet")
        pre0,pre1,post=(stage.get(k) for k in ("prehold_started_monotonic",
                            "prehold_qualified_monotonic","postselectors_verified_monotonic"))
        require(all(finite(x) for x in (pre0,pre1,post)) and
                write["validated_monotonic"]<=pre0<=pre1<=h0<h1<=stage["hold_verified_monotonic"]<=post,
                "Prehold/C1/selectors completion timing inconsistent")
        if index==0:require(post<=active,"Baseline postselectors completed after arm")
        if index==1:require(post<=writes[2]["started_monotonic"],"Stock return before middle postselectors")
        if index==2:require(pre1<=returned,"Stock return qualified before C1/selectors completed")

        require(all(finite(write.get(k)) for k in ("started_monotonic","dispatch_monotonic","validated_monotonic")) and
                0<=write["started_monotonic"]<=write["dispatch_monotonic"]<=write["validated_monotonic"]<=h0,
                "Write timing outside own stage")
        require(write.get("program")==stage["program_name"] and write.get("program_sha256")==stage["program_sha256"] and
                write.get("transaction")==stage["transaction"] and write.get("wire")==stage["wire"],
                "Writer/stage evidence mismatch")
    require(max(offsets)-min(offsets)<.05,"Clock offset changed between stages")
    require(writes[0]["validated_monotonic"]<=stages[0]["hold_start_monotonic"]<active and
            writes[1]["validated_monotonic"]<=stages[1]["hold_start_monotonic"] and
            stages[1]["hold_end_monotonic"]<=writes[2]["started_monotonic"] and
            writes[2]["validated_monotonic"]<=returned,"Writer ordering inconsistent")
    require(type(run.get("video_bytes")) is int and run["video_bytes"]>0,"Missing finalized video size")
    for snap in run.get("recording_preflight",[]):
        begin,end=bounds(snap)
        offsets.extend([utc(snap["host_call_start_utc"])-begin,utc(snap["host_call_end_utc"])-end])
    require(max(offsets)-min(offsets)<.05,"Preflight/stage clock offset changed")
    validate_session(stages,run.get("recording_preflight",[]))
    return stages

def validate_run(run):
    # An optical view is a separate derivative. The original report is never rewritten.
    require(run.get("status")=="awaiting_optical_review","Optical join required")
    original=dict(run)
    profile=original.pop("video_profile",{})
    original["status"]="awaiting_offline_video_validation"
    stages=validate_acquisition(original)
    require(profile.get("codec")=="h264" and profile.get("size")==[1280,720] and
            profile.get("audio_streams")==0,"Unqualified original video")
    return stages


QUALIFICATION_SCHEMA="aa-threshold-stock-optical-qualification-v1"
ALGORITHM={"window_frames":60,"edge_seconds":0.25,"snapshot_age_seconds":0.25,
           "binding_frames":2,"spatial_window":"Hann","detrend_degree":2,
           "fine_q_selection":"baseline main ROI only; fixed across stages",
           "normalization":"RMS Y coefficient / (mean Y - 16)",
           "temporal_mean_removed":False}

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def validate_stock_qualification(acquisition,qualification,source):
    """Limited same-version stock diagnostic. Not physical PWM or future timing proof."""
    validate_acquisition(acquisition)
    require(acquisition["scope"]==SCOPES[0],"Stock-only AA acquisition required")
    q=qualification
    require(isinstance(q,dict) and q.get("schema")==QUALIFICATION_SCHEMA and
            q.get("status")=="limited_stock_diagnostic_pass" and
            q.get("acquisition_canonical_sha256")==canonical_sha(acquisition),
            "Stock qualification/acquisition binding mismatch")
    require(q.get("source_commit")==acquisition["source_commit"]==source.get("source_commit") and
            q.get("source_blob_ids")==acquisition["source_blob_ids"]==source.get("source_blob_ids"),
            "Same exact runtime version required")
    require(isinstance(q.get("optical_analysis_sha256"),str) and
            re.fullmatch(r"[0-9a-f]{64}",q["optical_analysis_sha256"]) is not None,
            "Missing frozen optical analysis identity")
    require(q.get("algorithm")==ALGORITHM and q.get("fine_relative_tolerance")==0.05 and
            q.get("mean_y_relative_tolerance")==0.05,"Fixed stock diagnostic changed")
    rois=q.get("rois_xywh",{})
    require(isinstance(rois,dict) and set(rois)=={"main","left","right"},"Three frozen ROIs required")
    for rect in rois.values():
        require(isinstance(rect,list) and len(rect)==4 and all(type(x) is int for x in rect),"Bad frozen ROI")
        x,y,w,h=rect
        require(0<=x<x+w<=1280 and 0<=y<y+h<=720 and w>=20 and h>=300,"Invalid frozen geometry")
    require(len({(r[1],r[3]) for r in rois.values()})==1 and
            all(a[0]+a[2]<=b[0] for a,b in zip(sorted(rois.values()),sorted(rois.values())[1:])),
            "Frozen ROI overlap/vertical mismatch")
    band=q.get("baseline_fine_search_cycles_per_row")
    require(isinstance(band,list) and len(band)==2 and all(finite(x) for x in band) and
            .006<band[0]<band[1]<.1,"Invalid frozen baseline band")
    metrics=q.get("stock_ratios",[])
    require(isinstance(metrics,list) and len(metrics)==6 and
            {(x.get("roi"),x.get("stage")) for x in metrics}==
            {(roi,stage) for roi in rois for stage in ("sham_stock","return_stock")},"Incomplete stock diagnostics")
    for row in metrics:
        require(all(finite(row.get(k)) and abs(row[k]-1)<=.05 for k in
                    ("normalized_fine_over_baseline","mean_y_over_baseline")),
                "Stock fine/mean diagnostic outside fixed5%")
    require(q.get("observed_active_G_seconds")==acquisition["active_G_seconds"] and
            q.get("prearm_planning_estimate")==acquisition["prearm_planning_estimate"],
            "Stock timing evidence mismatch")
    require(q.get("physical_pwm_hz") is None and q.get("full_waveform_equivalence") is None and
            q.get("future_latency_bound") is False and q.get("optical_return_approval") is False and
            q.get("candidate_geometry_rule")=="Use frozen ROI/band; baseline-only geometry review; mismatch is inconclusive, no B-driven reselection",
            "Qualification claims exceed limited diagnostic")
    return q
