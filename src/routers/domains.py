from fastapi import APIRouter, HTTPException, Query

from src.dependencies import DomainProfileRepoDep, SettingsDep
from src.schemas.api.domains import (
    BatchPresetImportItemResponse,
    BatchPresetImportRequest,
    BatchPresetImportResponse,
    DomainDeleteResponse,
    DomainConfigUpsertRequest,
    DomainImportPresetResponse,
    DomainProfileCreateRequest,
    DomainPromptResponse,
    DomainPromptUpdateRequest,
    DomainProfileResponse,
    DomainProfileUpdateRequest,
    PresetLibraryItemResponse,
)
from src.services.domain.preset_loader import PresetLoader, PresetLoaderError

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])


def _build_preset_loader(settings: SettingsDep) -> PresetLoader:
    return PresetLoader(
        preset_dir=settings.preset_dir,
        default_preset_id=settings.default_preset_id,
    )


def _build_domain_payload_from_preset(preset) -> dict:
    return {
        "display_name": preset.display_name,
        "mode_default": preset.mode_default,
        "system_prompt_addon": preset.system_prompt_addon,
        "metadata_extract": [rule.model_dump() for rule in preset.metadata_extract],
        "search_boost": [rule.model_dump() for rule in preset.search_boost],
        "answer_policy": preset.answer_policy,
        "allow_external_web_search": preset.allow_external_web_search,
        "require_human_approval_for_external_search": preset.require_human_approval_for_external_search,
        "allow_image_perception": preset.allow_image_perception,
        "allowed_external_domains": preset.allowed_external_domains,
        "is_active": True,
    }


def _import_preset(
    *,
    repository: DomainProfileRepoDep,
    preset,
    target_domain_id: str,
    upsert: bool,
) -> BatchPresetImportItemResponse:
    payload = _build_domain_payload_from_preset(preset)
    existing = repository.get_by_domain_id(target_domain_id)
    if existing:
        if not upsert:
            return BatchPresetImportItemResponse(
                preset_id=preset.id,
                domain_id=target_domain_id,
                status="conflict",
                version=existing.version,
                message=f"Domain '{target_domain_id}' already exists.",
            )
        updated = repository.update(domain_profile=existing, update_data=payload)
        return BatchPresetImportItemResponse(
            preset_id=preset.id,
            domain_id=target_domain_id,
            status="updated",
            version=updated.version,
            message="Preset updated existing domain profile.",
        )

    created = repository.create({"domain_id": target_domain_id, **payload})
    return BatchPresetImportItemResponse(
        preset_id=preset.id,
        domain_id=target_domain_id,
        status="created",
        version=created.version,
        message="Preset created new domain profile.",
    )


@router.post("", response_model=DomainProfileResponse, status_code=201)
def create_domain(
    request: DomainProfileCreateRequest,
    repository: DomainProfileRepoDep,
) -> DomainProfileResponse:
    existing = repository.get_by_domain_id(request.domain_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Domain '{request.domain_id}' already exists.")
    domain = repository.create(request.model_dump())
    return DomainProfileResponse.model_validate(domain)


@router.get("", response_model=list[DomainProfileResponse])
def list_domains(
    repository: DomainProfileRepoDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[DomainProfileResponse]:
    items = repository.list(limit=limit, offset=offset)
    return [DomainProfileResponse.model_validate(item) for item in items]


@router.get("/presets/library", response_model=list[PresetLibraryItemResponse])
def list_preset_library(settings: SettingsDep) -> list[PresetLibraryItemResponse]:
    loader = _build_preset_loader(settings)
    try:
        presets = loader.list_presets()
    except PresetLoaderError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load preset library: {exc}") from exc

    return [
        PresetLibraryItemResponse(
            id=preset.id,
            display_name=preset.display_name,
            mode_default=preset.mode_default,
            allow_external_web_search=preset.allow_external_web_search,
            require_human_approval_for_external_search=preset.require_human_approval_for_external_search,
            allow_image_perception=preset.allow_image_perception,
        )
        for preset in presets
    ]


@router.post("/presets/library/{preset_id}/import", response_model=DomainImportPresetResponse, status_code=201)
def import_domain_from_preset(
    preset_id: str,
    repository: DomainProfileRepoDep,
    settings: SettingsDep,
    domain_id: str | None = Query(default=None, min_length=1, max_length=100),
    upsert: bool = Query(default=False),
) -> DomainImportPresetResponse:
    loader = _build_preset_loader(settings)
    try:
        preset = loader.get_preset(preset_id)
    except PresetLoaderError as exc:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found: {exc}") from exc

    target_domain_id = domain_id or preset.id
    result = _import_preset(
        repository=repository,
        preset=preset,
        target_domain_id=target_domain_id,
        upsert=upsert,
    )
    if result.status == "conflict":
        raise HTTPException(
            status_code=409,
            detail=f"Domain '{target_domain_id}' already exists. Set upsert=true to overwrite.",
        )
    return DomainImportPresetResponse(
        domain_id=target_domain_id,
        imported_from_preset=preset.id,
        created=result.status == "created",
        version=result.version or 1,
    )


@router.post("/presets/library/import-all", response_model=BatchPresetImportResponse)
def import_all_domains_from_presets(
    request: BatchPresetImportRequest,
    repository: DomainProfileRepoDep,
    settings: SettingsDep,
) -> BatchPresetImportResponse:
    loader = _build_preset_loader(settings)
    try:
        presets = loader.list_presets(refresh=True)
    except PresetLoaderError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load preset library: {exc}") from exc

    if request.preset_ids:
        selected_ids = set(request.preset_ids)
        presets = [preset for preset in presets if preset.id in selected_ids]

    items: list[BatchPresetImportItemResponse] = []
    for preset in presets:
        target_domain_id = preset.id
        if request.dry_run:
            existing = repository.get_by_domain_id(target_domain_id)
            if existing:
                status = "planned" if request.upsert else "conflict"
                message = (
                    "Would update existing domain profile."
                    if request.upsert
                    else f"Domain '{target_domain_id}' already exists."
                )
                version = existing.version + 1 if request.upsert else existing.version
            else:
                status = "planned"
                message = "Would create new domain profile."
                version = 1
            items.append(
                BatchPresetImportItemResponse(
                    preset_id=preset.id,
                    domain_id=target_domain_id,
                    status=status,
                    version=version,
                    message=message,
                )
            )
            continue

        items.append(
            _import_preset(
                repository=repository,
                preset=preset,
                target_domain_id=target_domain_id,
                upsert=request.upsert,
            )
        )

    created_count = sum(1 for item in items if item.status == "created")
    updated_count = sum(1 for item in items if item.status == "updated")
    conflict_count = sum(1 for item in items if item.status == "conflict")
    planned_count = sum(1 for item in items if item.status == "planned")

    return BatchPresetImportResponse(
        total_presets=len(items),
        created_count=created_count,
        updated_count=updated_count,
        conflict_count=conflict_count,
        planned_count=planned_count,
        dry_run=request.dry_run,
        items=items,
    )


@router.get("/{domain_id}", response_model=DomainProfileResponse)
def get_domain(
    domain_id: str,
    repository: DomainProfileRepoDep,
) -> DomainProfileResponse:
    domain = repository.get_by_domain_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")
    return DomainProfileResponse.model_validate(domain)


@router.get("/{domain_id}/config", response_model=DomainProfileResponse)
def get_domain_config(
    domain_id: str,
    repository: DomainProfileRepoDep,
) -> DomainProfileResponse:
    domain = repository.get_by_domain_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")
    return DomainProfileResponse.model_validate(domain)


@router.put("/{domain_id}/config", response_model=DomainProfileResponse)
def upsert_domain_config(
    domain_id: str,
    request: DomainConfigUpsertRequest,
    repository: DomainProfileRepoDep,
) -> DomainProfileResponse:
    payload = request.model_dump()
    existing = repository.get_by_domain_id(domain_id)
    if existing:
        updated = repository.update(domain_profile=existing, update_data=payload)
        return DomainProfileResponse.model_validate(updated)

    created = repository.create({"domain_id": domain_id, **payload})
    return DomainProfileResponse.model_validate(created)


@router.get("/{domain_id}/prompt", response_model=DomainPromptResponse)
def get_domain_prompt(
    domain_id: str,
    repository: DomainProfileRepoDep,
) -> DomainPromptResponse:
    domain = repository.get_by_domain_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")
    return DomainPromptResponse(
        domain_id=domain.domain_id,
        system_prompt_addon=domain.system_prompt_addon,
        answer_policy=domain.answer_policy,
        mode_default=domain.mode_default,
        version=domain.version,
        updated_at=domain.updated_at,
    )


@router.put("/{domain_id}/prompt", response_model=DomainPromptResponse)
def update_domain_prompt(
    domain_id: str,
    request: DomainPromptUpdateRequest,
    repository: DomainProfileRepoDep,
) -> DomainPromptResponse:
    domain = repository.get_by_domain_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")

    update_data = {
        "system_prompt_addon": request.system_prompt_addon,
        "answer_policy": request.answer_policy,
    }
    if request.mode_default is not None:
        update_data["mode_default"] = request.mode_default

    updated = repository.update(domain_profile=domain, update_data=update_data)
    return DomainPromptResponse(
        domain_id=updated.domain_id,
        system_prompt_addon=updated.system_prompt_addon,
        answer_policy=updated.answer_policy,
        mode_default=updated.mode_default,
        version=updated.version,
        updated_at=updated.updated_at,
    )


@router.patch("/{domain_id}", response_model=DomainProfileResponse)
def update_domain(
    domain_id: str,
    request: DomainProfileUpdateRequest,
    repository: DomainProfileRepoDep,
) -> DomainProfileResponse:
    domain = repository.get_by_domain_id(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")

    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        return DomainProfileResponse.model_validate(domain)

    updated = repository.update(domain_profile=domain, update_data=update_data)
    return DomainProfileResponse.model_validate(updated)


@router.delete("/{domain_id}", response_model=DomainDeleteResponse)
def delete_domain(
    domain_id: str,
    repository: DomainProfileRepoDep,
) -> DomainDeleteResponse:
    domain = repository.get_by_domain_id(domain_id)
    if not domain:
        return DomainDeleteResponse(domain_id=domain_id, deleted=False)

    repository.delete(domain_profile=domain)
    return DomainDeleteResponse(domain_id=domain_id, deleted=True)
