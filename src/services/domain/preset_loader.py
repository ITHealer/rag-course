from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import ValidationError

from src.services.domain.models import DomainPreset

logger = logging.getLogger(__name__)


class PresetLoaderError(Exception):
    """Base exception for preset loading failures."""


class PresetNotFoundError(PresetLoaderError):
    """Raised when a requested preset cannot be found."""


class PresetValidationError(PresetLoaderError):
    """Raised when a preset YAML file is malformed."""


class PresetLoader:
    """Load and validate domain presets from YAML files."""

    def __init__(self, preset_dir: str | Path, default_preset_id: str = "scoped_knowledge"):
        self.preset_dir = Path(preset_dir)
        self.default_preset_id = default_preset_id
        self._cache: Dict[str, DomainPreset] = {}

    def list_presets(self, refresh: bool = False) -> List[DomainPreset]:
        """Return all available presets."""
        presets = self._load_all(refresh=refresh)
        return sorted(presets.values(), key=lambda item: item.id)

    def resolve(self, preset_id: Optional[str] = None, refresh: bool = False) -> DomainPreset:
        """Return a specific preset, or the default when preset_id is not provided."""
        target_id = preset_id or self.default_preset_id
        return self.get_preset(target_id, refresh=refresh)

    def get_preset(self, preset_id: str, refresh: bool = False) -> DomainPreset:
        """Return one preset by identifier."""
        presets = self._load_all(refresh=refresh)
        if preset_id not in presets:
            raise PresetNotFoundError(
                f"Preset '{preset_id}' not found in '{self.preset_dir}'. "
                f"Available presets: {sorted(presets.keys())}"
            )
        return presets[preset_id]

    def _load_all(self, refresh: bool = False) -> Dict[str, DomainPreset]:
        if self._cache and not refresh:
            return self._cache

        if not self.preset_dir.exists():
            raise PresetLoaderError(f"Preset directory does not exist: {self.preset_dir}")

        presets: Dict[str, DomainPreset] = {}
        yaml_files = sorted(self.preset_dir.glob("*.yml")) + sorted(self.preset_dir.glob("*.yaml"))

        if not yaml_files:
            raise PresetLoaderError(f"No preset YAML files found in: {self.preset_dir}")

        for preset_file in yaml_files:
            preset = self._read_preset_file(preset_file)
            if preset.id in presets:
                raise PresetValidationError(
                    f"Duplicate preset id '{preset.id}' found in '{preset_file}' and another preset file."
                )
            presets[preset.id] = preset

        if self.default_preset_id not in presets:
            raise PresetValidationError(
                f"Default preset '{self.default_preset_id}' is missing. "
                f"Available presets: {sorted(presets.keys())}"
            )

        self._cache = presets
        logger.info("Loaded %s presets from %s", len(presets), self.preset_dir)
        return presets

    def _read_preset_file(self, preset_file: Path) -> DomainPreset:
        try:
            payload = yaml.safe_load(preset_file.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise PresetValidationError(f"Failed to read preset file '{preset_file}': {exc}") from exc

        if not isinstance(payload, dict):
            raise PresetValidationError(f"Preset file '{preset_file}' must contain a YAML object.")

        try:
            return DomainPreset.model_validate(payload)
        except ValidationError as exc:
            raise PresetValidationError(f"Invalid preset schema in '{preset_file}': {exc}") from exc
