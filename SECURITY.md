# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please send an email to the maintainer or open a Security Advisory through GitHub.

We will:
1. Acknowledge your report within 24 hours
2. Provide a timeline for the fix
3. Keep you updated on our progress

## Security Best Practices

When running this application:

### Backend
- Do not expose the server to the public internet without authentication
- Consider adding rate limiting
- Keep dependencies updated
- Run in a sandboxed environment

### Data Handling
- Downloaded files are stored temporarily - ensure cleanup
- Be mindful of storage limits
- Implement file expiration policies

### Legal
- This tool is for personal use and learning purposes
- Respect Xiaohongshu's Terms of Service
- Do not use for commercial purposes without authorization
