set -u
umask 077
LC_ALL=C; export LC_ALL
awk 'BEGIN {x=999999999*1000000+999999; if(sprintf("%.0f",x)!="999999999999999")exit 1; if(split("12.34",a,".")!=2||a[1]!="12"||a[2]!="34")exit 1; delete a[1]; if(1 in a)exit 1; s="abc"; sub(/b/,"x",s); match(s,/xc/); if(RLENGTH!=2)exit 1; if(ENVIRON["LC_ALL"]!="C")exit 1; printf "%c%c",65,10}'
