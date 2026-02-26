import math
from config.tower_data import TOWERS
from config.settings import MAX_TOWER_LEVEL, SELL_REFUND_RATE, TILE_SIZE
from entities.projectile import Projectile


class Tower:
    _id_counter = 0

    def __init__(self, tower_type, col, row):
        Tower._id_counter += 1
        self.id = f"t_{Tower._id_counter}"
        self.tower_type = tower_type
        self.col = col
        self.row = row
        stats = TOWERS[tower_type]
        self.pixel_x = col * TILE_SIZE + TILE_SIZE // 2
        self.pixel_y = row * TILE_SIZE + TILE_SIZE // 2
        self.level = 1
        self.damage = stats["damage"]
        self.range = stats["range"]
        self.fire_rate = stats["fire_rate"]
        self.projectile_speed = stats["projectile_speed"]
        self.color = stats["color"]
        self.projectile_color = stats["projectile_color"]
        self.letter = stats["letter"]
        self.can_hit_flying = stats["can_hit_flying"]
        self.aoe_radius = stats["aoe_radius"]
        self.dot_damage = stats["dot_damage"]
        self.dot_duration = stats["dot_duration"]
        self.slow_factor = stats["slow_factor"]
        self.slow_duration = stats["slow_duration"]
        self.cooldown = 0.0
        self.target = None
        self.total_invested = stats["cost"]

    def update(self, dt, enemies):
        """Update tower, return list of new projectiles."""
        self.cooldown -= dt
        projectiles = []

        # Find target
        self.target = self._find_target(enemies)

        if self.target and self.cooldown <= 0:
            proj = Projectile(
                self.pixel_x, self.pixel_y, self.target,
                self.damage, self.projectile_speed, self.projectile_color,
                self.aoe_radius, self.dot_damage, self.dot_duration,
                self.slow_factor, self.slow_duration,
                tower_type=self.tower_type,
            )
            projectiles.append(proj)
            self.cooldown = 1.0 / self.fire_rate

        return projectiles

    def _find_target(self, enemies):
        """Find enemy furthest along path within range."""
        best = None
        best_progress = -1
        for enemy in enemies:
            if not enemy.alive or enemy.reached_end:
                continue
            if enemy.flying and not self.can_hit_flying:
                continue
            dx = enemy.x - self.pixel_x
            dy = enemy.y - self.pixel_y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= self.range and enemy.progress() > best_progress:
                best = enemy
                best_progress = enemy.progress()
        return best

    def can_upgrade(self):
        return self.level < MAX_TOWER_LEVEL

    def get_upgrade_cost(self):
        return TOWERS[self.tower_type]["upgrade_cost"] * self.level

    def upgrade(self):
        if not self.can_upgrade():
            return False
        stats = TOWERS[self.tower_type]
        cost = self.get_upgrade_cost()
        self.level += 1
        self.damage += stats["upgrade_damage_bonus"]
        self.range += stats["upgrade_range_bonus"]
        self.total_invested += cost
        # Brighten color per level
        r, g, b = self.color
        self.color = (min(255, r + 30), min(255, g + 30), min(255, b + 30))
        return True

    def get_sell_value(self):
        return int(self.total_invested * SELL_REFUND_RATE)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.tower_type,
            "col": self.col,
            "row": self.row,
            "pixel_x": self.pixel_x,
            "pixel_y": self.pixel_y,
            "level": self.level,
            "damage": self.damage,
            "range": self.range,
            "color": self.color,
            "letter": self.letter,
        }
