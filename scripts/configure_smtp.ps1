param(
    [switch]$SendTrial
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DefaultHost = "smtp.office365.com"
$DefaultPort = "587"
$DefaultSenderName = "KPKAUE Fortune QA"

function Read-WithDefault($Prompt, $Default) {
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value.Trim()
}

function Set-UserEnv($Name, $Value) {
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value
}

Write-Host "SMTP setup for QA/QC calibration reminder emails" -ForegroundColor Cyan
Write-Host "For Microsoft 365, use smtp.office365.com, port 587, STARTTLS enabled." -ForegroundColor DarkGray
Write-Host ""

$HostName = Read-WithDefault "SMTP host" $DefaultHost
$Port = Read-WithDefault "SMTP port" $DefaultPort
$User = Read-Host "Sender mailbox / SMTP username"
if ([string]::IsNullOrWhiteSpace($User)) {
    throw "Sender mailbox / SMTP username is required."
}

$From = Read-WithDefault "Sender email address" $User
$FromName = Read-WithDefault "Sender display name" $DefaultSenderName
$SecurePassword = Read-Host "SMTP password or app password" -AsSecureString
$PasswordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
try {
    $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($PasswordPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($PasswordPtr)
}

if ([string]::IsNullOrWhiteSpace($Password)) {
    throw "SMTP password is required."
}

Set-UserEnv "SMTP_HOST" $HostName
Set-UserEnv "SMTP_PORT" $Port
Set-UserEnv "SMTP_USER" $User
Set-UserEnv "SMTP_PASSWORD" $Password
Set-UserEnv "SMTP_FROM" $From
Set-UserEnv "SMTP_STARTTLS" "1"
Set-UserEnv "SMTP_SSL" "0"
Set-UserEnv "CALIBRATION_EMAIL_FROM_NAME" $FromName

Write-Host ""
Write-Host "SMTP settings saved to the current Windows user environment." -ForegroundColor Green
Write-Host "Sender display name: $FromName"
Write-Host "Sender email: $From"
Write-Host ""

if ($SendTrial) {
    Push-Location $ProjectRoot
    try {
        py -c "import scripts.calibration_reminder as r; df=r.load_due_records(); msg=r.message_from_records(df.head(10), limit=None); r.send_email(msg); print(f'Trial email sent for {min(len(df), 10)} calibration record(s).')"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "To send a trial email now, run:" -ForegroundColor Yellow
    Write-Host "powershell -ExecutionPolicy Bypass -File .\scripts\configure_smtp.ps1 -SendTrial"
}
