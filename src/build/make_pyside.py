#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# *****************************************************************************
# Copyright 2020 Autodesk, Inc. All rights reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
# *****************************************************************************

import argparse
import glob
import os
import re
import pathlib
import shutil
import subprocess
import platform
import tempfile
import uuid

from utils import (
    download_file,
    extract_7z_archive,
    verify_7z_archive,
    update_env_path,
)
from make_python import get_python_interpreter_args

SOURCE_DIR = ""
OUTPUT_DIR = ""
TEMP_DIR = ""
VARIANT = ""

QT_OUTPUT_DIR = ""
PYTHON_OUTPUT_DIR = ""
OPENSSL_OUTPUT_DIR = ""

LIBCLANG_URL_BASE = "https://mirrors.ocf.berkeley.edu/qt/development_releases/prebuilt/libclang/libclang-release_"


def test_python_distribution(python_home: str) -> None:
    """
    Test the Python distribution.

    :param python_home: Package root of an Python package
    """
    tmp_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
    os.makedirs(tmp_dir)

    tmp_python_home = os.path.join(tmp_dir, os.path.basename(python_home))
    try:
        print(f"Moving {python_home} to {tmp_python_home}")
        shutil.move(python_home, tmp_python_home)

        python_validation_args = get_python_interpreter_args(tmp_python_home, VARIANT) + [
            "-c",
            "\n".join(
                [
                    "from PySide2 import *",
                    "from PySide2 import QtWebEngineCore, QtWebEngine",
                ]
            ),
        ]
        print(f"Validating the PySide package with {python_validation_args}")
        subprocess.run(python_validation_args).check_returncode()
    finally:
        print(f"Moving {tmp_python_home} to {python_home}")
        shutil.move(tmp_python_home, python_home)


def prepare() -> None:
    """
    Run the clean step of the build. Removes everything.
    """
    if os.path.exists(TEMP_DIR) is False:
        os.makedirs(TEMP_DIR)

    # PySide2 5.15.x recommends building with clang version 8.
    # But clang 8 headers are not compatible with Mac SDK 13.3+ headers.
    # To workaround it, since Mac is clang-based, we'll detect the OS clang
    # version and download the matching headers to build PySide.
    clang_filename_suffix = ""

    system = platform.system()
    if system == "Darwin":
        clang_version_search = re.search(
            "version (\d+)\.(\d+)\.(\d+)",
            os.popen("clang --version").read(),
        )
        clang_version_str = ".".join(clang_version_search.groups())
        clang_filename_suffix = clang_version_str + "-based-macos-universal.7z"
    elif system == "Linux":
        clang_filename_suffix = "80-based-linux-Rhel7.2-gcc5.3-x86_64.7z"
    elif system == "Windows":
        clang_filename_suffix = "140-based-windows-vs2019_64.7z"

    download_url = LIBCLANG_URL_BASE + clang_filename_suffix
    libclang_zip = os.path.join(TEMP_DIR, "libclang.7z")
    if os.path.exists(libclang_zip) is False:
        download_file(download_url, libclang_zip)
    # if we have a failed download, clean it up and redownload.
    # checking for False since it can return None when archive doesn't have a CRC
    elif verify_7z_archive(libclang_zip) is False:
        os.remove(libclang_zip)
        download_file(download_url, libclang_zip)

    # clean up previous failed extraction
    libclang_tmp = os.path.join(TEMP_DIR, "libclang-tmp")
    if os.path.exists(libclang_tmp) is True:
        shutil.rmtree(libclang_tmp)

    # extract to a temp location and only move if successful
    libclang_extracted = os.path.join(TEMP_DIR, "libclang")
    if os.path.exists(libclang_extracted) is False:
        extract_7z_archive(libclang_zip, libclang_tmp)
        shutil.move(libclang_tmp, libclang_extracted)

    libclang_install_dir = os.path.join(libclang_extracted, "libclang")

    if OPENSSL_OUTPUT_DIR:
        os.environ["PATH"] = os.path.pathsep.join(
            [
                os.path.join(OPENSSL_OUTPUT_DIR, "bin"),
                os.environ.get("PATH", ""),
            ]
        )

    print(f"PATH={os.environ['PATH']}")

    os.environ["LLVM_INSTALL_DIR"] = libclang_install_dir
    os.environ["CLANG_INSTALL_DIR"] = libclang_install_dir

    # PySide2 build requires a version of numpy lower than 1.23
    install_numpy_args = get_python_interpreter_args(PYTHON_OUTPUT_DIR, VARIANT) + [
        "-m",
        "pip",
        "install",
        "numpy<1.23",
    ]
    print(f"Installing numpy with {install_numpy_args}")
    subprocess.run(install_numpy_args).check_returncode()

    cmakelist_path = os.path.join(SOURCE_DIR, "sources", "shiboken2", "ApiExtractor", "CMakeLists.txt")
    old_cmakelist_path = os.path.join(SOURCE_DIR, "sources", "shiboken2", "ApiExtractor", "CMakeLists.txt.old")
    if os.path.exists(old_cmakelist_path):
        os.remove(old_cmakelist_path)

    os.rename(cmakelist_path, old_cmakelist_path)
    with open(old_cmakelist_path) as old_cmakelist:
        with open(cmakelist_path, "w") as cmakelist:
            for line in old_cmakelist:
                new_line = line.replace(
                    " set(HAS_LIBXSLT 1)",
                    " #set(HAS_LIBXSLT 1)",
                )

                cmakelist.write(new_line)


def remove_broken_shortcuts(python_home: str) -> None:
    """
    Remove broken Python shortcuts that depend on the absolute
    location of the Python executable.

    Note that this method will also remove scripts like
    pip, easy_install and wheel that were left around by
    previous steps of the build pipeline.

    :param str python_home: Path to the Python folder.
    :param int version: Version of the python executable.
    """
    if platform.system() == "Windows":
        # All executables inside Scripts have a hardcoded
        # absolute path to the python, which can't be relied
        # upon, so remove all scripts.
        shutil.rmtree(os.path.join(python_home, "Scripts"))
    else:
        # Aside from the python executables, every other file
        # in the build is a script that does not support
        bin_dir = os.path.join(python_home, "bin")
        for filename in os.listdir(bin_dir):
            filepath = os.path.join(bin_dir, filename)
            if filename not in [
                "python",
                "python3",
                f"python{PYTHON_VERSION}",
            ]:
                print(f"Removing {filepath}...")
                os.remove(filepath)
            else:
                print(f"Keeping {filepath}...")


def build() -> None:
    """
    Run the build step of the build. It compile every target of the project.
    """
    python_home = PYTHON_OUTPUT_DIR
    python_interpreter_args = get_python_interpreter_args(python_home, VARIANT)

    pyside_build_args = python_interpreter_args + [
        os.path.join(SOURCE_DIR, "setup.py"),
        "install",
        f"--qmake={os.path.join(QT_OUTPUT_DIR, 'bin', 'qmake' + ('.exe' if platform.system() == 'Windows' else ''))}",
        "--ignore-git",
        "--standalone",
        "--verbose-build",
        f"--parallel={os.cpu_count() or 1}",
        "--skip-docs",
    ]

    if OPENSSL_OUTPUT_DIR:
        pyside_build_args.append(f"--openssl={os.path.join(OPENSSL_OUTPUT_DIR, 'bin')}")

    # PySide2 v5.15.2.1 builds with errors on Windows using Visual Studio 2019.
    # We force Visual Studio 2017 here to make it build without errors.
    if platform.system() == "Windows":
        # Add Qt jom to the path to build in parallel
        jom_path = os.path.abspath(os.path.join(QT_OUTPUT_DIR, "..", "..", "Tools", "QtCreator", "bin", "jom"))
        if os.path.exists(os.path.join(jom_path, "jom.exe")):
            print(f"jom.exe was successfully located at: {jom_path}")
            update_env_path([jom_path])
        else:
            print(f"Could not find jom.exe at the expected location: {jom_path}")
            print("Build performance might be impacted")

        # Add the debug switch to match build type but only on Windows
        # (on other platforms, PySide2 is built in release)
        if VARIANT == "Debug":
            pyside_build_args.append("--debug")

    # On Windows, set DISTUTILS_USE_SDK so PySide2 uses the current VC environment
    # instead of trying to detect and initialize MSVC (which fails with VS 2025).
    build_env = os.environ.copy()
    if platform.system() == "Windows":
        build_env["DISTUTILS_USE_SDK"] = "1"
        build_env["MSSdk"] = "1"

        # Sanitize PATH: drop any non-Windows-style or corrupted entries that may
        # have been inherited from an MSYS2/Git-Bash parent shell.
        current_path = build_env.get("PATH", "")
        clean_entries = []
        seen = set()
        import re
        # Valid Windows path entry: starts with a drive letter like "C:\" or "D:\"
        valid_entry = re.compile(r"^[A-Za-z]:[\\/]")
        for entry in current_path.split(os.pathsep):
            entry = entry.strip()
            if not entry:
                continue
            if not valid_entry.match(entry):
                continue
            # Reject entries containing shell-like garbage (e.g., from ls -l leaking into PATH)
            if "'" in entry or "->" in entry or '"' in entry:
                continue
            key = entry.lower()
            if key in seen:
                continue
            seen.add(key)
            clean_entries.append(entry)
        build_env["PATH"] = os.pathsep.join(clean_entries)

        # Ensure MSVC tools (cl.exe, nmake.exe, link.exe) are on PATH.
        # When running as an MSBuild custom command, the VC tools may not be
        # on PATH if the environment was not fully propagated.
        import glob
        vs_base = os.environ.get("VSINSTALLDIR", "")
        if not vs_base:
            # Try to find VS installation via vswhere
            vswhere = os.path.join(
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                "Microsoft Visual Studio", "Installer", "vswhere.exe"
            )
            if os.path.exists(vswhere):
                try:
                    vs_base = subprocess.check_output(
                        [vswhere, "-latest", "-prerelease", "-property", "installationPath", "-products", "*"],
                    ).decode().strip()
                except Exception:
                    pass
        if vs_base:
            # Manually construct MSVC environment variables for VS 2025 compatibility.
            # vcvarsall.bat cannot be called from MSYS2 bash contexts.
            vc_tools_base = os.path.join(vs_base, "VC", "Tools", "MSVC")
            if os.path.isdir(vc_tools_base):
                msvc_versions = sorted(os.listdir(vc_tools_base), reverse=True)
                for msvc_ver in msvc_versions:
                    vc_bin = os.path.join(vc_tools_base, msvc_ver, "bin", "HostX64", "x64")
                    vc_include = os.path.join(vc_tools_base, msvc_ver, "include")
                    vc_lib = os.path.join(vc_tools_base, msvc_ver, "lib", "x64")
                    if os.path.isfile(os.path.join(vc_bin, "cl.exe")):
                        print(f"Setting up MSVC environment from: {vc_tools_base}/{msvc_ver}")
                        # Add VC tools to PATH
                        build_env["PATH"] = vc_bin + os.pathsep + build_env.get("PATH", "")
                        # Add INCLUDE paths
                        existing_include = build_env.get("INCLUDE", "")
                        build_env["INCLUDE"] = vc_include + (";" + existing_include if existing_include else "")
                        # Add LIB paths
                        existing_lib = build_env.get("LIB", "")
                        build_env["LIB"] = vc_lib + (";" + existing_lib if existing_lib else "")
                        # Add Windows SDK paths
                        win_sdk_root = os.environ.get("WindowsSdkDir", r"C:\Program Files (x86)\Windows Kits\10")
                        win_sdk_ver = os.environ.get("WindowsSDKVersion", "")
                        if not win_sdk_ver:
                            sdk_inc = os.path.join(win_sdk_root, "Include")
                            if os.path.isdir(sdk_inc):
                                sdk_versions = sorted(os.listdir(sdk_inc), reverse=True)
                                for sv in sdk_versions:
                                    if os.path.isdir(os.path.join(sdk_inc, sv, "ucrt")):
                                        win_sdk_ver = sv + "\\"
                                        break
                        if win_sdk_ver:
                            sv = win_sdk_ver.rstrip("\\")
                            sdk_inc_ucrt = os.path.join(win_sdk_root, "Include", sv, "ucrt")
                            sdk_inc_um = os.path.join(win_sdk_root, "Include", sv, "um")
                            sdk_inc_shared = os.path.join(win_sdk_root, "Include", sv, "shared")
                            sdk_lib_ucrt = os.path.join(win_sdk_root, "Lib", sv, "ucrt", "x64")
                            sdk_lib_um = os.path.join(win_sdk_root, "Lib", sv, "um", "x64")
                            sdk_bin = os.path.join(win_sdk_root, "bin", sv, "x64")
                            build_env["INCLUDE"] = build_env["INCLUDE"] + ";" + ";".join([sdk_inc_ucrt, sdk_inc_um, sdk_inc_shared])
                            build_env["LIB"] = build_env["LIB"] + ";" + ";".join([sdk_lib_ucrt, sdk_lib_um])
                            build_env["PATH"] = sdk_bin + os.pathsep + build_env["PATH"]
                        break

    print(f"Executing {pyside_build_args}", flush=True)
    print(f"DEBUG LLVM_INSTALL_DIR: {build_env.get('LLVM_INSTALL_DIR', '(unset)')}", flush=True)
    print(f"DEBUG CLANG_INSTALL_DIR: {build_env.get('CLANG_INSTALL_DIR', '(unset)')}", flush=True)

    # Capture output so MSBuild's buffering does not hide real errors
    log_file = os.path.join(TEMP_DIR, "pyside2_setup.log") if TEMP_DIR else "pyside2_setup.log"
    print(f"Writing PySide2 setup.py output to: {log_file}", flush=True)
    with open(log_file, "w", encoding="utf-8", errors="replace") as lf:
        proc = subprocess.run(pyside_build_args, env=build_env, stdout=lf, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        # On failure, dump the tail of the log so MSBuild shows the real error
        print(f"PySide2 setup.py FAILED with exit code {proc.returncode}", flush=True)
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as lf:
                lines = lf.readlines()
            tail = lines[-80:] if len(lines) > 80 else lines
            print("=== Last 80 lines of PySide2 setup.py log ===", flush=True)
            for line in tail:
                print(line.rstrip(), flush=True)
            print("=== End of log tail ===", flush=True)
        except Exception as e:
            print(f"Failed to read log: {e}", flush=True)
    proc.check_returncode()

    generator_cleanup_args = python_interpreter_args + [
        "-m",
        "pip",
        "uninstall",
        "-y",
        "shiboken2_generator",
    ]

    print(f"Executing {generator_cleanup_args}")
    subprocess.run(generator_cleanup_args).check_returncode()

    # Even if we remove shiboken2_generator from pip, the files stays... for some reasons
    generator_cleanup_args = python_interpreter_args + [
        "-c",
        "\n".join(
            [
                "import os, shutil",
                "try:",
                "  import shiboken2_generator",
                "except:",
                "  exit(0)",
                "shutil.rmtree(os.path.dirname(shiboken2_generator.__file__))",
            ]
        ),
    ]

    print(f"Executing {generator_cleanup_args}")
    subprocess.run(generator_cleanup_args).check_returncode()

    if OPENSSL_OUTPUT_DIR and platform.system() == "Windows":
        pyside_folder = glob.glob(os.path.join(python_home, "**", "site-packages", "PySide2"), recursive=True)[0]
        openssl_libs = glob.glob(os.path.join(OPENSSL_OUTPUT_DIR, "bin", "lib*"))

        for lib in openssl_libs:
            print(f"Copying {lib} into {pyside_folder}")
            shutil.copy(lib, pyside_folder)

    remove_broken_shortcuts(python_home)
    test_python_distribution(python_home)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--prepare", dest="prepare", action="store_true")
    parser.add_argument("--build", dest="build", action="store_true")

    parser.add_argument("--source-dir", dest="source", type=pathlib.Path, required=True)
    parser.add_argument("--python-dir", dest="python", type=pathlib.Path, required=True)
    parser.add_argument("--qt-dir", dest="qt", type=pathlib.Path, required=True)
    parser.add_argument("--openssl-dir", dest="openssl", type=pathlib.Path, required=False)
    parser.add_argument("--temp-dir", dest="temp", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", dest="output", type=pathlib.Path, required=True)

    parser.add_argument("--variant", dest="variant", type=str, required=True)

    # Major and minor version with dots.
    parser.add_argument("--python-version", dest="python_version", type=str, required=True, default="")

    parser.set_defaults(prepare=False, build=False)

    args = parser.parse_args()

    SOURCE_DIR = args.source
    OUTPUT_DIR = args.output
    TEMP_DIR = args.temp
    OPENSSL_OUTPUT_DIR = args.openssl
    PYTHON_OUTPUT_DIR = args.python
    QT_OUTPUT_DIR = args.qt
    VARIANT = args.variant
    PYTHON_VERSION = args.python_version

    print(args)

    if args.prepare:
        prepare()

    if args.build:
        build()
