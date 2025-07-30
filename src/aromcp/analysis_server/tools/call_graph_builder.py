"""
Call Graph Builder for TypeScript function call analysis.

This module provides scalable call graph construction from TypeScript code,
supporting various function call patterns and providing fallback implementations
when NetworkX is not available.
"""

import re
import time
from typing import Dict, List, Set, Tuple, Optional, Any

from ..models.typescript_models import (
    CallGraphResult,
    CallGraphStats,
    ExecutionPath,
    FunctionDefinition,
    CallSite,
    AnalysisError,
)


class CallGraphBuilder:
    """Builds call graphs from TypeScript code using regex-based parsing."""
    
    def __init__(self, parser=None, function_analyzer=None):
        """Initialize the call graph builder.
        
        Args:
            parser: TypeScript parser (can be None for regex-only mode)
            function_analyzer: Function analyzer (can be None for regex-only mode)
        """
        self.parser = parser
        self.function_analyzer = function_analyzer
        self.call_graph = {}  # adjacency list representation
        self.function_definitions = {}  # func_name -> FunctionDefinition
        self.call_sites = {}  # (file, line) -> CallSite
        self.use_networkx = False
        
        # Try to import NetworkX for advanced graph operations
        try:
            import networkx as nx
            self.nx = nx
            self.call_graph_nx = nx.DiGraph()
            self.use_networkx = True
        except ImportError:
            self.nx = None
            self.call_graph_nx = None
        
    def build_call_graph(self, entry_point: str, file_paths: list[str], 
                        max_depth: int = 10) -> CallGraphResult:
        """Build complete call graph from entry point.
        
        Args:
            entry_point: Starting function name
            file_paths: List of TypeScript files to analyze
            max_depth: Maximum recursion depth
            
        Returns:
            CallGraphResult with execution paths and statistics
        """
        start_time = time.time()
        stats = CallGraphStats(
            total_functions=0,
            total_edges=0,
            max_depth_reached=0,
            cycles_detected=0
        )
        
        try:
            # Phase 1: Extract all function definitions
            self._extract_function_definitions(file_paths)
            
            # Phase 2: Extract all call sites
            self._extract_call_sites(file_paths)
            
            # Phase 3: Build graph starting from entry point
            visited = set()
            self._build_graph_recursive(entry_point, visited, 0, max_depth)
            
            # Phase 4: Generate execution paths
            execution_paths = self._generate_execution_paths(entry_point, max_depth)
            
            # Calculate statistics
            stats.total_functions = len(self.function_definitions)
            if self.use_networkx and self.call_graph_nx:
                stats.total_edges = self.call_graph_nx.number_of_edges()
                stats.cycles_detected = len(list(self.nx.simple_cycles(self.call_graph_nx)))
            else:
                stats.total_edges = sum(len(calls) for calls in self.call_graph.values())
                stats.cycles_detected = self._detect_cycles_manual()
                
            stats.max_depth_reached = self._calculate_max_depth(entry_point)
            
            processing_time = (time.time() - start_time) * 1000
            
            return CallGraphResult(
                entry_point=entry_point,
                execution_paths=execution_paths,
                call_graph_stats=stats,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return CallGraphResult(
                entry_point=entry_point,
                execution_paths=[],
                call_graph_stats=stats,
                processing_time_ms=processing_time
            )
            
    def _extract_function_definitions(self, file_paths: list[str]):
        """Extract all function definitions using regex patterns."""
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Multiple patterns for different function types
                # Handle generic types like <T> in function signatures
                patterns = [
                    # function declaration: function myFunc(...) or function myFunc<T>(...)
                    r'function\s+(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)',
                    # arrow function: const myFunc = (...) =>
                    r'(?:const|let|var)\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*',
                    # method definition: myFunc(...) { ... } or myFunc<T>(...) { ... }
                    r'(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*\{',
                    # class methods: public myMethod(...) or public async myMethod<T>(...)
                    r'(?:public|private|protected)\s+(?:async\s+)?(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*\{',
                    r'(?:public|private|protected)\s+(?:async\s+)?(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*:\s*[^{]*\{',
                    # static methods: public static myMethod(...) or private static myMethod<T>(...)
                    r'(?:public|private|protected)\s+static\s+(?:async\s+)?(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*\{',
                    r'(?:public|private|protected)\s+static\s+(?:async\s+)?(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*:\s*[^{]*\{',
                    # async methods: async myMethod(...) or async myMethod<T>(...)
                    r'async\s+(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*\{',
                    r'async\s+(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*:\s*[^{]*\{',
                    # export function or export function with generics
                    r'export\s+function\s+(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)',
                    # export async function or export async function with generics
                    r'export\s+async\s+function\s+(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)'
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        func_name = match.group(1)
                        line_num = content[:match.start()].count('\n') + 1
                        
                        # Skip common keywords that might match
                        if func_name in ['if', 'for', 'while', 'catch', 'return', 'new']:
                            continue
                            
                        self.function_definitions[func_name] = FunctionDefinition(
                            name=func_name,
                            file=file_path,
                            line=line_num,
                            signature=match.group(0)
                        )
                        
            except Exception as e:
                continue  # Skip files that can't be read
                
    def _extract_call_sites(self, file_paths: list[str]):
        """Extract all function call sites."""
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Patterns for function calls: various call patterns
                call_patterns = [
                    r'(\w+)\s*\(',  # Direct function calls
                    r'this\.(\w+)\s*\(',  # Method calls via this
                    r'\w+\.\w+\.(\w+)\s*\(',  # Object method calls like database.users.find
                    r'\w+\.(\w+)\s*\(',  # Simple object method calls like obj.method
                    r'new\s+(\w+)\s*\('  # Constructor calls like new ClassName
                ]
                
                for call_pattern in call_patterns:
                    matches = re.finditer(call_pattern, content, re.MULTILINE)
                
                    for match in matches:
                        func_name = match.group(1)
                        line_num = content[:match.start()].count('\n') + 1
                        
                        # Skip common keywords and operators
                        if func_name in ['if', 'for', 'while', 'catch', 'return', 'new', 'typeof', 'instanceof', 'undefined', 'null']:
                            continue
                        
                        # Get surrounding context
                        lines = content.split('\n')
                        context = lines[line_num - 1] if line_num <= len(lines) else ""
                        
                        # Skip if this looks like a function definition rather than a call
                        if 'function' in context or '=>' in context:
                            continue
                        
                        call_site = CallSite(
                            function_name=func_name,
                            file=file_path,
                            line=line_num,
                            context=context.strip()
                        )
                        
                        self.call_sites[(file_path, line_num)] = call_site
                    
            except Exception as e:
                continue
                
    def _build_graph_recursive(self, func_name: str, visited: set, 
                             current_depth: int, max_depth: int):
        """Recursively build call graph with depth limiting."""
        # Enforce depth limit strictly - stop if we've reached max_depth
        if current_depth >= max_depth:
            return
            
        # For cycle detection, track if function is in current path
        if func_name in visited:
            # Still add the edge to show the cycle
            return
            
        visited.add(func_name)
        
        # Find calls made by this function
        calls = self._find_calls_in_function(func_name)
        
        # Add to adjacency list
        if func_name not in self.call_graph:
            self.call_graph[func_name] = []
        
        # Limit number of calls per function to prevent excessive processing
        # But increase limit to capture more of the graph
        calls = calls[:50]  # Increased from 20 to 50 for deeper graphs
        
        for called_func in calls:
            # Add edge even if we've seen this function before (to capture all paths)
            if called_func not in self.call_graph[func_name]:
                self.call_graph[func_name].append(called_func)
            
            # Add to NetworkX graph if available
            if self.use_networkx and self.call_graph_nx is not None:
                self.call_graph_nx.add_edge(func_name, called_func)
            
            # For self-recursion, record the edge but don't recurse
            if called_func == func_name:
                continue
                
            # Recurse if we haven't hit depth limit
            # Note: current_depth tracks the depth in the tree, not edges
            if current_depth < max_depth:
                # Use a new visited set for each branch to allow multiple paths
                new_visited = visited.copy()
                self._build_graph_recursive(called_func, new_visited, 
                                          current_depth + 1, max_depth)
                
    def _find_calls_in_function(self, func_name: str) -> List[str]:
        """Find all function calls within a specific function."""
        calls = []
        
        # Find the function definition
        if func_name not in self.function_definitions:
            return calls
            
        func_def = self.function_definitions[func_name]
        
        try:
            with open(func_def.file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract the function body (simplified approach)
            function_body = self._extract_function_body(func_name, content)
            if not function_body:
                return calls  # Don't fallback to entire file - too risky
                
            # Find function calls within the body using regex
            # Support various call patterns
            # Use separate patterns to avoid overlapping matches
            direct_call_pattern = r'(?<!\.)\b(\w+)\s*\('  # Direct function calls (not preceded by .)
            this_call_pattern = r'this\.(\w+)\s*\('  # Method calls via this
            object_call_pattern = r'(?<!this)\.\s*(\w+)\s*\('  # Object method calls
            constructor_pattern = r'new\s+(\w+)\s*\('  # Constructor calls
            
            matches = []
            # Process this. calls first (highest priority)
            matches.extend(re.finditer(this_call_pattern, function_body))
            # Then other patterns
            matches.extend(re.finditer(direct_call_pattern, function_body))
            matches.extend(re.finditer(object_call_pattern, function_body))
            matches.extend(re.finditer(constructor_pattern, function_body))
            
            seen_calls = set()  # Prevent duplicates
            for match in matches:
                called_func = match.group(1)
                
                # Skip common keywords
                if called_func in ['if', 'for', 'while', 'catch', 'return', 'new', 'typeof', 'instanceof', 'console', 'function', 'undefined', 'null']:
                    continue
                    
                # Include all function calls to see execution paths, not just defined ones
                if called_func not in seen_calls:
                    calls.append(called_func)
                    seen_calls.add(called_func)
                            
        except Exception as e:
            pass
            
        return calls
        
    def _extract_function_body(self, func_name: str, content: str) -> str:
        """Extract the body of a function (simplified approach)."""
        # Multiple patterns to match different function declarations
        # Use more flexible patterns that handle complex parameter types, nested generics, and TypeScript return types
        patterns = [
            # export function funcName<T>(...) { ... } - handle generics and complex types like (data: CallbackData, callback: (result: any) => void)
            rf'export\s+function\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'export\s+function\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
            # export async function funcName<T>(...) { ... }
            rf'export\s+async\s+function\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'export\s+async\s+function\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
            # function funcName<T>(...) { ... }
            rf'function\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'function\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
            # static methods: public static funcName<T>(...) { ... }
            rf'(?:public|private|protected)\s+static\s+(?:async\s+)?{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'(?:public|private|protected)\s+static\s+(?:async\s+)?{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
            # class methods: public async funcName<T>(...) { ... }
            rf'(?:public|private|protected)\s+(?:async\s+)?{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'(?:public|private|protected)\s+(?:async\s+)?{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
            # async methods: async funcName<T>(...) { ... }
            rf'async\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'async\s+{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
            # method in class or object: funcName<T>(...) { ... }
            rf'{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*:\s*.*?\s*\{{',
            rf'{re.escape(func_name)}\s*(?:<.*?>)?\s*\(.*?\)\s*\{{',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                start_pos = match.end() - 1  # Position of opening brace
                
                # Find matching closing brace with proper handling
                brace_count = 1
                pos = start_pos + 1
                max_search = min(len(content), start_pos + 5000)  # Limit search to prevent runaway
                
                while pos < max_search and brace_count > 0:
                    char = content[pos]
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                    pos += 1
                
                if brace_count == 0:
                    body = content[start_pos + 1:pos - 1]  # Exclude braces
                    return body
                    
        return ""
        
    def _is_call_in_function_body(self, call_line: int, func_start_line: int, function_body: str) -> bool:
        """Check if a call line is within the function body."""
        if not function_body:
            return False
            
        # Estimate function end line based on body content
        body_lines = function_body.count('\n')
        func_end_line = func_start_line + body_lines
        
        return func_start_line <= call_line <= func_end_line
        
    def _generate_execution_paths(self, entry_point: str, max_depth: int) -> List[ExecutionPath]:
        """Generate execution paths from the call graph."""
        paths = []
        
        def dfs_paths(current_func: str, current_path: List[str], depth: int):
            # Stop if we've exceeded max depth
            if depth > max_depth:
                # Still add the path we've found so far
                if len(current_path) > 1:
                    paths.append(ExecutionPath(
                        path=current_path.copy(),
                        condition=None,
                        execution_probability=1.0
                    ))
                return
                
            current_path = current_path + [current_func]
            
            # Continue to called functions
            if current_func in self.call_graph:
                called_functions = self.call_graph[current_func]
                if called_functions:  # If this function calls others
                    for called_func in called_functions:
                        # Check for cycles - if we encounter a function already in path, we've found a cycle
                        if called_func in current_path:
                            # Complete the cycle by adding the function one more time
                            cycle_path = current_path + [called_func]
                            paths.append(ExecutionPath(
                                path=cycle_path,
                                condition=None,
                                execution_probability=1.0
                            ))
                        else:
                            # Continue exploring
                            dfs_paths(called_func, current_path, depth + 1)
                else:
                    # Leaf node - add the path
                    if len(current_path) > 1:
                        paths.append(ExecutionPath(
                            path=current_path.copy(),
                            condition=None,
                            execution_probability=1.0
                        ))
            else:
                # No more calls from this function - add the path
                if len(current_path) > 1:
                    paths.append(ExecutionPath(
                        path=current_path.copy(),
                        condition=None,
                        execution_probability=1.0
                    ))
        
        # Start DFS from entry point
        if entry_point in self.function_definitions:
            dfs_paths(entry_point, [], 0)
        
        # If we have no paths but we have calls in the graph, create basic paths
        if not paths and entry_point in self.call_graph and self.call_graph[entry_point]:
            for called_func in self.call_graph[entry_point]:
                paths.append(ExecutionPath(
                    path=[entry_point, called_func],
                    condition=None,
                    execution_probability=1.0
                ))
        
        return paths
        
    def _calculate_max_depth(self, entry_point: str) -> int:
        """Calculate the maximum depth reached in the call graph."""
        if not self.call_graph or entry_point not in self.call_graph:
            return 0
            
        # Track the maximum depth seen across all paths
        max_depth_seen = 0
        
        def dfs_depth(func: str, visited: set, current_depth: int) -> int:
            nonlocal max_depth_seen
            
            # Update max depth seen
            max_depth_seen = max(max_depth_seen, current_depth)
            
            # Handle cycles - don't revisit nodes in current path
            if func in visited:
                return current_depth
                
            visited.add(func)
            
            # Track maximum depth from this node
            local_max_depth = current_depth
            
            if func in self.call_graph:
                for called_func in self.call_graph[func]:
                    # Explore each branch with a copy of visited set
                    child_depth = dfs_depth(called_func, visited.copy(), current_depth + 1)
                    local_max_depth = max(local_max_depth, child_depth)
                    
            return local_max_depth
            
        # Start DFS from entry point at depth 0
        dfs_depth(entry_point, set(), 0)
        return max_depth_seen
        
    def _detect_cycles_manual(self) -> int:
        """Manual cycle detection using DFS when NetworkX is not available."""
        visited = set()
        rec_stack = set()
        cycle_count = 0
        
        def dfs_has_cycle(node: str) -> bool:
            nonlocal cycle_count
            visited.add(node)
            rec_stack.add(node)
            
            if node in self.call_graph:
                for neighbor in self.call_graph[node]:
                    if neighbor not in visited:
                        if dfs_has_cycle(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        cycle_count += 1
                        return True
                        
            rec_stack.remove(node)
            return False
            
        for node in self.call_graph:
            if node not in visited:
                dfs_has_cycle(node)
                
        return cycle_count