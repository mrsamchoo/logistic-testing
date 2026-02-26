import json
import os
from config.settings import TILE_SIZE


class MapGrid:
    """Grid-based map with a path defined by waypoints."""

    GRASS = 0
    PATH = 1
    TOWER = 2

    def __init__(self, grid_data, waypoints):
        self.grid = [row[:] for row in grid_data]
        self.waypoints = waypoints  # list of [col, row]
        self.rows = len(grid_data)
        self.cols = len(grid_data[0])

    def can_place_tower(self, col, row):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[row][col] == self.GRASS
        return False

    def place_tower(self, col, row):
        self.grid[row][col] = self.TOWER

    def remove_tower(self, col, row):
        self.grid[row][col] = self.GRASS

    def grid_to_pixel(self, col, row):
        """Convert grid coords to pixel center of tile."""
        return (col * TILE_SIZE + TILE_SIZE // 2,
                row * TILE_SIZE + TILE_SIZE // 2)

    def pixel_to_grid(self, px, py):
        """Convert pixel position to grid coords."""
        return (px // TILE_SIZE, py // TILE_SIZE)

    def get_waypoints_pixels(self):
        """Return waypoints as pixel center coordinates."""
        return [self.grid_to_pixel(c, r) for c, r in self.waypoints]

    @classmethod
    def load_from_json(cls, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(data["grid"], data["waypoints"])

    def copy(self):
        return MapGrid(self.grid, self.waypoints)
