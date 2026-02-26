import pygame
import math
import random


class Particle:
    """A single visual particle."""
    __slots__ = ['x', 'y', 'vx', 'vy', 'life', 'max_life', 'color',
                 'size', 'gravity', 'fade', 'shrink']

    def __init__(self, x, y, vx, vy, life, color, size=3,
                 gravity=0, fade=True, shrink=True):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.gravity = gravity
        self.fade = fade
        self.shrink = shrink

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.life -= dt

    @property
    def alive(self):
        return self.life > 0

    @property
    def alpha(self):
        if self.fade:
            return max(0, min(255, int(255 * (self.life / self.max_life))))
        return 255

    @property
    def current_size(self):
        if self.shrink:
            return max(1, self.size * (self.life / self.max_life))
        return self.size


class EffectsManager:
    """Manages visual particle effects for the game."""

    def __init__(self):
        self.particles = []
        self.impact_effects = []  # [(x, y, type, timer)]
        self.tower_auras = {}     # tower_id -> aura_timer

    def update(self, dt):
        # Update particles
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        # Update impact effects
        self.impact_effects = [(x, y, t, timer - dt)
                               for x, y, t, timer in self.impact_effects
                               if timer - dt > 0]

        # Update aura timers
        for tid in list(self.tower_auras):
            self.tower_auras[tid] += dt

    def clear(self):
        self.particles.clear()
        self.impact_effects.clear()
        self.tower_auras.clear()

    # ── Archer Effects ────────────────────────────────────────

    def spawn_arrow_trail(self, x, y):
        """Small dust trail behind arrows."""
        for _ in range(1):
            self.particles.append(Particle(
                x + random.uniform(-2, 2), y + random.uniform(-2, 2),
                random.uniform(-15, 15), random.uniform(-15, 15),
                life=0.2, color=(180, 160, 100), size=2,
                gravity=0, fade=True, shrink=True,
            ))

    def spawn_arrow_impact(self, x, y):
        """Dust burst on arrow hit."""
        self.impact_effects.append((x, y, "arrow", 0.3))
        for _ in range(6):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(30, 80)
            self.particles.append(Particle(
                x, y,
                math.cos(angle) * speed, math.sin(angle) * speed,
                life=0.3, color=(200, 180, 120), size=3,
                gravity=100, fade=True, shrink=True,
            ))

    # ── Wizard Effects ────────────────────────────────────────

    def spawn_magic_trail(self, x, y):
        """Sparkle trail behind magic projectile."""
        for _ in range(2):
            self.particles.append(Particle(
                x + random.uniform(-4, 4), y + random.uniform(-4, 4),
                random.uniform(-20, 20), random.uniform(-30, -5),
                life=0.4, color=random.choice([
                    (180, 100, 255), (220, 150, 255), (140, 80, 220), (255, 200, 255)
                ]),
                size=random.uniform(2, 4), gravity=-20, fade=True, shrink=True,
            ))

    def spawn_magic_explosion(self, x, y, radius):
        """AOE magic explosion ring + sparkles."""
        self.impact_effects.append((x, y, "magic", 0.5))
        for _ in range(20):
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(0, radius)
            speed = random.uniform(20, 60)
            self.particles.append(Particle(
                x + math.cos(angle) * dist * 0.3,
                y + math.sin(angle) * dist * 0.3,
                math.cos(angle) * speed, math.sin(angle) * speed - 30,
                life=random.uniform(0.3, 0.7),
                color=random.choice([
                    (180, 100, 255), (255, 180, 255), (100, 50, 200), (220, 200, 255)
                ]),
                size=random.uniform(2, 5), gravity=-10, fade=True, shrink=True,
            ))

    # ── Fire Effects ──────────────────────────────────────────

    def spawn_fire_trail(self, x, y):
        """Flame particles behind fire projectile."""
        for _ in range(3):
            self.particles.append(Particle(
                x + random.uniform(-3, 3), y + random.uniform(-3, 3),
                random.uniform(-10, 10), random.uniform(-40, -10),
                life=random.uniform(0.2, 0.4),
                color=random.choice([
                    (255, 200, 50), (255, 140, 30), (255, 80, 0), (255, 60, 0)
                ]),
                size=random.uniform(3, 6), gravity=-50, fade=True, shrink=True,
            ))

    def spawn_fire_impact(self, x, y):
        """Fire burst on impact."""
        self.impact_effects.append((x, y, "fire", 0.4))
        for _ in range(15):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(30, 100)
            self.particles.append(Particle(
                x, y,
                math.cos(angle) * speed, math.sin(angle) * speed - 40,
                life=random.uniform(0.3, 0.6),
                color=random.choice([
                    (255, 220, 80), (255, 160, 30), (255, 100, 0), (200, 50, 0)
                ]),
                size=random.uniform(3, 7), gravity=-30, fade=True, shrink=True,
            ))

    def spawn_burn_particles(self, x, y):
        """Small flames on a burning enemy."""
        self.particles.append(Particle(
            x + random.uniform(-5, 5), y + random.uniform(-3, 3),
            random.uniform(-5, 5), random.uniform(-30, -15),
            life=0.3,
            color=random.choice([(255, 160, 30), (255, 100, 0), (255, 200, 50)]),
            size=random.uniform(2, 4), gravity=-20, fade=True, shrink=True,
        ))

    # ── Ice Effects ───────────────────────────────────────────

    def spawn_ice_trail(self, x, y):
        """Frost crystals behind ice projectile."""
        for _ in range(2):
            self.particles.append(Particle(
                x + random.uniform(-3, 3), y + random.uniform(-3, 3),
                random.uniform(-15, 15), random.uniform(-15, 15),
                life=0.4,
                color=random.choice([
                    (150, 220, 255), (200, 240, 255), (100, 200, 255), (220, 240, 255)
                ]),
                size=random.uniform(2, 4), gravity=10, fade=True, shrink=False,
            ))

    def spawn_ice_impact(self, x, y):
        """Ice crystal burst."""
        self.impact_effects.append((x, y, "ice", 0.4))
        for _ in range(12):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(20, 70)
            self.particles.append(Particle(
                x, y,
                math.cos(angle) * speed, math.sin(angle) * speed,
                life=random.uniform(0.4, 0.8),
                color=random.choice([
                    (150, 220, 255), (200, 240, 255), (100, 180, 255), (255, 255, 255)
                ]),
                size=random.uniform(2, 5), gravity=15, fade=True, shrink=False,
            ))

    def spawn_frozen_particles(self, x, y):
        """Snowflake particles on a slowed enemy."""
        self.particles.append(Particle(
            x + random.uniform(-6, 6), y + random.uniform(-8, -2),
            random.uniform(-8, 8), random.uniform(-10, 5),
            life=0.5,
            color=(200, 230, 255),
            size=random.uniform(1, 3), gravity=15, fade=True, shrink=False,
        ))

    # ── Tower Aura Effects ────────────────────────────────────

    def spawn_tower_idle_particles(self, tower_type, px, py, tower_id):
        """Ambient particles around towers."""
        if tower_id not in self.tower_auras:
            self.tower_auras[tower_id] = 0

        t = self.tower_auras[tower_id]

        if tower_type == "archer":
            if random.random() < 0.05:
                # Occasional leaf/wind particle
                self.particles.append(Particle(
                    px + random.uniform(-15, 15), py - 15,
                    random.uniform(10, 30), random.uniform(-5, 5),
                    life=0.6, color=(100, 180, 60), size=2,
                    gravity=20, fade=True, shrink=False,
                ))

        elif tower_type == "wizard":
            if random.random() < 0.1:
                angle = t * 3 + random.uniform(0, 1)
                dist = 14
                self.particles.append(Particle(
                    px + math.cos(angle) * dist,
                    py + math.sin(angle) * dist - 5,
                    0, -10, life=0.5,
                    color=random.choice([(180, 100, 255), (220, 150, 255)]),
                    size=2, gravity=-5, fade=True, shrink=True,
                ))

        elif tower_type == "fire":
            if random.random() < 0.15:
                self.particles.append(Particle(
                    px + random.uniform(-8, 8), py - 12,
                    random.uniform(-5, 5), random.uniform(-25, -10),
                    life=0.3,
                    color=random.choice([(255, 160, 30), (255, 100, 0)]),
                    size=random.uniform(2, 4), gravity=-15, fade=True, shrink=True,
                ))

        elif tower_type == "ice":
            if random.random() < 0.08:
                angle = random.uniform(0, math.pi * 2)
                self.particles.append(Particle(
                    px + math.cos(angle) * 12,
                    py + math.sin(angle) * 12 - 5,
                    math.cos(angle) * 3, -8,
                    life=0.6, color=(200, 230, 255),
                    size=2, gravity=5, fade=True, shrink=False,
                ))

    # ── Death Effects ────────────────────────────────────────

    def spawn_death_effect(self, x, y, enemy_type):
        """Dramatic death burst per enemy type."""
        if enemy_type == "goblin":
            # Small green poof
            for _ in range(10):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(30, 80)
                self.particles.append(Particle(
                    x + random.uniform(-3, 3), y + random.uniform(-3, 3),
                    math.cos(angle) * speed, math.sin(angle) * speed - 20,
                    life=random.uniform(0.3, 0.6),
                    color=random.choice([(60, 180, 45), (40, 140, 30), (80, 200, 50)]),
                    size=random.uniform(2, 5), gravity=60, fade=True, shrink=True,
                ))
            self.impact_effects.append((x, y, "death_green", 0.5))

        elif enemy_type == "orc":
            # Bigger green-brown burst
            for _ in range(18):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(40, 120)
                self.particles.append(Particle(
                    x + random.uniform(-5, 5), y + random.uniform(-5, 5),
                    math.cos(angle) * speed, math.sin(angle) * speed - 30,
                    life=random.uniform(0.4, 0.8),
                    color=random.choice([(50, 150, 35), (80, 100, 40), (100, 80, 30), (45, 140, 30)]),
                    size=random.uniform(3, 7), gravity=80, fade=True, shrink=True,
                ))
            self.impact_effects.append((x, y, "death_green", 0.6))

        elif enemy_type == "dark_knight":
            # Dark metallic shatter
            for _ in range(20):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(50, 130)
                self.particles.append(Particle(
                    x + random.uniform(-4, 4), y + random.uniform(-4, 4),
                    math.cos(angle) * speed, math.sin(angle) * speed - 25,
                    life=random.uniform(0.4, 0.9),
                    color=random.choice([(100, 100, 115), (70, 70, 80), (140, 140, 160),
                                          (180, 50, 30), (50, 50, 60)]),
                    size=random.uniform(2, 6), gravity=100, fade=True, shrink=False,
                ))
            # Red soul wisps
            for _ in range(5):
                self.particles.append(Particle(
                    x + random.uniform(-4, 4), y,
                    random.uniform(-15, 15), random.uniform(-60, -30),
                    life=random.uniform(0.5, 1.0),
                    color=random.choice([(255, 50, 20), (200, 30, 10)]),
                    size=random.uniform(2, 4), gravity=-20, fade=True, shrink=True,
                ))
            self.impact_effects.append((x, y, "death_dark", 0.6))

        elif enemy_type == "dragon":
            # Massive fiery explosion
            for _ in range(30):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(50, 160)
                self.particles.append(Particle(
                    x + random.uniform(-8, 8), y + random.uniform(-8, 8),
                    math.cos(angle) * speed, math.sin(angle) * speed - 40,
                    life=random.uniform(0.5, 1.2),
                    color=random.choice([(255, 200, 50), (255, 120, 20), (255, 60, 0),
                                          (200, 30, 10), (180, 35, 30)]),
                    size=random.uniform(3, 9), gravity=40, fade=True, shrink=True,
                ))
            # Bone/scale debris
            for _ in range(8):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(60, 140)
                self.particles.append(Particle(
                    x, y,
                    math.cos(angle) * speed, math.sin(angle) * speed - 50,
                    life=random.uniform(0.6, 1.0),
                    color=random.choice([(200, 180, 100), (160, 140, 80)]),
                    size=random.uniform(2, 5), gravity=120, fade=True, shrink=False,
                ))
            self.impact_effects.append((x, y, "death_fire", 0.7))

    # ── Spawn Effects ────────────────────────────────────────

    def spawn_entry_effect(self, x, y, enemy_type):
        """Visual effect when enemy appears on the map."""
        if enemy_type == "dragon":
            # Wing-beat gust
            for _ in range(12):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(20, 60)
                self.particles.append(Particle(
                    x + random.uniform(-10, 10), y + random.uniform(-5, 5),
                    math.cos(angle) * speed, math.sin(angle) * speed,
                    life=random.uniform(0.3, 0.6),
                    color=random.choice([(200, 180, 150), (180, 160, 130)]),
                    size=random.uniform(2, 4), gravity=-10, fade=True, shrink=True,
                ))
            self.impact_effects.append((x, y, "spawn_dark", 0.4))
        elif enemy_type == "dark_knight":
            # Dark energy coalesce
            for _ in range(8):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(20, 40)
                self.particles.append(Particle(
                    x + math.cos(angle) * dist, y + math.sin(angle) * dist,
                    -math.cos(angle) * 40, -math.sin(angle) * 40,
                    life=0.4,
                    color=random.choice([(80, 30, 30), (60, 20, 50), (100, 40, 40)]),
                    size=random.uniform(2, 4), gravity=0, fade=True, shrink=True,
                ))
            self.impact_effects.append((x, y, "spawn_dark", 0.4))
        else:
            # Simple dust poof for regular enemies
            for _ in range(6):
                angle = random.uniform(0, math.pi * 2)
                speed = random.uniform(15, 40)
                self.particles.append(Particle(
                    x + random.uniform(-3, 3), y + random.uniform(-3, 3),
                    math.cos(angle) * speed, math.sin(angle) * speed,
                    life=random.uniform(0.2, 0.4),
                    color=random.choice([(180, 170, 140), (160, 150, 120)]),
                    size=random.uniform(2, 4), gravity=30, fade=True, shrink=True,
                ))

    # ── Drawing ───────────────────────────────────────────────

    def draw(self, surf):
        """Draw all particles and impact effects."""
        # Draw impact effects
        for x, y, etype, timer in self.impact_effects:
            self._draw_impact(surf, x, y, etype, timer)

        # Draw particles
        for p in self.particles:
            alpha = p.alpha
            size = int(p.current_size)
            if size < 1:
                continue
            if alpha < 20:
                continue

            ps = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            r, g, b = p.color
            pygame.draw.circle(ps, (r, g, b, alpha), (size, size), size)
            surf.blit(ps, (int(p.x) - size, int(p.y) - size))

    def _draw_impact(self, surf, x, y, etype, timer):
        progress = 1.0 - (timer / 0.5)  # 0 -> 1

        if etype == "magic":
            # Expanding ring
            radius = int(20 + progress * 40)
            alpha = int(200 * (1 - progress))
            ring_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, (180, 100, 255, alpha),
                               (radius + 2, radius + 2), radius, 3)
            surf.blit(ring_surf, (int(x) - radius - 2, int(y) - radius - 2))

        elif etype == "fire":
            # Expanding fire glow
            radius = int(10 + progress * 25)
            alpha = int(150 * (1 - progress))
            glow_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 150, 30, alpha),
                               (radius, radius), radius)
            surf.blit(glow_surf, (int(x) - radius, int(y) - radius))

        elif etype == "ice":
            # Ice crystal pattern
            alpha = int(200 * (1 - progress))
            size = int(8 + progress * 15)
            ice_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            cx, cy = size, size
            for angle_deg in range(0, 360, 60):
                a = math.radians(angle_deg)
                ex = cx + int(math.cos(a) * size)
                ey = cy + int(math.sin(a) * size)
                pygame.draw.line(ice_surf, (150, 220, 255, alpha),
                                 (cx, cy), (ex, ey), 2)
            surf.blit(ice_surf, (int(x) - size, int(y) - size))

        elif etype == "arrow":
            # Dust puff
            radius = int(5 + progress * 10)
            alpha = int(150 * (1 - progress))
            dust = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(dust, (180, 160, 100, alpha),
                               (radius, radius), radius)
            surf.blit(dust, (int(x) - radius, int(y) - radius))

        elif etype == "death_green":
            # Green flash
            radius = int(10 + progress * 30)
            alpha = max(0, min(255, int(180 * (1 - progress))))
            if radius > 1 and alpha > 5:
                glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (80, 200, 50, alpha), (radius, radius), radius)
                half_r = max(1, radius // 2)
                pygame.draw.circle(glow, (120, 255, 80, alpha // 2),
                                   (radius, radius), half_r)
                surf.blit(glow, (int(x) - radius, int(y) - radius))

        elif etype == "death_dark":
            # Dark shockwave
            radius = int(12 + progress * 35)
            alpha = max(0, min(255, int(200 * (1 - progress))))
            if radius > 3 and alpha > 5:
                ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ring, (120, 40, 40, alpha),
                                   (radius + 2, radius + 2), radius, min(3, radius - 1))
                half_r = max(1, radius // 2)
                pygame.draw.circle(ring, (200, 60, 60, alpha // 2),
                                   (radius + 2, radius + 2), half_r, min(2, half_r))
                surf.blit(ring, (int(x) - radius - 2, int(y) - radius - 2))

        elif etype == "death_fire":
            # Massive fire ring
            radius = int(20 + progress * 50)
            alpha = max(0, min(255, int(220 * (1 - progress))))
            if radius > 4 and alpha > 5:
                glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 150, 30, alpha // 2), (radius, radius), radius)
                pygame.draw.circle(glow, (255, 200, 60, alpha),
                                   (radius, radius), radius, min(4, radius - 1))
                surf.blit(glow, (int(x) - radius, int(y) - radius))

        elif etype == "spawn_dark":
            # Dark portal
            radius = max(1, int(15 * (1 - progress)))
            alpha = max(0, min(255, int(160 * (1 - progress))))
            if radius > 2 and alpha > 5:
                portal = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(portal, (40, 20, 60, alpha),
                                   (radius + 2, radius + 2), radius)
                pygame.draw.circle(portal, (80, 40, 100, alpha),
                                   (radius + 2, radius + 2), radius, min(2, radius - 1))
                surf.blit(portal, (int(x) - radius - 2, int(y) - radius - 2))
