# One-shot read-only host wrapper

`deploy_readonly.py` is public reviewable code, not executed as part of its
implementation/tests. It contains no SSH route, ADB CLI, device write, full-trial
import, retry, repair, removal or fallback. Its own bytes must be independently
authenticated by the operator before use with a trusted Python interpreter.
The existing reviewed launch.py/probe.py bytes stay unchanged.

Private JSON arrives on stdin. The wrapper accepts exactly the supplied typed
payload contract: base path/pin, frozen code name/pin, new directory name,
config_without_evidence, and the two UTF-8 source files with SHA256. It checks
both supplied and computed file digests against public fixed reviewed constants.
It verifies the exact frozen dependency commit/source pins and validates config
through the already byte-verified inert launch parser. Unknown keys, duplicate
keys, wrong types/pins/hashes or >65536-byte payload reject before host writes.
No payload/cache/old private script is discovered or read by this wrapper.

The fixed destination is a new directory under the independently pinned root
directory. Existing destinations are terminal collisions: no adoption or retry.
Host changes are limited to exclusive 0700 directory creation and exclusive 0600
files: launch.py, probe.py, config.json, begin.json, outcome.json, plus the private
evidence subdirectory used by the observer. No chmod, overwrites or deletion.
Exact root/frozen-code/created-directory identity and namespace-edge checks run
before children; read-only results recheck pinned directories before acceptance.
Trusted root/UID/kernel/filesystem and no concurrent namespace mutation remain
assumptions, not a newly claimed race-proof security boundary.

Default mode creates the new host files and runs **source-only validation**.
Adding the one accepted flag `--execute-read-only` runs source-only validation
first and the pinned observer second, in that same invocation. A completed
default run cannot be resumed with the flag: its directory now exists and must
not be reused. The operator must choose the desired one-shot mode beforehand.
No flag selects full trial/setup/capture. Device observations remain partial,
non-atomic snapshots with false setup/acquisition admission and unknown PWM Hz.

Children use fixed `/usr/bin/python3 -I -B` argv, no shell, no inherited stdin,
captured stdout and discarded stderr. Source-only child must return its exact
zero-device-service schema before the observer can start. The observer response
passes a second typed summary allowlist; arbitrary fields/identifiers are not
forwarded. Exit/parse/timeout failures never print raw output or exceptions.
Source-only timeout and any failure after attempting the read-only child are
reported `uncertain`, with no retry. Files already created are retained.

The authoritative completion marker is the single JSON stdout object AND process
exit status. Outcomes: `source_only_validated`, `read_only_observed`, `failed`,
`uncertain`. Only the first two yield exit0. `host_cleanup_verified` must be true
for a successful complete wrapper return. UTC begin/end are retained overall and
for both child phases. Private outcome.json records the result before directory
descriptor cleanup and therefore deliberately has `host_cleanup_verified:false`;
its `receipt_phase` is `before_descriptor_close`, while final stdout says `final`.
it must not override a later failing/uncertain stdout marker or interrupted run.
No output receipt exists before successful destination creation. File-write or
descriptor-close uncertainty fails the overall result without trying another path.

Offline tests use temporary host directories, synthetic private pins/config,
the public reviewed source bytes, and a fake child runner. They never launch SSH,
ADB, the observer against devices, or a real deployment subprocess.

    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s 06-tools/stock_observation_readonly_20261110 -p test_deploy_readonly.py -q
    PYTHONDONTWRITEBYTECODE=1 python3 -O -m unittest discover -s 06-tools/stock_observation_readonly_20261110 -p test_deploy_readonly.py -q
