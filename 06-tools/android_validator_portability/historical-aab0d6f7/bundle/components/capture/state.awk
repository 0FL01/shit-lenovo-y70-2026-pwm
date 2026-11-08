# OFFLINE semantic fragment over already bounded/provenance-checked files.
# ARGV: FIELDS DISPLAY BOOT OWNER ESD; caller must set LC_ALL=C and supply the
# raw trusted P85_OFFLINE_EXPECTED_BOOT environment value (never awk -v).
# Supported identity dialect: 1..128 visible ASCII bytes, no whitespace.
BEGIN {expected_boot=ENVIRON["P85_OFFLINE_EXPECTED_BOOT"];if(ARGC!=6||length(expected_boot)<1||length(expected_boot)>128||expected_boot!~/^[!-~]+$/)bad=1;split("3600 0 0 Enforcing",want," ")}
FILENAME==ARGV[1] {fields++;if(fields>4||("text:" $0)!=("text:" want[fields]))bad=1;next}
FILENAME==ARGV[2] {
 if(index($0,"mActiveSfDisplayMode=")){
  display++;s=$0;sub(/^.*mActiveSfDisplayMode=/,"",s)
  if(s!~/peakRefreshRate=[0-9]+\.[0-9]+/)bad=1
  sub(/^.*peakRefreshRate=/,"",s);sub(/[^0-9.].*$/,"",s)
  if(s!~/^[0-9]+\.[0-9]+$/||s-120>=.03||120-s>=.03)bad=1
 }
 next
}
FILENAME==ARGV[3] {boot++;if(("text:" $0)!=("text:" expected_boot))bad=1;next}
FILENAME==ARGV[4] {bad=1;next}
FILENAME==ARGV[5] {esd++;if($0!="reg_read")bad=1;next}
END {if(fields!=4||display!=1||boot!=1||esd!=1)bad=1;if(bad)exit 1;print "dbv=3600\npower=0\ndc=0\nenforcing=1\nboot_match=1\nowner_output_empty=1\nesd=reg_read"}
