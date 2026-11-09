# Independent pinned-server guard review

2026-11-09. Verdict: bounded offline PASS within the narrowed trusted-host contract. No USB-host proc/socket/ADB/device action, runtime deployment or Git write was performed by this reviewer. This report alone does not admit a live experiment.

## Exact reviewed SHA-256 identities

- `06-tools/host_adb_full_api_spike/linux_adb_probe_dependencies.py`: `9ff5e7ea212d46961c4a74757acc5d50b9d666aa47f9f4e1c58722845bfd53d9`.
- `06-tools/host_adb_full_api_spike/test_linux_adb_probe_dependencies.py`: `528f6d9fb530591841f9a4b1991f130d94e39023850ca0aba1ebd7821d28d0c0`.
- `06-tools/host_adb_full_api_spike/offline_baseline_adb.py`: `17b2cc726497e95e16414192c808fb3eed64cbe64ed87fba39710685a818cf51`. Only its acquisition-contract class docstring changes; executable behavior is unchanged.
- `06-tools/host_source_integration_20261109/host_entrypoint.py`: `652a0ee2d774e172e91adf530bc086a79d3d65f9941b798150c7432ff532264a`. Independently verified byte-for-byte against HEAD: exactly one replacement of baseline runtime pin `7f2d60bffcf4e74fc4060941a6a8444ee6bb052ae24a07d23407aaef0ce0585e` with the reviewed baseline hash above. Other three runtime pins unchanged; all four match current source bytes.

## Independent tests

- Final Linux dependency suite: 37 tests PASS normally and with Python `-O`; all OS/proc/socket inputs fake, bytecode writes disabled.
- Seventeen independent fake-only cases passed on intermediate Linux source `fa2d5e15ef4040811d96b49e7f22c3f0eb56f582c5114f6f78a7c122372de151`: unrelated denied proc census/shared holder ignored; ten required-read failures sticky/no later I/O; mid-scan inode, UID, server namespace, PID and listener changes rejected; duplicate matching server FDs accepted. These standalone cases were not rerun after the final FD handling change.
- Six additional independent cases passed on final source: EACCES/EPERM/EIO/ENOTDIR remain sticky; late individual-FD ENOENT rejects at deadline; optional vanished FD succeeds only with a positively observed pinned listener.
- Final suite covers vanished sole listener/all FDs, caps counting skipped entries, fatal directory errors, immutable device aliases and post-dispatch failure retaining accepted/dispatched, two received bytes, uncertain completion and sticky invalidation with no next socket.

## Invariant and residual limits

Checks now target the independently pinned server: PID/starttime brackets, UIDs, executable path and held-file metadata/digest, server/self network namespaces, exact accepted IPv4 endpoint/listener inode, absence of competing accepted IPv6 listener, and positive pinned-process listener possession. Repeated snapshots detect persistent changes. Fixed endpoint, protocol and immutable serial-selected service binding are unchanged.

Only FileNotFoundError from an individual enumerated FD readlink may be omitted. Every visited entry consumes the count limit and omission is followed by a deadline check. Directory/enumeration errors, required stat/namespace/executable/listener-table reads, permissions and other errors are not exempt. Missing listener still fails. No discovery/repin, retry loop, fallback or security change was added.

This does not prove exclusive ownership, all-task visibility, hostile-root resistance or atomic TCP-peer authentication. Shared/inherited listener holders and transient ABA changes remain trusted-host boundaries. Synchronous OS reads have checked deadlines, not guaranteed cancellation. These limits do not establish a requirement for global census or universal independent recovery.

Actual preflight06 remains failed with uncertain completion after the accepted root read. No saved PID delta proves a benign cause or server replacement. No stock/settings/capture/DSI operation followed. Its failed adapter and receipt must not be revived or relabeled successful.

## Source gate and integration

Runtime pin mapping is independently verified. Route worker reports normal/-O PASS of original source_gate/source_provenance using current bytes and fake Git, including rejection of the old baseline runtime pin; see `artifacts/pinned_server_route_20261109_01/check_current_source_gate.py`. This is not true clean-Git admission.

Original clean-source admission remains pending publication of the reviewed changes and fresh replay. Dirty-worktree rejection is expected, not a regression to bypass. Historical freezes/pre-patch virtual fixture aggregates are not silently refreshed or claimed passing; the author reported legacy aggregate failures. No full integration or live qualification PASS is asserted. Fresh execution must preserve the original source gate and identity checks, use a new adapter and independently supplied real pins.
