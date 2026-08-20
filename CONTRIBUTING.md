# Contributing to MongoDB Ops Console

Thank you for your interest in contributing to MongoDB Ops Console! We welcome community contributions, bug reports, feature requests, and code updates.

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- Docker & Docker Compose
- `uv` (Fast Python package manager)

### Backend Setup

```bash
cd backend
uv sync --extra dev
uv run --extra dev pytest
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

## Pull Request Guidelines

1. **Tests**: Ensure all 86+ backend tests pass (`uv run --extra dev pytest`).
2. **Type Checking & Linting**: Run `npm run build` and `npm run lint` in the `frontend/` directory.
3. **Commit Messages**: Keep commit messages clear, concise, and focused on single logical changes.
4. **Documentation**: Update the relevant section of `README.md` if introducing new feature capabilities or environment variables.

## License

By contributing, you agree that your contributions will be licensed under the project's [Apache License 2.0](LICENSE).
