#!/usr/bin/env python3
"""Fantasy Tower Defense VS - Main client."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pygame
import json
import socket

from config.settings import *
from config.tower_data import TOWERS, TOWER_ORDER
from config.enemy_data import ENEMIES, ENEMY_ORDER
from config.wave_data import WAVES
from core.map_grid import MapGrid
from core.game import LaneGame
from ui.renderer import GameRenderer
from network.client import NetworkClient
from network.protocol import (
    MSG_WELCOME, MSG_PLAYER_COUNT, MSG_GAME_START,
    MSG_GAME_STATE, MSG_GAME_OVER,
)

SPEED_OPTIONS = [1, 2, 5]


class TowerDefenseClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Fantasy Tower Defense VS")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.renderer = GameRenderer(self.screen)

        # State
        self.state = "menu"
        self.running = True

        # Single player
        self.game = None
        self.map_grid = None

        # Multiplayer
        self.network = None
        self.player_id = None
        self.lobby_player_count = 0
        self.lobby_ready = False
        self.multi_your_state = None
        self.multi_opp_state = None
        self.multi_map = None
        self.multi_winner = None

        # UI state
        self.selected_tower_type = None
        self.selected_tower_obj = None
        self.ip_text = ""
        self.cursor_timer = 0
        self.cursor_visible = True
        self.game_speed = 1  # 1x, 2x, 5x

        self._build_ui_rects()

    def _build_ui_rects(self):
        hud_y = LANE_Y + LANE_HEIGHT + 5

        # Tower buttons
        self.tower_buttons = []
        start_x = 180
        for i, ttype in enumerate(TOWER_ORDER):
            rect = pygame.Rect(start_x + i * 115, hud_y + 30, 110, 40)
            self.tower_buttons.append((ttype, rect))

        # Send enemy buttons
        self.send_buttons = []
        start_x = 920
        for i, etype in enumerate(ENEMY_ORDER):
            col = i % 2
            row = i // 2
            rect = pygame.Rect(start_x + col * 115, hud_y + 25 + row * 38, 110, 35)
            self.send_buttons.append((etype, rect))

        # Action buttons
        self.action_buttons = [
            ("upgrade", pygame.Rect(640, hud_y + 48, 100, 28)),
            ("sell", pygame.Rect(745, hud_y + 48, 90, 28)),
        ]

        # Speed buttons
        self.speed_buttons = []
        for i, speed in enumerate(SPEED_OPTIONS):
            rect = pygame.Rect(835 + i * 45, hud_y + 30, 40, 28)
            self.speed_buttons.append((speed, rect))

        # Menu buttons
        btn_w, btn_h = 300, 55
        btn_x = (SCREEN_WIDTH - btn_w) // 2
        self.menu_buttons = [
            ("Single Player", pygame.Rect(btn_x, 370, btn_w, btn_h)),
            ("Host Game (VS)", pygame.Rect(btn_x, 440, btn_w, btn_h)),
            ("Join Game (VS)", pygame.Rect(btn_x, 510, btn_w, btn_h)),
            ("Quit", pygame.Rect(btn_x, 580, btn_w, btn_h)),
        ]

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            events = pygame.event.get()

            for event in events:
                if event.type == pygame.QUIT:
                    self.running = False
                    break

            if not self.running:
                break

            # Update effects (always at real dt for smooth visuals)
            self.renderer.update_effects(dt)

            if self.state == "menu":
                self._handle_menu(events)
            elif self.state == "single_playing":
                self._handle_single_player(events, dt)
            elif self.state == "ip_input":
                self._handle_ip_input(events, dt)
            elif self.state == "lobby":
                self._handle_lobby(events)
            elif self.state == "multi_playing":
                self._handle_multiplayer(events, dt)
            elif self.state == "game_over":
                self._handle_game_over(events)

            pygame.display.flip()

        if self.network:
            self.network.disconnect()
        pygame.quit()

    # ── Menu ──────────────────────────────────────────────────

    def _handle_menu(self, events):
        self.renderer.draw_menu(self.menu_buttons)

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for label, rect in self.menu_buttons:
                    if rect.collidepoint(event.pos):
                        if label == "Single Player":
                            self._start_single_player()
                        elif label == "Host Game (VS)":
                            self._start_host()
                        elif label == "Join Game (VS)":
                            self.state = "ip_input"
                            self.ip_text = ""
                        elif label == "Quit":
                            self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    # ── Single Player ─────────────────────────────────────────

    def _start_single_player(self):
        map_path = os.path.join(os.path.dirname(__file__), "maps", "map1.json")
        self.map_grid = MapGrid.load_from_json(map_path)
        self.game = LaneGame(self.map_grid)
        self.selected_tower_type = None
        self.selected_tower_obj = None
        self.game_speed = 1
        self.renderer.effects.clear()
        self.state = "single_playing"

    def _handle_single_player(self, events, dt):
        self.screen.fill(COLOR_BG)

        # Update game with speed multiplier
        game_dt = dt * self.game_speed
        self.game.update(game_dt)

        # Mouse grid
        mx, my = pygame.mouse.get_pos()
        mouse_grid = None
        if LANE1_X <= mx < LANE1_X + LANE_WIDTH and LANE_Y <= my < LANE_Y + LANE_HEIGHT:
            gx = (mx - LANE1_X) // TILE_SIZE
            gy = (my - LANE_Y) // TILE_SIZE
            mouse_grid = (gx, gy)

        # Hover tower
        hover_tower = None
        if mouse_grid and not self.selected_tower_type:
            t = self.game.get_tower_at(mouse_grid[0], mouse_grid[1])
            if t:
                hover_tower = t.to_dict()
                hover_tower["range"] = t.range

        game_state = self.game.get_state()

        # Draw lane
        self.renderer.draw_lane(
            self.map_grid, game_state, LANE1_X, interactive=True,
            selected_tower=self.selected_tower_type,
            mouse_grid=mouse_grid, hover_tower=hover_tower,
        )

        # Opponent lane (empty)
        empty_map = self.map_grid.copy()
        empty_state = {"towers": [], "enemies": [], "projectiles": []}
        self.renderer.draw_lane(empty_map, empty_state, LANE2_X, interactive=False)

        # HUD with speed buttons
        self.renderer.draw_hud(
            game_state, self.selected_tower_type, self.selected_tower_obj,
            self.tower_buttons, self.send_buttons, self.action_buttons,
            speed_buttons=self.speed_buttons, current_speed=self.game_speed,
        )

        # Notifications
        self.renderer.draw_notifications(game_state["notifications"], LANE1_X)

        # Game over
        if self.game.phase == "game_over":
            won = self.game.lives > 0
            self.renderer.draw_single_game_over(won)
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    self.state = "menu"
            return

        # Input
        for event in events:
            if event.type == pygame.KEYDOWN:
                self._handle_single_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_single_click(event, mouse_grid)

    def _handle_single_key(self, event):
        if event.key == pygame.K_ESCAPE:
            if self.selected_tower_type:
                self.selected_tower_type = None
            elif self.selected_tower_obj:
                self.selected_tower_obj = None
            else:
                self.state = "menu"
        elif event.key == pygame.K_SPACE:
            self.game.skip_to_next_wave()
        elif event.key == pygame.K_1:
            self.selected_tower_type = "archer"
            self.selected_tower_obj = None
        elif event.key == pygame.K_2:
            self.selected_tower_type = "wizard"
            self.selected_tower_obj = None
        elif event.key == pygame.K_3:
            self.selected_tower_type = "fire"
            self.selected_tower_obj = None
        elif event.key == pygame.K_4:
            self.selected_tower_type = "ice"
            self.selected_tower_obj = None

    def _handle_single_click(self, event, mouse_grid):
        mx, my = event.pos

        if event.button == 1:
            # Speed buttons
            for speed_val, rect in self.speed_buttons:
                if rect.collidepoint(mx, my):
                    self.game_speed = speed_val
                    return

            # Tower buttons
            for ttype, rect in self.tower_buttons:
                if rect.collidepoint(mx, my):
                    if self.selected_tower_type == ttype:
                        self.selected_tower_type = None
                    else:
                        self.selected_tower_type = ttype
                        self.selected_tower_obj = None
                    return

            # Action buttons
            if self.selected_tower_obj:
                for action, rect in self.action_buttons:
                    if rect.collidepoint(mx, my):
                        if action == "upgrade":
                            self.game.upgrade_tower(self.selected_tower_obj.id)
                        elif action == "sell":
                            self.game.sell_tower(self.selected_tower_obj.id)
                            self.selected_tower_obj = None
                        return

            # Lane click
            if mouse_grid:
                col, row = mouse_grid
                if self.selected_tower_type:
                    self.game.place_tower(self.selected_tower_type, col, row)
                else:
                    tower = self.game.get_tower_at(col, row)
                    self.selected_tower_obj = tower

        elif event.button == 3:
            self.selected_tower_type = None
            self.selected_tower_obj = None

    # ── IP Input ──────────────────────────────────────────────

    def _handle_ip_input(self, events, dt):
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_timer = 0
            self.cursor_visible = not self.cursor_visible

        self.renderer.draw_ip_input(self.ip_text, self.cursor_visible)

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.state = "menu"
                elif event.key == pygame.K_RETURN:
                    ip = self.ip_text.strip() or "127.0.0.1"
                    self._join_game(ip)
                elif event.key == pygame.K_BACKSPACE:
                    self.ip_text = self.ip_text[:-1]
                else:
                    char = event.unicode
                    if char and char in "0123456789.":
                        self.ip_text += char

    # ── Host / Join ───────────────────────────────────────────

    def _start_host(self):
        import subprocess
        server_script = os.path.join(os.path.dirname(__file__), "run_server.py")
        self._server_proc = subprocess.Popen(
            [sys.executable, server_script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        import time
        time.sleep(0.5)

        self.network = NetworkClient()
        if self.network.connect("127.0.0.1", DEFAULT_PORT):
            self.state = "lobby"
            self.lobby_player_count = 0
            self.lobby_ready = False
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self._host_ip = s.getsockname()[0]
                s.close()
            except Exception:
                self._host_ip = "127.0.0.1"
            self._is_host = True
        else:
            self.state = "menu"

    def _join_game(self, host):
        self.network = NetworkClient()
        if self.network.connect(host, DEFAULT_PORT):
            self.state = "lobby"
            self.lobby_player_count = 0
            self.lobby_ready = False
            self._host_ip = host
            self._is_host = False
        else:
            pass

    # ── Lobby ─────────────────────────────────────────────────

    def _handle_lobby(self, events):
        for msg in self.network.get_messages():
            if msg["type"] == MSG_WELCOME:
                self.player_id = msg["data"]["player_id"]
                self.multi_map = MapGrid(
                    msg["data"]["map_data"]["grid"],
                    msg["data"]["map_data"]["waypoints"],
                )
            elif msg["type"] == MSG_PLAYER_COUNT:
                self.lobby_player_count = msg["data"]["count"]
            elif msg["type"] == MSG_GAME_START:
                self.state = "multi_playing"
                self.selected_tower_type = None
                self.selected_tower_obj = None
                self.game_speed = 1
                self.renderer.effects.clear()
                return

        self.renderer.draw_lobby(
            self._host_ip, DEFAULT_PORT, self._is_host,
            self.lobby_player_count, self.lobby_ready,
        )

        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE and not self.lobby_ready:
                    self.lobby_ready = True
                    self.network.send_ready()
                elif event.key == pygame.K_ESCAPE:
                    self.network.disconnect()
                    self.state = "menu"

    # ── Multiplayer Playing ───────────────────────────────────

    def _handle_multiplayer(self, events, dt):
        self.screen.fill(COLOR_BG)

        for msg in self.network.get_messages():
            if msg["type"] == MSG_GAME_STATE:
                self.multi_your_state = msg["data"]["your_state"]
                self.multi_opp_state = msg["data"]["opponent_state"]
            elif msg["type"] == MSG_GAME_OVER:
                self.multi_winner = msg["data"]["winner"]
                self.state = "game_over"

        if not self.multi_your_state:
            return

        mx, my = pygame.mouse.get_pos()
        mouse_grid = None
        if LANE1_X <= mx < LANE1_X + LANE_WIDTH and LANE_Y <= my < LANE_Y + LANE_HEIGHT:
            gx = (mx - LANE1_X) // TILE_SIZE
            gy = (my - LANE_Y) // TILE_SIZE
            mouse_grid = (gx, gy)

        your_map = MapGrid(self.multi_map.grid, self.multi_map.waypoints)
        for t in self.multi_your_state.get("towers", []):
            if 0 <= t["row"] < your_map.rows and 0 <= t["col"] < your_map.cols:
                your_map.grid[t["row"]][t["col"]] = MapGrid.TOWER

        hover_tower = None
        if mouse_grid and not self.selected_tower_type:
            for t in self.multi_your_state.get("towers", []):
                if t["col"] == mouse_grid[0] and t["row"] == mouse_grid[1]:
                    hover_tower = t
                    break

        self.renderer.draw_lane(
            your_map, self.multi_your_state, LANE1_X, interactive=True,
            selected_tower=self.selected_tower_type,
            mouse_grid=mouse_grid, hover_tower=hover_tower,
        )

        opp_map = MapGrid(self.multi_map.grid, self.multi_map.waypoints)
        for t in self.multi_opp_state.get("towers", []):
            if 0 <= t["row"] < opp_map.rows and 0 <= t["col"] < opp_map.cols:
                opp_map.grid[t["row"]][t["col"]] = MapGrid.TOWER
        self.renderer.draw_lane(
            opp_map, self.multi_opp_state, LANE2_X, interactive=False,
        )

        # HUD (no speed buttons in multiplayer - server controls speed)
        self.renderer.draw_hud(
            self.multi_your_state, self.selected_tower_type, None,
            self.tower_buttons, self.send_buttons, self.action_buttons,
        )

        notifs = self.multi_your_state.get("notifications", [])
        self.renderer.draw_notifications(notifs, LANE1_X)

        for event in events:
            if event.type == pygame.KEYDOWN:
                self._handle_multi_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_multi_click(event, mouse_grid)

    def _handle_multi_key(self, event):
        if event.key == pygame.K_ESCAPE:
            if self.selected_tower_type:
                self.selected_tower_type = None
            else:
                self.network.disconnect()
                self.state = "menu"
        elif event.key == pygame.K_1:
            self.selected_tower_type = "archer"
        elif event.key == pygame.K_2:
            self.selected_tower_type = "wizard"
        elif event.key == pygame.K_3:
            self.selected_tower_type = "fire"
        elif event.key == pygame.K_4:
            self.selected_tower_type = "ice"

    def _handle_multi_click(self, event, mouse_grid):
        mx, my = event.pos

        if event.button == 1:
            for ttype, rect in self.tower_buttons:
                if rect.collidepoint(mx, my):
                    self.selected_tower_type = ttype if self.selected_tower_type != ttype else None
                    return

            for etype, rect in self.send_buttons:
                if rect.collidepoint(mx, my):
                    stats = ENEMIES[etype]
                    if self.multi_your_state and self.multi_your_state["gold"] >= stats["send_cost"]:
                        self.network.send_enemy(etype, stats["send_count"])
                    return

            if mouse_grid and self.selected_tower_type:
                col, row = mouse_grid
                self.network.send_place_tower(self.selected_tower_type, col, row)

        elif event.button == 3:
            self.selected_tower_type = None

    # ── Game Over ─────────────────────────────────────────────

    def _handle_game_over(self, events):
        if self.multi_your_state:
            self.screen.fill(COLOR_BG)
            your_map = MapGrid(self.multi_map.grid, self.multi_map.waypoints)
            self.renderer.draw_lane(your_map, self.multi_your_state, LANE1_X,
                                    interactive=False)
            opp_map = MapGrid(self.multi_map.grid, self.multi_map.waypoints)
            self.renderer.draw_lane(opp_map, self.multi_opp_state, LANE2_X,
                                    interactive=False)

        is_winner = self.multi_winner == self.player_id
        self.renderer.draw_game_over(self.multi_winner, is_winner)

        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if self.network:
                    self.network.disconnect()
                    self.network = None
                self.state = "menu"


def main():
    client = TowerDefenseClient()
    client.run()


if __name__ == "__main__":
    main()
