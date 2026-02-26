# Each wave: list of (enemy_type, count, spawn_interval_seconds)
WAVES = [
    # Wave 1: Easy intro
    [("goblin", 5, 1.0)],
    # Wave 2
    [("goblin", 8, 0.8)],
    # Wave 3: Introduce orcs
    [("goblin", 5, 0.8), ("orc", 2, 1.5)],
    # Wave 4
    [("goblin", 8, 0.6), ("orc", 4, 1.2)],
    # Wave 5: Introduce dark knights
    [("orc", 5, 1.0), ("dark_knight", 2, 2.0)],
    # Wave 6
    [("goblin", 10, 0.5), ("dark_knight", 3, 1.5)],
    # Wave 7
    [("orc", 6, 0.8), ("dark_knight", 4, 1.2)],
    # Wave 8: Big goblin rush
    [("goblin", 20, 0.3), ("orc", 3, 1.0)],
    # Wave 9: Heavy armor
    [("dark_knight", 8, 1.0), ("orc", 5, 0.8)],
    # Wave 10: First dragon!
    [("orc", 6, 0.8), ("dark_knight", 4, 1.0), ("dragon", 1, 3.0)],
    # Wave 11
    [("goblin", 15, 0.3), ("dark_knight", 5, 1.0), ("dragon", 1, 3.0)],
    # Wave 12
    [("orc", 8, 0.6), ("dark_knight", 6, 0.8), ("dragon", 2, 2.5)],
    # Wave 13: Dragon duo
    [("dark_knight", 8, 0.8), ("dragon", 3, 2.0)],
    # Wave 14: Everything
    [("goblin", 20, 0.2), ("orc", 10, 0.5), ("dark_knight", 6, 0.8), ("dragon", 2, 2.0)],
    # Wave 15: Final boss wave
    [("dark_knight", 10, 0.5), ("dragon", 5, 1.5)],
]
