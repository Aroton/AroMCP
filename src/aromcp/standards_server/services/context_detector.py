"""Context detection for AI coding sessions."""

import logging
import os
import re
from typing import Any

from .session_manager import SessionState

logger = logging.getLogger(__name__)


class ContextDetector:
    """Detect what the AI is working on."""

    def __init__(self):
        self.task_patterns = {
            "api_development": [
                r"/api/.*route\.(ts|js)",
                r"/api/.*\.ts",
                r"export.*GET|POST|PUT|DELETE",
                r"NextRequest|NextResponse",
            ],
            "component_development": [
                r"\.(tsx|jsx)$",
                r"export.*React\.FC",
                r"export.*function.*Component",
                r"import.*React",
            ],
            "testing": [r"\.(test|spec)\.(ts|js|tsx|jsx)$", r"describe\s*\(", r"it\s*\(", r"test\s*\(", r"expect\s*\("],
            "styling": [r"\.(css|scss|sass|less)$", r"styled-components", r"@emotion", r"tailwind", r"className="],
            "configuration": [
                r"(next|webpack|babel|eslint|prettier)\.config\.(js|ts)",
                r"package\.json",
                r"tsconfig\.json",
                r"\.env",
            ],
            "database": [r"(prisma|mongoose|sequelize)", r"\.sql$", r"migration", r"schema"],
        }

    def analyze_session_context(self, session: SessionState, current_file: str) -> dict[str, Any]:
        """Comprehensive context analysis."""
        try:
            return {
                "task_type": self._detect_task_type(session, current_file),
                "architectural_layer": self._detect_layer(current_file),
                "technology_stack": self._detect_tech_stack(session),
                "complexity_level": self._assess_complexity(session),
                "working_area": self._detect_working_area(session.file_history),
                "nextjs_context": self._detect_nextjs_context(current_file, session),
                "pattern_familiarity": self._assess_pattern_familiarity(session),
                "session_phase": self._detect_session_phase(session),
            }
        except Exception as e:
            logger.error(f"Error analyzing context: {e}")
            return self._get_default_context()

    def _detect_task_type(self, session: SessionState, current_file: str) -> str:
        """Detect what kind of task is being performed."""
        recent_files = session.get_recent_files(5)
        all_files = [current_file] + recent_files

        # Check patterns for each task type
        for task_type, patterns in self.task_patterns.items():
            matches = 0
            for pattern in patterns:
                for file_path in all_files:
                    if re.search(pattern, file_path, re.IGNORECASE):
                        matches += 1
                        break

            # If multiple patterns match, it's likely this task type
            if matches >= 2:
                return task_type

        # Special cases based on file visit patterns
        if self._is_refactoring_pattern(session):
            return "refactoring"

        if self._is_debugging_pattern(session):
            return "debugging"

        # Default fallback
        return "feature_development"

    def _detect_layer(self, current_file: str) -> str:
        """Detect architectural layer."""
        if "/components/" in current_file or current_file.endswith((".tsx", ".jsx")):
            return "presentation"
        elif "/api/" in current_file or "/server/" in current_file:
            return "api"
        elif "/lib/" in current_file or "/utils/" in current_file:
            return "utility"
        elif "/hooks/" in current_file:
            return "hooks"
        elif "/context/" in current_file or "/store/" in current_file:
            return "state"
        elif "/pages/" in current_file or "/app/" in current_file:
            return "routing"
        elif "/styles/" in current_file or current_file.endswith((".css", ".scss")):
            return "styling"
        else:
            return "business_logic"

    def _detect_tech_stack(self, session: SessionState) -> dict[str, bool]:
        """Detect technology stack from file history."""
        tech_indicators = {
            "react": [r"\.(tsx|jsx)$", r"import.*React"],
            "nextjs": [r"next/", r"app/", r"pages/"],
            "typescript": [r"\.(ts|tsx)$"],
            "tailwind": [r"tailwind", r"@apply"],
            "prisma": [r"prisma/", r"@prisma"],
            "api_routes": [r"/api/.*route\.(ts|js)"],
            "server_components": [r"app/.*\.(ts|tsx)$"],
            "client_components": [r"'use client'", r'"use client"'],
        }

        detected = {}
        for tech, patterns in tech_indicators.items():
            detected[tech] = any(
                re.search(pattern, file_path, re.IGNORECASE)
                for pattern in patterns
                for file_path in session.file_history
            )

        return detected

    def _assess_complexity(self, session: SessionState) -> str:
        """Assess complexity level based on session patterns."""
        file_count = len(session.file_history)
        pattern_count = len(session.loaded_patterns)

        if file_count < 3 and pattern_count < 2:
            return "basic"
        elif file_count < 10 and pattern_count < 5:
            return "intermediate"
        elif file_count < 20 and pattern_count < 10:
            return "advanced"
        else:
            return "expert"

    def _detect_working_area(self, file_history: list[str]) -> str:
        """Detect primary working area."""
        if not file_history:
            return "unknown"

        # Find common path prefix
        common_dirs = {}
        for file_path in file_history:
            dirs = file_path.split("/")
            for i in range(1, len(dirs)):
                dir_path = "/".join(dirs[:i])
                common_dirs[dir_path] = common_dirs.get(dir_path, 0) + 1

        if common_dirs:
            most_common = max(common_dirs.items(), key=lambda x: x[1])
            return most_common[0]

        return "root"

    def _detect_nextjs_context(self, file_path: str, session: SessionState) -> dict[str, Any]:
        """Detect Next.js specific context."""
        context = {
            "router_type": None,
            "is_api_route": False,
            "is_server_component": True,  # Default assumption
            "route_type": None,
            "rendering_strategy": "ssr",
        }

        try:
            # Detect router type
            if "/app/" in file_path:
                context["router_type"] = "app"
            elif "/pages/" in file_path:
                context["router_type"] = "pages"

            # Detect API routes
            context["is_api_route"] = "/api/" in file_path

            # Detect server vs client components
            if file_path.endswith((".tsx", ".jsx")):
                context["is_server_component"] = not self._has_use_client_directive(file_path)

            # Detect route type
            context["route_type"] = self._detect_route_type(file_path)

            # Detect rendering strategy
            context["rendering_strategy"] = self._detect_rendering_strategy(file_path, session)

        except Exception as e:
            logger.error(f"Error detecting Next.js context: {e}")

        return context

    def _detect_route_type(self, file_path: str) -> str | None:
        """Detect Next.js route type."""
        if "route.ts" in file_path or "route.js" in file_path:
            return "api_route"
        elif "page.tsx" in file_path or "page.jsx" in file_path:
            return "page"
        elif "layout.tsx" in file_path or "layout.jsx" in file_path:
            return "layout"
        elif "loading.tsx" in file_path or "loading.jsx" in file_path:
            return "loading"
        elif "error.tsx" in file_path or "error.jsx" in file_path:
            return "error"
        elif "not-found.tsx" in file_path or "not-found.jsx" in file_path:
            return "not_found"
        else:
            return "component"

    def _detect_rendering_strategy(self, file_path: str, session: SessionState) -> str:
        """Detect rendering strategy."""
        if "/api/" in file_path:
            return "api"
        elif self._has_use_client_directive(file_path):
            return "csr"
        elif "/app/" in file_path:
            return "ssr"  # App router default
        else:
            return "ssr"

    def _has_use_client_directive(self, file_path: str) -> bool:
        """Check if file has 'use client' directive."""
        try:
            if os.path.exists(file_path):
                with open(file_path, encoding="utf-8") as f:
                    first_few_lines = f.read(500)  # Check first 500 chars
                    return "'use client'" in first_few_lines or '"use client"' in first_few_lines
        except Exception:  # noqa: S110
            # Ignore file read errors for client detection - this is intentional
            # for robustness when checking potentially non-text files
            pass
        return False

    def _is_refactoring_pattern(self, session: SessionState) -> bool:
        """Detect refactoring pattern (multiple visits to same files)."""
        file_visits = {}
        for file_path in session.file_history:
            file_visits[file_path] = file_visits.get(file_path, 0) + 1
        return any(count >= 3 for count in file_visits.values())

    def _is_debugging_pattern(self, session: SessionState) -> bool:
        """Detect debugging pattern."""
        recent_files = session.get_recent_files(3)
        return (
            len(set(recent_files)) == 1
            and len(recent_files) > 1  # Same file multiple times
            or any("error" in f.lower() or "debug" in f.lower() for f in recent_files)
        )

    def _assess_pattern_familiarity(self, session: SessionState) -> dict[str, str]:
        """Assess familiarity with different patterns."""
        familiarity = {}
        for pattern, frequency in session.pattern_frequency.items():
            if frequency >= 5:
                familiarity[pattern] = "expert"
            elif frequency >= 3:
                familiarity[pattern] = "familiar"
            elif frequency >= 1:
                familiarity[pattern] = "novice"
            else:
                familiarity[pattern] = "new"
        return familiarity

    def _detect_session_phase(self, session: SessionState) -> str:
        """Detect what phase of development this session is in."""
        file_count = len(session.file_history)
        pattern_count = len(session.loaded_patterns)

        if file_count < 3:
            return "exploration"
        elif pattern_count < 3:
            return "learning"
        elif self._is_refactoring_pattern(session):
            return "refinement"
        elif file_count > 10:
            return "development"
        else:
            return "implementation"

    def _get_default_context(self) -> dict[str, Any]:
        """Get default context when detection fails."""
        return {
            "task_type": "feature_development",
            "architectural_layer": "business_logic",
            "technology_stack": {},
            "complexity_level": "intermediate",
            "working_area": "unknown",
            "nextjs_context": {
                "router_type": None,
                "is_api_route": False,
                "is_server_component": True,
                "route_type": None,
                "rendering_strategy": "ssr",
            },
            "pattern_familiarity": {},
            "session_phase": "exploration",
        }
