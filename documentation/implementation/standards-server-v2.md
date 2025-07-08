# Standards Server Migration Implementation Plan

## Overview
Complete overhaul of the standards server to implement context-aware loading, smart compression, and session-based deduplication. No backwards compatibility required.

## Phase 1: Core Data Models

### 1.1 Create Enhanced Rule Structure
**File**: `models/enhanced_rule.py`

```python
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class RuleMetadata(BaseModel):
    """Metadata for smart loading and compression."""
    pattern_type: str  # validation, error-handling, routing, etc.
    complexity: str = "intermediate"  # basic, intermediate, advanced, expert
    rule_type: str = "must"  # must, should, may, must-not, should-not
    nextjs_api: List[str] = []  # app-router, pages-router, api-routes, etc.
    client_server: str = "isomorphic"  # client-only, server-only, isomorphic, edge

class RuleCompression(BaseModel):
    """Compression configuration."""
    example_sharable: bool = True
    pattern_extractable: bool = True
    progressive_detail: List[str] = ["minimal", "standard", "detailed", "full"]

class RuleExamples(BaseModel):
    """Multiple format examples."""
    minimal: Optional[str] = None  # ~20 tokens
    standard: Optional[str] = None  # ~100 tokens
    detailed: Optional[str] = None  # ~200 tokens
    full: str  # Original format
    reference: Optional[str] = None  # File reference
    context_variants: Dict[str, str] = {}  # app_router, pages_router, etc.

class TokenCount(BaseModel):
    """Token counts for different formats."""
    minimal: int = 20
    standard: int = 100
    detailed: int = 200
    full: int

class EnhancedRule(BaseModel):
    """Complete rule structure."""
    rule: str
    ruleId: str  # Unique identifier for deduplication
    context: str
    metadata: RuleMetadata
    compression: RuleCompression
    examples: RuleExamples
    tokens: TokenCount
    importMap: List[Dict[str, Any]] = []
    hasEslintRule: bool = False
    relationships: Dict[str, List[str]] = {}  # similar_rules, prerequisite_rules, etc.
```

### 1.2 Create Standard Metadata Structure
**File**: `models/standard_metadata.py`

```python
class ContextTriggers(BaseModel):
    """When to load this standard."""
    task_types: List[str] = []
    architectural_layers: List[str] = []
    code_patterns: List[str] = []
    import_indicators: List[str] = []
    file_patterns: List[str] = []
    nextjs_features: List[str] = []

class OptimizationHints(BaseModel):
    """How to optimize loading."""
    priority: str = "medium"  # critical, high, medium, low
    load_frequency: str = "conditional"  # always, common, conditional, rare
    compressible: bool = True
    cacheable: bool = True
    context_sensitive: bool = True
    example_reusability: str = "medium"  # high, medium, low

class EnhancedStandardMetadata(BaseModel):
    """Enhanced standard metadata."""
    id: str
    name: str
    category: str
    tags: List[str]
    applies_to: List[str]
    severity: str
    priority: str
    dependencies: List[str]

    # New fields
    context_triggers: ContextTriggers
    optimization: OptimizationHints
    relationships: Dict[str, List[str]] = {}
    nextjs_config: Dict[str, Any] = {}
```

## Phase 2: Session Management

### 2.1 Create Session Manager
**File**: `services/session_manager.py`

```python
from datetime import datetime
from typing import Dict, Set, List, Optional
import asyncio

class SessionState:
    """Track state for an AI session."""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.loaded_rule_ids: Set[str] = set()
        self.loaded_patterns: Set[str] = set()  # Track pattern types seen
        self.file_history: List[str] = []
        self.token_count: int = 0
        self.last_activity: datetime = datetime.now()
        self.context_cache: Dict[str, Any] = {}

class SessionManager:
    """Manage AI coding sessions."""
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.cleanup_interval = 3600  # 1 hour

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get existing session or create new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id)

        session = self.sessions[session_id]
        session.last_activity = datetime.now()
        return session

    def cleanup_stale_sessions(self):
        """Remove inactive sessions."""
        current_time = datetime.now()
        stale_sessions = [
            sid for sid, session in self.sessions.items()
            if (current_time - session.last_activity).seconds > self.cleanup_interval
        ]
        for sid in stale_sessions:
            del self.sessions[sid]
```

### 2.2 Create Context Detector
**File**: `services/context_detector.py`

```python
class ContextDetector:
    """Detect what the AI is working on."""

    def analyze_session_context(self, session: SessionState, current_file: str) -> Dict:
        """Comprehensive context analysis."""
        return {
            "task_type": self._detect_task_type(session, current_file),
            "architectural_layer": self._detect_layer(current_file),
            "technology_stack": self._detect_tech_stack(session),
            "complexity_level": self._assess_complexity(session),
            "working_area": self._detect_working_area(session.file_history),
            "nextjs_context": self._detect_nextjs_context(current_file, session)
        }

    def _detect_task_type(self, session: SessionState, current_file: str) -> str:
        """Detect what kind of task is being performed."""
        recent_files = session.file_history[-5:]

        # API development
        if "/api/" in current_file and any("route.ts" in f for f in recent_files):
            return "api_development"

        # Component development
        if any(f.endswith(('.tsx', '.jsx')) for f in recent_files):
            if len(set(recent_files)) == 1:
                return "component_refinement"
            return "component_development"

        # Testing
        if any('test' in f or 'spec' in f for f in recent_files):
            return "writing_tests"

        # Refactoring (multiple visits to same files)
        file_visits = {}
        for f in session.file_history:
            file_visits[f] = file_visits.get(f, 0) + 1
        if any(count >= 3 for count in file_visits.values()):
            return "refactoring"

        return "feature_development"

    def _detect_nextjs_context(self, file: str, session: SessionState) -> Dict:
        """Detect Next.js specific context."""
        return {
            "router_type": "app" if "/app/" in file else "pages" if "/pages/" in file else None,
            "is_api_route": "/api/" in file,
            "is_server_component": not any("use client" in open(f).read() for f in [file]),
            "route_type": self._detect_route_type(file),
            "rendering_strategy": self._detect_rendering_strategy(file, session)
        }
```

## Phase 3: Rule Compression Engine

### 3.1 Create Rule Compressor
**File**: `services/rule_compressor.py`

```python
class RuleCompressor:
    """Compress rules based on context."""

    def compress_rule(self, rule: EnhancedRule, context: Dict, session: SessionState) -> Dict:
        """Apply smart compression to a rule."""
        # Check if pattern was seen before
        if rule.metadata.pattern_type in session.loaded_patterns:
            return self._create_minimal_reference(rule)

        # Check complexity match
        if context["complexity_level"] == "expert" and rule.metadata.complexity == "basic":
            return self._create_minimal_rule(rule)

        # Progressive detail based on context
        detail_level = self._determine_detail_level(rule, context, session)
        return self._format_rule_for_level(rule, detail_level)

    def _determine_detail_level(self, rule: EnhancedRule, context: Dict, session: SessionState) -> str:
        """Determine appropriate detail level."""
        # First time seeing this pattern type
        if rule.metadata.pattern_type not in session.loaded_patterns:
            return "standard"

        # Task-specific detail
        if context["task_type"] == "debugging":
            return "minimal"  # Just reminders
        elif context["task_type"] == "learning":
            return "detailed"  # More explanation

        # Default to minimal with reference
        return "minimal"

    def _format_rule_for_level(self, rule: EnhancedRule, level: str) -> Dict:
        """Format rule for specific detail level."""
        if level == "minimal":
            return {
                "ruleId": rule.ruleId,
                "rule": rule.rule,
                "hint": rule.examples.minimal or f"Apply {rule.metadata.pattern_type} pattern",
                "ref": rule.examples.reference,
                "tokens": rule.tokens.minimal
            }
        elif level == "standard":
            return {
                "ruleId": rule.ruleId,
                "rule": rule.rule,
                "context": rule.context[:100] + "...",  # Truncated
                "example": rule.examples.standard,
                "imports": rule.importMap,
                "tokens": rule.tokens.standard
            }
        else:  # detailed or full
            return rule.dict()
```

### 3.2 Create Rule Grouper
**File**: `services/rule_grouper.py`

```python
class RuleGrouper:
    """Group similar rules for compression."""

    def group_similar_rules(self, rules: List[EnhancedRule]) -> List[Dict]:
        """Group rules by pattern type and similarity."""
        groups = {}

        for rule in rules:
            pattern = rule.metadata.pattern_type
            if pattern not in groups:
                groups[pattern] = []
            groups[pattern].append(rule)

        compressed_groups = []
        for pattern, group_rules in groups.items():
            if len(group_rules) == 1:
                compressed_groups.append(group_rules[0])
            else:
                compressed_groups.append(self._create_rule_group(pattern, group_rules))

        return compressed_groups

    def _create_rule_group(self, pattern: str, rules: List[EnhancedRule]) -> Dict:
        """Create compressed group representation."""
        return {
            "type": "rule_group",
            "pattern": pattern,
            "rules": [
                {
                    "ruleId": r.ruleId,
                    "specific": r.rule,
                    "when": r.metadata.get("applies_when", {})
                } for r in rules
            ],
            "common_example": rules[0].examples.minimal,
            "tokens": sum(r.tokens.minimal for r in rules) // 2  # Compressed
        }
```

## Phase 4: Update Existing Tools

### 4.1 Enhance hints_for_file Tool
**File**: `tools/standards/hints_for_file.py`

```python
def hints_for_file_impl(
    file_path: str,
    max_tokens: int = 10000,
    project_root: str | None = None,
    session_id: str | None = None  # NEW: Add session support
) -> dict:
    """Get relevant coding hints with smart compression and deduplication."""

    # Get or create session
    session = session_manager.get_or_create_session(session_id or "default")

    # Detect context
    context = context_detector.analyze_session_context(session, file_path)

    # Get relevant standards (existing scoring logic)
    relevant_standards = get_relevant_standards(file_path, project_root)

    # Process rules with compression and deduplication
    output_rules = []
    references = []
    current_tokens = 0

    for standard in relevant_standards:
        for rule in standard.rules:
            # Skip if already loaded in session
            if rule.ruleId in session.loaded_rule_ids:
                references.append({
                    "ruleId": rule.ruleId,
                    "ref": f"Previously loaded: {rule.rule[:50]}..."
                })
                continue

            # Compress based on context
            compressed_rule = rule_compressor.compress_rule(rule, context, session)
            rule_tokens = compressed_rule.get("tokens", 100)

            # Check token budget
            if current_tokens + rule_tokens > max_tokens:
                break

            output_rules.append(compressed_rule)
            current_tokens += rule_tokens

            # Track in session
            session.loaded_rule_ids.add(rule.ruleId)
            session.loaded_patterns.add(rule.metadata.pattern_type)

    # Update session
    session.file_history.append(file_path)
    session.token_count += current_tokens

    return {
        "file_path": file_path,
        "context": context,
        "rules": output_rules,
        "references": references,
        "total_tokens": current_tokens,
        "session_stats": {
            "rules_loaded": len(session.loaded_rule_ids),
            "patterns_seen": list(session.loaded_patterns),
            "files_processed": len(session.file_history)
        }
    }
```

### 4.2 Update register Tool
**File**: `tools/standards/register.py`

```python
def register_impl(
    source_path: str,
    metadata: dict | str,
    project_root: str | None = None
) -> dict:
    """Register a standard with enhanced metadata."""

    # Parse enhanced metadata
    if isinstance(metadata, str):
        metadata = json.loads(metadata)

    # Validate against new schema
    enhanced_metadata = EnhancedStandardMetadata(**metadata)

    # Extract and process rules with new structure
    rules = []
    for rule_data in metadata.get("rules", []):
        rule = EnhancedRule(**rule_data)

        # Auto-generate compression variants if not provided
        if not rule.examples.minimal and rule.examples.full:
            rule.examples.minimal = generate_minimal_example(rule)
        if not rule.examples.standard and rule.examples.full:
            rule.examples.standard = generate_standard_example(rule)

        # Calculate token counts
        rule.tokens = calculate_token_counts(rule)

        rules.append(rule)

    # Store with new structure
    store_standard(enhanced_metadata, rules, project_root)

    return {
        "success": True,
        "standard_id": enhanced_metadata.id,
        "rules_registered": len(rules),
        "optimization_enabled": enhanced_metadata.optimization.dict()
    }
```

### 4.3 Update Tool Registration
**File**: `tools/standards/__init__.py`

```python
def register_standards_tools(mcp: FastMCP) -> None:
    """Register all standards management tools with session support."""

    # Initialize services
    session_manager = SessionManager()
    context_detector = ContextDetector()
    rule_compressor = RuleCompressor()
    rule_grouper = RuleGrouper()

    # Start session cleanup task
    asyncio.create_task(session_cleanup_loop(session_manager))

    @mcp.tool(
        name="hints_for_file",
        description="Gets relevant hints with smart compression and session deduplication"
    )
    @json_convert
    def hints_for_file(
        file_path: str,
        max_tokens: int = 10000,
        project_root: str | None = None,
        session_id: str | None = None  # NEW parameter
    ) -> dict:
        """Get relevant coding hints for a specific file."""
        return hints_for_file_impl(
            file_path, max_tokens, project_root, session_id,
            session_manager, context_detector, rule_compressor
        )

    # ... other tools remain similar with enhanced functionality
```

## Phase 5: Helper Functions

### 5.1 Create Token Calculator
**File**: `utils/token_utils.py`

```python
def estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    # Rough estimate: 1 token ≈ 4 characters
    return len(text) // 4

def calculate_token_counts(rule: EnhancedRule) -> TokenCount:
    """Calculate token counts for all rule formats."""
    return TokenCount(
        minimal=estimate_tokens(rule.examples.minimal or ""),
        standard=estimate_tokens(rule.examples.standard or ""),
        detailed=estimate_tokens(rule.examples.detailed or ""),
        full=estimate_tokens(rule.examples.full)
    )
```

### 5.2 Create Example Generators
**File**: `utils/example_generators.py`

```python
def generate_minimal_example(rule: EnhancedRule) -> str:
    """Generate minimal example from full example."""
    # Extract key pattern
    if rule.metadata.pattern_type == "validation":
        return "schema.parse(input)"
    elif rule.metadata.pattern_type == "error-handling":
        return "try { ... } catch (e) { handleError(e) }"
    # ... other patterns

    # Fallback: extract first meaningful line
    lines = rule.examples.full.split('\n')
    for line in lines:
        if any(keyword in line for keyword in ['const', 'function', 'export']):
            return line.strip()
    return "// Apply pattern"

def generate_standard_example(rule: EnhancedRule) -> str:
    """Generate standard example from full example."""
    # Extract core implementation
    lines = rule.examples.full.split('\n')
    core_lines = []
    in_core = False

    for line in lines:
        if any(marker in line for marker in ['function', 'const', 'export']):
            in_core = True
        if in_core:
            core_lines.append(line)
            if line.strip() == '}':
                break

    return '\n'.join(core_lines[:10])  # Limit to 10 lines
```

## Implementation Order

1. **Week 1**: Implement core models and session management
   - Create enhanced data models
   - Implement session manager
   - Set up context detector

2. **Week 2**: Implement compression engine
   - Create rule compressor
   - Implement rule grouper
   - Add token counting utilities

3. **Week 3**: Update existing tools
   - Enhance hints_for_file with session support
   - Update register tool for new format
   - Add migration scripts

4. **Week 4**: Testing and optimization
   - Test with real coding sessions
   - Tune compression algorithms
   - Optimize context detection

## Success Metrics

- **Token Reduction**: Target 70-80% reduction in tokens per session
- **Response Time**: < 100ms for hint retrieval
- **Deduplication Rate**: > 90% of duplicate rules caught
- **Context Accuracy**: > 85% correct context detection

## Configuration

```yaml
# config/standards_server.yaml
optimization:
  max_session_duration: 3600  # 1 hour
  default_max_tokens: 10000
  compression_levels:
    - minimal: 20
    - standard: 100
    - detailed: 200
    - full: null  # No limit
  context_detection:
    file_history_window: 10
    pattern_detection_threshold: 0.7
```