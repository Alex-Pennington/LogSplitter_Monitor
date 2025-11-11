# LogSplitter_Monitor Dual Remote Setup

## Overview

This repository is configured with dual Git remotes for redundancy and flexibility:

- **GitHub** (`origin`) - Public collaboration and sharing
- **GitMarv** (`gitmarv`) - Private backup and local control

## Current Configuration

### Remotes
```bash
origin   https://github.com/Alex-Pennington/LogSplitter_Monitor.git (fetch/push)
gitmarv  root@lilmarv.organicengineer.com:/opt/marvin/gitmarv/repositories/LogSplitter_Monitor.git (fetch/push)
```

### Authentication
- **GitHub**: HTTPS with personal access token
- **GitMarv**: SSH with Pageant authentication (`plink -batch`)

## VS Code Integration

### Available Tasks (F1 → Tasks: Run Task)

#### Git Operations
- **📡 Push to Both Remotes** - Pushes to both GitHub and GitMarv simultaneously
- **🐙 Push to GitHub Only** - GitHub-only push for public sharing
- **🏠 Push to GitMarv Only** - GitMarv-only push for private backup
- **🔗 Add GitMarv Remote** - Add GitMarv remote to new repositories
- **📋 Show Git Remotes** - Display current remote configuration

#### Build Operations (Existing)
- **🔧 Build Controller Program** - Build main monitor program
- **📤 Upload Controller Program** - Upload to Arduino hardware
- **🔍 Monitor Controller Serial** - Serial monitor output
- **🏗️ Build Both Programs** - Parallel build of all components

### Quick Access

**Default Build Task**: Ctrl+Shift+P → **Tasks: Run Build Task**

## Command Line Usage

### Daily Workflows

```powershell
# Push current branch to both remotes
git push origin cycle-metrics-update; git push gitmarv cycle-metrics-update

# Push main branch to both remotes  
git push origin main; git push gitmarv main

# Push all branches and tags
git push origin --all; git push gitmarv --all
git push origin --tags; git push gitmarv --tags
```

### Branch Management

```powershell
# Create new branch and push to both remotes
git checkout -b new-feature
git push origin new-feature
git push gitmarv new-feature

# Set upstream tracking for both remotes
git push -u origin new-feature
git push -u gitmarv new-feature
```

### Selective Operations

```powershell
# GitHub only (for public collaboration)
git push origin main

# GitMarv only (for private backup)
git push gitmarv main

# Fetch from both remotes
git fetch origin
git fetch gitmarv
```

## Repository Setup History

This repository was configured with dual remotes using these steps:

1. **Verified Pageant Configuration**:
   ```powershell
   git config --get core.sshCommand
   # Output: plink -batch
   ```

2. **Added GitMarv Remote**:
   ```powershell
   git remote add gitmarv root@lilmarv.organicengineer.com:/opt/marvin/gitmarv/repositories/LogSplitter_Monitor.git
   ```

3. **Created Repository on GitMarv**:
   ```bash
   # On GitMarv server
   cd /opt/marvin/gitmarv/repositories
   git init --bare LogSplitter_Monitor.git
   chown -R marvin:marvin LogSplitter_Monitor.git
   git config --global --add safe.directory /opt/marvin/gitmarv/repositories/LogSplitter_Monitor.git
   ```

4. **Initial Push to GitMarv**:
   ```powershell
   git push gitmarv main
   git push gitmarv cycle-metrics-update
   ```

## Benefits

### Development Advantages
- **Redundancy**: Code automatically backed up to both GitHub and private server
- **Flexibility**: Choose deployment target based on requirements (public vs private)
- **Local Control**: Complete repository control via GitMarv
- **Performance**: Local GitMarv server reduces latency for internal operations

### Operational Benefits
- **Seamless VS Code Integration**: One-click push to both remotes
- **Unified Authentication**: Pageant manages all SSH keys centrally
- **Automated Workflows**: Script-driven deployment and backup
- **Cross-Platform**: Compatible with existing PuTTY/Pageant infrastructure

## Security Considerations

- **SSH Key Management**: All authentication via Pageant with centralized key rotation
- **Network Security**: SSH encryption for GitMarv, HTTPS for GitHub
- **Access Control**: GitMarv provides private repository hosting
- **Backup Strategy**: Dual remotes provide natural disaster recovery

## Troubleshooting

### Permission Issues
If you get "dubious ownership" errors:
```bash
# On GitMarv server
git config --global --add safe.directory /opt/marvin/gitmarv/repositories/LogSplitter_Monitor.git
```

### Authentication Issues
1. Verify Pageant is running with SSH keys loaded
2. Test SSH connection: `plink -batch root@lilmarv.organicengineer.com`
3. Check Git SSH config: `git config --get core.sshCommand`

### Remote Management
```powershell
# View current remotes
git remote -v

# Update remote URLs
git remote set-url origin <new-github-url>
git remote set-url gitmarv <new-gitmarv-url>

# Remove and re-add remotes
git remote remove gitmarv
git remote add gitmarv root@lilmarv.organicengineer.com:/opt/marvin/gitmarv/repositories/LogSplitter_Monitor.git
```

## Next Steps

To apply this dual remote setup to other repositories:

1. **Global Configuration**: Ensure `git config --global core.sshCommand "plink -batch"`
2. **Create Repository on GitMarv**: Follow the server setup steps above
3. **Add Remote**: Use the "Add GitMarv Remote" VS Code task
4. **Copy Tasks**: Copy the Git tasks from `.vscode/tasks.json` to other projects
5. **Initial Push**: Push existing branches to GitMarv

---

**Setup Date**: November 2, 2025  
**Repository**: LogSplitter_Monitor  
**Author**: Dual Remote Configuration System