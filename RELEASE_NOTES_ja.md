# OpenRV (hiroshisaito/OpenRV-build) リリースノート

> English version: [RELEASE_NOTES.md](RELEASE_NOTES.md)

## v3.2.0 — 2026-05-11

### 概要

- ベース: upstream `AcademySoftwareFoundation/OpenRV` v3.2.0 相当
- 対応 VFX Platform: **CY2025**
- 動作確認環境: Windows 11, VS 2025 (v18.4), CMake 4.2.3, Qt 6.5.3, Python 3.11.9
- 主要拡張: AJA 17.6.0 / Blackmagic DeckLink 16.0 出力プラグイン同梱、FFmpeg ProRes デコーダ既定有効化、VS 2025 ビルド対応

### ⚠️ Blackmagic DeckLink ランタイム互換性（重要）

本ビルドは **Blackmagic DeckLink SDK 16.0** に対してリンクしています。出力プラグインを利用するには、ホストの **Blackmagic Desktop Video が SDK 16.0 に対応する版**である必要があります。

| Desktop Video バージョン | 動作 | 備考 |
|---|---|---|
| 12.5.1 以下 | ❌ 動作しない | DeckLink デバイスが Output Module に出現しません。ログに警告メッセージが出ます |
| 14.2.1 | ❌ 動作しない | 同上 |
| **16.0.1 以降** | ✅ **PASS** | 映像 + 音声 + SDI/HDMI 切替 + UHD↔HD フォーマット切替まで確認 |

**動作しない場合の症状**:
- File → Preferences → Video → Output Module ドロップダウンに **BlackMagic** が表示されない
- 起動時コンソール / ログに以下のような行が出る:
  ```
  ERROR: BlackMagicDevices: 'DeckLink XXX' does not expose the current
         IDeckLinkOutput interface (SDK 16.0). Update Desktop Video to
         a release matching the SDK used to build OpenRV.
         Download: https://www.blackmagicdesign.com/support
  ```

**対応**: <https://www.blackmagicdesign.com/support/family/capture-and-playback> より **Desktop Video 16.0 以降** をインストール / アップグレードしてください。DaVinci Resolve や他の Blackmagic 対応アプリは古い DV でも動作する場合がありますが、**本ビルドは SDK 16.0 で固定**のため後方互換しません。

**技術的背景**:
- SDK 16.0 の `IDeckLinkOutput` インターフェース GUID (`5F227C95-39D7-46C7-...`) は DV 16.x 以降でしか公開されていません
- 古い DV ランタイムが公開する `IDeckLinkOutput_v14_2_1` などの過去 IID は QueryInterface は通りますが、**vtable レイアウトが現行と非互換**（例: スロット 7 が v14_2_1 では `SetVideoOutputFrameMemoryAllocator`、現行では `CreateVideoFrame`）。誤って使うとプロセスがクラッシュします
- 本ビルドは現行 IID のみを受け入れる安全策を採用しており、非対応ランタイムでは BMD モジュールを意図的に非表示にします（commit `2977ba3d`）

### ⚠️ ProRes デコーダ ライセンスに関する注意

本ビルドは **FFmpeg のリバースエンジニアリング版 ProRes デコーダ**を既定で有効化しています ([FORK_NOTES.md](FORK_NOTES.md) 参照)。

- 社内ワークフロー / 内部レビューでは利用可
- **商用配布 / クライアント納品** では Apple ProRes Decoder SDK への切替を推奨（要 Apple への申請）
- 無効化したい場合: configure 時に `-DRV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE=` (空) を渡してリビルド

### その他の同梱機能・修正

- VS 2025 (Visual Studio 18, MSBuild 18.4) でのビルド対応
- Python `python.props` の v143 toolset 検出
- Boost VS 2025 bootstrap ラッパー
- DAV1D の meson 1.11+ 構文対応 (`meson setup` 必須)
- OCIO 2.x 1D LUT サンプラ uniform バインディング修正（ACES 2.0 GPU ディスプレイで黒画面回避、commit `b9d9beee`）

### 互換性 / 既知の制限

| 項目 | 必要バージョン |
|---|---|
| Windows | 10/11 (x64) |
| Visual Studio | 2025 (v18.4) 以降 |
| Qt | 6.5.3 (msvc2019_64) |
| Python | 3.11.9 |
| Blackmagic Desktop Video | **16.0 以降必須**（出力プラグイン使用時） |
| AJA | NTV2 SDK 17.6.0 同梱（自動ビルド、別途インストール不要） |

### UAT 検証範囲

[UAT_checklist.md](UAT_checklist.md) を参照。主要項目（起動、メディア再生、ACES 2.0、Blackmagic 出力、パフォーマンス）の PASS を確認済み。Qt/GUI 細部、Python スクリプト、RV ツール CLI 等は次回サイクルで検証予定。

### 関連リンク

- [FORK_NOTES.md](FORK_NOTES.md) — フォーク全般の差分とライセンス上の注意
- [workbench_history.md](workbench_history.md) — ビルドセッションの作業履歴
- [UAT_checklist.md](UAT_checklist.md) — UAT チェックリストと結果
