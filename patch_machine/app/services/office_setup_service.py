"""Initial office setup service boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from patch_machine.app.initial_setup import ParsedSetupFile
    from patch_machine.app.schemas import CompanyProfilePayload, InitialOfficeSetupResult


def build_initial_office_setup_prompt(
    *,
    message: str,
    intent: str,
    parsed_files: list[ParsedSetupFile],
    company_profile: CompanyProfilePayload | None = None,
) -> str:
    from patch_machine.app.api import _initial_office_setup_prompt

    return _initial_office_setup_prompt(
        message=message,
        intent=intent,
        parsed_files=parsed_files,
        company_profile=company_profile,
    )


def parse_initial_setup_result(
    raw: str,
    *,
    parsed_files: list[ParsedSetupFile],
    company_profile: CompanyProfilePayload | None = None,
) -> InitialOfficeSetupResult:
    from patch_machine.app.api import _parse_initial_setup_result

    return _parse_initial_setup_result(
        raw,
        parsed_files=parsed_files,
        company_profile=company_profile,
    )


def try_load_json_object(raw: str) -> dict[str, Any] | None:
    from patch_machine.app.api import _try_load_json_object

    return _try_load_json_object(raw)
