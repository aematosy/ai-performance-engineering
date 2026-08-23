from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(RuntimeError):
    """Raised when the project configuration is missing or invalid."""


class ConfigLoader:
    """
    Loads and validates the central project configuration.

    Resolution order:
    1. Explicit path passed to the constructor.
    2. PROJECT_CONFIG_FILE environment variable.
    3. config/project-config.yaml from the repository root.
    """

    DEFAULT_CONFIG_PATH = Path("config/project-config.yaml")
    ENV_CONFIG_PATH = "PROJECT_CONFIG_FILE"

    def __init__(
        self,
        config_path: str | Path | None = None,
        project_root: str | Path | None = None,
    ) -> None:
        self.project_root = self._resolve_project_root(project_root)
        self.config_path = self._resolve_config_path(config_path)
        self._config = self._load_yaml()
        self._validate_required_structure()

    @staticmethod
    def _resolve_project_root(project_root: str | Path | None) -> Path:
        if project_root:
            return Path(project_root).expanduser().resolve()

        # config_loader.py is expected inside <project>/scripts/
        return Path(__file__).resolve().parents[1]

    def _resolve_config_path(self, config_path: str | Path | None) -> Path:
        raw_path = (
            config_path
            or os.getenv(self.ENV_CONFIG_PATH)
            or self.DEFAULT_CONFIG_PATH
        )

        path = Path(raw_path).expanduser()

        if not path.is_absolute():
            path = self.project_root / path

        return path.resolve()

    def _load_yaml(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}"
            )

        if not self.config_path.is_file():
            raise ConfigurationError(
                f"Configuration path is not a file: {self.config_path}"
            )

        try:
            content = self.config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Unable to read configuration file: {self.config_path}"
            ) from exc

        if not content.strip():
            raise ConfigurationError(
                f"Configuration file is empty: {self.config_path}"
            )

        try:
            loaded = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ConfigurationError(
                f"Invalid YAML syntax in: {self.config_path}"
            ) from exc

        if not isinstance(loaded, dict):
            raise ConfigurationError(
                "The root of project-config.yaml must be a YAML mapping."
            )

        return loaded

    def _validate_required_structure(self) -> None:
        required_sections = (
            "project",
            "runtime",
            "paths",
            "scripts",
            "execution",
            "security",
        )

        missing_sections = [
            section
            for section in required_sections
            if section not in self._config
        ]

        if missing_sections:
            raise ConfigurationError(
                "Missing required configuration sections: "
                + ", ".join(missing_sections)
            )

        required_project_values = (
            "name",
            "language",
        )

        missing_project_values = [
            key
            for key in required_project_values
            if not self.get(f"project.{key}")
        ]

        if missing_project_values:
            raise ConfigurationError(
                "Missing required project values: "
                + ", ".join(missing_project_values)
            )

    @property
    def data(self) -> dict[str, Any]:
        """Returns a defensive copy of the complete configuration."""
        return deepcopy(self._config)

    def get(
        self,
        key: str,
        default: Any = None,
        *,
        required: bool = False,
    ) -> Any:
        """
        Returns a value using dot notation.

        Example:
            config.get("observability.prometheus.base_url")
        """
        current: Any = self._config

        for segment in key.split("."):
            if not isinstance(current, dict) or segment not in current:
                if required:
                    raise ConfigurationError(
                        f"Required configuration key not found: {key}"
                    )
                return default

            current = current[segment]

        return current

    def get_path(
        self,
        key: str,
        *,
        required: bool = False,
        create: bool = False,
        directory: bool = False,
    ) -> Path | None:
        """
        Resolves a configured path relative to the project root.

        Args:
            key: Dot-notation key containing the configured path.
            required: Fail if the key does not exist.
            create: Create the path if it does not exist.
            directory: Treat the path as a directory when creating it.
        """
        raw_value = self.get(key, required=required)

        if raw_value is None:
            return None

        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ConfigurationError(
                f"Configuration key must contain a valid path: {key}"
            )

        path = Path(raw_value).expanduser()

        if not path.is_absolute():
            path = self.project_root / path

        path = path.resolve()

        if create:
            if directory:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)

        return path

    def get_script_path(
        self,
        script_name: str,
        *,
        required: bool = True,
    ) -> Path | None:
        enabled = self.get(
            f"scripts.{script_name}.enabled",
            default=False,
        )

        if not enabled:
            if required:
                raise ConfigurationError(
                    f"Script is disabled or not configured: {script_name}"
                )
            return None

        path = self.get_path(
            f"scripts.{script_name}.path",
            required=required,
        )

        if required and path is not None and not path.is_file():
            raise ConfigurationError(
                f"Configured script does not exist: {path}"
            )

        return path

    def get_command(
        self,
        command_name: str,
        *,
        required: bool = True,
    ) -> str | None:
        value = self.get(
            f"runtime.{command_name}",
            required=required,
        )

        if value is None:
            return None

        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(
                f"Invalid runtime command: runtime.{command_name}"
            )

        return value.strip()

    def ensure_project_directories(self) -> dict[str, Path]:
        """
        Creates and returns the main writable project directories.
        """
        directory_keys = {
            "generated_jmx": "paths.generated_jmx_directory",
            "results": "paths.results_directory",
            "reports": "paths.reports_directory",
            "history": "paths.history_directory",
        }

        resolved: dict[str, Path] = {}

        for alias, key in directory_keys.items():
            path = self.get_path(
                key,
                required=True,
                create=True,
                directory=True,
            )
            assert path is not None
            resolved[alias] = path

        return resolved

    def validate_referenced_files(self) -> list[str]:
        """
        Validates referenced scripts and important configuration files.

        Returns a list of validation errors instead of stopping at the first one.
        """
        errors: list[str] = []

        for script_name, definition in self.get("scripts", {}).items():
            if not isinstance(definition, dict):
                errors.append(
                    f"Invalid script definition: scripts.{script_name}"
                )
                continue

            if not definition.get("enabled", False):
                continue

            try:
                self.get_script_path(script_name, required=True)
            except ConfigurationError as exc:
                errors.append(str(exc))

        file_keys = (
            "paths.files.sla",
            "paths.files.grafana_dashboard",
            "paths.files.docker_compose",
        )

        for key in file_keys:
            try:
                path = self.get_path(key, required=True)
                if path is not None and not path.exists():
                    errors.append(
                        f"Configured file does not exist for {key}: {path}"
                    )
            except ConfigurationError as exc:
                errors.append(str(exc))

        return errors


def load_config(
    config_path: str | Path | None = None,
    project_root: str | Path | None = None,
) -> ConfigLoader:
    """Convenience factory used by the project scripts."""
    return ConfigLoader(
        config_path=config_path,
        project_root=project_root,
    )


if __name__ == "__main__":
    try:
        config = load_config()
        directories = config.ensure_project_directories()
        errors = config.validate_referenced_files()

        print("Configuration loaded successfully")
        print(f"Project: {config.get('project.name')}")
        print(f"Language: {config.get('project.language')}")
        print(f"Config file: {config.config_path}")
        print(f"Project root: {config.project_root}")

        print("\nProject directories:")
        for name, path in directories.items():
            print(f"- {name}: {path}")

        if errors:
            print("\nConfiguration references with errors:")
            for error in errors:
                print(f"- {error}")
            raise SystemExit(1)

        print("\nAll configured references are valid.")

    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        raise SystemExit(1) from exc