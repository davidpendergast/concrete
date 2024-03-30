import math
import typing
import random

import const
import src.convexhull as convexhull
import src.utils as utils

import pygame
import src.scenes as scenes
import src.colors as colors

class GameState:

    def __init__(self, style=const.BOARD_STYLES[0]):
        self.board = Board.new_board(*style)


class Board:

    def __init__(self, pegs: typing.List[typing.Tuple[float, float]]):
        self.pegs = pegs
        self.outer_edges = self._calc_outer_edges()

    @staticmethod
    def new_board(style: str, size):
        if style == "SQUARE":
            return Board.new_rectangle_board((size, size))
        if style == "RECT":
            return Board.new_rectangle_board(size)
        if style == "HEX":
            return Board.new_hex_board(size)

    @staticmethod
    def new_rectangle_board(dims: typing.Tuple[int, int]):
        pegs = []

        width = 1
        height = 1
        if dims[0] < dims[1]:
            width = (dims[0] - 1) / (dims[1] - 1)
        elif dims[1] < dims[0]:
            height = (dims[1] - 1) / (dims[0] - 1)

        for x_idx in range(dims[0]):
            for y_idx in range(dims[1]):
                x = (x_idx / (dims[0] - 1)) * width + (1 - width) / 2
                y = (y_idx / (dims[1] - 1)) * height + (1 - height) / 2
                pegs.append((x, y))
        return Board(pegs)

    @staticmethod
    def new_hex_board(size):
        rows, cols = size
        if rows % 2 == 0:
            raise ValueError(f"rows must be odd: {rows}")
        board_height = (rows - 1) / (cols - 1) * math.sqrt(3) / 2
        pegs = []
        for y in range(rows):
            n_pts_in_row = cols - int(abs(y - (rows - 1) / 2))
            y_pos = y / (rows - 1) * board_height + (1 - board_height) / 2
            if n_pts_in_row > 0:
                row_total_width = (n_pts_in_row - 1) / (cols - 1)
                x_start = 0.5 - row_total_width / 2
                x_spacing = 1 / (cols - 1)
                for x in range(n_pts_in_row):
                    pegs.append((x_start + x * x_spacing, y_pos))
        return Board(pegs)

    def _calc_outer_edges(self) -> 'EdgeSet':
        res = EdgeSet()
        outer_pegs = convexhull.compute(self.pegs, include_colinear_edge_points=True)
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

        self.board_style_idx = 0

    def update(self, dt):
        super().update(dt)

        if pygame.K_r in const.KEYS_PRESSED_THIS_FRAME:
            self.board_style_idx += 1
            style = const.BOARD_STYLES[self.board_style_idx % len(const.BOARD_STYLES)]
            print(f"INFO: activating new board style {style}")
            self.gs = GameState(style)

    def board_xy_to_screen_xy(self, board_xy):
        return (int(self.board_area[0] + board_xy[0] * self.board_area[2]),
                int(self.board_area[1] + board_xy[1] * self.board_area[3]))

    def screen_xy_to_board_xy(self, screen_xy):
        return ((screen_xy[0] - self.board_area[0]) / self.board_area[2],
                (screen_xy[1] - self.board_area[1]) / self.board_area[3])

    def _shorten_line(self, p1, p2, px):
        mag = utils.dist(p1, p2)
        center = utils.lerp(p1, p2, 0.5)
        v1 = utils.set_length(utils.sub(p1, center), mag / 2 - px / 2)
        v2 = utils.set_length(utils.sub(p2, center), mag / 2 - px / 2)
        return (utils.add(v1, center), utils.add(v2, center))

    def render(self, surf: pygame.Surface):
        pygame.draw.rect(surf, colors.BLACK, self.board_area)  # background

        for edge in self.gs.board.outer_edges:  # outline
            p1 = self.board_xy_to_screen_xy(edge.p1)
            p2 = self.board_xy_to_screen_xy(edge.p2)
            p1, p2 = self._shorten_line(p1, p2, 16)

            pygame.draw.line(surf, colors.BOARD_LINE_COLOR, p1, p2, width=1)

        for peg in self.gs.board.pegs:  # nodes
            pygame.draw.circle(surf, colors.BOARD_LINE_COLOR, self.board_xy_to_screen_xy(peg), 4)

    def get_bg_color(self):
        return colors.DARK_GRAY



