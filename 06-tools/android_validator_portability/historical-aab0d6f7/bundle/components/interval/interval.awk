# OFFLINE text semantics only. Never acquires evidence or authorizes a child.
function fail() { bad=1 }
function invalid() { invalid_args=1; exit 2 }
function occurrences(s, needle, n,p) {
    n=0
    while ((p=index(s,needle))>0) { n++; s=substr(s,p+length(needle)) }
    return n
}
function stamp(s, a,n) {
    sub(/^\[ */, "", s); sub(/\].*$/, "", s)
    seconds=s+0
    n=split(s,a,".")
    if(n!=2 || length(a[1])>9 || length(a[2])!=6) { fail(); return -1 }
    return a[1]*1000000+a[2]
}
BEGIN {
    if(op!="read" && op!="quiet" && op!="dispatch" && op!="guard") invalid()
    if(begin!~/^[A-Za-z0-9_]+$/ || length(begin)<8 || length(begin)>180) invalid()
    if(op=="guard" && end!="-") invalid()
    if(op!="guard" && (end!~/^[A-Za-z0-9_]+$/ || length(end)<8 || length(end)>180 || index(begin,end) || index(end,begin))) invalid()
    if(ref!="120" && ref!="1") invalid()
    if(nonce!="-" && (nonce!~/^[0-9a-f]+$/ || length(nonce)!=12)) invalid()
    if((op=="dispatch" || op=="guard") && (nonce=="-" || ref!="120")) invalid()
    ts="^\\[ *[0-9]+\\.[0-9][0-9][0-9][0-9][0-9][0-9]\\] "
    native="^\\[drm:dsi_display_set_mode \\[msm_drm\\]\\] \\[msm-dsi-info\\]: mdp_transfer_time=[0-9]+, hactive=[0-9]+, vactive=[0-9]+, fps=[0-9]+\\(actual=[0-9]+, group=0x[0-9a-fA-F]+\\), clk_rate=[0-9]+$"
    packet="^dsi-ctrl-[0-9]+: dsi_ctrl_cmd_transfer len=[1-9][0-9]*, type=0x[0-9a-fA-F]+ (hs|lp) cmds= [0-9a-fA-F][0-9a-fA-F]( [0-9a-fA-F][0-9a-fA-F])*$"
}
{
    if(length($0)>32768 || $0 ~ /[^\t -~]/) fail()
    if(index($0,"LOST") || index($0,"Command transfer failed")) fail()
    if(nonce!="-" && index($0,"PWM_P85_WRITE_" nonce)) fail()
    b=occurrences($0,begin); e=(op=="guard" ? 0 : occurrences($0,end))
    mode=occurrences($0,"dsi_display_set_mode")
    tx=occurrences($0,"dsi_ctrl_cmd_transfer")
    if(b || e || mode || tx) {
        if($0 !~ ts) fail()
        time=stamp($0)
        body=$0; sub(ts,"",body)
        if(b+e+mode+tx!=1) fail()
    }
    if(mode) {
        if(body !~ native) fail()
        # Malformed latest event cannot retain an earlier valid state.
        current="invalid"
        if(body ~ /hactive=1440, vactive=3168, fps=120\(actual=120, group=0x3\), clk_rate=1234000000$/) current="120"
        if(body ~ /hactive=1440, vactive=3168, fps=120\(actual=1, group=0x8\), clk_rate=1234000000$/) current="1"
        if(started) fail()
    }
    if(tx) {
        if(body !~ packet) fail()
        if(started && (op!="read" || finished)) fail()
    }
    if(b) {
        nb+=b
        if(body!=begin || nb!=1 || finished || current!=ref) fail()
        started=1; bt=time; bs=seconds
    }
    if(e) {
        ne+=e
        if(body!=end || ne!=1 || !started || finished) fail()
        finished=1; et=time; es=seconds
    }
}
END {
    if(invalid_args) { print "REJECT invalid arguments"; exit 2 }
    if(nb!=1 || current!=ref || (op!="guard" && ne!=1)) fail()
    # Retain Python's floating-point boundary as an additional conservative
    # check; exact microseconds alone could admit a Python-rounded <2 result.
    if(op=="quiet" && (et-bt<2000000 || es-bs<2)) fail()
    if(op!="guard" && et<bt) fail()
    if(bad) { print "REJECT interval semantics"; exit 1 }
    print "ACCEPT offline interval semantics only"
}
