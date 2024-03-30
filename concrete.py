import pygame
import const

import src.scenes as scenes

import src.utils as utils


if __name__ == "__main__":
    screen = utils.make_fancy_scaled_display(
        (320, 240),
        scale_factor=2.,
        extra_flags=pygame.RESIZABLE
    )

    clock = pygame.time.Clock()
    dt = 0

    scene_manager = scenes.SceneManager(scenes.Scene())

    running = True
    while running and not scene_manager.should_quit:
        const.KEYS_PRESSED_THIS_FRAME.clear()
        const.KEYS_RELEASED_THIS_FRAME.clear()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                const.KEYS_PRESSED_THIS_FRAME.add(e.key)
                const.KEYS_HELD_THIS_FRAME.add(e.key)
            elif e.type == pygame.KEYUP:
                const.KEYS_RELEASED_THIS_FRAME.add(e.key)
                if e.key in const.KEYS_HELD_THIS_FRAME:
                    const.KEYS_HELD_THIS_FRAME.remove(e.key)

        scene_manager.update(dt)
        scene_manager.render(screen)

        pygame.display.flip()
        