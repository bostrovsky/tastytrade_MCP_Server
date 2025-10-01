#!/usr/bin/env python3
"""Check development environment setup."""
import subprocess
import sys
from pathlib import Path


def check_command(command: str, name: str) -> bool:
    """Check if a command is available."""
    try:
        subprocess.run(
            [command, "--version"],
            capture_output=True,
            check=False,
            timeout=2
        )
        print(f"✅ {name} is installed")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"❌ {name} is not installed or not running")
        return False


def check_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=False,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ Docker daemon is running")
            return True
        else:
            print("❌ Docker daemon is not running")
            print("   Please start Docker Desktop or Docker Engine")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Docker is not installed")
        return False


def check_python_version() -> bool:
    """Check Python version."""
    if sys.version_info >= (3, 11):
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} is installed")
        return True
    else:
        print(f"❌ Python {sys.version_info.major}.{sys.version_info.minor} is too old (need 3.11+)")
        return False


def check_poetry() -> bool:
    """Check if Poetry is installed."""
    try:
        # Try with full path first
        home = Path.home()
        poetry_path = home / ".local" / "bin" / "poetry"
        
        if poetry_path.exists():
            result = subprocess.run(
                [str(poetry_path), "--version"],
                capture_output=True,
                check=False,
                timeout=2
            )
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                print(f"✅ {version}")
                return True
    except:
        pass
    
    # Try system poetry
    return check_command("poetry", "Poetry")


def check_env_file() -> bool:
    """Check if .env file exists."""
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file exists")
        return True
    else:
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        return False


def main():
    """Run all checks."""
    print("🔍 Checking TastyTrade MCP development environment...\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Poetry", check_poetry),
        ("Docker", check_docker_running),
        ("Environment File", check_env_file),
    ]
    
    results = []
    for name, check_func in checks:
        results.append(check_func())
    
    print("\n" + "=" * 50)
    
    if all(results):
        print("✅ All checks passed! Your environment is ready.")
        print("\nYou can now run:")
        print("  • ./scripts/dev.sh start    - Start services")
        print("  • poetry run python -m tastytrade_mcp.main - Run MCP server")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nRequired setup:")
        if not results[0]:  # Python
            print("  • Install Python 3.11 or higher")
        if not results[1]:  # Poetry
            print("  • Install Poetry: curl -sSL https://install.python-poetry.org | python3 -")
        if not results[2]:  # Docker
            print("  • Install and start Docker Desktop")
        if not results[3]:  # .env
            print("  • Create .env file from template")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())