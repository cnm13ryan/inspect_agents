# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.1] - 2025-01-15

### Added
- Initial release of inspect-agents
- Inspect-AI-native agents with typed state management
- Built-in tools for todo management and virtual filesystem operations
- Support for supervisor and iterative agent patterns
- Safe-by-default configuration with environment-gated tools
- Comprehensive test suite with CI integration
- Documentation site with examples and guides
- Sub-agent orchestration with YAML configuration
- Approval policies and security controls
- Filesystem sandboxing with root confinement and symlink denial
- Rich observability with structured logging and tracing

### Features
- **State Management**: Pydantic-based `Todo` and `Files` models backed by Inspect-AI Store
- **Agent Types**: Supervisor agents with sub-agent delegation and iterative agents
- **Tool Ecosystem**: Built-in todos/filesystem tools plus optional standard tools (web search, exec, browser)
- **Security**: Approval system, quarantine filters, sandbox confinement
- **Observability**: Built-in logging, tracing, and structured transcripts

### Tools
- `write_todos`: Update and track agent plans
- `ls`, `read_file`, `write_file`, `edit_file`: Virtual filesystem operations
- Optional: `web_search`, `bash`, `python`, `web_browser`, `text_editor` (environment-gated)

### Examples
- Self-contained quickstart (no external dependencies)
- Research agents with web search capabilities
- Code analysis and file manipulation workflows
- Multi-step task automation with persistent state

[Unreleased]: https://github.com/cnm13ryan/inspect_agents/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/cnm13ryan/inspect_agents/releases/tag/v0.0.1
