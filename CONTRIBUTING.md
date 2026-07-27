# Contributing to AI LinkedIn Content Agent

Thank you for your interest in contributing to the AI LinkedIn Content Agent! This document provides guidelines and instructions for contributing to the project.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

---

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md) to ensure a welcoming and inclusive environment for all contributors.

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- A GitHub account
- A Gemini API key (for testing)

### Setup Development Environment

1. **Fork the Repository**

   Click the "Fork" button on the GitHub repository page to create your own copy.

2. **Clone Your Fork**

   ```bash
   git clone https://github.com/YOUR_USERNAME/LINKEDIN-AGENT.git
   cd LINKEDIN-AGENT
   ```

3. **Create Virtual Environment**

   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Linux/Mac
   source .venv/bin/activate
   ```

4. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Configure Environment**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   MODEL_NAME=gemini-3.5-flash
   TEMPERATURE=0.7
   ```

6. **Set Up Profile**

   ```bash
   cp profile/profile.template.json profile/profile.json
   ```

   Edit `profile/profile.json` with your information.

7. **Run the Application**

   ```bash
   python main.py
   ```

---

## Development Workflow

### Branch Strategy

- `main` - Stable production code
- `develop` - Integration branch for features
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches
- `hotfix/*` - Critical hotfixes

### Creating a Branch

```bash
git checkout -b feature/your-feature-name
```

### Making Changes

1. **Write Code**
   - Follow the coding standards (see below)
   - Add comments for complex logic
   - Update documentation as needed

2. **Test Your Changes**
   - Run the application manually
   - Test the specific feature you're working on
   - Ensure existing functionality still works

3. **Commit Your Changes**

   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

   Use conventional commit messages:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `style:` - Code style changes (formatting)
   - `refactor:` - Code refactoring
   - `test:` - Adding or updating tests
   - `chore:` - Maintenance tasks

4. **Push to GitHub**

   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create Pull Request**

   - Go to the GitHub repository
   - Click "New Pull Request"
   - Select your branch
   - Fill in the PR template
   - Submit for review

---

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use type hints for function signatures
- Add docstrings for all functions and classes

### Example Code Style

```python
"""Module description."""

from typing import List, Optional
from pydantic import BaseModel


class ExampleModel(BaseModel):
    """Description of the model."""
    
    field_name: str = Field(description="Field description")


def example_function(param: str, optional_param: Optional[int] = None) -> str:
    """Description of the function.
    
    Args:
        param: Description of param.
        optional_param: Description of optional_param.
        
    Returns:
        Description of return value.
    """
    # Implementation
    return result
```

### File Organization

- Keep files focused on a single responsibility
- Use descriptive file and variable names
- Group related functionality in modules
- Add `__init__.py` for packages

### Imports

- Order imports: standard library, third-party, local
- Use absolute imports for local modules
- Remove unused imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

# Local
from utils.config import config
from utils.models import LinkedInPost
```

### Error Handling

- Use specific exception types
- Provide meaningful error messages
- Log errors appropriately
- Handle exceptions gracefully

```python
try:
    result = some_function()
except SpecificError as e:
    console.print(f"[red]Error: {str(e)}[/red]")
    return None
```

### Documentation

- Update README.md for user-facing changes
- Update PROJECT_ARCHITECTURE.md for architectural changes
- Add inline comments for complex logic
- Update CHANGELOG.md for significant changes

---

## Submitting Changes

### Pull Request Checklist

Before submitting a PR, ensure:

- [ ] Code follows project coding standards
- [ ] Code is tested and working
- [ ] Documentation is updated
- [ ] Commit messages follow conventional format
- [ ] PR description is clear and complete
- [ ] No sensitive data is included
- [ ] `.env` file is not committed

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How did you test this change?

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
- [ ] Tests added/updated
```

---

## Reporting Issues

### Bug Reports

When reporting a bug, please include:

1. **Description** - Clear description of the bug
2. **Steps to Reproduce** - Steps to reproduce the behavior
3. **Expected Behavior** - What you expected to happen
4. **Actual Behavior** - What actually happened
5. **Environment** - Python version, OS, etc.
6. **Logs** - Relevant error messages or logs

### Issue Template

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Python version:
- OS:
- Dependencies:

## Logs/Error Messages
```

---

## Feature Requests

### Proposing a Feature

When proposing a new feature:

1. **Check Existing Issues** - Ensure it hasn't been requested already
2. **Use the Template** - Fill out the feature request template
3. **Provide Context** - Explain why this feature is needed
4. **Suggest Implementation** - If you have ideas on how to implement it

### Feature Request Template

```markdown
## Feature Description
Clear description of the feature

## Use Case
Why is this feature needed?

## Proposed Solution
How should this work?

## Alternatives Considered
What alternatives did you consider?

## Additional Context
Any other relevant information
```

---

## Areas for Contribution

### Good First Issues

Look for issues labeled `good first issue` for beginner-friendly contributions.

### Documentation

- Improve README.md
- Add code examples
- Fix typos
- Improve inline documentation
- Add tutorials

### Features

- Add new writing styles
- Add new image styles
- Implement LinkedIn API integration
- Add content scheduling
- Add analytics tracking

### Bug Fixes

- Fix reported bugs
- Improve error handling
- Fix edge cases
- Improve performance

### Testing

- Add unit tests
- Add integration tests
- Improve test coverage
- Add test data

---

## Questions?

If you have questions:

1. Check existing documentation
2. Search existing issues and discussions
3. Open a new discussion on GitHub
4. Contact maintainers

---

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing! 🎉
