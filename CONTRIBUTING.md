# Contributing to Neuro SAN Studio

Thank you for your interest in contributing to Neuro SAN Studio! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct v2.1](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

Please report any unacceptable behavior to **labgithub@cognizant.com**.

## Getting Started

Before you begin contributing, please:

1. Read the [README.md](README.md) to understand the project
2. Review the [User Guide](docs/user_guide.md) to understand how Neuro SAN works
3. Check out the [Tutorial](docs/tutorial.md) to get hands-on experience
4. Browse existing [Issues](https://github.com/cognizant-ai-lab/neuro-san-studio/issues) and [Pull Requests](https://github.com/cognizant-ai-lab/neuro-san-studio/pulls)
5. Browse existing [Discussions](https://github.com/cognizant-ai-lab/neuro-san-studio/discussions) to see if your topic has already been addressed

## Development Environment Setup

### Prerequisites

- Python 3.12 or 3.13
- Git
- Make (for macOS/Linux users)

### Setup Steps

1. **Fork the repository**

   Visit [https://github.com/cognizant-ai-lab/neuro-san-studio](https://github.com/cognizant-ai-lab/neuro-san-studio) and click the "Fork" button.

2. **Clone your fork**

   ```bash
   git clone https://github.com/your-username/neuro-san-studio.git
   cd neuro-san-studio
   ```

3. **Set up the development environment**

   For macOS/Linux:
   ```bash
   make install
   ```

   For Windows (manual setup):
   ```cmd
   python -m venv venv
   .\venv\Scripts\activate.bat
   pip install -r requirements-build.txt
   pip install -r requirements.txt
   set PYTHONPATH=%CD%
   ```

4. **Activate the virtual environment**

   For macOS/Linux:
   ```bash
   source venv/bin/activate
   export PYTHONPATH=`pwd`
   ```

   For Windows:
   ```cmd
   .\venv\Scripts\activate.bat
   set PYTHONPATH=%CD%
   ```

5. **Configure API keys**

   Set up your OpenAI API key (or other LLM provider keys):
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

   Alternatively, create a `.env` file based on `.env.example` with your API keys.

6. **Add upstream remote**

   ```bash
   git remote add upstream https://github.com/cognizant-ai-lab/neuro-san-studio.git
   ```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug fixes**: Fix issues reported in the issue tracker
- **New features**: Add new coded tools, agent networks, or capabilities
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **Examples**: Create new agent network examples
- **Performance improvements**: Optimize existing code
- **Code cleanup**: Refactor or improve code quality

### Finding Something to Work On

- Check the [Issues](https://github.com/cognizant-ai-lab/neuro-san-studio/issues) page for open issues
- Look for issues labeled `good first issue` or `help wanted`
- If you have a new idea, open a new [discussion](https://github.com/cognizant-ai-lab/neuro-san-studio/discussions) first to discuss it with maintainers

### Creating a Branch

Create a descriptive branch name:

```bash
git checkout -b feature/your-feature-name  # For new features
git checkout -b fix/bug-description        # For bug fixes
git checkout -b docs/documentation-update  # For documentation
```

## Coding Standards

### Python Code Style

This project follows these coding standards:

- **Line length**: Maximum 119 characters
- **Formatter**: Black (v25.1.0)
- **Import sorting**: isort with Black profile
- **Linting**: flake8 and pylint
- **Naming conventions**: Follow Google Python Style Guide
  - Functions and variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_CASE`

### Documentation

- Add docstrings to all functions, classes, and modules
- Use clear and descriptive variable names
- Add comments for complex logic
- Update relevant documentation when changing functionality

### Directory Structure

- `apps/`: Application code and server implementations
- `coded_tools/`: Custom Python tools for agents
- `registries/`: HOCON configuration files for agent networks
- `tests/`: Test files (mirror the structure of the code being tested)
- `docs/`: Documentation files

## Testing Guidelines

### Running Tests

For macOS/Linux:
```bash
make lint               # Run linting on source code
make lint-tests         # Run linting on test code
make test               # Run all tests with coverage except integration test
make test-integration   # run integration test

require to run the follow steps 1st:
- goto top level neuro-san-studio
- make install
- ". venv/bin/activate"
- export PYTHONPATH=`pwd`
- export AGENT_TOOL_PATH=tests/coded_tools/ 
- export AGENT_MANIFEST_FILE=tests/registries/manifest.hocon

# Run all integration test suite:
- Run pytest -s -m "integration"

# Run all test cases under that group of sectors:
- Run pytest -s -m "integration_basic"
- Run pytest -s -m "integration_industry"

# Run all test cases that related to network agent name:
- Run pytest -s -m "integration_basic_coffee_finder_advance"

```

For Windows (manual):
```bash
# Run linting
isort apps coded_tools tests
black apps coded_tools tests
flake8 apps coded_tools tests

# Run tests
pytest --verbose --cov=. --cov-report=term-missing --no-cov-on-fail
```

### Writing Tests

- Place tests in the `tests/` directory, mirroring the structure of the code being tested
- Use descriptive test function names: `test_<functionality>_<scenario>`
- Follow the Arrange-Act-Assert pattern
- Mock external dependencies (API calls, file I/O, etc.)
- Aim for high test coverage on new code

### Test Configuration

Tests are configured in `pyproject.toml` under `[tool.pytest.ini_options]`.

## Pull Request Process

### Before Submitting

1. **Ensure tests pass locally**
   ```bash
   make test  # or run tests manually on Windows
   ```

2. **Run linting checks**
   ```bash
   make lint
   make lint-tests
   ```

3. **Update documentation** if your changes affect user-facing functionality

4. **Update CHANGELOG** if applicable

### Commit Messages

Write clear and descriptive one-line summary commit messages, plus optional details if needed. If your commit relates to a specific issue, mention the issue number at the beginning:

```
#123: Add feature to support custom LLM providers

- Implement provider interface
- Add configuration options
- Update documentation
```

Or for fixes:

```
#456: Fix authentication bug in agent network designer

- Correct token validation logic
- Add test coverage for edge cases
```

One-line commit messages are usually sufficient, but if your commit is complex, consider adding a detailed description.

### Submitting a Pull Request

1. **Push your changes**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request**
   - Go to the [repository](https://github.com/cognizant-ai-lab/neuro-san-studio)
   - Click "New Pull Request"
   - Select your fork and branch
   - Fill out the PR template with:
     - Clear description of changes
     - Motivation for the changes
     - Related issue numbers (if applicable)
     - Testing performed

3. **Respond to review feedback**
   - Be open to feedback and suggestions
   - Make requested changes promptly
   - Push additional commits to the same branch

4. **Wait for CI checks**
   - GitHub Actions will run tests automatically
   - Ensure all checks pass before requesting review

### Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Include tests for new functionality
- Update documentation as needed
- Ensure backward compatibility when possible
- Follow the project's coding standards

## Additional Development Notes

### Markdown Linting

We use [pymarkdown](https://pymarkdown.readthedocs.io/en/latest/) for Markdown files:

```bash
pymarkdown --config ./.pymarkdownlint.yaml scan ./docs ./README.md
```

Configuration is in `.pymarkdownlint.yaml`.

### Logging

Use the `logging` module for logging instead of `print`.
To enable debug logs for coded tools, set:

```bash
export AGENT_SERVICE_LOG_JSON=logging.json
```

### Using the Makefile

The Makefile provides convenient commands for development (macOS/Linux):

- `make venv` - Create virtual environment
- `make install` - Install all dependencies
- `make activate` - Get activation instructions
- `make lint` - Run code formatting and linting
- `make lint-tests` - Run linting on tests
- `make test` - Run all tests with coverage except integration test
- `make test-integration` - Run integration test

## Keeping Your Fork Updated

Regularly sync your fork with the upstream repository:

```bash
# Fetch changes from upstream
git fetch upstream

# Update your main branch
git checkout main
git merge upstream/main
git push origin main

# Rebase your feature branch (if needed)
git checkout feature/your-feature-name
git rebase main
```

## Community

### Getting Help

- **Documentation**: Check [docs/](docs/) for guides and tutorials
- **Issues**: Search existing [issues](https://github.com/cognizant-ai-lab/neuro-san-studio/issues) or create a new one
- **Discussions**: Use [GitHub Discussions](https://github.com/cognizant-ai-lab/neuro-san-studio/discussions) for questions and ideas

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Pull Requests**: Code contributions
- **GitHub Discussions**: General questions and discussions

### Links

- **Main Library**: [Neuro SAN](https://github.com/cognizant-ai-lab/neuro-san)
- **YouTube**: [Decision AI](https://www.youtube.com/@decision-ai)
- **Website**: [Cognizant AI Lab](https://www.cognizant.com/us/en/ai-lab)
- **X**: [@cognizantailab](https://x.com/cognizantailab)
- **LinkedIn**: [Cognizant AI Lab](https://www.linkedin.com/showcase/cognizant-ai-lab)
- **Blog**: [Medium](https://medium.com/@evolutionmlmail)

## License

By contributing to Neuro SAN Studio, you agree that your contributions will be licensed under the project's [Apache 2.0 License](LICENSE.txt).

## Questions?

If you have questions about contributing, please:

1. Check existing documentation
2. Search [GitHub Discussions](https://github.com/cognizant-ai-lab/neuro-san-studio/discussions) for similar questions
3. Ask in [GitHub Discussions](https://github.com/cognizant-ai-lab/neuro-san-studio/discussions) - this is the best place for questions!
4. Search existing issues (for bug reports only)

For general support, see [SUPPORT.md](SUPPORT.md).

Thank you for contributing to Neuro SAN Studio!
