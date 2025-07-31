"""Analysis server models."""

# Import TypeScript models
from .typescript_models import (
    AnalysisError,
    # Progressive type resolution
    BasicTypeInfo,
    # Batch processing
    BatchFunctionRequest,
    BatchFunctionResult,
    BatchProcessingStats,
    CacheStats,
    CallGraphResult,
    CallSite,
    CallTraceResponse,
    # Call graph models
    ConditionalPath,
    EnhancedFunctionDetail,
    EnhancedFunctionDetailsResponse,
    FindReferencesResponse,
    FunctionDefinition,
    FunctionDetail,
    FunctionDetailsResponse,
    GenericTypeInfo,
    InferredTypeInfo,
    MemoryUsageStats,
    ParameterType,
    ParseResult,
    ParserStats,
    # Phase 3 advanced models
    TypeDefinition,
    TypeInstantiation,
    TypeResolutionMetadata,
    TypeResolutionResult,
)

__all__ = [
    "FindReferencesResponse",
    "FunctionDetailsResponse",
    "CallTraceResponse",
    "AnalysisError",
    "ParseResult",
    "ParserStats",
    # Phase 3 advanced models
    "TypeDefinition",
    "ParameterType",
    "FunctionDetail",
    "TypeResolutionMetadata",
    "TypeInstantiation",
    "CacheStats",
    "MemoryUsageStats",
    "BatchProcessingStats",
    "EnhancedFunctionDetail",
    "EnhancedFunctionDetailsResponse",
    # Progressive type resolution
    "BasicTypeInfo",
    "GenericTypeInfo",
    "InferredTypeInfo",
    "TypeResolutionResult",
    # Batch processing
    "BatchFunctionRequest",
    "BatchFunctionResult",
    # Call graph models
    "ConditionalPath",
    "CallGraphResult",
    "FunctionDefinition",
    "CallSite",
]
