import math
import typing
import random

import const
import src.convexhull as convexhull
import src.utils as utils

import pygame
import src.scenes as scenes
import src.colors as colors
import src.geometry as geometry
import src.goals as goals

class GameState:

    def __init__(self, style=const.BOARD_STYLES[0]):
        self.board = Board.new_board(*style)
        self.goal_generator = goals.GoalGenerator(self.board, goals.GoalGenParams())
        self.goals = []


class Board:

    def __init__(self, pegs: typing.Iterable[typing.Tuple[float, float]]):
        self.pegs = set(pegs)
        self.outer_edges = self._calc_outer_edges()
        self.user_edges = EdgeSet()

    def copy(self, exclude_edges=False):
        res = Board(self.pegs)
        if not exclude_edges:
            res.user_edges.add_all(self.user_edges)
        return res

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
        outer_pegs = convexhull.compute(list(self.pegs), include_colinear_edge_points=True)
        for i in range(len(outer_pegs)):
            p1 = outer_pegs[i]
            p2 = outer_pegs[(i + 1) % len(outer_pegs)]
            res.add(Edge(p1, p2))
        return res

    def try_to_split(self, edge):
        pts_inside = [edge.p1]
        for pt in self.all_nodes():
            if edge.contains_point(pt, including_endpoints=False):
                pts_inside.append(pt)
        pts_inside.append(edge.p2)
        if len(pts_inside) == 2:
            return [edge]
        else:
            pts_inside.sort(key=lambda x: utils.dist(edge.p1, x))
            res = []
            for i in range(len(pts_inside) - 1):
                res.append(Edge(pts_inside[i], pts_inside[i + 1]))
            return res

    def can_add_user_edge(self, edge, split_if_necessary=True, get_problems=False):
        split_edges = self.try_to_split(edge) if split_if_necessary else [edge]
        problems = {}

        def add_problem(key, edge_val):
            if key not in problems:
                problems[key] = EdgeSet()
            if isinstance(edge_val, Edge):
                problems[key].add(edge_val)
            else:
                problems[key].add_all(edge_val)

        if edge.p1 not in self.pegs or edge.p2 not in self.pegs:
            if not get_problems:
                return False
            else:
                add_problem('invalid_endpoint', edge)

        for edge in split_edges:
            if edge in self.user_edges:
                if not get_problems:
                    return False
                else:
                    add_problem('overlaps', edge)
            if edge in self.outer_edges:
                if not get_problems:
                    return False
                else:
                    add_problem('overlaps_outer', edge)

            if any(edge.intersects(e) for e in self.user_edges):
                if not get_problems:
                    return False
                else:
                    add_problem('intersects', [e for e in self.user_edges if edge.intersects(e)])

        if get_problems:
            return problems
        else:
            return True

    def add_user_edge(self, edge: 'Edge', split_if_necessary=True) -> bool:
        split_edges = self.try_to_split(edge) if split_if_necessary else [edge]

        if all(self.can_add_user_edge(e, split_if_necessary=False) for e in split_edges):
            self.user_edges.add_all(split_edges)
            return True
        else:
            return False

    def can_remove_user_edge(self, edge: 'Edge') -> bool:
        # TODO can't remove if it's holding concrete
        return edge in self.user_edges

    def remove_user_edge(self, edge: 'Edge') -> bool:
        if self.can_remove_user_edge(edge):
            self.user_edges.remove(edge)
            return True
        return False

    def clear_user_edges(self, force=False):
        if force:
            self.user_edges.clear()  # not wise if there's active concrete
        else:
            all_edges = list(self.all_edges(including_outer=False))
            for edge in all_edges:
                if self.can_remove_user_edge(edge):
                    self.remove_user_edge(edge)

    def get_closest_edge(self, xy, max_dist=float('inf'), including_outer=True):
        in_range = self.get_edges_in_circle(xy, radius=max_dist, including_outer=including_outer)
        return in_range[0] if len(in_range) > 0 else None

    def get_edges_in_circle(self, xy, radius, including_outer=True):
        res = []
        for edge in self.all_edges(including_outer=including_outer):
            if edge.dist_to_point(xy) <= radius:
                res.append(edge)
        res.sort(key=lambda x: x.dist_to_point(xy))
        return res

    def all_edges(self, including_outer=True):
        for e in self.user_edges:
            yield e
        if including_outer:
            for e in self.outer_edges:
                yield e

    def get_closest_node(self, xy, max_dist=float('inf')):
        # TODO not very efficient
        all_in_range = self.get_nodes_in_circle(xy, max_dist)
        return all_in_range[0] if len(all_in_range) > 0 else None

    def get_nodes_in_circle(self, xy, radius):
        res = []
        for n in self.all_nodes():
            if utils.dist(xy, n) <= radius:
                res.append(n)
        res.sort(key=lambda x: utils.dist(xy, x))
        return res

    def all_nodes(self):
        for n in self.pegs:
            yield n

    def is_outer_node(self, xy):
        return xy in self.outer_edges.points_to_edges

    def calc_regions(self, normalize=False) -> typing.List[geometry.Polygon]:

        graph = {}  # node -> list of connected nodes
        for edge in self.all_edges(including_outer=True):
            if edge.p1 not in graph:
                graph[edge.p1] = set()
            if edge.p2 not in graph:
                graph[edge.p2] = set()
            graph[edge.p1].add(edge.p2)
            graph[edge.p2].add(edge.p1)

        def pop_edge(n1, n2):
            edges = graph[n1]
            edges.remove(n2)
            if len(edges) == 0:
                del graph[n1]
                return True
            return False

        def find_next_step(prev, cur):
            v1 = pygame.Vector2(utils.sub(prev, cur))
            best_ang = float('inf')
            best = None
            for n in graph[cur]:
                vn = pygame.Vector2(utils.sub(n, cur))
                ccw_ang = utils.ccw_angle_to_rads(v1, vn)
                if (n != prev and ccw_ang < best_ang) or best is None:
                    best_ang = ccw_ang if n != prev else float('inf')
                    best = n
            return best, (best_ang if best_ang < float('inf') else 0)

        def remove_backtracking(pt_list):
            keep_going = True
            while keep_going and len(pt_list) > 2:
                keep_going = False
                for i in range(len(pt_list)):
                    if pt_list[i] == pt_list[(i + 2) % len(pt_list)]:
                        to_rm = tuple(sorted([(i + 2) % len(pt_list), (i + 1) % len(pt_list)]))
                        pt_list.pop(to_rm[1])
                        pt_list.pop(to_rm[0])
                        keep_going = True
                        break

        polys = []
        while len(graph) > 0:
            path = [next(iter(graph.keys()))]  # choose any first node
            path.append(next(iter(graph[path[0]])))  # choose any first edge
            pop_edge(*path)
            total_ang = 0

            keep_going = True
            while keep_going:
                next_node, ang = find_next_step(path[-2], path[-1])

                pop_edge(path[-1], next_node)
                total_ang += ang - math.pi  # want to end up with 360 or -360 total

                if next_node == path[0]:
                    # completed the loop
                    keep_going = False
                    if total_ang < 0:
                        remove_backtracking(path)
                        if len(path) > 2:
                            polys.append(geometry.Polygon(path, normalize=False))
                    else:
                        pass  # inverted poly, discard
                else:
                    path.append(next_node)

        return polys


class Edge:

    def __init__(self, p1, p2):
        self.p1 = p1  # for the love of god, treat these as immutable
        self.p2 = p2

    def points(self):
        return (self.p1, self.p2)

    def contains_point(self, pt, including_endpoints=False):
        dist = self.dist_to_point(pt)
        if dist < const.THRESH:
            if including_endpoints:
                return True
            else:
                dist_p1 = utils.dist(pt, self.p1)
                dist_p2 = utils.dist(pt, self.p2)
                return dist_p1 > const.THRESH and dist_p2 > const.THRESH

    def dist_to_point(self, pt):
        return utils.dist_from_point_to_line(pt, self.p1, self.p2, segment=True)

    def intersects(self, other: 'Edge'):
        xy = utils.line_line_intersection(self.p1, self.p2, other.p1, other.p2)
        if xy is None:
            return (self.contains_point(other.p1) or self.contains_point(other.p2) or  # lines are parallel
                    other.contains_point(self.p1) or other.contains_point(self.p2))

        if (utils.dist_from_point_to_line(xy, self.p1, self.p2, segment=True) > const.THRESH
                or utils.dist_from_point_to_line(xy, other.p1, other.p2, segment=True) > const.THRESH):
            return False  # intersect must be inside both edges

        if not min(utils.dist(xy, self.p1), utils.dist(xy, self.p2),
                   utils.dist(xy, other.p1), utils.dist(xy, other.p2)) > const.THRESH:
            return False  # intersect must not be at any endpoints

        return True

    def length(self):
        return utils.dist(self.p1, self.p2)

    def __eq__(self, other):
        return (self.p1 == other.p1 and self.p2 == other.p2) \
            or (self.p2 == other.p1 and self.p1 == other.p2)

    def __hash__(self):
        return hash(self.p1) + hash(self.p2)

    def __repr__(self):
        return f"{type(self).__name__}(({self.p1[0]:.2f}, {self.p1[1]:.2f}), ({self.p2[0]:.2f}, {self.p2[1]:.2f}))"

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

    def __repr__(self):
        return f"{type(self).__name__}{tuple(self.edges)}"

class GameplayScene(scenes.Scene):

    def __init__(self, gs: GameState):
        super().__init__()
        self.gs = gs
        self.board_area = [(const.GAME_DIMS[0] - const.BOARD_SIZE) / 2,
                           (const.GAME_DIMS[1] - const.BOARD_SIZE) / 2,
                           const.BOARD_SIZE, const.BOARD_SIZE]

        self.board_style_idx = 0

        self.potential_edge = None  # edge that's being dragged
        self.potential_edge_problems = {}

    def update(self, dt):
        super().update(dt)

        if pygame.K_r in const.KEYS_PRESSED_THIS_FRAME:
            self.board_style_idx += 1
            style = const.BOARD_STYLES[self.board_style_idx % len(const.BOARD_STYLES)]
            print(f"INFO: activating new board style {style}")
            self.gs = GameState(style)
            self.cancel_current_drag()

        if pygame.K_p in const.KEYS_PRESSED_THIS_FRAME:
            const.SHOW_POLYGONS = not const.SHOW_POLYGONS

        if pygame.K_f in const.KEYS_PRESSED_THIS_FRAME:
            goals.PolygonGoalFactory.subdivide_board(self.gs.board, goals.GoalGenParams())

        if pygame.K_c in const.KEYS_PRESSED_THIS_FRAME:
            self.gs.board.clear_user_edges()

        if len(self.gs.goals) < 3:
            new_goal = self.gs.goal_generator.gen_next_goal(max_tries=1)
            if new_goal is not None:
                print(f"INFO: added new goal: {new_goal}")
                self.gs.goals.append(new_goal)

        self.handle_board_mouse_events()

    def cancel_current_drag(self):
        self.potential_edge = None
        self.potential_edge_problems = {}

    def handle_board_mouse_events(self):
        click_dist = self.screen_dist_to_board_dist(const.CLICK_DISTANCE_PX)
        if self.potential_edge is not None:
            if pygame.BUTTON_RIGHT in const.MOUSE_PRESSED_AT_THIS_FRAME:
                # TODO sound effect (drag cancelled)
                self.cancel_current_drag()
            elif pygame.BUTTON_LEFT in const.MOUSE_RELEASED_AT_THIS_FRAME:
                scr_xy = const.MOUSE_RELEASED_AT_THIS_FRAME[pygame.BUTTON_LEFT]
                b_xy = self.screen_xy_to_board_xy(scr_xy)
                dest_node = self.gs.board.get_closest_node(b_xy, max_dist=click_dist)
                if dest_node is None:
                    # TODO sound effect (drag cancelled)
                    self.cancel_current_drag()
                else:
                    new_edge = Edge(self.potential_edge.p1, dest_node)
                    added = self.gs.board.add_user_edge(new_edge)
                    if added:
                        pass  # TODO sound effect (added new edge)
                    else:
                        # TODO sound effect (failed to add edge)
                        if const.AUTO_REMOVE_IF_INTERSECTING:
                            problems = self.gs.board.can_add_user_edge(new_edge, get_problems=True)
                            if len(problems) == 1 and 'intersects' in problems:
                                to_auto_rm = problems['intersects']
                                if all(self.gs.board.can_remove_user_edge(e) for e in to_auto_rm):
                                    print(f"INFO: auto-removing edges {to_auto_rm} to add {new_edge}")
                                    for e in to_auto_rm:
                                        if not self.gs.board.remove_user_edge(e):
                                            raise ValueError(f"Failed to remove edge {e} even though "
                                                             f"can_remove_user_edge said we could?")
                                    if not self.gs.board.add_user_edge(new_edge):
                                        raise ValueError(f"Failed to add edge {e} even though "
                                                         f"we removed everything it intersected with?")
                    self.cancel_current_drag()  # reset drag state

        elif pygame.BUTTON_LEFT in const.MOUSE_PRESSED_AT_THIS_FRAME:
            scr_xy = const.MOUSE_PRESSED_AT_THIS_FRAME[pygame.BUTTON_LEFT]
            b_xy = self.screen_xy_to_board_xy(scr_xy)
            start_node = self.gs.board.get_closest_node(b_xy, max_dist=click_dist)
            if start_node is not None:
                # TODO sound effect (started dragging)
                self.potential_edge = Edge(start_node, b_xy)
        elif pygame.BUTTON_RIGHT in const.MOUSE_PRESSED_AT_THIS_FRAME:
            scr_xy = const.MOUSE_PRESSED_AT_THIS_FRAME[pygame.BUTTON_RIGHT]
            b_xy = self.screen_xy_to_board_xy(scr_xy)
            edge = self.gs.board.get_closest_edge(b_xy, max_dist=click_dist, including_outer=False)
            if edge is not None:
                # TODO sound effect
                self.gs.board.remove_user_edge(edge)

        if self.potential_edge is not None:
            b_xy = self.screen_xy_to_board_xy(const.MOUSE_XY)
            dest_node = self.gs.board.get_closest_node(b_xy, max_dist=click_dist)
            if dest_node is None or dest_node == self.potential_edge.p1:
                self.potential_edge = Edge(self.potential_edge.p1, b_xy)
            else:
                self.potential_edge = Edge(self.potential_edge.p1, dest_node)

            self.potential_edge_problems = self.gs.board.can_add_user_edge(self.potential_edge, get_problems=True)
        else:
            self.potential_edge_problems = {}

    def board_xy_to_screen_xy(self, board_xy):
        if board_xy is None:
            return None
        return (int(self.board_area[0] + board_xy[0] * self.board_area[2]),
                int(self.board_area[1] + board_xy[1] * self.board_area[3]))

    def screen_xy_to_board_xy(self, screen_xy):
        if screen_xy is None:
            return None
        return ((screen_xy[0] - self.board_area[0]) / self.board_area[2],
                (screen_xy[1] - self.board_area[1]) / self.board_area[3])

    def screen_dist_to_board_dist(self, px):
        return px / self.board_area[2]

    def board_dist_to_screen_dist(self, dist):
        return dist * self.board_area[2]

    def _shorten_line(self, p1, p2, px):
        mag = utils.dist(p1, p2)
        center = utils.lerp(p1, p2, 0.5)
        if mag < px:
            return center, center
        v1 = utils.set_length(utils.sub(p1, center), mag / 2 - px / 2)
        v2 = utils.set_length(utils.sub(p2, center), mag / 2 - px / 2)
        return (utils.add(v1, center), utils.add(v2, center))

    def _render_edge(self, surf, edge, color, width=1):
        p1 = self.board_xy_to_screen_xy(edge.p1)
        p2 = self.board_xy_to_screen_xy(edge.p2)
        p1, p2 = self._shorten_line(p1, p2, 16)

        if p1 == p2:
            return

        pygame.draw.line(surf, color, p1, p2, width=width)

    def _render_polygon(self, surf, polygon: geometry.Polygon, color, width=0):
        vertices = [self.board_xy_to_screen_xy(pt) for pt in polygon.vertices]
        pygame.draw.polygon(surf, color, vertices, width=width)

    def render(self, surf: pygame.Surface):
        pygame.draw.rect(surf, colors.BLACK, self.board_area)  # background

        if const.SHOW_POLYGONS:
            for idx, poly in enumerate(self.gs.board.calc_regions(normalize=False)):
                self._render_polygon(surf, poly, colors.TONES[idx % len(colors.TONES)])

        color_overrides = {}  # Edge -> color
        if self.potential_edge is not None:
            for key in self.potential_edge_problems:
                for e_val in self.potential_edge_problems[key]:
                    color_overrides[e_val] = colors.REDS[4]

        for edge in self.gs.board.outer_edges:  # outline
            color = color_overrides[edge] if edge in color_overrides else colors.WHITE  # colors.BOARD_LINE_COLOR
            self._render_edge(surf, edge, color, width=1)

        for edge in self.gs.board.user_edges:
            color = color_overrides[edge] if edge in color_overrides else colors.WHITE
            self._render_edge(surf, edge, color, width=3)

        if self.potential_edge is not None:
            if len(self.potential_edge_problems) is None:
                color = colors.WHITE
            elif 'overlaps' in self.potential_edge_problems:
                color = colors.REDS[3]
            elif 'overlaps_outer' in self.potential_edge_problems:
                color = colors.REDS[3]
            elif 'intersects' in self.potential_edge_problems:
                color = colors.REDS[3]
            else:
                color = colors.LIGHT_GRAY
            self._render_edge(surf, self.potential_edge, color, width=3)

        for peg in self.gs.board.pegs:  # nodes
            pygame.draw.circle(surf, colors.WHITE, self.board_xy_to_screen_xy(peg), 4)

    def get_bg_color(self):
        return colors.DARK_GRAY


if __name__ == "__main__":
    e1 = Edge((0.00, 0.67), (0.33, 0.33))
    e2 = Edge((0.33, 0.67), (0.67, 1.00))
    print(e1.intersects(e2))



