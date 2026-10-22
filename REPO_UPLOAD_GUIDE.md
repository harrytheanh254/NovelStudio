# NovelStudio repository guide

Repository: https://github.com/harrytheanh254/NovelStudio

## Download and run
1. Use Code → Download ZIP and extract it to D:\NovelStudio.
2. Install Git for Windows, Python 3.12 and Chrome if not already installed.
3. Follow the setup instructions in README.md.
4. Third-party repos, Python environments and model weights are not bundled.

## Publishing local changes
The included publish script targets this repository and stages only application source, setup scripts, test helpers, requirements and documentation. It excludes vendor, envs, models, cache, data, temporary files, novels, MP3s and credentials.

The script may prompt for a Git commit name and email. These are commit metadata, not your GitHub password. You can set them in the repository with git config user.name and git config user.email. Git Credential Manager may open a browser to sign in.

Never put passwords, tokens, private novels or personal audio into Git.
