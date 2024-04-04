

class Level:

    def __init__(self, style, decay_rate=0.03, boost_rate=0.5, base_cure_time=10, max_temp_cure_boost=1.5, min_vertices=4, max_vertices=float('inf'), slab_req=15, banned_polys=()):
        self.style = style
        self.decay_rate = decay_rate  # percent max per second
        self.base_cure_time = base_cure_time  # sec
        self.max_temp_cure_boost = max_temp_cure_boost
        self.boost_rate = boost_rate  # percent max of slab board coverage
        self.min_vertices = min_vertices
        self.max_vertices = max_vertices
        self.slab_req = slab_req
        self.banned_polys = banned_polys


LEVELS = [
    Level(("SQUARE", 4), decay_rate=0.03, max_vertices=6),
    Level(("RECT", (3, 5))),
    Level(("SQUARE", 5), min_vertices=5),
    Level(("RECT", (4, 3))),
    Level(("HEX", (5, 5))),
    Level(("HEX", (3, 5)))
]