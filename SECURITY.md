# Security Policy

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please follow these steps:

1. **Do NOT** open a public issue
2. Email security details to: [create a security email]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if known)

## Security Measures

### Authentication
- OAuth2 with PKCE flow
- Encrypted token storage
- Automatic token refresh
- No credentials exposed to LLMs

### Data Protection
- Local SQLite database with encryption
- Fernet symmetric encryption for tokens
- No sensitive data in logs
- Secure credential handling

### API Security
- Request/response validation
- Rate limiting on trading operations
- Two-step confirmation for trades
- Comprehensive audit logging

### Best Practices
- Regular dependency updates
- Automated security scanning
- Code review requirements
- Minimal privilege principle

## Responsible Disclosure

We appreciate responsible disclosure of security vulnerabilities. We will:

1. Acknowledge receipt within 24 hours
2. Provide initial assessment within 72 hours
3. Keep you informed of progress
4. Credit you in release notes (if desired)
5. Release security fixes promptly

Thank you for helping keep our users safe! 🔒
