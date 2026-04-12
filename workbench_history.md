# OpenRV Build Workbench History (Windows 10/11)

---

## Session 4: 2026-04-12 — OCIO Display 黒画面バグ修正 ✅

**Result:** ACES 2.0 Output Transform が GPU で正常動作。sRGB / Rec.1886 / P3 等すべての display で
ACES 2.0 SDR/HDR ビューが正しく表示されることを確認。

### 問題
OCIO Display → ACES 2.0 系ビュー (SDR/HDR) を選択すると画面が真っ黒になる。
Raw / Un-tone-mapped は正常表示。CPU プロセッサは正常動作確認済み。

### 原因分析 (シェーダーデバッグログ `d:\tmp\rv_shader_debug.log` より)

ASSIGNMENTS セクションで LUT サンプラーのバインドが `-1` になっている：
```
1 / -1 -> GPU Processor: ...|ocio_gamut_cusp_table_0Sampler ()
2 / -1 -> GPU Processor: ...|ocio_reach_m_table_0Sampler ()
```

**根本原因：OCIO 2.x GLSL グローバル uniform とバインディングの名前ミスマッチ**

OCIO 2.x が生成する GLSL は：
1. グローバル uniform として LUT サンプラーを宣言: `uniform sampler1D ocio_gamut_cusp_table_0Sampler;`
2. ヘルパー関数がこのグローバルを直接使用: `ocio_reach_m_table_0_sample747b830a()` 等
3. メイン OCIO 関数は引数としてサンプラーを受け取る（が、ヘルパーはグローバルを使う）

`shaderAddLutAsParameter()` でサンプラーをメイン OCIO 関数のパラメータに追加→ OpenRV の
シェーダーコンパイルで hash suffix (`747b830a`) が付き `ocio_gamut_cusp_table_0Sampler747b830a`
になる → メインシェーダーで `_1` カウンタが付き `ocio_gamut_cusp_table_0Sampler747b830a_1`
としてバインドマップに登録される。

しかし OpenGL ドライバが判定：
- `ocio_gamut_cusp_table_0Sampler747b830a` (サブシェーダのグローバル) → **ACTIVE** (ヘルパー関数が使用)
- `ocio_gamut_cusp_table_0Sampler747b830a_1` (メインシェーダ `_1` 付き) → **NOT ACTIVE** (パラメータとして渡されるが実際には使われない)

`Program::bind2()` で `uniformLocation("ocio_gamut_cusp_table_0Sampler747b830a_1")` → `-1`
→ バインドスキップ → LUT テクスチャが未バインド → デフォルト texture unit 0 (画像) を参照
→ ACES 2.0 トーンマッピング計算が壊れ → 黒画面

### 修正内容

**ファイル:** `src/lib/ip/IPCore/ShaderProgram.cpp` — `Program::bind2()`

`uniformLocation(name_with_N_suffix)` が -1 を返した場合、末尾の `_N`（数字のみ）を
除いたベース名でも検索するフォールバックを追加。

```cpp
if (location == -1)
{
    size_t lastUnderscore = name.rfind('_');
    if (lastUnderscore != string::npos && lastUnderscore + 1 < name.size())
    {
        const string suffix = name.substr(lastUnderscore + 1);
        bool allDigits = !suffix.empty() && std::all_of(suffix.begin(), suffix.end(), ::isdigit);
        if (allDigits)
        {
            string baseName = name.substr(0, lastUnderscore);
            location = uniformLocation(baseName);
        }
    }
}
```

- `ocio_gamut_cusp_table_0Sampler747b830a_1` → -1 → strip `_1` →
  `ocio_gamut_cusp_table_0Sampler747b830a` → **ACTIVE uniform 発見** → テクスチャユニットにバインド

### 動作確認 (2026-04-12)

- View → OCIO Display → sRGB - Display → ACES 2.0 - SDR 100 nits (Rec.709) → **正常表示** ✅

### Commit

```
fix: Bind OCIO 2.x 1D LUT global sampler uniforms for ACES 2.0 GPU display
```

### 変更ファイル

- `src/lib/ip/IPCore/ShaderProgram.cpp` — fallback uniform lookup (+ `#include <algorithm>`)

---

## Session 3: 2026-04-12 — Boost wrapper hardened + end-to-end verified ✅

**Result:** Clean-rebuild persistence test of Boost VS 2025 wrapper passed.
Wrapper now survives the full `cmake --build` → MSBuild → `cmd /c bootstrap.bat`
pipeline without leaked VC environment variables.

### Boost end-to-end persistence test

Wiped `_build/RV_DEPS_BOOST/{src,install}` + all ExternalProject stamps, then
rebuilt via `cmake --build _build --config Release --target RV_DEPS_BOOST`.

**Attempt 1 — FAILED:** `'"cl"' is not recognized as an internal or external command`

- **Root cause:** `vcvarsall.bat` (VS 2025) checks the `VSCMD_VER` sentinel variable.
  When invoked via MSYS2 bash → `cmake --build` → MSBuild → `cmake -P` → `cmd /c
  bootstrap.bat`, the parent shell's `VSCMD_VER` was inherited. vcvarsall.bat saw
  the sentinel and exited early without setting up PATH/INCLUDE/LIB. Since the wrapper
  had already scrubbed PATH to a minimal set (no cl.exe), build.bat could not find
  the compiler.

**Attempt 2 — FAILED:** `LINK : fatal error LNK1158: cannot run 'mt.exe'`

- **Root cause:** After clearing the sentinels and pre-injecting cl.exe's directory
  into PATH, compilation succeeded but linking b2.exe with `/MANIFEST:EMBED` required
  `mt.exe` (Manifest Tool) from the Windows SDK x64 bin directory, which was not on
  the scrubbed PATH.

**Attempt 3 — PASSED:**

- Added Windows SDK x64 bin auto-detection: the wrapper now globs
  `C:/Program Files (x86)/Windows Kits/10/bin/10.*/x64/mt.exe` and picks the
  highest-versioned SDK directory.
- Final scrubbed PATH: `<MSVC bin>;<SDK x64 bin>;C:\Windows\System32;...`
- b2.exe linked successfully, project-config.jam overwritten with explicit
  `<setup>"...vcvarsall.bat"`, all 15 Boost libs built and installed.

### Verification

```
_build/RV_DEPS_BOOST/install/lib/  →  15 .dll + 15 .lib (30 files + cmake/)
project-config.jam  →  using msvc : 14.3 : "...cl.exe" : <setup>"...vcvarsall.bat" ;
ExternalProject stamp  →  RV_DEPS_BOOST-complete created
```

### Changes to `boost_bootstrap_vs2025.cmake`

1. Pre-inject MSVC cl.exe directory into scrubbed PATH (was missing before)
2. Auto-detect and inject Windows SDK x64 bin (mt.exe, rc.exe) into scrubbed PATH
3. Clear vcvarsall.bat sentinels: `VSCMD_VER`, `VSINSTALLDIR`, `VCINSTALLDIR`,
   `DevEnvDir`, `VCToolsVersion`

### Commit

```
e9ae9a79 build: Harden Boost VS 2025 bootstrap wrapper for clean environments
```

### All commits (cumulative)

```
e9ae9a79 build: Harden Boost VS 2025 bootstrap wrapper for clean environments
d7bf0827 build: Add VS 2025 environment handling for Python/PySide (VFX-CY2025)
1fdc3d5f build: Add VS 2025 bootstrap workaround for Boost (VFX-CY2025)
```

---

## Session 2: 2026-04-11 — CY2025 build COMPLETED ✅

**Result:** Full successful build of OpenRV 3.1.0 on VS 2025 / VFX CY2025.  
`rv.exe -version` → `3.1.0`. `cmake --install` install tree at `_install/`.

### Environment (changed from Session 1)

| Component | Version | Path |
|---|---|---|
| OS | Windows 10 Pro 10.0.19045 | - |
| Visual Studio | 2025 (v18.4) Community | D:\Program Files\Microsoft Visual Studio\18\Community |
| MSVC Toolchains | v143 14.44.35207, **14.50.35717** | VS dir/VC/Tools/MSVC/ |
| CMake | 4.2.3 | C:\Program Files\CMake\bin |
| **Python (host)** | **3.11.9** | **C:\Python311** |
| **Qt** | **6.5.3 msvc2019_64** | **D:\Qt\6.5.3\msvc2019_64** |
| Rust | 1.94.0 | ~/.cargo/bin |
| Strawberry Perl | installed | C:\Strawberry\perl\bin |
| MSYS2 | installed | C:\msys64 |

### Decision: Switch CY2023 → CY2025

The CY2023 attempt was blocked on PySide2 + VS 2025 incompatibility (see Session 1
archive below). PySide2's libclang-release_140-based ApiExtractor fails to parse Qt 5.15
headers against the Windows 10.0.26100 SDK bundled with VS 2025. The fix would require
shipping a newer libclang or running VS 2022 side-by-side.

Instead switched to **VFX CY2025** (experimentally supported per OpenRV docs):
- PySide6 replaces PySide2 — far more compatible with modern toolchains
- Qt 6.5.3, Python 3.11.9, Boost 1.85.0, OCIO 2.4.2, OIIO 3.1.x, OpenEXR 3.3.x
- Installed Qt 6.5.3 via aqtinstall to `D:\Qt\6.5.3\msvc2019_64`

### CMake reconfigure for CY2025

```bash
cmake -B _build -G "Visual Studio 18 2026" -A x64 \
  -DCMAKE_BUILD_TYPE=Release \
  -DRV_VFX_PLATFORM=CY2025 \
  -DRV_DEPS_QT_LOCATION="D:/Qt/6.5.3/msvc2019_64" \
  -DRV_PYTHON3_VERSION=3.11.9 \
  -DRV_DEPS_WIN_PERL_ROOT="C:/Strawberry/perl/bin"
```

Note: dropped explicit `-T v143,version=14.44` — VS 2025 default toolset (14.50) used
by all CMake sub-projects. Boost still uses 14.3/14.44 via explicit `<setup>` (see below).

### VS 2025 problems encountered and fixes

#### A. Boost bootstrap.bat — vcvarsall.bat not found (b2 fails)

- **Symptom:** `b2` errors: `don't know how to make ...HostX64\vcvarsall.bat`
- **Root cause:** Boost.Build's `msvc.jam` 14.3 computes `vcvarsall.bat` path from
  cl.exe's grandparent + `../../../../../Auxiliary/Build`. For the VS 2025 layout
  (`VC/Tools/MSVC/14.44.35207/bin/HostX64/x64/cl.exe`) this resolves wrongly.
  Additionally `bootstrap.bat`'s `set "VS170COMNTOOLS=...Tools\"` had a trailing
  backslash that cmd.exe parsed as an escaped quote → `\Common was unexpected at this time`.
- **Fix (in _build, not persisted):** Patched `_build/RV_DEPS_BOOST/src/bootstrap.bat`:
  - Removed trailing backslash from `VS170COMNTOOLS` value
  - Added explicit `<setup>"...vcvarsall.bat"` to the `using msvc : 14.3 : ...` line in `project-config.jam`
- **Fix (persisted — committed):** Added `cmake/dependencies/patch/boost_bootstrap_vs2025.cmake`
  (a `cmake -P` script that scrubs PATH, sets VS170COMNTOOLS correctly, runs stock
  `bootstrap.bat`, then overwrites `project-config.jam` with explicit `<setup>`).
  `cmake/dependencies/boost.cmake` now detects VS 2025+ by `CMAKE_GENERATOR_INSTANCE`
  segment (e.g. `/Visual Studio/18/`) and swaps `CONFIGURE_COMMAND` to invoke the
  wrapper. VS 2022 (`/2022/` segment) is unaffected.
- **Commit:** `1fdc3d5f build: Add VS 2025 bootstrap workaround for Boost (VFX-CY2025)`

#### B. Python/PySide6 build — wrong python3, vcvarsall.bat, MAX_PATH, pip source builds

- **Problem B1 (wrong python):** CMake `ADD_CUSTOM_COMMAND` used bare `python3`,
  resolved at build time to WindowsApps stub or MSYS2 python instead of venv.
- **Fix B1:** `cmake/dependencies/python3.cmake` now resolves `python3` absolutely at
  configure time (venv first, then `FIND_PROGRAM`).

- **Problem B2 (DISTUTILS vcvarsall):** `pip` native-extension builds call
  vcvarsall.bat from the MSBuild subprocess context, which fails on VS 2025.
- **Fix B2:** Set `DISTUTILS_USE_SDK=1`, `MSSdk=1` in pip environment.

- **Problem B3 (MAX_PATH with opentimelineio):** pip's FileTracker tlog files for
  opentimelineio exceed MAX_PATH under the default `%TEMP%`.
- **Fix B3:** Set `TMPDIR=TEMP=TMP=<repo>/../_rvtmp` for pip invocations.

- **Problem B4 (cffi/cryptography/pydantic built from source):** These were not in
  `RV_PYTHON_WHEEL_SAFE`, so pip compiled them — which fails on VS 2025 without
  extra setup.
- **Fix B4:** Added cffi, cryptography, pydantic, pydantic-core to `RV_PYTHON_WHEEL_SAFE`.

- **Problem B5 (PySide6 make_pyside6.py — MSYS2 PATH leakage):** `make_pyside6.py`
  inherited MSYS2 bash's PATH with Unix-style entries and corrupted tokens, preventing
  cl.exe/link.exe lookup by PySide6's shiboken subprocess.
- **Fix B5:** `src/build/make_pyside6.py` now builds a clean `build_env`:
  scrubs non-Windows-style PATH entries, vswhere-detects VS install, manually sets
  `INCLUDE`, `LIB`, `PATH` for MSVC + Windows SDK.
  Same treatment applied to `src/build/make_pyside.py` (CY2023 path, same logic).

- **Commit:** `d7bf0827 build: Add VS 2025 environment handling for Python/PySide (VFX-CY2025)`

### Build commands (CY2025 succeeded)

```bash
# 1. Build all 28 third-party dependencies
cmake --build _build --config Release --parallel 16 --target dependencies

# 2. Build rv.exe
cmake --build _build --config Release --parallel 16 --target main_executable

# 3. Create install tree
cmake --install _build --prefix "D:/GitHub/OpenRV_mdk-build/_install" --config Release
```

### Completed dependencies (CY2025)

All 28 ExternalProject stamps present in `_build/cmake/dependencies/CMakeFiles/Release/`:

| Dep | Version |
|---|---|
| AJA | 17.6.0 |
| Atomic Ops | — |
| Boost | 1.85.0 (15 libs) |
| Dav1d | 1.4.3 |
| Doctest | — |
| Expat | 2.6.3 |
| FFmpeg | 7.1 |
| GC | — |
| GLEW | — |
| Imath | 3.1.12 |
| imgui | bundle 2025-03-23 |
| JPEGTURBO | — |
| Nanobind | — |
| OCIO | 2.4.2 |
| OIIO | 3.1.x |
| OpenEXR | 3.3.x |
| OpenJPEG | — |
| OpenJPH | — |
| OpenSSL | 3.4.x |
| PCRE2 | — |
| PNG | — |
| **Python3** | **3.11.9** (94 libs + full requirements) |
| **PySide6** | **6.5.3** (30 .pyd files) |
| PYIMGUI / PYIMPLOT | — |
| libraw | — |
| spdlog | — |
| TIFF | — |
| WebP | — |
| YAML-CPP | — |

### Build artifacts

| Artifact | Path | Notes |
|---|---|---|
| `rv.exe` | `_build/stage/app/bin/rv.exe` | 13 MB |
| `rvio.exe` etc. | `_build/stage/app/bin/` | All 7 rv tools |
| Install tree | `_install/` | bin, lib, DLLs, PlugIns, scripts, translations |

**Smoke tests (2026-04-11):**
- `rv.exe -version` → `3.1.0` ✅
- `rvio smoke_in.png -o smoke_out.exr` → 512×512 16f EXR, 174 KB ✅
- `rvio smoke_out.exr -o smoke_round.jpg` → round-trip OK ✅
- `rv.exe -pyeval "from rv import commands; print(commands.frame())"` → `1` ✅
  (Python + PySide6 + rv.commands C++ bridge all live)
- MediaLibrary plugins imported, AJADevices.dll loaded, OIIO reads image ✅

### Commits

```
d7bf0827 build: Add VS 2025 environment handling for Python/PySide (VFX-CY2025)
1fdc3d5f build: Add VS 2025 bootstrap workaround for Boost (VFX-CY2025)
```

Files changed (repo source tree):
- `cmake/dependencies/boost.cmake` — VS 2025 detection + conditional CONFIGURE_COMMAND
- `cmake/dependencies/patch/boost_bootstrap_vs2025.cmake` — new wrapper script (b2 bootstrap)
- `cmake/dependencies/python3.cmake` — host python resolution, DISTUTILS_USE_SDK, short TMPDIR, wheel-safe list
- `src/build/make_pyside6.py` — clean build_env, vswhere-based VC/SDK injection
- `src/build/make_pyside.py` — same, for CY2023/PySide2 path

---

## Session 1 archive: 2026-04-10 — CY2023 attempt (BLOCKED on PySide2)

### Environment (Session 1)

| Component | Version | Path |
|---|---|---|
| OS | Windows 10 Pro 10.0.19045 | - |
| Visual Studio | 2025 (v18.4) Community | D:\Program Files\Microsoft Visual Studio\18\Community |
| MSVC Toolchains | v143 14.44.35207, 14.50.35717 | VS dir/VC/Tools/MSVC/ |
| CMake | 4.2.3 | C:\Program Files\CMake\bin |
| Python (host) | 3.10.10 | C:\Users\hiroshi\AppData\Local\Programs\Python\Python310 |
| Qt | 5.15.2 msvc2019_64 | C:\Qt\5.15.2\msvc2019_64 |
| Rust | 1.94.0 | ~/.cargo/bin |
| Strawberry Perl | installed | C:\Strawberry\perl\bin |
| MSYS2 | installed | C:\msys64 |

CMake configure:
```bash
cmake -B _build -G "Visual Studio 18 2026" -T v143,version=14.44 -A x64 \
  -DCMAKE_BUILD_TYPE=Release \
  -DRV_DEPS_QT_LOCATION="C:/Qt/5.15.2/msvc2019_64" \
  -DRV_VFX_PLATFORM=CY2023 \
  -DRV_DEPS_WIN_PERL_ROOT="c:/Strawberry/perl/bin"
```

### Problems hit and fixed during CY2023 attempt

- **CMake generator:** Overrode to `"Visual Studio 18 2026" -T v143,version=14.44`.
- **Python 3.10 MSBuild v140 error:** Added `VisualStudioVersion == 18.0 → v143` condition
  to `_build/RV_DEPS_PYTHON3/src/PCbuild/python.props`.
- **Python requirements (cffi, opentimelineio, numpy):** Same DISTUTILS_USE_SDK / short
  TMPDIR / wheel-safe list fixes now captured in the CY2025 commits above.
- **Boost bootstrap.bat:** Patched `call build.bat vc143` (in-place, not persisted).
- **PySide2 jom:** Installed jom 1.1.4 to `tools/jom/` and
  `C:\Qt\Tools\QtCreator\bin\jom\jom.exe`.
- **PySide2 `init_msvc_env`:** Patched `_build/_deps/rv_deps_pyside2-src/build_scripts/utils.py`
  to return early when `DISTUTILS_USE_SDK` is set.
- **PySide2 cmake_minimum_required:** Patched 9 nested CMakeLists.txt from 3.1 → 3.5
  (CMake 4 dropped compatibility with < 3.5).

### CY2023 blocker (reason for switching)

After all the above patches, `shiboken2` itself built and linked, but the per-module
ApiExtractor code-generation step crashed for every Qt module:

```
shiboken: Error running ApiExtractor.
--generator-set=shiboken ... QtHelp_global.h
--include-paths=.../Qt/5.15.2/msvc2019_64/include/...
```

The pre-built `libclang-release_140-based-windows-vs2019_64.7z` (bundled with PySide2)
is too old to parse Qt 5.15 headers against the Windows 10.0.26100 SDK shipped with
VS 2025. No straightforward fix without either:
- A newer libclang (release_160 or _170)
- VS 2022 v14.40 side-by-side with VS 2025
- **→ Chose Option C: switch to CY2025 + PySide6** (see Session 2 above)

### Local tools (Session 1)

- `tools/jom/jom.exe` — jom 1.1.4 (also copied to Qt's expected path)
- `tools/llvm/` — libclang bits accumulated while investigating the ApiExtractor crash
