"""Inert host-only protocol probe proposal. Injected dependencies, no adapter.
No source/config discovery, CLI, default socket or selected-device services.
"""
import stat
import sys

class ProbeFailure(RuntimeError): pass

def require(value,message):
    if not value:raise ProbeFailure(message)

def run(*,association,proc,pin,limits,make_socket,clock,sleep,os_api,parse_starttime):
    started=clock()
    deadline=started+12
    protocol_deadline=None
    def current_deadline():return min(deadline,protocol_deadline) if protocol_deadline is not None else deadline
    report=dict(status='running',entries=[],request_attempts=0,device_requests=0,
        scope='visible_thread_group_leader_fd_tables',unique_holder_qualified=False)
    def remaining():
        value=current_deadline()-clock()
        require(value>0,'Absolute deadline exhausted')
        return value
    def call(method,*args):
        remaining();value=getattr(proc,method)(*args,current_deadline());remaining();return value
    def association_check():
        remaining();require(association(current_deadline())==(pin.process,),'Original association failed');remaining()
    def address(value):
        host,port=value
        require(host=='127.0.0.1' and type(port) is int and 0<port<65536,'Unexpected tuple')
        return '0100007F:'+format(port,'04X')
    def held(sock):
        raw=sock.sock
        fd=raw.fileno();require(type(fd) is int and fd>=0,'Invalid held FD')
        st=os_api.fstat(fd)
        require(stat.S_ISSOCK(st.st_mode) and st.st_uid==os_api.getuid(),'Held FD type/owner mismatch')
        local,peer=raw.getsockname(),raw.getpeername()
        require(peer==pin.process.endpoint and raw.get_inheritable() is False,'Wrong peer or inheritable FD')
        address(local);address(peer)
        return (fd,st.st_dev,st.st_ino,st.st_uid,st.st_mode,local,peer)
    def custody(identity):
        raw=call('read','/proc/net/tcp',limits.tcp_bytes)
        require(len(raw)<=limits.tcp_bytes,'TCP cap exceeded')
        lines=raw.decode('ascii').splitlines()
        require(lines and 'local_address' in lines[0],'Bad TCP header')
        matches=[]
        for line in lines[1:]:
            f=line.split();require(len(f)>=10,'Malformed TCP row')
            if f[1]==address(identity[6]) and f[2]==address(identity[5]) and f[3]=='01':
                require(f[7].isdigit() and f[9].isdigit(),'Malformed owner/inode')
                matches.append((int(f[7]),int(f[9])))
        require(len(matches)==1 and matches[0][0]==pin.process.uids[0] and matches[0][1]>0,'Accepted connection absent/ambiguous')
        inode=matches[0][1]
        names=call('names','/proc',limits.max_pids)
        require(len(names)<=limits.max_pids and len(set(names))==len(names),'Incomplete process scan')
        pids=tuple(sorted(int(n) for n in names if n.isascii() and n.isdigit() and n!='0'))
        require(pin.process.pid in pids,'Pinned process absent')
        owners=[];total=0
        for pid in pids:
            before=call('read','/proc/'+str(pid)+'/stat',limits.stat_bytes)
            require(len(before)<=limits.stat_bytes,'Stat cap exceeded')
            start=parse_starttime(before,pid)
            pairs=call('fd_links',pid,limits.max_fds_per_pid,limits.link_bytes)
            require(len(pairs)<=limits.max_fds_per_pid and len({n for n,_ in pairs})==len(pairs),'Incomplete FD scan')
            total+=len(pairs);require(total<=limits.max_total_fds,'Total FD cap exceeded')
            for fd,link in pairs:
                require(fd.isascii() and fd.isdigit() and len(link.encode())<=limits.link_bytes,'Malformed FD metadata')
            after=call('read','/proc/'+str(pid)+'/stat',limits.stat_bytes)
            require(len(after)<=limits.stat_bytes and parse_starttime(after,pid)==start,'Task identity changed')
            if any(link=='socket:['+str(inode)+']' for _,link in pairs):owners.append((pid,start))
        after_names=call('names','/proc',limits.max_pids)
        require(sorted(names)==sorted(after_names),'Process set changed')
        require(owners==[(pin.process.pid,pin.process.starttime)],'Accepted socket holder mismatch')
        remaining();return inode
    def exact(sock,count):
        result=b''
        while len(result)<count:
            sock.settimeout(remaining());part=sock.recv(count-len(result));remaining()
            require(part and len(part)<=count-len(result),'Truncated response')
            result+=part
        return result
    try:
        for idle in (1.0,):
            entry=dict(idle_seconds=idle,phase='association_before',close_attempted=False,close_completed=False)
            report['entries'].append(entry);sock=None
            try:
                association_check()
                entry['phase']='connect';protocol_deadline=min(deadline,clock()+8);sock=make_socket();sock.settimeout(remaining());sock.connect(pin.process.endpoint)
                identity=held(sock);entry['held_identity']=identity
                entry['phase']='custody_before';inode=custody(identity);association_check()
                entry['phase']='idle';require(remaining()>idle,'Insufficient idle budget');sleep(idle);remaining()
                require(held(sock)==identity,'Held socket identity changed')
                require(custody(identity)==inode,'Accepted inode changed');association_check()
                entry['phase']='version_send';view=memoryview(b'000chost:version')
                report['request_attempts']+=1
                entry['send_attempted']=True;entry['confirmed_sent_bytes']=0;entry['request_outcome_unknown']=True
                while view:
                    sock.settimeout(remaining());n=sock.send(view);remaining()
                    require(type(n) is int and 0<n<=len(view),'Invalid send count');view=view[n:];entry['confirmed_sent_bytes']+=n
                entry['phase']='version_response'
                response=exact(sock,4)+exact(sock,4)+exact(sock,4)
                require(response==b'OKAY00040029','Unexpected protocol41 framing')
                entry['response_hex']=response.hex();entry['response_verified']=True;entry['request_outcome_unknown']=False
                entry['phase']='consume_eof';sock.settimeout(remaining());require(sock.recv(1)==b'','Unexpected bytes after one-shot version');remaining()
                entry['eof_observed']=True;protocol_deadline=None;entry['phase']='association_after';association_check()
                entry['phase']='complete'
            finally:
                primary=sys.exc_info()[1]
                cleanup_error=None
                try:
                    if sock is not None:
                        if not sock.closed:
                            entry['close_attempted']=True
                            sock.close()
                            entry['close_completed']=True
                        else:
                            entry['dependency_close_latch_set']=True
                            entry['dependency_raw_close_outcome']='unknown'
                except BaseException as error:
                    cleanup_error=error
                    entry['close_error_type']=type(error).__name__
                entry['terminal_elapsed_seconds']=clock()-started
                entry['cleanup_late']=entry['terminal_elapsed_seconds']>12
                if entry['cleanup_late'] and cleanup_error is None:
                    cleanup_error=ProbeFailure('Terminal cleanup exceeded overall deadline')
                if cleanup_error is not None:
                    entry['cleanup_error_type']=type(cleanup_error).__name__
                    if primary is None:raise cleanup_error
                    entry['primary_error_preserved']=True
        report['status']='host_only_protocol_sample_pass'
        return report
    except BaseException as error:
        report['status']='failed_no_retry';report['error_type']=type(error).__name__
        error.probe_report=report
        raise
