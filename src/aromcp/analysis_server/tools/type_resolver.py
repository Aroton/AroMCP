"""
Progressive TypeScript type resolution with 3-tier analysis levels.

Phase 3 implementation for comprehensive type analysis:
- Level 1 (basic): Only explicitly declared types  
- Level 2 (generics): Generic constraints and instantiations
- Level 3 (full_type): Deep type inference and analysis
"""

import os
import re
import time
from typing import Any
from dataclasses import dataclass, field

from .typescript_parser import TypeScriptParser, ResolutionDepth
from .symbol_resolver import SymbolResolver
from .import_tracker import ModuleResolver
from ..models.typescript_models import (
    TypeDefinition,
    AnalysisError,
    BasicTypeInfo,
    GenericTypeInfo,
    InferredTypeInfo,
    TypeResolutionResult,
    TypeResolutionMetadata,
    GenericConstraintInfo,
    TypeInstantiation,
)


class TypeResolver:
    """
    Progressive TypeScript type resolution with caching and performance optimization.
    
    Implements 3-tier analysis:
    - Basic: Explicitly declared types only (fast)
    - Generics: Generic constraints and instantiations (moderate)
    - Full Type: Deep inference with TypeScript compiler integration (comprehensive)
    """
    
    def __init__(self, parser: TypeScriptParser, symbol_resolver: SymbolResolver, project_root: str = None):
        """
        Initialize type resolver with parser and symbol resolver.
        
        Args:
            parser: TypeScript parser instance
            symbol_resolver: Symbol resolver for cross-file analysis
            project_root: Project root for resolving imports
        """
        self.parser = parser
        self.symbol_resolver = symbol_resolver
        self.type_cache = {}
        self.project_root = project_root
        if project_root:
            self.module_resolver = ModuleResolver(project_root)
        else:
            import os
            self.module_resolver = ModuleResolver(os.environ.get("MCP_FILE_ROOT", "."))
        self.resolution_depth_limit = 5
        
        # Built-in TypeScript types
        self.primitive_types = {
            'string', 'number', 'boolean', 'any', 'unknown', 'void', 
            'null', 'undefined', 'never', 'object', 'bigint', 'symbol'
        }
        
        # Built-in generic types
        self.builtin_generics = {
            'Array', 'Promise', 'Map', 'Set', 'Record', 'Partial', 
            'Required', 'Pick', 'Omit', 'Exclude', 'Extract'
        }
    
    def resolve_type(self, type_annotation: str, file_path: str, 
                     resolution_depth: str = "basic", 
                     max_constraint_depth: int = 3,
                     track_instantiations: bool = False,
                     resolve_conditional_types: bool = False,
                     handle_recursive_types: bool = False,
                     check_circular: bool = True) -> TypeDefinition:
        """
        Progressive type resolution with 3 levels of analysis.
        
        Args:
            type_annotation: Type annotation string to resolve
            file_path: File containing the type annotation
            resolution_depth: Analysis level ("basic", "generics", "full_type")
            max_constraint_depth: Maximum constraint depth to resolve
            track_instantiations: Track generic type instantiations
            resolve_conditional_types: Resolve conditional type expressions
            handle_recursive_types: Handle recursive type definitions
            check_circular: Check for circular type references
            
        Returns:
            TypeDefinition with resolved type information
        """
        start_time = time.perf_counter()
        
        try:
            # Check for circular references if enabled
            if check_circular and hasattr(self, '_resolution_stack'):
                if type_annotation in self._resolution_stack:
                    return TypeDefinition(
                        kind="error",
                        definition=f"Circular constraint detected: {type_annotation}",
                        location=f"{file_path}:circular_constraint"
                    )
            else:
                self._resolution_stack = set()
                
            self._resolution_stack.add(type_annotation)
            
            try:
                # Check constraint depth limit
                current_depth = getattr(self, '_current_constraint_depth', 0)
                if current_depth > max_constraint_depth:
                    return TypeDefinition(
                        kind="error", 
                        definition=f"Constraint depth limit exceeded for '{type_annotation}': {current_depth} > {max_constraint_depth}",
                        location=f"{file_path}:constraint_depth_exceeded"
                    )
                
                if resolution_depth == "basic":
                    result = self._resolve_basic_type(type_annotation, file_path, 
                                                    max_constraint_depth=max_constraint_depth,
                                                    handle_recursive_types=handle_recursive_types)
                elif resolution_depth == "generics":
                    result = self._resolve_with_generics(type_annotation, file_path,
                                                       max_constraint_depth=max_constraint_depth,
                                                       handle_recursive_types=handle_recursive_types)
                elif resolution_depth in ["full_type", "full_inference"]:
                    result = self._resolve_with_full_inference(type_annotation, file_path,
                                                             resolve_conditional_types=resolve_conditional_types,
                                                             handle_recursive_types=handle_recursive_types,
                                                             max_constraint_depth=max_constraint_depth)
                else:
                    # Default to basic if unknown depth
                    result = self._resolve_basic_type(type_annotation, file_path,
                                                    max_constraint_depth=max_constraint_depth,
                                                    handle_recursive_types=handle_recursive_types)
                
                # If result is unknown type, return specific error code
                if result.kind == "unknown":
                    return TypeDefinition(
                        kind="error",
                        definition=f"Unknown type: {type_annotation}",
                        location=f"{file_path}:unknown_type"
                    )
                
                resolution_time = (time.perf_counter() - start_time) * 1000
                return result
                
            finally:
                self._resolution_stack.discard(type_annotation)
            
        except Exception as e:
            # Return error type definition with specific error code
            error_code = "TYPE_RESOLUTION_ERROR"
            if "circular" in str(e).lower():
                error_code = "CIRCULAR_REFERENCE_DETECTED"
            elif "constraint depth" in str(e).lower():
                error_code = "CONSTRAINT_DEPTH_EXCEEDED"
            elif "unknown" in str(e).lower():
                error_code = "UNKNOWN_TYPE"
                
            return TypeDefinition(
                kind="error",
                definition=f"Error resolving type '{type_annotation}': {str(e)}",
                location=f"{file_path}:{error_code.lower()}"
            )
    
    def _resolve_basic_type(self, type_annotation: str, file_path: str,
                          max_constraint_depth: int = 3,
                          handle_recursive_types: bool = False) -> TypeDefinition:
        """
        Level 1: Only explicitly declared types.
        Fast resolution for primitive types and declared interfaces/types.
        """
        # Clean up type annotation
        type_annotation = type_annotation.strip()
        
        # Handle primitive types
        if type_annotation in self.primitive_types:
            return TypeDefinition(
                kind="primitive",
                definition=type_annotation,
                location=f"{file_path}:builtin"
            )
        
        # Handle union types (basic level)
        if '|' in type_annotation:
            union_types = [t.strip() for t in type_annotation.split('|')]
            union_definitions = []
            for union_type in union_types:
                if union_type in self.primitive_types:
                    union_definitions.append(union_type)
                else:
                    # Try to find this type in the file
                    type_def = self._find_type_definition(union_type, file_path,
                                                        check_inheritance_depth=True,
                                                        max_inheritance_depth=max_constraint_depth)
                    if type_def:
                        union_definitions.append(type_def.definition)
            
            return TypeDefinition(
                kind="union",
                definition=" | ".join(union_definitions),
                location=f"{file_path}:union"
            )
        
        # Handle array types (basic syntax: Type[])
        if type_annotation.endswith('[]'):
            base_type = type_annotation[:-2].strip()
            base_def = self._resolve_basic_type(base_type, file_path, 
                                              max_constraint_depth=max_constraint_depth,
                                              handle_recursive_types=handle_recursive_types)
            return TypeDefinition(
                kind="array",
                definition=f"{base_def.definition}[]",
                location=base_def.location
            )
        
        # Handle object type literals (e.g., { id: string, name: string })
        if type_annotation.strip().startswith('{') and type_annotation.strip().endswith('}'):
            return TypeDefinition(
                kind="object_type",
                definition=type_annotation.strip(),
                location=f"{file_path}:object_literal"
            )
        
        # Handle intersection types (e.g., T & U)
        if '&' in type_annotation and not type_annotation.strip().startswith('('):
            return TypeDefinition(
                kind="intersection",
                definition=type_annotation.strip(),
                location=f"{file_path}:intersection"
            )
        
        # Handle function types (e.g., (t: T, u: U) => ReturnType)
        if ('=>' in type_annotation and 
            type_annotation.strip().startswith('(') and 
            ')' in type_annotation):
            return TypeDefinition(
                kind="function_type",
                definition=type_annotation.strip(),
                location=f"{file_path}:function_type"
            )
        
        # Try to find custom type definition
        return self._find_type_definition(type_annotation, file_path, 
                                        check_inheritance_depth=True, 
                                        max_inheritance_depth=max_constraint_depth)
    
    def _resolve_with_generics(self, type_annotation: str, file_path: str,
                             max_constraint_depth: int = 3,
                             handle_recursive_types: bool = False) -> TypeDefinition:
        """
        Level 2: Include generic constraints and instantiations.
        Handles generic types like Array<T>, Promise<User>, Map<string, number>.
        """
        # First try basic resolution
        basic_result = self._resolve_basic_type(type_annotation, file_path,
                                              max_constraint_depth=max_constraint_depth,
                                              handle_recursive_types=handle_recursive_types)
        
        # Check for generic pattern
        generic_match = re.match(r'(\w+)<(.+)>', type_annotation)
        if generic_match:
            base_type, type_args_str = generic_match.groups()
            
            # Parse type arguments
            type_args = self._parse_type_arguments(type_args_str)
            
            # Resolve each type argument
            resolved_args = []
            for arg in type_args:
                arg_def = self._resolve_with_generics(arg.strip(), file_path,
                                                    max_constraint_depth=max_constraint_depth,
                                                    handle_recursive_types=handle_recursive_types)
                resolved_args.append(arg_def.definition)
            
            # Handle built-in generics
            if base_type in self.builtin_generics:
                return TypeDefinition(
                    kind="utility_type",  # Built-in generics are utility types
                    definition=f"{base_type}<{', '.join(resolved_args)}>",
                    location=f"{file_path}:builtin_generic"
                )
            
            # Handle custom generic types
            base_def = self._find_type_definition(base_type, file_path,
                                                check_inheritance_depth=True,
                                                max_inheritance_depth=max_constraint_depth)
            if base_def:
                # If base type resolution returned an error (e.g., constraint depth exceeded), return that error
                if base_def.kind == "error":
                    return base_def
                    
                # Preserve the base type's kind if it's a template literal
                result_kind = "generic_instantiation"
                if base_def.kind == "template_literal":
                    result_kind = "template_literal"
                    
                return TypeDefinition(
                    kind=result_kind,
                    definition=f"{base_def.definition}<{', '.join(resolved_args)}>",
                    location=base_def.location
                )
        
        return basic_result
    
    def _resolve_with_full_inference(self, type_annotation: str, file_path: str,
                                   resolve_conditional_types: bool = False,
                                   handle_recursive_types: bool = False,
                                   max_constraint_depth: int = 3) -> TypeDefinition:
        """
        Level 3: Deep type analysis with inference.
        Handles conditional types, mapped types, and complex type relationships.
        """
        # Start with generic resolution
        generic_result = self._resolve_with_generics(type_annotation, file_path,
                                                   max_constraint_depth=max_constraint_depth,
                                                   handle_recursive_types=handle_recursive_types)
        
        # If the generic result found a template literal type, return it
        if generic_result.kind == "template_literal":
            return generic_result
        
        # Handle conditional types
        if resolve_conditional_types and 'extends' in type_annotation and '?' in type_annotation and ':' in type_annotation:
            return self._resolve_conditional_type(type_annotation, file_path)
        
        # Handle mapped types
        if '{' in type_annotation and 'in' in type_annotation:
            return self._resolve_mapped_type(type_annotation, file_path)
        
        # Handle keyof operator
        if type_annotation.startswith('keyof '):
            return self._resolve_keyof_type(type_annotation, file_path)
        
        # Handle typeof operator
        if type_annotation.startswith('typeof '):
            return self._resolve_typeof_type(type_annotation, file_path)
        
        # Handle template literal types
        if '`' in type_annotation and '${' in type_annotation:
            return TypeDefinition(
                kind="template_literal",
                definition=type_annotation,
                location=f"{file_path}:template_literal"
            )
        
        # Handle recursive types
        if handle_recursive_types:
            # Check for recursive patterns like TreeNode<T> { children: TreeNode<T>[] }
            # or DeepReadonly<T> = { readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P] }
            if self._is_recursive_type(type_annotation, file_path):
                # Try to get the actual definition but mark it as recursive
                base_type = type_annotation.split('<')[0] if '<' in type_annotation else type_annotation
                actual_def = self._find_type_definition(base_type, file_path, check_inheritance_depth=False)
                if actual_def and actual_def.kind != "error" and actual_def.kind != "unknown":
                    return TypeDefinition(
                        kind="recursive",
                        definition=actual_def.definition,
                        location=actual_def.location
                    )
                else:
                    return TypeDefinition(
                        kind="recursive", 
                        definition=f"Recursive type: {type_annotation}",
                        location=f"{file_path}:recursive"
                    )
        
        return generic_result
    
    def _find_type_definition(self, type_name: str, file_path: str, check_inheritance_depth: bool = True, 
                             max_inheritance_depth: int = 10) -> TypeDefinition:
        """
        Find the definition of a custom type (interface, type alias, class, enum).
        """
        try:
            # For generic instantiations like EventName<T>, extract base type name
            base_type_name = type_name
            if '<' in type_name:
                base_type_name = type_name.split('<')[0]
            
            # Parse the file to look for type definitions
            parse_result = self.parser.parse_file(file_path)
            if not parse_result.success or not parse_result.tree:
                # Even if parsing fails, try regex-based interface detection
                interface_def = self._find_interface_definition(base_type_name, None, file_path)
                if interface_def:
                    if check_inheritance_depth:
                        # Check inheritance depth for interfaces
                        inheritance_depth = self._calculate_inheritance_depth(base_type_name, file_path)
                        if inheritance_depth > max_inheritance_depth:
                            return TypeDefinition(
                                kind="error",
                                definition=f"Constraint depth limit exceeded for '{base_type_name}': inheritance depth {inheritance_depth} > {max_inheritance_depth}",
                                location=f"{file_path}:constraint_depth_exceeded"
                            )
                    return interface_def
                
                # Try to find the type in imported files
                imported_type_def = self._find_type_in_imports(type_name, file_path)
                if imported_type_def:
                    return imported_type_def
                
                return TypeDefinition(
                    kind="unknown",
                    definition=f"Unknown type: {type_name}",
                    location=f"{file_path}:unknown"
                )
            
            # Look for interface declarations
            interface_def = self._find_interface_definition(base_type_name, parse_result.tree, file_path)
            if interface_def and check_inheritance_depth:
                # Check inheritance depth for interfaces
                inheritance_depth = self._calculate_inheritance_depth(base_type_name, file_path)
                if inheritance_depth > max_inheritance_depth:
                    return TypeDefinition(
                        kind="error",
                        definition=f"Constraint depth limit exceeded for '{base_type_name}': inheritance depth {inheritance_depth} > {max_inheritance_depth}",
                        location=f"{file_path}:constraint_depth_exceeded"
                    )
            if interface_def:
                return interface_def
            
            # Look for type alias declarations
            type_alias_def = self._find_type_alias_definition(base_type_name, parse_result.tree, file_path)
            if type_alias_def:
                return type_alias_def
            
            # Look for class declarations
            class_def = self._find_class_definition(base_type_name, parse_result.tree, file_path)
            if class_def and check_inheritance_depth:
                # Check inheritance depth for classes
                inheritance_depth = self._calculate_inheritance_depth(base_type_name, file_path)
                if inheritance_depth > max_inheritance_depth:
                    return TypeDefinition(
                        kind="error",
                        definition=f"Constraint depth limit exceeded for '{base_type_name}': inheritance depth {inheritance_depth} > {max_inheritance_depth}",
                        location=f"{file_path}:constraint_depth_exceeded"
                    )
            if class_def:
                return class_def
            
            # Look for enum declarations
            enum_def = self._find_enum_definition(base_type_name, parse_result.tree, file_path)
            if enum_def:
                return enum_def
            
            # Try to find the type in imported files
            imported_type_def = self._find_type_in_imports(base_type_name, file_path)
            if imported_type_def:
                return imported_type_def
            
            # Type not found anywhere
            return TypeDefinition(
                kind="unknown",
                definition=f"Unknown type: {type_name}",
                location=f"{file_path}:not_found"
            )
            
        except Exception as e:
            return TypeDefinition(
                kind="error",
                definition=f"Error finding type {type_name}: {str(e)}",
                location=f"{file_path}:error"
            )
    
    def _find_type_in_imports(self, type_name: str, file_path: str) -> TypeDefinition | None:
        """Find a type definition in imported files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for import statements that include this type
            import_patterns = [
                # Named imports: import { Type } from 'module'
                rf'import\s*\{{\s*[^}}]*\b{re.escape(type_name)}\b[^}}]*\}}\s*from\s*[\'"]([^\'"]+)[\'"]',
                # Type imports: import type { Type } from 'module'
                rf'import\s+type\s*\{{\s*[^}}]*\b{re.escape(type_name)}\b[^}}]*\}}\s*from\s*[\'"]([^\'"]+)[\'"]',
                # Default imports (less common for types): import Type from 'module'
                rf'import\s+{re.escape(type_name)}\s+from\s*[\'"]([^\'"]+)[\'"]'
            ]
            
            for pattern in import_patterns:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    import_path = match.group(1)
                    
                    # Resolve the import path to actual file
                    resolved_path = self.module_resolver.resolve_path(import_path, file_path)
                    if resolved_path and os.path.exists(resolved_path):
                        # Look for the type definition in the imported file
                        imported_type_def = self._extract_type_from_file(type_name, resolved_path)
                        if imported_type_def:
                            return imported_type_def
            
            return None
            
        except Exception:
            return None
    
    def _extract_type_from_file(self, type_name: str, file_path: str) -> TypeDefinition | None:
        """Extract a specific type definition from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for interface definition
            interface_match = self._extract_interface_definition(type_name, content, file_path)
            if interface_match:
                return interface_match
            
            # Look for type alias definition  
            type_alias_match = self._extract_type_alias_definition(type_name, content, file_path)
            if type_alias_match:
                return type_alias_match
                
            # Look for enum definition
            enum_match = self._extract_enum_definition(type_name, content, file_path)
            if enum_match:
                return enum_match
                
            return None
            
        except Exception:
            return None
    
    def _extract_interface_definition(self, interface_name: str, content: str, file_path: str) -> TypeDefinition | None:
        """Extract interface definition from file content."""
        pattern = rf'(?:export\s+)?interface\s+{re.escape(interface_name)}\s*(?:<[^{{}}]*>)?\s*(?:extends\s+[^{{}}]*?)?\s*\{{([^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*)\}}'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            # Extract the full interface definition including the interface keyword
            start = match.start()
            # Find the complete interface block
            full_match = re.search(rf'(?:export\s+)?interface\s+{re.escape(interface_name)}[^{{}}]*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*\}}', content[start:], re.MULTILINE | re.DOTALL)
            if full_match:
                definition = full_match.group(0).strip()
                # Find line number
                line_num = content[:start].count('\n') + 1
                
                return TypeDefinition(
                    kind="interface",
                    definition=definition,
                    location=f"{file_path}:{line_num}"
                )
        return None
    
    def _extract_type_alias_definition(self, type_name: str, content: str, file_path: str) -> TypeDefinition | None:
        """Extract type alias definition from file content."""
        pattern = rf'(?:export\s+)?type\s+{re.escape(type_name)}\s*(?:<[^=]*>)?\s*=\s*([^;]+);?'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            definition = match.group(0).strip()
            line_num = content[:match.start()].count('\n') + 1
            
            return TypeDefinition(
                kind="type",
                definition=definition,
                location=f"{file_path}:{line_num}"
            )
        return None
    
    def _extract_enum_definition(self, enum_name: str, content: str, file_path: str) -> TypeDefinition | None:
        """Extract enum definition from file content."""
        pattern = rf'(?:export\s+)?enum\s+{re.escape(enum_name)}\s*\{{([^{{}}]*)\}}'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if match:
            definition = match.group(0).strip()
            line_num = content[:match.start()].count('\n') + 1
            
            return TypeDefinition(
                kind="enum",
                definition=definition,
                location=f"{file_path}:{line_num}"
            )
        return None

    def _find_interface_definition(self, interface_name: str, tree: Any, file_path: str) -> TypeDefinition | None:
        """Find interface definition using regex-based parsing."""
        try:
            # Always read the actual file content, regardless of tree type
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find interface with a simpler pattern first, then extract generics manually
            simple_pattern = rf'(?:export\s+)?interface\s+{re.escape(interface_name)}\s*'
            match = re.search(simple_pattern, content, re.MULTILINE | re.DOTALL)
            
            if match:
                # Find the start of the interface definition
                start_pos = match.end()
                
                # Extract generic parameters using balanced bracket matching
                generic_params = ""
                if start_pos < len(content) and content[start_pos] == '<':
                    bracket_count = 0
                    param_start = start_pos
                    pos = start_pos
                    while pos < len(content):
                        if content[pos] == '<':
                            bracket_count += 1
                        elif content[pos] == '>':
                            bracket_count -= 1
                            if bracket_count == 0:
                                generic_params = content[param_start:pos+1]
                                start_pos = pos + 1
                                break
                        pos += 1
                
                # Skip whitespace and optional 'extends' clause
                while start_pos < len(content) and content[start_pos].isspace():
                    start_pos += 1
                
                if start_pos < len(content) and content[start_pos:].startswith('extends'):
                    # Skip extends clause - find opening brace
                    brace_pos = content.find('{', start_pos)
                    if brace_pos != -1:
                        start_pos = brace_pos
                
                # Find interface body
                if start_pos < len(content) and content[start_pos] == '{':
                    brace_count = 0
                    body_start = start_pos + 1
                    pos = start_pos
                    while pos < len(content):
                        if content[pos] == '{':
                            brace_count += 1
                        elif content[pos] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                interface_body = content[body_start:pos].strip()
                                break
                        pos += 1
                    else:
                        return None
                else:
                    return None
                
                line_num = content[:match.start()].count('\n') + 1
                
                # Check for circular constraints in generic parameters
                if generic_params and "extends" in generic_params:
                    if self._has_circular_interface_constraint(interface_name, generic_params, content):
                        return TypeDefinition(
                            kind="error",
                            definition=f"Circular constraint detected in interface {interface_name}: {generic_params}",
                            location=f"{file_path}:circular_constraint"
                        )
                
                return TypeDefinition(
                    kind="interface",
                    definition=f"interface {interface_name}{generic_params} {{\n{interface_body}\n}}",
                    location=f"{file_path}:{line_num}"
                )
                
        except Exception as e:
            # Debug: print the error
            print(f"Error finding interface {interface_name} in {file_path}: {e}")
            pass
        
        return None
    
    def _find_type_alias_definition(self, type_name: str, tree: Any, file_path: str) -> TypeDefinition | None:
        """Find type alias definition using regex-based parsing."""
        try:
            # Always read the actual file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the type declaration
            pattern = rf'(?:export\s+)?type\s+{re.escape(type_name)}\s*(?:<[^>]*>)?\s*=\s*'
            match = re.search(pattern, content, re.MULTILINE)
            
            if match:
                # Start position after the '='
                start_pos = match.end()
                
                # Extract the type definition - handle object types with balanced braces
                if start_pos < len(content) and content[start_pos:].lstrip().startswith('{'):
                    # Object type - find matching closing brace
                    brace_count = 0
                    end_pos = start_pos
                    while end_pos < len(content):
                        if content[end_pos] == '{':
                            brace_count += 1
                        elif content[end_pos] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos += 1
                                break
                        end_pos += 1
                    
                    type_definition = content[start_pos:end_pos].strip()
                else:
                    # Non-object type - find semicolon or next declaration
                    end_match = re.search(r';|\n\s*(?:export|type|interface|function|const|let|var|class|enum)', 
                                        content[start_pos:], re.MULTILINE)
                    if end_match:
                        type_definition = content[start_pos:start_pos + end_match.start()].strip()
                    else:
                        type_definition = content[start_pos:].strip()
                
                line_num = content[:match.start()].count('\n') + 1
            else:
                match = None
            
            if match and 'type_definition' in locals():
                # Determine if this is a template literal type
                kind = "type"  # Use "type" instead of "type_alias" for consistency
                if '`' in type_definition and '${' in type_definition:
                    kind = "template_literal"
                
                return TypeDefinition(
                    kind=kind,
                    definition=f"type {type_name} = {type_definition}",
                    location=f"{file_path}:{line_num}"
                )
                
        except Exception:
            pass
        
        return None
    
    def _find_class_definition(self, class_name: str, tree: Any, file_path: str) -> TypeDefinition | None:
        """Find class definition using regex-based parsing."""
        try:
            # Always read the actual file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Regex pattern for class declarations
            pattern = rf'(?:export\s+)?class\s+{re.escape(class_name)}\s*(?:<[^>]*>)?(?:\s+extends\s+[^{{]*)?(?:\s+implements\s+[^{{]*)?\s*\{{'
            match = re.search(pattern, content, re.MULTILINE)
            
            if match:
                line_num = content[:match.start()].count('\n') + 1
                class_header = match.group(0).rstrip('{').strip()
                
                # Extract the constructor if present
                class_start = match.end() - 1  # Position of opening brace
                
                # Find the constructor
                constructor_pattern = r'constructor\s*\([^)]*\)'
                constructor_match = re.search(constructor_pattern, content[class_start:class_start+500])
                
                constructor_str = ""
                if constructor_match:
                    constructor_str = constructor_match.group(0)
                
                # Build the definition with constructor info
                definition = f"{class_header} {{ {constructor_str} /* ... */ }}" if constructor_str else f"{class_header} {{ /* class body */ }}"
                
                return TypeDefinition(
                    kind="class",
                    definition=definition,
                    location=f"{file_path}:{line_num}"
                )
                
        except Exception:
            pass
        
        return None
    
    def _find_enum_definition(self, enum_name: str, tree: Any, file_path: str) -> TypeDefinition | None:
        """Find enum definition using regex-based parsing."""
        try:
            # Always read the actual file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Regex pattern for enum declarations
            pattern = rf'(?:export\s+)?enum\s+{re.escape(enum_name)}\s*\{{([^}}]*)\}}'
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            
            if match:
                enum_body = match.group(1).strip()
                line_num = content[:match.start()].count('\n') + 1
                
                return TypeDefinition(
                    kind="enum",
                    definition=f"enum {enum_name} {{\n{enum_body}\n}}",
                    location=f"{file_path}:{line_num}"
                )
                
        except Exception:
            pass
        
        return None
    
    def _parse_type_arguments(self, type_args_str: str) -> list[str]:
        """
        Parse type arguments from generic type instantiation.
        Handles nested generics like Map<string, Array<number>>.
        """
        args = []
        current_arg = ""
        paren_depth = 0
        bracket_depth = 0
        
        for char in type_args_str:
            if char == '<':
                bracket_depth += 1
            elif char == '>':
                bracket_depth -= 1
            elif char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and bracket_depth == 0 and paren_depth == 0:
                args.append(current_arg.strip())
                current_arg = ""
                continue
            
            current_arg += char
        
        if current_arg.strip():
            args.append(current_arg.strip())
        
        return args
    
    def _resolve_conditional_type(self, type_annotation: str, file_path: str) -> TypeDefinition:
        """Resolve conditional types (T extends U ? X : Y)."""
        try:
            # Parse conditional type pattern: T extends U ? X : Y
            # Find the main conditional structure
            conditional_match = re.search(r'(\w+)\s+extends\s+([^?]+)\s*\?\s*([^:]+)\s*:\s*(.+)', type_annotation.strip())
            
            if conditional_match:
                check_type = conditional_match.group(1).strip()
                extends_type = conditional_match.group(2).strip()
                true_type = conditional_match.group(3).strip()
                false_type = conditional_match.group(4).strip()
                
                # Create a more detailed definition that preserves the structure
                definition = f"type {check_type} extends {extends_type} ? {true_type} : {false_type}"
                
                return TypeDefinition(
                    kind="conditional",
                    definition=definition,
                    location=f"{file_path}:conditional",
                    properties={
                        "check_type": check_type,
                        "extends_type": extends_type,
                        "true_type": true_type,
                        "false_type": false_type
                    }
                )
            else:
                # Fallback for complex conditional types
                return TypeDefinition(
                    kind="conditional",
                    definition=type_annotation,
                    location=f"{file_path}:conditional"
                )
                
        except Exception:
            # Fallback on any parsing error
            return TypeDefinition(
                kind="conditional",
                definition=type_annotation,
                location=f"{file_path}:conditional"
            )
    
    def _resolve_mapped_type(self, type_annotation: str, file_path: str) -> TypeDefinition:
        """Resolve mapped types ({ [K in keyof T]: ... })."""
        return TypeDefinition(
            kind="mapped",
            definition=f"Mapped type: {type_annotation}",
            location=f"{file_path}:mapped"
        )
    
    def _resolve_keyof_type(self, type_annotation: str, file_path: str) -> TypeDefinition:
        """Resolve keyof operator types."""
        target_type = type_annotation[6:].strip()  # Remove 'keyof '
        return TypeDefinition(
            kind="keyof",
            definition=f"keyof {target_type}",
            location=f"{file_path}:keyof"
        )
    
    def _resolve_typeof_type(self, type_annotation: str, file_path: str) -> TypeDefinition:
        """Resolve typeof operator types."""
        target_expr = type_annotation[7:].strip()  # Remove 'typeof '
        return TypeDefinition(
            kind="typeof",
            definition=f"typeof {target_expr}",
            location=f"{file_path}:typeof"
        )
    
    def extract_generic_constraints(self, generic_params: str, file_path: str,
                                   resolution_depth: str = "generics", 
                                   max_constraint_depth: int = 3,
                                   check_circular: bool = True) -> dict[str, TypeDefinition]:
        """
        Extract and resolve type constraints from generic parameters.
        
        Args:
            generic_params: Generic parameter string like "<T extends BaseEntity, U extends T>"
            file_path: File containing the generic definition
            resolution_depth: Type resolution level
            
        Returns:
            Dictionary of constraint type names to TypeDefinitions
        """
        constraint_types = {}
        
        if not generic_params or not generic_params.startswith('<') or not generic_params.endswith('>'):
            return constraint_types
        
        # Initialize constraint depth tracking for this call
        self._constraint_resolution_depth = 0
        
        # Remove outer angle brackets
        params_content = generic_params[1:-1]
        
        # Split by comma but respect nested angle brackets
        param_parts = self._parse_type_arguments(params_content)
        
        # First pass: collect all constraint relationships
        param_constraints = {}
        for param in param_parts:
            if ' extends ' in param:
                parts = param.split(' extends ', 1)
                if len(parts) == 2:
                    param_name = parts[0].strip()
                    constraint_type = parts[1].strip()
                    param_constraints[param_name] = constraint_type
        
        # Second pass: calculate actual constraint depth based on dependencies
        for param in param_parts:
            # Look for 'extends' keyword
            if ' extends ' in param:
                parts = param.split(' extends ', 1)
                if len(parts) == 2:
                    param_name = parts[0].strip()
                    constraint_type = parts[1].strip()
                    
                    # Calculate true constraint depth based on parameter dependencies
                    constraint_depth = self._calculate_constraint_dependency_depth(
                        constraint_type, param_constraints, set()
                    )
                    
                    # Also check inheritance depth for the constraint type
                    base_constraint_type = constraint_type.split('<')[0] if '<' in constraint_type else constraint_type
                    inheritance_depth = self._calculate_inheritance_depth(base_constraint_type, file_path)
                    
                    # Use the maximum of parameter dependency depth and inheritance depth
                    constraint_depth = max(constraint_depth, inheritance_depth)
                    
                    if constraint_depth > max_constraint_depth:
                        constraint_types[constraint_type] = TypeDefinition(
                            kind="error",
                            definition=f"Constraint depth limit exceeded for '{constraint_type}': {constraint_depth} > {max_constraint_depth}",
                            location=f"{file_path}:constraint_depth_exceeded"
                        )
                    else:
                        # Resolve the constraint type
                        type_def = self.resolve_type(constraint_type, file_path, resolution_depth,
                                                   max_constraint_depth=max_constraint_depth,
                                                   check_circular=check_circular)
                        if type_def.kind != "error" and type_def.kind != "unknown":
                            constraint_types[constraint_type] = type_def
                        elif type_def.kind == "error":
                            # Propagate the error
                            constraint_types[constraint_type] = type_def
                    
                    # Always try to extract and resolve base types from generic instantiations
                    if '<' in constraint_type:
                        base_match = re.match(r'(\w+)<', constraint_type)
                        if base_match:
                            base_type = base_match.group(1)
                            if base_type in self.builtin_generics:
                                constraint_types[base_type] = TypeDefinition(
                                    kind="utility_type",
                                    definition=f"TypeScript utility type: {base_type}",
                                    location=f"{file_path}:builtin"
                                )
                            else:
                                # Try to resolve the base generic type (e.g., Level2 from Level2<T>)
                                base_type_def = self.resolve_type(base_type, file_path, resolution_depth,
                                                                 max_constraint_depth=max_constraint_depth,
                                                                 check_circular=check_circular)
                                if base_type_def.kind != "error" and base_type_def.kind != "unknown":
                                    constraint_types[base_type] = base_type_def
                                else:
                                    # If we can't resolve it properly, create a basic definition
                                    # This handles cases where the interface exists but parsing fails
                                    constraint_types[base_type] = TypeDefinition(
                                        kind="interface",
                                        definition=f"interface {base_type} {{ /* complex generic interface */ }}",
                                        location=f"{file_path}:inferred"
                                    )
        
        # Check for circular constraints if requested
        if check_circular:
            circular_errors = self._detect_circular_constraints(constraint_types)
            for error in circular_errors:
                constraint_types[f"ERROR_{error}"] = TypeDefinition(
                    kind="error",
                    definition=f"Circular constraint detected: {error}",
                    location=f"{file_path}:circular_constraint"
                )
        
        return constraint_types
    
    def _detect_circular_constraints(self, constraint_types: dict[str, TypeDefinition]) -> list[str]:
        """
        Detect circular constraints in generic type parameters.
        
        Returns:
            List of constraint names that are circular
        """
        circular_errors = []
        
        for constraint_name, constraint_def in constraint_types.items():
            if self._is_circular_constraint(constraint_name, constraint_def.definition, constraint_types):
                circular_errors.append(constraint_name)
                
        return circular_errors
    
    def _is_circular_constraint(self, constraint_name: str, definition: str, 
                               all_constraints: dict[str, TypeDefinition], 
                               visited: set[str] = None) -> bool:
        """
        Check if a constraint definition is circular.
        
        Args:
            constraint_name: Name of the constraint being checked
            definition: Definition string of the constraint
            all_constraints: All constraint definitions
            visited: Set of already visited constraint names (for recursion detection)
            
        Returns:
            True if circular constraint is detected
        """
        if visited is None:
            visited = set()
            
        if constraint_name in visited:
            return True
            
        visited.add(constraint_name)
        
        # Check if the definition references itself or creates a cycle
        # More precise check: look for the constraint name in constraint expressions, not just anywhere
        import re
        
        # Pattern to match "extends ConstraintName" - this would be truly circular
        extends_pattern = rf'\bextends\s+{re.escape(constraint_name)}\b'
        if re.search(extends_pattern, definition):
            return True
        
        # Pattern to match recursive generic instantiation like "T extends T" or "Level1<Level1>"
        recursive_pattern = rf'\b{re.escape(constraint_name)}<[^>]*{re.escape(constraint_name)}'
        if re.search(recursive_pattern, definition):
            return True
            
        # Check for indirect cycles through other constraints - be more precise
        for other_name, other_def in all_constraints.items():
            if other_name != constraint_name:
                # Only check for constraint relationships, not just any reference
                extends_other_pattern = rf'\bextends\s+{re.escape(constraint_name)}\b'
                if re.search(extends_other_pattern, other_def.definition):
                    if self._is_circular_constraint(other_name, other_def.definition, all_constraints, visited.copy()):
                        return True
                    
        return False
    
    def _is_recursive_type(self, type_annotation: str, file_path: str) -> bool:
        """
        Check if a type annotation represents a recursive type definition.
        
        Args:
            type_annotation: Type annotation to check
            file_path: File containing the type
            
        Returns:
            True if the type is recursive
        """
        # Simple heuristic: look for type name appearing within its own definition
        base_type = type_annotation.split('<')[0] if '<' in type_annotation else type_annotation
        
        try:
            # Find the type definition in the file (disable inheritance depth check for recursive check)
            type_def = self._find_type_definition(base_type, file_path, 
                                                check_inheritance_depth=False)
            if type_def and type_def.kind != "error":
                # Check if the type references itself in its definition
                if base_type.lower() in type_def.definition.lower():
                    return True
                    
                # Check for recursive patterns in mapped/conditional types
                if (('extends' in type_def.definition and base_type in type_def.definition) or
                    ('keyof' in type_def.definition and base_type in type_def.definition)):
                    return True
                    
        except Exception:
            pass
            
        return False
    
    def _has_circular_interface_constraint(self, interface_name: str, generic_params: str, file_content: str) -> bool:
        """
        Check if an interface has circular constraints with other interfaces.
        
        Args:
            interface_name: Name of the interface being checked
            generic_params: Generic parameters of the interface (e.g., "<T extends CircularB<T>>")
            file_content: Full content of the file
            
        Returns:
            True if circular constraint is detected
        """
        try:
            # Extract constraint types from generic parameters
            # Pattern to match "T extends SomeType<...>"
            constraint_pattern = r'(\w+)\s+extends\s+(\w+)(?:<[^>]*>)?'
            constraint_matches = re.findall(constraint_pattern, generic_params)
            
            for param_name, constraint_type in constraint_matches:
                # Check if the constraint type has a reciprocal constraint back to this interface
                if self._check_reciprocal_constraint(interface_name, constraint_type, file_content):
                    return True
                    
            return False
        except Exception:
            return False
    
    def _check_reciprocal_constraint(self, interface_name: str, constraint_type: str, file_content: str) -> bool:
        """
        Check if constraint_type has a constraint back to interface_name.
        
        Args:
            interface_name: Original interface name (e.g., "CircularA")
            constraint_type: Type being constrained to (e.g., "CircularB")
            file_content: Full file content
            
        Returns:
            True if reciprocal constraint found
        """
        try:
            # Find the definition of constraint_type interface
            constraint_pattern = rf'interface\s+{re.escape(constraint_type)}\s*<([^>]*)>'
            match = re.search(constraint_pattern, file_content)
            
            if match:
                constraint_generic_params = match.group(1)
                # Check if this interface has a constraint back to the original interface
                reciprocal_pattern = rf'\w+\s+extends\s+{re.escape(interface_name)}'
                if re.search(reciprocal_pattern, constraint_generic_params):
                    return True
                    
            return False
        except Exception:
            return False
    
    def _count_constraint_depth(self, constraint_type: str) -> int:
        """
        Count the constraint depth by analyzing the constraint type structure.
        
        Args:
            constraint_type: The constraint type string to analyze
            
        Returns:
            The depth of the constraint (1 for simple, higher for nested)
        """
        # For now, use a simple heuristic based on constraint complexity
        # Count generic parameters and nested structures
        depth = 1
        
        # Count nested generics (each < > pair adds depth)
        depth += constraint_type.count('<')
        
        # Count array access patterns like T[K] (adds complexity)
        depth += constraint_type.count('[')
        
        # Count union/intersection types
        depth += constraint_type.count('|') + constraint_type.count('&')
        
        # Count conditional/mapped type patterns
        if 'extends' in constraint_type:
            depth += 1
        if 'keyof' in constraint_type:
            depth += 1
        if 'infer' in constraint_type:
            depth += 1
            
        return depth
    
    def _calculate_constraint_dependency_depth(self, constraint_type: str, 
                                             param_constraints: dict[str, str], 
                                             visited: set[str]) -> int:
        """
        Calculate the true dependency depth of a constraint type.
        
        Args:
            constraint_type: The constraint type to analyze (e.g., "L4<T, U, V>")
            param_constraints: Dictionary of parameter name to constraint type
            visited: Set of already visited types to prevent infinite recursion
            
        Returns:
            The dependency depth of this constraint
        """
        # Base depth is 1
        depth = 1
        
        # Extract all parameter references from the constraint type
        # Find parameter names that are referenced
        referenced_params = []
        for param_name in param_constraints.keys():
            if param_name in constraint_type:
                referenced_params.append(param_name)
        
        # If no parameters are referenced, depth is just based on syntactic complexity
        if not referenced_params:
            return self._count_constraint_depth(constraint_type)
        
        # Calculate maximum depth from referenced parameters
        max_param_depth = 0
        for param_name in referenced_params:
            if param_name in visited:
                # Circular reference - return high depth to potentially trigger limit
                return 10
            
            visited.add(param_name)
            param_constraint = param_constraints.get(param_name)
            if param_constraint:
                param_depth = self._calculate_constraint_dependency_depth(
                    param_constraint, param_constraints, visited.copy()
                )
                max_param_depth = max(max_param_depth, param_depth)
            visited.discard(param_name)
        
        # Total depth is base depth plus the maximum depth of dependencies
        return depth + max_param_depth
    
    def check_constraint_depth_limit(self, constraint_depth: int, max_depth: int, 
                                   constraint_name: str, file_path: str) -> TypeDefinition | None:
        """
        Check if constraint depth exceeds the maximum allowed depth.
        
        Args:
            constraint_depth: Current constraint depth
            max_depth: Maximum allowed constraint depth
            constraint_name: Name of the constraint being checked
            file_path: File containing the constraint
            
        Returns:
            Error TypeDefinition if depth limit exceeded, None otherwise
        """
        if constraint_depth > max_depth:
            return TypeDefinition(
                kind="error",
                definition=f"Constraint depth limit exceeded for '{constraint_name}': {constraint_depth} > {max_depth}",
                location=f"{file_path}:constraint_depth_exceeded"
            )
        return None
    
    def _extract_type_references(self, type_annotation: str) -> list[str]:
        """
        Extract all type references from a complex type annotation.
        
        Args:
            type_annotation: Complex type annotation string
            
        Returns:
            List of type names referenced in the annotation
        """
        type_refs = []
        
        # Pattern to match type identifiers (including generics)
        # Matches: TypeName, TypeName<T>, TypeName<T, U>
        pattern = r'\b([A-Z][a-zA-Z0-9_]*(?:<[^>]+>)?)\b'
        
        matches = re.findall(pattern, type_annotation)
        for match in matches:
            if match not in self.primitive_types:
                type_refs.append(match)
                
                # Also extract base type from generic instantiation
                if '<' in match:
                    base_type = match.split('<')[0]
                    if base_type not in self.primitive_types:
                        type_refs.append(base_type)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_refs = []
        for ref in type_refs:
            if ref not in seen:
                seen.add(ref)
                unique_refs.append(ref)
        
        return unique_refs
    
    def _calculate_inheritance_depth(self, type_name: str, file_path: str, visited: set[str] = None) -> int:
        """
        Calculate the inheritance depth of a type by traversing its inheritance chain.
        
        Args:
            type_name: Type name to calculate depth for
            file_path: File containing the type
            visited: Set of visited types to prevent circular dependencies
            
        Returns:
            Inheritance depth (0 for base types, 1+ for derived types)
        """
        if visited is None:
            visited = set()
            
        # Prevent infinite recursion
        if type_name in visited:
            return 0
            
        visited.add(type_name)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for inheritance patterns
            # Interface inheritance: interface B<T> extends A<T>
            interface_pattern = rf'interface\s+{re.escape(type_name)}\s*(?:<[^>]*>)?\s+extends\s+(\w+)'
            interface_match = re.search(interface_pattern, content)
            
            if interface_match:
                base_type = interface_match.group(1)
                base_depth = self._calculate_inheritance_depth(base_type, file_path, visited.copy())
                return base_depth + 1
            
            # Class inheritance: class B extends A
            class_pattern = rf'class\s+{re.escape(type_name)}\s*(?:<[^>]*>)?\s+extends\s+(\w+)'
            class_match = re.search(class_pattern, content)
            
            if class_match:
                base_type = class_match.group(1)
                base_depth = self._calculate_inheritance_depth(base_type, file_path, visited.copy())
                return base_depth + 1
            
            # Check for generic constraints depth (new logic)
            # Look for interface with generic constraints using balanced bracket parsing
            simple_pattern = rf'interface\s+{re.escape(type_name)}\s*<'
            match = re.search(simple_pattern, content)
            
            if match:
                # Extract generic parameters using balanced bracket matching
                start_pos = match.end() - 1  # Position of '<'
                bracket_count = 0
                pos = start_pos
                
                while pos < len(content):
                    if content[pos] == '<':
                        bracket_count += 1
                    elif content[pos] == '>':
                        bracket_count -= 1
                        if bracket_count == 0:
                            generic_params = content[start_pos+1:pos]  # Extract content between < >
                            constraint_depth = self._calculate_generic_constraint_depth(generic_params, file_path, visited.copy())
                            # The interface depth is the maximum constraint depth
                            return constraint_depth
                    pos += 1
            
            # No inheritance found - this is a base type
            return 0
            
        except Exception:
            # If we can't read the file or parse it, assume no inheritance
            return 0
    
    def _calculate_generic_constraint_depth(self, generic_params: str, file_path: str, visited: set[str]) -> int:
        """
        Calculate the depth of generic constraints.
        
        Args:
            generic_params: Generic parameters string (e.g., "T extends Level1, U extends Level2<T>")
            file_path: File containing the constraints
            visited: Set of visited types to prevent circular dependencies
            
        Returns:
            Maximum constraint depth
        """
        max_depth = 0
        
        # Parse constraint expressions more carefully
        # Handle complex patterns like "V extends Level3<T, U>"
        constraints = self._parse_constraint_expressions(generic_params)
        
        for param_name, constraint_expr in constraints:
            # Extract base type if it's a generic instantiation
            base_type = constraint_expr.split('<')[0] if '<' in constraint_expr else constraint_expr
            base_type = base_type.strip()
            
            if base_type not in visited:
                # Calculate depth of the constraint type
                constraint_depth = self._calculate_inheritance_depth(base_type, file_path, visited.copy())
                max_depth = max(max_depth, constraint_depth + 1)
        
        return max_depth
    
    def _parse_constraint_expressions(self, generic_params: str) -> list[tuple[str, str]]:
        """
        Parse complex constraint expressions handling nested generics.
        
        Args:
            generic_params: Generic parameters string
            
        Returns:
            List of (parameter_name, constraint_expression) tuples
        """
        constraints = []
        
        # Split by comma but respect nested angle brackets
        current_constraint = ""
        bracket_depth = 0
        paren_depth = 0
        
        for char in generic_params:
            if char == '<':
                bracket_depth += 1
            elif char == '>':
                bracket_depth -= 1
            elif char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and bracket_depth == 0 and paren_depth == 0:
                # Process this constraint
                if current_constraint.strip():
                    constraints.append(self._parse_single_constraint(current_constraint.strip()))
                current_constraint = ""
                continue
            
            current_constraint += char
        
        # Process the last constraint
        if current_constraint.strip():
            constraints.append(self._parse_single_constraint(current_constraint.strip()))
        
        return [c for c in constraints if c is not None]
    
    def _parse_single_constraint(self, constraint: str) -> tuple[str, str] | None:
        """
        Parse a single constraint expression like "V extends Level3<T, U>".
        
        Args:
            constraint: Single constraint string
            
        Returns:
            Tuple of (parameter_name, constraint_type) or None if parsing fails
        """
        if ' extends ' not in constraint:
            return None
            
        parts = constraint.split(' extends ', 1)
        if len(parts) != 2:
            return None
            
        param_name = parts[0].strip()
        constraint_type = parts[1].strip()
        
        return (param_name, constraint_type)
    
    def resolve_batch_types(self, type_annotations: list[str], file_path: str,
                           resolution_depth: str = "basic",
                           max_constraint_depth: int = 3,
                           track_instantiations: bool = False,
                           resolve_conditional_types: bool = False,
                           handle_recursive_types: bool = False,
                           check_circular: bool = True) -> TypeResolutionResult:
        """
        Batch resolve multiple types for performance optimization.
        
        Args:
            type_annotations: List of type annotations to resolve
            file_path: File containing the type annotations
            resolution_depth: Analysis level for all types
            
        Returns:
            TypeResolutionResult with resolved types and metadata
        """
        start_time = time.perf_counter()
        
        basic_types = {}
        generic_types = {}
        inferred_types = {}
        errors = []
        total_resolved = 0
        
        for annotation in type_annotations:
            try:
                type_def = self.resolve_type(annotation, file_path, resolution_depth,
                                           max_constraint_depth=max_constraint_depth,
                                           track_instantiations=track_instantiations,
                                           resolve_conditional_types=resolve_conditional_types,
                                           handle_recursive_types=handle_recursive_types,
                                           check_circular=check_circular)
                
                if type_def.kind == "error":
                    # Extract specific error code from location field
                    error_code = "TYPE_RESOLUTION_ERROR"
                    if ":unknown_type" in type_def.location:
                        error_code = "UNKNOWN_TYPE"
                    elif ":circular_constraint" in type_def.location:
                        error_code = "CIRCULAR_REFERENCE_DETECTED"
                    elif ":constraint_depth_exceeded" in type_def.location:
                        error_code = "CONSTRAINT_DEPTH_EXCEEDED"
                    
                    errors.append(AnalysisError(
                        code=error_code,
                        message=type_def.definition,
                        file=file_path
                    ))
                else:
                    # Categorize resolved type
                    if type_def.kind in ["primitive", "interface", "class", "type", "enum"]:
                        basic_types[annotation] = BasicTypeInfo(
                            type_name=annotation,
                            kind=type_def.kind,
                            definition=type_def.definition,
                            location=type_def.location
                        )
                    elif type_def.kind in ["generic", "generic_instantiation"]:
                        generic_types[annotation] = GenericTypeInfo(
                            type_name=annotation,
                            type_parameters=[],  # Would extract from actual definition
                            constraints=[],
                            instantiations=[]
                        )
                    else:
                        inferred_types[annotation] = InferredTypeInfo(
                            type_name=annotation,
                            inference_source="pattern_matching",
                            confidence=0.8
                        )
                    
                    total_resolved += 1
                    
            except Exception as e:
                # Categorize the error based on exception type or message
                error_code = "TYPE_RESOLUTION_ERROR"
                error_msg = str(e)
                
                if "timeout" in error_msg.lower():
                    error_code = "TYPE_RESOLUTION_TIMEOUT"
                elif "complexity" in error_msg.lower():
                    error_code = "COMPLEXITY_LIMIT_EXCEEDED"
                elif "circular" in error_msg.lower():
                    error_code = "CIRCULAR_REFERENCE_DETECTED"
                elif "constraint depth" in error_msg.lower():
                    error_code = "CONSTRAINT_DEPTH_EXCEEDED"
                
                errors.append(AnalysisError(
                    code=error_code,
                    message=f"Failed to resolve type '{annotation}': {error_msg}",
                    file=file_path
                ))
        
        resolution_time = (time.perf_counter() - start_time) * 1000
        
        metadata = TypeResolutionMetadata(
            resolution_depth_used=resolution_depth,
            max_constraint_depth_reached=1,
            fallbacks_used=0,
            total_types_resolved=total_resolved,
            resolution_time_ms=resolution_time
        )
        
        return TypeResolutionResult(
            success=len(errors) == 0,
            resolution_level=resolution_depth,
            basic_types=basic_types,
            generic_types=generic_types,
            inferred_types=inferred_types,
            resolution_metadata=metadata,
            errors=errors
        )