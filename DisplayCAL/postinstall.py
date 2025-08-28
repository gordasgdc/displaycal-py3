"""Post-install and uninstall tasks for DisplayCAL on Windows, macOS, and Linux.

It includes functions to create shortcuts, manage installed files, and update
system resources such as icons and desktop menu entries.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import traceback
from io import StringIO
from os.path import basename, splitext
from subprocess import call

from DisplayCAL.meta import NAME
from DisplayCAL.util_os import safe_glob, which

RECORD_FILE_NAME = "INSTALLED_FILES"

if sys.stdout and hasattr(sys.stdout, "isatty") and not sys.stdout.isatty():
    sys.stdout = StringIO()

if sys.platform == "win32":
    if "create_shortcut" not in globals():
        # this function is only available within bdist_wininst installers
        try:
            import win32con
            from pythoncom import (
                CLSCTX_INPROC_SERVER,
                CoCreateInstance,
                IID_IPersistFile,
            )
            from win32com.shell import shell
        except ImportError:

            def create_shortcut(*args) -> None:
                """Dummy function to create a Windows shortcut."""

        else:

            def create_shortcut(*args) -> None:
                """Create a Windows shortcut."""
                shortcut = CoCreateInstance(
                    shell.CLSID_ShellLink,
                    None,
                    CLSCTX_INPROC_SERVER,
                    shell.IID_IShellLink,
                )
                shortcut.SetPath(args[0])
                shortcut.SetDescription(args[1])
                if len(args) > 3:
                    shortcut.SetArguments(args[3])
                if len(args) > 4:
                    shortcut.SetWorkingDirectory(args[4])
                if len(args) > 5:
                    shortcut.SetIconLocation(args[5], args[6] if len(args) > 6 else 0)
                shortcut.SetShowCmd(win32con.SW_SHOWNORMAL)
                shortcut.QueryInterface(IID_IPersistFile).Save(args[2], 0)

    if "directory_created" not in globals():
        # this function is only available within bdist_wininst installers

        def directory_created(path: str) -> None:
            """Dummy function to record directory creation.

            Args:
                path (str): The path of the directory that was created.
            """

    if "file_created" not in globals():
        # this function is only available within bdist_wininst installers
        try:
            import win32api
        except ImportError:

            def file_created(path: str) -> None:
                """Dummy function to record file creation.

                Args:
                    path (str): The path of the file that was created.
                """

        else:

            def file_created(path: str) -> None:
                """Record the file creation in the installed files record.

                Args:
                    path (str): The path of the file that was created.
                """
                if not os.path.exists(RECORD_FILE_NAME):
                    return
                installed_files = []
                if os.path.exists(RECORD_FILE_NAME):
                    with open(RECORD_FILE_NAME) as record_file:
                        installed_files.extend(
                            line.rstrip("\n") for line in record_file
                        )
                try:
                    path.encode("ASCII")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    # the contents of the record file used by distutils
                    # must be ASCII GetShortPathName allows us to avoid
                    # any issues with encoding because it returns the
                    # short path as 7-bit string (while still being a
                    # valid path)
                    path = win32api.GetShortPathName(path)
                installed_files.append(path)
                with open(RECORD_FILE_NAME, "w") as record_file:
                    record_file.write("\n".join(installed_files))

    if "get_special_folder_path" not in globals():
        # this function is only available within bdist_wininst installers
        try:
            from win32com.shell import shell, shellcon
        except ImportError:

            def get_special_folder_path(csidl_string: str) -> None:
                """Implement the dummy version of getting the path to a special folder.

                Args:
                    csidl_string (str): The CSIDL string representing the
                        special folder.

                Returns:
                    None: Returns None.
                """

        else:

            def get_special_folder_path(csidl_string: str) -> str:
                """Get the path to a special folder.

                Args:
                    csidl_string (str): The CSIDL string representing the
                        special folder.

                Returns:
                    str: The path to the special folder.
                """
                return shell.SHGetSpecialFolderPath(
                    0, getattr(shellcon, csidl_string), 1
                )


def postinstall_macos(prefix: None | str = None) -> None:
    """Do postinstall actions for macOS.

    Args:
        prefix (None | str, optional): The installation prefix. Defaults to None.
    """
    # TODO: implement


def postinstall_windows(prefix: str) -> None:
    """Do postinstall actions for Windows.

    Args:
        prefix (str): The installation prefix.
    """
    # assume we are running from bdist_wininst installer if prefix is None,
    # otherwise assume we are running from source dir, or from install dir
    module_path = (
        os.path.dirname(os.path.abspath(__file__)) if prefix is None else prefix
    )
    if not os.path.exists(module_path):
        print("warning - '{}' not found".format(module_path.encode("MBCS", "replace")))
        return

    create_installed_files_record(module_path)
    main_icon = get_main_icon(module_path)
    if not main_icon:
        return

    try:
        start_menu_programs_common = get_special_folder_path("CSIDL_COMMON_PROGRAMS")
        start_menu_programs = get_special_folder_path("CSIDL_PROGRAMS")
        start_menu_common = get_special_folder_path("CSIDL_COMMON_start_menu")
        start_menu = get_special_folder_path("CSIDL_start_menu")
    except OSError:
        traceback.print_exc()
        return

    create_start_menu_shortcuts(
        module_path,
        main_icon,
        start_menu_programs_common,
        start_menu_programs,
        start_menu_common,
        start_menu,
    )


def create_installed_files_record(module_path: str) -> None:
    """Create the installed files record.

    Args:
        module_path (str): The module path.
    """
    if not os.path.exists(RECORD_FILE_NAME):
        return
    installed_record_file_path = os.path.join(module_path, RECORD_FILE_NAME)
    # touch - create the file
    with open(installed_record_file_path, "w"):
        pass
    file_created(installed_record_file_path)
    shutil.copy2(RECORD_FILE_NAME, installed_record_file_path)


def get_main_icon(module_path: str) -> None | str:
    """Get the main icon for the application.

    Args:
        module_path (str): The module path.

    Returns:
        None | str: The path to the main icon, or None if not found.
    """
    main_icon = os.path.join(module_path, "theme", "icons", f"{NAME}.ico")
    if not os.path.exists(main_icon):
        print("warning - '{}' not found".format(main_icon.encode("MBCS", "replace")))
        return None
    return main_icon


def create_start_menu_shortcuts(
    module_path: str,
    main_icon: str,
    start_menu_programs_common: str,
    start_menu_programs: str,
    start_menu_common: str,
    start_menu: str,
) -> None:
    """Create start menu shortcuts for the application.

    Args:
        module_path (str): The module path.
        main_icon (str): The path to the main icon.
        start_menu_programs_common (str): The path to the common programs
            start menu.
        start_menu_programs (str): The path to the user's programs start menu.
        start_menu_common (str): The path to the common start menu.
        start_menu (str): The path to the user's start menu.
    """
    filenames = [
        filename
        for filename in safe_glob(os.path.join(sys.prefix, "Scripts", f"{NAME}*"))
        if not filename.endswith("-script.py")
        and not filename.endswith("-script.pyw")
        and not filename.endswith(".manifest")
        and not filename.endswith(".pyc")
        and not filename.endswith(".pyo")
        and not filename.endswith("_postinstall.py")
    ] + ["LICENSE.txt", "README.html", "Uninstall"]
    installed_shortcuts = []
    for path in (start_menu_programs_common, start_menu_programs):
        if not path:
            continue

        group, group_path = create_group_path(
            path,
            start_menu_programs,
            start_menu_common,
            start_menu,
        )
        if not group_path:
            continue

        directory_created(group_path)

        create_shortcut_files(
            filenames, group, group_path, module_path, main_icon, installed_shortcuts
        )

        if installed_shortcuts == filenames:
            break


def create_group_path(
    path: str, start_menu_programs: str, start_menu_common: str, start_menu: str
) -> tuple[str, None | str]:
    """Create the group path for the start menu.

    Args:
        path (str): The path to create the group in.
        start_menu_programs (str): The path to the user's programs start menu.
        start_menu_common (str): The path to the common start menu.
        start_menu (str): The path to the user's start menu.

    Returns:
        tuple[str, None | str]: The group name and the group path, or None if
            creation failed.
    """
    group_path = os.path.join(path, NAME)
    if path == start_menu_programs:
        group = os.path.relpath(group_path, start_menu)
    else:
        group = os.path.relpath(group_path, start_menu_common)

    if not os.path.exists(group_path):
        with contextlib.suppress(Exception):
            os.makedirs(group_path)
            # maybe insufficient privileges?

    if os.path.exists(group_path):
        print(
            ("Created start menu group '{}' in {}").format(
                NAME,
                (
                    str(path, "MBCS", "replace") if not isinstance(path, str) else path
                ).encode("MBCS", "replace"),
            )
        )
    else:
        print(
            ("Failed to create start menu group '{}' in {}").format(
                NAME,
                (
                    str(path, "MBCS", "replace") if not isinstance(path, str) else path
                ).encode("MBCS", "replace"),
            )
        )
        return group_path, None
    return group, group_path


def create_shortcut_files(
    filenames: list,
    group: str,
    group_path: str,
    module_path: str,
    main_icon: str,
    installed_shortcuts: list,
) -> None:
    """Create shortcut files in the specified group path.

    Args:
        filenames (list): List of filenames to create shortcuts for.
        group (str): The name of the group.
        group_path (str): The path to the group directory.
        module_path (str): The module path.
        main_icon (str): The path to the main icon.
        installed_shortcuts (list): List to store installed shortcuts.
    """
    for filename in filenames:
        link_name = splitext(basename(filename))[0]
        link_path = os.path.join(group_path, f"{link_name}.lnk")
        if os.path.exists(link_path):
            try:
                os.remove(link_path)
            except Exception:
                # maybe insufficient privileges?
                print(
                    ("Failed to create start menu entry '{}' in {}").format(
                        link_name,
                        (
                            str(group_path, "MBCS", "replace")
                            if not isinstance(group_path, str)
                            else group_path
                        ).encode("MBCS", "replace"),
                    )
                )
                continue

        if os.path.exists(link_path):
            file_created(link_path)
            installed_shortcuts.append(filename)
            continue

        if link_name != "Uninstall":
            target_path = os.path.join(module_path, filename)

        try:
            if link_name == "Uninstall":
                uninstaller = os.path.join(sys.prefix, f"Remove{NAME}.exe")
                if os.path.exists(uninstaller):
                    create_shortcut(
                        uninstaller,
                        link_name,
                        link_path,
                        f'-u "{os.path.join(sys.prefix, NAME)}-wininst.log"',
                        sys.prefix,
                        os.path.join(
                            module_path,
                            "theme",
                            "icons",
                            f"{NAME}-uninstall.ico",
                        ),
                    )
                else:
                    # When running from a bdist_wininst or bdist_msi installer,
                    # sys.executable points to the installer executable,
                    # not python.exe
                    create_shortcut(
                        os.path.join(sys.prefix, "python.exe"),
                        link_name,
                        link_path,
                        '"{}" uninstall --record="{}"'.format(
                            os.path.join(module_path, "setup.py"),
                            os.path.join(module_path, RECORD_FILE_NAME),
                        ),
                        sys.prefix,
                        os.path.join(
                            module_path,
                            "theme",
                            "icons",
                            f"{NAME}-uninstall.ico",
                        ),
                    )
            elif link_name.startswith(NAME):
                # When running from a bdist_wininst or bdist_msi installer,
                # sys.executable points to the installer executable,
                # not python.exe
                icon = os.path.join(
                    module_path,
                    "theme",
                    "icons",
                    f"{link_name}.ico",
                )
                icon = main_icon if not os.path.isfile(icon) else icon
                if filename.endswith(".exe"):
                    exe = filename
                    args = ""
                else:
                    exe = os.path.join(sys.prefix, "pythonw.exe")
                    args = f'"{target_path}"'
                create_shortcut(
                    exe,
                    link_name,
                    link_path,
                    args,
                    module_path,
                    icon,
                )
            else:
                create_shortcut(target_path, link_name, link_path, "", module_path)
        except Exception:
            # maybe insufficient privileges?
            print(
                ("Failed to create start menu entry '{}' in {}").format(
                    link_name,
                    (
                        str(group_path, "MBCS", "replace")
                        if not isinstance(group_path, str)
                        else group_path
                    ).encode("MBCS", "replace"),
                )
            )
            continue
        print(
            ("Installed start menu entry '{}' to {}").format(
                link_name,
                (
                    str(group, "MBCS", "replace")
                    if not isinstance(group, str)
                    else group
                ).encode("MBCS", "replace"),
            )
        )
        file_created(link_path)
        installed_shortcuts.append(filename)


def postinstall_linux(prefix: None | str = None) -> None:
    """Do postinstall actions for Linux.

    Args:
        prefix (None | str, optional): The installation prefix. Defaults to
            None.
    """
    # Linux/Unix
    if prefix is None:
        prefix = sys.prefix
    if which("touch"):
        call(["touch", "--no-create", f"{prefix}/share/icons/hicolor"])  # noqa: S607
    if which("xdg-icon-resource"):
        # print("installing icon resources...")
        # for size in [16, 22, 24, 32, 48, 256]:
        # call([
        #     "xdg-icon-resource",
        #     "install",
        #     "--noupdate",
        #     "--novendor",
        #     "--size",
        #     str(size),
        #     f"{prefix}/share/{name}/theme/icons/{size}x{size}/{name}.png"
        # ])
        call(["xdg-icon-resource", "forceupdate"])  # noqa: S607
    if which("xdg-desktop-menu"):
        # print("installing desktop menu entry...")
        # call([
        #     "xdg-desktop-menu",
        #     "install",
        #     "--novendor",
        #     f"{prefix}/share/{name}/{name}.desktop"
        # ])
        call(["xdg-desktop-menu", "forceupdate"])  # noqa: S607


def postinstall(prefix: None | str = None) -> None:
    """Do postinstall actions.

    Args:
        prefix (None | str, optional): The installation prefix. Defaults to
            None.
    """
    if sys.platform == "darwin":
        postinstall_macos()
    elif sys.platform == "win32":
        postinstall_windows(prefix)
    else:
        postinstall_linux(prefix)


def postuninstall(prefix: None | str = None) -> None:
    """Do postuninstall actions.

    Args:
        prefix (None | str, optional): The installation prefix. Defaults to
            None.
    """
    if sys.platform == "darwin":
        # TODO: implement
        pass
    elif sys.platform == "win32":
        # nothing to do
        pass
    else:
        # Linux/Unix
        if prefix is None:
            prefix = sys.prefix
        if which("xdg-desktop-menu"):
            # print("uninstalling desktop menu entry...")
            # call(["xdg-desktop-menu", "uninstall", prefix +
            # (f"/share/applications/{name}.desktop")])
            call(["xdg-desktop-menu", "forceupdate"])  # noqa: S607
        if which("xdg-icon-resource"):
            # print("uninstalling icon resources...")
            # for size in [16, 22, 24, 32, 48, 256]:
            # call(["xdg-icon-resource", "uninstall", "--noupdate", "--size",
            # str(size), name])
            call(["xdg-icon-resource", "forceupdate"])  # noqa: S607


def main() -> None:
    """Main function to handle post-installation and uninstallation tasks."""
    prefix = None
    for arg in sys.argv[1:]:
        arg = arg.split("=")
        if len(arg) == 2 and arg[0] == "--prefix":
            prefix = arg[1]
    try:
        if "-remove" in sys.argv[1:]:
            postuninstall(prefix)
        else:
            postinstall(prefix)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
