# Contributing to Xiaohongshu Converter

Thank you for your interest in contributing!

## Ways to Contribute

### 🐛 Reporting Bugs

1. Check if the issue already exists
2. Create a new issue with:
   - Clear title describing the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, browser, etc.)

### 💡 Suggesting Features

1. Open a discussion first to gauge interest
2. Describe the feature and use case
3. Explain why it would be beneficial

### 🔧 Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests if available
5. Commit with clear messages: `git commit -m 'Add some feature'`
6. Push to the branch: `git push origin feature/your-feature`
7. Submit a Pull Request

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Apple20251125/xiaohongshu-convert.git
cd xiaohongshu-convert

# Install frontend dependencies
cd app && npm install

# Install backend dependencies
cd ../api && pip install -r requirements.txt

# Install Playwright
playwright install chromium

# Run development servers
# Terminal 1: Backend
cd api && python app.py

# Terminal 2: Frontend (dev mode)
cd app && npm run dev
```

## Code Style

- **Frontend**: Follow existing React/TypeScript patterns
- **Backend**: Follow Python PEP 8 style
- Use meaningful variable and function names
- Add comments for complex logic

## Commit Messages

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
