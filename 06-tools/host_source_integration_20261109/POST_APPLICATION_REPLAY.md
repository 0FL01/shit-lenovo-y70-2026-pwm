# Post-application replay, inactive only

The e2492c19 freeze and its 86-test discovery suite are PRE-APPLICATION ONLY. They deliberately bind original caller/adapter files and include an assertion that today's expanded checkout is untracked. Do not present that suite as a post-commit suite. Exact e249 and621 files/manifests are retained in historical_e249_621/. The current inactive ABI correction is documented in ABI_COMPATIBILITY.md; no actual runtime or Git edits were made.

## Separate regression route

- `check_future_tree.py`: 52 selected combined/entrypoint tests, using exact intended source bytes, fake OS/socket/proc/time and virtual Git. Omits only the obsolete real-current-untracked assertion from the 53 tests. Production clean-source checks still execute against explicit fake Git in these fixtures, never a claimed actual admission.
- Default mode overlays four immutable intended snapshots; unchanged dependencies are independently hash-checked. `--current` instead reads each of the 22 actual hardware/preverification paths and requires its exact intended hash. No baseline fallback, no launch-time transformation, no reading original runtime paths to reconstruct a patch. Today's unpatched tree fails this mode before the suite.
- `check_future_imports.py`: isolated import-only 19-module intended-byte DAG (22 source inputs), real sys.modules/dataclass and the same precise Path.resolve stub as the earlier import fixture. Default uses intended snapshots; `--current` reads only exact intended current bytes. No instances, entrypoint execution, device services or real source admission.
- `check_replay_contract.py`: six checks including a write-free overlay of all four intended current paths running the 52 tests; corrupt/uncomposed current rejection; immutable baseline independence; corrupt baseline rejection; exact reconstruction of the reviewed four-file diff. The baseline is used only for test comparisons and the explicitly uncomposed negative case. The test runner replaces the fixture's compose function with exact snapshot selection, not a source transformer.

The 3 tracked baseline callers were obtained by read-only `git show` from 0548cf6ba5916c40c6512ef0e2cca332f8e4a4e3 and checked against the previously reviewed original SHA256 pins. The untracked adapter original0177f5de was copied from its independently reviewed exact bytes, NOT from that Git commit. `replay_binding.json` records both origins and all original/intended hashes. Production never imports these readers or reads these snapshots.

## Commands

From repository root, run both normal Python and `python3 -O`:

    PYTHONDONTWRITEBYTECODE=1 python3 06-tools/host_source_integration_20261109/check_future_tree.py
    PYTHONDONTWRITEBYTECODE=1 python3 06-tools/host_source_integration_20261109/check_replay_contract.py
    python3 -I -B 06-tools/host_source_integration_20261109/check_future_imports.py

Only after separately authorized application, the same regression/import commands with `--current` must pass. They verify intended bytes, NOT a tracked clean HEAD. Actual original require_clean admission remains a separate prerequisite, followed by separately authorized platform qualification. No current command applies patches or mutates Git/runtime.

## Exact supporting package

`supporting_test_manifest.json` lists exact hashed paths, separately:

1. The 25 source/data support paths actually consumed by the historical original86, beyond runtime sources. This includes canonical binding/patch, video proposal/lifecycle patch and six AST fixture sources. No whole spike directory.
2. The post-application route's support inputs, including pinned original/intended snapshots and the narrow baseline reader.
3. Documentation/audit artifacts, not runtime dependencies.

QualificationOS is AST-extracted from test_qualify_private_sink.py: this route does not import or run qualify_private_sink.py or its standalone tests. Standalone sink/video/legacy suites and their broader closures are NOT promised by this manifest. Python cache files are not dependencies; use -B/PYTHONDONTWRITEBYTECODE. The runtime source set remains the separately audited26 paths. Private configuration, media, identifiers and the denied13 policy checkpoint are excluded. These lists remain audit inputs, not permission or a publication-ready clean source gate.

Existing fake-I/O coverage limitations remain: the Scenario supplies stage choreography and substitutes baseline Sweep.state; full envelope/DDIC/platform qualification is not proven. The main fake factory and separate real constructor smoke retain their previously documented bounds. Current HEAD/application/commit and hardware work remain untouched and blocked pending their required authorization/admission.
