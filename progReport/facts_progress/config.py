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
    # The school-scoped FACTS API key (~108 chars), sent as the
    # Ocp-Apim-Subscription-Key header on every request. NOT your
    # developer subscription key (the shorter, ~32-char key you enter in
    # the FACTS Developer Portal UI to create/authorize this API key --
    # that key is portal-only and is never sent to the API itself). See
    # the comment in .env.example if that distinction is new to you.
    api_key: str
    api_version: str
    base_url: str
    school_id: int
    school_code: str
    attendance_codes: AttendanceCodeMap
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")

    @classmethod
    def load(cls) -> "Settings":
        api_key = os.getenv("FACTS_API_KEY", "").strip()
        api_version = os.getenv("FACTS_API_VERSION", "").strip()
        base_url = os.getenv("FACTS_BASE_URL", "https://api.factsmgt.com").strip()
        school_id_raw = os.getenv("FACTS_SCHOOL_ID", "").strip()
        school_code = os.getenv("FACTS_SCHOOL_CODE", "").strip()

        missing = [
            name
            for name, val in [
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
                f"FACTS_API_KEY looks too short ({len(api_key)} characters). "
                "Make sure you used your school-scoped API key (~108 characters), "
                "not your shorter developer subscription key -- the subscription "
                "key only authorizes API keys inside the FACTS Developer Portal "
                "and is never sent to the API itself."
            )

        try:
            school_id = int(school_id_raw)
        except ValueError:
            raise ConfigError("FACTS_SCHOOL_ID must be a number.")

        attendance_codes = AttendanceCodeMap.load(PROJECT_ROOT / "attendance_codes.json")

        return cls(
            api_key=api_key,
            api_version=api_version,
            base_url=base_url,
            school_id=school_id,
            school_code=school_code,
            attendance_codes=attendance_codes,
        )
