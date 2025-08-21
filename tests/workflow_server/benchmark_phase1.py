"""Performance benchmarks for Phase 1 workflow server as specified in implementation plan."""

import asyncio
import logging
import time
from typing import Dict, List

from src.aromcp.workflow_server.server import WorkflowServer
from src.aromcp.workflow_server.config import WorkflowServerConfig
from src.aromcp.workflow_server.temporal_client import get_temporal_manager, reset_temporal_manager
from src.aromcp.workflow_server.pending_actions import get_pending_actions_manager, reset_pending_actions_manager


# Disable logging during benchmarks for accurate timing
logging.getLogger().setLevel(logging.CRITICAL)


class Phase1Benchmarks:
    """Phase 1 performance benchmarks as specified in implementation plan."""
    
    def __init__(self):
        self.results: Dict[str, float] = {}
        
    async def benchmark_startup(self) -> float:
        """Benchmark server startup time. Target: < 2 seconds."""
        print("Benchmarking server startup time...")
        
        # Reset global singletons for clean test
        reset_temporal_manager()
        reset_pending_actions_manager()
        
        start = time.time()
        
        # Create server with mock configuration
        config = WorkflowServerConfig(
            mock_mode=True,
            debug_mode=False,
            log_level="CRITICAL"
        )
        server = WorkflowServer(config)
        
        # Initialize server (connects to Temporal, registers tools)
        await server.initialize()
        
        startup_time = time.time() - start
        self.results["startup_time"] = startup_time
        
        print(f"  Startup time: {startup_time:.3f}s (target: < 2.0s)")
        return startup_time
    
    async def benchmark_temporal_connection(self) -> float:
        """Benchmark Temporal connection time. Target: < 500ms."""
        print("Benchmarking Temporal connection time...")
        
        # Reset manager for clean test
        reset_temporal_manager()
        
        config = WorkflowServerConfig(
            mock_mode=True,
            debug_mode=False,
            log_level="CRITICAL"
        )
        
        start = time.time()
        
        # Get manager and connect
        manager = get_temporal_manager()
        connected = await manager.connect()
        
        connection_time = time.time() - start
        self.results["temporal_connection"] = connection_time
        
        print(f"  Connection time: {connection_time:.3f}s (target: < 0.5s)")
        print(f"  Connected: {connected}")
        return connection_time
    
    async def benchmark_tool_call_latency(self, server: WorkflowServer, iterations: int = 100) -> float:
        """Benchmark tool call latency. Target: < 50ms per call."""
        print(f"Benchmarking tool call latency ({iterations} iterations)...")
        
        # Create a simple test workflow definition
        test_workflow = {
            "name": "benchmark-test",
            "description": "Simple test workflow for benchmarking",
            "steps": [
                {
                    "id": "test_step",
                    "type": "shell",
                    "command": "echo 'test'",
                    "timeout": 30
                }
            ]
        }
        
        # Write test workflow to temporary file
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_workflow, f)
            workflow_path = f.name
        
        try:
            total_time = 0.0
            successful_calls = 0
            
            for i in range(iterations):
                start = time.time()
                
                try:
                    # Simulate tool call through the registered tools
                    from src.aromcp.workflow_server.tools.workflow_start import workflow_start_impl
                    result = await workflow_start_impl(workflow_path, {})
                    
                    call_time = time.time() - start
                    total_time += call_time
                    successful_calls += 1
                    
                    # Clean up workflow to prevent memory buildup
                    if hasattr(result, 'workflow_id') and result.workflow_id:
                        manager = get_temporal_manager()
                        manager.cancel_workflow(result.workflow_id)
                        
                except Exception as e:
                    print(f"    Call {i+1} failed: {e}")
                    continue
            
            avg_latency = (total_time / successful_calls) * 1000 if successful_calls > 0 else float('inf')
            self.results["tool_call_latency"] = avg_latency
            
            print(f"  Average latency: {avg_latency:.1f}ms (target: < 50ms)")
            print(f"  Successful calls: {successful_calls}/{iterations}")
            return avg_latency
            
        finally:
            # Clean up temp file
            os.unlink(workflow_path)
    
    async def benchmark_workflow_start(self, iterations: int = 50) -> float:
        """Benchmark workflow_start tool. Target: < 100ms."""
        print(f"Benchmarking workflow_start tool ({iterations} iterations)...")
        
        # Create test workflow
        test_workflow = {
            "name": "start-benchmark",
            "description": "Workflow start benchmark",
            "steps": [
                {
                    "id": "step1",
                    "type": "prompt",
                    "message": "Test step",
                    "timeout": 30
                }
            ]
        }
        
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_workflow, f)
            workflow_path = f.name
        
        try:
            total_time = 0.0
            successful_starts = 0
            
            for i in range(iterations):
                start = time.time()
                
                try:
                    from src.aromcp.workflow_server.tools.workflow_start import workflow_start_impl
                    result = await workflow_start_impl(workflow_path, {"test": "data"})
                    
                    start_time = time.time() - start
                    total_time += start_time
                    successful_starts += 1
                    
                    # Clean up
                    if hasattr(result, 'workflow_id') and result.workflow_id:
                        manager = get_temporal_manager()
                        manager.cancel_workflow(result.workflow_id)
                        
                except Exception as e:
                    print(f"    Start {i+1} failed: {e}")
                    continue
            
            avg_start_time = (total_time / successful_starts) * 1000 if successful_starts > 0 else float('inf')
            self.results["workflow_start"] = avg_start_time
            
            print(f"  Average start time: {avg_start_time:.1f}ms (target: < 100ms)")
            print(f"  Successful starts: {successful_starts}/{iterations}")
            return avg_start_time
            
        finally:
            os.unlink(workflow_path)
    
    async def benchmark_result_submission(self, iterations: int = 50) -> float:
        """Benchmark submit_result tool. Target: < 50ms."""
        print(f"Benchmarking submit_result tool ({iterations} iterations)...")
        
        # Create workflow with pending action
        test_workflow = {
            "name": "submit-benchmark",
            "description": "Result submission benchmark",
            "steps": [
                {
                    "id": "step1", 
                    "type": "shell",
                    "command": "echo 'test'",
                    "timeout": 30
                },
                {
                    "id": "step2",
                    "type": "prompt", 
                    "message": "Complete",
                    "timeout": 30
                }
            ]
        }
        
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_workflow, f)
            workflow_path = f.name
        
        try:
            total_time = 0.0
            successful_submissions = 0
            
            for i in range(iterations):
                # Start workflow first
                try:
                    from src.aromcp.workflow_server.tools.workflow_start import workflow_start_impl
                    start_result = await workflow_start_impl(workflow_path, {})
                    
                    if not hasattr(start_result, 'workflow_id') or not start_result.workflow_id:
                        continue
                        
                    workflow_id = start_result.workflow_id
                    
                    # Now benchmark result submission
                    start = time.time()
                    
                    from src.aromcp.workflow_server.tools.submit_result import submit_result_impl
                    result = submit_result_impl(workflow_id, {"exit_code": 0, "output": "test"})
                    
                    submit_time = time.time() - start
                    total_time += submit_time
                    successful_submissions += 1
                    
                    # Clean up
                    manager = get_temporal_manager()
                    manager.cancel_workflow(workflow_id)
                    
                except Exception as e:
                    print(f"    Submission {i+1} failed: {e}")
                    continue
            
            avg_submit_time = (total_time / successful_submissions) * 1000 if successful_submissions > 0 else float('inf')
            self.results["result_submission"] = avg_submit_time
            
            print(f"  Average submission time: {avg_submit_time:.1f}ms (target: < 50ms)")
            print(f"  Successful submissions: {successful_submissions}/{iterations}")
            return avg_submit_time
            
        finally:
            os.unlink(workflow_path)
    
    def check_memory_baseline(self) -> float:
        """Check baseline memory usage. Target: < 50MB."""
        print("Checking baseline memory usage...")
        
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            self.results["memory_baseline"] = memory_mb
            print(f"  Memory usage: {memory_mb:.1f}MB (target: < 50MB)")
            return memory_mb
            
        except ImportError:
            print("  psutil not available, skipping memory check")
            return 0.0
    
    def print_summary(self):
        """Print benchmark summary with pass/fail status."""
        print("\n" + "="*60)
        print("PHASE 1 BENCHMARK SUMMARY")
        print("="*60)
        
        targets = {
            "startup_time": 2.0,
            "temporal_connection": 0.5,
            "tool_call_latency": 50.0,
            "workflow_start": 100.0,
            "result_submission": 50.0,
            "memory_baseline": 50.0
        }
        
        passed = 0
        total = 0
        
        for metric, target in targets.items():
            if metric in self.results:
                value = self.results[metric]
                unit = "s" if metric in ["startup_time", "temporal_connection"] else "ms" if "time" in metric or "latency" in metric else "MB"
                status = "PASS" if value <= target else "FAIL"
                
                if status == "PASS":
                    passed += 1
                total += 1
                
                print(f"{metric:20} {value:8.1f}{unit:2} (target: < {target}{unit}) - {status}")
            else:
                print(f"{metric:20} {'N/A':>10} (target: < {target}) - SKIP")
        
        print("-" * 60)
        print(f"OVERALL: {passed}/{total} benchmarks passed")
        
        if passed == total:
            print("✅ All Phase 1 performance targets met!")
        else:
            print("❌ Some performance targets not met. Optimization needed.")
        
        return passed == total


async def main():
    """Run all Phase 1 benchmarks."""
    print("PHASE 1 WORKFLOW SERVER BENCHMARKS")
    print("="*60)
    
    benchmarks = Phase1Benchmarks()
    
    # Run benchmarks in order
    await benchmarks.benchmark_startup()
    await benchmarks.benchmark_temporal_connection()
    
    # Initialize server for tool benchmarks
    config = WorkflowServerConfig(
        mock_mode=True,
        debug_mode=False,
        log_level="CRITICAL"
    )
    server = WorkflowServer(config)
    await server.initialize()
    
    await benchmarks.benchmark_tool_call_latency(server, iterations=50)
    await benchmarks.benchmark_workflow_start(iterations=25)
    await benchmarks.benchmark_result_submission(iterations=25)
    
    benchmarks.check_memory_baseline()
    
    # Print final summary
    benchmarks.print_summary()


if __name__ == "__main__":
    asyncio.run(main())