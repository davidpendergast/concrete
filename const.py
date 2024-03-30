import os

NAME_OF_GAME = "Diabolical Slabs"
GAME_DIMS = (320, 240)
BOARD_SIZE = 200
THRESH = 0.0001

BOARD_STYLES = [
    ("SQUARE", 4),
    ("SQUARE", 5),
    ("RECT", (3, 5)),
    ("RECT", (4, 3)),
    ("HEX", (5, 5)),
    ("HEX", (3, 3)),
    ("HEX", (3, 5))
]

IS_DEV = os.path.exists(".gitignore")

KEYS_HELD_THIS_FRAME = set()
KEYS_PRESSED_THIS_FRAME = set()
KEYS_RELEASED_THIS_FRAME = set()

MOUSE_XY = (0, 0)
MOUSE_PRESSED_AT_THIS_FRAME = {}   # btn -> xy
MOUSE_RELEASED_AT_THIS_FRAME = {}  # btn -> xy
MOUSE_BUTTONS_HELD_THIS_FRAME = set()

CLICK_DISTANCE_PX = 8
AUTO_REMOVE_IF_INTERSECTING = True

