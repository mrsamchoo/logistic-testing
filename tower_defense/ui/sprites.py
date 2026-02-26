"""
Pre-rendered sprite factory.
All game sprites are generated once at startup using layered drawing
with gradients, shadows, and highlights for premium pixel-art look.
"""
import pygame
import math
import random

from config.settings import TILE_SIZE

# ── Utility Functions ─────────────────────────────────────

def _radial_gradient(size, center_color, edge_color, radius=None):
    """Create a radial gradient surface."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    if radius is None:
        radius = size // 2
    for r in range(radius, 0, -1):
        t = r / radius
        c = tuple(int(center_color[i] + (edge_color[i] - center_color[i]) * t)
                  for i in range(min(len(center_color), len(edge_color))))
        if len(c) == 3:
            c = (*c, 255)
        pygame.draw.circle(surf, c, (cx, cy), r)
    return surf


def _draw_gradient_rect(surf, rect, top_color, bottom_color):
    """Draw a vertical gradient rectangle."""
    x, y, w, h = rect
    for row in range(h):
        t = row / max(1, h - 1)
        c = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t)
                  for i in range(3))
        pygame.draw.line(surf, c, (x, y + row), (x + w - 1, y + row))


def _draw_gradient_circle(surf, cx, cy, radius, inner_color, outer_color):
    """Draw a radial gradient circle."""
    for r in range(radius, 0, -1):
        t = 1.0 - (r / radius)
        c = tuple(int(outer_color[i] + (inner_color[i] - outer_color[i]) * t)
                  for i in range(3))
        pygame.draw.circle(surf, c, (cx, cy), r)


def _add_noise(surf, intensity=15, alpha=60):
    """Add subtle noise texture."""
    w, h = surf.get_size()
    noise = pygame.Surface((w, h), pygame.SRCALPHA)
    for _ in range(int(w * h * 0.08)):
        nx = random.randint(0, w - 1)
        ny = random.randint(0, h - 1)
        v = random.randint(-intensity, intensity)
        a = random.randint(alpha // 2, alpha)
        c = (128 + v, 128 + v, 128 + v, a)
        noise.set_at((nx, ny), c)
    surf.blit(noise, (0, 0))


class SpriteFactory:
    """Generates and caches all game sprites."""

    def __init__(self):
        self.tile_cache = {}
        self.tower_cache = {}
        self.enemy_frames = {}
        self.projectile_cache = {}
        self.decoration_cache = {}
        self.shadow_cache = {}
        self._generate_all()

    def _generate_all(self):
        self._gen_tiles()
        self._gen_towers()
        self._gen_enemies()
        self._gen_projectiles()
        self._gen_decorations()
        self._gen_shadows()

    # ── Tile Sprites ──────────────────────────────────────────

    def _gen_tiles(self):
        TS = TILE_SIZE
        # Grass tiles (4 variants)
        for i in range(4):
            s = pygame.Surface((TS, TS), pygame.SRCALPHA)
            base_g = 110 + i * 8
            _draw_gradient_rect(s, (0, 0, TS, TS),
                                (30, base_g + 20, 25), (25, base_g - 5, 20))
            # Grass blades
            random.seed(i * 42)
            for _ in range(6):
                gx = random.randint(4, TS - 4)
                gy = random.randint(TS // 2, TS - 4)
                gh = random.randint(4, 10)
                blade_c = (40 + random.randint(0, 30), 130 + random.randint(0, 40), 30)
                pygame.draw.line(s, blade_c, (gx, gy),
                                 (gx + random.randint(-3, 3), gy - gh), 1)
            # Tiny flower
            if i == 2:
                pygame.draw.circle(s, (220, 200, 60), (28, 12), 2)
                pygame.draw.circle(s, (255, 255, 100), (28, 12), 1)
            if i == 3:
                pygame.draw.circle(s, (200, 80, 80), (12, 30), 2)
            random.seed()
            self.tile_cache[f"grass_{i}"] = s

        # Path tiles (4 variants)
        for i in range(4):
            s = pygame.Surface((TS, TS), pygame.SRCALPHA)
            base = 160 + i * 5
            _draw_gradient_rect(s, (0, 0, TS, TS),
                                (base + 10, base - 5, base - 40),
                                (base - 10, base - 20, base - 50))
            # Stone texture
            random.seed(i * 77)
            for _ in range(3):
                sx = random.randint(4, TS - 12)
                sy = random.randint(4, TS - 12)
                sw = random.randint(6, 14)
                sh = random.randint(4, 8)
                stone_c = (base - 20 + random.randint(-10, 10),
                           base - 30 + random.randint(-10, 10),
                           base - 55 + random.randint(-10, 10))
                pygame.draw.ellipse(s, stone_c, (sx, sy, sw, sh))
                pygame.draw.ellipse(s, (stone_c[0] - 15, stone_c[1] - 15, stone_c[2] - 15),
                                    (sx, sy, sw, sh), 1)
            # Edge darkening
            edge = pygame.Surface((TS, TS), pygame.SRCALPHA)
            pygame.draw.rect(edge, (0, 0, 0, 20), (0, 0, TS, 2))
            pygame.draw.rect(edge, (0, 0, 0, 20), (0, TS - 2, TS, 2))
            s.blit(edge, (0, 0))
            random.seed()
            self.tile_cache[f"path_{i}"] = s

    # ── Tower Sprites ─────────────────────────────────────────

    def _gen_towers(self):
        for level in range(1, 4):
            self._gen_archer_tower(level)
            self._gen_wizard_tower(level)
            self._gen_fire_tower(level)
            self._gen_ice_tower(level)

    def _gen_archer_tower(self, level):
        TS = TILE_SIZE
        s = pygame.Surface((TS, TS), pygame.SRCALPHA)
        lv = level - 1  # 0-based

        # Shadow
        shadow = pygame.Surface((TS, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 40), (4, 0, TS - 8, 8))
        s.blit(shadow, (0, TS - 8))

        # Stone base
        base_c = (110 + lv * 15, 105 + lv * 10, 90 + lv * 10)
        _draw_gradient_rect(s, (6, 28, 28, 10), base_c,
                            (base_c[0] - 30, base_c[1] - 30, base_c[2] - 30))
        pygame.draw.rect(s, (base_c[0] - 40, base_c[1] - 40, base_c[2] - 40),
                         (6, 28, 28, 10), 1)

        # Wooden tower body
        wood_top = (100 + lv * 20, 70 + lv * 10, 35)
        wood_bot = (70 + lv * 15, 50 + lv * 8, 25)
        _draw_gradient_rect(s, (8, 8, 24, 22), wood_top, wood_bot)
        # Wood grain
        for gy in range(10, 28, 3):
            pygame.draw.line(s, (wood_bot[0] - 10, wood_bot[1] - 10, wood_bot[2]),
                             (9, gy), (30, gy), 1)

        # Battlements
        bc = (wood_top[0] + 15, wood_top[1] + 10, wood_top[2] + 10)
        for bx in range(8, 32, 8):
            pygame.draw.rect(s, bc, (bx, 4, 6, 6))
            pygame.draw.rect(s, (bc[0] - 20, bc[1] - 15, bc[2] - 10),
                             (bx, 4, 6, 6), 1)

        # Arrow slit (glowing green at higher levels)
        slit_c = (30, 50 + lv * 40, 20) if level > 1 else (20, 20, 15)
        pygame.draw.rect(s, slit_c, (18, 14, 4, 10))
        pygame.draw.rect(s, slit_c, (15, 18, 10, 3))

        # Banner at level 3
        if level == 3:
            pygame.draw.line(s, (80, 50, 30), (30, 4), (30, -2), 2)
            pts = [(30, -2), (38, 1), (30, 4)]
            pygame.draw.polygon(s, (180, 40, 40), pts)

        # Level gems
        gem_colors = [(100, 200, 100), (200, 200, 50), (255, 180, 50)]
        for i in range(level):
            pygame.draw.circle(s, gem_colors[i], (12 + i * 8, 35), 2)
            pygame.draw.circle(s, (255, 255, 200), (11 + i * 8, 34), 1)

        self.tower_cache[f"archer_{level}"] = s

    def _gen_wizard_tower(self, level):
        TS = TILE_SIZE
        s = pygame.Surface((TS, TS), pygame.SRCALPHA)
        lv = level - 1

        # Shadow
        shadow = pygame.Surface((TS, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 40), (4, 0, TS - 8, 8))
        s.blit(shadow, (0, TS - 8))

        # Stone base
        base_c = (80, 70, 100 + lv * 15)
        _draw_gradient_rect(s, (8, 32, 24, 6), base_c,
                            (base_c[0] - 20, base_c[1] - 20, base_c[2] - 20))

        # Tower body (cylindrical stone)
        body_top = (90 + lv * 10, 75 + lv * 8, 120 + lv * 15)
        body_bot = (60, 50, 85)
        _draw_gradient_rect(s, (11, 12, 18, 22), body_top, body_bot)
        # Stone brick lines
        for gy in range(14, 32, 4):
            off = 0 if (gy // 4) % 2 == 0 else 4
            pygame.draw.line(s, (body_bot[0] - 10, body_bot[1] - 10, body_bot[2] - 10),
                             (12, gy), (28, gy), 1)
            pygame.draw.line(s, (body_bot[0] - 10, body_bot[1] - 10, body_bot[2] - 10),
                             (17 + off, gy), (17 + off, gy + 4), 1)

        # Pointed roof
        roof_c = (80 + lv * 30, 30 + lv * 10, 140 + lv * 30)
        pts = [(7, 14), (20, -2), (33, 14)]
        pygame.draw.polygon(s, roof_c, pts)
        pygame.draw.polygon(s, (roof_c[0] + 30, roof_c[1] + 20, roof_c[2] + 20),
                            [(10, 13), (20, 1), (20, 13)])  # highlight
        pygame.draw.polygon(s, (roof_c[0] - 30, roof_c[1] - 20, roof_c[2] - 20),
                            pts, 2)

        # Glowing orb on top
        orb_c = (180 + lv * 25, 100 + lv * 30, 255)
        glow = _radial_gradient(16, (*orb_c, 200), (*orb_c[:3], 0), 8)
        s.blit(glow, (12, -6))
        pygame.draw.circle(s, orb_c, (20, 2), 3)
        pygame.draw.circle(s, (255, 230, 255), (19, 1), 1)

        # Magic window
        win_c = (140 + lv * 20, 80 + lv * 20, 200 + lv * 15)
        pygame.draw.circle(s, win_c, (20, 22), 4)
        pygame.draw.circle(s, (win_c[0] + 40, win_c[1] + 40, min(255, win_c[2] + 30)),
                           (19, 21), 2)

        # Level gems
        gem_colors = [(150, 100, 255), (200, 150, 255), (255, 200, 255)]
        for i in range(level):
            pygame.draw.circle(s, gem_colors[i], (12 + i * 8, 36), 2)
            pygame.draw.circle(s, (255, 230, 255), (11 + i * 8, 35), 1)

        self.tower_cache[f"wizard_{level}"] = s

    def _gen_fire_tower(self, level):
        TS = TILE_SIZE
        s = pygame.Surface((TS, TS), pygame.SRCALPHA)
        lv = level - 1

        # Shadow
        shadow = pygame.Surface((TS, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 40), (4, 0, TS - 8, 8))
        s.blit(shadow, (0, TS - 8))

        # Dark volcanic base
        _draw_gradient_rect(s, (5, 30, 30, 8),
                            (70 + lv * 10, 40, 25), (40, 20, 10))
        pygame.draw.rect(s, (30, 15, 5), (5, 30, 30, 8), 1)

        # Volcanic rock body
        body_top = (90 + lv * 15, 50 + lv * 8, 30)
        body_bot = (50 + lv * 10, 30, 15)
        _draw_gradient_rect(s, (8, 12, 24, 20), body_top, body_bot)
        pygame.draw.rect(s, (40, 20, 10), (8, 12, 24, 20), 2)

        # Lava cracks (glowing)
        crack_c = (255, 120 + lv * 40, 0)
        crack_glow = (255, 80 + lv * 30, 0, 100)
        # Glow layer
        glow_s = pygame.Surface((TS, TS), pygame.SRCALPHA)
        pygame.draw.line(glow_s, crack_glow, (12, 14), (16, 28), 3)
        pygame.draw.line(glow_s, crack_glow, (25, 15), (21, 30), 3)
        pygame.draw.line(glow_s, crack_glow, (14, 22), (26, 24), 3)
        s.blit(glow_s, (0, 0))
        pygame.draw.line(s, crack_c, (12, 14), (16, 28), 2)
        pygame.draw.line(s, crack_c, (25, 15), (21, 30), 2)
        pygame.draw.line(s, crack_c, (14, 22), (26, 24), 1)

        # Brazier
        _draw_gradient_rect(s, (10, 8, 20, 5),
                            (120 + lv * 20, 60, 30), (80, 40, 20))

        # Static flames (animated flames are drawn by renderer)
        flame_colors = [(255, 220, 80), (255, 160, 30), (255, 80, 0)]
        for i, fc in enumerate(flame_colors):
            fx = 14 + i * 5
            pts = [(fx, 7), (fx - 3 + i, 2 - lv), (fx + 3 - i, 7)]
            pygame.draw.polygon(s, fc, pts)

        # Level
        gem_colors = [(255, 150, 50), (255, 200, 50), (255, 255, 100)]
        for i in range(level):
            pygame.draw.circle(s, gem_colors[i], (12 + i * 8, 36), 2)
            pygame.draw.circle(s, (255, 255, 200), (11 + i * 8, 35), 1)

        self.tower_cache[f"fire_{level}"] = s

    def _gen_ice_tower(self, level):
        TS = TILE_SIZE
        s = pygame.Surface((TS, TS), pygame.SRCALPHA)
        lv = level - 1

        # Shadow
        shadow = pygame.Surface((TS, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 40), (4, 0, TS - 8, 8))
        s.blit(shadow, (0, TS - 8))

        # Ice platform
        plat_c = (140 + lv * 20, 200 + lv * 10, 230)
        _draw_gradient_rect(s, (6, 28, 28, 10), plat_c,
                            (plat_c[0] - 30, plat_c[1] - 20, plat_c[2] - 10))
        pygame.draw.rect(s, (200, 230, 255), (6, 28, 28, 10), 1)

        # Crystal body (diamond)
        cx, cy = 20, 16
        crystal_c = (100 + lv * 30, 190 + lv * 15, 255)
        crystal_light = (min(255, crystal_c[0] + 60),
                         min(255, crystal_c[1] + 30),
                         min(255, crystal_c[2]))
        crystal_dark = (crystal_c[0] - 40, crystal_c[1] - 30, crystal_c[2] - 20)

        # Main crystal
        main_pts = [(cx, 4 - lv * 2), (cx + 10, cy), (cx, cy + 14), (cx - 10, cy)]
        pygame.draw.polygon(s, crystal_c, main_pts)
        # Left face (darker)
        left_pts = [(cx, 4 - lv * 2), (cx - 10, cy), (cx, cy + 14)]
        pygame.draw.polygon(s, crystal_dark, left_pts)
        # Right face (lighter)
        right_pts = [(cx, 4 - lv * 2), (cx + 10, cy), (cx, cy + 14)]
        pygame.draw.polygon(s, crystal_light, right_pts)
        # Outline
        pygame.draw.polygon(s, (220, 240, 255), main_pts, 2)
        # Inner highlight
        pygame.draw.line(s, (255, 255, 255, 180), (cx - 2, 10), (cx - 5, cy + 4), 1)

        # Small crystals at level 2+
        if level >= 2:
            sm = [(cx - 8, cy + 4, 6), (cx + 7, cy + 2, 7)]
            for sx, sy, sh in sm:
                pts = [(sx, sy - sh), (sx + 3, sy), (sx - 3, sy)]
                pygame.draw.polygon(s, crystal_light, pts)
                pygame.draw.polygon(s, (200, 230, 255), pts, 1)

        # Level
        gem_colors = [(100, 200, 255), (150, 220, 255), (200, 240, 255)]
        for i in range(level):
            pygame.draw.circle(s, gem_colors[i], (12 + i * 8, 36), 2)
            pygame.draw.circle(s, (240, 250, 255), (11 + i * 8, 35), 1)

        self.tower_cache[f"ice_{level}"] = s

    # ── Enemy Sprite Frames ───────────────────────────────────

    def _gen_enemies(self):
        for frame in range(4):  # 4 walk frames
            self._gen_goblin_frame(frame)
            self._gen_orc_frame(frame)
            self._gen_dark_knight_frame(frame)
            self._gen_dragon_frame(frame)

    def _gen_goblin_frame(self, frame):
        s = pygame.Surface((24, 28), pygame.SRCALPHA)
        cx, cy = 12, 18
        bob = [0, -1, 0, 1][frame]
        leg_off = [-2, 0, 2, 0][frame]

        # Shadow
        pygame.draw.ellipse(s, (0, 0, 0, 30), (4, 24, 16, 4))

        # Legs
        skin = (50, 160, 40)
        skin_dark = (35, 120, 25)
        pygame.draw.rect(s, skin_dark, (cx - 4, cy + 2 + leg_off, 3, 5))
        pygame.draw.rect(s, skin_dark, (cx + 1, cy + 2 - leg_off, 3, 5))

        # Body (hunched)
        _draw_gradient_circle(s, cx, cy - 2 + bob, 6, skin, skin_dark)
        # Tattered vest
        pygame.draw.arc(s, (80, 60, 40), (cx - 5, cy - 5 + bob, 10, 8), 0.3, 2.8, 2)

        # Head
        head_c = (60, 175, 45)
        _draw_gradient_circle(s, cx, cy - 8 + bob, 5, head_c, (40, 120, 30))
        # Pointy ears
        pygame.draw.polygon(s, head_c,
                            [(cx - 5, cy - 9 + bob), (cx - 9, cy - 15 + bob), (cx - 3, cy - 10 + bob)])
        pygame.draw.polygon(s, head_c,
                            [(cx + 5, cy - 9 + bob), (cx + 9, cy - 15 + bob), (cx + 3, cy - 10 + bob)])
        # Eyes
        pygame.draw.circle(s, (255, 40, 0), (cx - 2, cy - 9 + bob), 2)
        pygame.draw.circle(s, (255, 40, 0), (cx + 2, cy - 9 + bob), 2)
        pygame.draw.circle(s, (0, 0, 0), (cx - 2, cy - 9 + bob), 1)
        pygame.draw.circle(s, (0, 0, 0), (cx + 2, cy - 9 + bob), 1)
        # Mouth
        pygame.draw.line(s, (30, 80, 20), (cx - 2, cy - 5 + bob), (cx + 2, cy - 5 + bob), 1)

        self.enemy_frames[f"goblin_{frame}"] = s

    def _gen_orc_frame(self, frame):
        s = pygame.Surface((32, 36), pygame.SRCALPHA)
        cx, cy = 16, 22
        bob = [0, -1, 0, 1][frame]
        leg_off = [-2, 0, 2, 0][frame]
        arm_off = [2, 0, -2, 0][frame]

        # Shadow
        pygame.draw.ellipse(s, (0, 0, 0, 35), (4, 30, 24, 6))

        skin = (45, 145, 35)
        skin_dark = (30, 100, 20)
        skin_light = (65, 170, 50)

        # Legs (thick)
        pygame.draw.rect(s, skin_dark, (cx - 6, cy + 3 + leg_off, 5, 8))
        pygame.draw.rect(s, skin_dark, (cx + 1, cy + 3 - leg_off, 5, 8))
        # Boots
        pygame.draw.rect(s, (60, 45, 25), (cx - 7, cy + 9 + leg_off, 6, 3))
        pygame.draw.rect(s, (60, 45, 25), (cx + 1, cy + 9 - leg_off, 6, 3))

        # Body
        _draw_gradient_circle(s, cx, cy - 3 + bob, 9, skin, skin_dark)
        # Chest scar / belt
        pygame.draw.line(s, (80, 60, 30), (cx - 6, cy + bob), (cx + 6, cy + bob), 2)
        # Shoulder pads
        pygame.draw.ellipse(s, (90, 70, 40), (cx - 11, cy - 7 + bob, 7, 5))
        pygame.draw.ellipse(s, (90, 70, 40), (cx + 4, cy - 7 + bob, 7, 5))

        # Arms
        pygame.draw.rect(s, skin, (cx - 12, cy - 4 + bob + arm_off, 4, 10))
        pygame.draw.rect(s, skin, (cx + 8, cy - 4 + bob - arm_off, 4, 10))
        # Weapon (crude axe in right hand)
        pygame.draw.line(s, (100, 80, 50), (cx + 9, cy - 2 + bob), (cx + 9, cy - 10 + bob), 2)
        pygame.draw.polygon(s, (150, 150, 160),
                            [(cx + 7, cy - 10 + bob), (cx + 12, cy - 12 + bob),
                             (cx + 12, cy - 8 + bob)])

        # Head
        _draw_gradient_circle(s, cx, cy - 12 + bob, 7, (55, 155, 40), skin_dark)
        # Jaw
        pygame.draw.ellipse(s, (50, 140, 35), (cx - 5, cy - 10 + bob, 10, 5))
        # Tusks!
        pygame.draw.polygon(s, (230, 220, 180),
                            [(cx - 4, cy - 8 + bob), (cx - 6, cy - 4 + bob), (cx - 3, cy - 6 + bob)])
        pygame.draw.polygon(s, (230, 220, 180),
                            [(cx + 4, cy - 8 + bob), (cx + 6, cy - 4 + bob), (cx + 3, cy - 6 + bob)])
        # Eyes (yellow, angry)
        pygame.draw.circle(s, (255, 200, 0), (cx - 3, cy - 13 + bob), 2)
        pygame.draw.circle(s, (255, 200, 0), (cx + 3, cy - 13 + bob), 2)
        pygame.draw.circle(s, (0, 0, 0), (cx - 3, cy - 13 + bob), 1)
        pygame.draw.circle(s, (0, 0, 0), (cx + 3, cy - 13 + bob), 1)
        # Eyebrows
        pygame.draw.line(s, skin_dark, (cx - 6, cy - 16 + bob), (cx - 1, cy - 15 + bob), 2)
        pygame.draw.line(s, skin_dark, (cx + 6, cy - 16 + bob), (cx + 1, cy - 15 + bob), 2)

        self.enemy_frames[f"orc_{frame}"] = s

    def _gen_dark_knight_frame(self, frame):
        s = pygame.Surface((30, 36), pygame.SRCALPHA)
        cx, cy = 15, 22
        bob = [0, -1, 0, 1][frame]
        leg_off = [-2, 0, 2, 0][frame]

        # Shadow
        pygame.draw.ellipse(s, (0, 0, 0, 35), (3, 30, 24, 6))

        armor = (65, 65, 75)
        armor_light = (100, 100, 115)
        armor_dark = (40, 40, 48)

        # Legs (armored)
        pygame.draw.rect(s, armor, (cx - 5, cy + 2 + leg_off, 4, 8))
        pygame.draw.rect(s, armor, (cx + 1, cy + 2 - leg_off, 4, 8))
        pygame.draw.rect(s, armor_light, (cx - 5, cy + 2 + leg_off, 4, 2))
        pygame.draw.rect(s, armor_light, (cx + 1, cy + 2 - leg_off, 4, 2))
        # Boots
        pygame.draw.rect(s, armor_dark, (cx - 6, cy + 8 + leg_off, 5, 3))
        pygame.draw.rect(s, armor_dark, (cx + 1, cy + 8 - leg_off, 5, 3))

        # Body (heavy plate)
        _draw_gradient_circle(s, cx, cy - 4 + bob, 8, armor_light, armor_dark)
        # Chest plate highlight
        pygame.draw.ellipse(s, armor_light, (cx - 4, cy - 6 + bob, 8, 5))
        # Red trim
        pygame.draw.line(s, (120, 30, 30), (cx - 6, cy + 1 + bob), (cx + 6, cy + 1 + bob), 1)

        # Shield (left)
        shield_bob = [0, 1, 0, -1][frame]
        sx, sy = cx - 13, cy - 4 + bob + shield_bob
        pygame.draw.ellipse(s, (100, 35, 35), (sx, sy, 9, 12))
        pygame.draw.ellipse(s, (140, 50, 50), (sx + 1, sy + 1, 7, 10))
        pygame.draw.line(s, (180, 80, 30), (sx + 4, sy + 2), (sx + 4, sy + 10), 1)
        pygame.draw.line(s, (180, 80, 30), (sx + 1, sy + 5), (sx + 7, sy + 5), 1)

        # Sword (right)
        sword_bob = [-1, 0, 1, 0][frame]
        pygame.draw.line(s, (180, 180, 200), (cx + 7, cy - 1 + bob),
                         (cx + 9, cy - 12 + bob + sword_bob), 2)
        pygame.draw.line(s, (255, 255, 230), (cx + 9, cy - 12 + bob + sword_bob),
                         (cx + 9, cy - 16 + bob + sword_bob), 2)
        # Cross guard
        pygame.draw.line(s, (200, 180, 100), (cx + 6, cy - 1 + bob),
                         (cx + 10, cy - 1 + bob), 2)

        # Helmet
        _draw_gradient_circle(s, cx, cy - 11 + bob, 7, armor_light, armor_dark)
        # Visor
        pygame.draw.rect(s, (30, 30, 35), (cx - 5, cy - 13 + bob, 10, 3))
        # Glowing eyes
        pygame.draw.circle(s, (255, 50, 0), (cx - 2, cy - 12 + bob), 1)
        pygame.draw.circle(s, (255, 50, 0), (cx + 2, cy - 12 + bob), 1)
        # Plume
        pygame.draw.polygon(s, (120, 20, 20),
                            [(cx, cy - 18 + bob), (cx - 3, cy - 13 + bob),
                             (cx + 3, cy - 13 + bob)])
        pygame.draw.polygon(s, (160, 40, 40),
                            [(cx, cy - 18 + bob), (cx, cy - 13 + bob),
                             (cx + 2, cy - 13 + bob)])

        self.enemy_frames[f"dark_knight_{frame}"] = s

    def _gen_dragon_frame(self, frame):
        s = pygame.Surface((48, 44), pygame.SRCALPHA)
        cx, cy = 24, 26
        flap = [0, -3, 0, 3][frame]

        # Shadow (large, faint - flying)
        shadow = pygame.Surface((48, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 20), (8, 0, 32, 8))
        s.blit(shadow, (0, 38))

        body_c = (180, 35, 30)
        body_dark = (130, 20, 15)
        body_light = (210, 60, 50)
        belly = (230, 175, 60)

        # Tail
        tail_pts = [(cx, cy + 6), (cx - 8, cy + 10), (cx - 14, cy + 14), (cx - 12, cy + 16)]
        pygame.draw.lines(s, body_dark, False, tail_pts, 3)
        # Tail spike
        pygame.draw.polygon(s, body_c,
                            [(cx - 12, cy + 16), (cx - 16, cy + 19), (cx - 10, cy + 18)])

        # Wings
        wing_y_off = flap
        # Left wing
        lw = [(cx - 6, cy - 4), (cx - 22, cy - 16 + wing_y_off),
              (cx - 20, cy - 2), (cx - 10, cy)]
        pygame.draw.polygon(s, (150, 25, 25), lw)
        pygame.draw.polygon(s, body_dark, lw, 2)
        # Wing membrane
        pygame.draw.line(s, (120, 20, 20), lw[0], lw[1], 1)
        pygame.draw.line(s, (120, 20, 20), (cx - 10, cy - 2), lw[1], 1)
        # Right wing
        rw = [(cx + 6, cy - 4), (cx + 22, cy - 16 + wing_y_off),
              (cx + 20, cy - 2), (cx + 10, cy)]
        pygame.draw.polygon(s, (160, 30, 30), rw)
        pygame.draw.polygon(s, body_dark, rw, 2)
        pygame.draw.line(s, (130, 25, 25), rw[0], rw[1], 1)
        pygame.draw.line(s, (130, 25, 25), (cx + 10, cy - 2), rw[1], 1)

        # Body
        _draw_gradient_circle(s, cx, cy - 2, 10, body_light, body_dark)
        # Belly
        pygame.draw.ellipse(s, belly, (cx - 6, cy - 1, 12, 8))

        # Legs
        for lx_off in [-6, 4]:
            pygame.draw.rect(s, body_dark, (cx + lx_off, cy + 6, 4, 5))
            for c in range(3):
                pygame.draw.line(s, (200, 180, 100),
                                 (cx + lx_off + c * 2, cy + 11),
                                 (cx + lx_off + c * 2 - 1, cy + 13), 1)

        # Head
        _draw_gradient_circle(s, cx, cy - 13, 6, body_light, body_dark)
        # Snout
        pygame.draw.ellipse(s, (195, 45, 40), (cx - 2, cy - 12, 10, 5))
        # Nostrils (with tiny flame)
        pygame.draw.circle(s, (100, 15, 10), (cx + 2, cy - 11), 1)
        pygame.draw.circle(s, (100, 15, 10), (cx + 5, cy - 11), 1)
        # Eyes
        pygame.draw.circle(s, (255, 220, 0), (cx - 3, cy - 14), 3)
        pygame.draw.circle(s, (255, 220, 0), (cx + 3, cy - 14), 3)
        pygame.draw.circle(s, (0, 0, 0), (cx - 3, cy - 14), 1)
        pygame.draw.circle(s, (0, 0, 0), (cx + 3, cy - 14), 1)
        # Eye glow
        glow = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 200, 0, 40), (4, 4), 4)
        s.blit(glow, (cx - 7, cy - 18))
        s.blit(glow, (cx - 1, cy - 18))
        # Horns
        pygame.draw.polygon(s, (200, 180, 90),
                            [(cx - 5, cy - 16), (cx - 9, cy - 23), (cx - 3, cy - 15)])
        pygame.draw.polygon(s, (200, 180, 90),
                            [(cx + 5, cy - 16), (cx + 9, cy - 23), (cx + 3, cy - 15)])
        # Horn highlight
        pygame.draw.line(s, (230, 220, 140), (cx - 7, cy - 20), (cx - 5, cy - 16), 1)
        pygame.draw.line(s, (230, 220, 140), (cx + 7, cy - 20), (cx + 5, cy - 16), 1)

        self.enemy_frames[f"dragon_{frame}"] = s

    # ── Projectile Sprites ────────────────────────────────────

    def _gen_projectiles(self):
        # Archer arrow
        s = pygame.Surface((12, 12), pygame.SRCALPHA)
        glow = _radial_gradient(12, (200, 180, 100, 150), (200, 180, 100, 0), 6)
        s.blit(glow, (0, 0))
        pygame.draw.circle(s, (220, 190, 120), (6, 6), 3)
        pygame.draw.circle(s, (255, 240, 180), (5, 5), 1)
        self.projectile_cache["archer"] = s

        # Wizard orb
        s = pygame.Surface((18, 18), pygame.SRCALPHA)
        glow = _radial_gradient(18, (200, 130, 255, 120), (180, 100, 255, 0), 9)
        s.blit(glow, (0, 0))
        pygame.draw.circle(s, (180, 100, 255), (9, 9), 5)
        pygame.draw.circle(s, (255, 220, 255), (8, 8), 2)
        self.projectile_cache["wizard"] = s

        # Fireball
        s = pygame.Surface((20, 20), pygame.SRCALPHA)
        glow = _radial_gradient(20, (255, 160, 30, 100), (255, 60, 0, 0), 10)
        s.blit(glow, (0, 0))
        pygame.draw.circle(s, (255, 160, 40), (10, 10), 5)
        pygame.draw.circle(s, (255, 240, 120), (9, 9), 2)
        self.projectile_cache["fire"] = s

        # Ice shard
        s = pygame.Surface((16, 16), pygame.SRCALPHA)
        glow = _radial_gradient(16, (150, 220, 255, 100), (100, 200, 255, 0), 8)
        s.blit(glow, (0, 0))
        pts = [(8, 1), (14, 8), (8, 15), (2, 8)]
        pygame.draw.polygon(s, (170, 225, 255), pts)
        pygame.draw.polygon(s, (220, 245, 255), pts, 1)
        # Inner shine
        pygame.draw.polygon(s, (220, 245, 255),
                            [(8, 3), (11, 8), (8, 13), (5, 8)])
        self.projectile_cache["ice"] = s

    # ── Map Decorations ───────────────────────────────────────

    def _gen_decorations(self):
        # Tree (small)
        s = pygame.Surface((20, 28), pygame.SRCALPHA)
        # Trunk
        _draw_gradient_rect(s, (8, 16, 5, 10), (90, 65, 35), (60, 40, 20))
        # Foliage layers
        for ly, lr, lc in [(12, 9, (30, 130, 30)), (8, 7, (40, 150, 35)), (4, 5, (50, 160, 40))]:
            pygame.draw.circle(s, lc, (10, ly), lr)
            pygame.draw.circle(s, (lc[0] + 20, lc[1] + 20, lc[2] + 10),
                               (9, ly - 1), lr - 2)
        self.decoration_cache["tree"] = s

        # Rock
        s = pygame.Surface((14, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (100, 100, 105), (0, 2, 14, 8))
        pygame.draw.ellipse(s, (120, 120, 125), (1, 2, 10, 6))
        pygame.draw.ellipse(s, (80, 80, 85), (0, 2, 14, 8), 1)
        self.decoration_cache["rock"] = s

        # Bush
        s = pygame.Surface((16, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (35, 120, 25), (0, 2, 16, 10))
        pygame.draw.ellipse(s, (45, 140, 35), (2, 3, 10, 7))
        pygame.draw.ellipse(s, (55, 150, 40), (6, 1, 8, 6))
        self.decoration_cache["bush"] = s

        # Mushroom
        s = pygame.Surface((10, 12), pygame.SRCALPHA)
        pygame.draw.rect(s, (200, 190, 170), (4, 6, 3, 5))
        pygame.draw.ellipse(s, (180, 40, 40), (0, 2, 10, 7))
        pygame.draw.circle(s, (255, 255, 200), (3, 4), 1)
        pygame.draw.circle(s, (255, 255, 200), (7, 5), 1)
        self.decoration_cache["mushroom"] = s

    # ── Shadows ───────────────────────────────────────────────

    def _gen_shadows(self):
        for size_name, w, h in [("small", 16, 6), ("medium", 24, 8), ("large", 36, 10)]:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (0, 0, 0, 35), (0, 0, w, h))
            self.shadow_cache[size_name] = s

    # ── Access Methods ────────────────────────────────────────

    def get_tile(self, tile_type, variant):
        key = f"{tile_type}_{variant % 4}"
        return self.tile_cache.get(key)

    def get_tower(self, tower_type, level):
        key = f"{tower_type}_{level}"
        return self.tower_cache.get(key)

    def get_enemy_frame(self, enemy_type, frame):
        key = f"{enemy_type}_{frame % 4}"
        return self.enemy_frames.get(key)

    def get_projectile(self, tower_type):
        return self.projectile_cache.get(tower_type)

    def get_decoration(self, name):
        return self.decoration_cache.get(name)

    def get_shadow(self, size):
        return self.shadow_cache.get(size)
