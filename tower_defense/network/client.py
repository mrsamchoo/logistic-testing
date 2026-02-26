import socket
import threading
from queue import Queue, Empty

from config.settings import DEFAULT_PORT
from network.protocol import (
    encode_message, decode_messages,
    MSG_PLACE_TOWER, MSG_SELL_TOWER, MSG_UPGRADE_TOWER,
    MSG_SEND_ENEMY, MSG_READY, MSG_DISCONNECT,
)


class NetworkClient:
    def __init__(self):
        self.sock = None
        self.player_id = None
        self.incoming = Queue()
        self.connected = False
        self._recv_buffer = b''

    def connect(self, host, port=DEFAULT_PORT):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            self.connected = True

            # Start receiver thread
            t = threading.Thread(target=self._receive_loop, daemon=True)
            t.start()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def _receive_loop(self):
        while self.connected:
            try:
                data = self.sock.recv(8192)
                if not data:
                    self.connected = False
                    break
                self._recv_buffer += data
                messages, self._recv_buffer = decode_messages(self._recv_buffer)
                for msg in messages:
                    self.incoming.put(msg)
            except (ConnectionResetError, OSError):
                self.connected = False
                break

    def get_messages(self):
        """Drain all pending messages."""
        messages = []
        while True:
            try:
                messages.append(self.incoming.get_nowait())
            except Empty:
                break
        return messages

    def send_place_tower(self, tower_type, col, row):
        self._send(MSG_PLACE_TOWER, {
            "tower_type": tower_type, "col": col, "row": row
        })

    def send_sell_tower(self, tower_id):
        self._send(MSG_SELL_TOWER, {"tower_id": tower_id})

    def send_upgrade_tower(self, tower_id):
        self._send(MSG_UPGRADE_TOWER, {"tower_id": tower_id})

    def send_enemy(self, enemy_type, count):
        self._send(MSG_SEND_ENEMY, {"enemy_type": enemy_type, "count": count})

    def send_ready(self):
        self._send(MSG_READY, {})

    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.sendall(encode_message(MSG_DISCONNECT))
                self.sock.close()
            except Exception:
                pass

    def _send(self, msg_type, data):
        if self.connected and self.sock:
            try:
                self.sock.sendall(encode_message(msg_type, data))
            except Exception:
                self.connected = False
