"""Performance benchmarking utilities for workflow testing."""

import concurrent.futures
import logging
import os
import statistics
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import psutil

from ..monitoring.metrics import MetricsCollector, PerformanceMetrics

logger = logging.getLogger(__name__)


class WorkflowBenchmark:
    """Benchmark workflow execution performance."""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.results: list[dict[str, Any]] = []
        self._process = psutil.Process(os.getpid())

    def benchmark_workflow_execution(
        self,
        workflow_executor_func: Callable,
        workflow_def: Any,
        inputs: dict[str, Any],
        iterations: int = 10,
        warmup_iterations: int = 2,
    ) -> dict[str, Any]:
        """Benchmark single workflow execution."""

        # Warmup runs
        for _ in range(warmup_iterations):
            try:
                workflow_executor_func(workflow_def, inputs)
            except Exception:  # noqa: S112
                # Ignore warmup errors - these are expected during warmup phase
                continue

        # Benchmark runs
        durations = []
        memory_usage = []
        cpu_usage = []
        success_count = 0

        for i in range(iterations):
            # Measure initial state
            initial_memory = self._process.memory_info().rss / 1024 / 1024  # MB
            self._process.cpu_percent()  # Initialize CPU measurement

            start_time = time.time()
            success = True

            try:
                result = workflow_executor_func(workflow_def, inputs)
                success = bool(result.get("success", True))
                if success:
                    success_count += 1
            except Exception:
                success = False

            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            # Measure final state
            final_memory = self._process.memory_info().rss / 1024 / 1024  # MB
            final_cpu = self._process.cpu_percent()

            durations.append(duration_ms)
            memory_usage.append(final_memory - initial_memory)
            cpu_usage.append(final_cpu)

            # Record performance metric
            if self.metrics_collector:
                metric = PerformanceMetrics(
                    operation_name="workflow_execution_benchmark",
                    timestamp=datetime.now(),
                    duration_ms=duration_ms,
                    success=success,
                    operation_type="benchmark",
                    memory_delta_mb=final_memory - initial_memory,
                    cpu_percent=final_cpu,
                    metadata={"iteration": i, "total_iterations": iterations},
                )
                self.metrics_collector.record_performance_metric(metric)

        # Calculate statistics
        result = {
            "iterations": iterations,
            "success_rate": (success_count / iterations) * 100,
            "duration_ms": {
                "mean": statistics.mean(durations),
                "median": statistics.median(durations),
                "min": min(durations),
                "max": max(durations),
                "stddev": statistics.stdev(durations) if len(durations) > 1 else 0,
                "p95": self._percentile(durations, 95),
                "p99": self._percentile(durations, 99),
            },
            "memory_delta_mb": {
                "mean": statistics.mean(memory_usage),
                "max": max(memory_usage),
                "min": min(memory_usage),
            },
            "cpu_usage": {
                "mean": statistics.mean(cpu_usage),
                "max": max(cpu_usage),
            },
            "throughput_ops_per_second": iterations / (sum(durations) / 1000),
        }

        self.results.append(result)
        return result

    def benchmark_concurrent_execution(
        self,
        workflow_executor_func: Callable,
        workflow_def: Any,
        inputs: dict[str, Any],
        concurrent_users: int = 10,
        operations_per_user: int = 5,
    ) -> dict[str, Any]:
        """Benchmark concurrent workflow execution."""

        total_operations = concurrent_users * operations_per_user
        results = []
        start_time = time.time()

        def user_simulation(user_id: int) -> list[dict[str, Any]]:
            """Simulate a single user's operations."""
            user_results = []

            for op_id in range(operations_per_user):
                op_start = time.time()
                success = True

                try:
                    result = workflow_executor_func(workflow_def, inputs)
                    success = bool(result.get("success", True))
                except Exception:
                    success = False

                op_end = time.time()
                duration_ms = (op_end - op_start) * 1000

                user_results.append({
                    "user_id": user_id,
                    "operation_id": op_id,
                    "duration_ms": duration_ms,
                    "success": success,
                    "timestamp": datetime.now(),
                })

            return user_results

        # Execute concurrent users
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [
                executor.submit(user_simulation, user_id)
                for user_id in range(concurrent_users)
            ]

            for future in concurrent.futures.as_completed(futures):
                try:
                    user_results = future.result()
                    results.extend(user_results)
                except Exception:  # noqa: S112
                    # Log error but continue - user benchmark failed
                    continue

        end_time = time.time()
        total_duration = end_time - start_time

        # Analyze results
        durations = [r["duration_ms"] for r in results]
        successes = [r for r in results if r["success"]]

        result = {
            "concurrent_users": concurrent_users,
            "operations_per_user": operations_per_user,
            "total_operations": total_operations,
            "completed_operations": len(results),
            "successful_operations": len(successes),
            "success_rate": (len(successes) / len(results)) * 100 if results else 0,
            "total_duration_seconds": total_duration,
            "throughput_ops_per_second": len(results) / total_duration if total_duration > 0 else 0,
            "duration_ms": {
                "mean": statistics.mean(durations) if durations else 0,
                "median": statistics.median(durations) if durations else 0,
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "p95": self._percentile(durations, 95) if durations else 0,
                "p99": self._percentile(durations, 99) if durations else 0,
            },
        }

        self.results.append(result)
        return result

    def benchmark_state_operations(
        self,
        state_manager: Any,
        operations: list[dict[str, Any]],
        iterations: int = 100,
    ) -> dict[str, Any]:
        """Benchmark state management operations."""

        operation_results = {}

        for operation in operations:
            op_type = operation["type"]
            op_func = operation["function"]
            op_args = operation.get("args", [])
            op_kwargs = operation.get("kwargs", {})

            durations = []
            success_count = 0

            for _ in range(iterations):
                start_time = time.time()
                success = True

                try:
                    result = op_func(*op_args, **op_kwargs)
                    success = bool(result)
                    if success:
                        success_count += 1
                except Exception:
                    success = False

                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                durations.append(duration_ms)

            operation_results[op_type] = {
                "iterations": iterations,
                "success_rate": (success_count / iterations) * 100,
                "duration_ms": {
                    "mean": statistics.mean(durations),
                    "median": statistics.median(durations),
                    "min": min(durations),
                    "max": max(durations),
                    "p95": self._percentile(durations, 95),
                },
                "throughput_ops_per_second": iterations / (sum(durations) / 1000),
            }

        return {
            "state_operations": operation_results,
            "summary": {
                "total_operations": sum(len(durations) for op in operation_results.values()),
                "avg_throughput": statistics.mean([
                    op["throughput_ops_per_second"]
                    for op in operation_results.values()
                ]),
            }
        }

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))


class PerformanceBenchmark:
    """General performance benchmarking utilities."""

    def __init__(self):
        self.baseline_results: dict[str, Any] = {}

    def measure_memory_usage(self, func: Callable, *args, **kwargs) -> dict[str, Any]:
        """Measure memory usage of a function."""
        process = psutil.Process(os.getpid())

        # Measure initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Execute function
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception:
            result = None
            success = False
        end_time = time.time()

        # Measure final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        return {
            "success": success,
            "result": result,
            "duration_ms": (end_time - start_time) * 1000,
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_delta_mb": final_memory - initial_memory,
        }

    def measure_cpu_usage(
        self,
        func: Callable,
        duration_seconds: float = 10.0,
        interval_seconds: float = 0.1,
        *args,
        **kwargs
    ) -> dict[str, Any]:
        """Measure CPU usage while running a function."""
        process = psutil.Process(os.getpid())
        cpu_measurements = []

        # Start CPU monitoring
        def monitor_cpu():
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                cpu_measurements.append(process.cpu_percent())
                time.sleep(interval_seconds)

        monitor_thread = threading.Thread(target=monitor_cpu)
        monitor_thread.daemon = True
        monitor_thread.start()

        # Execute function
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            success = True
        except Exception:
            result = None
            success = False
        execution_time = time.time() - start_time

        # Wait for monitoring to complete
        monitor_thread.join(timeout=duration_seconds + 1)

        return {
            "success": success,
            "result": result,
            "execution_time_ms": execution_time * 1000,
            "cpu_usage": {
                "measurements": cpu_measurements,
                "mean": statistics.mean(cpu_measurements) if cpu_measurements else 0,
                "max": max(cpu_measurements) if cpu_measurements else 0,
                "min": min(cpu_measurements) if cpu_measurements else 0,
            },
        }

    def set_baseline(self, name: str, result: dict[str, Any]):
        """Set performance baseline for comparison."""
        self.baseline_results[name] = result

    def compare_to_baseline(self, name: str, current_result: dict[str, Any]) -> dict[str, Any]:
        """Compare current result to baseline."""
        if name not in self.baseline_results:
            return {"error": f"No baseline set for '{name}'"}

        baseline = self.baseline_results[name]

        comparison = {
            "baseline": baseline,
            "current": current_result,
            "improvements": {},
            "regressions": {},
        }

        # Compare key metrics
        metrics_to_compare = ["duration_ms", "memory_delta_mb", "throughput_ops_per_second"]

        for metric in metrics_to_compare:
            if metric in baseline and metric in current_result:
                baseline_value = baseline[metric]
                current_value = current_result[metric]

                if isinstance(baseline_value, dict) and isinstance(current_value, dict):
                    # Compare nested metrics (like duration_ms.mean)
                    for submetric in ["mean", "median", "max"]:
                        if submetric in baseline_value and submetric in current_value:
                            baseline_sub = baseline_value[submetric]
                            current_sub = current_value[submetric]

                            if baseline_sub > 0:
                                change_percent = ((current_sub - baseline_sub) / baseline_sub) * 100

                                full_metric = f"{metric}.{submetric}"
                                if change_percent < -5:  # 5% improvement threshold
                                    comparison["improvements"][full_metric] = {
                                        "baseline": baseline_sub,
                                        "current": current_sub,
                                        "improvement_percent": abs(change_percent),
                                    }
                                elif change_percent > 5:  # 5% regression threshold
                                    comparison["regressions"][full_metric] = {
                                        "baseline": baseline_sub,
                                        "current": current_sub,
                                        "regression_percent": change_percent,
                                    }
                else:
                    # Compare simple numeric values
                    if baseline_value > 0:
                        change_percent = ((current_value - baseline_value) / baseline_value) * 100

                        if change_percent < -5:
                            comparison["improvements"][metric] = {
                                "baseline": baseline_value,
                                "current": current_value,
                                "improvement_percent": abs(change_percent),
                            }
                        elif change_percent > 5:
                            comparison["regressions"][metric] = {
                                "baseline": baseline_value,
                                "current": current_value,
                                "regression_percent": change_percent,
                            }

        return comparison


class ScalabilityBenchmark:
    """Benchmark scalability characteristics."""

    def __init__(self):
        self.scalability_results: list[dict[str, Any]] = []

    def test_user_scalability(
        self,
        test_func: Callable,
        user_counts: list[int],
        operations_per_user: int = 10,
        test_duration_seconds: int = 30,
    ) -> dict[str, Any]:
        """Test how performance scales with user count."""

        results = []

        for user_count in user_counts:
            logger.info(f"Testing with {user_count} users...")

            # Run load test
            start_time = time.time()
            successful_operations = 0
            total_operations = 0
            durations = []

            def user_load():
                nonlocal successful_operations, total_operations
                local_durations = durations.copy()  # noqa: B023 - Create a copy to avoid loop variable binding
                end_time = time.time() + test_duration_seconds

                while time.time() < end_time:
                    op_start = time.time()
                    try:
                        result = test_func()
                        success = bool(result.get("success", True))
                        if success:
                            successful_operations += 1
                    except Exception:  # noqa: S112
                        # Failed operation - continue tracking
                        continue

                    total_operations += 1
                    local_durations.append((time.time() - op_start) * 1000)

            # Start user threads
            threads = []
            for _ in range(user_count):
                thread = threading.Thread(target=user_load)
                threads.append(thread)
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join()

            total_time = time.time() - start_time

            result = {
                "user_count": user_count,
                "test_duration_seconds": test_duration_seconds,
                "total_operations": total_operations,
                "successful_operations": successful_operations,
                "success_rate": (successful_operations / total_operations) * 100 if total_operations > 0 else 0,
                "throughput_ops_per_second": total_operations / total_time if total_time > 0 else 0,
                "avg_response_time_ms": statistics.mean(durations) if durations else 0,
                "p95_response_time_ms": self._percentile(durations, 95) if durations else 0,
            }

            results.append(result)

        # Analyze scalability
        analysis = self._analyze_scalability(results)

        final_result = {
            "test_results": results,
            "scalability_analysis": analysis,
        }

        self.scalability_results.append(final_result)
        return final_result

    def test_data_scalability(
        self,
        test_func: Callable,
        data_sizes: list[int],
        iterations: int = 10,
    ) -> dict[str, Any]:
        """Test how performance scales with data size."""

        results = []

        for data_size in data_sizes:
            durations = []
            memory_usage = []
            success_count = 0

            for _ in range(iterations):
                start_time = time.time()
                initial_memory = psutil.Process().memory_info().rss / 1024 / 1024

                try:
                    result = test_func(data_size)
                    success = bool(result.get("success", True))
                    if success:
                        success_count += 1
                except Exception:  # noqa: S112
                    # Failed operation - continue tracking
                    continue

                end_time = time.time()
                final_memory = psutil.Process().memory_info().rss / 1024 / 1024

                durations.append((end_time - start_time) * 1000)
                memory_usage.append(final_memory - initial_memory)

            result = {
                "data_size": data_size,
                "iterations": iterations,
                "success_rate": (success_count / iterations) * 100,
                "avg_duration_ms": statistics.mean(durations),
                "avg_memory_delta_mb": statistics.mean(memory_usage),
                "throughput_items_per_second": data_size / (statistics.mean(durations) / 1000) if durations else 0,
            }

            results.append(result)

        return {
            "test_results": results,
            "data_scalability_analysis": self._analyze_data_scalability(results),
        }

    def _analyze_scalability(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze scalability characteristics."""
        if len(results) < 2:
            return {"error": "Need at least 2 data points for analysis"}

        # Calculate scalability metrics
        baseline = results[0]
        worst_case = results[-1]

        throughput_degradation = (
            (baseline["throughput_ops_per_second"] - worst_case["throughput_ops_per_second"]) /
            baseline["throughput_ops_per_second"] * 100
        ) if baseline["throughput_ops_per_second"] > 0 else 0

        response_time_increase = (
            (worst_case["avg_response_time_ms"] - baseline["avg_response_time_ms"]) /
            baseline["avg_response_time_ms"] * 100
        ) if baseline["avg_response_time_ms"] > 0 else 0

        # Find breaking point (where success rate drops below 95%)
        breaking_point = None
        for result in results:
            if result["success_rate"] < 95:
                breaking_point = result["user_count"]
                break

        return {
            "baseline_users": baseline["user_count"],
            "max_tested_users": worst_case["user_count"],
            "throughput_degradation_percent": throughput_degradation,
            "response_time_increase_percent": response_time_increase,
            "breaking_point_users": breaking_point,
            "scalability_rating": self._rate_scalability(throughput_degradation, response_time_increase),
        }

    def _analyze_data_scalability(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze data size scalability."""
        if len(results) < 2:
            return {"error": "Need at least 2 data points for analysis"}

        # Check if performance scales linearly
        data_sizes = [r["data_size"] for r in results]
        durations = [r["avg_duration_ms"] for r in results]

        # Simple linear regression to check complexity
        complexity_factor = durations[-1] / durations[0] / (data_sizes[-1] / data_sizes[0])

        return {
            "complexity_factor": complexity_factor,
            "complexity_assessment": (
                "Linear" if complexity_factor < 1.5 else
                "Slightly worse than linear" if complexity_factor < 3 else
                "Significantly worse than linear"
            ),
            "largest_data_size": max(data_sizes),
            "performance_at_largest": durations[-1],
        }

    def _rate_scalability(self, throughput_degradation: float, response_time_increase: float) -> str:
        """Rate overall scalability."""
        if throughput_degradation < 20 and response_time_increase < 100:
            return "Excellent"
        elif throughput_degradation < 40 and response_time_increase < 200:
            return "Good"
        elif throughput_degradation < 60 and response_time_increase < 400:
            return "Fair"
        else:
            return "Poor"

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
