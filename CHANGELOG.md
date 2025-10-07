# Changelog

All notable changes to the TastyTrade MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2024-10-07

### Fixed
- **Critical**: Fixed OAuth2 setup async context manager bug that caused installation failures
- Changed `get_session()` to `get_session_context()` in OAuth flow (cli.py, oauth_service.py)
- Resolved `'async_generator' object does not support the asynchronous context manager protocol` error

### Impact
- Database mode OAuth2 setup now completes successfully
- Fresh installations with OAuth2 credentials work correctly
- No API changes or breaking changes to existing functionality

## [1.0.2] - 2024-10-01

### Fixed
- Fixed OAuth CLI authentication flow
- Added proper browser-based OAuth with callback server
- Improved error handling in CLI setup

### Added
- Comprehensive OAuth setup documentation
- TastyTrade Developer Portal registration guide
- OAuth troubleshooting section in README

### Security
- Enhanced token encryption and storage
- Improved OAuth flow security

## [1.0.1] - 2024-09-30

### Added
- Initial public release
- Complete MCP server implementation
- Claude Desktop and ChatGPT support
- OAuth2 authentication with database mode
- Simple username/password mode
- Comprehensive tool suite for trading
- Real-time market data integration
- Security-first architecture

### Security
- Encrypted token storage
- Two-step trading confirmation
- Comprehensive audit logging
- No credentials exposed to LLMs

[1.0.2]: https://github.com/your-username/tastytrade-mcp-server/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/your-username/tastytrade-mcp-server/releases/tag/v1.0.1
