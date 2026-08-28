[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidatePattern('^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')]
    [string]$Version,

    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$PythonCommand = "python",
    [string]$CommitMessage,
    [switch]$Yes,
    [switch]$SkipChecks,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($ArgumentList -join ' ')"
    }
}

function Get-NativeOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    $output = & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath $($ArgumentList -join ' ')"
    }
    return ($output -join "`n").Trim()
}

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$versionTool = Join-Path $repositoryRoot "scripts\set_version.py"
$workflowFile = Join-Path $repositoryRoot ".github\workflows\release.yml"
$tagName = "v$Version"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git was not found in PATH."
}
if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python command '$PythonCommand' was not found in PATH."
}
if (-not (Test-Path -LiteralPath $versionTool)) {
    throw "Version synchronization tool is missing: $versionTool"
}
if (-not (Test-Path -LiteralPath $workflowFile)) {
    throw "GitHub release workflow is missing: $workflowFile"
}

Push-Location $repositoryRoot
try {
    $gitRoot = Get-NativeOutput "git" @("rev-parse", "--show-toplevel")
    $resolvedGitRoot = [System.IO.Path]::GetFullPath($gitRoot)
    if ($resolvedGitRoot -ne $repositoryRoot) {
        throw "Run this script from the Glimpse repository; detected Git root: $resolvedGitRoot"
    }

    $currentBranch = Get-NativeOutput "git" @("branch", "--show-current")
    if (-not $currentBranch) {
        throw "Releases cannot be created from a detached HEAD."
    }
    if ($currentBranch -ne $Branch) {
        throw "Current branch is '$currentBranch'; expected release branch '$Branch'."
    }

    $unmerged = Get-NativeOutput "git" @("diff", "--name-only", "--diff-filter=U")
    if ($unmerged) {
        throw "Resolve merge conflicts before releasing:`n$unmerged"
    }

    [void](Get-NativeOutput "git" @("remote", "get-url", $Remote))

    & git show-ref --verify --quiet "refs/tags/$tagName"
    if ($LASTEXITCODE -eq 0) {
        throw "Local tag $tagName already exists."
    }
    if ($LASTEXITCODE -ne 1) {
        throw "Unable to inspect local tag $tagName."
    }

    $currentVersionText = Get-NativeOutput $PythonCommand @($versionTool, "--current")
    if ($currentVersionText -notmatch '^(?<major>0|[1-9]\d*)\.(?<minor>0|[1-9]\d*)\.(?<patch>0|[1-9]\d*)(?<prerelease>-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$') {
        throw "Current version $currentVersionText is not valid SemVer."
    }
    $currentVersion = [System.Version]::new(
        [int]$Matches.major,
        [int]$Matches.minor,
        [int]$Matches.patch
    )
    $targetVersion = [System.Version]::Parse($Version)
    $currentIsPrerelease = -not [string]::IsNullOrEmpty($Matches.prerelease)
    if ($targetVersion -lt $currentVersion -or ($targetVersion -eq $currentVersion -and -not $currentIsPrerelease)) {
        throw "Release version $Version must be greater than current version $currentVersionText."
    }

    if (-not $DryRun) {
        & git ls-remote --exit-code --tags $Remote "refs/tags/$tagName" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            throw "Remote tag $tagName already exists on $Remote."
        }
        if ($LASTEXITCODE -ne 2) {
            throw "Unable to check tag $tagName on remote $Remote."
        }
    }

    $versionArguments = @($versionTool, $Version)
    if ($DryRun) {
        $versionArguments += "--dry-run"
    }
    Invoke-NativeCommand $PythonCommand $versionArguments

    if ($DryRun) {
        Write-Host ""
        Write-Host "Dry run completed. No files, commits, tags, or remotes were changed."
        Write-Host "Planned release:"
        Write-Host "  Version: $Version"
        Write-Host "  Commit:  release: 发布 $tagName"
        Write-Host "  Push:    $Remote/$Branch and $tagName (atomic)"
        return
    }

    Invoke-NativeCommand $PythonCommand @(
        $versionTool,
        "--check",
        "--expected",
        $Version
    )

    if (-not $SkipChecks) {
        Invoke-NativeCommand $PythonCommand @(
            "-m",
            "pytest",
            "tests/unit/test_set_version.py",
            "tests/unit/test_runtime_env.py",
            "-q"
        )
        Invoke-NativeCommand "git" @("diff", "--check")
    }

    $changes = Get-NativeOutput "git" @("status", "--short")
    Write-Host ""
    Write-Host "Release plan"
    Write-Host "  Version: $Version"
    Write-Host "  Branch:  $Branch"
    Write-Host "  Remote:  $Remote"
    if ($changes) {
        Write-Host "  Changes:"
        $changes -split "`n" | ForEach-Object { Write-Host "    $_" }
    } else {
        Write-Host "  Changes: none (the current commit will be tagged)"
    }

    if (-not $Yes) {
        $confirmation = Read-Host "Type '$tagName' to commit all listed changes and publish"
        if ($confirmation -ne $tagName) {
            throw "Release cancelled; confirmation did not match $tagName."
        }
    }

    Invoke-NativeCommand "git" @("add", "--all")

    & git diff --cached --quiet
    $stagedDiffExitCode = $LASTEXITCODE
    if ($stagedDiffExitCode -eq 1) {
        if (-not $CommitMessage) {
            $CommitMessage = "release: 发布 $tagName"
        }
        Invoke-NativeCommand "git" @("commit", "-m", $CommitMessage)
    } elseif ($stagedDiffExitCode -ne 0) {
        throw "Unable to inspect staged changes."
    }

    Invoke-NativeCommand "git" @("tag", "-a", $tagName, "-m", "Glimpse $tagName")
    Invoke-NativeCommand "git" @(
        "push",
        "--atomic",
        $Remote,
        "HEAD:refs/heads/$Branch",
        "refs/tags/$tagName"
    )

    Write-Host ""
    Write-Host "Published $tagName. GitHub Actions is building the Windows installer."
} finally {
    Pop-Location
}
