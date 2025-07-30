"""
Cycle Detector for TypeScript call graph analysis.

This module provides cycle detection and handling for call graphs,
with NetworkX integration and manual fallback implementations.
"""

from typing import List, Set, Dict, Optional, Any


class CycleDetector:
    """Detects and handles cycles in function call graphs."""
    
    def __init__(self, call_graph_builder):
        """Initialize cycle detector with call graph data.
        
        Args:
            call_graph_builder: CallGraphBuilder instance with built graph
        """
        self.call_graph_builder = call_graph_builder
        self.detected_cycles = []
        self.broken_edges = []
        
    def detect_and_break_cycles(self) -> List[List[str]]:
        """Detect cycles and break them with placeholder references.
        
        Returns:
            List of detected cycles (each cycle is a list of function names)
        """
        try:
            if self.call_graph_builder.use_networkx and self.call_graph_builder.call_graph_nx:
                return self._detect_cycles_networkx()
            else:
                return self._detect_cycles_manual()
                
        except Exception as e:
            # Fallback to manual detection if NetworkX fails
            return self._detect_cycles_manual()
            
    def _detect_cycles_networkx(self) -> List[List[str]]:
        """Detect cycles using NetworkX."""
        cycles = []
        
        try:
            # Find all strongly connected components (cycles)
            nx_cycles = list(self.call_graph_builder.nx.simple_cycles(
                self.call_graph_builder.call_graph_nx
            ))
            
            for cycle in nx_cycles:
                if len(cycle) > 1:  # Only consider actual cycles, not self-loops
                    cycles.append(cycle)
                    self._break_cycle_networkx(cycle)
                elif len(cycle) == 1:
                    # Self-loop (direct recursion)
                    func_name = cycle[0]
                    if self.call_graph_builder.call_graph_nx.has_edge(func_name, func_name):
                        cycles.append(cycle)
                        self._break_self_loop_networkx(func_name)
                        
            self.detected_cycles = cycles
            return cycles
            
        except Exception as e:
            # Fallback to manual detection
            return self._detect_cycles_manual()
            
    def _break_cycle_networkx(self, cycle: List[str]):
        """Break a cycle in the NetworkX graph."""
        if len(cycle) < 2:
            return
            
        # Remove edge from last to first node in cycle
        if self.call_graph_builder.call_graph_nx.has_edge(cycle[-1], cycle[0]):
            self.call_graph_builder.call_graph_nx.remove_edge(cycle[-1], cycle[0])
            self.broken_edges.append((cycle[-1], cycle[0]))
            
            # Add placeholder reference
            placeholder_name = f"[CYCLE: {cycle[0]}]"
            cycle_info = {
                'type': 'cycle_placeholder',
                'original_target': cycle[0],
                'cycle_path': cycle
            }
            
            # Add placeholder node with metadata
            self.call_graph_builder.call_graph_nx.add_node(placeholder_name, **cycle_info)
            self.call_graph_builder.call_graph_nx.add_edge(cycle[-1], placeholder_name)
            
    def _break_self_loop_networkx(self, func_name: str):
        """Break a self-loop (direct recursion)."""
        if self.call_graph_builder.call_graph_nx.has_edge(func_name, func_name):
            self.call_graph_builder.call_graph_nx.remove_edge(func_name, func_name)
            self.broken_edges.append((func_name, func_name))
            
            # Add placeholder for recursion
            placeholder_name = f"[RECURSION: {func_name}]"
            recursion_info = {
                'type': 'recursion_placeholder',
                'original_target': func_name
            }
            
            self.call_graph_builder.call_graph_nx.add_node(placeholder_name, **recursion_info)
            self.call_graph_builder.call_graph_nx.add_edge(func_name, placeholder_name)
            
    def _detect_cycles_manual(self) -> List[List[str]]:
        """Manual cycle detection using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []
        call_graph = self.call_graph_builder.call_graph
        
        for node in call_graph:
            if node not in visited:
                self._dfs_cycle_detection(node, visited, rec_stack, [], cycles, call_graph)
                
        # Break detected cycles
        for cycle in cycles:
            self._break_cycle_manual(cycle)
            
        self.detected_cycles = cycles
        return cycles
        
    def _dfs_cycle_detection(self, node: str, visited: Set[str], rec_stack: Set[str], 
                           path: List[str], cycles: List[List[str]], call_graph: Dict[str, List[str]]):
        """DFS-based cycle detection."""
        visited.add(node)
        rec_stack.add(node)
        path.append(node)
        
        if node in call_graph:
            for neighbor in call_graph[node]:
                if neighbor not in visited:
                    self._dfs_cycle_detection(neighbor, visited, rec_stack, path, cycles, call_graph)
                elif neighbor in rec_stack:
                    # Found cycle - extract the cycle path
                    try:
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        
                        # Only add unique cycles
                        if not self._is_duplicate_cycle(cycle, cycles):
                            cycles.append(cycle)
                    except ValueError:
                        # neighbor not in path (shouldn't happen, but be safe)
                        pass
                        
        rec_stack.remove(node)
        path.pop()
        
    def _is_duplicate_cycle(self, new_cycle: List[str], existing_cycles: List[List[str]]) -> bool:
        """Check if a cycle is already detected (considering rotations)."""
        for existing_cycle in existing_cycles:
            if len(new_cycle) == len(existing_cycle):
                # Check all rotations of the cycle
                for i in range(len(existing_cycle)):
                    rotated = existing_cycle[i:] + existing_cycle[:i]
                    if new_cycle == rotated:
                        return True
        return False
        
    def _break_cycle_manual(self, cycle: List[str]):
        """Break a cycle in the manual adjacency list."""
        if len(cycle) < 2:
            return
            
        call_graph = self.call_graph_builder.call_graph
        
        # Find the edge to break (last -> first in cycle)
        if len(cycle) >= 2:
            source = cycle[-2] if len(cycle) > 2 else cycle[-1]
            target = cycle[0] if len(cycle) > 1 else cycle[-1]
            
            # Remove the edge if it exists
            if source in call_graph and target in call_graph[source]:
                call_graph[source].remove(target)
                self.broken_edges.append((source, target))
                
                # Add placeholder reference
                placeholder_name = f"[CYCLE: {target}]"
                call_graph[source].append(placeholder_name)
                
                # Create entry for placeholder if needed
                if placeholder_name not in call_graph:
                    call_graph[placeholder_name] = []
                    
    def get_cycle_statistics(self) -> Dict[str, Any]:
        """Get statistics about detected cycles."""
        total_cycles = len(self.detected_cycles)
        cycle_lengths = [len(cycle) for cycle in self.detected_cycles]
        
        stats = {
            'total_cycles': total_cycles,
            'cycles_broken': len(self.broken_edges),
            'average_cycle_length': sum(cycle_lengths) / len(cycle_lengths) if cycle_lengths else 0,
            'max_cycle_length': max(cycle_lengths) if cycle_lengths else 0,
            'min_cycle_length': min(cycle_lengths) if cycle_lengths else 0,
            'self_loops': len([c for c in self.detected_cycles if len(c) == 1]),
            'multi_node_cycles': len([c for c in self.detected_cycles if len(c) > 1])
        }
        
        return stats
        
    def get_broken_edges(self) -> List[tuple]:
        """Get list of edges that were broken to eliminate cycles."""
        return self.broken_edges.copy()
        
    def restore_cycles(self):
        """Restore broken cycles (for testing or analysis purposes)."""
        if self.call_graph_builder.use_networkx and self.call_graph_builder.call_graph_nx:
            # Restore NetworkX edges
            for source, target in self.broken_edges:
                if not self.call_graph_builder.call_graph_nx.has_edge(source, target):
                    self.call_graph_builder.call_graph_nx.add_edge(source, target)
        
        # Restore manual graph edges
        call_graph = self.call_graph_builder.call_graph
        for source, target in self.broken_edges:
            if source in call_graph and target not in call_graph[source]:
                call_graph[source].append(target)
                
        # Clear broken edges list
        self.broken_edges.clear()
        
    def has_cycles(self) -> bool:
        """Check if any cycles were detected."""
        return len(self.detected_cycles) > 0
        
    def get_functions_in_cycles(self) -> Set[str]:
        """Get set of all function names that participate in cycles."""
        functions_in_cycles = set()
        for cycle in self.detected_cycles:
            functions_in_cycles.update(cycle)
        return functions_in_cycles