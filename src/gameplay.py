import pygame
import src.scenes as scenes
import src.colors as colors

class GameState:
    def __init__(self):
        pass

class GameplayScene(scenes.Scene):

    def __init__(self, gs: GameState):
        super().__init__()
        self.gs = gs

    def update(self, dt):
        super().update(dt)

    def render(self, surf: pygame.Surface):
        pass

    def get_bg_color(self):
        return colors.DARK_GRAY



