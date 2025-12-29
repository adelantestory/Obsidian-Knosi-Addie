# Knosi Sync - Auto-start Scripts

Scripts to automatically start the Knosi sync client at login.

## macOS

```bash
# Install
./setup-mac.sh

# View logs
tail -f /tmp/knosi-sync.log

# Stop
launchctl unload ~/Library/LaunchAgents/ai.knosi.sync.plist

# Start
launchctl load ~/Library/LaunchAgents/ai.knosi.sync.plist

# Uninstall
launchctl unload ~/Library/LaunchAgents/ai.knosi.sync.plist
rm ~/Library/LaunchAgents/ai.knosi.sync.plist
```

## Windows

### With Administrator (Task Scheduler - Recommended)

```powershell
# Install
.\setup-windows.ps1

# View logs
Get-Content $env:TEMP\knosi-sync.log -Wait

# Stop
Stop-ScheduledTask -TaskName KnosiSync

# Start
Start-ScheduledTask -TaskName KnosiSync

# View status
Get-ScheduledTask -TaskName KnosiSync

# Uninstall
.\setup-windows.ps1 -Uninstall
```

### Without Administrator (Startup Folder)

```powershell
# Install
.\setup-windows.ps1 -UseStartupFolder

# View logs
Get-Content $env:TEMP\knosi-sync.log -Wait

# Uninstall
.\setup-windows.ps1 -Uninstall
```
