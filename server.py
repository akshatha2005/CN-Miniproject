"""
Online Music Streaming Server
Member 1: Server-side streaming module + multi-client connection management
"""
import socket
import threading
import os"""
Online Music Streaming Server — SSL/TLS Secured
Member 1: Server-side streaming module + multi-client connection management

SECURITY: All communication encrypted via SSL/TLS
"""

import socket
import threading
import os
import time
import json
import struct
import ssl

# ─── Configuration ───────────────────────────────────────────
HOST = '0.0.0.0'
PORT = 5000
MUSIC_DIR = 'music'
CHUNK_SIZE = 4096
BUFFER_DELAY = 0.01

# SSL Certificate files (generate with: see README.md)
CERTFILE = 'cert.pem'
KEYFILE  = 'key.pem'

# ─── Shared state ────────────────────────────────────────────
connected_clients = {}
clients_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# SSL Context Setup
# ─────────────────────────────────────────────────────────────

def create_ssl_context():
    """Create and return a server-side SSL context."""
    if not os.path.exists(CERTFILE) or not os.path.exists(KEYFILE):
        print("[SERVER] ERROR: SSL certificate files not found!")
        print("         Run this command to generate them:")
        print("         openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
        raise FileNotFoundError("cert.pem or key.pem missing.")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERTFILE, keyfile=KEYFILE)

    # Enforce strong TLS (TLS 1.2 minimum)
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    print(f"[SERVER] SSL context created — TLS {context.minimum_version.name}+")
    return context


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def list_music_files():
    if not os.path.exists(MUSIC_DIR):
        os.makedirs(MUSIC_DIR)
    return [f for f in os.listdir(MUSIC_DIR)
            if f.endswith(('.mp3', '.wav', '.ogg'))]


def send_message(conn, msg: dict):
    """Send a JSON control message prefixed with 4-byte length (encrypted by SSL)."""
    data = json.dumps(msg).encode('utf-8')
    length = struct.pack('>I', len(data))
    conn.sendall(length + data)


def recv_message(conn) -> dict:
    """Receive a length-prefixed JSON control message (decrypted by SSL)."""
    raw_len = recvall(conn, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('>I', raw_len)[0]
    data = recvall(conn, msg_len)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))


def recvall(conn, n: int) -> bytes:
    """Receive exactly n bytes."""
    buf = b''
    while len(buf) < n:
        try:
            chunk = conn.recv(n - len(buf))
        except Exception:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf


# ─────────────────────────────────────────────────────────────
# Streaming
# ─────────────────────────────────────────────────────────────

def stream_file(conn, addr, filename: str):
    """Stream audio file to client in encrypted chunks over SSL."""
    filepath = os.path.join(MUSIC_DIR, filename)

    if not os.path.exists(filepath):
        send_message(conn, {'type': 'error', 'msg': 'File not found'})
        return

    file_size = os.path.getsize(filepath)
    send_message(conn, {
        'type': 'stream_start',
        'filename': filename,
        'file_size': file_size,
        'chunk_size': CHUNK_SIZE
    })

    print(f"[SERVER] Streaming (SSL) '{filename}' ({file_size} bytes) → {addr}")
    bytes_sent = 0
    start_time = time.time()

    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            try:
                conn.sendall(chunk)   # SSL layer encrypts automatically
                bytes_sent += len(chunk)
                time.sleep(BUFFER_DELAY)
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError) as e:
                print(f"[SERVER] Stream interrupted ({addr}): {e}")
                return

    elapsed = time.time() - start_time
    throughput = (bytes_sent / 1024) / elapsed if elapsed > 0 else 0
    print(f"[SERVER] Done → {addr} | {bytes_sent} bytes | "
          f"{elapsed:.2f}s | {throughput:.1f} KB/s")

    send_message(conn, {
        'type': 'stream_end',
        'bytes_sent': bytes_sent,
        'duration': round(elapsed, 3)
    })


# ─────────────────────────────────────────────────────────────
# Client handler
# ─────────────────────────────────────────────────────────────

def handle_client(conn, addr):
    """Handle a single SSL-secured client session."""
    # Log TLS details
    cipher = conn.cipher()
    print(f"[SERVER] New SSL connection from {addr}")
    print(f"[SERVER] Cipher: {cipher[0]} | Protocol: {cipher[1]}")

    with clients_lock:
        connected_clients[addr] = threading.current_thread()

    try:
        songs = list_music_files()
        send_message(conn, {'type': 'song_list', 'songs': songs})

        while True:
            msg = recv_message(conn)
            if msg is None:
                break

            if msg.get('type') == 'request':
                filename = msg.get('filename', '')
                print(f"[SERVER] {addr} requested: {filename}")
                stream_file(conn, addr, filename)

            elif msg.get('type') == 'disconnect':
                print(f"[SERVER] {addr} disconnected gracefully.")
                break

    except ssl.SSLError as e:
        print(f"[SERVER] SSL error with {addr}: {e}")
    except Exception as e:
        print(f"[SERVER] Error with {addr}: {e}")
    finally:
        with clients_lock:
            connected_clients.pop(addr, None)
        conn.close()
        print(f"[SERVER] Connection closed: {addr} | "
              f"Active clients: {len(connected_clients)}")


# ─────────────────────────────────────────────────────────────
# Server startup
# ─────────────────────────────────────────────────────────────

def start_server():
    ssl_context = create_ssl_context()

    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    raw_sock.bind((HOST, PORT))
    raw_sock.listen(10)

    # Wrap the listening socket with SSL
    server_sock = ssl_context.wrap_socket(raw_sock, server_side=True)

    print("=" * 52)
    print(f"   Secure Music Streaming Server — port {PORT}")
    print(f"  SSL/TLS encryption : ENABLED")
    print(f"  Certificate        : {CERTFILE}")
    songs = list_music_files()
    print(f"  Songs available    : {len(songs)}")
    for s in songs:
        print(f"    • {s}")
    print("=" * 52)
    print("Waiting for clients...\n")

    try:
        while True:
            try:
                conn, addr = server_sock.accept()
                t = threading.Thread(target=handle_client,
                                     args=(conn, addr), daemon=True)
                t.start()
                print(f"[SERVER] Active clients: {len(connected_clients) + 1}")
            except ssl.SSLError as e:
                print(f"[SERVER] SSL handshake failed: {e}")
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down.")
    finally:
        server_sock.close()


if __name__ == '__main__':
    start_server()

import time
import json
import struct
# ─── Configuration ───────────────────────────────────────────
HOST = '0.0.0.0'
PORT = 5000
MUSIC_DIR = 'music'          # Folder containing .mp3 / .wav files
CHUNK_SIZE = 4096            # Bytes per packet
BUFFER_DELAY = 0.01          # Seconds between chunks (simulate stream rate)
# ─── Shared state ────────────────────────────────────────────
connected_clients = {}       # {addr: thread}
clients_lock = threading.Lock()
def list_music_files():
    """Return list of available music files in MUSIC_DIR."""
    if not os.path.exists(MUSIC_DIR):
        os.makedirs(MUSIC_DIR)
    return [f for f in os.listdir(MUSIC_DIR)
            if f.endswith(('.mp3', '.wav', '.ogg'))]
def send_message(conn, msg: dict):
    """Send a JSON control message prefixed with 4-byte length."""
    data = json.dumps(msg).encode('utf-8')
    length = struct.pack('>I', len(data))
    conn.sendall(length + data)
def recv_message(conn) -> dict:
    """Receive a length-prefixed JSON control message."""
    raw_len = recvall(conn, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('>I', raw_len)[0]
    data = recvall(conn, msg_len)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))
def recvall(conn, n: int) -> bytes:
    """Receive exactly n bytes from socket."""
    buf = b''
    while len(buf) < n:
        try:
            chunk = conn.recv(n - len(buf))
        except Exception:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf
def stream_file(conn, addr, filename: str):
    """Stream a single audio file to the client in chunks."""
    filepath = os.path.join(MUSIC_DIR, filename)
    if not os.path.exists(filepath):
        send_message(conn, {'type': 'error', 'msg': 'File not found'})
        return
    file_size = os.path.getsize(filepath)
    send_message(conn, {
        'type': 'stream_start',
        'filename': filename,
        'file_size': file_size,
        'chunk_size': CHUNK_SIZE
    })
    print(f"[SERVER] Streaming '{filename}' ({file_size} bytes) → {addr}")
    bytes_sent = 0
    start_time = time.time()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            try:
                conn.sendall(chunk)
                bytes_sent += len(chunk)
                time.sleep(BUFFER_DELAY)   # Controlled streaming rate
            except (BrokenPipeError, ConnectionResetError):
                print(f"[SERVER] Client {addr} disconnected mid-stream.")
                return
    elapsed = time.time() - start_time
    throughput = (bytes_sent / 1024) / elapsed if elapsed > 0 else 0
    print(f"[SERVER] Done streaming to {addr} | "
          f"{bytes_sent} bytes in {elapsed:.2f}s | "
          f"Throughput: {throughput:.1f} KB/s")

    send_message(conn, {'type': 'stream_end', 'bytes_sent': bytes_sent,
                        'duration': round(elapsed, 3)})
def handle_client(conn, addr):
    """Handle a single connected client session."""
    print(f"[SERVER] New connection from {addr}")
    with clients_lock:
        connected_clients[addr] = threading.current_thread()
    try:
        # Send available song list
        songs = list_music_files()
        send_message(conn, {'type': 'song_list', 'songs': songs})
        while True:
            msg = recv_message(conn)
            if msg is None:
                break
            if msg.get('type') == 'request':
                filename = msg.get('filename', '')
                print(f"[SERVER] {addr} requested: {filename}")
                stream_file(conn, addr, filename)
            elif msg.get('type') == 'disconnect':
                print(f"[SERVER] {addr} disconnected gracefully.")
                break
            else:
                print(f"[SERVER] Unknown message from {addr}: {msg}")
    except Exception as e:
        print(f"[SERVER] Error with client {addr}: {e}")
    finally:
        with clients_lock:
            connected_clients.pop(addr, None)
        conn.close()
        print(f"[SERVER] Connection closed: {addr} | "
              f"Active clients: {len(connected_clients)}")
def start_server():
    """Start the TCP streaming server."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(10)
    print("=" * 50)
    print(f"  Music Streaming Server started on port {PORT}")
    print(f"  Music folder : ./{MUSIC_DIR}/")
    print(f"  Chunk size   : {CHUNK_SIZE} bytes")
    songs = list_music_files()
    print(f"  Songs found  : {len(songs)}")
    for s in songs:
        print(f"    • {s}")
    print("=" * 50)
    print("Waiting for clients...\n")
    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr),
                                 daemon=True)
            t.start()
            print(f"[SERVER] Active clients: {len(connected_clients) + 1}")
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down.")
    finally:
        server_sock.close()
if __name__ == '__main__':
    start_server()
