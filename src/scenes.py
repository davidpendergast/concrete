import pygame


class SceneManager:

    def __init__(self, start: 'Scene'):
        self.active_scene = None
        self._next_scene = start

        self.should_quit = False

    def jump_to_scene(self, next_scene):
        self._next_scene = next_scene

    def update(self, dt):
        if self._next_scene is not None:
            if self.active_scene is not None:
                self.active_scene.on_exit()
                self.active_scene.manager = None
            self._next_scene.manager = self
            self.active_scene = self._next_scene
            self.active_scene.on_start()
            self._next_scene = None

        self.active_scene.update(dt)

    def render(self, surf):
        bg_color = self.active_scene.get_bg_color()
        if bg_color is not None:
            surf.fill(bg_color)
        self.active_scene.render(surf)

    def do_quit(self):
        self.should_quit = True


class Scene:

    def __init__(self):
        self.elapsed_time = 0
        self.manager = None

    def is_active(self):
        return self.manager is not None and self.manager.active_scene is self

    def on_start(self):
        pass

    def on_exit(self):
        pass

    def update(self, dt):
        self.elapsed_time += dt

    def render(self, surf: pygame.Surface):
        pass

    def get_bg_color(self):
        return (0, 0, 0)

    def get_caption_info(self):
        return {}
