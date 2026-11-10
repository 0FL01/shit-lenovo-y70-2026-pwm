# Offline v2 review

Reviewed exact FREEZE_V2.json bytes. Author, independent camera-source reviewer
and execution lead each passed30 tests in normal and optimized Python. The
reviewer additionally simulated exact restoration of original duration, restart
count and filesize-restart switch. No device action occurred in these tests.

Official Open Camera1.56.2 source supports the exact English UI choices for10s,
zero duration restarts and filesize restart OFF. Installed version96/1.56.2 was
separately observed at14:06UTC, but actual settings/UI and cap behavior remain
unverified. Version strings alone do not prove binary/source identity.

Resolved during review: a direct second record() cannot dispatch Start again;
an immediate PREVIEW before advancing recording is not accepted as a stop;
the late-stop helper also requires earlier advancing recording. One Start is
latched before dispatch and no Stop toggle exists. Startup and stop verification
count in the15s acceptance interval. Native10s is asynchronous media-duration
control, not a guarantee of forced wall-time stopping under all failures.

The four v2 windows are fixed before new data: [30,90), [90,150), [150,210),
[210,270). They are adjacent, not independent trials. Original v1 is unchanged.
ROI, q and5% comparison rule are not replaced or relaxed.

This is an offline code checkpoint, not live-ready execution. Source-bound
construction, authentic scene/geometry/current mode revalidation at dispatch,
actual UI/output route, retained sink integration and decoded-media analysis
remain required. No capture, optical result, physical Hz or candidate admission
follows from the synthetic PASS.
