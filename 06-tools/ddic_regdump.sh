#!/system/bin/sh
# On-device read-only ILI97701A register dump (runs as root inside `unshare -m`).
# Usage: ddic_regdump.sh PASSES LEN REGFILE PAGE...
# Per register: page select -> one DCS read -> immediate page 0 restore.
# ESD reg_read is simulated as success during the dump and restored on exit.
set -u
T=/data/local/tmp/ddic-regdump
C=$T/dbg/dri/9800000.qcom,mdss_mdp/DSI-1
E=$T/dbg/qcom,mdss_dsi_mot_boe_ili97701A_682_1440x3168_dsc_cmd_v4/esd_check_mode
P0='0x39 0x00 0x00 0x00 0x00 0x00 0x04 0xFF 0x5A 0xA5 0x00'
PASSES=$1 LEN=$2 REGS=$(cat $3)
shift 3

mount -o rprivate none / || exit 10
mount -t debugfs -o nosuid,nodev,noexec debugfs $T/dbg || exit 11
[ -w $C/tx_cmd ] && [ -w $C/rx_cmd ] && [ -w $E ] || { umount $T/dbg; exit 12; }
m=$(cat $E)
case "$m" in reg_read*) ;; *) echo "ESD_UNEXPECTED $m"; umount $T/dbg; exit 13;; esac

restore() {
	echo -n "$P0" > $C/tx_cmd || echo "ERR RESTORE_PAGE"
	echo reg_read > $E || echo "ERR RESTORE_ESD"
	m=$(cat $E)
	echo "ESD_RESTORED $m"
	umount $T/dbg
}
trap restore EXIT
trap "exit 30" HUP INT TERM
echo esd_sw_sim_success > $E || exit 14
echo "BEGIN passes=$PASSES len=$LEN pages=$*"
fails=0

for p in "$@"; do
	pass=1
	while [ $pass -le $PASSES ]; do
		for h in $REGS; do
			ok=0
			if echo -n "0x39 0x00 0x00 0x00 0x00 0x00 0x04 0xFF 0x5A 0xA5 $p" > $C/tx_cmd; then
				echo -n "$LEN 0x06 0x01 0x00 0x01 0x00 0x00 0x01 $h" > $C/rx_cmd && ok=1
			else
				echo "ERR TX $p $h"
			fi
			echo -n "$P0" > $C/tx_cmd || echo "ERR TX0 $p $h"
			if [ $ok = 1 ]; then
				v=$(cat $C/rx_cmd)
				echo "R $pass $p $h $v"
				fails=0
			else
				echo "E $pass $p $h"
				fails=$((fails + 1))
				[ $fails -ge 5 ] && { echo "ABORT consecutive_failures"; exit 20; }
			fi
		done
		pass=$((pass + 1))
	done
done
echo END
