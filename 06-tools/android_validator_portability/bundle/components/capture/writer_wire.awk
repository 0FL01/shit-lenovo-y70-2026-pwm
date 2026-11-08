# OFFLINE stock15 writer wire/native/protected-origin/tail validator.
# Caller supplies exact previously validated protected, begin, end markers.
function occurrences(s,t, n,i){n=0;while(i=index(s,t)){n++;s=substr(s,i+length(t))}return n}
BEGIN {
 if(protected !~ /^[A-Za-z0-9_]+$/||begin !~ /^[A-Za-z0-9_]+$/||end !~ /^[A-Za-z0-9_]+$/||index(protected,begin)||index(begin,protected)||index(begin,end)||index(end,begin)||index(protected,end)||index(end,protected)){bad=1;exit 2}
 stamp="\\[ +[0-9]+[.][0-9]+\\] "
 native="^" stamp "\\[drm:dsi_display_set_mode \\[msm_drm\\]\\] \\[msm-dsi-info\\]: mdp_transfer_time=(0|[1-9][0-9]*), hactive=1440, vactive=3168, fps=120\\(actual=120, group=0x3\\), clk_rate=1234000000$"
}
{
 po=occurrences($0,protected);bo=occurrences($0,begin);eo=occurrences($0,end)
 if(po+bo+eo){
  # A boundary is its own complete printk line, never a substring in an
  # operation line or a coalesced/reordered set of multiple markers.
  if(po+bo+eo!=1)bad=1
  if(po){if($0 !~ ("^" stamp protected "$"))bad=1;p++;if(b||e)bad=1;active=1;if(anchor!=1)bad=1}
  if(bo){if($0 !~ ("^" stamp begin "$"))bad=1;b++;if(p!=1||e)bad=1;writing=1}
  if(eo){if($0 !~ ("^" stamp end "$"))bad=1;e++;if(b!=1||p!=1||wire!=3)bad=1;writing=0;ended=1}
  next
 }
 if(/dsi_display_set_mode/){
  # Full-line native grammar rejects multiple tuples and alternate prefixes.
  # Every later set_mode replaces/invalidate the anchor, even malformed ones.
  anchor=($0 ~ native && occurrences($0,"dsi_display_set_mode")==1)
 }
 if(active && /dsi_display_set_mode|Command transfer failed|LOST/)bad=1
 if(active && /dsi_ctrl_cmd_transfer len=/){
  if(!writing||ended)bad=1
  wire++;prefix="^" stamp "dsi-ctrl-1: "
  if(occurrences($0,"dsi_ctrl_cmd_transfer len=")!=1||occurrences($0,"dsi-ctrl-1:")!=1||$0 !~ prefix){bad=1;next}
  s=$0;sub(prefix,"",s)
  packet="dsi_ctrl_cmd_transfer len=" (wire==2?"2":"4") ", type=0x39 hs cmds= "
  if(index(s,packet)!=1){bad=1;next}
  payload=substr(s,length(packet)+1);sub(/ +$/,"",payload)
  want=(wire==1?"ff 5a a5 23":(wire==2?"85 15":"ff 5a a5 00"))
  if(tolower(payload)!=want||wire>3)bad=1
 }
}
END {if(p!=1||b!=1||e!=1||wire!=3||anchor!=1)bad=1;if(bad)exit 1;print "stock_wire_packets=3\nnative_actual_hz=120\nnative_group=3\nprotected_tail_verified=1"}
