import math


class Projectile:
    def __init__(self, x, y, target_enemy, damage, speed, color,
                 aoe_radius=0, dot_damage=0, dot_duration=0,
                 slow_factor=0, slow_duration=0, tower_type="archer"):
        self.x = float(x)
        self.y = float(y)
        self.target = target_enemy
        self.damage = damage
        self.speed = speed
        self.color = color
        self.tower_type = tower_type
        self.aoe_radius = aoe_radius
        self.dot_damage = dot_damage
        self.dot_duration = dot_duration
        self.slow_factor = slow_factor
        self.slow_duration = slow_duration
        self.alive = True
        self.radius = 4

    def update(self, dt, all_enemies):
        if not self.alive:
            return

        # If target is dead, die too
        if not self.target.alive and not self.target.reached_end:
            self.alive = False
            return

        # Move toward target
        dx = self.target.x - self.x
        dy = self.target.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < self.speed * dt + self.target.radius:
            self._hit(all_enemies)
            return

        self.x += (dx / dist) * self.speed * dt
        self.y += (dy / dist) * self.speed * dt

    def _hit(self, all_enemies):
        self.alive = False

        if self.aoe_radius > 0:
            # AOE: damage all enemies in radius
            for enemy in all_enemies:
                if not enemy.alive:
                    continue
                dx = enemy.x - self.target.x
                dy = enemy.y - self.target.y
                if math.sqrt(dx * dx + dy * dy) <= self.aoe_radius:
                    enemy.take_damage(self.damage)
                    self._apply_effects(enemy)
        else:
            # Single target
            if self.target.alive:
                self.target.take_damage(self.damage)
                self._apply_effects(self.target)

    def _apply_effects(self, enemy):
        if self.dot_damage > 0 and self.dot_duration > 0:
            enemy.apply_burn(self.dot_damage, self.dot_duration)
        if self.slow_factor > 0 and self.slow_duration > 0:
            enemy.apply_slow(self.slow_factor, self.slow_duration)

    def to_dict(self):
        return {
            "x": round(self.x, 1),
            "y": round(self.y, 1),
            "color": self.color,
            "tower_type": self.tower_type,
            "aoe_radius": self.aoe_radius,
        }
