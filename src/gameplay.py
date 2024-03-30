import typing

import const
import src.convexhull as convexhull

import pygame
import src.scenes as scenes
import src.colors as colors

class GameState:
    def __init__(self):
        self.board = Board.new_square_board((4, 4))


class Board:

    def __init__(self, pegs: typing.List[typing.Tuple[float, float]]):
        self.pegs = pegs
        self.outer_edges = self._calc_outer_edges()

    @staticmethod
    def new_square_board(dims: typing.Tuple[int, int]):
        pegs = []
        for x_idx in range(dims[0]):
            for y_idx in range(dims[1]):
                pegs.append((x_idx / (dims[0]-1), y_idx / (dims[1]-1)))
        return Board(pegs)

    def _calc_outer_edges(self) -> 'EdgeSet':
        res = EdgeSet()
        outer_pegs = convexhull.compute(self.pegs)
        for i in range(len(outer_pegs)):
            p1 = outer_pegs[i]
            p2 = outer_pegs[(i + 1) % len(outer_pegs)]
            res.add(Edge(p1, p2))
        return res

    def all_nodes(self):
        for n in self.pegs:
            yield n

class Edge:

    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

    def points(self):
        return (self.p1, self.p2)

    def __eq__(self, other):
        return (self.p1 == other.p1 and self.p2 == other.p2) \
            or (self.p2 == other.p1 and self.p1 == other.p2)

    def __hash__(self):
        return hash(self.p1) + hash(self.p2)

class EdgeSet:

    def __init__(self):
        self.edges = set()
        self.points_to_edges = {}  # pt -> set of Edges

    def add(self, edge: Edge):
        self.edges.add(edge)
        for p in edge.points():
            if p not in self.points_to_edges:
                self.points_to_edges[p] = set()
            self.points_to_edges[p].add(edge)
        return self

    def add_all(self, edges):
        for e in edges:
            self.add(e)
        return self

    def remove(self, edge: Edge):
        if edge in self.edges:
            self.edges.remove(edge)
            for p in edge.points():
                if p in self.points_to_edges:
                    if edge in self.points_to_edges[p]:
                        self.points_to_edges[p].remove(edge)
                    if len(self.points_to_edges[p]) == 0:
                        del self.points_to_edges[p]

    def remove_all(self, edges):
        for e in edges:
            self.remove(e)

    def clear(self):
        self.edges.clear()
        self.points_to_edges.clear()

    def __contains__(self, edge):
        return edge in self.edges

    def __len__(self):
        return len(self.edges)

    def __iter__(self):
        return self.edges.__iter__()


class GameplayScene(scenes.Scene):

    def __init__(self, gs: GameState):
        super().__init__()
        self.gs = gs
        self.board_area = [(const.GAME_DIMS[0] - const.BOARD_SIZE) / 2,
                           (const.GAME_DIMS[1] - const.BOARD_SIZE) / 2,
                           const.BOARD_SIZE, const.BOARD_SIZE]

    def update(self, dt):
        super().update(dt)

    def board_xy_to_screen_xy(self, board_xy):
        return (int(self.board_area[0] + board_xy[0] * self.board_area[2]),
                int(self.board_area[1] + board_xy[1] * self.board_area[3]))

    def screen_xy_to_board_xy(self, screen_xy):
        return ((screen_xy[0] - self.board_area[0]) / self.board_area[2],
                (screen_xy[1] - self.board_area[1]) / self.board_area[3])

    def render(self, surf: pygame.Surface):
        for edge in self.gs.board.outer_edges:
            p1 = self.board_xy_to_screen_xy(edge.p1)
            p2 = self.board_xy_to_screen_xy(edge.p2)
            pygame.draw.line(surf, colors.LIGHT_GRAY, p1, p2, width=2)

        for peg in self.gs.board.pegs:
            pygame.draw.circle(surf, colors.WHITE, self.board_xy_to_screen_xy(peg), 3)



    def get_bg_color(self):
        return colors.DARK_GRAY



