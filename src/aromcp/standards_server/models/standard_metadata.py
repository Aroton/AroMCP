"""Standard metadata structure for standards server v2."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContextTriggers(BaseModel):
    """When to load this standard."""

    task_types: list[str] = Field(default_factory=list, description="Task types that trigger this standard")
    architectural_layers: list[str] = Field(
        default_factory=list, description="Architectural layers that need this standard"
    )
    code_patterns: list[str] = Field(default_factory=list, description="Code patterns that trigger this standard")
    import_indicators: list[str] = Field(
        default_factory=list, description="Import patterns that indicate need for this standard"
    )
    file_patterns: list[str] = Field(default_factory=list, description="File patterns that trigger this standard")
    nextjs_features: list[str] = Field(default_factory=list, description="Next.js features that need this standard")


class OptimizationHints(BaseModel):
    """How to optimize loading."""

    priority: str = Field(default="medium", description="Priority: critical, high, medium, low")
    load_frequency: str = Field(default="conditional", description="Load frequency: always, common, conditional, rare")
    compressible: bool = Field(default=True, description="Whether this standard can be compressed")
    cacheable: bool = Field(default=True, description="Whether this standard can be cached")
    context_sensitive: bool = Field(default=True, description="Whether this standard depends on context")
    example_reusability: str = Field(default="medium", description="Example reusability: high, medium, low")


class EnhancedStandardMetadata(BaseModel):
    """Enhanced standard metadata with context awareness."""

    id: str = Field(..., description="Unique identifier for the standard")
    name: str = Field(..., description="Human-readable name")
    category: str = Field(..., description="Category of the standard")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    applies_to: list[str] = Field(
        default_factory=list, description="File types/patterns this applies to", alias="appliesTo"
    )
    severity: str = Field(..., description="Severity level")
    priority: str = Field(..., description="Priority level")
    dependencies: list[str] = Field(default_factory=list, description="Dependencies on other standards")

    # Enhanced fields
    context_triggers: ContextTriggers = Field(
        default_factory=ContextTriggers, description="Context triggers for smart loading"
    )
    optimization: OptimizationHints = Field(default_factory=OptimizationHints, description="Optimization hints")
    relationships: dict[str, list[str]] = Field(default_factory=dict, description="Relationships to other standards")
    nextjs_config: dict[str, Any] = Field(default_factory=dict, description="Next.js specific configuration")

    model_config = ConfigDict(validate_assignment=True, use_enum_values=True, populate_by_name=True)
