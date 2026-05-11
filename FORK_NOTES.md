# Fork Notes (hiroshisaito/OpenRV-build)

このリポジトリは [AcademySoftwareFoundation/OpenRV](https://github.com/AcademySoftwareFoundation/OpenRV) のフォークです。upstream との主な差分と、利用上の注意事項を記録します。

## ProRes デコーダ：FFmpeg 内蔵版を既定で有効化 ⚠️

### 仕様

- **本フォークは `RV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE=prores` を CMake のキャッシュ変数で既定値として設定**しています（[cmake/dependencies/ffmpeg.cmake](cmake/dependencies/ffmpeg.cmake)）
- これにより FFmpeg のリバースエンジニアリングされた ProRes デコーダがビルドに含まれ、`.mov` の ProRes（codec_id 147）コンテンツがそのまま再生できます
- upstream は ProRes をデフォルトで無効化しており、再生には Apple 公式の ProRes Decoder SDK の組込み（`prores@apple.com` への申請が必要）を要求します

### ライセンス上の注意

- **Apple は FFmpeg 実装をライセンス対象としていません**。FFmpeg 内蔵 ProRes デコーダを含むビルドを **商用配布する**、または **クライアントへ納品する** 行為は、管轄によっては Apple の知的財産権を侵害する可能性があります
- 社内ワークフロー / プロダクションパイプライン内部での利用は、多くのスタジオで「低リスク」として扱われていますが、**最終的には自己責任** で判断してください
- ProRes 納品が要件のプロダクションでは、Apple SDK へ移行することを強く推奨します

### 既定の無効化方法

ProRes 内蔵デコーダを無効化する場合：

```powershell
cmake -B _build -S . -DRV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE= ...
```

### 他の non-free デコーダの追加有効化

```powershell
cmake -B _build -S . -DRV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE="prores;dnxhd;qtrle" ...
```

利用可能なリストは [cmake/dependencies/ffmpeg.cmake](cmake/dependencies/ffmpeg.cmake) の `NON_FREE_DECODERS_TO_DISABLE` を参照。

---

## Blackmagic DeckLink ランタイム互換性 ⚠️

本ビルドは **Blackmagic DeckLink SDK 16.0** に対してリンクされています。出力プラグインを使うには **Desktop Video 16.0 以降** が必要です。

| Desktop Video | 結果 |
|---|---|
| 12.5.1 以下 | ❌ 非対応 (デバイス非表示) |
| 14.2.1 | ❌ 非対応 (デバイス非表示) |
| **16.0.1** | ✅ **動作確認済**（映像 + 音声 + SDI/HDMI + UHD↔HD）|

非対応ランタイムを使うと起動ログに以下のメッセージが表示され、BMD モジュールは Output Module ドロップダウンに**意図的に出現しません**（クラッシュ防止）:

```
ERROR: BlackMagicDevices: 'DeckLink XXX' does not expose the current
       IDeckLinkOutput interface (SDK 16.0). Update Desktop Video to
       a release matching the SDK used to build OpenRV.
       Download: https://www.blackmagicdesign.com/support
```

詳細は [RELEASE_NOTES.md](RELEASE_NOTES.md) を参照。

---

## VS 2025 / VFX CY2025 ビルド対応

upstream は CY2025 へ移行済みですが、VS 2025（Visual Studio 18, MSBuild 18.4）でのビルドには追加対応が必要です。詳細は [workbench_history.md](workbench_history.md) のセッション 5 を参照。

主な追加修正：

- Boost VS 2025 bootstrap ラッパー（`cmake/dependencies/patch/boost_bootstrap_vs2025.cmake`）
- Python `python.props` v143 toolset 検出（in-tree、現状非永続）
- DAV1D で `meson setup` 構文対応（meson 1.11+）
- OCIO 2.x 1D LUT サンプラ uniform バインディング修正（`src/lib/ip/IPCore/ShaderProgram.cpp`）

## ビルド手順サマリ（Windows）

```powershell
$env:PATH = "C:\msys64\usr\bin;C:\Users\hiroshi\AppData\Roaming\Python\Python311\Scripts;" + $env:PATH
$env:RUSTUP_TOOLCHAIN = "stable-x86_64-pc-windows-msvc"
$env:CMAKE_POLICY_VERSION_MINIMUM = "3.5"
Remove-Item Env:\VIRTUAL_ENV -ErrorAction SilentlyContinue

cmake -B _build -S . -G "Visual Studio 18 2026" -A x64 `
  -DCMAKE_BUILD_TYPE=Release `
  -DRV_VFX_PLATFORM=CY2025 `
  -DCMAKE_INSTALL_PREFIX="$PWD/_install" `
  -DRV_DEPS_QT_LOCATION="C:/Qt/6.5.3/msvc2019_64" `
  -DRV_DEPS_WIN_PERL_ROOT="C:/Strawberry/perl/bin" `
  -DRV_DEPS_BMD_DECKLINK_SDK_ZIP_PATH="<path>/Blackmagic_DeckLink_SDK_<ver>.zip" `
  -DRV_PYTHON3_VERSION=3.11.9 `
  "-DGIT_EXECUTABLE=C:/Program Files/Git/bin/git.exe"

cmake --build _build --config Release --parallel 16 --target dependencies
cmake --build _build --config Release --parallel 16 --target main_executable
cmake --install _build --config Release
```

詳細は [workbench_history.md](workbench_history.md) を参照。
