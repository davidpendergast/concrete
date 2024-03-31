import typing
import random

import src.geometry as geometry
import src.gameplay as gameplay
import src.utils as utils

class PolygonGoal:
    def __init__(self, polygon: geometry.Polygon):
        self.polygon = polygon


class GoalGenerator:

    def __init__(self, board, params: 'GoalGenParams'):
        self.board = board.copy(exclude_edges=True)

        self.params = params
        self.buffer = []

    def gen_next_goal(self, max_tries=float('inf')) -> PolygonGoal:
        cnt = 0
        while len(self.buffer) == 0:
            if cnt > max_tries:
                print(f"WARN: failed to find a valid goal after {cnt} tries")
                break
            cnt += 1
            self.board.clear_user_edges(force=True)
            PolygonGoalFactory.subdivide_board(self.board, self.params)

            polys = self.board.calc_regions(normalize=True)
            for p in polys:
                if self.params.accepts(p):
                    self.buffer.append(p)

        if len(self.buffer) > 0:
            return self.buffer.pop()
        else:
            return None

class GoalGenParams:

    def __init__(self):
        self.small_edge_bias = 0.5
        self.pcnt_edges_to_try = 0.2
        self.max_n_vertices = float('inf')
        self.min_n_vertices = 3

    def accepts(self, polygon) -> bool:
        if not (self.min_n_vertices <= len(polygon.get_angles()) <= self.max_n_vertices):
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


