#!/system/bin/sh
# SYNTHETIC fixed finite producer. No arguments, files, subprocesses or device IO.
printf '\012\000'
printf 'diagnostic\012\000' >&2
exit 7
