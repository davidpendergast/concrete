import math
import typing

import pygame

import const
import src.utils as utils

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

        if min(utils.dist(xy, self.p1), utils.dist(xy, self.p2),
               utils.dist(xy, other.p1), utils.dist(xy, other.p2)) < const.THRESH:
            return False  # intersect must not be at any endpoints

        return True

    def length(self):
        return utils.dist(self.p1, self.p2)

    def center(self, t=0.5):
        return utils.lerp(self.p1, self.p2, t=t, clamp=True)

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

    def __eq__(self, other):
        return self.edges == other.edges

    def __hash__(self):
        return sum(hash(e) for e in self.edges)

class Polygon:

    def __init__(self, vertices):
        self.vertices = vertices  # immutable pls

        self.edges = EdgeSet()
        for i in range(len(self.vertices)):
            p1 = self.vertices[i]
            p2 = self.vertices[(i + 1) % len(self.vertices)]
            self.edges.add(Edge(p1, p2))

        # used for scale-independent equivalence checking
        self._cached_angles = None
        self._cached_length_ratios = None
        self._cached_nonflat_vertices = None

    @staticmethod
    def _scale_to_new_bounding_box(vertices, new_bb):
        bb = utils.bounding_box(vertices)
        return [utils.map_from_rect_to_rect(pt, bb, new_bb) for pt in vertices]

    def get_nonflat_vertices(self):
        if self._cached_nonflat_vertices is None:
            self.get_angles_and_edge_ratios()
        return self._cached_nonflat_vertices

    def get_angles_and_edge_ratios(self):
        if self._cached_angles is None:
            angles = []
            vertices_used = []
            for i in range(len(self.vertices)):
                p0 = self.vertices[i - 1]
                p1 = self.vertices[i]
                p2 = self.vertices[(i + 1) % len(self.vertices)]
                v1 = pygame.Vector2(utils.sub(p0, p1))
                v2 = pygame.Vector2(utils.sub(p2, p1))
                ang = utils.ccw_angle_to_rads(v1, v2) * 180 / math.pi

                if abs(ang - 180) > 1:  # ignore flat (redundant) angles
                    angles.append(ang)
                    vertices_used.append(p1)
            self._cached_angles = tuple(angles)

            total_perimeter = 0
            edge_lengths = []
            for i in range(len(vertices_used)):
                p0 = vertices_used[i]
                p1 = vertices_used[(i + 1) % len(vertices_used)]
                dist = utils.dist(p0, p1)
                edge_lengths.append(dist)
                total_perimeter += dist
            if total_perimeter > 0:
                self._cached_length_ratios = tuple(l / total_perimeter for l in edge_lengths)
            else:
                self._cached_length_ratios = (0,) * len(edge_lengths)

            self._cached_nonflat_vertices = vertices_used

        return self._cached_angles, self._cached_length_ratios

    def get_angles(self):
        return self.get_angles_and_edge_ratios()[0]

    def is_equivalent_by_angles_and_edge_ratios(self, other, allow_mirrored=True):
        # XXX in theory it might be possible to mismatched angle & edge arrays that happen
        # to match independently... but that seems rare
        my_angles, my_lengths = self.get_angles_and_edge_ratios()
        other_angles, other_lengths = other.get_angles_and_edge_ratios()

        if not utils.circular_lists_equal(my_angles, other_angles, thresh=const.THRESH):
            if not allow_mirrored or not utils.circular_lists_equal(my_angles, list(reversed(other_angles)), thresh=const.THRESH):
                return False

        if not utils.circular_lists_equal(my_lengths, other_lengths, thresh=const.THRESH):
            if not allow_mirrored or not utils.circular_lists_equal(my_lengths, list(reversed(other_lengths)), thresh=const.THRESH):
                return False

        return True

    def scale(self, scale, from_center=True) -> 'Polygon':
        if from_center:
            bb = utils.bounding_box(self.vertices)
            new_bb = [bb[0] + bb[2] / 2 - bb[2] / 2 * scale,
                      bb[1] + bb[3] / 2 - bb[3] / 2 * scale,
                      bb[2] * scale, bb[3] * scale]
            return self.normalize(new_bb=new_bb, preserve_aspect_ratio=False)
        else:
            return Polygon([utils.mult(v, scale) for v in self.vertices])

    def expand_from_center(self, expansion):
        bb = utils.bounding_box(self.vertices)
        new_bb = [bb[0] - expansion, bb[1] - expansion, bb[2] + expansion * 2, bb[3] + expansion * 2]
        return self.normalize(new_bb=new_bb, preserve_aspect_ratio=False)

    def pizza_cut(self, about_pt) -> typing.List['Polygon']:
        res = []
        for v1, v2 in utils.iterate_pairwise(self.get_nonflat_vertices()):
            res.append(Polygon([about_pt, v1, v2]))
        return res

    def avg_pt(self):
        xtot = 0
        ytot = 0
        for pt in self.vertices:
            xtot += pt[0]
            ytot += pt[1]
        return xtot / len(self.vertices), ytot / len(self.vertices)

    def shift(self, dxy):
        return Polygon([utils.add(v, dxy) for v in self.vertices])

    def rotate(self, rads) -> 'Polygon':
        bb = utils.bounding_box(self.vertices)
        cp = pygame.Vector2(bb[0] + bb[2] / 2, bb[1] + bb[3] / 2)
        new_vertices = []
        for v in self.vertices:
            raw = pygame.Vector2(v[0] - cp.x, v[1] - cp.y)
            raw.rotate_ip_rad(rads)
            new_vertices.append((raw.x + cp.x, raw.y + cp.y))
        return Polygon(new_vertices)

    def normalize(self, new_bb=(0, 0, 1, 1), preserve_aspect_ratio=True, center=True) -> 'Polygon':
        if preserve_aspect_ratio:
            bb = utils.bounding_box(self.vertices)
            if bb[2] > bb[3]:
                fixed_bb = [new_bb[0], new_bb[1], new_bb[2], new_bb[3] * bb[3] / bb[2]]
            else:
                fixed_bb = [new_bb[0], new_bb[1], new_bb[2] * bb[2] / bb[3], new_bb[3]]
            if center:
                new_bb = utils.center_rect_in_rect(fixed_bb, new_bb)
            else:
                new_bb = fixed_bb
        return Polygon(Polygon._scale_to_new_bounding_box(self.vertices, new_bb))

    def contains_point(self, p):
        v = pygame.Vector2(1, 0)
        v.rotate_ip(360 / 7)  # invent a ray and **pray** it doesn't hit a fucking corner
        v.scale_to_length(1000)  # literally every stackoverflow enthusiast that posts python
        ray = Edge(p, utils.add(p, v))  # code to check polygon point containment fucks this up
        return sum((1 if ray.intersects(e) else 0) for e in self.edges) % 2 == 1

    def __repr__(self):
        return f"{type(self).__name__}(n={len(self.vertices)}, vertices={self.vertices}, angles={self.get_angles()})"

