<#
.SYNOPSIS
    Installs or updates the S-Legal Antigravity Plugin and UTF-8 MCP Bridge on Windows.
.DESCRIPTION
    Supports both local cloned/staging execution (-SourceDir) and 1-command online install:
    irm https://raw.githubusercontent.com/Somsanl/s-legal-agent-kit/main/install-windows.ps1 | iex
#>
[CmdletBinding()]
param(
    [string]$SourceDir = "",
    [string]$HomeDir = "",
    [string]$BaseUrl = "",
    [switch]$SkipConfig,
    [switch]$SkipKey,
    [switch]$ForceRemoveGlobalCollision
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
try {
    [Console]::InputEncoding = $Utf8NoBom
    [Console]::OutputEncoding = $Utf8NoBom
} catch {
}

$RepoArchiveUrl = "https://github.com/Somsanl/s-legal-agent-kit/archive/refs/heads/main.zip"
$KeyRegex = '^slk_[0-9a-fA-F-]{36}_[A-Za-z0-9_-]{43}$'

function Write-Info([string]$Message) {
    Write-Host "[S-Legal] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Utf8NoBomFile([string]$Path, [string]$Content) {
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}

function Resolve-RealPython39Plus {
    $candidates = New-Object System.Collections.Generic.List[string]

    $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if (-not $pyLauncher) { $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue }
    if ($pyLauncher) {
        try {
            $resolved = & $pyLauncher.Source -3 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                $candidates.Add(($resolved | Select-Object -First 1).Trim())
            }
        } catch {
        }
    }

    foreach ($cmdName in @("python.exe", "python3.exe", "python")) {
        $cmds = Get-Command $cmdName -All -ErrorAction SilentlyContinue
        foreach ($c in $cmds) {
            if ($c.Source) {
                $candidates.Add($c.Source)
            }
        }
    }

    $seen = @{}
    foreach ($exe in $candidates) {
        if (-not $exe -or $seen.ContainsKey($exe)) { continue }
        $seen[$exe] = $true

        # Explicitly skip fake Microsoft Store WindowsApps shim
        if ($exe -like "*\Microsoft\WindowsApps\python*.exe") {
            continue
        }
        if (-not (Test-Path -LiteralPath $exe)) {
            continue
        }

        try {
            $ver = & $exe -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}'); sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return [PSCustomObject]@{
                    Path    = $exe
                    Version = ($ver | Select-Object -First 1).Trim()
                }
            }
        } catch {
        }
    }

    throw @"
ไม่พบ Python 3.9 ขึ้นไปบนเครื่อง (ข้าม Microsoft Store alias แล้ว)
กรุณาติดตั้ง Python 3.9+ จาก https://www.python.org/downloads/
โดยติ๊กถูกช่อง "Add python.exe to PATH" จากนั้นรันคำสั่งติดตั้งนี้อีกครั้ง
"@
}

function Resolve-HomeDirectory([string]$RequestedHome) {
    if ($RequestedHome -and $RequestedHome.Trim()) {
        $resolved = $RequestedHome.Trim()
        if (-not (Test-Path -LiteralPath $resolved)) {
            New-Item -ItemType Directory -Path $resolved -Force | Out-Null
        }
        return (Resolve-Path -LiteralPath $resolved).Path
    }
    if ($env:USERPROFILE -and $env:USERPROFILE.Trim()) {
        return $env:USERPROFILE.Trim()
    }
    return [Environment]::GetFolderPath("UserProfile")
}

function Test-IsSourceRoot([string]$Dir) {
    if (-not $Dir) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Dir "plugins\slegal\plugin.json")) -and
           (Test-Path -LiteralPath (Join-Path $Dir "mcp\bridge.py")) -and
           (Test-Path -LiteralPath (Join-Path $Dir "mcp\run-slegal-mcp.py"))
}

function Protect-PrivateFileAcl([string]$FilePath) {
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $grantArg = "*${sid}:(F)"
    $null = & icacls.exe $FilePath /inheritance:r /grant:r $grantArg 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "ไม่สามารถตั้งค่า ACL เฉพาะผู้ใช้บน $FilePath ด้วย icacls (รันต่อได้ แต่ควรตรวจสิทธิ์ไฟล์)"
    }
}

function ConvertTo-NormalizedEndpoint([string]$RawUrl, [bool]$AllowPlaceholder) {
    $trimmed = $RawUrl.Trim()
    if (-not $trimmed) {
        throw "S-Legal URL ต้องไม่เป็นค่าว่าง"
    }
    [Uri]$uri = $null
    if (-not [Uri]::TryCreate($trimmed, [UriKind]::Absolute, [ref]$uri)) {
        throw "รูปแบบ URL ไม่ถูกต้อง (ต้องเป็น https://...)"
    }
    $scheme = $uri.Scheme.ToLowerInvariant()
    $epHost = $uri.Host.ToLowerInvariant()
    if ($uri.UserInfo -or $uri.Query -or $uri.Fragment -or -not $epHost) {
        throw "URL ต้องไม่มีข้อมูลล็อกอิน พารามิเตอร์ หรือ #fragment"
    }
    if ($scheme -ne "https" -and -not ($scheme -eq "http" -and $epHost -in @("localhost", "127.0.0.1", "::1"))) {
        throw "S-Legal URL ต้องขึ้นต้นด้วย https://"
    }
    if (-not $AllowPlaceholder -and ($epHost -eq "example.com" -or $epHost.EndsWith(".example.com"))) {
        throw "กรุณาระบุ URL จริงของระบบ S-Legal ของสำนักงาน (ไม่ใช่ตัวอย่าง example.com)"
    }
    $path = $uri.AbsolutePath.TrimEnd("/")
    if ($path -eq "" -or $path -eq "/") {
        $normPath = "/api/mcp"
    } elseif ($path -eq "/api/mcp") {
        $normPath = "/api/mcp"
    } else {
        throw "URL ควรเป็น Base URL ของ S-Legal หรือลงท้ายด้วย /api/mcp"
    }
    $builder = New-Object System.UriBuilder($uri)
    $builder.Path = $normPath
    $builder.Query = ""
    $builder.Fragment = ""
    return $builder.Uri.AbsoluteUri.TrimEnd("/")
}

$TempExtractRoot = $null
try {
    Write-Info "กำลังตรวจสอบ Python 3.9+ และเตรียมการติดตั้ง S-Legal Agent Kit..."
    $pyInfo = Resolve-RealPython39Plus
    Write-Ok "พบ Python $($pyInfo.Version) ที่ $($pyInfo.Path)"

    $TargetHome = Resolve-HomeDirectory -RequestedHome $HomeDir
    Write-Info "โฟลเดอร์เป้าหมายผู้ใช้: $TargetHome"

    $KitRoot = $null
    if ($SourceDir -and $SourceDir.Trim()) {
        $KitRoot = (Resolve-Path -LiteralPath $SourceDir.Trim()).Path
        if (-not (Test-IsSourceRoot $KitRoot)) {
            throw "SourceDir ไม่ถูกต้อง: ไม่พบ plugins\slegal\plugin.json และ mcp\bridge.py ใน $KitRoot"
        }
    } elseif ($PSScriptRoot -and (Test-IsSourceRoot $PSScriptRoot)) {
        $KitRoot = $PSScriptRoot
    } else {
        $TempExtractRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("slegal-kit-" + [Guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $TempExtractRoot -Force | Out-Null
        $zipPath = Join-Path $TempExtractRoot "kit.zip"
        Write-Info "กำลังดาวน์โหลด S-Legal Agent Kit จาก GitHub..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
        Invoke-WebRequest -Uri $RepoArchiveUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $TempExtractRoot -Force
        $extracted = Get-ChildItem -LiteralPath $TempExtractRoot -Directory | Where-Object { Test-IsSourceRoot $_.FullName } | Select-Object -First 1
        if (-not $extracted) {
            throw "แตกไฟล์จาก GitHub ไม่สำเร็จ: ไม่พบโครงสร้างปลั๊กอิน"
        }
        $KitRoot = $extracted.FullName
    }

    # 1. Install/update MCP Bridge into ~/.slegal/mcp/ (NEVER touch endpoint or api_key)
    $McpDestDir = Join-Path $TargetHome ".slegal\mcp"
    New-Item -ItemType Directory -Path $McpDestDir -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $KitRoot "mcp\bridge.py") -Destination (Join-Path $McpDestDir "bridge.py") -Force
    Copy-Item -LiteralPath (Join-Path $KitRoot "mcp\run-slegal-mcp.py") -Destination (Join-Path $McpDestDir "run-slegal-mcp.py") -Force
    $RunScriptPath = Join-Path $McpDestDir "run-slegal-mcp.py"
    Write-Ok "ติดตั้ง MCP Bridge UTF-8 ลง $McpDestDir เรียบร้อย"

    # 2. Install/update Native Plugin into ~/.gemini/config/plugins/slegal/
    $GeminiConfigDir = Join-Path $TargetHome ".gemini\config"
    $PluginDestDir = Join-Path $GeminiConfigDir "plugins\slegal"
    if (Test-Path -LiteralPath $PluginDestDir) {
        Remove-Item -LiteralPath $PluginDestDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $PluginDestDir -Force | Out-Null
    Copy-Item -Path (Join-Path $KitRoot "plugins\slegal\*") -Destination $PluginDestDir -Recurse -Force

    # 3. Write machine-resolved mcp_config.json inside the plugin (UTF-8 enforced for Windows cp874 safety)
    $McpConfigObject = [ordered]@{
        mcpServers = [ordered]@{
            slegal = [ordered]@{
                command = $pyInfo.Path
                args    = @("-X", "utf8", $RunScriptPath)
                env     = [ordered]@{
                    PYTHONUTF8       = "1"
                    PYTHONIOENCODING = "utf-8"
                }
            }
        }
    }
    $McpConfigJson = ($McpConfigObject | ConvertTo-Json -Depth 6) + "`n"
    Write-Utf8NoBomFile -Path (Join-Path $PluginDestDir "mcp_config.json") -Content $McpConfigJson
    Write-Ok "ติดตั้งปลั๊กอินและตั้งค่า mcp_config.json (-X utf8) ใน $PluginDestDir เรียบร้อย"

    # 4. Check legacy global ~/.gemini/config/mcp_config.json collision
    $GlobalMcpPath = Join-Path $GeminiConfigDir "mcp_config.json"
    if (Test-Path -LiteralPath $GlobalMcpPath) {
        try {
            $globalRaw = [System.IO.File]::ReadAllText($GlobalMcpPath, $Utf8NoBom)
            $globalObj = $globalRaw | ConvertFrom-Json
            if ($globalObj -and $globalObj.PSObject.Properties["mcpServers"] -and $globalObj.mcpServers -and $globalObj.mcpServers.PSObject.Properties["slegal"]) {
                $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
                $backupPath = "$GlobalMcpPath.bak.$stamp"
                Copy-Item -LiteralPath $GlobalMcpPath -Destination $backupPath -Force
                Write-Warn "พบการตั้งค่า 'slegal' เดิมซ้ำซ้อนใน $GlobalMcpPath (สำรองไว้ที่ $backupPath)"

                $shouldRemove = [bool]$ForceRemoveGlobalCollision
                if (-not $shouldRemove -and [Environment]::UserInteractive -and -not $SkipKey -and -not $SkipConfig) {
                    $ans = Read-Host "ต้องการลบเฉพาะคีย์ 'slegal' ออกจาก Global mcp_config.json เพื่อไม่ให้ชนกับปลั๊กอินหรือไม่? (Y/n)"
                    if (-not $ans -or $ans.Trim().ToLowerInvariant() -in @("y", "yes")) {
                        $shouldRemove = $true
                    }
                }
                if ($shouldRemove) {
                    $globalObj.mcpServers.PSObject.Properties.Remove("slegal")
                    $updatedGlobalJson = ($globalObj | ConvertTo-Json -Depth 16) + "`n"
                    Write-Utf8NoBomFile -Path $GlobalMcpPath -Content $updatedGlobalJson
                    Write-Ok "ลบคีย์ 'slegal' ที่ซ้ำซ้อนออกจาก Global mcp_config.json แล้ว (เซิร์ฟเวอร์ MCP อื่นคงเดิม 100%)"
                } else {
                    Write-Warn "กรุณาลบ 'slegal' ออกจาก $GlobalMcpPath ด้วยตนเองเพื่อป้องกันการโหลด MCP ซ้ำ"
                }
            }
        } catch {
            Write-Warn "ไม่สามารถตรวจสอบ $GlobalMcpPath อัตโนมัติได้: $($_.Exception.Message)"
        }
    }

    # 5A. S-Legal Endpoint onboarding (~/.slegal/mcp/endpoint)
    $EndpointFilePath = Join-Path $McpDestDir "endpoint"
    $HasExistingEndpoint = $false
    if (Test-Path -LiteralPath $EndpointFilePath) {
        $epItem = Get-Item -LiteralPath $EndpointFilePath -Force
        if ($epItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "ไฟล์ $EndpointFilePath เป็น symlink/reparse point ซึ่งไม่อนุญาต กรุณาลบและสร้างใหม่"
        }
        $epExisting = ([System.IO.File]::ReadAllText($EndpointFilePath, $Utf8NoBom)).Trim()
        if ($epExisting.Length -gt 0) {
            $HasExistingEndpoint = $true
            Write-Ok "พบ S-Legal Endpoint เดิมที่ $EndpointFilePath — คงไว้ไม่เปลี่ยนแปลง"
        }
    }

    $UsedPlaceholderEndpoint = $false
    if (-not $HasExistingEndpoint) {
        if ($SkipConfig) {
            Write-Warn "ข้ามการตั้งค่า Endpoint (-SkipConfig) — ก่อนใช้งานจริงให้นำ URL ใส่ใน $EndpointFilePath"
        } else {
            $rawEndpoint = $BaseUrl
            if (-not $rawEndpoint -or -not $rawEndpoint.Trim()) {
                Write-Host ""
                Write-Info "กรุณากรอก S-Legal URL ของสำนักงานท่าน (เช่น https://your-slegal-host.example.com)"
                $rawEndpoint = Read-Host "S-Legal Base URL"
            }
            $allowPlaceholder = [bool]($SkipKey -or $SkipConfig)
            $normalizedEndpoint = ConvertTo-NormalizedEndpoint -RawUrl $rawEndpoint -AllowPlaceholder $allowPlaceholder
            $epUri = [Uri]$normalizedEndpoint
            if ($epUri.Host.ToLowerInvariant() -eq "example.com" -or $epUri.Host.ToLowerInvariant().EndsWith(".example.com")) {
                $UsedPlaceholderEndpoint = $true
            }
            Write-Utf8NoBomFile -Path $EndpointFilePath -Content ($normalizedEndpoint + "`n")
            Protect-PrivateFileAcl -FilePath $EndpointFilePath
            Write-Ok "บันทึก S-Legal Endpoint ลง $EndpointFilePath เรียบร้อย"
        }
    } elseif ($BaseUrl -and $BaseUrl.Trim()) {
        $epUriCheck = [Uri]([System.IO.File]::ReadAllText($EndpointFilePath, $Utf8NoBom)).Trim()
        if ($epUriCheck.Host.ToLowerInvariant() -eq "example.com" -or $epUriCheck.Host.ToLowerInvariant().EndsWith(".example.com")) {
            $UsedPlaceholderEndpoint = $true
        }
    }

    # 5B. Personal API Key onboarding (~/.slegal/mcp/api_key)
    $KeyFilePath = Join-Path $McpDestDir "api_key"
    $HasValidExistingKey = $false
    if (Test-Path -LiteralPath $KeyFilePath) {
        $existingItem = Get-Item -LiteralPath $KeyFilePath -Force
        if ($existingItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "ไฟล์ $KeyFilePath เป็น symlink/reparse point ซึ่งไม่อนุญาต กรุณาลบและสร้างใหม่"
        }
        $existingText = ([System.IO.File]::ReadAllText($KeyFilePath, $Utf8NoBom)).Trim()
        if ($existingText.Length -gt 0) {
            $HasValidExistingKey = $true
            Write-Ok "พบ API Key เดิมที่ $KeyFilePath — คงไว้ไม่เปลี่ยนแปลง"
        }
    }

    if (-not $HasValidExistingKey) {
        if ($SkipKey -or $SkipConfig) {
            Write-Warn "ข้ามการกรอก API Key (-SkipKey) — ก่อนใช้งานจริงให้นำคีย์มาใส่ใน $KeyFilePath"
        } else {
            Write-Host ""
            Write-Info "กรุณาวาง S-Legal API Key ของท่าน (จากเมนู ตั้งค่า > Integrations ใน S-Legal)"
            $plainKey = $null
            $bstr = [IntPtr]::Zero
            $secureKey = Read-Host "S-Legal API Key (ตัวอักษรจะถูกซ่อน)" -AsSecureString
            try {
                $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
                $plainKey = ([System.Runtime.InteropServices.Marshal]::PtrToStringUni($bstr)).Trim()
            } finally {
                if ($bstr -ne [IntPtr]::Zero) {
                    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
                }
                if ($secureKey) { $secureKey.Dispose() }
            }

            if (-not $plainKey -or ($plainKey -notmatch $KeyRegex)) {
                throw "รูปแบบ API Key ไม่ถูกต้อง (ต้องขึ้นต้นด้วย slk_ ตามมาตรฐาน S-Legal) — ไม่ได้บันทึกไฟล์"
            }

            Write-Utf8NoBomFile -Path $KeyFilePath -Content ($plainKey + "`n")
            $plainKey = $null
            Protect-PrivateFileAcl -FilePath $KeyFilePath
            Write-Ok "บันทึก API Key ลง $KeyFilePath และล็อกสิทธิ์เฉพาะผู้ใช้ปัจจุบันเรียบร้อย"
        }
    }

    # 6. Post-install self-check
    Write-Info "กำลังตรวจสอบการทำงานของ MCP Bridge (--check)..."
    $prevKeyEnv = $env:SLEGAL_API_KEY_FILE
    $prevUrlEnv = $env:SLEGAL_MCP_URL_FILE
    try {
        $env:SLEGAL_API_KEY_FILE = $KeyFilePath
        $env:SLEGAL_MCP_URL_FILE = $EndpointFilePath
        $checkArgs = @("-X", "utf8", $RunScriptPath, "--check")
        if (($SkipKey -or $SkipConfig) -and -not (Test-Path -LiteralPath $KeyFilePath)) {
            $checkArgs += "--allow-missing-key"
        }
        if ($SkipConfig -and -not (Test-Path -LiteralPath $EndpointFilePath)) {
            $checkArgs += "--allow-missing-config"
        }
        if ($UsedPlaceholderEndpoint -and ($SkipKey -or $SkipConfig)) {
            $checkArgs += "--allow-placeholder-endpoint"
        }
        $checkOutput = & $pyInfo.Path @checkArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "การตรวจสอบ MCP Bridge ไม่ผ่าน: $($checkOutput -join ' ')"
        }
        Write-Ok "MCP Bridge Self-Check ผ่าน: $($checkOutput | Select-Object -First 1)"
    } finally {
        if ($null -eq $prevKeyEnv) {
            Remove-Item Env:SLEGAL_API_KEY_FILE -ErrorAction SilentlyContinue
        } else {
            $env:SLEGAL_API_KEY_FILE = $prevKeyEnv
        }
        if ($null -eq $prevUrlEnv) {
            Remove-Item Env:SLEGAL_MCP_URL_FILE -ErrorAction SilentlyContinue
        } else {
            $env:SLEGAL_MCP_URL_FILE = $prevUrlEnv
        }
    }

    $agyCmd = Get-Command "agy.exe" -ErrorAction SilentlyContinue
    if (-not $agyCmd) { $agyCmd = Get-Command "agy" -ErrorAction SilentlyContinue }
    if (-not $agyCmd) {
        $fallbackAgy = Join-Path $env:LOCALAPPDATA "agy\bin\agy.exe"
        if (Test-Path -LiteralPath $fallbackAgy) {
            $agyCmd = [PSCustomObject]@{ Source = $fallbackAgy }
        }
    }
    if ($agyCmd) {
        $valOut = & $agyCmd.Source plugin validate $PluginDestDir --strict --json 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "agy plugin validate ไม่ผ่าน: $($valOut -join ' ')"
        }
        Write-Ok "agy plugin validate --strict ผ่าน (0 errors, 0 warnings)"
    } else {
        Write-Info "ไม่พบคำสั่ง agy ใน PATH (สามารถเปิด Antigravity Desktop ได้ตามปกติ)"
    }

    Write-Host ""
    Write-Ok "ติดตั้ง/อัปเดต S-Legal Agent Kit เสร็จสมบูรณ์!"
    Write-Host "ขั้นตอนถัดไป: รีสตาร์ท Antigravity แล้วลองพิมพ์ `"เช็กสิทธิ์ S-Legal ของฉัน`"" -ForegroundColor White
} finally {
    if ($TempExtractRoot -and (Test-Path -LiteralPath $TempExtractRoot)) {
        Remove-Item -LiteralPath $TempExtractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
