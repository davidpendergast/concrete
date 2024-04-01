import random

import pygame

import src.geometry as geometry
import src.colors as colors
import collections
import src.utils as utils

class Filler:

    def __init__(
            self,
            polygon: geometry.Polygon,
            rect,
            px_per_sec=200,
            palette=colors.TONES,
            dry_time_secs=2.5,
            max_brightness=0.3,
            final_brightness=0.4,
            n_starts=1):

        self.paint_surf = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        # pygame.draw.polygon(self.paint_surf, "black", polygon.vertices, width=1)  # test

        self.mask_surf = pygame.Surface((rect[2], rect[3]))
        self.mask_surf.fill("white")
        pygame.draw.polygon(self.mask_surf, "black", polygon.shift((-rect[0], -rect[1])).vertices, width=0)

        self.size = self.mask_surf.get_size()

        self.palette = palette
        self.max_brightness = max_brightness
        self.final_brightness = final_brightness

        self.remaining_cells = set()
        for x in range(0, self.size[0]):
            for y in range(0, self.size[1]):
                px = self.mask_surf.get_at((x, y))
                if px == (0, 0, 0):
                    self.remaining_cells.add((x, y))

        self.edge_cells = collections.deque()
        starters = random.sample(list(self.remaining_cells), k=min(n_starts, len(self.remaining_cells)))
        for xy in starters:
            self.edge_cells.appendleft(xy)
            self._fill_cell(xy)
            self.remaining_cells.remove(xy)

        self.has_filled = 0
        self.elapsed_time = 0
        self.px_per_sec = px_per_sec

        self.dry_time = dry_time_secs
        self.dry_time_remaining = self.dry_time
        self.drying_image = None

        self.kernel = self._get_kernel(3)

    def _get_kernel(self, radius):
        res = []
        for x in range(-radius, radius + 1):
            for y in range(-radius, radius + 1):
                if 0 < utils.mag((x, y)) <= radius:
                    res.append((x, y))
        return res

    def update(self, dt):
        self.elapsed_time += dt / 1000

        if not self.is_finished_pouring():
            random.shuffle(self.edge_cells)
            need_to_fill = int(self.px_per_sec * self.elapsed_time) - self.has_filled
            while need_to_fill > 0 and len(self.edge_cells) > 0:
                next_xy = self.edge_cells.pop()
                my_color = self.paint_surf.get_at(next_xy)  # should already be colored
                for k in self.kernel:
                    neighbor = (next_xy[0] + k[0], next_xy[1] + k[1])
                    if neighbor in self.remaining_cells:
                        self._fill_cell(neighbor, my_color)
                        self.edge_cells.appendleft(neighbor)
                        need_to_fill -= 1
                        self.remaining_cells.remove(neighbor)

        else:
            if self.drying_image is None:
                self.drying_image = pygame.Surface(self.paint_surf.get_size(), pygame.SRCALPHA)

            prog = min(1.0, 1 - self.dry_time_remaining / self.dry_time)
            self.drying_image.fill((0, 0, 0, 0))
            self.drying_image.blit(self.paint_surf, (0, 0))
            overlay = pygame.Surface(self.paint_surf.get_size(), pygame.SRCALPHA)
            clr = pygame.Color(colors.WHITE)
            clr.a = int(255 * prog * (self.max_brightness if prog < 1 else self.final_brightness))
            overlay.fill(clr)
            overlay.blit(self.paint_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            overlay.fill(colors.WHITE, special_flags=pygame.BLEND_RGB_ADD)
            self.drying_image.blit(overlay, (0, 0))

            self.dry_time_remaining -= dt / 1000

    def _fill_cell(self, xy, from_color=None):
        if from_color is not None and random.random() < 0.5:
            color = from_color
        else:
            color = random.choice(self.palette)
        self.paint_surf.set_at(xy, color)

    def is_finished_pouring(self):
        return len(self.edge_cells) == 0

    def is_finished(self):
        return self.is_finished_pouring() and self.dry_time_remaining <= 0

    def get_image(self):
        return self.paint_surf if (not self.is_finished_pouring() or self.drying_image is None) else self.drying_image


if __name__ == "__main__":
    p = geometry.Polygon([(0.3333333333333333, 0.49999999999999994), (0.3333333333333333, 0.16666666666666663),
                          (0.0, 0.16666666666666663), (0.0, 0.49999999999999994), (0.0, 0.8333333333333334),
                          (0.3333333333333333, 0.8333333333333334), (0.6666666666666666, 0.8333333333333334),
                          (1.0, 0.8333333333333334), (1.0, 0.49999999999999994), (1.0, 0.16666666666666663),
                          (0.6666666666666666, 0.16666666666666663), (0.6666666666666666, 0.49999999999999994)])\
        .scale(150, from_center=False).shift((5, 5))

    def make_filter():
        return Filler(p, (0, 0, 160, 160), palette=colors.TONES)

    filler = make_filter()

    screen = pygame.display.set_mode((400, 400))
    clock = pygame.time.Clock()
    dt = 0

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    filler = make_filter()
                elif e.key == pygame.K_ESCAPE:
                    running = False

        filler.update(dt)

        screen.fill("purple")
        img = filler.get_image()
        img = pygame.transform.scale_by(img, 2)

        xy = (screen.get_size()[0] / 2 - img.get_size()[0] / 2,
              screen.get_size()[1] / 2 - img.get_size()[1] / 2)

        screen.blit(img, xy)
        pygame.draw.rect(screen, "red", (xy[0], xy[1], img.get_size()[0], img.get_size()[1]), width=1)

        pygame.display.flip()

        dt = clock.tick(60)


