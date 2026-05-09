# OpenRV 3.2.0 UAT チェックリスト

**ビルド情報**
- バージョン: 3.2.0 (CY2025 / VFX2025)
- ベースコミット: `767a49b9`（main）
- ビルド環境: Windows 11, VS 2025 (v18.4), CMake 4.2.3, Qt 6.5.3, Python 3.11.9
- 同梱プラグイン: AJADevices.dll, BlackMagicDevices.dll
- パッケージ: `D:/tmp/OpenRV-3.2.0-CY2025-win64-AJA-BMD-20260509-767a49b9.zip` (380.6 MB)

---

## 1. 基本起動・スタンドアロン動作

- [ ] zip を任意のディレクトリに展開（例: `C:\OpenRV-3.2.0\`）
- [ ] `bin\rv.exe` をダブルクリックで起動
- [ ] スプラッシュ表示後、メインウィンドウが開く
- [ ] `rv.exe -version` で `3.2.0` を確認
- [ ] `rv.exe -help` でコマンドオプション一覧が表示される
- [ ] **環境変数なしで動作する**（PYTHONHOME / PYTHONPATH 不要）

## 2. メディア再生

- [ ] 静止画 (PNG, JPG, EXR, TIFF) を読み込んで表示
- [ ] EXR シーケンス（マルチチャンネル含む）の再生
- [ ] H.264 mp4 / MOV 動画の再生（FFmpeg 経由）
- [ ] **ProRes** がデコードできるか（FFmpeg 経由、Apple SDK 無し）
- [ ] **DAV1D による AV1** の再生
- [ ] **OpenJPEG / OpenJPH** による J2K / JPEG-XS の再生
- [ ] 音声付き動画の再生 + 音声同期

## 3. AJA 出力プラグイン（実機があれば）

- [ ] File → Preferences → Video で **AJA Kona / Io** デバイス選択肢が出現
- [ ] 出力デバイスを選択して再生 → 外部モニタに映像出力
- [ ] **3G/6G/12G SDI** のリンク選択（Kona 5 持っていれば）
- [ ] 解像度 / フレームレート（24, 25, 29.97, 30, 50, 59.94, 60）切替

## 4. Blackmagic Decklink 出力プラグイン（実機があれば）

- [ ] File → Preferences → Video で **BlackmagicDesign** デバイス選択肢が出現
- [ ] Decklink から外部モニタへの映像出力
- [ ] SDI / HDMI 切替
- [ ] フォーマット切替が反映される

## 5. OCIO カラーマネジメント（重要：セッション 4 のリグレッション確認）

- [ ] View → OCIO Display → sRGB - Display → **ACES 2.0 - SDR 100 nits (Rec.709)** で **黒画面にならない** ✅
- [ ] ACES 2.0 - HDR 1000 nits (Rec.2020) などのバリエーション
- [ ] Raw / Un-tone-mapped で問題ないこと
- [ ] OCIO config 切替が即座に反映される

## 6. Qt / GUI

- [ ] **Qt WebEngine** が動作する（ヘルプ / Web ベース UI 要素）
- [ ] Session Manager の表示・操作
- [ ] タイムライン操作（in/out, ブックマーク, アノテーション）
- [ ] フル画面モード切替
- [ ] マルチモニタでの表示

## 7. Python / Mu スクリプティング

- [ ] `rv.exe -pyeval "from rv import commands; print(commands.frame())"` (GUI なしで Python 実行モード — 値が返る)
- [ ] PySide6 ベースの Python パッケージ機能（File → Packages）
- [ ] サンプル `.rvpkg` のインストールと有効化

## 8. RV ツール群

- [ ] `bin\rvio.exe -version` → 3.2.0
- [ ] `rvio input.exr -o output.jpg` で変換
- [ ] `rvio input.mov -t in:out -o clip.mp4` でトリム
- [ ] `bin\rvls.exe`、`bin\rvpush.exe` などその他ツールの起動確認

## 9. パフォーマンス / 安定性

- [ ] 4K EXR を 30 秒以上連続再生でメモリリーク無し（タスクマネージャ確認）
- [ ] GPU 使用率が再生中に上がる（Intel/NVIDIA GPU で OpenGL レンダリング）
- [ ] 5 分間操作してクラッシュしない
- [ ] セッションファイル (.rv) の保存・読み込み

## 10. プラグイン読み込み確認

- [ ] 起動時に AJADevices.dll が読み込まれる（Console / `--debug video`）
- [ ] BlackMagicDevices.dll が読み込まれる
- [ ] OIIO 画像フォーマットプラグインが正常ロード（PNG/EXR/TIFF/JPEG/RAW）

---

## 推奨優先順位

1. **必須**: §1, §2 基本動作 / §5 OCIO ACES 2.0（黒画面リグレッション）
2. **重要**: §3 AJA / §4 Blackmagic（今回有効化した目玉機能）
3. **任意**: §7 Python / §9 パフォーマンス / §6 GUI 細部

## 不具合発見時のフロー

1. 再現手順を本ファイルに追記（`### 不具合 - <タイトル>` セクション）
2. main ブランチで修正コミット
3. `cmake --build _build --config Release --target main_executable`（差分のみ再ビルド）
4. `cmake --install _build --config Release`
5. 新しい zip パッケージを作成

差分の起点コミット範囲: `fe403976`（v3.1.0）〜 `767a49b9`（v3.2.0）

---

## 不具合・改善要望ログ

<!-- ここに UAT で発見した問題を記録 -->
