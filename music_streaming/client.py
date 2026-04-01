"""
Online Music Streaming Client
Member 2: Client application, audio playback, and buffering mechanism
"""

import socket
import threading
import json
import struct
import time
import os
import queue
import io

# pygame is used for audio playback (pip install pygame)
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[CLIENT] pygame not found. Audio playback disabled.")
    print("         Install with: pip install pygame")

# ─── Configuration ───────────────────────────────────────────
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000
BUFFER_FILL_THRESHOLD = 8    # Chunks to buffer before playback starts
DOWNLOADS_DIR = 'downloads'  # Local folder to save received files

# ─── QoS tracking ────────────────────────────────────────────
qos_stats = {
    'bytes_received': 0,
    'start_time': None,
    'buffer_fill_time': None,
    'playback_start_time': None,
    'chunks_received': 0,
}


# ─────────────────────────────────────────────────────────────
# Low-level helpers
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


# ─────────────────────────────────────────────────────────────
# Buffer + Playback
# ─────────────────────────────────────────────────────────────

def play_audio_from_bytes(audio_data: bytes, filename: str):
    """Play audio bytes using pygame mixer."""
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

        # Wait until playback finishes
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        print(f"[CLIENT] ■  Playback finished: {filename}")
    except Exception as e:
        print(f"[CLIENT] Playback error: {e}")
    finally:
        pygame.mixer.quit()


def receive_and_buffer(conn, meta: dict) -> bytes:
    """
    Receive audio stream in chunks into a buffer queue.
    Simulates real-time buffering — playback starts after
    BUFFER_FILL_THRESHOLD chunks are received.
    """
    filename = meta['filename']
    file_size = meta['file_size']
    chunk_size = meta['chunk_size']

    chunk_queue = queue.Queue()
    audio_buffer = b''
    playback_started = False
    playback_thread = None

    qos_stats['start_time'] = time.time()
    qos_stats['bytes_received'] = 0
    qos_stats['chunks_received'] = 0

    print(f"\n[CLIENT] Receiving '{filename}' ({file_size} bytes)...")
    print(f"[CLIENT] Buffering first {BUFFER_FILL_THRESHOLD} chunks before playback...")

    bytes_received = 0

    while bytes_received < file_size:
        remaining = file_size - bytes_received
        to_recv = min(chunk_size, remaining)
        chunk = recvall(conn, to_recv)
        if not chunk:
            break

        audio_buffer += chunk
        bytes_received += len(chunk)
        qos_stats['bytes_received'] += len(chunk)
        qos_stats['chunks_received'] += 1

        chunk_queue.put(chunk)

        # Progress bar
        pct = int((bytes_received / file_size) * 40)
        bar = '█' * pct + '░' * (40 - pct)
        print(f"\r  [{bar}] {bytes_received}/{file_size} bytes", end='', flush=True)

        # Start playback after buffer fills
        if not playback_started and chunk_queue.qsize() >= BUFFER_FILL_THRESHOLD:
            qos_stats['buffer_fill_time'] = time.time() - qos_stats['start_time']
            print(f"\n[CLIENT] Buffer ready in {qos_stats['buffer_fill_time']:.3f}s — starting playback thread...")
            qos_stats['playback_start_time'] = time.time()
            # Playback on separate thread so download continues simultaneously
            playback_thread = threading.Thread(
                target=play_audio_from_bytes,
                args=(audio_buffer, filename),
                daemon=True
            )
            playback_thread.start()
            playback_started = True

    print()  # newline after progress bar

    # If file was small and buffer threshold never hit, play now
    if not playback_started and audio_buffer:
        qos_stats['buffer_fill_time'] = time.time() - qos_stats['start_time']
        qos_stats['playback_start_time'] = time.time()
        play_audio_from_bytes(audio_buffer, filename)
    elif playback_thread:
        playback_thread.join()

    return audio_buffer


# ─────────────────────────────────────────────────────────────
# Main client loop
# ─────────────────────────────────────────────────────────────

def save_file(filename: str, data: bytes):
    """Optionally save received audio to downloads folder."""
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    path = os.path.join(DOWNLOADS_DIR, filename)
    with open(path, 'wb') as f:
        f.write(data)
    print(f"[CLIENT] Saved to ./{DOWNLOADS_DIR}/{filename}")


def run_client():
    print("=" * 50)
    print("  Music Streaming Client")
    print(f"  Connecting to {SERVER_HOST}:{SERVER_PORT}...")
    print("=" * 50)

    try:
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn.connect((SERVER_HOST, SERVER_PORT))
        print("[CLIENT] Connected to server.\n")
    except ConnectionRefusedError:
        print(f"[CLIENT] ERROR: Cannot connect to {SERVER_HOST}:{SERVER_PORT}")
        print("         Make sure the server is running first.")
        return

    try:
        # Receive song list
        msg = recv_message(conn)
        if not msg or msg.get('type') != 'song_list':
            print("[CLIENT] Did not receive song list from server.")
            return

        songs = msg.get('songs', [])
        if not songs:
            print("[CLIENT] No songs available on the server.")
            print("         Add .mp3 / .wav files to the server's 'music/' folder.")
            return

        while True:
            print("\n─── Available Songs ──────────────────────────")
            for i, song in enumerate(songs, 1):
                print(f"  {i}. {song}")
            print("  0. Quit")
            print("──────────────────────────────────────────────")

            choice = input("Select a song number: ").strip()

            if choice == '0':
                send_message(conn, {'type': 'disconnect'})
                break

            if not choice.isdigit() or not (1 <= int(choice) <= len(songs)):
                print("[CLIENT] Invalid choice. Try again.")
                continue

            selected = songs[int(choice) - 1]
            send_message(conn, {'type': 'request', 'filename': selected})

            # Receive stream_start metadata
            meta = recv_message(conn)
            if not meta:
                print("[CLIENT] No response from server.")
                break

            if meta.get('type') == 'error':
                print(f"[CLIENT] Server error: {meta.get('msg')}")
                continue

            if meta.get('type') == 'stream_start':
                audio_data = receive_and_buffer(conn, meta)

                # Receive stream_end ack with server-side stats
                end_msg = recv_message(conn)

                # Ask to save
                save = input("\nSave file locally? (y/n): ").strip().lower()
                if save == 'y':
                    save_file(selected, audio_data)

                # Print QoS report
                from qos import print_qos_report
                print_qos_report(qos_stats, end_msg)

    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted.")
    finally:
        conn.close()
        print("[CLIENT] Disconnected.")


if __name__ == '__main__':
    run_client()
