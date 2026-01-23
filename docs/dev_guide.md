# Development Guide

## Using the Makefile

This repository includes a Makefile with several useful commands to streamline development tasks.
**Note: These Makefile commands are designed for macOS and Unix-like systems and will not work directly on Windows.**

- `make venv` - Creates a virtual environment in the `./venv` directory if it doesn't already exist
- `make install` - Creates the virtual environment (if needed) and installs all dependencies including build dependencies
- `make activate` - Checks if the virtual environment exists and either provides activation instructions (if it exists)
or suggests running `make install` (if it doesn't)
- `make lint` - Runs code formatting and linting tools (isort, black, flake8) on the source code
- `make lint-tests` - Runs code formatting and linting tools on the test code
- `make test` - Runs lint and lint-tests, then executes the tests with pytest and generates coverage reports

These Makefile commands provide a convenient alternative to the manual steps described in the Installation section for
macOS users. Windows users should follow the manual installation instructions instead.

### Note on Markdown Linting

We use [pymarkdown](https://pymarkdown.readthedocs.io/en/latest/) to run linting on .md files.
`pymarkdown` can be configured via `.pymarkdown.yaml` located in the projects top level folder. See
this [page](https://pymarkdown.readthedocs.io/en/latest/rules/) for all the configuration options.
`pymarkdown` is installed in the virtual environment as part of the build dependency requirements
specified in `build-requirements.txt`.

You can run `pymarkdown` in two ways:

<!-- pyml disable blanks-around-fences -->
- Using an installed version of `pymarkdown`

    - ```bash
      pymarkdown --config ./.pymarkdownlint.yaml scan ./docs ./README.md
      ```

    - The `--config` flag is used to pass in a configuration file to `pymarkdownlint`
    - To see all the options, run the following command:

    ```bash
    pymarkdown --help
    ```

<!-- pyml enable blanks-around-fences -->
- Using Make

    - `make lint`

## Python Project Configuration

This project uses `pyproject.toml` for configuration of various Python development tools. This modern approach
centralizes tool configurations in a single file instead of using separate configuration files for each tool.

These configurations are automatically applied when running the relevant Makefile commands (`make lint`,
`make lint-tests`, `make test`).

## Logging

To turn on debug logs for coded tools, export the following environment variable or set it in your `.env` file:

```shell
AGENT_SERVICE_LOG_JSON=logging.json
```

## Contribution Workflow

This section outlines the recommended workflow for contributing to this project.

### Getting Started

1. **Fork the repository**: Create your own fork of the repository on GitHub.

2. **Clone your fork**:

   ```bash
   git clone https://github.com/your-username/neuro-san-studio.git
   cd neuro-san-studio
   ```

3. **Set up the development environment**:

   ```bash
   make install
   ```

   This will create a virtual environment and install all dependencies.

4. **Activate the virtual environment**:

   ```bash
   source venv/bin/activate  # On macOS/Linux
   ```

   Or follow the instructions provided by `make activate`.

### Making Changes

1. **Create a feature branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

   Use a descriptive name that reflects the changes you're making.

2. **Make your changes**: Implement your feature or fix.

3. **Follow code standards**:
   - Keep line length to 119 characters
   - Add docstrings to functions and classes
   - Include unit tests for new functionality

4. **Run linting and tests locally**:

   ```bash
   make lint      # Run linting on source code
   make lint-tests # Run linting on test code
   make test      # Run all tests and generate coverage reports
   ```

   Ensure all tests pass and there are no linting errors.

### Submitting Changes

1. **Commit your changes**:

   ```bash
   git add .
   git commit -m "Descriptive commit message"
   ```

   Use clear and descriptive commit messages that explain what changes were made and why.

2. **Push to your fork**:

   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create a Pull Request**:
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Select your fork and branch
   - Add a clear description of your changes
   - Reference any related issues

4. **Respond to feedback**: Be open to feedback and make requested changes if necessary.

### Keeping Your Fork Updated

To keep your fork up to date with the upstream repository:

```bash
# Add the upstream repository
git remote add upstream https://github.com/cognizant-ai-lab/neuro-san-studio.git

# Fetch changes from upstream
git fetch upstream

# Update your main branch
git checkout main
git merge upstream/main

# Update your feature branch (if needed)
git checkout feature/your-feature-name
git rebase main
```

Following this workflow will help ensure a smooth contribution process and maintain the project's quality standards.

## Reorganizing Agent Networks

When moving an agent network to a different directory (e.g., from root to an industry
subfolder), multiple files need to be updated to maintain consistency across the codebase.
This section provides a comprehensive checklist to ensure all references are properly updated.

### Files to Move

1. **Agent Configuration File** (`registries/<agent_name>.hocon`)
   - Move to appropriate subdirectory (e.g., `registries/industry/<agent_name>.hocon`)
   - Ensure metadata section is present with:
     - `description`: Brief description of the agent network
     - `tags`: Array of relevant tags (e.g., `["AAOSA", "industry-specific-tags"]`)
     - `sample_queries`: Array of 2-3 example queries users might ask

2. **Documentation File** (`docs/examples/<agent_name>.md`)
   - Move to corresponding subdirectory (e.g., `docs/examples/industry/<agent_name>.md`)

3. **Test Fixture** (`tests/fixtures/<agent_name>_test.hocon`)
   - Move to corresponding subdirectory (e.g., `tests/fixtures/industry/<agent_name>_test.hocon`)

### Files to Update

1. **Agent Documentation** (`docs/examples/industry/<agent_name>.md`)
   - Update file path reference in the `## File` section to reflect new location
   - Update test fixture path reference in the `## Testing` section
   - Adjust relative path depth (e.g., `../../` to `../../../` when moving into subfolder)

2. **Test Fixture** (`tests/fixtures/industry/<agent_name>_test.hocon`)
   - Update the `"agent"` field to include the subdirectory path
   - Example: `"agent": "cpg_agents"` becomes `"agent": "industry/cpg_agents"`

3. **Integration Test Suite** (`tests/integration/test_integration_test_hocons.py`)
   - Update the test file path in the `@parameterized.expand()` list
   - Example: `"cpg_agents_test.hocon"` becomes `"industry/cpg_agents_test.hocon"`
   - Ensure the test is in the appropriate test group (basic, industry, etc.)

4. **Manifest Files** (registry configuration)
   - `registries/manifest.hocon`: Update the agent path in the registry list
   - Example: `"cpg_agents.hocon": true` becomes `"industry/cpg_agents.hocon": true`

5. **Examples Index** (`docs/examples.md`)
   - Add or update the agent entry in the appropriate section
   - Update the documentation link to reflect the new path
   - Include description and tags

6. **External References** (other `.hocon` files)
   - Search for any `.hocon` files that reference this agent network as a tool or sub-agent
   - Update `external_network` or similar references to use the new path
   - Example: `"external_network": "airline_policy"` becomes
     `"external_network": "industry/airline_policy"`

7. **CodedTools Document Paths** (if applicable)
   - Check if any CodedTools reference document files from this agent network
   - Update file paths in the CodedTools to reflect the new location
   - Example: Policy documents or data files referenced by coded tools

### Checklist

Use this checklist when reorganizing an agent network:

- [ ] Move `.hocon` file to target directory
- [ ] Add/verify metadata in `.hocon` file (description, tags, sample_queries)
- [ ] Move documentation `.md` file to target directory
- [ ] Move test fixture `.hocon` file to target directory
- [ ] Update file path references in documentation `.md` file
- [ ] Update `"agent"` field in test fixture
- [ ] Update integration test suite to reference new test path
- [ ] Update `registries/manifest.hocon`
- [ ] Update `docs/examples.md` with new documentation path
- [ ] Update any `.hocon` files referencing this agent as a tool/sub-agent
- [ ] Update CodedTools document paths (if applicable)
- [ ] Run tests to verify all references are correct
- [ ] Create separate commits for each logical change

### Verification

After reorganization, verify the changes:

```bash
# Check that the agent loads correctly
python -m run

# Run integration tests
pytest tests/integration/test_integration_test_hocons.py -k "agent_name"

# Verify documentation links are not broken
# (manually check relative paths in documentation)
```
