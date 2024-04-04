import src.geometry as geometry


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


# square grid (declare ccw)
RIGHT_TRI = geometry.Polygon([(0, 0), (0, 1), (1, 0)])
SQUARE = geometry.Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
HALF_SQUARE = geometry.Polygon([(0, 0), (0, 1), (2, 1), (2, 0)])
SHANK = geometry.Polygon([(0, 0), (0, 1), (1, 2), (1, 0)])
PARALLELOGRAM = geometry.Polygon([(0, 0), (1, 1), (2, 1), (1, 0)])

# hex grid
DIAMOND = geometry.Polygon([(0.6666666666666667, 0.7886751345948129), (1.0, 0.21132486540518713), (0.3333333333333334, 0.21132486540518713), (0.0, 0.7886751345948129)])
EQ_TRI = geometry.Polygon([(1.0, 0.06698729810778081), (0.0, 0.06698729810778081), (0.5, 0.9330127018922192)])


LEVELS = [
    Level(("SQUARE", 4), decay_rate=0.015, max_vertices=5),  # 5 rows
    Level(("RECT", (3, 5)), decay_rate=0.02, min_vertices=3),
    Level(("HEX", (3, 5)), decay_rate=0.015, min_vertices=4),
    Level(("HEX", (5, 5)), decay_rate=0.02, boost_rate=1.5, min_vertices=4, max_vertices=5),  # good

    Level(("SQUARE", 4), decay_rate=0.03, boost_rate=0.75, banned_polys=[RIGHT_TRI, HALF_SQUARE]),  # 5 rows
    Level(("RECT", (4, 5)), decay_rate=0.03, boost_rate=0.75, min_vertices=4, banned_polys=[SQUARE, RIGHT_TRI, HALF_SQUARE]),
    Level(("HEX", (3, 4)), decay_rate=0.05, base_cure_time=7, min_vertices=4, banned_polys=[EQ_TRI, DIAMOND]),
    Level(("HEX", (5, 5)), decay_rate=0.03, boost_rate=0.75, min_vertices=3, banned_polys=[EQ_TRI, DIAMOND]),

    Level(("SQUARE", 4), decay_rate=0.05, boost_rate=1, min_vertices=4, banned_polys=[RIGHT_TRI, HALF_SQUARE, SHANK], slab_req=30),  # 10 rows
    Level(("RECT", (5, 5)), decay_rate=0.04, boost_rate=1, min_vertices=4, banned_polys=[RIGHT_TRI, HALF_SQUARE, SHANK], slab_req=30),
    Level(("HEX", (3, 5)), decay_rate=0.07, boost_rate=0.8, base_cure_time=3, min_vertices=4, banned_polys=[EQ_TRI, DIAMOND], slab_req=30),
    Level(("HEX", (5, 5)), decay_rate=0.04, boost_rate=1, min_vertices=4, banned_polys=[EQ_TRI], slab_req=30),

    Level(("SQUARE", 4), decay_rate=0.08, boost_rate=0.9, base_cure_time=2, max_temp_cure_boost=1.8, min_vertices=3, banned_polys=[SQUARE, RIGHT_TRI, HALF_SQUARE, SHANK], slab_req=45),
]