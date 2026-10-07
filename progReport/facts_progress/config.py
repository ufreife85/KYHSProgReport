"""Loads settings from environment variables (.env) and the attendance
code mapping (attendance_codes.json).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env from the project root if present. Real env vars (e.g. set by
# the shell or a Codespaces secret) always take precedence.
load_dotenv(PROJECT_ROOT / ".env")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass
class AttendanceCodeMap:
    tardy_codes: set[str]
    absent_codes: set[str]
    cut_codes: set[str]
    # Real FACTS codes that are deliberately not counted anywhere. Only used
    # by scripts/check_setup.py so it can tell "skipped on purpose" apart
    # from "forgotten"; categorize() treats them like any unmapped code.
    ignored_codes: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> "AttendanceCodeMap":
        if not path.exists():
            raise ConfigError(
                f"Attendance code mapping file not found: {path}\n"
                "Copy/edit attendance_codes.json in the project root."
            )
        data = json.loads(path.read_text())
        return cls(
            tardy_codes={c.upper() for c in data.get("tardy_codes", [])},
            absent_codes={c.upper() for c in data.get("absent_codes", [])},
            cut_codes={c.upper() for c in data.get("cut_codes", [])},
            ignored_codes={c.upper() for c in data.get("ignored_codes", [])},
        )

    def categorize(self, code: str) -> str | None:
        """Returns 'tardy', 'absent', 'cut', or None for an unmapped code."""
        code = (code or "").upper()
        if code in self.cut_codes:
            return "cut"
        if code in self.absent_codes:
            return "absent"
        if code in self.tardy_codes:
            return "tardy"
        return None


@dataclass
class Settings:
    # FACTS actually requires BOTH of these, sent as two separate headers
    # on every request (confirmed against a live 200 OK response from the
    # FACTS Developer Portal's own request tester -- see facts_client.py):
    #
    #   Ocp-Apim-Subscription-Key: <subscription_key>   (the short ~32-char
    #       key tied to your developer account -- the one you enter in the
    #       portal UI when authorizing/scoping an API key)
    #   Facts-Api-Key:              <api_key>            (the long ~108-char
    #       school-scoped key that subscription key was used to generate)
    #
    # Earlier versions of this project claimed the subscription key was
    # portal-only and never sent to the API -- that was wrong. Both keys
    # are required together.
    subscription_key: str
    api_key: str
    api_version: str
    base_url: str
    school_id: int
    school_code: str
    attendance_codes: AttendanceCodeMap
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")

    @classmethod
    def load(cls) -> "Settings":
        subscription_key = os.getenv("FACTS_SUBSCRIPTION_KEY", "").strip()
        api_key = os.getenv("FACTS_API_KEY", "").strip()
        api_version = os.getenv("FACTS_API_VERSION", "").strip()
        base_url = os.getenv("FACTS_BASE_URL", "https://api.factsmgt.com").strip()
        school_id_raw = os.getenv("FACTS_SCHOOL_ID", "").strip()
        school_code = os.getenv("FACTS_SCHOOL_CODE", "").strip()

        missing = [
            name
            for name, val in [
                ("FACTS_SUBSCRIPTION_KEY", subscription_key),
                ("FACTS_API_KEY", api_key),
                ("FACTS_API_VERSION", api_version),
                ("FACTS_SCHOOL_ID", school_id_raw),
                ("FACTS_SCHOOL_CODE", school_code),
            ]
            if not val
        ]
        if missing:
            raise ConfigError(
                "Missing required settings in .env: " + ", ".join(missing) +
                "\nCopy .env.example to .env and fill these in."
            )

        if len(api_key) < 60:
            raise ConfigError(
                f"FACTS_API_KEY looks too short ({len(api_key)} characters) for the "
                "~108-character school-scoped key. Did you paste FACTS_SUBSCRIPTION_KEY's "
                "value here by mistake?"
            )

        if len(subscription_key) > 60:
            raise ConfigError(
                f"FACTS_SUBSCRIPTION_KEY looks too long ({len(subscription_key)} characters) "
                "for the ~32-character developer subscription key. Did you paste "
                "FACTS_API_KEY's value here by mistake? (The two keys may have gotten swapped.)"
            )

        try:
            school_id = int(school_id_raw)
        except ValueError:
            raise ConfigError("FACTS_SCHOOL_ID must be a number.")

        attendance_codes = AttendanceCodeMap.load(PROJECT_ROOT / "attendance_codes.json")

        return cls(
            subscription_key=subscription_key,
            api_key=api_key,
            api_version=api_version,
            base_url=base_url,
            school_id=school_id,
            school_code=school_code,
            attendance_codes=attendance_codes,
        )