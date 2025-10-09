# Database Setup Guide

## Overview

The TastyTrade MCP Server supports two database configurations:
- **SQLite**: Simple, file-based, perfect for quick development
- **PostgreSQL**: Full-featured, production-ready, supports all features

## Quick Start

### Option 1: SQLite (Simplest)
```bash
# Already configured by default in .env
# Just run the app - database created automatically

# For order management tables (Story 3.1):
python scripts/create_order_tables_sqlite.py
```

### Option 2: PostgreSQL (Recommended for Full Features)
```bash
# Switch to PostgreSQL configuration
./scripts/switch_database.sh
# Select option 2

# Or manually:
docker compose up -d postgres redis
alembic upgrade head
```

## Database Comparison

| Feature | SQLite | PostgreSQL |
|---------|---------|------------|
| Setup Complexity | None | Docker required |
| UUID Support | Text strings | Native UUID |
| JSON Support | Text strings | Native JSONB |
| Concurrent Writes | Limited | Full support |
| ALTER TABLE | Very limited | Full support |
| Performance | Good for dev | Production ready |
| Migrations | Manual scripts | Alembic migrations |

## Current Architecture Issues & Solutions

### The Problem
The codebase was designed for PostgreSQL but defaults to SQLite for ease of development. This creates several issues:

1. **Migration Failures**: Alembic migrations use PostgreSQL-specific features
2. **Type Mismatches**: UUID and JSONB types don't exist in SQLite
3. **Feature Limitations**: Some features require PostgreSQL

### The Solution

#### For Development
Use the database switcher script:
```bash
./scripts/switch_database.sh
```

This script:
- Automatically updates your .env file
- Starts/stops Docker containers as needed
- Provides clear instructions for migrations

#### For Production
Always use PostgreSQL:
```bash
# Production .env should have:
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

## Manual Setup Instructions

### SQLite Setup
```bash
# 1. Ensure .env contains:
DATABASE_URL=sqlite+aiosqlite:///data/tastytrade_mcp.db

# 2. Create data directory:
mkdir -p data

# 3. Run SQLite-compatible scripts:
python scripts/create_order_tables_sqlite.py

# 4. Run the application:
python -m tastytrade_mcp.api.app
```

### PostgreSQL Setup
```bash
# 1. Start PostgreSQL:
docker compose up -d postgres

# 2. Update .env:
DATABASE_URL=postgresql+asyncpg://tastytrade:localdev123@localhost:5432/tastytrade_mcp

# 3. Run migrations:
alembic upgrade head

# 4. Run the application:
python -m tastytrade_mcp.api.app
```

## Troubleshooting

### "Docker daemon not running"
**Solution**: Start Docker Desktop application

### "ALTER table error" with SQLite
**Solution**: Use PostgreSQL or run manual SQLite scripts:
```bash
python scripts/create_order_tables_sqlite.py
```

### "Cannot connect to PostgreSQL"
**Solution**: Ensure Docker containers are running:
```bash
docker compose ps
docker compose up -d postgres
```

### Migration Issues
```bash
# Reset migrations (PostgreSQL):
alembic downgrade base
alembic upgrade head

# Reset SQLite database:
rm data/tastytrade_mcp.db
python scripts/create_order_tables_sqlite.py
```

## Best Practices

1. **Development**: Use SQLite for quick prototyping, PostgreSQL for feature development
2. **Testing**: Always test with PostgreSQL before deployment
3. **CI/CD**: Use PostgreSQL in all pipelines
4. **Production**: Only use PostgreSQL

## Environment Variables

### Essential Database Settings
```bash
# SQLite (development)
DATABASE_URL=sqlite+aiosqlite:///data/tastytrade_mcp.db

# PostgreSQL (recommended)
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database

# Redis (optional with SQLite, recommended with PostgreSQL)
REDIS_URL=redis://localhost:6379/0
USE_REDIS=true  # or false
```

## Database Schema

The database includes the following tables:

### Core Tables (All Stories)
- `users` - User accounts
- `broker_links` - OAuth connections to TastyTrade
- `broker_secrets` - Encrypted tokens

### Order Management Tables (Story 3.1)
- `order_previews` - Two-step confirmation previews
- `orders` - Order records
- `order_events` - Audit trail
- `bracket_orders` - OCO orders

## Migration Strategy

### For New Features
1. Create PostgreSQL migration: `alembic revision -m "description"`
2. Create SQLite script in `scripts/` directory
3. Document in this guide

### For Existing Code
1. PostgreSQL: Use Alembic migrations
2. SQLite: Use manual scripts in `scripts/` directory

## Recommendations

### For This Project
**Use PostgreSQL** for all development going forward:
1. Full feature support
2. Consistent dev/prod environment
3. No migration issues
4. Better performance

To switch permanently:
```bash
./scripts/switch_database.sh
# Select option 2 (PostgreSQL)
```

Then all migrations will work correctly:
```bash
alembic upgrade head
```

---

**Last Updated**: 2025-09-16
**Story**: 3.1 - Equity Order Management