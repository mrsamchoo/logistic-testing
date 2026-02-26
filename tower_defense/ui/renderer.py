import pygame
import math
import random
from config.settings import *
from config.tower_data import TOWERS, TOWER_ORDER
from config.enemy_data import ENEMIES, ENEMY_ORDER
from ui.effects import EffectsManager
from ui.sprites import SpriteFactory


class GameRenderer:
    """Renders the full game screen with pre-rendered sprites and effects."""

    def __init__(self, screen):
        self.screen = screen
        self.font_large = pygame.font.SysFont("arial", 28, bold=True)
        self.font_med = pygame.font.SysFont("arial", 20, bold=True)
        self.font_small = pygame.font.SysFont("arial", 16)
        self.font_tiny = pygame.font.SysFont("arial", 13)
        self.lane_surface = pygame.Surface((LANE_WIDTH, LANE_HEIGHT))
        self.range_surface = pygame.Surface((LANE_WIDTH, LANE_HEIGHT), pygame.SRCALPHA)
        self.effects = EffectsManager()
        self.sprites = SpriteFactory()
        self.anim_time = 0.0
        self.anim_frame = 0
        self._frame_timer = 0.0
        self._decorations = {}  # lane_key -> [(x, y, deco_type)]
        self._prev_enemy_ids = set()  # track for death detection
        self._known_enemy_ids = set()  # track for spawn detection

    def update_effects(self, dt):
        self.anim_time += dt
        self._frame_timer += dt
        if self._frame_timer >= 0.15:
            self._frame_timer -= 0.15
            self.anim_frame = (self.anim_frame + 1) % 4
        self.effects.update(dt)

    def _get_decorations(self, map_grid, key):
        """Generate decorations for a map (cached by key)."""
        if key not in self._decorations:
            decos = []
            random.seed(hash(key) + 42)
            for row in range(map_grid.rows):
                for col in range(map_grid.cols):
                    if map_grid.grid[row][col] != 0:
                        continue
                    r = random.random()
                    px = col * TILE_SIZE + random.randint(4, TILE_SIZE - 4)
                    py = row * TILE_SIZE + random.randint(4, TILE_SIZE - 4)
                    if r < 0.04:
                        decos.append((px - 10, py - 20, "tree"))
                    elif r < 0.08:
                        decos.append((px - 7, py - 3, "rock"))
                    elif r < 0.14:
                        decos.append((px - 8, py - 4, "bush"))
                    elif r < 0.17:
                        decos.append((px - 5, py - 6, "mushroom"))
            random.seed()
            self._decorations[key] = decos
        return self._decorations[key]

    # ── Lane Drawing ──────────────────────────────────────────

    def draw_lane(self, map_grid, game_state, offset_x, interactive=True,
                  selected_tower=None, mouse_grid=None, hover_tower=None):
        surf = self.lane_surface
        surf.fill((25, 100, 25))

        # Draw tiles with pre-rendered sprites
        for row in range(map_grid.rows):
            for col in range(map_grid.cols):
                x = col * TILE_SIZE
                y = row * TILE_SIZE
                cell = map_grid.grid[row][col]
                variant = (row * 7 + col * 13) % 4
                if cell == map_grid.PATH:
                    tile = self.sprites.get_tile("path", variant)
                else:
                    tile = self.sprites.get_tile("grass", variant)
                if tile:
                    surf.blit(tile, (x, y))

        # Draw decorations (trees, rocks, etc.)
        key = "lane1" if interactive else "lane2"
        for dx, dy, dtype in self._get_decorations(map_grid, key):
            deco = self.sprites.get_decoration(dtype)
            if deco:
                surf.blit(deco, (dx, dy))

        # Draw tower shadows first, then towers
        towers = game_state.get("towers", [])
        for t in towers:
            shadow = self.sprites.get_shadow("medium")
            if shadow:
                sx = t["col"] * TILE_SIZE + (TILE_SIZE - shadow.get_width()) // 2
                sy = t["row"] * TILE_SIZE + TILE_SIZE - shadow.get_height()
                surf.blit(shadow, (sx, sy))

        for t in towers:
            self._draw_tower(surf, t)
            if interactive:
                self.effects.spawn_tower_idle_particles(
                    t["type"], t["pixel_x"], t["pixel_y"], t["id"])

        # Range circle
        if hover_tower:
            self.range_surface.fill((0, 0, 0, 0))
            r = int(hover_tower["range"])
            # Multi-ring glow
            for ring_r, ring_a in [(r, 25), (r - 3, 15), (r + 3, 10)]:
                pygame.draw.circle(self.range_surface, (255, 255, 255, ring_a),
                                   (hover_tower["pixel_x"], hover_tower["pixel_y"]), ring_r, 2)
            # Fill
            pygame.draw.circle(self.range_surface, (255, 255, 255, 12),
                               (hover_tower["pixel_x"], hover_tower["pixel_y"]), r)
            surf.blit(self.range_surface, (0, 0))

        # Placement preview
        if interactive and selected_tower and mouse_grid:
            mc, mr = mouse_grid
            if 0 <= mc < map_grid.cols and 0 <= mr < map_grid.rows:
                can = map_grid.can_place_tower(mc, mr)
                # Preview with tower sprite
                prev_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                twr = self.sprites.get_tower(selected_tower, 1)
                if twr:
                    prev_surf.blit(twr, (0, 0))
                overlay_c = (0, 255, 0, 60) if can else (255, 0, 0, 60)
                prev_surf.fill(overlay_c, special_flags=pygame.BLEND_RGBA_ADD)
                prev_surf.set_alpha(160)
                surf.blit(prev_surf, (mc * TILE_SIZE, mr * TILE_SIZE))
                if can:
                    stats = TOWERS[selected_tower]
                    cx = mc * TILE_SIZE + TILE_SIZE // 2
                    cy = mr * TILE_SIZE + TILE_SIZE // 2
                    self.range_surface.fill((0, 0, 0, 0))
                    pygame.draw.circle(self.range_surface, (255, 255, 255, 20),
                                       (cx, cy), stats["range"])
                    pygame.draw.circle(self.range_surface, (255, 255, 255, 40),
                                       (cx, cy), stats["range"], 1)
                    surf.blit(self.range_surface, (0, 0))

        # Draw enemy shadows, then enemies
        enemies = game_state.get("enemies", [])

        # Trigger death and spawn effects (only for interactive lane)
        if interactive:
            current_ids = set(e["id"] for e in enemies)

            # Spawn effects for new enemies
            for e in enemies:
                if e["id"] not in self._known_enemy_ids:
                    self.effects.spawn_entry_effect(e["x"], e["y"], e["type"])

            # Death effects from game state
            for x, y, etype in game_state.get("recently_dead", []):
                self.effects.spawn_death_effect(x, y, etype)

            self._prev_enemy_ids = current_ids
            self._known_enemy_ids |= current_ids

        for e in enemies:
            etype = e["type"]
            stats = ENEMIES[etype]
            shadow_size = "small" if etype == "goblin" else (
                "large" if etype == "dragon" else "medium")
            shadow = self.sprites.get_shadow(shadow_size)
            if shadow:
                sx = int(e["x"]) - shadow.get_width() // 2
                sy = int(e["y"]) + stats["radius"] - 2
                if etype == "dragon":
                    sy += 6  # flying higher
                surf.blit(shadow, (sx, sy))

        for e in enemies:
            self._draw_enemy(surf, e)
            if interactive:
                effects = e.get("effects", [])
                if "burn" in effects and random.random() < 0.3:
                    self.effects.spawn_burn_particles(e["x"], e["y"])
                if "slow" in effects and random.random() < 0.15:
                    self.effects.spawn_frozen_particles(e["x"], e["y"])

        # Draw projectiles
        projectiles = game_state.get("projectiles", [])
        for p in projectiles:
            self._draw_projectile(surf, p)
            if interactive:
                self._spawn_projectile_trail(p)

        # Draw particle effects
        self.effects.draw(surf)

        # Dim opponent's lane with gradient
        if not interactive:
            dim = pygame.Surface((LANE_WIDTH, LANE_HEIGHT), pygame.SRCALPHA)
            dim.fill((0, 0, 20, 45))
            surf.blit(dim, (0, 0))

        self.screen.blit(surf, (offset_x, LANE_Y))

        # Lane border (gradient effect)
        border_rect = (offset_x, LANE_Y, LANE_WIDTH, LANE_HEIGHT)
        c = (120, 120, 150) if interactive else (80, 80, 100)
        pygame.draw.rect(self.screen, c, border_rect, 2)
        # Corner accents
        for corner in [(offset_x, LANE_Y), (offset_x + LANE_WIDTH - 8, LANE_Y),
                        (offset_x, LANE_Y + LANE_HEIGHT - 8),
                        (offset_x + LANE_WIDTH - 8, LANE_Y + LANE_HEIGHT - 8)]:
            pygame.draw.rect(self.screen, COLOR_GOLD, (*corner, 8, 8), 1)

        label = "YOUR LANE" if interactive else "OPPONENT"
        label_bg = pygame.Surface((90, 18), pygame.SRCALPHA)
        label_bg.fill((0, 0, 0, 120))
        self.screen.blit(label_bg, (offset_x + 3, LANE_Y + 2))
        text = self.font_tiny.render(label, True, COLOR_GOLD if interactive else COLOR_TEXT_DIM)
        self.screen.blit(text, (offset_x + 6, LANE_Y + 3))

    # ── Tower Drawing ─────────────────────────────────────────

    def _draw_tower(self, surf, t):
        sprite = self.sprites.get_tower(t["type"], t["level"])
        if sprite:
            x = t["col"] * TILE_SIZE
            y = t["row"] * TILE_SIZE
            surf.blit(sprite, (x, y))

            # Animated overlay effects per tower type
            cx, cy = t["pixel_x"], t["pixel_y"]
            ttype = t["type"]

            if ttype == "fire":
                # Animated flame flicker
                for i in range(2):
                    fx = cx - 3 + i * 4 + math.sin(self.anim_time * 10 + i * 2) * 2
                    fy = y + 2 + math.sin(self.anim_time * 12 + i) * 1
                    fc = [(255, 220, 80), (255, 140, 30)][i]
                    pts = [(fx, fy), (fx - 2, fy + 4), (fx + 2, fy + 4)]
                    pygame.draw.polygon(surf, fc, pts)

            elif ttype == "wizard":
                # Orbiting sparkle
                angle = self.anim_time * 3
                ox = cx + math.cos(angle) * 8
                oy = cy - 6 + math.sin(angle) * 4
                glow = pygame.Surface((8, 8), pygame.SRCALPHA)
                alpha = int(150 + math.sin(self.anim_time * 5) * 80)
                pygame.draw.circle(glow, (200, 150, 255, min(255, alpha)), (4, 4), 3)
                surf.blit(glow, (int(ox) - 4, int(oy) - 4))

            elif ttype == "ice":
                # Frost shimmer
                alpha = int(80 + math.sin(self.anim_time * 4) * 40)
                shimmer = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                pygame.draw.circle(shimmer, (200, 240, 255, alpha), (TILE_SIZE // 2, 16), 12, 1)
                surf.blit(shimmer, (x, y))

    # ── Enemy Drawing ─────────────────────────────────────────

    def _draw_enemy(self, surf, e):
        x, y = int(e["x"]), int(e["y"])
        etype = e["type"]
        frame = self.anim_frame

        sprite = self.sprites.get_enemy_frame(etype, frame)
        if sprite:
            sx = x - sprite.get_width() // 2
            sy = y - sprite.get_height() // 2
            if etype == "dragon":
                sy -= 4  # lift dragon slightly
            surf.blit(sprite, (sx, sy))

        # Status effect overlays
        stats = ENEMIES[etype]
        radius = stats["radius"]
        effects = e.get("effects", [])

        if "slow" in effects:
            frost_s = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
            alpha = 80 + int(math.sin(self.anim_time * 6) * 30)
            cx, cy_f = radius * 2, radius * 2
            pygame.draw.circle(frost_s, (100, 200, 255, alpha), (cx, cy_f), radius + 5, 2)
            # Ice crystal overlay
            for a_deg in range(0, 360, 60):
                a = math.radians(a_deg + self.anim_time * 30)
                ex = cx + int(math.cos(a) * (radius + 3))
                ey = cy_f + int(math.sin(a) * (radius + 3))
                pygame.draw.circle(frost_s, (200, 240, 255, alpha), (ex, ey), 1)
            surf.blit(frost_s, (x - radius * 2, y - radius * 2))

        if "burn" in effects:
            fire_s = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
            alpha = 100 + int(math.sin(self.anim_time * 8) * 50)
            cx_f, cy_f = radius * 2, radius * 2
            pygame.draw.circle(fire_s, (255, 100, 0, alpha), (cx_f, cy_f), radius + 3, 2)
            surf.blit(fire_s, (x - radius * 2, y - radius * 2))

        # HP bar (nicer)
        hp_ratio = e["hp"] / e["max_hp"]
        bar_w = max(16, radius * 2 + 8)
        bar_h = 4
        bar_x = x - bar_w // 2
        bar_y = y - radius - 12
        if etype == "dragon":
            bar_y -= 8
            bar_w = 28
            bar_x = x - 14
        # Background
        pygame.draw.rect(surf, (20, 20, 20), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(surf, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h))
        # HP fill with gradient
        hp_w = int(bar_w * hp_ratio)
        if hp_w > 0:
            if hp_ratio > 0.5:
                hp_c1, hp_c2 = (50, 220, 50), (30, 180, 30)
            elif hp_ratio > 0.25:
                hp_c1, hp_c2 = (220, 200, 30), (180, 160, 20)
            else:
                hp_c1, hp_c2 = (220, 40, 30), (180, 20, 15)
            for px in range(hp_w):
                t = px / max(1, hp_w - 1)
                c = tuple(int(hp_c1[i] + (hp_c2[i] - hp_c1[i]) * t) for i in range(3))
                pygame.draw.line(surf, c, (bar_x + px, bar_y), (bar_x + px, bar_y + bar_h - 1))
            # Shine on top
            pygame.draw.line(surf, (255, 255, 255),
                             (bar_x, bar_y), (bar_x + hp_w - 1, bar_y))

    # ── Projectile Drawing ────────────────────────────────────

    def _draw_projectile(self, surf, p):
        x, y = int(p["x"]), int(p["y"])
        ttype = p.get("tower_type", "archer")
        sprite = self.sprites.get_projectile(ttype)
        if sprite:
            surf.blit(sprite, (x - sprite.get_width() // 2, y - sprite.get_height() // 2))

    def _spawn_projectile_trail(self, p):
        x, y = p["x"], p["y"]
        ttype = p.get("tower_type", "archer")
        if ttype == "archer":
            self.effects.spawn_arrow_trail(x, y)
        elif ttype == "wizard":
            self.effects.spawn_magic_trail(x, y)
        elif ttype == "fire":
            self.effects.spawn_fire_trail(x, y)
        elif ttype == "ice":
            self.effects.spawn_ice_trail(x, y)

    # ── HUD Drawing ───────────────────────────────────────────

    def draw_hud(self, game_state, selected_tower_type, selected_tower_obj,
                 tower_buttons, send_buttons, action_buttons,
                 speed_buttons=None, current_speed=1):
        hud_y = LANE_Y + LANE_HEIGHT + 5

        # HUD background with gradient
        for row in range(HUD_HEIGHT):
            t = row / max(1, HUD_HEIGHT - 1)
            c = tuple(int(35 + (20 - 35) * t) for _ in range(1)) * 2 + (int(50 + (35 - 50) * t),)
            pygame.draw.line(self.screen, c, (0, hud_y + row), (SCREEN_WIDTH, hud_y + row))
        # Top border glow
        for i in range(3):
            alpha = 100 - i * 30
            c = (80 + i * 10, 80 + i * 10, 130 + i * 10)
            pygame.draw.line(self.screen, c, (0, hud_y + i), (SCREEN_WIDTH, hud_y + i))

        # Gold with icon
        pygame.draw.circle(self.screen, COLOR_GOLD, (28, hud_y + 16), 8)
        pygame.draw.circle(self.screen, (200, 170, 0), (28, hud_y + 16), 6)
        g_text = self.font_tiny.render("G", True, (100, 80, 0))
        self.screen.blit(g_text, (24, hud_y + 10))
        gold_text = self.font_med.render(f"{game_state['gold']}", True, COLOR_GOLD)
        self.screen.blit(gold_text, (42, hud_y + 6))

        # Lives with heart
        heart_c = COLOR_HP_BAR_LOW if game_state["lives"] <= 5 else (220, 60, 80)
        hx, hy = 20, hud_y + 37
        pygame.draw.circle(self.screen, heart_c, (hx, hy), 4)
        pygame.draw.circle(self.screen, heart_c, (hx + 6, hy), 4)
        pygame.draw.polygon(self.screen, heart_c, [(hx - 4, hy + 1), (hx + 3, hy + 8), (hx + 10, hy + 1)])
        lives_text = self.font_med.render(
            f"{game_state['lives']}/{STARTING_LIVES}", True,
            COLOR_TEXT if game_state["lives"] > 5 else COLOR_HP_BAR_LOW)
        self.screen.blit(lives_text, (42, hud_y + 32))

        # Wave with sword icon
        wave_num = game_state["wave_number"] + 1
        from config.wave_data import WAVES
        pygame.draw.line(self.screen, (180, 180, 200), (22, hud_y + 62), (30, hud_y + 72), 2)
        pygame.draw.line(self.screen, (140, 140, 160), (18, hud_y + 68), (34, hud_y + 68), 2)
        wave_text = self.font_med.render(f"{wave_num}/{len(WAVES)}", True, COLOR_TEXT)
        self.screen.blit(wave_text, (42, hud_y + 60))

        # Phase info
        phase = game_state["phase"]
        if phase == "between_waves":
            timer = game_state.get("between_wave_timer", 0)
            # Timer bar
            bar_w = 120
            bar_x = 180
            bar_y_pos = hud_y + 12
            ratio = timer / 10.0
            pygame.draw.rect(self.screen, (40, 40, 55), (bar_x, bar_y_pos, bar_w, 8))
            pygame.draw.rect(self.screen, (80, 180, 80), (bar_x, bar_y_pos, int(bar_w * ratio), 8))
            pygame.draw.rect(self.screen, (100, 100, 130), (bar_x, bar_y_pos, bar_w, 8), 1)
            phase_text = self.font_tiny.render(
                f"Next wave: {timer:.0f}s [SPACE]", True, COLOR_TEXT_DIM)
            self.screen.blit(phase_text, (bar_x, bar_y_pos + 10))
        elif phase == "waiting":
            # Pulsing text
            alpha = int(180 + math.sin(self.anim_time * 4) * 75)
            phase_text = self.font_small.render("Press SPACE to start!", True, COLOR_GOLD)
            phase_text.set_alpha(alpha)
            self.screen.blit(phase_text, (180, hud_y + 8))

        # Tower buttons
        self._draw_tower_buttons(tower_buttons, selected_tower_type, game_state["gold"])
        if selected_tower_obj:
            self._draw_tower_info(selected_tower_obj, action_buttons, hud_y, game_state["gold"])
        self._draw_send_buttons(send_buttons, game_state["gold"], hud_y)
        if speed_buttons:
            self._draw_speed_buttons(speed_buttons, current_speed, hud_y)

    def _draw_tower_buttons(self, buttons, selected_type, gold):
        for i, (tower_type, rect) in enumerate(buttons):
            stats = TOWERS[tower_type]
            is_selected = tower_type == selected_type
            can_afford = gold >= stats["cost"]

            # Button with gradient
            if is_selected:
                c1, c2 = (70, 70, 140), (55, 55, 110)
            elif can_afford:
                c1, c2 = (55, 55, 85), (40, 40, 65)
            else:
                c1, c2 = (35, 35, 45), (25, 25, 35)
            for row in range(rect.h):
                t = row / max(1, rect.h - 1)
                c = tuple(int(c1[j] + (c2[j] - c1[j]) * t) for j in range(3))
                pygame.draw.line(self.screen, c, (rect.x, rect.y + row),
                                 (rect.x + rect.w - 1, rect.y + row))
            border_c = COLOR_GOLD if is_selected else (
                (100, 100, 140) if can_afford else (60, 60, 70))
            pygame.draw.rect(self.screen, border_c, rect, 2, border_radius=4)

            # Tower mini sprite
            icon = self.sprites.get_tower(tower_type, 1)
            if icon:
                mini = pygame.transform.scale(icon, (22, 22))
                self.screen.blit(mini, (rect.x + 4, rect.y + 9))

            name = self.font_tiny.render(stats["name"], True,
                                          COLOR_TEXT if can_afford else (80, 80, 80))
            cost = self.font_tiny.render(f"{stats['cost']}g", True,
                                          COLOR_GOLD if can_afford else (80, 80, 80))
            self.screen.blit(name, (rect.x + 28, rect.y + 4))
            self.screen.blit(cost, (rect.x + 28, rect.y + 20))
            hotkey = self.font_tiny.render(f"[{i+1}]", True, COLOR_TEXT_DIM)
            self.screen.blit(hotkey, (rect.x + rect.w - 22, rect.y + 4))

    def _draw_tower_info(self, tower, action_buttons, hud_y, gold):
        x = 640
        y = hud_y + 5
        stats = TOWERS[tower.tower_type]
        # Tower icon
        icon = self.sprites.get_tower(tower.tower_type, tower.level)
        if icon:
            self.screen.blit(icon, (x, y))
        info = self.font_small.render(
            f"{stats['name']} Lv.{tower.level}", True, COLOR_TEXT)
        self.screen.blit(info, (x + 44, y + 2))
        dmg = self.font_tiny.render(
            f"DMG:{tower.damage} RNG:{tower.range}", True, COLOR_TEXT_DIM)
        self.screen.blit(dmg, (x + 44, y + 22))

        for action, rect in action_buttons:
            if action == "upgrade":
                cost = tower.get_upgrade_cost()
                can = tower.can_upgrade() and gold >= cost
                label = f"Upgrade ({cost}g)" if tower.can_upgrade() else "MAX"
            elif action == "sell":
                can = True
                label = f"Sell ({tower.get_sell_value()}g)"
            else:
                continue
            bg = (55, 55, 85) if can else (35, 35, 45)
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            pygame.draw.rect(self.screen, (100, 100, 130) if can else (50, 50, 60),
                             rect, 1, border_radius=4)
            text = self.font_tiny.render(label, True, COLOR_TEXT if can else (70, 70, 70))
            tx = rect.x + (rect.w - text.get_width()) // 2
            ty = rect.y + (rect.h - text.get_height()) // 2
            self.screen.blit(text, (tx, ty))

    def _draw_send_buttons(self, buttons, gold, hud_y):
        header = self.font_small.render("SEND:", True, (255, 100, 100))
        self.screen.blit(header, (920, hud_y + 6))

        for etype, rect in buttons:
            stats = ENEMIES[etype]
            can_afford = gold >= stats["send_cost"]
            bg = (70, 35, 35) if can_afford else (35, 25, 25)
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            pygame.draw.rect(self.screen, (120, 55, 55) if can_afford else (60, 40, 40),
                             rect, 1, border_radius=4)

            # Mini enemy sprite
            enemy_sprite = self.sprites.get_enemy_frame(etype, 0)
            if enemy_sprite:
                mini = pygame.transform.scale(enemy_sprite,
                                               (int(enemy_sprite.get_width() * 0.5),
                                                int(enemy_sprite.get_height() * 0.5)))
                self.screen.blit(mini, (rect.x + 2, rect.y + (rect.h - mini.get_height()) // 2))

            label = f"{stats['name']}"
            if stats["send_count"] > 1:
                label += f" x{stats['send_count']}"
            text = self.font_tiny.render(label, True,
                                          COLOR_TEXT if can_afford else (70, 70, 70))
            self.screen.blit(text, (rect.x + 20, rect.y + 3))
            cost_text = self.font_tiny.render(f"{stats['send_cost']}g", True,
                                               COLOR_GOLD if can_afford else (60, 60, 60))
            self.screen.blit(cost_text, (rect.x + 20, rect.y + 18))

    def _draw_speed_buttons(self, buttons, current_speed, hud_y):
        header = self.font_tiny.render("SPEED", True, COLOR_TEXT_DIM)
        self.screen.blit(header, (843, hud_y + 20))

        for speed_val, rect in buttons:
            is_active = speed_val == current_speed
            if is_active:
                c1, c2 = (60, 110, 60), (45, 85, 45)
                border = COLOR_GOLD
            else:
                c1, c2 = (45, 45, 60), (35, 35, 48)
                border = (70, 70, 90)
            for row in range(rect.h):
                t = row / max(1, rect.h - 1)
                c = tuple(int(c1[j] + (c2[j] - c1[j]) * t) for j in range(3))
                pygame.draw.line(self.screen, c, (rect.x, rect.y + row),
                                 (rect.x + rect.w - 1, rect.y + row))
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=3)
            label = f"{speed_val}x"
            text = self.font_small.render(label, True,
                                          COLOR_GOLD if is_active else COLOR_TEXT_DIM)
            tx = rect.x + (rect.w - text.get_width()) // 2
            ty = rect.y + (rect.h - text.get_height()) // 2
            self.screen.blit(text, (tx, ty))

    # ── Notifications ─────────────────────────────────────────

    def draw_notifications(self, notifications, offset_x):
        y = LANE_Y + 40
        for text_str, remaining in notifications:
            alpha = min(255, int(remaining * 255 / 0.5)) if remaining < 0.5 else 255
            # Background banner
            text_surf = self.font_med.render(text_str, True, COLOR_GOLD)
            tw = text_surf.get_width()
            banner = pygame.Surface((tw + 30, 28), pygame.SRCALPHA)
            banner.fill((0, 0, 0, int(alpha * 0.5)))
            banner.blit(text_surf, (15, 3))
            banner.set_alpha(alpha)
            tx = offset_x + (LANE_WIDTH - tw - 30) // 2
            self.screen.blit(banner, (tx, y))
            y += 34

    # ── Menu Screens ──────────────────────────────────────────

    def draw_menu(self, menu_buttons):
        # Background with gradient
        for row in range(SCREEN_HEIGHT):
            t = row / SCREEN_HEIGHT
            c = (int(15 + 10 * t), int(15 + 5 * t), int(30 + 15 * t))
            pygame.draw.line(self.screen, c, (0, row), (SCREEN_WIDTH, row))

        # Title with glow
        title_text = "FANTASY TOWER DEFENSE VS"
        glow = self.font_large.render(title_text, True, (100, 80, 0))
        self.screen.blit(glow, ((SCREEN_WIDTH - glow.get_width()) // 2 + 1, 81))
        title = self.font_large.render(title_text, True, COLOR_GOLD)
        self.screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 80))

        subtitle = self.font_med.render("Dragon & Wizard Edition", True, (140, 140, 160))
        self.screen.blit(subtitle, ((SCREEN_WIDTH - subtitle.get_width()) // 2, 125))

        # Tower showcase
        for i, ttype in enumerate(TOWER_ORDER):
            x = 170 + i * 250
            y = 210
            sprite = self.sprites.get_tower(ttype, 2)
            if sprite:
                big = pygame.transform.scale(sprite, (64, 64))
                self.screen.blit(big, (x, y))
            stats = TOWERS[ttype]
            name = self.font_small.render(stats["name"], True, COLOR_TEXT_DIM)
            self.screen.blit(name, (x + 32 - name.get_width() // 2, y + 70))

        # Enemy showcase
        for i, etype in enumerate(ENEMY_ORDER):
            x = 170 + i * 250 + 80
            y = 230
            sprite = self.sprites.get_enemy_frame(etype, 0)
            if sprite:
                big = pygame.transform.scale(sprite, (
                    int(sprite.get_width() * 1.5), int(sprite.get_height() * 1.5)))
                self.screen.blit(big, (x, y))

        # Menu buttons
        for label, rect in menu_buttons:
            # Gradient button
            for row in range(rect.h):
                t = row / max(1, rect.h - 1)
                c = (int(50 - 15 * t), int(50 - 15 * t), int(80 - 20 * t))
                pygame.draw.line(self.screen, c, (rect.x, rect.y + row),
                                 (rect.x + rect.w - 1, rect.y + row))
            pygame.draw.rect(self.screen, COLOR_GOLD, rect, 2, border_radius=6)
            text = self.font_med.render(label, True, COLOR_TEXT)
            tx = rect.x + (rect.w - text.get_width()) // 2
            ty = rect.y + (rect.h - text.get_height()) // 2
            self.screen.blit(text, (tx, ty))

    def draw_lobby(self, host_ip, port, is_host, player_count, ready):
        for row in range(SCREEN_HEIGHT):
            t = row / SCREEN_HEIGHT
            c = (int(15 + 10 * t), int(15 + 5 * t), int(30 + 15 * t))
            pygame.draw.line(self.screen, c, (0, row), (SCREEN_WIDTH, row))

        title = self.font_large.render("LOBBY", True, COLOR_GOLD)
        self.screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 60))

        info = self.font_med.render(
            f"Server: {host_ip}:{port}" if is_host else "Connected to server", True, COLOR_TEXT)
        self.screen.blit(info, ((SCREEN_WIDTH - info.get_width()) // 2, 140))

        players = self.font_med.render(f"Players: {player_count}/2", True, COLOR_TEXT)
        self.screen.blit(players, ((SCREEN_WIDTH - players.get_width()) // 2, 200))

        if player_count == 2:
            msg = "Waiting for opponent..." if ready else "Press SPACE when ready!"
            c = COLOR_TEXT_DIM if ready else COLOR_GOLD
        else:
            msg, c = "Waiting for opponent to connect...", COLOR_TEXT_DIM
        wait = self.font_med.render(msg, True, c)
        self.screen.blit(wait, ((SCREEN_WIDTH - wait.get_width()) // 2, 280))

    def draw_game_over(self, winner, is_you):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        text = "VICTORY!" if is_you else "DEFEAT!"
        color = COLOR_GOLD if is_you else COLOR_HP_BAR_LOW
        # Glow
        glow = self.font_large.render(text, True, (color[0] // 2, color[1] // 2, color[2] // 2))
        self.screen.blit(glow, ((SCREEN_WIDTH - glow.get_width()) // 2 + 2, 252))
        title = self.font_large.render(text, True, color)
        self.screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 250))

        restart = self.font_med.render("Press SPACE to return to menu", True, COLOR_TEXT_DIM)
        self.screen.blit(restart, ((SCREEN_WIDTH - restart.get_width()) // 2, 330))

    def draw_single_game_over(self, won):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        text = "YOU WIN! All waves cleared!" if won else "GAME OVER!"
        color = COLOR_GOLD if won else COLOR_HP_BAR_LOW
        glow = self.font_large.render(text, True, (color[0] // 2, color[1] // 2, color[2] // 2))
        self.screen.blit(glow, ((SCREEN_WIDTH - glow.get_width()) // 2 + 2, 282))
        title = self.font_large.render(text, True, color)
        self.screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 280))

        restart = self.font_med.render("Press SPACE to return to menu", True, COLOR_TEXT_DIM)
        self.screen.blit(restart, ((SCREEN_WIDTH - restart.get_width()) // 2, 350))

    def draw_ip_input(self, ip_text, cursor_visible):
        for row in range(SCREEN_HEIGHT):
            t = row / SCREEN_HEIGHT
            c = (int(15 + 10 * t), int(15 + 5 * t), int(30 + 15 * t))
            pygame.draw.line(self.screen, c, (0, row), (SCREEN_WIDTH, row))

        title = self.font_large.render("JOIN GAME", True, COLOR_GOLD)
        self.screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 100))

        prompt = self.font_med.render("Enter server IP address:", True, COLOR_TEXT)
        self.screen.blit(prompt, ((SCREEN_WIDTH - prompt.get_width()) // 2, 220))

        box_w, box_h = 400, 50
        box_x = (SCREEN_WIDTH - box_w) // 2
        box_y = 280
        # Input box gradient
        for row in range(box_h):
            t = row / box_h
            c = (int(35 + 15 * t), int(35 + 15 * t), int(55 + 15 * t))
            pygame.draw.line(self.screen, c, (box_x, box_y + row), (box_x + box_w, box_y + row))
        pygame.draw.rect(self.screen, COLOR_GOLD, (box_x, box_y, box_w, box_h), 2, border_radius=5)

        display_text = ip_text + ("|" if cursor_visible else "")
        text_surf = self.font_med.render(display_text, True, COLOR_TEXT)
        self.screen.blit(text_surf, (box_x + 15, box_y + 12))

        hint = self.font_small.render("Press ENTER to connect, ESC to go back",
                                      True, COLOR_TEXT_DIM)
        self.screen.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, 350))
