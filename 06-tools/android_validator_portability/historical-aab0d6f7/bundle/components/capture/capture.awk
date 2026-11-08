# OFFLINE feasibility spike. No device operations. POSIX awk subset.
function reject(){bad=1}
function occurrences(s,t, n,i){n=0;while(i=index(s,t)){n++;s=substr(s,i+length(t))}return n}
function num(s, i,n,c){
 if(s ~ /^0x[0-9a-fA-F]+$/){n=0;for(i=3;i<=length(s);i++){c=index("0123456789abcdef",tolower(substr(s,i,1)))-1;n=n*16+c}return n}
 if(s !~ /^(0|[1-9][0-9]*)$/){reject();return -999}return s+0
}
function fields(line, n,a,i,p,k){
 for(k in f)delete f[k]; for(k in rawfield)delete rawfield[k]; n=split(line,a," ");fc=0
 for(i=1;i<=n;i++)if(index(a[i],"=")){p=index(a[i],"=");k=substr(a[i],1,p-1);if(k in f)reject();rawfield[k]=substr(a[i],p+1);f[k]=num(rawfield[k]);fc++}
}
function eq(k,v){if(!(k in f)||f[k]!=v)reject()}
function event_grammar(line,name, prefix,rest,symbol,pattern,n){
 prefix="^ *printf-[1-9][0-9]* +\\[[0-9][0-9][0-9]\\] (d[.][.][.][.]|d[.][.]1[.]) +[0-9]+[.][0-9]+: " name "_" nonce ": "
 if(line !~ prefix)return 0
 rest=line;sub(prefix,"",rest)
 symbol=symbols[name]
 if(index(rest,"(symbol) ")==1)rest=substr(rest,10)
 else if(index(rest,symbol" ")==1)rest=substr(rest,length(symbol)+2)
 else if(name=="ctrl" && index(rest,readsymbol" ")==1)rest=substr(rest,length(readsymbol)+2)
 else return 0
 n="(0|[1-9][0-9]*|0x[0-9a-fA-F]+)"
 if(name=="entry")pattern="pending=0 length=(9|11) flags=0"
 if(name=="ctrl"||name=="tx")pattern="rc=(0|3)"
 if(name=="header")pattern="header=" n " requested=" n " count=" n " allocation=" n " disp_op=" n
 if(name=="hardware")pattern="hw_status=" n " read_bytes=" n " mrps=" n
 return rest ~ ("^" pattern "$")
}
BEGIN {
 if(length(nonce)!=12 || nonce ~ /[^0-9a-f]/ || (kind!="85"&&kind!="C1"&&kind!="write"))bad=1
 want["header"]=(kind=="write"?0:1);want["hardware"]=want["header"];want["ctrl"]=(kind=="write"?3:4);want["tx"]=3;want["entry"]=3
 symbols["entry"]="(dsi_display_cmd_transfer+0x0/0x34c [msm_drm])"
 symbols["ctrl"]="(dsi_host_transfer_sub+0x2f4/0x558 [msm_drm] <- dsi_ctrl_cmd_transfer)"
 readsymbol="(dsi_display_cmd_receive+0x448/0x4e8 [msm_drm] <- dsi_ctrl_cmd_transfer)"
 symbols["tx"]="(_sde_debugfs_conn_cmd_tx_write+0x3ac/0x4d8 [msm_drm] <- dsi_display_cmd_transfer)"
 symbols["hardware"]="(dsi_ctrl_hw_cmn_get_cmd_read_data+0x5c/0x350 [msm_drm])"
 symbols["header"]="(dsi_ctrl_cmd_transfer+0x494/0x86c [msm_drm])"
 comments["#"]=1;comments["# tracer: nop"]=1
 comments["#                                _-----=> irqs-off/BH-disabled"]=1
 comments["#                               / _----=> need-resched"]=1
 comments["#                              | / _---=> hardirq/softirq"]=1
 comments["#                              || / _--=> preempt-depth"]=1
 comments["#                              ||| / _-=> migrate-disable"]=1
 comments["#                              |||| /     delay"]=1
 comments["#              | |         |   |||||     |         |"]=1
 comments["#           TASK-PID     CPU#  |||||  TIMESTAMP  FUNCTION"]=1
 comments["# TASK-PID CPU TIMESTAMP FUNCTION"]=1
 comments["# entries-in-buffer/entries-written: " (kind=="write"?"9/9":"12/12") "   #P:8"]=1
}
/LOST|RECOVERY_REQUIRED/ {reject()}
{
 if($0 !~ /^[ \t]*$/ && phase!=1 && phase!=3)meta=meta " " $1
 if(length($0)>4096)reject()
 if($0=="TRACE_BEGIN"){if(phase!=0||tb++)reject();phase=1;next}
 if($0=="TRACE_END"){if(phase!=1||te++)reject();phase=2;next}
 if($0=="PROFILE_BEGIN"){if(phase!=2||pb++)reject();phase=3;next}
 if($0=="PROFILE_END"){if(phase!=3||pe++)reject();phase=4;next}
 if(phase==1){
  if($0 ~ /^#/){if(!($0 in comments))reject();next}
  if($0 ~ /^[ \t]*$/)next
  name="";for(k in want)if(index($0,k"_"nonce":")){if(name!="")reject();name=k}
  if(name==""||$5!=name"_"nonce":"||occurrences($0,"_"nonce":")!=1){reject();next}
  if(!event_grammar($0,name)){reject();next}
  pid=$1;sub(/^.*-/,"",pid);if(pid !~ /^[0-9]+$/ || $2 !~ /^\[[0-9]+\]$/)reject()
  fields($0);seq=seq " " name;count[name]++
  if(name=="entry"){ep=pid;eq("pending",0);eq("flags",0);eq("length",kind=="write"&&count[name]==2?9:11);if(fc!=3||rawfield["pending"]!="0"||rawfield["flags"]!="0"||rawfield["length"]!=(kind=="write"&&count[name]==2?"9":"11"))reject()}
  if(name=="ctrl"){eq("rc",kind!="write"&&count[name]==2?3:0);if(fc!=1)reject();if(kind!="write"&&count[name]==2){if(pid!=hp||pid!=wp)reject()}else if(pid!=ep)reject()}
  if(name=="tx"){eq("rc",0);if(fc!=1||pid!=ep)reject()}
  if(name=="header"){
   hp=pid;eq("requested",3);eq("allocation",16);eq("disp_op",0);eq("count",9)
   # Exact valid DT1c/WC3/ECC16 header; no bitwise extensions required.
   eq("header",369099548);if(fc!=5)reject()
  }
  if(name=="hardware"){wp=pid;eq("read_bytes",16);eq("mrps",3);raw=int(f["hw_status"]/65536);if(fc!=3||!("hw_status" in f)||(raw!=9&&raw!=13))reject()}
  next
 }
 if(phase==3){
  n=$1;sub("_"nonce"$","",n);if(!(n in want)||$0 !~ ("^ *" n "_" nonce " +(0|[1-9][0-9]*) +0 *$")||$2+0!=want[n]||prof[n]++)reject();next
 }
 if($0 ~ /^[ \t]*$/)next
 if($1=="STATE"){if(phase!=0||state++||$0!~/^STATE 3600 (0|[1-9][0-9]*)\.[0-9]+$/||$3-120>=.03||120-$3>=.03)reject();hz=$3;next}
 if($1=="ESD_INITIAL"){if(phase!=0||ei++||$0!="ESD_INITIAL reg_read")reject();next}
 if($1=="ESD_ACTIVE"){if(phase!=0||ea++||$0!="ESD_ACTIVE esd_sw_sim_success")reject();next}
 if($1=="ESD_RESTORED"){if(phase!=(kind=="C1"?0:4)||er++||$0!="ESD_RESTORED reg_read")reject();next}
 if($1=="GATE_OK"||$1=="WRITE_GATE_OK"){if(phase!=0||$0 !~ ("^" (kind=="write"?"WRITE_GATE_OK":"GATE_OK") " [0-4]$"))reject();gates=gates $2;next}
 if($1=="C1"||$1=="P85_LONG3"){
  byte="0x[0-9a-fA-F][0-9a-fA-F]?"
  if(phase!=0||data++||$0 !~ ("^" (kind=="85"?"P85_LONG3":"C1") " " byte " " byte " " byte " *$")||kind=="write")reject()
  for(i=2;i<=4;i++){if($i!~/^0x[0-9a-fA-F]+$/||length($i)>4)reject();values=values (i==2?"":",") num($i)}next
 }
 if($0=="CLEANUP_OK"){if(phase!=4||clean++)reject();phase=5;next}
 reject()
}
END {
 common=" STATE ESD_INITIAL ESD_ACTIVE"
 if(kind=="write")expectedmeta=common " WRITE_GATE_OK WRITE_GATE_OK WRITE_GATE_OK WRITE_GATE_OK WRITE_GATE_OK TRACE_BEGIN PROFILE_BEGIN ESD_RESTORED CLEANUP_OK"
 else expectedmeta=common " GATE_OK GATE_OK GATE_OK GATE_OK " (kind=="85"?"P85_LONG3":"C1") " GATE_OK GATE_OK " (kind=="C1"?"ESD_RESTORED ":"") "TRACE_BEGIN PROFILE_BEGIN " (kind=="85"?"ESD_RESTORED ":"") "CLEANUP_OK"
 if(meta!=expectedmeta)bad=1
 expected=(kind=="write"?" entry ctrl tx entry ctrl tx entry ctrl tx":" entry ctrl tx hardware header ctrl entry ctrl tx entry ctrl tx")
 if(seq!=expected||gates!=(kind=="write"?"01233":"012334")||state!=1||ei!=1||ea!=1||er!=1||clean!=1||tb!=1||te!=1||pb!=1||pe!=1||phase!=5||data!=(kind=="write"?0:1))bad=1
 for(k in want)if(count[k]+0!=want[k]||prof[k]!=1)bad=1
 if(bad)exit 1
 printf "kind=%s\ndata=%s\nraw_count=%d\nrefresh=%s\ncallbacks=3\n",kind,values,raw,hz
}
