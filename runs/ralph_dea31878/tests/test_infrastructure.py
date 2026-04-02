"""Tests for FEAT-001: Project Infrastructure & Setup."""
import os
import subprocess
import sys


# TASK-001: pyproject.toml with all dependencies
class TestPyprojectToml:
    def test_pyproject_exists(self):
        """Step 1: pyproject.toml exists in project root."""
        assert os.path.isfile("pyproject.toml")

    def test_fastapi_dependency(self):
        """Step 2: fastapi>=0.115 is listed in dependencies."""
        with open("pyproject.toml") as f:
            content = f.read()
        assert "fastapi>=0.115" in content

    def test_uvicorn_dependency(self):
        """Step 2: uvicorn>=0.30 is listed in dependencies."""
        with open("pyproject.toml") as f:
            content = f.read()
        assert "uvicorn>=0.30" in content

    def test_httpx_dev_dependency(self):
        """Step 3: httpx>=0.27 is listed in dev optional-dependencies."""
        with open("pyproject.toml") as f:
            content = f.read()
        assert "httpx>=0.27" in content

    def test_pytest_dev_dependency(self):
        """Step 3: pytest>=8.0 is listed in dev optional-dependencies."""
        with open("pyproject.toml") as f:
            content = f.read()
        assert "pytest>=8.0" in content

    def test_setuptools_build_backend(self):
        """Build backend is setuptools."""
        with open("pyproject.toml") as f:
            content = f.read()
        assert 'build-backend = "setuptools.build_meta"' in content

    def test_imports_work(self):
        """All dependencies are importable."""
        import fastapi
        import uvicorn
        import httpx
        import pytest

        assert fastapi is not None
        assert uvicorn is not None
        assert httpx is not None
        assert pytest is not None


# TASK-002: Directory structure with all __init__.py files
class TestDirectoryStructure:
    def test_app_init_exists(self):
        """Step 1: app/__init__.py exists."""
        assert os.path.isfile("app/__init__.py")

    def test_app_routers_init_exists(self):
        """Step 2: app/routers/__init__.py exists."""
        assert os.path.isfile("app/routers/__init__.py")

    def test_tests_init_exists(self):
        """Step 3: tests/__init__.py exists."""
        assert os.path.isfile("tests/__init__.py")

    def test_app_importable(self):
        """app package is importable."""
        import app

        assert app is not None

    def test_app_routers_importable(self):
        """app.routers package is importable."""
        import app.routers

        assert app.routers is not None


# TASK-003: init.sh bootstraps project from scratch
class TestInitScript:
    def test_init_sh_exists(self):
        """Step 1: init.sh exists."""
        assert os.path.isfile("init.sh")

    def test_init_sh_executable(self):
        """Step 1: init.sh is executable."""
        assert os.access("init.sh", os.X_OK)

    def test_init_sh_creates_venv(self):
        """Step 2: Script creates .venv if it doesn't exist."""
        with open("init.sh") as f:
            content = f.read()
        assert ".venv" in content
        assert "python3 -m venv" in content

    def test_init_sh_installs_deps(self):
        """Step 3: Script installs dependencies via pip install -e '.[dev]'."""
        with open("init.sh") as f:
            content = f.read()
        assert "pip install -e" in content
        assert ".[dev]" in content

    def test_init_sh_ensures_dirs(self):
        """Step 4: Script ensures directory structure."""
        with open("init.sh") as f:
            content = f.read()
        assert "app/routers" in content
        assert "tests" in content
        assert "__init__.py" in content

    def test_init_sh_runs_pytest(self):
        """Step 5: Script runs pytest."""
        with open("init.sh") as f:
            content = f.read()
        assert "pytest" in content

    def test_init_sh_prints_instructions(self):
        """Step 6: Script prints startup instructions."""
        with open("init.sh") as f:
            content = f.read()
        assert "uvicorn" in content
        assert "8000" in content
