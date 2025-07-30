"""Analysis server models."""

# Import TypeScript models
from .typescript_models import (
    FindReferencesResponse,
    FunctionDetailsResponse,
    CallTraceResponse,
    AnalysisError,
    ParseResult,
    ParserStats,
    # Phase 3 advanced models
    TypeDefinition,
    ParameterType,
    FunctionDetail,
    TypeResolutionMetadata,
    TypeInstantiation,
    CacheStats,
    MemoryUsageStats,
    BatchProcessingStats,
    EnhancedFunctionDetail,
    EnhancedFunctionDetailsResponse,
    # Progressive type resolution
    BasicTypeInfo,
    GenericTypeInfo,
    InferredTypeInfo,
    TypeResolutionResult,
    # Batch processing
    BatchFunctionRequest,
    BatchFunctionResult,
    # Call graph models
    ConditionalPath,
    CallGraphResult,
    FunctionDefinition,
    CallSite,
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
