# Linux association correction: pinned server, not host process stability

2026-11-09, source-only correction after actual preflight06. The current contract
below supersedes the historical visible-leader census description retained below.
Historical source freeze JSON and actual invocation reports remain unchanged.

## Current contract and exact changes

`LinuxAssociation` keeps its constructor and acquire-process tuple bridge. It
checks the independently supplied PID/starttime, four UIDs, executable path and
held executable FD stat/size/SHA-256, server and caller network namespace, exact
IPv4 listener inode/UID and absence of wildcard/IPv6 ambiguity. Two pinned-server
FD possession scans sit between two full identity snapshots, with endpoint and
caller namespace checks at both boundaries. Each identity/FD scan brackets its
reads with the pinned starttime. It does not discover a replacement PID or repin.

No host-wide PID enumeration or unrelated process FD inspection remains. Ordinary
unrelated PID births/exits and even a shared listener holder are outside the new
contract. This is deliberately **not sole-holder proof**, a process census or
atomic TCP-peer authentication. Trusted host/root/kernel/server and snapshot/ABA
race limits remain. Receipt scope is now `pinned_server_fd_table`, with
`unique_holder_qualified=False`. OfflineBaselineADB's acquisition docstring is
updated; its protocol, immutable device binding, fixed endpoint and runtime code
are unchanged. ProcLimits stays constructor-compatible; max_pids is retained but
not used for this contract, while max_total_fds still caps the pinned table.

Required server read failures, missing listener, changed PID/starttime, executable,
UID or namespace remain sticky. No error is diagnosed as benign. Only a typed FileNotFoundError for an individually enumerated server FD link
is omitted; every visited entry still consumes the finite count budget and
deadlines are checked. Positive pinned-listener possession remains mandatory.
Directory/enumeration, required identity and permission failures remain fatal. A failed post-dispatch check
retains dispatched/accepted/uncertain facts and blocks the next operation, even if
the process subsequently appears healthy. No retries, fallback, new-client
continuation or protected producer/receipt execution were added.

## Verification and limits

37 fake-only tests pass under normal Python and -O. Added cases cover ignored
unrelated PID changes/read denial, shared-holder scope, required visibility errors,
second-snapshot UID/netns/exe stat+digest/path/starttime/listener changes, and an
actual OfflineBaselineADB fake-shell flow. The shell success fixture tolerates
unrelated process change. The failure fixture receives two bytes after acceptance,
then invalidates association: completion false, uncertainty true, next operation
blocked with no socket. Existing protocol/device tests remain unchanged.

An attempted broad legacy aggregate did NOT pass: canonical_boot_guard rejects
its old stock-source pin; old sink fixtures lack the already-present observed_size
keyword. Those historical gates were not repinned, bypassed or counted as passes.
Active source-integration manifests and virtual patch fixtures still identify
older sources and require deliberate current-source integration evidence. A broad
runner pass is not claimed by the 37 association tests.

The lead independently reran37 normal/-O successfully and verified the baseline
runtime AST is identical to HEAD after stripping docstrings. Its direct legacy
baseline run had27 tests with7 old pull/sink fixture errors, not27 passes.
Independent reviewer ran the earlier34-test freeze and17 additional fake cases;
final narrow per-FD extension review is tracked separately by the lead. No real /proc, socket, USB-host, ADB or device
operation ran. Actual06 remains accepted root read with uncertain completion,
without PID-delta evidence, current ownership or completed identity. This fix does
not retroactively diagnose benign churn or authorize retry-until-PASS.

## Deployment/provenance consequences

This is a source correction, NOT deployed336 bytes or current hardware admission.
A replacement route needs a separately reviewed exact source closure including
both changed modules, corresponding current source/config bindings and verified
same-buffer deployment/provenance. Preserve historical frozen hashes/evidence;
do not relabel their old successes as new tests. Fresh independently supplied
process/executable/namespace/listener pins remain required, as do original
protocol/device immutable bindings. No prebound stack is made a prerequisite.
The necessary `host_source_integration_20261109/host_entrypoint.py` runtime
pin for the doc-only baseline change was deliberately updated from7f2d60bf to
17b2cc72; the other three pins are unchanged. An AST-only check verified all four
pins against current files. No source deployment or Git writes were performed here.

---

# Historical slice report (superseded contract and hashes)

The following is retained as history only; its all-leader scan, old source hashes,
and original test attestations do not describe the corrected current source.

# Linux acquisition/socket slice: inert source, fake-only validation

2026-11-09. New production-OS-call source implemented, but NO production acquisition, socket connection, host copy/execution or device service performed. Private sink/ffprobe/full runner are not prerequisites for this narrower host-only probe and are not implemented here.

## Files and revised review freeze

- linux_adb_probe_dependencies.py: SHA-256 `e341d0e2a844d03dd0f69ab7604d9defb86865ccd4649875b6670165b3bbcd06`.
- test_linux_adb_probe_dependencies.py: SHA-256 `1cbc37a17251c7aafe639bb73c9f178daedd306d0dff3cc4f40b93abea3289f9`.
- Independent bounded PASS on sourcee341d0e2/tests1cbc37a1:31 tests normal/-O plus4 independent error/scope cases. Earlier27 tests and6 association negatives also passed; raw-error leakage found in the first freeze is fixed. Sanitization verified in exception str/code/formatted traceback, including raw OSError/ValueError/sticky ProbeError inputs.
- Reviewed adapter0177f5de, prior tests9122d8d5 and concrete testsbe331832 unchanged.

Import, construction and direct module execution define objects only. No CLI execution path or output. `inspect_existing_server` is an explicit Python entrypoint and remains separately unadmitted on a real host.

## Interfaces

`VerifiedPin(process, listener_inode, network_namespace, executable_sha256, executable_size)` is mandatory, privately supplied and independently approved. Process includes PID/starttime/executable dev+inode+mode+owner/four UIDs/full version. No PID discovery -> auto-trust, no repin, no executable launch. Version provenance comes from the approved digest manifest, not proc and not running adb.

`ProcLimits(tcp_bytes, stat_bytes, status_bytes, max_pids, max_fds_per_pid, max_total_fds, link_bytes)` is mandatory with positive finite integer ceilings. No silent truncation. Count ceilings are resource limits, not claims of completeness; exceed/read failure/malformed data -> reject. Actual host values have NOT been qualified. Tests use small fixture ceilings, not future production defaults.

`LinuxProcFS(os_api=os, monotonic=...)` implements bounded reads, directory enumeration, links and held executable FD hashing. OS object injection makes every test syscall fake. Real content reads use final O_NOFOLLOW, except intentional /proc/PID/exe magic-link open for hashing; no write/chmod/install/spawn.

`LinuxAssociation(pin, limits, proc, monotonic)` performs checked namespace, IPv4/tcp6 listener scan, complete visible thread-group-leader PID/FD scan, owner/executable checks, then second listener/holder/namespace checks. `association(deadline)` raises sanitized ProbeError. `association.acquire_process(deadline)` is the existing adapter bridge: sticky observed trust failure returns empty tuple, which reviewed adapter makes sticky too. Ordinary deadline errors remain errors, never a trusted identity.

`make_socket_factory(socket_factory=socket.socket, monotonic=...)` returns inert constructor; FD creation only happens on explicit connect. Wrapper fixed numeric127.0.0.1:5037, AF_INET/SOCK_STREAM, non-inheritable, one connect, no fallback/retry. Subsequent settimeout cannot extend initial deadline. send/recv check remaining before and after; underlying receive chunk<=65536, allowing larger caller exact-read loops without allocating unbounded data.

## Source-backed parsing and bounds

Process starttime uses Linux proc_pid_stat field22, parsing after the final ')' of comm; four Uid fields from status. TCP parsing follows Linux proc_net_tcp columns local_address/state/uid/inode; state0A=LISTEN and0100007F:13AD is numeric127.0.0.1:5037 in proc IPv4 representation. Exact approved listener inode/owner is mandatory. Wildcard at the same port and ANY IPv6 listener at that port are conservatively rejected, not interpreted as an alternative.

All visible thread-group-leader process directories are scanned, not just expected PID; all their FD links must be readable. Matching socket inode must have exactly the expected PID/starttime holder. Multiple FDs within the same process are allowed; another process holder is ambiguous. PID-list changes between scans, PID reuse, inaccessible FD/stat/status/exe, byte/count cap or duplicate entries reject. FD symlinks are read while scandir remains open so a scanner's own transient directory FD is still valid; its non-socket directory link cannot be mistaken for the listener.

Executable FD size is pinned; read at most size+1 with64KiB chunks, SHA-256, fstat metadata before/after. Device/inode/mode/owner/size/digest must equal manifest. The source does not invent a new binary identity from observed bytes.

Host protocol bounds reused from reviewed A: version frame16, inventory65535, FAIL4096, strict hex lengths and partial I/O checks. One shared12s self-test budget is based on existing preflight12; it is a configured cap, NOT measured achievable proc-scan latency. General socket timeout validation0<seconds<=600 matches reviewed transport ceiling. Proc limits are separately explicit since protocol caps do not prove suitable proc scan limits.

## Explicit self-test

`inspect_existing_server(association, make_socket, expected_serials, monotonic)` performs:
1. Acquisition before.
2. One host:version query, exact0029.
3. One host:devices-l query, bounded/strict inventory, two independently supplied expected serials ready.
4. Acquisition after.

One deadline12s covers all steps. No bind/selected service, device shell, wait loop, reboot, sync, sink, ffprobe or process spawn. There is no automatic second attempt after errors.

Success returns only protocol41, process_pin_matched, expected_map_matched, elapsed_seconds, device_services_sent=0 and explicit association_scope='visible_thread_group_leader_fd_tables', unique_holder_qualified=False. No raw inventory, serials, endpoint/private pins, executable path, command line, stdout logging or printing. No evidence handle is fabricated: there is no storage API in this narrow slice. Public proc/socket/helper errors are normalized to stable ProbeError.code/string, with no raw callback/OS details or implicit exception-chain display. Sticky invalidation is preserved; KeyboardInterrupt/SystemExit remain interrupts. No private evidence-storage interface is implemented.

## Tested scope and explicit remaining blockers

31 fake-only tests cover listener absence/duplicates/wildcard/IPv6 ambiguity, holder ambiguity, denial, all caps, namespace/PID/owner/path/binary mismatch, changed second snapshot, process-set churn, late matching/mismatching acquisition, adapter sticky bridge, held scanner FD lifetime, low-level bounded OS reads/hash/caps, fixed endpoint, one connect, send/recv/connect delays, no deadline extension, exact two host requests, malformed/missing inventory and after-snapshot failure.

No real `/proc`, sockets, process acquisition, executable hashing, namespaces or signal delivery were exercised. Production OS calls are implementation, not qualification. Synchronous proc/executable reads can block beyond the checked deadline; post-return checks reject late success, but this does not prove mathematical cancellation. Process/socket snapshots have unavoidable races and do not atomically authenticate a TCP peer. Trusted host/root/kernel/server assumption remains explicit.

Completeness is relative to the approved visible proc view. Hidden processes, ancestor PID-namespace holders or restrictive proc mounts can defeat a naive visibility assumption without a read error. Current source binds network namespace, not a proof that its proc view covers every possible listener holder. The scan also omits nonleader task-private FD tables after unshare(CLONE_FILES). It therefore does NOT claim all-thread or universal holder completeness. A separately authorized read-only host observation can report this bounded association honestly under the already explicit trusted USB-host/root/server model; it does not need an impossible proof against trusted malicious root. Eventual runner/mutation qualification must explicitly accept/review this scope or add appropriate task/visibility checks. This is an engineering/trust limit, distinct from permission to make a read-only observation. Actual approved pins, digest/version manifest and explicit host scan ceilings are also absent; fixture pins cannot be deployed.

Full runner source/placement integration remains unavailable. This read-only self-test would neither measure the full trial performance bound nor admit unknown14. Sink and ffprobe are separate later engineering work, not reasons to block reviewing this narrow source slice. Real host observation still needs separate scoped authorization after source review and supplied real pins/limits, with the visible-leader scope disclosed. No full-runner or mutation readiness follows from a successful read-only probe. Protected synthetic receipt/producer remains stopped, spent path untouched; no security change, new service, root/path fallback or Git/runtime edits.

First-review correction: raw factory/OS exceptions could escape despite sanitized success dict. This was a real error-contract defect, now covered by factory/connect/send/recv/close/proc negative tests. Revised code also exposes its bounded association claim in the success object. No namespaces/mounts/security settings were changed to make the claim stronger.

Final review status: no remaining blocker within the narrow visible-leader read-only observation model. Actual OS behavior, hidden/task-private holder coverage and full runner qualification remain unverified. A separate worker has only a read-only bootstrap grant to establish real pins/limits; that grant does not authorize adapter copy/execution, device services, sink creation or a runner trial. No such operations were performed by this source/test work.
