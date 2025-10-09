# Architecture Documentation

## Overview

The TastyTrade MCP Server is built with a modern, scalable architecture that prioritizes security, reliability, and developer experience. This document describes the system architecture, design decisions, and implementation patterns.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Clients                             │
├─────────────┬───────────────┬──────────────┬───────────────┤
│   Claude    │   REST API    │   WebSocket  │   Webhooks    │
│    (MCP)    │   Clients     │   Clients    │  (TastyTrade) │
└──────┬──────┴───────┬───────┴──────┬───────┴───────┬───────┘
       │              │              │               │
       ▼              ▼              ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                     API Gateway Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │   MCP    │  │ FastAPI  │  │WebSocket │  │ Webhook  │    │
│  │  Server  │  │   REST   │  │  Server  │  │ Handler  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  Business Logic Layer                         │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Service Components                       │    │
│  ├──────────┬──────────┬──────────┬──────────┬────────┤    │
│  │   Auth   │  Market  │ Trading  │ Account  │  Risk  │    │
│  │ Service  │   Data   │  Engine  │  Manager │ Control│    │
│  └──────────┴──────────┴──────────┴──────────┴────────┘    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    Data Access Layer                          │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │   SQLAlchemy     │  │   Cache Layer    │                 │
│  │    (Async)       │  │ (Redis/Memory)   │                 │
│  └────────┬─────────┘  └────────┬─────────┘                 │
└───────────┼──────────────────────┼───────────────────────────┘
            │                      │
            ▼                      ▼
┌──────────────────┐    ┌──────────────────┐
│   PostgreSQL/    │    │      Redis        │
│     SQLite       │    │    (Optional)     │
└──────────────────┘    └──────────────────┘
```

## Core Components

### 1. API Gateway Layer

#### MCP Server
- **Purpose**: Integration with Claude and other LLM assistants
- **Protocol**: Model Context Protocol (MCP)
- **Features**:
  - Tool registration and discovery
  - Conversational interface
  - Context management
  - Token security (never exposed to LLM)

#### FastAPI REST
- **Purpose**: Traditional REST API for web/mobile clients
- **Framework**: FastAPI with async support
- **Features**:
  - OpenAPI documentation
  - Request validation
  - Authentication middleware
  - Rate limiting

#### WebSocket Server
- **Purpose**: Real-time data streaming
- **Use Cases**:
  - Market data updates
  - Order status changes
  - Account notifications
- **Implementation**: FastAPI WebSocket support

#### Webhook Handler
- **Purpose**: Receive events from TastyTrade
- **Security**: Signature verification
- **Processing**: Async queue for reliability

### 2. Business Logic Layer

#### Authentication Service
```python
# Core responsibilities
- OAuth2 flow management
- Token encryption/decryption
- Session management
- Permission checking
```

#### Market Data Service
```python
# Core responsibilities
- Symbol search and validation
- Quote retrieval and caching
- Options chain management
- Market hours calculation
```

#### Trading Engine
```python
# Core responsibilities
- Order validation
- Two-step confirmation flow
- Risk checks
- Order submission to TastyTrade
```

#### Account Manager
```python
# Core responsibilities
- Position tracking
- Balance calculations
- Transaction history
- Performance metrics
```

#### Risk Control
```python
# Core responsibilities
- Position limits
- Buying power checks
- Pattern day trader rules
- Order validation
```

### 3. Data Access Layer

#### Database Design
```sql
-- Core Tables
users
├── id (UUID, PK)
├── email
├── status
└── timestamps

broker_links
├── id (UUID, PK)
├── user_id (FK)
├── provider
├── status
└── encrypted_tokens

order_previews
├── id (UUID, PK)
├── user_id (FK)
├── order_json
├── nonce
├── status
└── expires_at

order_audits
├── id (UUID, PK)
├── user_id (FK)
├── action
├── payload
└── result
```

#### Caching Strategy
- **L1 Cache**: In-memory for hot data
- **L2 Cache**: Redis for shared state
- **Cache Keys**:
  ```
  market:quote:{symbol}        # 5 second TTL
  user:positions:{user_id}     # 30 second TTL
  market:hours:{date}          # 24 hour TTL
  ```

## Security Architecture

### Token Management
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   OAuth     │────▶│  Encryption │────▶│   Database  │
│   Token     │     │   Service   │     │  (Encrypted)│
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │     KMS     │
                    │   (Future)  │
                    └─────────────┘
```

### Security Layers
1. **Transport**: HTTPS/TLS everywhere
2. **Authentication**: OAuth2 with PKCE
3. **Authorization**: Role-based access control
4. **Encryption**: AES-256 for tokens at rest
5. **Audit**: Complete audit trail

### Two-Step Trading Flow
```
User Request ──▶ Preview ──▶ Confirmation ──▶ Submit
                    │             │              │
                    ▼             ▼              ▼
                 Validate      Verify        Execute
                 & Price       Nonce         Trade
```

## Deployment Architecture

### Development
```yaml
# Single process, SQLite database
MCP Server + API ──▶ SQLite
                 ──▶ In-Memory Cache
```

### Production
```yaml
# Multi-process, PostgreSQL, Redis
┌──── Load Balancer ────┐
│                       │
▼                       ▼
API Server (n)    MCP Server (n)
│                       │
└──────┬────────────────┘
       │
       ▼
┌─────────────┐  ┌─────────────┐
│ PostgreSQL  │  │    Redis    │
│  (Primary)  │  │   Cluster   │
└─────────────┘  └─────────────┘
```

### Container Architecture
```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder
# Install dependencies

FROM python:3.11-slim
# Copy only runtime requirements
# Run as non-root user
```

## Performance Considerations

### Async Everything
- All database operations use async SQLAlchemy
- HTTP calls use httpx with connection pooling
- Background tasks use asyncio

### Connection Pooling
```python
# Database connections
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

# HTTP connections
limits = httpx.Limits(
    max_keepalive_connections=10,
    max_connections=100
)
```

### Rate Limiting
- Per-user limits: 100 requests/minute
- Per-IP limits: 1000 requests/minute
- WebSocket connections: 5 per user

## Monitoring & Observability

### Health Checks
```
/health/          # Basic health
/health/ready     # Readiness probe
/health/live      # Liveness probe
/health/detailed  # Component status
```

### Metrics
- Request latency (p50, p95, p99)
- Error rates by endpoint
- Database query performance
- Cache hit rates
- Active WebSocket connections

### Logging
```python
# Structured logging
{
  "timestamp": "2025-09-14T01:58:14.823582",
  "level": "INFO",
  "logger": "tastytrade_mcp.api",
  "message": "Order submitted",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "order_id": "ORD-12345",
  "symbol": "AAPL",
  "quantity": 100
}
```

## Design Patterns

### Repository Pattern
```python
class UserRepository:
    async def get(self, user_id: UUID) -> User
    async def create(self, user: User) -> User
    async def update(self, user: User) -> User
```

### Service Layer
```python
class TradingService:
    def __init__(self, repo: OrderRepository):
        self.repo = repo
    
    async def preview_order(self, request: OrderRequest):
        # Business logic here
        return await self.repo.create_preview(preview)
```

### Dependency Injection
```python
# FastAPI dependency injection
async def get_trading_service(
    session: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache)
) -> TradingService:
    return TradingService(session, cache)
```

## Testing Strategy

### Test Pyramid
```
         /\
        /  \  E2E Tests (5%)
       /────\
      /      \  Integration Tests (25%)
     /────────\
    /          \  Unit Tests (70%)
   /────────────\
```

### Test Coverage Goals
- Unit Tests: 90% coverage
- Integration Tests: Critical paths
- E2E Tests: Happy path + key errors

## Future Enhancements

### Planned Features
1. **Multi-broker Support**: Interactive Brokers, TD Ameritrade
2. **Advanced Analytics**: P&L tracking, tax reporting
3. **Algorithmic Trading**: Strategy backtesting
4. **Social Features**: Follow traders, share strategies

### Scalability Path
1. **Phase 1**: Single server (current)
2. **Phase 2**: Multiple API servers + Redis
3. **Phase 3**: Microservices architecture
4. **Phase 4**: Event-driven with Kafka

### Technology Upgrades
- **GraphQL API**: For flexible queries
- **gRPC**: For internal services
- **TimescaleDB**: For time-series data
- **Apache Pulsar**: For event streaming

## Decision Log

### Why FastAPI?
- **Pros**: Async support, automatic OpenAPI, type hints
- **Cons**: Younger ecosystem than Flask/Django
- **Decision**: Performance and developer experience win

### Why SQLAlchemy?
- **Pros**: Mature ORM, async support, migrations
- **Cons**: Learning curve, complexity
- **Decision**: Best async ORM for Python

### Why Poetry?
- **Pros**: Modern dependency management, lock files
- **Cons**: Not standard pip
- **Decision**: Better than pip + requirements.txt

### Why MCP?
- **Pros**: Native Claude integration, standardized protocol
- **Cons**: New protocol, limited tooling
- **Decision**: Best for LLM integration

## Compliance & Regulations

### Data Privacy
- PII encryption at rest
- Token rotation every 30 days
- Audit trail retention: 7 years
- GDPR compliance ready

### Trading Compliance
- Pattern day trader checks
- Regulation T compliance
- Best execution tracking
- Order audit trail

## Disaster Recovery

### Backup Strategy
- **Database**: Daily backups, 30-day retention
- **Configuration**: Version controlled
- **Secrets**: Encrypted backups

### Recovery Procedures
1. **RTO**: 4 hours
2. **RPO**: 1 hour
3. **Failover**: Manual (automated planned)

## Appendix

### Environment Variables
See [DEVELOPMENT.md](./DEVELOPMENT.md#environment-variables)

### API Endpoints
See [OpenAPI Documentation](./api/openapi.yaml)

### Database Schema
See [migrations/](../migrations/)

### Error Codes
| Code | Description |
|------|-------------|
| 1001 | Authentication failed |
| 1002 | Insufficient permissions |
| 2001 | Invalid order |
| 2002 | Insufficient buying power |
| 3001 | Market closed |
| 3002 | Symbol not found |