#!/usr/bin/env python3

import time
import socket
import selectors
import paramiko

def splice(fd_in, fd_out):
    try:
        data = fd_in.recv(8192)
        fd_out.send(data)
        l = len(data)
    except (BrokenPipeError, OSError):
        l = 0
    return l


def forwarder(to_fileobj):
    def handler(conn, mask):
        length = splice(conn, to_fileobj)
        return conn, length
    return handler


def attach(fd_out):
    def accept(sock, mask):
        conn, addr = sock.accept()  # Should be ready
        conn.setblocking(False)
        new_chan = fd_out()
        sel.register(conn, selectors.EVENT_READ, forwarder(new_chan))
        sel.register(new_chan, selectors.EVENT_READ, forwarder(conn))
        return conn, None
    return accept

def get_local_sock(port):
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('localhost', port))
    sock.listen(10) # to check with the SSH client source code
    sock.setblocking(False)
    return sock

def get_tunnel_chan(transport, lp, rp):
    chan = transport.open_channel(
        'direct-tcpip',
        src_addr=('localhost', lp),
        dest_addr=('localhost', rp)
    )
    chan.setblocking(0)
    return chan

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.load_system_host_keys()
ssh.connect(HOST, username='root', port=22, password=None)
transport = ssh.get_transport()

# ssh -L p1:host:p2
p1 = 8080
p2 = 80

local_sock = get_local_sock(p1)
get_new = lambda: get_tunnel_chan(transport, p1, p2)

sel = selectors.DefaultSelector()
sel.register(local_sock, selectors.EVENT_READ, attach(get_new))

while True:
    events = sel.select(1)
    for key, mask in events:
        callback = key.data
        conn, length = callback(key.fileobj, mask)
        if length == 0:
            sel.unregister(conn)
            conn.close()

