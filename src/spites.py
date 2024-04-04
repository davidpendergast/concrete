import pygame

_SCORE_BG = [64, 0, 179, 19]
_THERMO_BG_UPPER = [0, 0, 22, 218]
_THERMO_BG_LOWER = [0, _THERMO_BG_UPPER[1] + _THERMO_BG_UPPER[3], 22, 22]
_THERMO = [37, 8, 12, 211]

class Sheet:
    SCORE_BG = None
    THERMO_BG_UPPER = None
    THERMO_BG_LOWER = None
    THERMO = None
    THERMO_Y_RANGE = [8, 8 + 210]

    NUMERALS = []
    NUMERAL_SIZE = (12, 12)
    GOAL_LINE = None

    DECORATION_BANNER = None
    DEMON_DADDY = None

    FONT: pygame.Font = None
    TITLE_FONT: pygame.Font = None

    @staticmethod
    def get_numerals(total_val, rng_seed=12345):
        if total_val <= 0:
            return []
        else:
            ret = []
            n_fives = total_val // 5
            last_val = total_val % 5
            v = rng_seed
            for _ in range(n_fives):
                v = (v*v + 1) % 101  # idk
                ret.append(Sheet.NUMERALS[v % len(Sheet.NUMERALS)][4])
            if last_val > 0:
                ret.append(Sheet.NUMERALS[v % len(Sheet.NUMERALS)][last_val - 1])
            return ret

    @staticmethod
    def load(filepath, font_path):
        sheet = pygame.image.load(filepath)
        Sheet.SCORE_BG = sheet.subsurface(_SCORE_BG)
        Sheet.THERMO_BG_UPPER = sheet.subsurface(_THERMO_BG_UPPER)
        Sheet.THERMO_BG_LOWER = sheet.subsurface(_THERMO_BG_LOWER)
        Sheet.THERMO = sheet.subsurface(_THERMO)
        Sheet.GOAL_LINE = sheet.subsurface([128, 32, 36, 16])
        Sheet.DECORATION_BANNER = sheet.subsurface([0, 256, 183, 20])
        Sheet.DEMON_DADDY = sheet.subsurface([64, 80, 64, 120])

        n_types = 2
        xy = (64, 32)
        for i in range(n_types):
            type_vals = []
            for j in range(5):
                type_vals.append(sheet.subsurface([xy[0] + j * Sheet.NUMERAL_SIZE[0], xy[1] + i * 16,
                                                   *Sheet.NUMERAL_SIZE]))
            Sheet.NUMERALS.append(type_vals)

        Sheet.FONT = pygame.Font(font_path)
        Sheet.TITLE_FONT = pygame.Font(font_path, size=32)
