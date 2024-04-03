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

    @staticmethod
    def load(filepath):
        sheet = pygame.image.load(filepath)
        Sheet.SCORE_BG = sheet.subsurface(_SCORE_BG)
        Sheet.THERMO_BG_UPPER = sheet.subsurface(_THERMO_BG_UPPER)
        Sheet.THERMO_BG_LOWER = sheet.subsurface(_THERMO_BG_LOWER)
        Sheet.THERMO = sheet.subsurface(_THERMO)
