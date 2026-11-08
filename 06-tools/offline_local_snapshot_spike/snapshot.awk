# OFFLINE CONTENT SEMANTICS ONLY; wrapper is required for byte and status gates.
function fail(){bad=1;exit 2}
function occurrences(s,t, n,p){if(t=="")fail();n=0;while(p=index(s,t)){n++;s=substr(s,p+length(t))}return n}
function decimal(s, a){if(s!~/^(0|[1-9][0-9]*)\.[0-9]+$/)return 0;split(s,a,".");return length(a[1])<=9&&length(a[2])<=9}
BEGIN {
 kind=ENVIRON["SNAP_KIND"];bootwant=ENVIRON["SNAP_BOOT"]
 if(kind=="STATE_ONLY"){if(ARGC!=5||length(bootwant)!=36||bootwant~/[^0-9a-f-]/)fail()}
 else if(kind=="GUARD_TIMING"){if(ARGC!=2)fail()}
 else fail()
 split("3600 0 0 Enforcing",want," ")
}
kind=="GUARD_TIMING"{
 if(++lines!=1||$0!~/^GUARD_TIMING [0-9]+\.[0-9]+ [0-9]+\.[0-9]+$/)fail()
 split($0,a," ");if(!decimal(a[2])||!decimal(a[3]))fail()
 delta=(a[3]+0)-(a[2]+0);if(delta<0||delta>8)fail();next
}
FILENAME==ARGV[1]{if(++fields>4||("x" $0)!=("x" want[fields]))fail();next}
FILENAME==ARGV[2]{
 if(index($0,"mActiveSfDisplayMode=")){
  if(++display!=1||occurrences($0,"mActiveSfDisplayMode=")!=1||occurrences($0,"peakRefreshRate=")!=1)fail()
  s=substr($0,index($0,"mActiveSfDisplayMode=")+length("mActiveSfDisplayMode="))
  p=index(s,"peakRefreshRate=");if(!p)fail()
  s=substr(s,p+length("peakRefreshRate="));match(s,/^[0-9.]+/);v=substr(s,1,RLENGTH)
  if(!decimal(v))fail()
  tail=substr(s,length(v)+1);if(tail!=""&&tail!~/^[ ,})]/)fail()
  delta=(v+0)-120;if(delta<0)delta=-delta;if(delta>=.03)fail()
 }
 next
}
FILENAME==ARGV[3]{if(++boots!=1||("x" $0)!=("x" bootwant))fail();next}
FILENAME==ARGV[4]{fail()}
END{if(bad)exit 2;if(kind=="GUARD_TIMING"){if(lines!=1)exit 2}else if(fields!=4||display!=1||boots!=1)exit 2}
