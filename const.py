import os

NAME_OF_GAME = "Diabolical Slabs"
GAME_DIMS = (320, 240)
BOARD_SIZE = 200

IS_DEV = os.path.exists(".gitignore")

KEYS_HELD_THIS_FRAME = set()
KEYS_PRESSED_THIS_FRAME = set()
KEYS_RELEASED_THIS_FRAME = set()