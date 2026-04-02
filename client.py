"""
Online Music Streaming Client — SSL/TLS Secured
Member 2: Client application, audio playback, and buffering mechanism

SECURITY: All communication encrypted via SSL/TLS
"""

import socket
import threading
import json
import struct
import time
import os
import io
import ssl

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[CLIENT] pygame not found. Install: pip install pygame")

# ─── Configuration ───────────────────────────────────────────
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
BUFFER_FILL_THRESHOLD = 8
DOWNLOADS_DIR = 'downloads'

# SSL certificate (same cert.pem used by server)
CERTFILE = 'cert.pem'

# ─── QoS tracking ────────────────────────────────────────────
qos_stats = {
    'bytes_received': 0,
    'start_time': None,
    'buffer_fill_time': None,
    'playback_start_time': None,
    'chunks_received': 0,
}


# ─────────────────────────────────────────────────────────────
# SSL Context Setup
# ─────────────────────────────────────────────────────────────

def create_ssl_context():
    """Create client-side SSL context that trusts our self-signed cert."""
    if not os.path.exists(CERTFILE):
        print("[CLIENT] ERROR: cert.pem not found!")
        print("         Copy cert.pem from the server to this folder.")
        raise FileNotFoundError("cert.pem missing.")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(CERTFILE)      # Trust our server's cert
    context.minimum_version = ssl.TLSVersion.TLSv1_2

    # For self-signed certs: disable hostname check
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED      # Still verify the certificate

    return context


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def send_message(conn, msg: dict):
    data = json.dumps(msg).encode('utf-8')
    length = struct.pack('>I', len(data))
    conn.sendall(length + data)


def recv_message(conn) -> dict:
    raw_len = recvall(conn, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack('>I', raw_len)[0]
    data = recvall(conn, msg_len)
    if not data:
        return None
    return json.loads(data.decode('utf-8'))


def recvall(conn, n: int) -> bytes:
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


def save_file(filename: str, data: bytes):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    path = os.path.join(DOWNLOADS_DIR, filename)
    with open(path, 'wb') as f:
        f.write(data)
    print(f"[CLIENT] Saved to ./{DOWNLOADS_DIR}/{filename}")


# ─────────────────────────────────────────────────────────────
# Audio playback
# ─────────────────────────────────────────────────────────────

def play_audio_from_bytes(audio_data: bytes, filename: str):
    """Play received audio bytes using pygame."""
    if not PYGAME_AVAILABLE:
        print("[CLIENT] Playback skipped (pygame not installed).")
        return

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ('.mp3', '.wav', '.ogg'):
        print(f"[CLIENT] Unsupported format: {ext}")
        return

    pygame.mixer.init()
    audio_buf = io.BytesIO(audio_data)
    try:
        pygame.mixer.music.load(audio_buf, ext.lstrip('.'))
        print(f"[CLIENT] ▶  Playing: {filename}")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        print(f"[CLIENT] ■  Playback finished.")
    except Exception as e:
        print(f"[CLIENT] Playback error: {e}")
    finally:
        pygame.mixer.quit()


# ─────────────────────────────────────────────────────────────
# Buffered receiving
# ─────────────────────────────────────────────────────────────

def receive_and_buffer(conn, meta: dict) -> bytes:
    """Receive audio chunks over SSL, buffer them, start playback."""
    filename  = meta['filename']
    file_size = meta['file_size']
    chunk_size = meta['chunk_size']

    audio_buffer    = b''
    playback_started = False
    playback_thread  = None

    qos_stats['start_time']      = time.time()
    qos_stats['bytes_received']  = 0
    qos_stats['chunks_received'] = 0

    print(f"\n[CLIENT] Receiving '{filename}' ({file_size} bytes) over SSL...")
    print(f"[CLIENT] Buffering {BUFFER_FILL_THRESHOLD} chunks before playback...")

    bytes_received = 0

    while bytes_received < file_size:
        to_recv = min(chunk_size, file_size - bytes_received)
        chunk = recvall(conn, to_recv)
        if not chunk:
            break

        audio_buffer   += chunk
        bytes_received += len(chunk)
        qos_stats['bytes_received']  += len(chunk)
        qos_stats['chunks_received'] += 1

        # Progress bar
        pct = int((bytes_received / file_size) * 40)
        bar = '█' * pct + '░' * (40 - pct)
        print(f"\r  [{bar}] {bytes_received}/{file_size} bytes", end='', flush=True)

        # Start playback after buffer fills
        if not playback_started and qos_stats['chunks_received'] >= BUFFER_FILL_THRESHOLD:
            qos_stats['buffer_fill_time'] = time.time() - qos_stats['start_time']
            print(f"\n[CLIENT] Buffer ready ({qos_stats['buffer_fill_time']:.3f}s) — starting playback...")
            qos_stats['playback_start_time'] = time.time()
            playback_thread = threading.Thread(
                target=play_audio_from_bytes,
                args=(audio_buffer, filename),
                daemon=True
            )
            playback_thread.start()
            playback_started = True

    print()

    if not playback_started and audio_buffer:
        qos_stats['buffer_fill_time']    = time.time() - qos_stats['start_time']
        qos_stats['playback_start_time'] = time.time()
        play_audio_from_bytes(audio_buffer, filename)
    elif playback_thread:
        playback_thread.join()

    return audio_buffer


# ─────────────────────────────────────────────────────────────
# Main client
# ─────────────────────────────────────────────────────────────

def run_client():
    print("=" * 52)
    print("  🔒 Secure Music Streaming Client")
    print(f"  Connecting to {SERVER_HOST}:{SERVER_PORT} (SSL)...")
    print("=" * 52)

    try:
        ssl_context = create_ssl_context()
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn = ssl_context.wrap_socket(raw_sock, server_hostname=SERVER_HOST)
        conn.connect((SERVER_HOST, SERVER_PORT))

        cipher = conn.cipher()
        print(f"[CLIENT] Connected!")
        print(f"[CLIENT] Cipher : {cipher[0]}")
        print(f"[CLIENT] Protocol: {cipher[1]}\n")

    except ssl.SSLError as e:
        print(f"[CLIENT] SSL error: {e}")
        return
    except ConnectionRefusedError:
        print(f"[CLIENT] Cannot connect. Is the server running?")
        return

    try:
        msg = recv_message(conn)
        if not msg or msg.get('type') != 'song_list':
            print("[CLIENT] Did not receive song list.")
            return

        songs = msg.get('songs', [])
        if not songs:
            print("[CLIENT] No songs on server.")
            return

        while True:
            print("\n─── Available Songs ───────────────────────────")
            for i, song in enumerate(songs, 1):
                print(f"  {i}. {song}")
            print("  0. Quit")
            print("───────────────────────────────────────────────")

            choice = input("Select a song number: ").strip()
            if choice == '0':
                send_message(conn, {'type': 'disconnect'})
                break
            if not choice.isdigit() or not (1 <= int(choice) <= len(songs)):
                print("[CLIENT] Invalid choice.")
                continue

            selected = songs[int(choice) - 1]
            send_message(conn, {'type': 'request', 'filename': selected})

            meta = recv_message(conn)
            if not meta:
                break
            if meta.get('type') == 'error':
                print(f"[CLIENT] Server error: {meta.get('msg')}")
                continue
            if meta.get('type') == 'stream_start':
                audio_data = receive_and_buffer(conn, meta)
                end_msg = recv_message(conn)

                save = input("\nSave file locally? (y/n): ").strip().lower()
                if save == 'y':
                    save_file(selected, audio_data)

                from qos import print_qos_report
                print_qos_report(qos_stats, end_msg)

    except ssl.SSLError as e:
        print(f"[CLIENT] SSL error during session: {e}")
    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted.")
    finally:
        conn.close()
        print("[CLIENT] Disconnected.")


if __name__ == '__main__':
    run_client()
