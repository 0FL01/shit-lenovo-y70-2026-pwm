# Input is checked od decimal bytes, not text evidence. LC_ALL=C is mandatory.
function fail() { bad=1; exit 1 }
function flush() { if (length(buf)) { printf "%s",buf > dest; buf="" } }
function framing(s, a,k) {
 if (state=="start") { if(s!=prefix "START") fail(); state="header"; return }
 if (state=="header") {
  k=split(s,a," ")
  if(k!=5 || s!=prefix "SECTION " label[part] " " a[3] " " a[4] " " a[5]) fail()
  if(a[3]!="0" || a[5]!="0" || a[4]!~/^(0|[1-9][0-9]*)$/ || length(a[4])>9 || a[4]+0>cap[part]) fail()
  left=a[4]+0; dest=ENVIRON["P85_STAGE"] "/section" sprintf("%02d",part)
  printf "%s","" > dest
  tail=""; buf=""; state=left ? "payload" : "boundary"; return
 }
 if(state=="end") {
  if(s!=prefix "END " label[part]) fail()
  flush(); if(close(dest)!=0) fail()
  part++; state=part<=count ? "header" : "done"; return
 }
 if(state=="done") { if(s!=prefix "DONE") fail(); state="finished"; return }
 fail()
}
BEGIN {
 expected=ENVIRON["P85_RAW_SIZE"]
 if(expected!~/^[0-9]+$/ || length(expected)>8 || expected+0>25165824) fail()
 nonce=ENVIRON["P85_NONCE"]
 if(length(nonce)!=12 || nonce~/[^0-9a-f]/) fail()
 # Validate every trusted plan row BEFORE consuming any evidence.
 while((r=(getline row < ENVIRON["P85_PLAN"]))>0) {
  if(++count>16 || length(row)>60) fail()
  k=split(row,a," ")
  if(k!=2 || row!=a[1] " " a[2] || a[1]!~/^[A-Z][A-Z0-9_]*$/ || length(a[1])>40 || seen[a[1]]++) fail()
  if(a[2]!~/^(0|[1-9][0-9]*)$/ || length(a[2])>8 || a[2]+0>16777216) fail()
  label[count]=a[1];cap[count]=a[2]+0
 }
 if(r<0 || close(ENVIRON["P85_PLAN"])!=0 || count<1) fail()
 prefix="@P85E:" nonce ":"; part=1;state="start"; line=""
}
{
 for(i=1;i<=NF;i++) {
  if($i!~/^[0-9]+$/ || $i+0>127 || $i+0<1 || ++total>25165824) fail()
  b=$i+0;c=sprintf("%c",b)
  if(state=="finished") fail()
  if(state=="payload") {
   tail=tail c;if(length(tail)>length(prefix)) tail=substr(tail,2)
   if(tail==prefix) fail()
   buf=buf c;if(length(buf)>=4096) flush()
   if(--left==0) state="boundary"
  } else if(state=="boundary") {
   if(b!=10) fail(); state="end"
  } else {
   if(b==10) { framing(line);line="" }
   else {line=line c;if(length(line)>160) fail()}
  }
 }
}
END { if(bad || state!="finished" || length(line) || total!=expected+0) exit 1 }
