import socket
import threading
import time
import json
import os
from queue import Queue, Empty

from config.settings import (
    DEFAULT_HOST, DEFAULT_PORT, SERVER_TICK_RATE,
    STATE_BROADCAST_INTERVAL,
)
from config.enemy_data import ENEMIES
from core.map_grid import MapGrid
from core.game import LaneGame
from network.protocol import (
    encode_message, decode_messages,
    MSG_WELCOME, MSG_PLAYER_COUNT, MSG_GAME_START,
    MSG_GAME_STATE, MSG_EVENT, MSG_GAME_OVER,
    MSG_PLACE_TOWER, MSG_SELL_TOWER, MSG_UPGRADE_TOWER,
    MSG_SEND_ENEMY, MSG_READY, MSG_DISCONNECT,
)


class GameServer:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}        # player_id -> socket
        self.queues = {}         # player_id -> Queue
        self.lanes = {}          # player_id -> LaneGame
        self.ready = {}          # player_id -> bool
        self.phase = "lobby"     # "lobby", "playing", "game_over"
        self.running = True
        self.tick_count = 0

        # Load map
        map_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "maps", "map1.json")
        self.map_data = json.load(open(map_path, 'r'))

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(2)
        self.sock.settimeout(1.0)

        # Get actual IP for display
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "127.0.0.1"

        print(f"Server started on {ip}:{self.port}")
        print("Waiting for 2 players...")

        # Accept connections
        player_id = 0
        while self.running and len(self.clients) < 2:
            try:
                conn, addr = self.sock.accept()
                player_id += 1
                self.clients[player_id] = conn
                self.queues[player_id] = Queue()
                self.ready[player_id] = False

                # Create lane for player
                map_grid = MapGrid(self.map_data["grid"], self.map_data["waypoints"])
                self.lanes[player_id] = LaneGame(map_grid)

                # Send welcome
                welcome = encode_message(MSG_WELCOME, {
                    "player_id": player_id,
                    "map_data": self.map_data,
                })
                conn.sendall(welcome)

                print(f"Player {player_id} connected from {addr}")

                # Notify all about player count
                self._broadcast(MSG_PLAYER_COUNT, {"count": len(self.clients)})

                # Start receiver thread
                t = threading.Thread(target=self._receive_loop, args=(player_id,),
                                     daemon=True)
                t.start()
            except socket.timeout:
                continue

        if len(self.clients) == 2:
            print("Both players connected! Waiting for ready...")
            self._wait_for_ready()
            if self.running:
                self._game_loop()

    def _receive_loop(self, player_id):
        conn = self.clients[player_id]
        buffer = b''
        while self.running:
            try:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data
                messages, buffer = decode_messages(buffer)
                for msg in messages:
                    self.queues[player_id].put(msg)
            except (ConnectionResetError, OSError):
                break

        # Player disconnected
        print(f"Player {player_id} disconnected")
        if self.running:
            opponent = 2 if player_id == 1 else 1
            if opponent in self.clients:
                try:
                    self.clients[opponent].sendall(
                        encode_message(MSG_GAME_OVER, {"winner": opponent}))
                except Exception:
                    pass
            self.running = False

    def _wait_for_ready(self):
        while self.running and not all(self.ready.values()):
            for pid in list(self.queues.keys()):
                try:
                    msg = self.queues[pid].get_nowait()
                    if msg["type"] == MSG_READY:
                        self.ready[pid] = True
                        print(f"Player {pid} is ready!")
                except Empty:
                    pass
            time.sleep(0.05)

        if self.running:
            print("Both players ready! Starting game...")
            self._broadcast(MSG_GAME_START, {})
            for lane in self.lanes.values():
                lane.start_game()

    def _game_loop(self):
        self.phase = "playing"
        tick_interval = 1.0 / SERVER_TICK_RATE

        while self.running and self.phase == "playing":
            start = time.time()

            # Process messages
            for pid in list(self.queues.keys()):
                while True:
                    try:
                        msg = self.queues[pid].get_nowait()
                        self._process_message(pid, msg)
                    except Empty:
                        break

            # Update both lanes
            for lane in self.lanes.values():
                lane.update(tick_interval)

            # Check win/lose
            for pid, lane in self.lanes.items():
                if lane.phase == "game_over" and lane.lives <= 0:
                    opponent = 2 if pid == 1 else 1
                    self._broadcast(MSG_GAME_OVER, {"winner": opponent})
                    self.phase = "game_over"
                    print(f"Player {opponent} wins!")
                    break

            # Broadcast state
            self.tick_count += 1
            if self.tick_count % STATE_BROADCAST_INTERVAL == 0:
                self._broadcast_state()

            # Sleep for remaining tick time
            elapsed = time.time() - start
            sleep_time = tick_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Cleanup
        time.sleep(1)
        self.running = False
        for conn in self.clients.values():
            try:
                conn.close()
            except Exception:
                pass
        self.sock.close()

    def _process_message(self, pid, msg):
        mtype = msg["type"]
        data = msg.get("data", {})
        lane = self.lanes[pid]

        if mtype == MSG_PLACE_TOWER:
            lane.place_tower(data["tower_type"], data["col"], data["row"])
        elif mtype == MSG_SELL_TOWER:
            lane.sell_tower(data["tower_id"])
        elif mtype == MSG_UPGRADE_TOWER:
            lane.upgrade_tower(data["tower_id"])
        elif mtype == MSG_SEND_ENEMY:
            opponent_id = 2 if pid == 1 else 1
            etype = data["enemy_type"]
            count = data["count"]
            cost = ENEMIES[etype]["send_cost"]
            if lane.gold >= cost:
                lane.gold -= cost
                self.lanes[opponent_id].spawn_extra_enemies(etype, count)

    def _broadcast_state(self):
        for pid in self.clients:
            opponent_id = 2 if pid == 1 else 1
            state = {
                "your_state": self.lanes[pid].get_state(),
                "opponent_state": self.lanes[opponent_id].get_state(),
            }
            try:
                self.clients[pid].sendall(encode_message(MSG_GAME_STATE, state))
            except Exception:
                pass

    def _broadcast(self, msg_type, data):
        msg = encode_message(msg_type, data)
        for conn in self.clients.values():
            try:
                conn.sendall(msg)
            except Exception:
                pass


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = GameServer(port=port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.running = False


if __name__ == "__main__":
    main()
