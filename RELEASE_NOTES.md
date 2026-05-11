# OpenRV (hiroshisaito/OpenRV-build) Release Notes

> 日本語版: [RELEASE_NOTES_ja.md](RELEASE_NOTES_ja.md)

## v3.2.0 — 2026-05-11

### Overview

- Base: equivalent to upstream `AcademySoftwareFoundation/OpenRV` v3.2.0
- VFX Platform: **CY2025**
- Verified build environment: Windows 11, VS 2025 (v18.4), CMake 4.2.3, Qt 6.5.3, Python 3.11.9
- Extensions in this fork: AJA 17.6.0 / Blackmagic DeckLink 16.0 output plugins bundled, FFmpeg ProRes decoder enabled by default, VS 2025 build patches

### ⚠️ Blackmagic DeckLink Runtime Compatibility (Important)

This build is linked against **Blackmagic DeckLink SDK 16.0**. To use the output plugin you must have a **Blackmagic Desktop Video runtime that matches SDK 16.0**.

| Desktop Video version | Result | Notes |
|---|---|---|
| 12.5.1 and earlier | ❌ Does not work | The DeckLink device does not appear in the Output Module dropdown; a warning is printed to the log |
| 14.2.1 | ❌ Does not work | Same as above |
| **16.0.1 or later** | ✅ **PASS** | Verified: video + audio + SDI/HDMI switching + UHD↔HD format switching |

**Symptoms when the runtime is too old**:
- `File → Preferences → Video → Output Module` dropdown does **not** list **BlackMagic**.
- The startup console / log file contains:
  ```
  ERROR: BlackMagicDevices: 'DeckLink XXX' does not expose the current
         IDeckLinkOutput interface (SDK 16.0). Update Desktop Video to
         a release matching the SDK used to build OpenRV.
         Download: https://www.blackmagicdesign.com/support
  ```

**Fix**: download and install **Desktop Video 16.0 or later** from <https://www.blackmagicdesign.com/support/family/capture-and-playback>. DaVinci Resolve and some other Blackmagic-aware apps may keep working on older Desktop Video releases, but **this build is pinned to SDK 16.0** and is not backwards compatible.

**Technical background**:
- The `IDeckLinkOutput` interface GUID introduced in SDK 16.0 (`5F227C95-39D7-46C7-...`) is only registered by Desktop Video 16.x and later.
- Older runtimes expose legacy IIDs such as `IDeckLinkOutput_v14_2_1`. `QueryInterface` succeeds for those, but the **vtable layout is not compatible with the current interface** (e.g. slot 7 maps to `SetVideoOutputFrameMemoryAllocator` in v14_2_1 versus `CreateVideoFrame` in the current SDK). Using such a pointer through `IDeckLinkOutput*` dispatches to the wrong function and crashes the process.
- This build accepts only the current IID. When an incompatible runtime is detected the plugin intentionally hides the BlackMagic module instead of letting it appear and crash (commit `2977ba3d`).

### ⚠️ ProRes Decoder Licensing Notice

This build enables FFmpeg's **reverse-engineered ProRes decoder** by default (see [FORK_NOTES.md](FORK_NOTES.md) for details).

- In-house workflows / internal review: generally fine.
- **Commercial distribution / client deliveries**: switch to Apple's official ProRes Decoder SDK (requires registration with Apple).
- To disable, re-run CMake with `-DRV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE=` (empty).

### Other bundled features and fixes

- Visual Studio 2025 (Visual Studio 18, MSBuild 18.4) build support.
- Python `python.props` `v143` toolset detection patch.
- Boost VS 2025 bootstrap wrapper.
- DAV1D upgraded to the meson 1.11+ `meson setup` syntax.
- OCIO 2.x 1D LUT sampler uniform binding fix — prevents the ACES 2.0 black-screen regression on GPU displays (commit `b9d9beee`).

### Compatibility / known constraints

| Item | Required version |
|---|---|
| Windows | 10/11 (x64) |
| Visual Studio | 2025 (v18.4) or later |
| Qt | 6.5.3 (msvc2019_64) |
| Python | 3.11.9 |
| Blackmagic Desktop Video | **16.0 or later (required when the output plugin is used)** |
| AJA | NTV2 SDK 17.6.0 (built automatically; no separate installer needed) |

### UAT coverage

See [UAT_checklist.md](UAT_checklist.md). The key items — launch, media playback, ACES 2.0, Blackmagic output, performance — have all PASSed. Qt/GUI details, Python scripting, and the RV CLI tools are scheduled for the next UAT cycle.

### Related links

- [FORK_NOTES.md](FORK_NOTES.md) — fork-wide deltas and licensing notes.
- [workbench_history.md](workbench_history.md) — build session history.
- [UAT_checklist.md](UAT_checklist.md) — UAT checklist and results.
