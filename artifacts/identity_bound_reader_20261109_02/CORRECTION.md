# Revision02: public lifecycle reopening blocked

Previous b5e207cd reader/test/report remain unchanged in identity_bound_reader_20261109_01. New readerbaefa4ac13a0f42da8736c2eca0f743361cd0e26daa59190f25efb3bc89fbb8f exposes lifecycle/identity/dependency references through read-only properties backed by slots. Public assignment/deletion cannot reopen terminal state or replace PID/FD/owner/root. Evidence properties return copies/tuples; owned descriptor list is not publicly mutable. Explicit __init__ replay is rejected. This is API misuse protection, not a hostile-Python-interpreter or malicious injected-OS security boundary; deliberate private-attribute/reflection manipulation is outside the claim.

12 fake tests normal/-O pass, including the exact uncertain-close/public-state-reopening counterexample, identity mutation, event snapshot mutation and constructor replay. Uncertain closes are not retried. The original acquired-handle/read/namespace/pidfd/error/cleanup semantics remain unchanged. No live qualification or production change occurred.

## Refined identity and provenance limits

The held reference supports PID-object/process identity under explicit proc-mount/PID-numbering and sole-FD-ownership assumptions, NOT an immutable task_struct or executable. Linux nonleader exec/de_thread can transfer leader PID/starttime identity to another task: https://github.com/torvalds/linux/blob/v6.12/fs/exec.c#L1094-L1111 . Same PID object and sampled starttime therefore cannot establish unchanged executable/thread/FD-table custody. No exec-proof recovery conclusion follows.

readlink(root,'self/ns/pid') equality does not prove that proc superblock numbering equals caller pidfd_open numbering: a proc mount from an ancestor PID namespace can expose the calling task's ns link. RootPin keeps authenticated mount/numbering linkage as an external unmet prerequisite, not a self-approved boolean. No new privileged operation is proposed.

ESRCH from read can arise before proc_single_show through security/notification/filter behavior; buffered seq bytes may survive task exit. This code's pre/post guards remain required but do not turn errno into causal proof. ENOENT/hidepid, EACCES/EPERM and all unknowns remain terminal. The upstream v6.12 reference is not exact host-kernel provenance; saved host facts only establish Linux/x86_64, not release/config. No past failure is relabelled.

An independently reviewed sticky-error integration shim is a separate next artifact; no shim is installed in a production loader. The prior ASSESSMENT.md remains historical, while these narrower identity qualifications govern this revision. Root/target/camera recovery and stock remain HOLD.
