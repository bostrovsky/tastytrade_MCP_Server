# Development Guide

This guide will help you set up and run the TastyTrade MCP Server for local development.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Running the Application](#running-the-application)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Database Management](#database-management)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- **Python 3.11+** - The application requires Python 3.11 or higher
- **Poetry** - Dependency management tool
- **Git** - Version control
- **Docker** (optional) - For PostgreSQL and Redis in production-like setup

### macOS Installation
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11+
brew install python@3.11

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

# Verify installations
python3 --version  # Should show 3.11.x or higher
poetry --version   # Should show 2.x.x
```

### Linux Installation
```bash
# Update package manager
sudo apt update

# Install Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

### Windows Installation
1. Download Python 3.11+ from [python.org](https://www.python.org/downloads/)
2. Install Poetry using PowerShell:
   ```powershell
   (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
   ```

## Initial Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd tastytrade-mcp
```

### 2. Install Dependencies
```bash
# Install all dependencies
poetry install

# Install with development dependencies
poetry install --with dev
```

### 3. Environment Configuration
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your configuration
# Key variables to configure:
# - ENVIRONMENT=development
# - DATABASE_URL=sqlite+aiosqlite:///data/tastytrade_mcp.db
# - USE_SANDBOX=true
# - SECRET_KEY=<generate-a-secure-key>
# - ENCRYPTION_KEY=<generate-another-secure-key>
```

#### Generate Secure Keys
```python
# Generate secure keys for .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

### 4. Database Setup

#### SQLite (Default for Development)
```bash
# Create data directory
mkdir -p data

# Initialize the database
poetry run python scripts/setup_sqlite.py

# Run migrations
export PYTHONPATH=src
poetry run alembic upgrade head
```

#### PostgreSQL (Optional - Production-like)
```bash
# Start PostgreSQL with Docker
docker run -d \
  --name tastytrade-postgres \
  -e POSTGRES_USER=tastytrade \
  -e POSTGRES_PASSWORD=localdev123 \
  -e POSTGRES_DB=tastytrade_mcp \
  -p 5432:5432 \
  postgres:15-alpine

# Update .env
# DATABASE_URL=postgresql+asyncpg://tastytrade:localdev123@localhost:5432/tastytrade_mcp

# Run migrations
poetry run alembic upgrade head
```

### 5. Redis Setup (Optional)

Redis provides better caching performance but falls back to in-memory cache if not available.

```bash
# Start Redis with Docker
docker run -d \
  --name tastytrade-redis \
  -p 6379:6379 \
  redis:7-alpine

# Update .env
# REDIS_URL=redis://localhost:6379/0
# USE_REDIS=true
```

## Running the Application

### Start the MCP Server
```bash
# Run the MCP server (for Claude integration)
export PYTHONPATH=src
poetry run python -m tastytrade_mcp.main
```

### Start the API Server
```bash
# Run the FastAPI server (for REST API)
export PYTHONPATH=src
poetry run python scripts/run_api.py

# The API will be available at:
# - http://localhost:8000 - API root
# - http://localhost:8000/docs - Swagger UI documentation
# - http://localhost:8000/redoc - ReDoc documentation
# - http://localhost:8000/health/ - Health check
```

### Using Development Scripts
```bash
# Start all services (database, cache, API)
./scripts/dev.sh start

# Stop all services
./scripts/dev.sh stop

# View logs
./scripts/dev.sh logs

# Reset database
./scripts/dev.sh reset

# Seed with test data
./scripts/dev.sh seed
```

## Development Workflow

### 1. Code Organization
```
src/tastytrade_mcp/
├── api/          # FastAPI endpoints
├── auth/         # Authentication logic
├── config/       # Configuration management
├── db/           # Database models and engine
├── models/       # SQLAlchemy models
├── services/     # Business logic services
├── tools/        # MCP tool implementations
└── utils/        # Utility functions
```

### 2. Making Changes

#### Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

#### Code Style
The project uses:
- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

```bash
# Format code
poetry run black src tests

# Run linter
poetry run ruff check src tests

# Type checking
poetry run mypy src

# Run all checks
poetry run pre-commit run --all-files
```

### 3. Database Migrations

#### Create a New Migration
```bash
# After modifying models
poetry run alembic revision --autogenerate -m "Description of changes"

# Review the generated migration in migrations/versions/
# Apply the migration
poetry run alembic upgrade head
```

#### Rollback Migration
```bash
# Rollback one migration
poetry run alembic downgrade -1

# Rollback to specific revision
poetry run alembic downgrade <revision_id>
```

## Testing

### Run All Tests
```bash
# Run test suite
poetry run pytest

# With coverage
poetry run pytest --cov=tastytrade_mcp --cov-report=term-missing

# Run specific test file
poetry run pytest tests/test_auth.py

# Run with verbose output
poetry run pytest -v
```

### Test Categories
```bash
# Unit tests only
poetry run pytest tests/unit/

# Integration tests
poetry run pytest tests/integration/

# Run tests in parallel
poetry run pytest -n auto
```

### Writing Tests
```python
# tests/test_example.py
import pytest
from tastytrade_mcp.services.cache import CacheService

@pytest.mark.asyncio
async def test_cache_service():
    """Test cache service operations."""
    cache = CacheService()
    await cache.initialize()
    
    # Test set and get
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value"
```

## Database Management

### Database Console
```bash
# SQLite
sqlite3 data/tastytrade_mcp.db

# PostgreSQL
psql postgresql://tastytrade:localdev123@localhost:5432/tastytrade_mcp
```

### Common Database Commands
```sql
-- View all tables
.tables  -- SQLite
\dt      -- PostgreSQL

-- View table schema
.schema users  -- SQLite
\d users       -- PostgreSQL

-- Count records
SELECT COUNT(*) FROM users;
```

### Backup and Restore

#### SQLite
```bash
# Backup
sqlite3 data/tastytrade_mcp.db ".backup data/backup.db"

# Restore
cp data/backup.db data/tastytrade_mcp.db
```

#### PostgreSQL
```bash
# Backup
pg_dump -U tastytrade -h localhost tastytrade_mcp > backup.sql

# Restore
psql -U tastytrade -h localhost tastytrade_mcp < backup.sql
```

## API Documentation

### Swagger UI
Access interactive API documentation at: http://localhost:8000/docs

Features:
- Try out endpoints directly
- View request/response schemas
- Authentication testing

### ReDoc
Alternative documentation at: http://localhost:8000/redoc

### OpenAPI Schema
Download the OpenAPI specification:
```bash
curl http://localhost:8000/openapi.json > openapi.json
```

## Environment Variables

### Core Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment (development/staging/production) | development |
| `DEBUG` | Enable debug mode | true |
| `LOG_LEVEL` | Logging level | INFO |

### Database
| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | sqlite+aiosqlite:///data/tastytrade_mcp.db |

### Security
| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Application secret key | (generate one) |
| `ENCRYPTION_KEY` | Token encryption key | (generate one) |

### TastyTrade API
| Variable | Description | Default |
|----------|-------------|---------|
| `TASTYTRADE_BASE_URL` | API base URL | https://sandbox.api.tastyworks.com |
| `USE_SANDBOX` | Use sandbox environment | true |

### Optional Services
| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | redis://localhost:6379/0 |
| `USE_REDIS` | Enable Redis cache | false |
| `USE_KMS` | Enable KMS encryption | false |
| `SENTRY_DSN` | Sentry error tracking | (optional) |

## Troubleshooting

### Common Issues

#### Poetry Not Found
```bash
# Add Poetry to PATH
export PATH="$HOME/.local/bin:$PATH"

# Add to shell profile (.bashrc, .zshrc, etc.)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

#### Database Connection Error
```bash
# Check if database file exists
ls -la data/tastytrade_mcp.db

# Recreate database
rm data/tastytrade_mcp.db
poetry run python scripts/setup_sqlite.py
```

#### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn tastytrade_mcp.api.app:app --port 8001
```

#### Import Errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=src

# Reinstall dependencies
poetry install
```

### Debug Mode

Enable detailed logging:
```python
# .env
DEBUG=true
LOG_LEVEL=DEBUG

# Or via environment
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Health Checks

Verify service health:
```bash
# Basic health check
curl http://localhost:8000/health/

# Detailed health check
curl http://localhost:8000/health/detailed | python -m json.tool

# Check specific component
curl http://localhost:8000/health/ready
```

## Getting Help

### Documentation
- [README.md](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - AI assistant guide
- [API Documentation](http://localhost:8000/docs) - Interactive API docs

### Resources
- [Poetry Documentation](https://python-poetry.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

### Support
- GitHub Issues: Report bugs and request features
- Pull Requests: Contribute improvements
- Discussions: Ask questions and share ideas