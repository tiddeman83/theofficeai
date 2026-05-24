#!/usr/bin/env python3
"""
HQ Skill Manager (The Librarian Engine)
Phase 3a: Governance & Intelligence.
"""

import re
from pathlib import Path


class Librarian:
    """File-backed skill storage for HQ prompt memory."""

    def __init__(self, skills_dir=None):
        self.skills_dir = Path(skills_dir) if skills_dir else Path(__file__).resolve().parent / "skills"

    def save_skill(self, agent_persona, skill_name, raw_lesson):
        persona = self._safe_name(agent_persona, "agent_persona")
        name = self._safe_name(skill_name, "skill_name")
        if not isinstance(raw_lesson, str) or not raw_lesson.strip():
            raise ValueError("raw_lesson must be a non-empty string")

        target_dir = self.skills_dir / persona
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{name}.md"
        target_file.write_text(self._compress_caveman(raw_lesson), encoding="utf-8")
        return target_file

    def load_skills(self, agent_persona):
        persona = self._safe_name(agent_persona, "agent_persona")
        persona_dir = self.skills_dir / persona
        if not persona_dir.is_dir():
            return ""

        chunks = []
        for skill_file in sorted(persona_dir.glob("*.md")):
            if skill_file.is_file():
                content = skill_file.read_text(encoding="utf-8").strip()
                if content:
                    chunks.append(content)
        return "\n\n".join(chunks)

    def _safe_name(self, value, field_name):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"{field_name} contains forbidden path traversal")
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", value.strip()).strip("_")
        if not safe:
            raise ValueError(f"{field_name} contains no valid filename characters")
        return safe

    def _compress_caveman(self, raw_lesson):
        lines = []
        for line in raw_lesson.splitlines():
            stripped = " ".join(line.strip().split())
            if stripped:
                lines.append(stripped)
        return "# CAVEMAN SKILL\n" + "\n".join(lines) + "\n"
