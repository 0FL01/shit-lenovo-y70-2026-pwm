# Capture deployment contract: separate new root only

Never modify or reuse the frozen d5 runtime root as the capture source root.
Create a separate private Git root, proposed:
`/root/legion-y70-stock-capture-dispatch-20261110-01`.
Its HEAD must be the NEW reviewed commit containing every path in
`capture_source_paths.txt`. The root may be a scoped Git deployment, but the
commit/tree/blob objects needed by Git rev-parse must exist and each working file
must match that commit and the independently reviewed SHA manifest. No blanket
repository copy or older commit promotion is necessary.

Existing immutable process config is read, never edited:
`/root/legion-y70-stock-readonly-2a53eb4-20261110-01/config.json`.
The old config contributes only previously pinned process/association/roles and
host evidence-base identity. Its relevant dependency SHA pins must match the new
fixed DAG; its old source commit is not the new code provenance. No repinning from
fresh observations. New output uses a fresh child under that pinned private base.

Create a NEW private0600 capture config under a private0700 parent. Required
shape is shown in `capture_config.template.json`; replace placeholders only from
reviewed source freeze, actual inspected private receipt/image paths and the
lead's actual visual decision. No serials or credentials belong in the public
capture config template. Do not mark a nonexistent screenshot as reviewed.

Source-only check (no device services, no fresh output directory):

    python3 -I /root/legion-y70-stock-capture-dispatch-20261110-01/06-tools/stock_observation_20261110/launch.py --source-root /root/legion-y70-stock-capture-dispatch-20261110-01 --process-config /root/legion-y70-stock-readonly-2a53eb4-20261110-01/config.json --capture-config <NEW_PRIVATE_CAPTURE_CONFIG>

Expected sanitized status: source_config_review_checked, device_services_sent0,
capture_admitted false. This check requires the real visual-review input already
present; no bypass flag or fake receipt is provided. Failure is terminal for that
attempt, not permission for another route.

Only after separate lead execution orchestration and actual readiness may the
same exact command add `--execute-capture`. No execution was performed here.
Source freeze includes the launcher itself; authenticate it before Python -I.
No shell interpolation, custom command strings, private configuration Python,
additional auth, server fallback, automatic recording retry or AA main is used.
