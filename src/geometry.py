import math

import pygame

import const
import src.utils as utils

class Polygon:

    def __init__(self, vertices):
        self.vertices = vertices  # immutable pls

        # used for scale-independent equivalence checking
        self._cached_angles = None
        self._cached_length_ratios = None

    @staticmethod
    def _scale_to_new_bounding_box(vertices, new_bb):
        bb = utils.bounding_box(vertices)
        return [utils.map_from_rect_to_rect(pt, bb, new_bb) for pt in vertices]

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

                if abs(ang - 180) > const.THRESH:  # ignore flat (redundant) angles
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

        return self._cached_angles, self._cached_length_ratios

    def get_angles(self):
        return self.get_angles_and_edge_ratios()[0]

    def is_equivalent_by_angles_and_edge_ratios(self, other):
        # XXX in theory it might be possible to mismatched angle & edge arrays that happen
        # to match independently... but that seems rare
        my_angles, my_lengths = self.get_angles_and_edge_ratios()
        other_angles, other_lengths = other.get_angles_and_edge_ratios()

        if not utils.circular_lists_equal(my_angles, other_angles, thresh=const.THRESH):
            return False

        if not utils.circular_lists_equal(my_lengths, other_lengths, thresh=const.THRESH):
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

    def __repr__(self):
        return f"{type(self).__name__}(n={len(self.vertices)}, vertices={self.vertices}, angles={self.get_angles()})"

