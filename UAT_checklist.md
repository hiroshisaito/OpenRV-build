# OpenRV 3.2.0 UAT チェックリスト

**ビルド情報**

* バージョン: 3.2.0 (CY2025 / VFX2025)

* ベースコミット: `767a49b9`（main）

* ビルド環境: Windows 11, VS 2025 (v18.4), CMake 4.2.3, Qt 6.5.3, Python 3.11.9

* 同梱プラグイン: AJADevices.dll, BlackMagicDevices.dll

* パッケージ: `D:/tmp/OpenRV-3.2.0-CY2025-win64-AJA-BMD-ProRes-20260511-402e71c9.zip` (BMD IID フォールバック修正後の最終版)

***

## 1. 基本起動・スタンドアロン動作 ✅ PASS (2026-05-09)

* [x] zip を任意のディレクトリに展開（例: `C:\OpenRV-3.2.0\`）

* [x] `bin\rv.exe` をダブルクリックで起動

* [x] メインウィンドウが開く ※スプラッシュ画面は表示されない（仕様）

* [x] `rv.exe -version` で `3.2.0` を確認

* [x] `rv.exe -help` でコマンドオプション一覧が表示される

* [x] **環境変数なしで動作する**（PYTHONHOME / PYTHONPATH 不要）

## 2. メディア再生 ⚠️ 部分 PASS (2026-05-09)

* [x] 静止画 (PNG, JPG, EXR, TIFF) を読み込んで表示 — **PASS**

* [x] EXR シーケンス（マルチチャンネル含む）の再生 — **PASS**

* [x] H.264 mp4 / MOV 動画の再生（FFmpeg 経由） — **PASS**

* [x] **ProRes** がデコードできるか（FFmpeg 経由、Apple SDK 無し） — **PASS** (commit `56728fb7` で FFmpeg ProRes デコーダを既定有効化、commit `402e71c9` 以降に同梱)

* [ ] **DAV1D による AV1** の再生 — **DEFERRED**（テストメディア準備中）

* [ ] **OpenJPEG / OpenJPH** による J2K / JPEG-XS の再生 — **DEFERRED**（テストメディア準備中）

* [ ] 音声付き動画の再生 + 音声同期

## 3. AJA 出力プラグイン（実機があれば）⏸ DEFERRED (2026-05-09)

実機が現状ないため UAT は保留。プラグイン DLL のロード自体は §10 で確認する。

* [ ] File → Preferences → Video で **AJA Kona / Io** デバイス選択肢が出現

* [ ] 出力デバイスを選択して再生 → 外部モニタに映像出力

* [ ] **3G/6G/12G SDI** のリンク選択（Kona 5 持っていれば）

* [ ] 解像度 / フレームレート（24, 25, 29.97, 30, 50, 59.94, 60）切替

## 4. Blackmagic Decklink 出力プラグイン (DeckLink 4K Pro + DV 16.0.1) ✅ PASS (2026-05-11)

* [x] File → Preferences → Video → Output Module に **BlackMagic** が出現 — **PASS**

* [x] DeckLink から外部モニタへの映像出力 — **PASS**

* [x] **音声出力** — **PASS**

* [x] SDI / HDMI 切替 — **PASS** (2026-05-11)

* [x] フォーマット切替が反映される — **PASS** (UHD ↔ HD 切替確認, 2026-05-11)

**最終構成**: Desktop Video **16.0.1** (DV 12.5.1 / 14.2.1 では SDK 16.0 の現行 IID が未公開で動作不可)。
**前提条件**: 本フォーク（SDK 16.0 でビルド）の BMD 出力には **Desktop Video 16.x 以降が必須**。

## 5. OCIO カラーマネジメント（重要：セッション 4 のリグレッション確認）

* [ ] View → OCIO Display → sRGB - Display → **ACES 2.0 - SDR 100 nits (Rec.709)** で **黒画面にならない** ✅

* [ ] ACES 2.0 - HDR 1000 nits (Rec.2020) などのバリエーション

* [ ] Raw / Un-tone-mapped で問題ないこと

* [ ] OCIO config 切替が即座に反映される

## 6. Qt / GUI

* [ ] **Qt WebEngine** が動作する（ヘルプ / Web ベース UI 要素）

* [ ] Session Manager の表示・操作

* [ ] タイムライン操作（in/out, ブックマーク, アノテーション）

* [ ] フル画面モード切替

* [ ] マルチモニタでの表示

## 7. Python / Mu スクリプティング

* [ ] `rv.exe -pyeval "from rv import commands; print(commands.frame())"` (GUI なしで Python 実行モード — 値が返る)

* [ ] PySide6 ベースの Python パッケージ機能（File → Packages）

* [ ] サンプル `.rvpkg` のインストールと有効化

## 8. RV ツール群

* [ ] `bin\rvio.exe -version` → 3.2.0

* [ ] `rvio input.exr -o output.jpg` で変換

* [ ] `rvio input.mov -t in:out -o clip.mp4` でトリム

* [ ] `bin\rvls.exe`、`bin\rvpush.exe` などその他ツールの起動確認

## 9. パフォーマンス / 安定性

* [ ] 4K EXR を 30 秒以上連続再生でメモリリーク無し（タスクマネージャ確認）

* [ ] GPU 使用率が再生中に上がる（Intel/NVIDIA GPU で OpenGL レンダリング）

* [ ] 5 分間操作してクラッシュしない

* [ ] セッションファイル (.rv) の保存・読み込み

## 10. プラグイン読み込み確認

* [ ] 起動時に AJADevices.dll が読み込まれる（Console / `--debug video`）

* [ ] BlackMagicDevices.dll が読み込まれる

* [ ] OIIO 画像フォーマットプラグインが正常ロード（PNG/EXR/TIFF/JPEG/RAW）

***

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

***

## 不具合・改善要望ログ

### 仕様確認 - スプラッシュ画面なし (§1, 2026-05-09)

* 起動時にスプラッシュ画面は表示されない仕様。アクションなし。

* ステータス: 確認済み（不具合ではない）

### FIXED - ProRes 未サポート (§2, 2026-05-09)

* ファイル: `Q:/FPTT_2026/composite/renders/Transit/FLTT_S102_0021_comp_v0001.mov`

* エラー: `MovieFFMpeg: Unsupported codec_id '147'` → codec\_id 147 は ProRes (`AV_CODEC_ID_PRORES`)

* 原因: upstream は ProRes を含む non-free デコーダを既定で無効化しており、FFmpeg 自体に ProRes デコーダが含まれていなかった

  * `cmake/dependencies/ffmpeg.cmake` の `NON_FREE_DECODERS_TO_DISABLE` リストに `prores` が含まれていた

  * ランタイムの allow-list は `src/lib/image/mio_ffmpeg/init.cpp` の `disallowedCodecsArray` で管理

* 採用した解決策: **option 2（FFmpeg 内蔵デコーダ利用）**

  * `cmake/dependencies/ffmpeg.cmake` で `RV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE=prores` を本フォークの既定キャッシュ値に設定

  * 副作用: FFmpeg と mio\_ffmpeg の再ビルドが必要

  * **ライセンス上の注意**: Apple は FFmpeg 実装をライセンス対象としていない。商用配布や外部納品では Apple SDK を使うべき。詳細は [FORK\_NOTES.md](FORK_NOTES.md) 参照

* ステータス: **解決済み**（再ビルド + 動作確認は別途実施予定）

### 確認 - \$OCIO 環境変数の扱い (§2, 2026-05-09)

* 症状: 起動時に `ERROR: Unable to retrieve OCIO context: ERROR: $OCIO environment variable unset!`

* OpenRV 自体は OCIO 環境変数を**必須としない**が、デフォルト View が OCIO Display に設定されているとロード時にエラーが出る

* 対応: Preferences → Color → 既定 View を Default / Linear に変更、または `OCIO=<path-to-config.ocio>` を設定

* ステータス: 仕様内（不具合ではない）

### 確認 - H.264 mp4 / MOV (§2, 2026-05-09)

* 別ファイル（実際の H.264）で再テスト → **PASS**

* ステータス: 解決済み

### BLOCKED - BlackMagic デバイス表示 → 出力でクラッシュ → 安全に非表示へ (§4, 2026-05-11)

**最終状態**: Desktop Video 16.x 系（SDK 16.0 と整合）へのアップグレードが必須。本フォークの BMD プラグインは現行 IID のみ使用、ランタイム不整合時は明確なメッセージを表示してデバイスを非表示にする。

**経緯（FIXED → CRASH → BLOCKED の流れ）**:

#### FIXED 段階 (commit `402e71c9`) — 誤判定で導入したフォールバック
旧記録（誤り）:

* 症状: DeckLink 4K Pro + Desktop Video 12.5.1 環境で、`BlackMagicDevices.dll` はロードされるが Preferences → Video → Output Module に `BlackMagic` が出現しない。エラーログにも何も出ない（DaVinci Resolve / xSTUDIO 等の他アプリでは動作）。

* 原因:
  1. `BlackMagicOutput.cpp` および `AJAOutput.cpp` の `output_module_create()` が `catch (...) {}` で例外を完全に黙殺 → 失敗原因の手がかりが残らない
  2. `QueryInterface(IID_IDeckLinkOutput)` および `QueryInterface(IID_IDeckLinkConfiguration)` が、SDK 16.0 が定義する現行 GUID で問い合わせる。Desktop Video 12.5.1 にはこの GUID が登録されていない (`E_NOINTERFACE = 0x80004002`) → `BlackMagicModule::open()` が "Black Magic: no boards found" を投げ、上記の catch で握り潰される

* 採用した解決策:
  1. 例外メッセージを stderr に出力 (commit `3fe0a9b1`)
  2. SDK ヘッダに同梱されている過去 IID へのフォールバックチェーンを追加 (commit `402e71c9`):
     - `IDeckLinkOutput`: current → v15_3_1 → v14_2_1（DoesSupportVideoMode シグネチャが SDK 14.2.1 以降同一なので vtable 互換）
     - `IDeckLinkConfiguration`: current → v15_3_1 → v10_11（SetInt/SetFlag/Release のみ使用）

* テスト結果: DeckLink 4K Pro が v14_2_1 経由で取得され、Output Module ドロップダウンに `BlackMagic` が出現、numVideoFormats=28 をサポート ✅

* ステータス: **解決済み**

#### CRASH 段階 (User test 2026-05-11) — 致命的バグ判明

* 症状: BMD を Output Module に選択し View → Presentation Device をオンにすると RV がクラッシュ（再現性あり）。

* 原因: SDK 16.0 ヘッダの `IDeckLinkOutput_v14_2_1` を `IDeckLinkOutput*` にキャストして使用するのは**安全ではない**。vtable レイアウトが異なる:
  - スロット 7: current SDK は `CreateVideoFrame`、v14_2_1 は `SetVideoOutputFrameMemoryAllocator`
  - 以降のスロットも全てずれる
  - QueryInterface は IUnknown 部分のみ vtable-stable なので通る
  - `CreateVideoFrame()` 呼び出し → 別関数（別シグネチャ）へジャンプ → クラッシュ
  
* 当初の私の判断「`DoesSupportVideoMode` のシグネチャが同一だから vtable 互換」は誤り。**シグネチャ一致は vtable 互換性を保証しない**。スロット位置（メソッド順序）が同一である必要がある。

#### BLOCKED 段階 (commit `2977ba3d`) — 安全策の実装

* `IDeckLinkOutput` のフォールバックを撤去、**current IID のみ使用**。
* 古い IID は **診断専用** で QI を試し、見つかれば「v14_2_1 が公開されているが unsafe」のメッセージを表示。
* 最終的にデバイスが追加できない場合は明確なエラー: "Update Desktop Video to a release matching the SDK"
* `IDeckLinkConfiguration` のフォールバックは維持（SetInt/SetFlag/Release は IUnknown 近傍のスロットで安定）

#### 検証結果 (2026-05-11)

| Desktop Video | 結果 |
|---|---|
| 12.5.1 | デバイス出現しない（旧バージョン、警告表示） |
| 14.2.1 | デバイス出現しない（v14_2_1 IID のみ公開、警告表示） |
| **16.0.1** | **動作 ✅（映像 + 音声 OK）** |

**結論**: SDK 16.0 でビルドした OpenRV を使うには Desktop Video 16.x 系のランタイムが必要。本フォークでは DV 16.0.1 で完全動作を確認。

**upstream Issue 報告について**:
- 当初の提案レポート（v14_2_1 vtable 互換）は誤りなので訂正が必要
- 本質的な問題: SDK 16.0 と古い DV ランタイムの組み合わせは原理的に動作しない（IID も vtable も不一致）
- upstream の解決方針候補:
  1. version-aware wrapper を実装（ABI 違いを抽象化）
  2. ビルド時に「対応 DV バージョン」をメッセージで明示
  3. 起動時に DV バージョンを検出して非対応なら明確にエラー
- 本フォークでは選択肢 3 を簡易実装済（commit `2977ba3d` の診断メッセージ）
