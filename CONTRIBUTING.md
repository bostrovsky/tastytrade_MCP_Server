# Contributing to TastyTrade MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up development environment**:
   ```bash
   git clone https://github.com/your-username/tastytrade-mcp-server.git
   cd tastytrade-mcp-server
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

## Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests**:
   ```bash
   pytest
   black .
   ruff check .
   mypy src/
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

- Use **Black** for code formatting
- Use **Ruff** for linting
- Use **MyPy** for type checking
- Follow **PEP 8** conventions
- Add type hints to all new code

## Testing

- Write tests for all new functionality
- Maintain test coverage above 80%
- Use **pytest** for testing
- Mock external API calls in tests

## Documentation

- Update README.md for user-facing changes
- Add docstrings to all public functions
- Update API documentation for new tools
- Include usage examples

## Security

- Never commit credentials or API keys
- Use .env files for configuration
- Follow secure coding practices
- Report security issues privately

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Check existing issues before creating new ones

Thank you for contributing! 🎉
