import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell is required for setup scripts")


@pytest.fixture
def project(tmp_path):
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    (tmp_path / "backend").mkdir()
    shutil.copyfile(ROOT / ".env.example", tmp_path / ".env.example")
    shutil.copyfile(ROOT / "backend/.env.example", tmp_path / "backend/.env.example")
    return tmp_path


def read_env(path):
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if "=" in line and not line.startswith("#")
    )


def run_script(project, script, prelude=""):
    harness = project / "harness.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        + prelude
        + f"\n& (Join-Path $PSScriptRoot 'scripts/{script}')\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(harness)],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_initialize_generates_independent_passwords_and_preserves_existing_values(project):
    result = run_script(project, "Initialize-Env.ps1")
    assert result.returncode == 0, "Environment initialization failed"
    root = read_env(project / ".env")
    backend = read_env(project / "backend/.env")
    assert len(root["MYSQL_PASSWORD"]) == len(root["MYSQL_ROOT_PASSWORD"]) == 64
    assert root["MYSQL_PASSWORD"] != root["MYSQL_ROOT_PASSWORD"]
    assert backend["DATABASE_PASSWORD"] == root["MYSQL_PASSWORD"]
    assert root["MYSQL_PASSWORD"] not in result.stdout + result.stderr
    assert run_script(project, "Initialize-Env.ps1").returncode == 0
    assert read_env(project / ".env") == root


def test_rotation_synchronizes_only_after_database_verification(project):
    assert run_script(project, "Initialize-Env.ps1").returncode == 0
    original = read_env(project / ".env")
    result = run_script(
        project,
        "Rotate-DatabaseCredentials.ps1",
        r"""
function docker {
    $sqlInput = @($input) -join "`n"
    $global:LASTEXITCODE = 0
    if ($sqlInput.Contains('SELECT User, Host')) {
        "root`tlocalhost"
        "root`t%"
        "tickets_app`t%"
    } elseif ($sqlInput.Contains('ALTER USER')) {
        if (!$sqlInput.Contains("'tickets_app'@'%' IDENTIFIED BY")) { throw 'Missing app rotation' }
        if (!$sqlInput.Contains("'root'@'localhost' IDENTIFIED BY")) {
            throw 'Missing root rotation'
        }
        $pending = Read-ProjectEnv (Join-Path $PSScriptRoot '.env.rotation')
        $active = Read-ProjectEnv (Join-Path $PSScriptRoot '.env')
        if ($pending['MYSQL_PASSWORD'] -eq $active['MYSQL_PASSWORD']) {
            throw 'Active credentials changed before database verification'
        }
    } else { '1' }
}
""",
    )
    assert result.returncode == 0, "Simulated credential rotation failed"
    updated = read_env(project / ".env")
    assert updated["MYSQL_PASSWORD"] != original["MYSQL_PASSWORD"]
    assert updated["MYSQL_ROOT_PASSWORD"] != original["MYSQL_ROOT_PASSWORD"]
    assert read_env(project / "backend/.env")["DATABASE_PASSWORD"] == updated["MYSQL_PASSWORD"]
    assert not (project / ".env.rotation").exists()
    assert updated["MYSQL_PASSWORD"] not in result.stdout + result.stderr


def test_failed_rotation_preserves_active_env_and_retains_pending_passwords(project):
    assert run_script(project, "Initialize-Env.ps1").returncode == 0
    original = (project / ".env").read_bytes()
    result = run_script(
        project,
        "Rotate-DatabaseCredentials.ps1",
        r"""
function docker { $global:LASTEXITCODE = 1 }
""",
    )
    assert result.returncode != 0
    assert (project / ".env").read_bytes() == original
    pending = read_env(project / ".env.rotation")
    assert len(pending["MYSQL_PASSWORD"]) == 64
    assert pending["MYSQL_PASSWORD"] not in result.stdout + result.stderr


def test_interrupted_rotation_resumes_with_pending_root_password(project):
    assert run_script(project, "Initialize-Env.ps1").returncode == 0
    original = (project / ".env").read_bytes()
    (project / "fail-verification").touch()
    prelude = r"""
function docker {
    $sqlInput = @($input) -join "`n"
    $global:LASTEXITCODE = 0
    $marker = Join-Path $PSScriptRoot 'database-updated'
    if ($sqlInput.Contains('SELECT User, Host')) {
        $active = Read-ProjectEnv (Join-Path $PSScriptRoot '.env')
        if ((Test-Path $marker) -and $sqlInput.StartsWith($active['MYSQL_ROOT_PASSWORD'])) {
            $global:LASTEXITCODE = 1
            return
        }
        "root`tlocalhost"
        "tickets_app`t%"
    } elseif ($sqlInput.Contains('ALTER USER')) {
        [IO.File]::WriteAllText($marker, 'updated')
    } elseif (Test-Path (Join-Path $PSScriptRoot 'fail-verification')) {
        $global:LASTEXITCODE = 1
    } else { '1' }
}
"""
    assert run_script(project, "Rotate-DatabaseCredentials.ps1", prelude).returncode != 0
    assert (project / ".env").read_bytes() == original
    pending = read_env(project / ".env.rotation")
    (project / "fail-verification").unlink()
    assert run_script(project, "Rotate-DatabaseCredentials.ps1", prelude).returncode == 0
    assert read_env(project / ".env")["MYSQL_ROOT_PASSWORD"] == pending["MYSQL_ROOT_PASSWORD"]
    assert not (project / ".env.rotation").exists()
