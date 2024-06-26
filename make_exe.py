import os
import platform
import tempfile
import shutil
import stat
import struct

####   OPTIONS   ####

NAME_OF_GAME = "Slabferno"
NAME_OF_GAME_SIMPLE = "slabferno"

ICON_PATH_ICO = None
ICON_PATH_ICNS = None

SPLASH_IMAGE_PATH = None

ONEFILE_MODE = True
SHOW_CONSOLE = False

SHOW_TRACEBACK_ON_CRASH = True

ENTRY_POINT_FILE = "concrete.py"

DATA_TO_BUNDLE = [
    ("assets", "assets")
]
DATA_TO_COPY = [
    ("info.txt", "info.txt")
]

#### END OPTIONS ####

_WINDOWS = "Windows"
_LINUX = "Linux"
_MAC = "Darwin"

OS_SYSTEM_STR = platform.system()
if OS_SYSTEM_STR not in (_WINDOWS, _LINUX, _MAC):
    raise ValueError("Unrecognized operating system: {}".format(OS_SYSTEM_STR))

if not ONEFILE_MODE:
    # XXX using a splash image with ONEFILE_MODE = False seems to
    # cause the exe to create a non-focused pygame window (that
    # lands behind the file browser). So I'm disabling this for now.
    # You don't really need a splash image with non-onefile anyways.
    SPLASH_IMAGE_PATH = None

if OS_SYSTEM_STR == _MAC:
    SPLASH_IMAGE_PATH = None  # doesn't work on mac
    ONEFILE_MODE = True  # onedir doesn't really seem to work

SPEC_CONTENTS = f"""
# -*- mode: python ; coding: utf-8 -*-
# WARNING: This file is auto-generated (see make_exe.py)

a = Analysis(['{ENTRY_POINT_FILE}'],
             pathex=[''],
             binaries=[],
             datas=[{", ".join(f"('{src}', '{dest}')" for (src, dest) in DATA_TO_BUNDLE)}],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=None)

# a.datas += Tree('data', prefix='data')  # pygame_gui thing?

pyz = PYZ(a.pure, a.zipped_data, cipher=None)
"""

STD_EXE_OPTS = f"""
          name='{NAME_OF_GAME}',
          console={SHOW_CONSOLE},
          icon=~ICON_PATH~,
          debug=False,
          strip=False,
          upx=True,
          disable_windowed_traceback={not SHOW_TRACEBACK_ON_CRASH},
          bootloader_ignore_signals=False
"""

# PREVENT YOUR DEATH. GO NO FURTHER
# There's nothing in this file worth dying for.
# Do not go beyond this point

if ONEFILE_MODE and SPLASH_IMAGE_PATH is None:
    SPEC_CONTENTS += f"""
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],  # no idea
{STD_EXE_OPTS})

# for mac builds, which I guess requires onefile mode?
app = BUNDLE(exe,  
         name='{NAME_OF_GAME}.app',
         icon=~ICON_PATH~,
         bundle_identifier=None)
"""
elif not ONEFILE_MODE and SPLASH_IMAGE_PATH is None:
    SPEC_CONTENTS += f"""
exe = EXE(pyz,
          a.scripts,
          [],  # no idea what this is
          exclude_binaries=True,
{STD_EXE_OPTS})

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='{NAME_OF_GAME}',
    strip=False,
    upx=True
)
"""
else:  # splash mode (note that mac + splash doesn't work)
    SPEC_CONTENTS += f"""
splash = Splash('{SPLASH_IMAGE_PATH}',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True)
"""
    if ONEFILE_MODE:
        SPEC_CONTENTS += f"""
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas, 
          splash, 
          splash.binaries,
          [],
{STD_EXE_OPTS})
"""
    else:
        SPEC_CONTENTS += f"""
exe = EXE(pyz,
          a.scripts,
          splash,
          [],  # no idea what this is
          exclude_binaries=True,
{STD_EXE_OPTS})

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    splash.binaries,
    name='{NAME_OF_GAME}',
    strip=False,
    upx=True
)
"""


def _ask_yes_or_no_question(question):
    print("")  # newline to make it a little less claustrophobic
    answer = None
    while answer is None:
        txt = input("  " + question + " (y/n): ")
        if txt == "y" or txt == "Y":
            answer = True
        elif txt == "n" or txt == "N":
            answer = False
    print("")
    return answer


def _calc_bit_count_str():
    return "{}bit".format(struct.calcsize("P") * 8)


def _get_icon_path(os_version_str):
    if os_version_str == _MAC:
        return os.path.normpath(ICON_PATH_ICNS) if ICON_PATH_ICNS else None
    else:
        return os.path.normpath(ICON_PATH_ICO) if ICON_PATH_ICO else None


def do_it():
    if OS_SYSTEM_STR == _MAC:
        pretty_os_str = "Mac"  # darwin is weird
    else:
        pretty_os_str = OS_SYSTEM_STR

    os_bit_count_str = _calc_bit_count_str()

    spec_filename = "output.spec"
    print("INFO: creating spec file {}".format(spec_filename))

    icon_path = _get_icon_path(OS_SYSTEM_STR)
    with open(spec_filename, "w") as f:
        f.write(SPEC_CONTENTS.replace("~ICON_PATH~", f"'{icon_path}'" if icon_path else "None"))

    dist_dir = os.path.join("dist", "{}_{}_{}".format(
        NAME_OF_GAME_SIMPLE,
        pretty_os_str.lower(),
        os_bit_count_str.lower()))

    if os.path.exists(dist_dir):
        ans = _ask_yes_or_no_question("Overwrite {}?".format(dist_dir))
        if ans:
            print("INFO: deleting pre-existing build {}".format(dist_dir))
            shutil.rmtree(str(dist_dir), ignore_errors=True)
        else:
            print("INFO: user opted to not overwrite pre-existing build, exiting")
            return

    dist_dir_subdir = os.path.join(dist_dir, NAME_OF_GAME_SIMPLE)

    with tempfile.TemporaryDirectory() as temp_dir:
        print("INFO: created temp directory: {}".format(temp_dir))
        print("INFO: launching pyinstaller...\n")

        # note that this call blocks until the process is finished
        pyinstaller_cmd = "py -3.8 -m PyInstaller" if OS_SYSTEM_STR == _WINDOWS else "pyinstaller"
        os.system("{} {} --distpath {} --workpath {}".format(
            pyinstaller_cmd, spec_filename, dist_dir_subdir, temp_dir))

        print("\nINFO: cleaning up {}".format(temp_dir))

    print("INFO: cleaning up {}".format(spec_filename))
    if os.path.exists(str(spec_filename)):
        os.remove(str(spec_filename))

    if OS_SYSTEM_STR == _LINUX:
        print("INFO: chmod'ing execution permissions to all users (linux)")
        exe_path = os.path.join(dist_dir_subdir, NAME_OF_GAME)
        if not os.path.exists(str(exe_path)):
            raise ValueError("couldn't find exe to apply exec permissions: {}".format(exe_path))
        else:
            st = os.stat(str(exe_path))
            os.chmod(str(exe_path), st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    for src_path, dest_path in DATA_TO_COPY:
        if not os.path.exists(src_path):
            raise ValueError("couldn't find data to copy: {}".format(src_path))
        else:
            full_dest_path = os.path.join(dist_dir_subdir, dest_path)
            print("INFO: copying {} to {}".format(src_path, full_dest_path))
            if os.path.isfile(src_path):
                shutil.copy2(src_path, full_dest_path)  # copying a single file
            else:
                shutil.copytree(src_path, full_dest_path)  # copying a directory

    print("\nINFO: make_exe.py has finished")


if __name__ == "__main__":
    do_it()
