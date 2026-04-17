import pytest
import shutil
from pathlib import Path
from uuid import uuid4

from src.services.domain.preset_loader import (
    PresetLoader,
    PresetNotFoundError,
    PresetValidationError,
)


def _write_yaml(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def preset_temp_dir():
    base_dir = Path("tests") / ".tmp_presets"
    base_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_dir / str(uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_preset_loader_resolve_default(preset_temp_dir):
    _write_yaml(
        preset_temp_dir / "scoped_knowledge.yaml",
        """
id: scoped_knowledge
display_name: Scoped
system_prompt_addon: grounded
""".strip(),
    )
    _write_yaml(
        preset_temp_dir / "cv_matching.yaml",
        """
id: cv_matching
display_name: CV
system_prompt_addon: cv mode
allow_image_perception: true
""".strip(),
    )

    loader = PresetLoader(preset_dir=preset_temp_dir, default_preset_id="scoped_knowledge")
    preset = loader.resolve()

    assert preset.id == "scoped_knowledge"
    assert len(loader.list_presets()) == 2


def test_preset_loader_get_preset_missing(preset_temp_dir):
    _write_yaml(
        preset_temp_dir / "scoped_knowledge.yaml",
        """
id: scoped_knowledge
display_name: Scoped
""".strip(),
    )

    loader = PresetLoader(preset_dir=preset_temp_dir, default_preset_id="scoped_knowledge")

    with pytest.raises(PresetNotFoundError):
        loader.get_preset("does_not_exist")


def test_preset_loader_invalid_schema_raises(preset_temp_dir):
    _write_yaml(
        preset_temp_dir / "bad.yaml",
        """
id: bad
""".strip(),
    )
    _write_yaml(
        preset_temp_dir / "scoped_knowledge.yaml",
        """
id: scoped_knowledge
display_name: Scoped
""".strip(),
    )

    loader = PresetLoader(preset_dir=preset_temp_dir, default_preset_id="scoped_knowledge")

    with pytest.raises(PresetValidationError):
        loader.list_presets(refresh=True)
