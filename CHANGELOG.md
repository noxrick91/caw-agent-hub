# Changelog

Notable user-facing changes to caw-agent are recorded here. Implementation details remain in the source history.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions match Git tags.

## [Unreleased]

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
