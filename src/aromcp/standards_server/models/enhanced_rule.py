"""Enhanced rule structure for standards server v2."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleMetadata(BaseModel):
    """Metadata for smart loading and compression."""

    pattern_type: str = Field(..., description="Type of pattern: validation, error-handling, routing, etc.")
    complexity: str = Field(
        default="intermediate", description="Complexity level: basic, intermediate, advanced, expert"
    )
    rule_type: str = Field(default="must", description="Rule type: must, should, may, must-not, should-not")
    nextjs_api: list[str] = Field(
        default_factory=list, description="Next.js API features: app-router, pages-router, api-routes, etc."
    )
    client_server: str = Field(default="isomorphic", description="Context: client-only, server-only, isomorphic, edge")


class RuleCompression(BaseModel):
    """Compression configuration."""

    example_sharable: bool = Field(default=True, description="Whether examples can be shared across similar rules")
    pattern_extractable: bool = Field(
        default=True, description="Whether patterns can be extracted for minimal representation"
    )
    progressive_detail: list[str] = Field(
        default_factory=lambda: ["minimal", "standard", "detailed", "full"], description="Available detail levels"
    )


class RuleExamples(BaseModel):
    """Multiple format examples."""

    minimal: str | None = Field(None, description="Minimal example (~20 tokens)")
    standard: str | None = Field(None, description="Standard example (~100 tokens)")
    detailed: str | None = Field(None, description="Detailed example (~200 tokens)")
    full: str = Field(..., description="Full example in original format")
    reference: str | None = Field(None, description="File reference for detailed examples")
    context_variants: dict[str, str] = Field(
        default_factory=dict, description="Context-specific variants (app_router, pages_router, etc.)"
    )


class TokenCount(BaseModel):
    """Token counts for different formats."""

    minimal: int = Field(default=20, description="Tokens in minimal format")
    standard: int = Field(default=100, description="Tokens in standard format")
    detailed: int = Field(default=200, description="Tokens in detailed format")
    full: int = Field(..., description="Tokens in full format")


class EnhancedRule(BaseModel):
    """Complete rule structure with compression and context awareness."""

    rule: str = Field(..., description="The rule statement")
    rule_id: str = Field(..., description="Unique identifier for deduplication")
    context: str = Field(..., description="Context for when to apply the rule")
    metadata: RuleMetadata = Field(..., description="Rule metadata for smart loading")
    compression: RuleCompression = Field(default_factory=RuleCompression, description="Compression configuration")
    examples: RuleExamples = Field(..., description="Examples in multiple formats")
    tokens: TokenCount = Field(..., description="Token counts for different formats")
    import_map: list[dict[str, Any]] = Field(default_factory=list, description="Import mappings for the rule")
    has_eslint_rule: bool = Field(default=False, description="Whether rule has ESLint equivalent")
    relationships: dict[str, list[str]] = Field(
        default_factory=dict, description="Relationships: similar_rules, prerequisite_rules, etc."
    )

    model_config = ConfigDict(validate_assignment=True, use_enum_values=True)
