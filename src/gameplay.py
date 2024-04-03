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
from src.geometry import Edge, EdgeSet
import src.goals as goals
import src.cementfill as cementfill

class GameState:

    def __init__(self, style=const.BOARD_STYLES[0]):
        self.board = Board.new_board(*style)

        cur_regions = self.board.calc_regions()
        self.board_bg_polygon = cur_regions[0].polygon  # only used for rendering
        self.current_regions = cur_regions

        params = goals.GoalGenParams()
        params.banned_polys.append(self.board_bg_polygon)
        params.min_n_vertices = 4

        self.goal_generator = goals.GoalGenerator(self.board, params)
        self.goals: typing.List[goals.PolygonGoal] = [None] * const.N_GOALS  # active_goals
        self.satisfied_goals = []
        self.completed_count = 0

    def update_regions(self, dt):
        old_regions = set(self.current_regions)  # recalc in case updates caused deletions
        new_regions = set(self.board.calc_regions())
        to_add = [r for r in new_regions if r not in old_regions]
        to_keep = [r for r in old_regions if r in new_regions]
        self.current_regions = to_keep + to_add

        for r in self.current_regions:
            r.update(dt)

    def remove_region(self, region):
        self.current_regions.remove(region)
        used_by_other_active_regions = EdgeSet()
        for r in self.current_regions:
            if r.is_satisfying_goal():
                used_by_other_active_regions.add_all(r.edges)
        for edge in region.edges:
            if edge not in used_by_other_active_regions and self.board.can_remove_user_edge(edge):
                self.board.remove_user_edge(edge)

    def can_add_edge(self, edge, try_to_split=True):
        split_edges = self.board.try_to_split(edge) if try_to_split else [edge]
        concrete_regions = [r for r in self.current_regions if r.is_satisfying_goal()]
        for r in concrete_regions:
            for edge in split_edges:
                if r.polygon.contains_point(edge.center()):
                    return False
                for r_edge in r.edges:
                    if edge.intersects(r_edge):
                        return False
        return True

    def can_remove_edge(self, edge):
        concrete_regions = [r for r in self.current_regions if r.is_satisfying_goal()]
        for r in concrete_regions:
            if edge in r.edges:
                return False
        return True

    def satisfied_goal(self, goal):
        self.completed_count += 1
        print(f"INFO: completed goal {goal} (count={self.completed_count})")

    def update_goals(self, dt):
        # update active goals
        for i in range(len(self.goals)):
            goal = self.goals[i]
            if goal is not None and not goal.is_satisfied():
                for region in self.current_regions:
                    if not region.is_satisfying_goal() and goal.is_satisfied_by(region):
                        goal.set_satisfied(region)
                        region.set_satisfying_goal(goal)
                        self.goals[i] = None  # make way for new active goal
                        self.satisfied_goals.append(goal)
                        self.satisfied_goal(goal)
                        break
            if self.goals[i] is None:
                temp_banned = [s.polygon for s in self.goals if s is not None] + [s.polygon for s in self.satisfied_goals]
                self.goals[i] = self.goal_generator.gen_next_goal(temp_banned_shapes=temp_banned, max_tries=1)

        # rm regions of fully completed goals
        keep = []
        for i in range(len(self.satisfied_goals)):
            goal = self.satisfied_goals[i]
            if goal.is_satisfied_and_finished():
                # remove the goal and its board region
                self.remove_region(goal.actual)
            else:
                keep.append(goal)
        self.satisfied_goals = keep

    def update(self, dt):
        self.update_regions(dt)
        self.update_goals(dt)


class BoardRegion:

    def __init__(self, polygon, edges):
        self.polygon = polygon  # board space
        self.edges = edges

        self.satisfying_goal = None
        self.goal_time_remaining = 5

    def set_satisfying_goal(self, goal):
        self.satisfying_goal = goal

    def is_satisfying_goal(self):
        return self.satisfying_goal is not None

    def is_done(self):
        return self.goal_time_remaining <= 0

    def blocks_edge_removal(self):
        return self.is_satisfying_goal() and not self.is_done()

    def update(self, dt):
        if self.is_satisfying_goal():
            self.goal_time_remaining -= dt / 1000

    def __hash__(self):
        return hash(self.edges)

    def __eq__(self, other):
        return self.edges == other.edges


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

    def calc_polygons(self) -> typing.List[geometry.Polygon]:
        return [region.polygon for region in self.calc_regions()]

    def calc_regions(self) -> typing.List[BoardRegion]:

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

        def recover_edges(pth) -> 'EdgeSet':
            res = EdgeSet()
            for i in range(len(pth)):
                n1 = pth[i]
                n2 = pth[(i + 1) % len(pth)]
                res.add(Edge(n1, n2))
            return res

        regions = []
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
                        edges = recover_edges(path)
                        remove_backtracking(path)
                        if len(path) > 2:
                            regions.append(BoardRegion(geometry.Polygon(path), edges))
                    else:
                        pass  # inverted poly, discard
                else:
                    path.append(next_node)

        return regions


class GameplayScene(scenes.Scene):

    def __init__(self, gs: GameState):
        super().__init__()
        self.gs = gs
        self.goals_area = [0, 0, const.GAME_DIMS[0] / 5, const.GAME_DIMS[1]]

        w = const.GAME_DIMS[0] / 5
        self.scoring_area = [const.GAME_DIMS[0] - w, 0, w, const.GAME_DIMS[1]]

        self.remaining_area = [self.goals_area[0] + self.goals_area[2], 0,
                               const.GAME_DIMS[0] - self.goals_area[2] - self.scoring_area[2],
                               const.GAME_DIMS[1]]
        board_rect = [0, 0, const.BOARD_SIZE, const.BOARD_SIZE]
        self.board_area = utils.center_rect_in_rect(board_rect, self.remaining_area)

        self.board_style_idx = 0

        self.potential_edge = None  # edge that's being dragged
        self.potential_edge_problems = {}

        self.rot_time = 0
        self.region_to_animator_mapping = {}

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

        if pygame.K_SPACE not in const.KEYS_HELD_THIS_FRAME:
            self.rot_time += dt  # space to slow the diabolical rotation
        else:
            self.rot_time += dt / 15

        self.handle_board_mouse_events()

        self.gs.update(dt)

        self._update_animations(dt)

    def _update_animations(self, dt):
        old_regions = set(self.region_to_animator_mapping.keys())
        new_regions = set(self.gs.current_regions)
        for r in old_regions:
            if r not in new_regions:
                del self.region_to_animator_mapping[r]
        for n in new_regions:
            if n.is_satisfying_goal() and n not in self.region_to_animator_mapping:
                screen_poly = geometry.Polygon([self.board_xy_to_screen_xy(v) for v in n.polygon.vertices])
                bb = utils.bounding_box(screen_poly.vertices)
                filler = cementfill.Filler(screen_poly, bb, total_time=n.goal_time_remaining, fill_time_pcnt=0.333)
                self.region_to_animator_mapping[n] = (filler, bb)

        for (k, v) in self.region_to_animator_mapping.items():
            v[0].update(dt)

    def cancel_current_drag(self):
        self.potential_edge = None
        self.potential_edge_problems = {}

    def can_remove_edge(self, edge):
        return self.gs.can_remove_edge(edge) and self.gs.board.can_remove_user_edge(edge)

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
                if dest_node is None or dest_node == self.potential_edge.p1:
                    # TODO sound effect (drag cancelled)
                    self.cancel_current_drag()
                else:
                    new_edge = Edge(self.potential_edge.p1, dest_node)
                    if self.gs.can_add_edge(new_edge):
                        added = self.gs.board.add_user_edge(new_edge)
                        if added:
                            pass  # TODO sound effect (added new edge)
                        else:
                            # TODO sound effect (failed to add edge)
                            if const.AUTO_REMOVE_IF_INTERSECTING:
                                problems = self.gs.board.can_add_user_edge(new_edge, get_problems=True)
                                if len(problems) == 1 and 'intersects' in problems:
                                    to_auto_rm = problems['intersects']
                                    if all(self.can_remove_edge(e) for e in to_auto_rm):
                                        print(f"INFO: auto-removing edges {to_auto_rm} to add {new_edge}")
                                        for e in to_auto_rm:
                                            if not self.gs.board.remove_user_edge(e):
                                                raise ValueError(f"Failed to remove edge {e} even though "
                                                                 f"can_remove_edge said we could?")
                                        if not self.gs.board.add_user_edge(new_edge):
                                            raise ValueError(f"Failed to add edge {e} even though "
                                                             f"we removed everything it intersected with?")
                    else:
                        pass  # TODO sound effect (failed to add edge)

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
            if edge is not None and self.can_remove_edge(edge):
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
        self.render_board(surf)
        self.render_goals(surf)
        self.render_temperature(surf)

    def render_goals(self, surf: pygame.Surface):
        # pygame.draw.rect(surf, colors.BOARD_LINE_COLOR, self.goals_area, width=1)
        px_size = self.goals_area[2] - 2

        rot = self.rot_time / 1000

        imgs = []
        for goal in self.gs.goals:
            if goal is not None:
                fg_color = colors.BLUE_LIGHT if not goal.is_satisfied() else colors.WHITE
                imgs.append(goal.get_image(px_size, colors.BLUE_DARK, fg_color, rot=rot, width=2, inset=2))
            else:
                imgs.append(None)

        for idx, img in enumerate(imgs):
            if img is not None:
                surf.blit(img, (self.goals_area[0] + 1, self.goals_area[1] + (px_size + 2) * idx))

    def render_temperature(self, surf: pygame.Surface):
        pygame.draw.rect(surf, colors.BOARD_LINE_COLOR, self.scoring_area, width=1)

    def render_board(self, surf: pygame.Surface):
        pygame.draw.rect(surf, colors.BLUE_MID, utils.rect_expand(self.remaining_area, all_sides=-1), width=0)

        # background
        true_bg_poly = geometry.Polygon([self.board_xy_to_screen_xy(v) for v in self.gs.board_bg_polygon.vertices])
        inner_bg_poly = true_bg_poly.expand_from_center(6)
        outer_bg_poly = inner_bg_poly.expand_from_center(6)
        pygame.draw.polygon(surf, colors.BLUE_DARK, outer_bg_poly.vertices)

        center = outer_bg_poly.avg_pt()
        for tri in outer_bg_poly.pizza_cut(center):
            tri_center = tri.avg_pt()
            dx = tri_center[0] - center[0]
            dy = tri_center[1] - center[1]
            if abs(dx) > abs(dy):
                tri_color = colors.BLUE_MID_LIGHT
            else:
                tri_color = colors.BLUE_LIGHT if dy > 0 else colors.BLUE_DARK
            pygame.draw.polygon(surf, tri_color, tri.vertices)

        pygame.draw.polygon(surf, colors.BLACK, inner_bg_poly.vertices)

        if const.SHOW_POLYGONS:
            for idx, poly in enumerate(self.gs.board.calc_polygons()):
                self._render_polygon(surf, poly, colors.TONES[idx % len(colors.TONES)])

        color_overrides = {}  # Edge -> color
        if self.potential_edge is not None:
            for key in self.potential_edge_problems:
                for e_val in self.potential_edge_problems[key]:
                    color_overrides[e_val] = colors.REDS[4]

        for (r, (animator, bb)) in self.region_to_animator_mapping.items():
            img = animator.get_image()
            surf.blit(img, bb)

        for edge in self.gs.board.outer_edges:  # outline
            color = color_overrides[edge] if edge in color_overrides else colors.WHITE
            self._render_edge(surf, edge, color, width=1)

        for edge in self.gs.board.user_edges:
            color = color_overrides[edge] if edge in color_overrides else colors.WHITE
            self._render_edge(surf, edge, color, width=2)

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
            pygame.draw.circle(surf, colors.BLACK, self.board_xy_to_screen_xy(peg), 5)
            pygame.draw.circle(surf, colors.WHITE, self.board_xy_to_screen_xy(peg), 3)

    def get_bg_color(self):
        return colors.DARK_GRAY


if __name__ == "__main__":
    e1 = Edge((0.00, 0.67), (0.33, 0.33))
    e2 = Edge((0.33, 0.67), (0.67, 1.00))
    print(e1.intersects(e2))



