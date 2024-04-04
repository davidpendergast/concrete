import pygame

import const
import src.utils as utils
import src.spites as sprites
import src.colors as colors

import src.scenes as scenes

import src.gameplay as gameplay


DELAY = 20
ALPHA = 96

class BasicTextScene(scenes.Scene):

    def __init__(self, title_text, info_text=None, underlay: gameplay.GameplayScene = None):
        super().__init__()
        self.title_text = title_text
        self.info_text = info_text
        self.underlay = underlay

    def get_title_color(self):
        return colors.BLUE_LIGHT

    def get_title_font(self):
        return sprites.Sheet.TITLE_FONT

    def get_info_color(self):
        return colors.BLUE_LIGHT

    def get_info_font(self):
        return sprites.Sheet.FONT

    def update_underlay(self, dt):
        self.underlay.update(dt, fake=True)

    def apply_fader(self, surf, rect='full', alpha='default', color='default'):
        rect = surf.get_rect() if rect == 'full' else rect
        alpha = ALPHA if 'default' else alpha
        color = colors.BLACK if color == 'default' else color
        if rect is not None and alpha > 0:
            fader = pygame.Surface((rect[2], rect[3]), pygame.SRCCOLORKEY)
            fader.fill(color)
            fader.set_alpha(alpha)
            surf.blit(fader, (rect[0], rect[1]))

    def update(self, dt):
        super().update(dt)
        self.update_underlay(dt)

    def render(self, surf: pygame.Surface):
        super().render(surf)

        self.underlay.render(surf, skip_board=True)
        self.apply_fader(surf)

        screen_rect = self.underlay.board_area

        if self.title_text is not None:
            title_img = self.get_title_font().render(self.title_text, False, self.get_title_color())
            title_xy = (screen_rect[0] + screen_rect[2] // 2 - title_img.get_width() // 2,
                        screen_rect[1] + screen_rect[3] // 3 - title_img.get_height() // 2)
            surf.blit(title_img, title_xy)
            screen_rect = utils.rect_expand(screen_rect, top=-title_xy[1] - title_img.get_height())

        info_img = self.get_info_font().render(self.info_text, False, self.get_info_color(), None, screen_rect[2])
        info_rect = utils.center_rect_in_rect(info_img.get_rect(), screen_rect)
        surf.blit(info_img, info_rect)


class MainMenuScene(BasicTextScene):

    def __init__(self, underlay: gameplay.GameplayScene = None):
        super().__init__("Diabolical\nConcrete", "Click to Start",
                         gameplay.fresh_gameplay_scene() if underlay is None else underlay)

    def get_info_color(self):
        return colors.lerp_color(colors.BLUE_LIGHT, colors.WHITE)

    def update(self, dt):
        super().update(dt)
        if self.elapsed_time > DELAY:
            if pygame.K_ESCAPE in const.KEYS_PRESSED_THIS_FRAME:
                self.manager.do_quit()
            elif (len(const.KEYS_PRESSED_THIS_FRAME) > 0 and pygame.K_LEFT not in const.KEYS_PRESSED_THIS_FRAME) \
                    or len(const.MOUSE_PRESSED_AT_THIS_FRAME) > 0:
                self.manager.jump_to_scene(InstructionsScene(underlay=self.underlay))


class InstructionsScene(BasicTextScene):

    PAGES = [
        "Welcome to Hell.",
        "Your job is simple: Make slabs.",
        "A sequence of blueprints will appear to the left.\n<---",  # 2
        "Draw lines in the play area to construct them.",
        "Rotation, orientation, and scale does not matter. Right-click to erase.",
        "You get one tally mark for each completed slab.\n--->",  # 5
        "When you reach the dotted lines, you'll be promoted to the next design.",
        "A temperature meter is shown to the right.\n--->",  # 7
        "When you complete slabs, you'll be given more heat.",
        "Slabs will cure faster when the temperature is higher.",
        "If your heat runs out, you're fired.",
        "A score is kept above.",  # 11
        "Good luck."  # 12
    ]

    def __init__(self, page=0, underlay: gameplay.GameplayScene = None):
        super().__init__(None, InstructionsScene.PAGES[page], underlay=underlay)
        self.page = page

    def apply_fader(self, surf, rect='full', alpha='default', color='default'):
        rect = surf.get_rect()
        if self.page >= 2:
            rect = utils.rect_expand(rect, left=-self.underlay.goals_area[0] - self.underlay.goals_area[2])
        if self.page >= 5:
            rect = utils.rect_expand(rect, right=-self.underlay.tally_width)
        if self.page >= 7:
            rect = utils.rect_expand(rect, right=-self.underlay.thermo_width)
        if self.page >= 11:
            rect = self.underlay.board_area

        super().apply_fader(surf, rect=rect, alpha=alpha, color=color)

    def update_underlay(self, dt):
        self.underlay.update(dt, fake=True)
        if self.page >= 2:
            self.underlay.gs.update_goals(dt, None)

    def inc_page(self, change):
        if self.page + change < 0:
            self.manager.jump_to_scene(MainMenuScene(underlay=self.underlay))
        elif self.page + change >= len(InstructionsScene.PAGES):
            self.manager.jump_to_scene(self.underlay)  # start game
        else:
            self.manager.jump_to_scene(InstructionsScene(page=self.page + change, underlay=self.underlay))

    def update(self, dt):
        super().update(dt)
        if self.elapsed_time > DELAY:
            if pygame.K_ESCAPE in const.KEYS_PRESSED_THIS_FRAME or pygame.K_LEFT in const.KEYS_PRESSED_THIS_FRAME:
                self.inc_page(-1)
            elif len(const.KEYS_PRESSED_THIS_FRAME) > 0 or len(const.MOUSE_PRESSED_AT_THIS_FRAME) > 0:
                self.inc_page(1)


class GameOverScene(BasicTextScene):

    DELAY = 750

    def __init__(self, level=0, underlay: gameplay.GameplayScene = None):
        super().__init__("GAME OVER", "Click to Continue", underlay=underlay)

    def get_info_color(self):
        return colors.lerp_color(colors.BLUE_LIGHT, colors.WHITE)

    def apply_fader(self, surf, rect='full', alpha='default', color='default'):
        opac = int(min(1.0, self.elapsed_time / GameOverScene.DELAY) * ALPHA)
        super().apply_fader(surf, rect=rect, alpha=opac, color=color)

    def update(self, dt):
        super().update(dt)
        if self.elapsed_time > GameOverScene.DELAY:
            if len(const.KEYS_PRESSED_THIS_FRAME) > 0 or len(const.MOUSE_PRESSED_AT_THIS_FRAME) > 0:
                self.manager.jump_to_scene(MainMenuScene())