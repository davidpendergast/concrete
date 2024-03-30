import pygame
import os
import const
import src.utils as utils

_MAX_CACHE_SIZE = 1000
_IMG_XFORM_CACHE = {}


def resize(img: pygame.Surface, size, method='nearest', nocache=False):
    if size[0] is None and size[1] is None:
        return img
    elif size[0] is None:
        size = (int(img.get_width() / img.get_height() * size[1]), size[1])
    elif size[1] is None:
        size = (size[0], int(img.get_height() / img.get_width() * size[0]))

    key = (id(img), size, method)
    if len(_IMG_XFORM_CACHE) > _MAX_CACHE_SIZE:
        print(f"WARN: _IMG_XFORM_CACHE overfilled! (current item={key})")
        if const.IS_DEV:
            raise ValueError(f"Cache overfilled, probably due to a leak.")
        _IMG_XFORM_CACHE.clear()

    if key not in _IMG_XFORM_CACHE:
        if method == 'smooth':
            resized_img = pygame.transform.smoothscale(img, size)
        else:
            resized_img = pygame.transform.scale(img, size)
        if nocache:
            return resized_img
        _IMG_XFORM_CACHE[key] = resized_img

    return _IMG_XFORM_CACHE[key]


def tint(surf: pygame.Surface, color, strength: float, nocache=False):
    q = 8
    strength = (int(255 * strength) // q) * q
    strength = min(255, max(0, strength))
    if strength == 0:
        return surf
    key = (id(surf), color, strength)
    if key not in _IMG_XFORM_CACHE:
        non_tint_img = surf.copy()
        non_tint_img.fill(utils.int_mults(utils.int_sub((255, 255, 255), color), (255 - strength) / 255), special_flags=pygame.BLEND_MULT)
        tint_img = surf.copy()
        tint_img.fill(utils.int_mults(color, strength / 255), special_flags=pygame.BLEND_MULT)
        tint_img.blit(non_tint_img, (0, 0), special_flags=pygame.BLEND_ADD)

        if nocache:
            return tint_img
        else:
            _IMG_XFORM_CACHE[key] = tint_img
    return _IMG_XFORM_CACHE[key]


def sc(surf, factor):
    return pygame.transform.scale_by(surf, (factor, factor))


def fl(surf, x=False, y=True):
    return pygame.transform.flip(surf, x, y)


class Spritesheet:

    @staticmethod
    def load(filepath):
        pass
