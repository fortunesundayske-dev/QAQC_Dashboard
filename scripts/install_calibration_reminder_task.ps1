$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = "C:\Users\evome\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$ReminderScript = Join-Path $ProjectRoot "scripts\calibration_reminder.py"
$TaskName = "QAQC Calibration Reminder"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}

if (-not (Test-Path -LiteralPath $ReminderScript)) {
    throw "Reminder script not found: $ReminderScript"
}

$Action = New-ScheduledTaskAction -Execute $Python -Argument "`"$ReminderScript`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Write-Host "Installed '$TaskName'. It will check calibration reminders every day at 9:00 AM."
