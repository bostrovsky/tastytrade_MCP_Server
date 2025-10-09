# TastyTrade MCP Server - Deployment Guide

This guide covers deploying the TastyTrade MCP Server to production and staging environments using our automated CI/CD pipeline.

## Overview

The deployment pipeline supports:
- **Staging Environment**: Uses TastyTrade sandbox for safe testing
- **Production Environment**: Uses live TastyTrade API for real trading
- **Automated CI/CD**: GitHub Actions pipeline with security scanning
- **Database Migrations**: Automated with backup and rollback capabilities
- **Health Monitoring**: Built-in health checks and monitoring

## Prerequisites

### Required Environment Variables

#### Staging Environment
```bash
# TastyTrade Sandbox Credentials
TASTYTRADE_SANDBOX_USERNAME=your_sandbox_email
TASTYTRADE_SANDBOX_PASSWORD=your_sandbox_password

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Security
SECRET_KEY=your_secret_key

# Optional: Monitoring
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

#### Production Environment
```bash
# TastyTrade Production Credentials (HANDLE WITH EXTREME CARE)
TASTYTRADE_PRODUCTION_USERNAME=your_production_email
TASTYTRADE_PRODUCTION_PASSWORD=your_production_password

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Security
SECRET_KEY=your_production_secret_key

# Optional: Monitoring
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

### GitHub Secrets Setup

Configure these secrets in your GitHub repository:

1. Go to Settings → Secrets and variables → Actions
2. Add the following secrets:

```
# Railway Deployment
RAILWAY_TOKEN=your_railway_token

# Environment Variables (for both staging and production)
DATABASE_URL_STAGING=postgresql://staging_user:pass@host:port/db
DATABASE_URL_PRODUCTION=postgresql://prod_user:pass@host:port/db
SECRET_KEY=your_secret_key
TASTYTRADE_SANDBOX_USERNAME=your_sandbox_email
TASTYTRADE_SANDBOX_PASSWORD=your_sandbox_password
TASTYTRADE_PRODUCTION_USERNAME=your_production_email
TASTYTRADE_PRODUCTION_PASSWORD=your_production_password
SLACK_WEBHOOK_URL=your_slack_webhook
```

## Deployment Pipeline

### Automatic Deployment

The CI/CD pipeline automatically triggers on:
- **Staging**: Push to `main` branch
- **Production**: Push to `production` branch or manual trigger

### Pipeline Stages

1. **Test**: Runs all tests with PostgreSQL service
2. **Security Scan**:
   - Trivy for container vulnerabilities
   - Bandit for Python security issues
   - Safety for dependency vulnerabilities
3. **Build**: Creates Docker images for staging/production
4. **Deploy**: Deploys to Railway with environment-specific configs

### Manual Deployment

You can also deploy manually using Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Deploy to staging
railway deploy --service staging-tastytrade-mcp

# Deploy to production (requires confirmation)
railway deploy --service production-tastytrade-mcp
```

## Database Management

### Running Migrations

#### Automatic (Recommended)
Migrations run automatically during deployment via the startup script.

#### Manual Migration
```bash
# Using the migration script
./scripts/migrate-database.sh migrate

# Check migration status
./scripts/migrate-database.sh status

# Dry run (see what would be executed)
DRY_RUN=true ./scripts/migrate-database.sh migrate
```

### Backup and Rollback

#### Create Backup
```bash
# Backup is created automatically before migrations
# Manual backup:
./scripts/migrate-database.sh backup
```

#### Rollback Migration
```bash
# Rollback to previous version
./scripts/migrate-database.sh rollback

# Rollback to specific revision
./scripts/migrate-database.sh rollback abc123

# Restore from backup
./scripts/migrate-database.sh restore /path/to/backup.sql
```

## Environment Configuration

### Staging Environment (`config/environments/staging.env`)
- **TastyTrade**: Sandbox mode enabled
- **Database**: Staging PostgreSQL instance
- **Logging**: INFO level
- **Features**: All safety features enabled
- **Rate Limiting**: 100 requests/minute

### Production Environment (`config/environments/production.env`)
- **TastyTrade**: Live trading mode
- **Database**: Production PostgreSQL with connection pooling
- **Logging**: WARNING level (minimal noise)
- **Features**: All safety and compliance features enabled
- **Rate Limiting**: 200 requests/minute
- **SSL**: Enabled with certificates
- **Monitoring**: APM and health checks enabled

## Monitoring and Health Checks

### Built-in Health Check
```bash
# Check server health
curl -f http://localhost:8000/health
```

### Docker Health Check
The Docker container includes automatic health checks that:
- Monitor server responsiveness
- Check database connectivity
- Validate TastyTrade API access

### Monitoring Setup
- **Health Check Interval**: 30 seconds
- **Metrics Collection**: Enabled in production
- **Alert Email**: ops@tastytrade-mcp.com
- **Slack Notifications**: Configured via webhook

## Security Considerations

### Production Security
- **SSL/TLS**: Enforced in production
- **Non-root User**: Container runs as `mcp` user
- **Secret Management**: Environment variables only
- **API Rate Limiting**: Enforced
- **Audit Logging**: All trading actions logged
- **Compliance Checks**: Enabled for all orders

### Development Security
- **Sandbox Only**: Development uses TastyTrade sandbox
- **Local Environment**: No production credentials in dev
- **Security Scanning**: All dependencies scanned
- **Code Analysis**: Bandit security linting

## Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check database connectivity
./scripts/migrate-database.sh status

# Verify DATABASE_URL format
echo $DATABASE_URL
```

#### TastyTrade Authentication Errors
```bash
# Verify credentials are set
echo $TASTYTRADE_SANDBOX_USERNAME  # for staging
echo $TASTYTRADE_PRODUCTION_USERNAME  # for production

# Check sandbox/production mode
echo $USE_SANDBOX
```

#### Docker Build Failures
```bash
# Build locally to debug
docker build -t tastytrade-mcp .

# Check logs
docker logs <container_id>
```

### Log Analysis
```bash
# View application logs
docker logs -f <container_name>

# View startup logs
docker logs <container_name> | grep "Starting"

# View error logs
docker logs <container_name> | grep ERROR
```

## Rollback Procedures

### Application Rollback
```bash
# Rollback to previous deployment (Railway)
railway rollback --service production-tastytrade-mcp

# Rollback database migration
./scripts/migrate-database.sh rollback
```

### Emergency Procedures
1. **Stop Production Traffic**: Update Railway to maintenance mode
2. **Rollback Database**: Use backup restoration
3. **Rollback Application**: Deploy previous known-good version
4. **Verify Health**: Run full health check suite
5. **Resume Traffic**: Remove maintenance mode

## Maintenance

### Regular Tasks
- **Database Backups**: Automated daily at 2 AM
- **Security Updates**: Monthly dependency updates
- **Log Rotation**: Automatic via Docker
- **Health Monitoring**: Continuous via built-in checks

### Backup Retention
- **Staging**: 7 days
- **Production**: 30 days
- **Critical Backups**: Manual archival for major releases

## Performance Optimization

### Production Settings
- **Workers**: 2 × CPU cores + 1
- **Connection Pool**: 20 connections + 30 overflow
- **Query Timeout**: 30 seconds
- **Request Timeout**: 120 seconds

### Monitoring Metrics
- Response time percentiles
- Database query performance
- TastyTrade API latency
- Error rates and types
- Resource utilization

## Support and Escalation

### Contact Information
- **Operations**: ops@tastytrade-mcp.com
- **Development**: Slack channel
- **Emergency**: On-call rotation

### Issue Escalation
1. **Level 1**: Application restart
2. **Level 2**: Database investigation
3. **Level 3**: TastyTrade API issues
4. **Level 4**: Infrastructure problems