# OpenRV ビルド作業履歴 (Windows 10/11)

---

## セッション 4: 2026-04-12 — OCIO Display 黒画面バグ修正 ✅

**結果:** ACES 2.0 Output Transform が GPU で正常動作。sRGB / Rec.1886 / P3 等すべての
ディスプレイで ACES 2.0 SDR/HDR ビューが正しく表示されることを確認。

### 問題

OCIO Display → ACES 2.0 系ビュー (SDR/HDR) を選択すると画面が真っ黒になる。
Raw / Un-tone-mapped は正常表示。CPU プロセッサは正常動作確認済み。

### 原因分析（シェーダーデバッグログ `d:\tmp\rv_shader_debug.log` より）

ASSIGNMENTS セクションで LUT サンプラーのバインドが `-1` になっている：

```
1 / -1 -> GPU Processor: ...|ocio_gamut_cusp_table_0Sampler ()
2 / -1 -> GPU Processor: ...|ocio_reach_m_table_0Sampler ()
```

**根本原因：OCIO 2.x GLSL グローバル uniform とバインディングの名前ミスマッチ**

OCIO 2.x が生成する GLSL の構造：
1. グローバル uniform として LUT サンプラーを宣言: `uniform sampler1D ocio_gamut_cusp_table_0Sampler;`
2. ヘルパー関数がこのグローバルを直接使用: `ocio_reach_m_table_0_sample747b830a()` 等
3. メイン OCIO 関数は引数としてサンプラーを受け取る（がヘルパーはグローバルを使う）

`shaderAddLutAsParameter()` でサンプラーをメイン OCIO 関数のパラメータに追加 →
OpenRV のシェーダーコンパイルで ハッシュサフィックス (`747b830a`) が付き
`ocio_gamut_cusp_table_0Sampler747b830a` になる → メインシェーダーで `_1` カウンタが付き
`ocio_gamut_cusp_table_0Sampler747b830a_1` としてバインドマップに登録される。

しかし OpenGL ドライバの判定：
- `ocio_gamut_cusp_table_0Sampler747b830a`（サブシェーダのグローバル）→ **有効**（ヘルパー関数が使用）
- `ocio_gamut_cusp_table_0Sampler747b830a_1`（メインシェーダ `_1` 付き）→ **無効**（パラメータとして渡されるが実際には使われない）

`Program::bind2()` で `uniformLocation("ocio_gamut_cusp_table_0Sampler747b830a_1")` → `-1`
→ バインドスキップ → LUT テクスチャが未バインド → デフォルト texture unit 0（画像）を参照
→ ACES 2.0 トーンマッピング計算が壊れ → 黒画面

### 修正内容

**ファイル:** `src/lib/ip/IPCore/ShaderProgram.cpp` — `Program::bind2()`

`uniformLocation(名前_N)` が -1 を返した場合、末尾の `_N`（数字のみ）を除いた
ベース名でも検索するフォールバックを追加。

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

- `ocio_gamut_cusp_table_0Sampler747b830a_1` → -1 → `_1` を除去 →
  `ocio_gamut_cusp_table_0Sampler747b830a` → **有効な uniform 発見** → テクスチャユニットにバインド

### 動作確認（2026-04-12）

- ビュー → OCIO Display → sRGB - Display → ACES 2.0 - SDR 100 nits (Rec.709) → **正常表示** ✅

### コミット

```
b9d9beee fix: Bind OCIO 2.x 1D LUT global sampler uniforms for ACES 2.0 GPU display
```

### 変更ファイル

- `src/lib/ip/IPCore/ShaderProgram.cpp` — フォールバック uniform 検索を追加（`#include <algorithm>` も追加）

---

## セッション 3: 2026-04-12 — Boost ラッパー強化・エンドツーエンド検証 ✅

**結果:** Boost VS 2025 ラッパーのクリーンビルド持続性テスト通過。
`cmake --build` → MSBuild → `cmd /c bootstrap.bat` のパイプライン全体を通じて
VC 環境変数のリークなしで動作することを確認。

### Boost エンドツーエンド持続性テスト

`_build/RV_DEPS_BOOST/{src,install}` と全 ExternalProject スタンプを削除し、
`cmake --build _build --config Release --target RV_DEPS_BOOST` で再ビルド。

**試行 1 — 失敗:** `'"cl"' is not recognized as an internal or external command`

- **原因:** `vcvarsall.bat`（VS 2025）は `VSCMD_VER` センチネル変数を確認する。
  MSYS2 bash → `cmake --build` → MSBuild → `cmake -P` → `cmd /c bootstrap.bat`
  という経路で呼び出した場合、親シェルの `VSCMD_VER` が継承される。
  vcvarsall.bat はセンチネルを検出して PATH/INCLUDE/LIB のセットアップを行わずに終了。
  ラッパーが PATH を最小限に絞っていたため（cl.exe なし）、build.bat がコンパイラを見つけられなかった。

**試行 2 — 失敗:** `LINK : fatal error LNK1158: cannot run 'mt.exe'`

- **原因:** センチネルを削除して cl.exe のディレクトリを PATH に事前注入した後、
  コンパイルは成功したが、b2.exe を `/MANIFEST:EMBED` でリンクする際に
  Windows SDK x64 bin ディレクトリの `mt.exe`（マニフェストツール）が必要で、
  スクラブ後の PATH に含まれていなかった。

**試行 3 — 成功:**

- Windows SDK x64 bin の自動検出を追加: ラッパーが
  `C:/Program Files (x86)/Windows Kits/10/bin/10.*/x64/mt.exe` を glob して
  バージョンが最も高い SDK ディレクトリを選択する。
- スクラブ後の最終 PATH: `<MSVC bin>;<SDK x64 bin>;C:\Windows\System32;...`
- b2.exe のリンク成功、project-config.jam に明示的な `<setup>"...vcvarsall.bat"` を書き込み、
  Boost の全 15 ライブラリをビルド・インストール完了。

### 検証

```
_build/RV_DEPS_BOOST/install/lib/  →  15 .dll + 15 .lib（30 ファイル + cmake/）
project-config.jam  →  using msvc : 14.3 : "...cl.exe" : <setup>"...vcvarsall.bat" ;
ExternalProject スタンプ  →  RV_DEPS_BOOST-complete 作成済み
```

### `boost_bootstrap_vs2025.cmake` への変更点

1. MSVC cl.exe ディレクトリをスクラブ後の PATH に事前注入（以前は欠落していた）
2. Windows SDK x64 bin（mt.exe, rc.exe）を自動検出して PATH に注入
3. vcvarsall.bat センチネル変数を削除: `VSCMD_VER`, `VSINSTALLDIR`, `VCINSTALLDIR`,
   `DevEnvDir`, `VCToolsVersion`

### コミット

```
e9ae9a79 build: Harden Boost VS 2025 bootstrap wrapper for clean environments
```

### 累積コミット一覧

```
e9ae9a79 build: Harden Boost VS 2025 bootstrap wrapper for clean environments
d7bf0827 build: Add VS 2025 environment handling for Python/PySide (VFX-CY2025)
1fdc3d5f build: Add VS 2025 bootstrap workaround for Boost (VFX-CY2025)
```

---

## セッション 2: 2026-04-11 — CY2025 ビルド完了 ✅

**結果:** OpenRV 3.1.0 を VS 2025 / VFX CY2025 環境でフルビルドに成功。
`rv.exe -version` → `3.1.0`。`cmake --install` によるインストールツリーを `_install/` に作成。

### 環境（セッション 1 から変更あり）

| コンポーネント | バージョン | パス |
|---|---|---|
| OS | Windows 10 Pro 10.0.19045 | - |
| Visual Studio | 2025 (v18.4) Community | D:\Program Files\Microsoft Visual Studio\18\Community |
| MSVC ツールチェーン | v143 14.44.35207, **14.50.35717** | VS dir/VC/Tools/MSVC/ |
| CMake | 4.2.3 | C:\Program Files\CMake\bin |
| **Python（ホスト）** | **3.11.9** | **C:\Python311** |
| **Qt** | **6.5.3 msvc2019_64** | **D:\Qt\6.5.3\msvc2019_64** |
| Rust | 1.94.0 | ~/.cargo/bin |
| Strawberry Perl | インストール済み | C:\Strawberry\perl\bin |
| MSYS2 | インストール済み | C:\msys64 |

### 判断: CY2023 → CY2025 へ切り替え

CY2023 の試みは PySide2 と VS 2025 の非互換性でブロックされた（セッション 1 参照）。
PySide2 の libclang-release_140 ベースの ApiExtractor が、VS 2025 に同梱された
Windows 10.0.26100 SDK に対して Qt 5.15 ヘッダーを解析できない。
修正には新しい libclang の導入か VS 2022 との並列インストールが必要となる。

代わりに **VFX CY2025**（OpenRV ドキュメントに実験的サポートと記載）へ切り替え：
- PySide2 → PySide6（最新ツールチェーンとの互換性が大幅に向上）
- Qt 6.5.3、Python 3.11.9、Boost 1.85.0、OCIO 2.4.2、OIIO 3.1.x、OpenEXR 3.3.x
- Qt 6.5.3 を aqtinstall で `D:\Qt\6.5.3\msvc2019_64` へインストール

### CY2025 向け CMake 再設定

```bash
cmake -B _build -G "Visual Studio 18 2026" -A x64 \
  -DCMAKE_BUILD_TYPE=Release \
  -DRV_VFX_PLATFORM=CY2025 \
  -DRV_DEPS_QT_LOCATION="D:/Qt/6.5.3/msvc2019_64" \
  -DRV_PYTHON3_VERSION=3.11.9 \
  -DRV_DEPS_WIN_PERL_ROOT="C:/Strawberry/perl/bin"
```

注: `-T v143,version=14.44` の明示指定を削除。全 CMake サブプロジェクトで
VS 2025 デフォルトツールセット（14.50）を使用。Boost のみ明示的な `<setup>` で
14.3/14.44 を継続使用（下記参照）。

### VS 2025 で発生した問題と修正

#### A. Boost bootstrap.bat — vcvarsall.bat が見つからない（b2 が失敗）

- **症状:** `b2` エラー: `don't know how to make ...HostX64\vcvarsall.bat`
- **原因:** Boost.Build の `msvc.jam` 14.3 が cl.exe の祖父ディレクトリ +
  `../../../../../Auxiliary/Build` から `vcvarsall.bat` のパスを計算する。
  VS 2025 のレイアウト（`VC/Tools/MSVC/14.44.35207/bin/HostX64/x64/cl.exe`）では
  このパス解決が正しく行われない。また `bootstrap.bat` の
  `set "VS170COMNTOOLS=...Tools\"` の末尾バックスラッシュを cmd.exe がエスケープされた
  クォートと解釈し `\Common was unexpected at this time` エラーが発生。
- **修正（_build 内、非永続）:** `_build/RV_DEPS_BOOST/src/bootstrap.bat` を直接パッチ:
  - `VS170COMNTOOLS` の値から末尾バックスラッシュを削除
  - `project-config.jam` の `using msvc : 14.3 : ...` 行に明示的な
    `<setup>"...vcvarsall.bat"` を追加
- **修正（永続化・コミット済み）:** `cmake/dependencies/patch/boost_bootstrap_vs2025.cmake`
  を追加（PATH をスクラブして VS170COMNTOOLS を正しく設定し、標準 `bootstrap.bat` を
  実行してから明示的な `<setup>` で `project-config.jam` を上書きする `cmake -P` スクリプト）。
  `cmake/dependencies/boost.cmake` が `CMAKE_GENERATOR_INSTANCE` のセグメント
  （例: `/Visual Studio/18/`）で VS 2025 以降を検出し `CONFIGURE_COMMAND` を
  ラッパー呼び出しに切り替える。VS 2022（`/2022/` セグメント）は影響なし。
- **コミット:** `1fdc3d5f build: Add VS 2025 bootstrap workaround for Boost (VFX-CY2025)`

#### B. Python/PySide6 ビルド — python3 パス、vcvarsall.bat、MAX_PATH、pip ソースビルド

- **問題 B1（python3 のパス解決が不正）:** CMake の `ADD_CUSTOM_COMMAND` が
  bare の `python3` を使用し、ビルド時に WindowsApps スタブや MSYS2 python に
  解決されてしまう。
- **修正 B1:** `cmake/dependencies/python3.cmake` で設定時に `python3` を絶対パスに解決
  （venv を優先し、次に `FIND_PROGRAM` を使用）。

- **問題 B2（DISTUTILS の vcvarsall）:** pip のネイティブ拡張ビルドが MSBuild の
  サブプロセスコンテキストから vcvarsall.bat を呼び出し、VS 2025 では失敗する。
- **修正 B2:** pip 環境に `DISTUTILS_USE_SDK=1`、`MSSdk=1` を設定。

- **問題 B3（opentimelineio の MAX_PATH 超過）:** デフォルトの `%TEMP%` 配下で
  opentimelineio の pip FileTracker tlog ファイルが MAX_PATH を超過する。
- **修正 B3:** pip 呼び出し時に `TMPDIR=TEMP=TMP=<リポジトリ>/../_rvtmp` を設定。

- **問題 B4（cffi/cryptography/pydantic のソースビルド）:** これらが
  `RV_PYTHON_WHEEL_SAFE` に含まれておらず、pip がソースコンパイルを試みるが
  VS 2025 では追加設定なしでは失敗する。
- **修正 B4:** cffi、cryptography、pydantic、pydantic-core を `RV_PYTHON_WHEEL_SAFE` に追加。

- **問題 B5（PySide6 make_pyside6.py — MSYS2 PATH の混入）:** `make_pyside6.py` が
  MSYS2 bash の PATH（Unix スタイルのエントリと壊れたトークンを含む）を継承し、
  PySide6 の shiboken サブプロセスが cl.exe/link.exe を見つけられなくなる。
- **修正 B5:** `src/build/make_pyside6.py` でクリーンな `build_env` を構築:
  Windows スタイル以外の PATH エントリを除去し、vswhere で VS インストールを検出して
  MSVC + Windows SDK の `INCLUDE`、`LIB`、`PATH` を手動設定。
  `src/build/make_pyside.py`（CY2023/PySide2 パス）にも同様の処理を適用。

- **コミット:** `d7bf0827 build: Add VS 2025 environment handling for Python/PySide (VFX-CY2025)`

### ビルドコマンド（CY2025 で成功）

```bash
# 1. サードパーティ依存関係 28 本をビルド
cmake --build _build --config Release --parallel 16 --target dependencies

# 2. rv.exe をビルド
cmake --build _build --config Release --parallel 16 --target main_executable

# 3. インストールツリーを作成
cmake --install _build --prefix "D:/GitHub/OpenRV_mdk-build/_install" --config Release
```

### ビルド完了済み依存関係（CY2025）

`_build/cmake/dependencies/CMakeFiles/Release/` に全 28 個の ExternalProject スタンプが存在:

| 依存関係 | バージョン |
|---|---|
| AJA | 17.6.0 |
| Atomic Ops | — |
| Boost | 1.85.0（15 ライブラリ）|
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
| **Python3** | **3.11.9**（94 ライブラリ + フル requirements）|
| **PySide6** | **6.5.3**（30 .pyd ファイル）|
| PYIMGUI / PYIMPLOT | — |
| libraw | — |
| spdlog | — |
| TIFF | — |
| WebP | — |
| YAML-CPP | — |

### ビルド成果物

| 成果物 | パス | 備考 |
|---|---|---|
| `rv.exe` | `_build/stage/app/bin/rv.exe` | 13 MB |
| `rvio.exe` 等 | `_build/stage/app/bin/` | rv ツール全 7 本 |
| インストールツリー | `_install/` | bin, lib, DLL, PlugIns, scripts, translations |

**スモークテスト（2026-04-11）:**
- `rv.exe -version` → `3.1.0` ✅
- `rvio smoke_in.png -o smoke_out.exr` → 512×512 16f EXR、174 KB ✅
- `rvio smoke_out.exr -o smoke_round.jpg` → ラウンドトリップ OK ✅
- `rv.exe -pyeval "from rv import commands; print(commands.frame())"` → `1` ✅
  （Python + PySide6 + rv.commands C++ ブリッジすべて正常動作）
- MediaLibrary プラグイン読み込み、AJADevices.dll ロード、OIIO 画像読み込み ✅

### コミット

```
d7bf0827 build: Add VS 2025 environment handling for Python/PySide (VFX-CY2025)
1fdc3d5f build: Add VS 2025 bootstrap workaround for Boost (VFX-CY2025)
```

変更ファイル（リポジトリソースツリー）:
- `cmake/dependencies/boost.cmake` — VS 2025 検出 + 条件付き CONFIGURE_COMMAND
- `cmake/dependencies/patch/boost_bootstrap_vs2025.cmake` — 新規ラッパースクリプト（b2 bootstrap）
- `cmake/dependencies/python3.cmake` — ホスト python 解決、DISTUTILS_USE_SDK、短い TMPDIR、wheel-safe リスト
- `src/build/make_pyside6.py` — クリーン build_env、vswhere ベースの VC/SDK 注入
- `src/build/make_pyside.py` — 同上（CY2023/PySide2 パス用）

---

## セッション 1 アーカイブ: 2026-04-10 — CY2023 試行（PySide2 でブロック）

### 環境（セッション 1）

| コンポーネント | バージョン | パス |
|---|---|---|
| OS | Windows 10 Pro 10.0.19045 | - |
| Visual Studio | 2025 (v18.4) Community | D:\Program Files\Microsoft Visual Studio\18\Community |
| MSVC ツールチェーン | v143 14.44.35207, 14.50.35717 | VS dir/VC/Tools/MSVC/ |
| CMake | 4.2.3 | C:\Program Files\CMake\bin |
| Python（ホスト）| 3.10.10 | C:\Users\hiroshi\AppData\Local\Programs\Python\Python310 |
| Qt | 5.15.2 msvc2019_64 | C:\Qt\5.15.2\msvc2019_64 |
| Rust | 1.94.0 | ~/.cargo/bin |
| Strawberry Perl | インストール済み | C:\Strawberry\perl\bin |
| MSYS2 | インストール済み | C:\msys64 |

CMake 設定コマンド:
```bash
cmake -B _build -G "Visual Studio 18 2026" -T v143,version=14.44 -A x64 \
  -DCMAKE_BUILD_TYPE=Release \
  -DRV_DEPS_QT_LOCATION="C:/Qt/5.15.2/msvc2019_64" \
  -DRV_VFX_PLATFORM=CY2023 \
  -DRV_DEPS_WIN_PERL_ROOT="c:/Strawberry/perl/bin"
```

### CY2023 試行中に発生した問題と修正

- **CMake ジェネレーター:** `"Visual Studio 18 2026" -T v143,version=14.44` に変更。
- **Python 3.10 MSBuild v140 エラー:** `_build/RV_DEPS_PYTHON3/src/PCbuild/python.props` に
  `VisualStudioVersion == 18.0 → v143` の条件を追加。
- **Python 要件（cffi、opentimelineio、numpy）:** DISTUTILS_USE_SDK / 短い TMPDIR /
  wheel-safe リストの修正は CY2025 のコミットに統合済み。
- **Boost bootstrap.bat:** `call build.bat vc143` をインプレースでパッチ（非永続）。
- **PySide2 jom:** jom 1.1.4 を `tools/jom/` と
  `C:\Qt\Tools\QtCreator\bin\jom\jom.exe` にインストール。
- **PySide2 `init_msvc_env`:** `_build/_deps/rv_deps_pyside2-src/build_scripts/utils.py` を
  `DISTUTILS_USE_SDK` が設定されている場合に早期 return するようパッチ。
- **PySide2 cmake_minimum_required:** ネストされた CMakeLists.txt 9 ファイルを
  3.1 → 3.5 に変更（CMake 4 が 3.5 未満との互換性を廃止したため）。

### CY2023 のブロック要因（切り替えの理由）

上記すべてのパッチ適用後、`shiboken2` 自体のビルドとリンクは成功したが、
各 Qt モジュールのモジュール別 ApiExtractor コード生成ステップがクラッシュ:

```
shiboken: Error running ApiExtractor.
--generator-set=shiboken ... QtHelp_global.h
--include-paths=.../Qt/5.15.2/msvc2019_64/include/...
```

PySide2 に同梱されたビルド済み
`libclang-release_140-based-windows-vs2019_64.7z` が古すぎて、
VS 2025 に同梱された Windows 10.0.26100 SDK に対して Qt 5.15 ヘッダーを解析できない。
根本的な修正には以下のいずれかが必要:
- 新しい libclang（release_160 または _170）
- VS 2022 v14.40 の VS 2025 との並列インストール
- **→ 選択肢 C: CY2025 + PySide6 へ切り替え**（セッション 2 参照）

### ローカルツール（セッション 1）

- `tools/jom/jom.exe` — jom 1.1.4（Qt の期待するパスにもコピー済み）
- `tools/llvm/` — ApiExtractor クラッシュ調査中に収集した libclang 関連ファイル
