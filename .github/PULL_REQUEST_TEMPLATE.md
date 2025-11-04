## Description

<!-- Provide a clear and concise description of your changes -->

## Type of Change

<!-- Please delete options that are not relevant and check the box that applies -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] Test addition or improvement
- [ ] New agent network or example
- [ ] New coded tool

## Related Issues

<!-- Link to related issues using #issue_number or "Fixes #issue_number" if this PR closes an issue -->

Fixes #  
Related to #  

## Motivation and Context

<!-- Why is this change required? What problem does it solve? -->

## Changes Made

<!-- Provide a detailed list of changes made in this PR -->

-
-
-

## Testing Performed

<!-- Describe the testing you performed to verify your changes -->

### Manual Testing
- [ ] Tested locally with `python -m run`
- [ ] Tested with relevant agent networks
- [ ] Tested with different LLM providers (if applicable)

### Automated Testing
- [ ] Added new unit tests
- [ ] Added new integration tests
- [ ] All existing tests pass (`make test`)

### Test Details
<!-- Provide specific details about how you tested your changes -->



## Code Quality Checklist

- [ ] My code follows the style guidelines of this project (line length ≤ 119 characters)
- [ ] I have run `make lint` and `make lint-tests` (or equivalent on Windows)
- [ ] I have added docstrings to new functions, classes, and modules
- [ ] I have commented complex logic where necessary
- [ ] My changes generate no new warnings or errors

## Dependencies

<!-- IMPORTANT: Read this section carefully if you're adding new dependencies -->

**Modifying `./requirements.txt`:**
- [ ] I have NOT modified `./requirements.txt`, OR
- [ ] The new dependency is useful for everyone (core functionality, not specific to one coded tool/agent network/plugin)

**If adding dependencies for a specific coded tool, agent network, or plugin:**
- [ ] I have created a dedicated `requirements.txt` file in the appropriate directory (e.g., `coded_tools/my_tool/requirements.txt`)
- [ ] I have documented the dependency requirements in the relevant documentation (README, docstrings, or `docs/`)

**Note:** Only add to the main `./requirements.txt` if the library benefits all users. For tool-specific or network-specific dependencies, use a dedicated requirements file or clearly document them.

## Documentation

- [ ] I have updated relevant documentation in `docs/`
- [ ] I have updated the README.md (if needed)
- [ ] I have added/updated HOCON configuration examples (if applicable)
- [ ] I have added inline code comments where needed

## Breaking Changes

<!-- If this PR introduces breaking changes, describe them here and provide migration guidance -->

- [ ] No breaking changes
- [ ] Breaking changes (describe below)

**Breaking Changes Description:**


## Additional Notes

<!-- Add any other context, screenshots, or information about the PR here -->

### For New Coded Tools:
<!-- If you're adding a new coded tool, please answer these questions -->
- [ ] Tool is properly documented with docstrings
- [ ] Tool is added to the appropriate directory under `coded_tools/`
- [ ] Example HOCON configuration is provided
- [ ] Tests are included in `tests/coded_tools/`

### For New Agent Networks:
<!-- If you're adding a new agent network, please answer these questions -->
- [ ] HOCON configuration is in the `registries/` directory
- [ ] Network is documented in `docs/examples.md`
- [ ] Network has been tested end-to-end
- [ ] Any required coded tools are included or documented

## Deployment Notes

<!-- Any special considerations for deployment? Dependencies? Environment variables? -->



---

**By submitting this pull request, I confirm that my contribution is made under the terms of the project's [Academic Public License](../LICENSE.txt).**
