# Independent transfer review — 2026-11-10

**PASS: offline source-bound transfer helper + conditional analyzer consumer, within the documented trusted-caller boundary.** No actual remote transfer, device access, deployment, commit or publication was performed. No new media exists from this review.

## Frozen bytes and tests

All10 entries in FREEZE_TRANSFER.json matched before testing; principal files remained unchanged after testing:
- transfer.py: `f4278fecb36e66a8d9bc9b826955f5c857801effb9aafac6c518549b5b7d66b7`
- analyze.py: `9503205f52a12f8a4c09e96d3203f7e327d79febd62dca0c4e1bb8dfb0f872a7`
- test_transfer.py: `b456f9965de213b4fa41e5818279de0abc5b82fe78c422091138c9c830b8eeee`

Independently executed: **52/52 normal PASS;52/52 optimized(-O) PASS;10/10 existing spectrum PASS.** These are local synthetic streams/media with real OwnedDirectory/PrivateSinkFactory, not a network or actual-video test. The stdlib sender subprocess test uses `python -S` and verifies NumPy is not imported.

## Verified behavior

- Helper/dependency raw bytes are checked against independently supplied exact pins before dependency execution. Preloaded dependency names are rejected. Old AA/P85 acquisition functions are not invoked.
- Sender copies only the named original capsule, its exact four hash-bound JSON records and capture.mp4. Source closure digest, original created inode, media size/hash and source completion/header are bound. Original capsule bytes and source inode claim are not rewritten.
- Receiver creates fresh0700 directory/0600 files and a new bounded private sink. Source inode remains separate from destination created inode; destination reopen must match actual sink identity. Consumer reconstructs stream-header binding and requires original records plus destination receipt, local inode/stat and matching bytes. An ordinary same-byte copy without this chain is rejected.
- Truncation, extra trailing bytes, corruption, wrong helper/source/header, nonzero sender exit, same-byte replacement inode and post-sink-close replacement reject. Existing destinations are not overwritten; no automatic retry or file deletion.
- Both endpoints reject nonfinite deadlines at entry. Sender rejects media exceeding256MiB or inconsistent declared size before hashing. Synchronous checks are not cancellation: external whole-process/transport timeout remains required.
- Stat stability excludes read-induced atime, preserving dev/ino/uid/mode/nlink/size/mtime_ns/ctime_ns and SHA256. Aged-atime regression passes.

## Fixed blocking finding and admission boundary

The previous implementation wrote an apparently finalized receipt before final directory close; an injected close error left a receipt accepted by the old consumer. That defect was independently reproduced.

The corrected receipt says `destination_bytes_verified_receiver_exit_pending` and requires external receiver-exit observation. `analyze_actual` defaults receiver_exit_code to None and accepts only an explicitly supplied integer0, independently observed from the actual receiver process. Missing/nonzero values reject; the exact final-close failure sequence is covered by regression. A pending receipt may remain after failure and must never be treated as completion by its existence alone. Close exceptions are not swallowed or converted into success. Sender exit0 is separately required.

The caller must authenticate the specific source peer, independently pin source/helper identities, enforce process timeouts, observe real sender/receiver process exits, and preserve the no-concurrent-writers/namespace assumptions. Hardcoded success callbacks/codes, copying expected pins from untrusted receipts, or catching receiver exceptions and returning0 invalidate this verdict. Hashes establish byte identity, not truth against a hostile owner/root or fabricated evidence.

## Scientific limits retained

Actual ROI review remains a separate genuine byte-bound review after transfer. Numeric q/ROI/windows/all-ROI5% computation is unchanged. Outputs remain conditional diagnostic only; late first-window controls stay unknown, strict acquisition inconclusive, qualification/candidate flags false, no physical-Hz claim. This software verdict neither authorizes nor proves a new capture or transfer.
