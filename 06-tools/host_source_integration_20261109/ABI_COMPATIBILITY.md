# Narrow legacy pull ABI correction, inactive

The earlier e249/621 intended patch unconditionally passed expected_size/byte_cap to stop_camera's transport. Original GuardedADB.run does not accept those keywords. Its default Trial/Batched pull would fail with TypeError before sync/ffprobe. The earlier adapter-based legacy test did not establish original GuardedADB compatibility. This is a real defect in the proposed bytes, not an actual device execution.

The combined intended caller now has two separate keyword flags:

    stop_camera(*, defer_video_validation=False, bounded_pull=False)

Default bounded_pull=False executes the exact original timeout=90/check=True pull call. The default ffprobe behavior is unchanged. Defer-video alone does not opt into a transport capability. bounded_pull=True sends both expected_size=size and byte_cap=size. The intended timed host execute explicitly passes both defer_video_validation=True and bounded_pull=True. The strict host adapter continues to reject an unbounded pull before sync/sink; it has no legacy fallback. No TypeError is caught to retry a pull, and GuardedADB itself is unchanged.

Tests load the unchanged original GuardedADB class/run implementation through the verified-source fixture and check its exact signature. Only shell/sync are fakes. Default stop_camera calls its original run body, performs exactly one fake sync with timeout90 and continues to fake ffprobe/validation. A separate deferred-only test confirms the flags are independent. Other regressions prove timed-host exact-size/cap forwarding once, strict rejection of omitted metadata, and no second call after a bounded TypeError. The fake shell bridge uses the reviewed fake adapter; no actual legacy socket/sync or device is executed.

Current counts: pre-application discovery90, combined25, entrypoint28; intended-current replay52 (53 less the explicitly pre-application-only real-untracked assertion); six replay contract checks including nested52; isolated intended19 module imports. Run normal and -O. Prior e249/86 and621/48 evidence is preserved exactly in historical_e249_621/, including original manifests and all referenced integration artifacts. Historical84ccb remains untouched.

Changed intended caller hashes and all source expectations are recorded in combined_binding.json/replay_binding.json/runtime_audit_manifest.json. host_entrypoint's required composed byte pins are updated; original require_clean is unchanged. The four-file combined diff remains an offline review/commit prerequisite and is never transformed at production launch. Existing standalone video/proposal and original spike metadata fixtures are immutable historical inputs; only this combined proposal includes the ABI correction.

No actual runtime, Git state, USB host, network endpoint or phone changed. All publication/source-clean/platform/permission blockers remain. Review manifests are audit inputs, not authorization or admission.
