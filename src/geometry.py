import pygame

import const
import src.utils as utils

class Polygon:

    def __init__(self, vertices, normalize=True):
        if normalize:
            bb = utils.bounding_box(vertices)
            if bb[2] > bb[3]:
                new_bb = [0, 0, 1, bb[3] / bb[2]]
            else:
                new_bb = [0, 0, bb[2] / bb[3], 1]
            vertices = [utils.map_from_rect_to_rect(pt, bb, new_bb) for pt in vertices]

        self.vertices = vertices
        self._cached_angles = None

    def get_angles(self):
        if self._cached_angles is None:
            res = []
            for i in range(self.vertices):
                p0 = self.vertices[i - 1]
                p1 = self.vertices[i]
                p2 = self.vertices[(i + 1) % len(self.vertices)]
                v1 = pygame.Vector2(utils.sub(p0, p1))
                v2 = pygame.Vector2(utils.sub(p2, p1))
                res.append(v1.angle_to(v2))
            self._cached_angles = tuple(res)
        return self._cached_angles

    def is_equivalent_by_angles(self, other):
        my_angles = self.get_angles()
        other_angles = other.get_angles()

        if len(my_angles) != len(other_angles):
            return False

        if list(sorted(my_angles)) != list(sorted(other_angles)):
            return False

        for offs in range(1, len(my_angles)):
            my_offset_angles = my_angles[:offs] + my_angles[offs:]
            if utils.eq(my_offset_angles, other_angles, thresh=const.THRESH):
                return True

        return False

