import pygame
import const

import src.scenes as scenes
import src.utils as utils
import src.gameplay as gameplay
import src.spites as sprites


if __name__ == "__main__":
    pygame.init()
    screen = utils.make_fancy_scaled_display(
        const.GAME_DIMS,
        scale_factor=2.,
        extra_flags=pygame.RESIZABLE
    )
    pygame.display.set_caption(const.NAME_OF_GAME)

    sprites.Sheet.load(utils.res_path("assets/sprites.png"),
                       utils.res_path("assets/fonts/m6x11.ttf"))

    clock = pygame.time.Clock()
    dt = 0

    gs = gameplay.GameState()
    scene_manager = scenes.SceneManager(gameplay.GameplayScene(gs))

    running = True
    while running and not scene_manager.should_quit:
        const.KEYS_PRESSED_THIS_FRAME.clear()
        const.KEYS_RELEASED_THIS_FRAME.clear()
        const.MOUSE_PRESSED_AT_THIS_FRAME.clear()
        const.MOUSE_RELEASED_AT_THIS_FRAME.clear()
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
            elif e.type == pygame.MOUSEMOTION:
                const.MOUSE_XY = e.pos
            elif e.type == pygame.MOUSEBUTTONDOWN:
                const.MOUSE_PRESSED_AT_THIS_FRAME[e.button] = e.pos
                const.MOUSE_BUTTONS_HELD_THIS_FRAME.add(e.button)
            elif e.type == pygame.MOUSEBUTTONUP:
                const.MOUSE_RELEASED_AT_THIS_FRAME[e.button] = e.pos
                if e.button in const.MOUSE_BUTTONS_HELD_THIS_FRAME:
                    const.MOUSE_BUTTONS_HELD_THIS_FRAME.remove(e.button)
            elif e.type == pygame.WINDOWLEAVE:
                const.MOUSE_XY = None

        scene_manager.update(dt)
        scene_manager.render(screen)

        pygame.display.flip()

        dt = clock.tick(60)
