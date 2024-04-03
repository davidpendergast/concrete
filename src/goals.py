import pygame
import typing
import random

import src.geometry as geometry
import src.gameplay as gameplay
import src.utils as utils
import src.colors as colors

class PolygonGoal:

    def __init__(self, polygon: geometry.Polygon):
        self.polygon = polygon.normalize()
        self.actual = None

    def is_satisfied_by(self, region):
        return self.polygon.is_equivalent_by_angles_and_edge_ratios(region.polygon)

    def set_satisfied(self, region):
        if self.is_satisfied_by(region):
            self.actual = region
            return True
        else:
            return False

    def is_satisfied(self):
        return self.actual is not None

    def is_satisfied_and_finished(self):
        return self.is_satisfied() and self.actual.is_done()

    def get_image(self, size, bg_color, fg_color, rot=0, width=2, inset=2) -> pygame.Surface:
        res = pygame.Surface((size, size))
        res.fill(bg_color)
        poly = self.polygon
        if rot != 0:
            poly = poly.rotate(rot)
        scaled_poly = poly.normalize([inset, inset, size-inset*2, size-inset*2], preserve_aspect_ratio=True)
        pygame.draw.polygon(res, fg_color, scaled_poly.vertices, width=width)
        return res

    def __repr__(self):
        return f"{type(self).__name__}({self.polygon})"


class GoalGenerator:

    def __init__(self, board, params: 'GoalGenParams'):
        self.board = board.copy(exclude_edges=True)

        self.params = params
        self.buffer = []

    def gen_next_goal(self, temp_banned_shapes=(), max_tries=float('inf')) -> PolygonGoal:

        def accepts_poly(p):
            return self.params.accepts(p) and \
                    not any(p.is_equivalent_by_angles_and_edge_ratios(s) for s in temp_banned_shapes)

        self.buffer = [p for p in self.buffer if accepts_poly(p)]

        cnt = 0
        while len(self.buffer) == 0:
            if cnt > max_tries:
                print(f"WARN: failed to find a valid goal after {cnt} tries")
                break
            cnt += 1
            self.board.clear_user_edges(force=True)
            PolygonGoalFactory.subdivide_board(self.board, self.params)

            polys = [p.normalize() for p in self.board.calc_polygons()]
            for p in polys:
                if accepts_poly(p):
                    self.buffer.append(p)

        if len(self.buffer) > 0:
            return PolygonGoal(self.buffer.pop())
        else:
            return None

class GoalGenParams:

    def __init__(self):
        self.small_edge_bias = 0.5
        self.pcnt_edges_to_try = 0.2
        self.max_n_vertices = float('inf')
        self.min_n_vertices = 3
        self.banned_polys = []

    def accepts(self, polygon) -> bool:
        if not (self.min_n_vertices <= len(polygon.get_angles()) <= self.max_n_vertices):
            return False
        if any(p.is_equivalent_by_angles_and_edge_ratios(polygon) for p in self.banned_polys):
            return False
        return True

class PolygonGoalFactory:

    @staticmethod
    def subdivide_board(board, params: GoalGenParams):
        all_nodes = list(board.all_nodes())

        all_possible_edges = []
        for i in range(0, len(all_nodes) - 1):
            for j in range(i + 1, len(all_nodes)):
                if not board.is_outer_node(all_nodes[i]) or not board.is_outer_node(all_nodes[j]):
                    all_possible_edges.append(gameplay.Edge(all_nodes[i], all_nodes[j]))

        random.shuffle(all_possible_edges)
        all_possible_edges.sort(key=lambda e: e.length())
        all_possible_edges = utils.lightly_shuffle(all_possible_edges, strength=(1 - params.small_edge_bias))

        n_to_try = int(params.pcnt_edges_to_try * len(all_possible_edges))
        failed = 0

        for i in range(n_to_try):
            edge = all_possible_edges[i]
            if board.can_add_user_edge(edge):
                board.add_user_edge(edge)
            else:
                failed += 1

        if n_to_try > 0:
            print(f"INFO: added {(n_to_try-failed)}/{n_to_try} edges ({100*(n_to_try-failed)/n_to_try:.2f}%) of {len(all_possible_edges)} possible edges.")

        return board


