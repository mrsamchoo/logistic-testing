import math
from config.enemy_data import ENEMIES


class Enemy:
    _id_counter = 0

    def __init__(self, enemy_type, waypoints_pixels):
        Enemy._id_counter += 1
        self.id = f"e_{Enemy._id_counter}"
        self.enemy_type = enemy_type
        stats = ENEMIES[enemy_type]
        self.waypoints = waypoints_pixels
        self.current_wp = 0
        self.x, self.y = float(waypoints_pixels[0][0]), float(waypoints_pixels[0][1])
        self.max_hp = stats["hp"]
        self.hp = stats["hp"]
        self.base_speed = stats["speed"]
        self.speed = stats["speed"]
        self.armor = stats["armor"]
        self.gold_reward = stats["gold_reward"]
        self.flying = stats["flying"]
        self.color = stats["color"]
        self.radius = stats["radius"]
        self.alive = True
        self.reached_end = False
        self.effects = []  # {"type": "slow"/"burn", "remaining": float, ...}

    def update(self, dt):
        if not self.alive or self.reached_end:
            return

        # Apply status effects
        self._update_effects(dt)

        # Move toward current waypoint
        if self.current_wp >= len(self.waypoints):
            self.reached_end = True
            return

        tx, ty = self.waypoints[self.current_wp]
        dx = tx - self.x
        dy = ty - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        move_dist = self.speed * dt
        if dist <= move_dist:
            self.x, self.y = float(tx), float(ty)
            self.current_wp += 1
            if self.current_wp >= len(self.waypoints):
                self.reached_end = True
        else:
            self.x += (dx / dist) * move_dist
            self.y += (dy / dist) * move_dist

    def _update_effects(self, dt):
        self.speed = self.base_speed
        burn_damage = 0
        remaining = []
        for eff in self.effects:
            eff["remaining"] -= dt
            if eff["remaining"] > 0:
                remaining.append(eff)
                if eff["type"] == "slow":
                    self.speed = self.base_speed * eff["factor"]
                elif eff["type"] == "burn":
                    burn_damage += eff["dps"] * dt
        self.effects = remaining
        if burn_damage > 0:
            self.hp -= burn_damage
            if self.hp <= 0:
                self.hp = 0
                self.alive = False

    def take_damage(self, damage):
        actual = max(0, damage - self.armor)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.alive = False

    def apply_slow(self, factor, duration):
        # Refresh existing slow or add new
        for eff in self.effects:
            if eff["type"] == "slow":
                eff["remaining"] = duration
                eff["factor"] = factor
                return
        self.effects.append({"type": "slow", "remaining": duration, "factor": factor})

    def apply_burn(self, dps, duration):
        # Stack up to 3 burns
        burn_count = sum(1 for e in self.effects if e["type"] == "burn")
        if burn_count < 3:
            self.effects.append({"type": "burn", "remaining": duration, "dps": dps})
        else:
            # Refresh the oldest burn
            for eff in self.effects:
                if eff["type"] == "burn":
                    eff["remaining"] = duration
                    eff["dps"] = dps
                    break

    def progress(self):
        """How far along the path (0.0 to 1.0). Used for targeting priority."""
        if self.current_wp == 0:
            return 0.0
        return self.current_wp / len(self.waypoints)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.enemy_type,
            "x": round(self.x, 1),
            "y": round(self.y, 1),
            "hp": round(self.hp, 1),
            "max_hp": self.max_hp,
            "effects": [e["type"] for e in self.effects],
        }
