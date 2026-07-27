# Git Setup Commands

Follow these commands to initialize the Git repository and push to GitHub.

## Initialize Repository

```bash
# Initialize Git repository
git init

# Add all files
git add .

# Commit initial release
git commit -m "Initial release: AI LinkedIn Content Agent v1.0

- Multi-agent architecture with specialized agents
- AI-powered content planning and generation
- Web search integration
- Automated content review and improvement
- Image prompt generation and AI image generation
- Multiple writing styles and personalization
- User profile system
- Regeneration and edit workflows
- Rich terminal UI
- Complete documentation"

# Add remote repository 
git remote add origin https://github.com/think11723/LINKEDIN-AGENT.git

# Rename branch to main
git branch -M main

# Push to GitHub (first time)
git push -u origin main
```

## Verify Repository

After pushing, verify:

```bash
# Check remote
git remote -v

# Check status
git status

# View commit history
git log --oneline
```

## Note

- Replace `https://github.com/think11723/LINKEDIN-AGENT.git` with your actual repository URL
- Ensure you have created the repository on GitHub first
- The `.gitignore` file will prevent sensitive files from being committed
- `.env` file is excluded by .gitignore for security
