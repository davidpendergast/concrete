import math
import typing
import random
import time

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
import src.spites as sprites
import src.levels as levels
import src.sounds as sounds

INNER_EXPANSION = 6
OUTER_EXPANSION = 6


class GameState:

    def __init__(self, level_idx=0):
        self.level_idx = level_idx
        self.level = levels.LEVELS[level_idx % len(levels.LEVELS)]
        self.board = Board.new_board(*self.level.style)

        cur_regions = self.board.calc_regions()
        self.board_bg_polygon = cur_regions[0].polygon  # only used for rendering
        self.current_regions = cur_regions

        params = goals.GoalGenParams()
        params.banned_polys.append(self.board_bg_polygon)
        params.banned_polys.extend(self.level.banned_polys)
        params.min_n_vertices = self.level.min_vertices
        params.max_n_vertices = self.level.max_vertices

        self.goal_generator = goals.GoalGenerator(self.board, params)
        self.goals: typing.List[goals.PolygonGoal] = []  # active_goals
        self.satisfied_goals = []
        self.finishing_goals_still_moving = []

        self.overflow_zone = 0.05
        self.max_temperature = 1.0

        # these items carry over between levels
        self.slabs_completed_count = 0
        self.slabs_required_for_next_level = self.level.slab_req
        self.temperature = 0.666
        self.score = 0

    def ready_for_next_level(self):
        return self.slabs_completed_count >= self.slabs_required_for_next_level

    def next_level(self) -> 'GameState':
        new_idx = self.level_idx + 1
        if new_idx >= len(levels.LEVELS):
            return None  # finished !
        else:
            gs = GameState(level_idx=new_idx)
            gs.temperature = self.temperature
            gs.add_temperature(0.25)  # lil boost
            gs.score = self.score
            gs.slabs_completed_count += self.slabs_completed_count
            gs.slabs_required_for_next_level += self.slabs_required_for_next_level
            return gs

    def get_temperature(self, normalize=True):
        if normalize:
            return min(1.0, max(0.0, self.temperature / self.max_temperature))
        return self.temperature

    def is_game_over(self):
        return self.get_temperature() <= 0

    def update_regions(self, dt):
        old_regions = set(self.current_regions)  # recalc in case updates caused deletions
        new_regions = set(self.board.calc_regions())
        to_add = [r for r in new_regions if r not in old_regions]
        to_keep = [r for r in old_regions if r in new_regions]
        self.current_regions = to_keep + to_add

        rate = 1 + self.level.max_temp_cure_boost * self.get_temperature(normalize=True)
        for r in self.current_regions:
            r.update(dt, rate=rate)

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
        self.slabs_completed_count += 1
        print(f"INFO: completed goal {goal} (count={self.slabs_completed_count})")

        board_bb = utils.bounding_box(self.board_bg_polygon.vertices)
        bb = utils.bounding_box(goal.actual.polygon.vertices)
        pcnt_of_board = bb[2] * bb[3] / (board_bb[2] * board_bb[3])

        self.score += int(100 * pcnt_of_board) * len(goal.actual.polygon.get_angles()) * 10
        self.add_temperature(self.level.boost_rate * self.max_temperature * pcnt_of_board)

    def update_goals(self, dt, region_to_animator_mapping):
        # update active goals
        keep_goals = []
        for goal in self.goals:
            keep = True
            if not goal.is_satisfied():
                for region in self.current_regions:
                    if not region.is_satisfying_goal() and goal.is_satisfied_by(region):
                        sounds.play_sound("pour")
                        goal.set_satisfied(region)
                        region.set_satisfying_goal(goal, cure_time=self.level.base_cure_time)
                        keep = False
                        self.satisfied_goals.append(goal)
                        self.satisfied_goal(goal)
                        break
            if keep:
                keep_goals.append(goal)

        self.goals = keep_goals

        # gen new goals
        if len(self.goals) < const.N_GOALS:
            temp_banned = [s.polygon for s in self.goals if s is not None] + [s.polygon for s in self.satisfied_goals]
            for _ in range(const.N_GOALS - len(self.goals)):
                new_goal = self.goal_generator.gen_next_goal(temp_banned_shapes=temp_banned, max_tries=1)
                if new_goal is not None:
                    self.goals.append(new_goal)

        # rm regions of fully completed goals
        keep = []
        for i in range(len(self.satisfied_goals)):
            goal = self.satisfied_goals[i]
            if goal.is_satisfied_and_finished():
                # remove the goal and its board region
                self.remove_region(goal.actual)

                if region_to_animator_mapping is not None and goal.actual in region_to_animator_mapping:
                    sounds.play_sound("slab_slide")
                    animator_bb = region_to_animator_mapping[goal.actual]
                    img = animator_bb[0].get_image()
                    bb = animator_bb[1]
                    self.finishing_goals_still_moving.append(((0, 0), 512, 0, 30 * (random.random() - 0.5), goal, img, bb))
            else:
                keep.append(goal)
        self.satisfied_goals = keep

        keep = []
        for (xy, yvel, rot, rot_rate, goal, img, bb) in self.finishing_goals_still_moving:
            yvel += 128 * dt / 1000  # px per sec of acceleration
            xy = (xy[0], xy[1] + yvel * dt / 1000)
            if xy[1] > const.GAME_DIMS[1]:
                continue
            else:
                rot += rot_rate * dt / 1000
            keep.append((xy, yvel, rot, rot_rate, goal, img, bb))
        self.finishing_goals_still_moving = keep

    def update_temperature(self, dt):
        decay = self.level.decay_rate * self.max_temperature * dt / 1000
        self.temperature -= decay

    def add_temperature(self, val):
        self.temperature = min(self.temperature + val,
                               self.max_temperature + self.max_temperature * self.overflow_zone)

    def update(self, dt, region_to_animator_mapping):
        self.update_regions(dt)
        self.update_goals(dt, region_to_animator_mapping)
        self.update_temperature(dt)


class BoardRegion:

    def __init__(self, polygon, edges):
        self.polygon = polygon  # board space
        self.edges = edges

        self.satisfying_goal = None
        self.goal_time_remaining = 5

    def set_satisfying_goal(self, goal, cure_time=5):
        self.satisfying_goal = goal
        self.goal_time_remaining = cure_time

    def is_satisfying_goal(self):
        return self.satisfying_goal is not None

    def is_done(self):
        return self.goal_time_remaining <= 0

    def blocks_edge_removal(self):
        return self.is_satisfying_goal() and not self.is_done()

    def update(self, dt, rate=1):
        if self.is_satisfying_goal():
            self.goal_time_remaining -= (dt / 1000) * rate

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


def fresh_gameplay_scene() -> 'GameplayScene':
    return GameplayScene(GameState())

class GameplayScene(scenes.Scene):

    def __init__(self, gs: GameState):
        super().__init__()
        self.gs = gs
        self.goals_area = [0, 0, const.GAME_DIMS[0] / 5, const.GAME_DIMS[1]]
        self.goal_px_size = self.goals_area[2] - 2

        w = const.GAME_DIMS[0] / 5
        self.thermo_area = [const.GAME_DIMS[0] - w, 0, w, const.GAME_DIMS[1]]
        self.thermo_width = sprites.Sheet.THERMO_BG_UPPER.get_width()
        self.tally_width = self.thermo_area[2] - self.thermo_width

        self.remaining_area = [self.goals_area[0] + self.goals_area[2], 0,
                               const.GAME_DIMS[0] - self.goals_area[2] - self.thermo_area[2],
                               const.GAME_DIMS[1]]
        board_rect = [0, 0, const.BOARD_SIZE, const.BOARD_SIZE]
        self.board_area = utils.center_rect_in_rect(board_rect, self.remaining_area)

        scoring_rect = [0, 0, *sprites.Sheet.SCORE_BG.get_size()]
        scoring_rect = utils.center_rect_in_rect(scoring_rect, self.remaining_area)
        scoring_rect[1] = ((self.remaining_area[1] + self.board_area[1] - INNER_EXPANSION - OUTER_EXPANSION) - scoring_rect[3]) // 2
        self.scoring_area = scoring_rect

        self.board_style_idx = 0

        self.potential_edge = None  # edge that's being dragged
        self.potential_edge_problems = {}

        self.rot_time = 0
        self.region_to_animator_mapping = {}

    def update(self, dt, fake=False):
        super().update(dt)

        if const.IS_DEV and pygame.K_r in const.KEYS_PRESSED_THIS_FRAME:
            self.gs.slabs_completed_count += self.gs.level.slab_req

        if const.IS_DEV and pygame.K_p in const.KEYS_PRESSED_THIS_FRAME:
            const.SHOW_POLYGONS = not const.SHOW_POLYGONS

        if const.IS_DEV and pygame.K_f in const.KEYS_PRESSED_THIS_FRAME:
            goals.PolygonGoalFactory.subdivide_board(self.gs.board, goals.GoalGenParams())

        if not fake:
            self.handle_board_mouse_events()
            self.gs.update(dt, self.region_to_animator_mapping)  # i fucked up here

            if self.gs.is_game_over() or pygame.K_ESCAPE in const.KEYS_PRESSED_THIS_FRAME:
                import src.textscenes as textscenes
                sounds.play_sound("death")
                self.manager.jump_to_scene(textscenes.GameOverScene(underlay=self))
            elif self.gs.ready_for_next_level():
                import src.textscenes as textscenes
                next_gs = self.gs.next_level()
                sounds.play_sound("promote", volume=0.5)
                if next_gs is None:
                    self.manager.jump_to_scene(textscenes.YouWinScene(underlay=self))
                else:
                    self.manager.jump_to_scene(textscenes.NextLevelScene(self, GameplayScene(next_gs)))

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
                filler = cementfill.Filler(screen_poly, bb, total_time=n.goal_time_remaining, fill_time_pcnt=0.5)
                self.region_to_animator_mapping[n] = (filler, bb)

        for (k, v) in self.region_to_animator_mapping.items():
            v[0].update(dt)

        goal_move_speed = 40  # px per sec
        next_y = 0
        spawn_y = self.goals_area[1] + self.goals_area[3]  # spawn offscreen
        buffer = 2
        for goal in self.gs.goals:
            if 'xy' not in goal.data:
                goal.data['xy'] = (0, spawn_y)
                spawn_y += self.goal_px_size + buffer
            else:
                x, y = goal.data['xy']
                if y > next_y:  # room to move
                    move_y = dt / 1000 * goal_move_speed
                    goal.data['xy'] = (x, max(next_y, y - move_y))
                next_y = goal.data['xy'][1] + self.goal_px_size + buffer

        fling_speed = 100
        for goal in self.gs.satisfied_goals:
            if 'xy' in goal.data:
                x, y = goal.data['xy']
                goal.data['xy'] = (x - fling_speed * dt / 1000, y)

    def cancel_current_drag(self):
        self.potential_edge = None
        self.potential_edge_problems = {}

    def can_remove_edge(self, edge):
        return self.gs.can_remove_edge(edge) and self.gs.board.can_remove_user_edge(edge)

    def handle_board_mouse_events(self):
        click_dist = self.screen_dist_to_board_dist(const.CLICK_DISTANCE_PX)
        if self.potential_edge is not None:
            if pygame.BUTTON_RIGHT in const.MOUSE_PRESSED_AT_THIS_FRAME:
                sounds.play_sound('back')  # drag canceled
                self.cancel_current_drag()
            elif pygame.BUTTON_LEFT in const.MOUSE_RELEASED_AT_THIS_FRAME:
                scr_xy = const.MOUSE_RELEASED_AT_THIS_FRAME[pygame.BUTTON_LEFT]
                b_xy = self.screen_xy_to_board_xy(scr_xy)
                dest_node = self.gs.board.get_closest_node(b_xy, max_dist=click_dist)
                if dest_node is None or dest_node == self.potential_edge.p1:
                    sounds.play_sound('back')  # drag cancelled
                    self.cancel_current_drag()
                else:
                    new_edge = Edge(self.potential_edge.p1, dest_node)
                    if self.gs.can_add_edge(new_edge):
                        added = self.gs.board.add_user_edge(new_edge)
                        if added:
                            sounds.play_sound('draw_line')  # added new edge
                        else:
                            added_anyways = False
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
                                        added_anyways = True
                                        sounds.play_sound("delete_line", volume=0.5)
                            if not added_anyways:
                                sounds.play_sound('back')  # failed to add edge
                    else:
                        sounds.play_sound('back')  # failed to add edge

                    self.cancel_current_drag()  # reset drag state

        elif pygame.BUTTON_LEFT in const.MOUSE_PRESSED_AT_THIS_FRAME:
            scr_xy = const.MOUSE_PRESSED_AT_THIS_FRAME[pygame.BUTTON_LEFT]
            b_xy = self.screen_xy_to_board_xy(scr_xy)
            start_node = self.gs.board.get_closest_node(b_xy, max_dist=click_dist)
            if start_node is not None:
                sounds.play_sound("start_line")  # started dragging
                self.potential_edge = Edge(start_node, b_xy)
        elif pygame.BUTTON_RIGHT in const.MOUSE_PRESSED_AT_THIS_FRAME:
            scr_xy = const.MOUSE_PRESSED_AT_THIS_FRAME[pygame.BUTTON_RIGHT]
            b_xy = self.screen_xy_to_board_xy(scr_xy)
            edge = self.gs.board.get_closest_edge(b_xy, max_dist=click_dist, including_outer=False)
            if edge is not None and self.can_remove_edge(edge):
                sounds.play_sound("delete_line", volume=0.5)  # deleted line
                self.gs.board.remove_user_edge(edge)

        if self.potential_edge is not None and const.MOUSE_XY is not None:
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

    def get_board_bb_onscreen(self):
        pts = [self.board_xy_to_screen_xy(v) for v in self.gs.board_bg_polygon.vertices]
        return utils.bounding_box(pts)

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

    def render(self, surf: pygame.Surface, skip_board=False):
        self.render_board(surf, skip_board=skip_board)
        self.render_goals(surf)
        self.render_temperature(surf)
        self.render_score(surf)
        self.render_moving_regions(surf)

    def render_goals(self, surf: pygame.Surface):
        pygame.draw.rect(surf, colors.BLACK, self.goals_area)
        cur_time = time.time()

        imgs = []
        for goal in self.gs.goals:
            rot = cur_time - goal.data['rand'] * 100
            if 'xy' in goal.data:
                imgs.append((goal.data['xy'], goal.get_image(self.goal_px_size, colors.BLUE_DARK, colors.BLUE_LIGHT,
                                                             rot=rot, width=2, inset=2)))

        for goal in self.gs.satisfied_goals:
            if 'xy' in goal.data:
                x, y = goal.data['xy']
                rot = cur_time - goal.data['rand'] * 100
                fg_color = colors.BLUE_LIGHT if not goal.is_satisfied() else colors.WHITE
                if x > -2 * self.goal_px_size:
                    imgs.append((goal.data['xy'],
                                 goal.get_image(self.goal_px_size, colors.BLUE_DARK, fg_color, rot=rot, width=2,
                                                inset=2)))

        for (xy, img) in imgs:
            surf.blit(img, (self.goals_area[0] + 1 + xy[0],
                            self.goals_area[1] + xy[1]))

    def render_temperature(self, surf: pygame.Surface):
        w, h = sprites.Sheet.THERMO_BG_UPPER.get_size()
        surf.blit(sprites.Sheet.THERMO_BG_UPPER, self.thermo_area)
        y_min, y_max = sprites.Sheet.THERMO_Y_RANGE
        thermo_y = y_min + (1 - self.gs.get_temperature()) * (y_max - y_min)
        surf.blit(sprites.Sheet.THERMO, (self.thermo_area[0] + 5, self.thermo_area[1] + thermo_y))
        surf.blit(sprites.Sheet.THERMO_BG_LOWER, (self.thermo_area[0], self.thermo_area[1] + h))

        extra_rect = [self.thermo_area[0] + w + 1,
                      self.thermo_area[1] + 1,
                      self.thermo_area[2] - w - 2,
                      self.thermo_area[3] - 2]
        pygame.draw.rect(surf, colors.BLUE_DARK, extra_rect, width=0)
        pygame.draw.rect(surf, colors.BLUE_MID, extra_rect, width=1)

        numeral_imgs = sprites.Sheet.get_numerals(self.gs.slabs_completed_count)
        for i in range(len(numeral_imgs)):
            img = numeral_imgs[i]
            x = (i % 3) * img.get_size()[0] + extra_rect[0] + 2
            y = (i // 3) * img.get_size()[1] + extra_rect[1] + 1
            surf.blit(img, (x, y))

        goal_line_y = (self.gs.slabs_required_for_next_level // 15) * sprites.Sheet.NUMERAL_SIZE[1]
        surf.blit(sprites.Sheet.GOAL_LINE, (extra_rect[0] + 2, extra_rect[1] + goal_line_y))

    def render_score(self, surf: pygame.Surface):
        surf.blit(sprites.Sheet.SCORE_BG, self.scoring_area)
        xy_offs = (3, 2)
        score_text = str(self.gs.score)
        rendered_text = sprites.Sheet.FONT.render(score_text, True, colors.WHITE)
        surf.blit(rendered_text, utils.add(self.scoring_area[:2], xy_offs))

    def render_board(self, surf: pygame.Surface, skip_board=False):
        pygame.draw.rect(surf, colors.BLUE_MID, utils.rect_expand(self.remaining_area, all_sides=-1), width=0)

        decoration_rect = [0, 0, *sprites.Sheet.DECORATION_BANNER.get_size()]
        decoration_rect = utils.center_rect_in_rect(decoration_rect, self.remaining_area)
        decoration_rect[1] = self.remaining_area[1] + self.remaining_area[3] - decoration_rect[3] - 3
        surf.blit(sprites.Sheet.DECORATION_BANNER, decoration_rect)

        # background
        true_bg_poly = geometry.Polygon([self.board_xy_to_screen_xy(v) for v in self.gs.board_bg_polygon.vertices])
        inner_bg_poly = true_bg_poly.expand_from_center(INNER_EXPANSION)
        outer_bg_poly = inner_bg_poly.expand_from_center(OUTER_EXPANSION)
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

        if const.IS_DEV and const.SHOW_POLYGONS:
            for idx, poly in enumerate(self.gs.board.calc_polygons()):
                self._render_polygon(surf, poly, colors.TONES[idx % len(colors.TONES)])

        if not skip_board:
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

    def render_moving_regions(self, surf):
        for (xy, yvel, rot, rot_rate, goal, img, bb) in self.gs.finishing_goals_still_moving:
            surf.blit(img, (bb[0], bb[1] + xy[1]))

    def get_bg_color(self):
        return colors.DARK_GRAY


if __name__ == "__main__":
    e1 = Edge((0.00, 0.67), (0.33, 0.33))
    e2 = Edge((0.33, 0.67), (0.67, 1.00))
    print(e1.intersects(e2))



