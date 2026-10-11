"""Test-only PostgreSQL wire fault proxy. No business code or database queries.
Drops one operation INSERT before forwarding, or the acknowledgement of a
COMMIT after PostgreSQL emitted CommandComplete. Not included in normal API.
"""
import json
import socket
import socketserver
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

lock = threading.Lock()
control = {'armed': None, 'event': None}


def exact(sock, count):
    data = b''
    while len(data) < count:
        chunk = sock.recv(count-len(data))
        if not chunk:
            raise EOFError()
        data += chunk
    return data


def claim(mode):
    with lock:
        if control['armed'] == mode:
            control['armed'] = None
            return True
    return False


def event(value):
    with lock:
        control['event'] = value


class Proxy(socketserver.BaseRequestHandler):
    def handle(self):
        upstream = socket.create_connection(('db', 5432), timeout=5)
        upstream.settimeout(None)
        client = self.request
        drop_ack = threading.Event()

        def close():
            for sock in (client, upstream):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        def backend():
            try:
                while True:
                    kind = exact(upstream, 1)
                    length = exact(upstream, 4)
                    body = exact(upstream, struct.unpack('!I', length)[0]-4)
                    if kind == b'C' and body == b'COMMIT\x00' and drop_ack.is_set():
                        event('commit_confirmed_by_server_ack_dropped')
                        close()
                        return
                    client.sendall(kind+length+body)
            except (EOFError, OSError):
                close()

        try:
            # TLS/GSS encryption disabled only on this isolated test connection.
            length = exact(client, 4)
            upstream.sendall(length+exact(client, struct.unpack('!I', length)[0]-4))
            thread = threading.Thread(target=backend, daemon=True)
            thread.start()
            while True:
                kind = exact(client, 1)
                length = exact(client, 4)
                body = exact(client, struct.unpack('!I', length)[0]-4)
                if kind == b'Q':
                    normalized = body.rstrip(b'\x00').strip().upper()
                    if normalized.startswith(b'INSERT INTO OPERATION') and claim('before_write'):
                        event('operation_insert_not_forwarded')
                        close()
                        return
                    if normalized == b'COMMIT' and claim('commit_ack'):
                        drop_ack.set()
                upstream.sendall(kind+length+body)
        except (EOFError, OSError):
            close()
        finally:
            upstream.close()


class Admin(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        with lock:
            body = json.dumps(control).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        mode = body.get('mode')
        if mode not in ('before_write', 'commit_ack'):
            self.send_error(400)
            return
        with lock:
            control.update(armed=mode, event=None)
        self.send_response(204)
        self.end_headers()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


threading.Thread(target=lambda: ThreadingHTTPServer(('0.0.0.0', 9090), Admin).serve_forever(), daemon=True).start()
Server(('0.0.0.0', 5432), Proxy).serve_forever()
