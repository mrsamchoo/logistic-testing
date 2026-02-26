from config.settings import (
    STARTING_GOLD, STARTING_LIVES, GOLD_PER_SECOND,
    WAVE_CLEAR_BONUS_BASE, WAVE_CLEAR_BONUS_PER_WAVE,
    BETWEEN_WAVE_TIME,
)
from config.tower_data import TOWERS
from config.enemy_data import ENEMIES
from config.wave_data import WAVES
from core.map_grid import MapGrid
from entities.tower import Tower
from entities.enemy import Enemy
from entities.projectile import Projectile


class WaveSpawner:
    """Spawns enemies for one wave according to wave_data."""

    def __init__(self, waypoints_pixels):
        self.waypoints = waypoints_pixels
        self.groups = []       # [(enemy_type, remaining_count, interval, timer)]
        self.active = False

    def start_wave(self, wave_number):
        if wave_number < 0 or wave_number >= len(WAVES):
            return
        self.groups = []
        for enemy_type, count, interval in WAVES[wave_number]:
            self.groups.append([enemy_type, count, interval, 0.0])
        self.active = True

    def update(self, dt):
        """Returns list of newly spawned Enemy objects."""
        if not self.active:
            return []

        spawned = []
        all_done = True
        for group in self.groups:
            etype, remaining, interval, timer = group
            if remaining <= 0:
                continue
            all_done = False
            group[3] += dt
            if group[3] >= interval:
                group[3] -= interval
                group[1] -= 1
                spawned.append(Enemy(etype, self.waypoints))

        if all_done:
            self.active = False

        return spawned

    @property
    def is_done(self):
        return not self.active


class LaneGame:
    """Manages one player's lane: towers, enemies, gold, lives."""

    def __init__(self, map_grid):
        self.map = map_grid
        self.towers = []
        self.enemies = []
        self.projectiles = []
        self.gold = STARTING_GOLD
        self.lives = STARTING_LIVES
        self.wave_number = -1  # -1 = not started
        self.spawner = WaveSpawner(map_grid.get_waypoints_pixels())
        self.income_timer = 0.0
        self.phase = "waiting"  # "waiting", "combat", "between_waves", "game_over"
        self.between_wave_timer = 0.0
        self.notifications = []  # [(text, remaining_time)]
        self.recently_dead = []  # [(x, y, enemy_type)] - cleared each frame

    def update(self, dt):
        if self.phase == "game_over":
            return

        # Passive income
        self.income_timer += dt
        if self.income_timer >= 1.0:
            self.gold += GOLD_PER_SECOND
            self.income_timer -= 1.0

        # Between waves timer
        if self.phase == "between_waves":
            self.between_wave_timer -= dt
            if self.between_wave_timer <= 0:
                self._start_next_wave()

        # Spawn enemies
        new_enemies = self.spawner.update(dt)
        self.enemies.extend(new_enemies)

        # Update enemies
        for enemy in self.enemies:
            enemy.update(dt)

        # Update towers
        for tower in self.towers:
            new_projs = tower.update(dt, self.enemies)
            self.projectiles.extend(new_projs)

        # Update projectiles
        for proj in self.projectiles:
            proj.update(dt, self.enemies)

        # Process dead enemies (gold + death tracking)
        self.recently_dead = []
        for enemy in self.enemies:
            if not enemy.alive and enemy.gold_reward > 0:
                self.gold += enemy.gold_reward
                enemy.gold_reward = 0  # prevent double-collect
                self.recently_dead.append((enemy.x, enemy.y, enemy.enemy_type))

        # Process enemies that reached end
        for enemy in self.enemies:
            if enemy.reached_end and enemy.gold_reward >= 0:
                self.lives -= 1
                enemy.gold_reward = -1  # mark as processed

        # Clean up
        self.enemies = [e for e in self.enemies if e.alive and not e.reached_end]
        self.projectiles = [p for p in self.projectiles if p.alive]

        # Check wave complete
        if self.phase == "combat" and self.spawner.is_done and len(self.enemies) == 0:
            bonus = WAVE_CLEAR_BONUS_BASE + WAVE_CLEAR_BONUS_PER_WAVE * (self.wave_number + 1)
            self.gold += bonus
            self.add_notification(f"Wave {self.wave_number + 1} Clear! +{bonus}g")
            self.phase = "between_waves"
            self.between_wave_timer = BETWEEN_WAVE_TIME

        # Check game over
        if self.lives <= 0:
            self.lives = 0
            self.phase = "game_over"

        # Update notifications
        self.notifications = [(t, r - dt) for t, r in self.notifications if r - dt > 0]

    def start_game(self):
        """Start wave 1."""
        self.phase = "combat"
        self.wave_number = 0
        self.spawner.start_wave(0)
        self.add_notification("Wave 1 Start!")

    def _start_next_wave(self):
        self.wave_number += 1
        if self.wave_number >= len(WAVES):
            self.phase = "game_over"
            self.add_notification("You survived all waves!")
            return
        self.phase = "combat"
        self.spawner.start_wave(self.wave_number)
        self.add_notification(f"Wave {self.wave_number + 1} Start!")

    def skip_to_next_wave(self):
        """Player manually starts next wave early (bonus gold?)."""
        if self.phase == "between_waves":
            self._start_next_wave()
        elif self.phase == "waiting":
            self.start_game()

    def place_tower(self, tower_type, col, row):
        if tower_type not in TOWERS:
            return False
        cost = TOWERS[tower_type]["cost"]
        if self.gold < cost:
            return False
        if not self.map.can_place_tower(col, row):
            return False
        self.gold -= cost
        tower = Tower(tower_type, col, row)
        self.towers.append(tower)
        self.map.place_tower(col, row)
        return True

    def sell_tower(self, tower_id):
        for tower in self.towers:
            if tower.id == tower_id:
                self.gold += tower.get_sell_value()
                self.map.remove_tower(tower.col, tower.row)
                self.towers.remove(tower)
                return True
        return False

    def upgrade_tower(self, tower_id):
        for tower in self.towers:
            if tower.id == tower_id:
                cost = tower.get_upgrade_cost()
                if self.gold >= cost and tower.can_upgrade():
                    self.gold -= cost
                    tower.upgrade()
                    return True
        return False

    def get_tower_at(self, col, row):
        for tower in self.towers:
            if tower.col == col and tower.row == row:
                return tower
        return None

    def spawn_extra_enemies(self, enemy_type, count):
        """Spawn enemies sent by opponent."""
        waypoints = self.map.get_waypoints_pixels()
        for _ in range(count):
            self.enemies.append(Enemy(enemy_type, waypoints))
        self.add_notification(f"Incoming: {count}x {ENEMIES[enemy_type]['name']}!")

    def add_notification(self, text, duration=3.0):
        self.notifications.append((text, duration))

    def get_state(self):
        return {
            "gold": self.gold,
            "lives": self.lives,
            "wave_number": self.wave_number,
            "phase": self.phase,
            "between_wave_timer": round(self.between_wave_timer, 1),
            "towers": [t.to_dict() for t in self.towers],
            "enemies": [e.to_dict() for e in self.enemies],
            "projectiles": [p.to_dict() for p in self.projectiles],
            "notifications": self.notifications,
            "recently_dead": [(round(x, 1), round(y, 1), t)
                              for x, y, t in self.recently_dead],
        }
