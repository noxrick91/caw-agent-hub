# Changelog

Notable user-facing changes to caw-agent are recorded here. Implementation details remain in the source history.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions match Git tags.

## [Unreleased]

## [0.1.16] - 2026-08-19

### Added

- Added keyboard selection and detail opening to the Todo list, matching the Agents panel controls.
- Added Plan-style Todo detail sheets with Markdown tables, code blocks, and Mermaid diagrams.

### Fixed

- Reduced intermittent UI stalls during active tasks by making periodic persistence non-blocking and consolidating recovery snapshots.

## [0.1.15] - 2026-08-18

### Fixed

- Fixed `upgrade now` rejecting GitHub releases whose optional notes field is `null`.

## [0.1.14] - 2026-08-18

### Changed

- Improved the contrast of compact header, status, and footer text.
- Presented LLM failures as a distinct error block instead of inline transcript text.

### Fixed

- Fixed stale characters appearing around ambiguous-width punctuation in Chinese Windows Terminal sessions.
- Fixed Windows workspace paths showing Unix separators or leaking the `\\?\` verbatim prefix.
- Kept bottom chrome above ConPTY's partially visible resize row so footer text is not clipped.

## [0.1.13] - 2026-08-18

### Changed

- Added native Windows ARM64 release builds, installers, self-upgrades, and website downloads alongside Linux x86_64/ARM64 and Windows x86_64.
- Removed unavailable macOS binaries from the public download matrix while retaining source-level macOS support.

## [0.1.12] - 2026-08-18

### Changed

- Hardened built-in MCP services with workspace-confined paths, dependency allowlists, and framing-safe stdout handling.
- Added separate prompt-cache write token and pricing accounting.
- Added self-hosted Forgejo release builds for Linux x86_64, Linux ARM64, and Windows x86_64 GNU; macOS prebuilt packages are temporarily unavailable.

### Fixed

- Fixed Anthropic prompt totals, cache-hit percentages, cache-write accounting, context compaction thresholds, and cost estimates.
- Fixed document, image, OCR, and speech MCP smoke tests hanging on Content-Length framing.
- Fixed FreeCAD and Blender status calls failing when their desktop backends are not installed.

## [0.1.11] - 2026-08-18

### Changed

- Improved terminal image previews with full half-block color detail and theme-aware transparent backgrounds.
- Hardened Unix and Windows installers with executable/version verification, strict checksum matching, and automatic rollback.

### Fixed

- Fixed Windows commands that used unavailable `head` or `tail` utilities, including commands inside shell pipelines.
- Fixed the unpainted Windows terminal safety column that could leave a missing background patch at the lower-right edge.
- Fixed completed projects occasionally reopening the Welcome setup after restart or console-window close.
- Fixed model API keys entered for a non-active provider being dispatched as chat messages instead of saved securely.

## [0.1.10] - 2026-08-18

### Changed

- Added Tab-cycled keyboard focus so the composer, tasks, and agents panels can be navigated without fighting the input caret.
- Improved file downloads with live byte and percentage progress.
- Improved install and upgrade guidance: Linux sudo is requested in another terminal, PATH conflicts are explained, and Windows replaces the locked executable after exit.

### Fixed

- Fixed failed background tasks leaving the parent idle instead of recovering.
- Fixed transcript scrolling so code and diagram headers no longer stay pinned while the body moves.
- Fixed markdown tables overflowing a narrow terminal.

## [0.1.9] - 2026-08-18

### Added

- Added dedicated language-server isolation controls and a clear confirmation before a project-defined server starts.
- Added platform-aware dependency installation suggestions with an explicit Install / Cancel prompt.
- Added safer opt-in loading for workspace MCP configuration.

### Changed

- Refined the terminal interface, including larger plan diagrams, more consistent panels, and smoother task, agent, and todo updates.
- Improved background-task handling so interactive and long-running programs are represented more accurately.
- Refined built-in skills, tool guidance, permission prompts, and project safety rules.
- Improved browser, screenshot, build, and debugging workflows across supported platforms.

### Fixed

- Fixed incomplete terminal borders and background painting in several layouts.
- Fixed task lifecycle and timeout edge cases that could report active work as failed.
- Fixed several permission, path, and cross-platform command handling issues.

## [0.1.8] - 2026-08-15

### Changed

- Improved setup, model providers, public documentation, and terminal presentation.

### Fixed

- Fixed provider-key handling and compatibility with third-party OpenAI-compatible gateways.

## [0.1.7] - 2026-08-15

### Added

- Added model routing, local REST/SSE control, broader GitHub and infrastructure tools, and improved task and agent panels.

### Changed

- Expanded help and public usage documentation.

## [0.1.6] - 2026-08-15

### Fixed

- Ollama works without an API key.
- An empty configuration file no longer blocks startup.

## [0.1.5] - 2026-08-15

### Added

- Added Windows ARM64 installation assets and a live Ollama model picker.

## [0.1.4] - 2026-08-14

### Changed

- Improved installer PATH setup and command documentation.

## [0.1.3] - 2026-08-14

### Added

- Added MCP catalog update checks and clearer package status.

### Changed

- Improved rewind coverage for file operations.

## [0.1.2] - 2026-08-14

### Added

- Added official MCP pack installation and public release downloads.

## [0.1.1] - 2026-08-14

### Fixed

- Fixed macOS ScreenCaptureKit build compatibility.

## [0.1.0] - 2026-08-14

### Added

- First public release of the sandboxed terminal coding agent, including permissions, sessions, MCP, GitHub integration, and verified upgrades.
