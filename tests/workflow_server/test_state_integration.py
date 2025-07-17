"""
Test file for Phase 1: Core State Engine - Integration Tests

Tests complex workflows, performance, and real-world transformation examples.
"""

import time

import pytest

# Import implemented state system components
from aromcp.workflow_server.state.manager import StateManager


class TestCascadingTransformations:
    """Test complex cascading transformation scenarios"""

    def test_deep_cascading_chain(self):
        """Test deep chain of dependent transformations"""
        # Given
        schema = {
            "raw": {"value": "number"},
            "computed": {
                "step1": {"from": "raw.value", "transform": "input * 2"},
                "step2": {"from": "computed.step1", "transform": "input + 10"},
                "step3": {"from": "computed.step2", "transform": "input / 2"},
                "step4": {"from": "computed.step3", "transform": "input"},
                "final": {"from": "computed.step4", "transform": "input * 100"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_cascade"

        # When
        manager.update(workflow_id, [{"path": "raw.value", "value": 7}])
        state = manager.read(workflow_id)

        # Then
        # value=7 → step1=14 → step2=24 → step3=12 → step4=12 → final=1200
        assert state["value"] == 7
        assert state["step1"] == 14
        assert state["step2"] == 24
        assert state["step3"] == 12
        assert state["step4"] == 12
        assert state["final"] == 1200

    def test_diamond_dependency_pattern(self):
        """Test diamond-shaped dependency graph"""
        # Given
        schema = {
            "raw": {"source": "number"},
            "computed": {
                "branch_a": {"from": "raw.source", "transform": "input * 2"},
                "branch_b": {"from": "raw.source", "transform": "input + 5"},
                "merge": {"from": ["computed.branch_a", "computed.branch_b"], "transform": "input[0] * input[1]"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_diamond"

        # When
        manager.update(workflow_id, [{"path": "raw.source", "value": 3}])
        state = manager.read(workflow_id)

        # Then
        # source=3 → branch_a=6, branch_b=8 → merge=48
        assert state["source"] == 3
        assert state["branch_a"] == 6
        assert state["branch_b"] == 8
        assert state["merge"] == 48

    def test_multiple_root_dependencies(self):
        """Test transformations with multiple independent sources"""
        # Given
        schema = {
            "raw": {"a": "number", "b": "number", "c": "number"},
            "computed": {
                "sum_ab": {"from": ["raw.a", "raw.b"], "transform": "input[0] + input[1]"},
                "product_bc": {"from": ["raw.b", "raw.c"], "transform": "input[0] * input[1]"},
                "final": {"from": ["computed.sum_ab", "computed.product_bc"], "transform": "input[0] + input[1]"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_multiple"

        # When
        manager.update(
            workflow_id, [{"path": "raw.a", "value": 2}, {"path": "raw.b", "value": 3}, {"path": "raw.c", "value": 4}]
        )
        state = manager.read(workflow_id)

        # Then
        # a=2, b=3, c=4 → sum_ab=5, product_bc=12 → final=17
        assert state["sum_ab"] == 5
        assert state["product_bc"] == 12
        assert state["final"] == 17


class TestComplexDependencyGraphs:
    """Test complex dependency resolution scenarios"""

    def test_large_dependency_graph(self):
        """Test dependency resolution with many fields"""
        # Given - Create a larger graph with 20 computed fields
        schema = {"raw": {"base": "number"}, "computed": {}}

        # Create 10 first-level dependencies
        for i in range(10):
            schema["computed"][f"level1_{i}"] = {"from": "raw.base", "transform": f"input + {i}"}

        # Create 10 second-level dependencies (each depends on 2 first-level)
        for i in range(10):
            dep1 = f"computed.level1_{i % 10}"
            dep2 = f"computed.level1_{(i + 1) % 10}"
            schema["computed"][f"level2_{i}"] = {"from": [dep1, dep2], "transform": "input[0] + input[1]"}

        manager = StateManager(schema)
        workflow_id = "wf_large"

        # When
        manager.update(workflow_id, [{"path": "raw.base", "value": 10}])
        state = manager.read(workflow_id)

        # Then
        assert state["base"] == 10
        assert state["level1_0"] == 10  # 10 + 0
        assert state["level1_5"] == 15  # 10 + 5
        assert state["level2_0"] == 21  # (10+0) + (10+1)

    def test_mixed_tier_dependencies(self):
        """Test dependencies across all three tiers"""
        # Given
        schema = {
            "raw": {"counter": "number"},
            "state": {"multiplier": "number"},
            "computed": {
                "doubled": {"from": "raw.counter", "transform": "input * 2"},
                "scaled": {"from": ["computed.doubled", "state.multiplier"], "transform": "input[0] * input[1]"},
                "combined": {
                    "from": ["raw.counter", "state.multiplier", "computed.scaled"],
                    "transform": "input[0] + input[1] + input[2]",
                },
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_mixed"

        # When
        manager.update(workflow_id, [{"path": "raw.counter", "value": 5}, {"path": "state.multiplier", "value": 3}])
        state = manager.read(workflow_id)

        # Then
        # counter=5, multiplier=3 → doubled=10 → scaled=30 → combined=38 (5+3+30)
        assert state["doubled"] == 10
        assert state["scaled"] == 30
        assert state["combined"] == 38


class TestRealWorldTransformationExamples:
    """Test realistic transformation scenarios from documentation"""

    def test_git_file_parsing_example(self):
        """Test git output parsing transformation from docs"""
        # Given
        schema = {
            "raw": {"git_output": "string"},
            "computed": {
                "parsed_files": {
                    "from": "raw.git_output",
                    "transform": "input.split('\\n').filter(l => l.trim()).map(l => l.trim())",
                },
                "file_count": {"from": "computed.parsed_files", "transform": "input.length"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_git"

        # When
        git_output = "file1.ts\n  file2.js  \n\nfile3.py\n"
        manager.update(workflow_id, [{"path": "raw.git_output", "value": git_output}])
        state = manager.read(workflow_id)

        # Then
        assert state["parsed_files"] == ["file1.ts", "file2.js", "file3.py"]
        assert state["file_count"] == 3

    def test_user_data_processing_example(self):
        """Test user data aggregation and formatting"""
        # Given
        schema = {
            "raw": {"users": "array", "department": "string"},
            "computed": {
                "adult_users": {"from": "raw.users", "transform": "input.filter(u => u.age >= 18)"},
                "user_summary": {
                    "from": ["computed.adult_users", "raw.department"],
                    "transform": (
                        "`${input[1]}: ${input[0].length} adult users (${input[0].map(u => u.name).join(', ')})`"
                    ),
                },
                "average_age": {
                    "from": "computed.adult_users",
                    "transform": "Math.round(input.reduce((sum, u) => sum + u.age, 0) / input.length)",
                },
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_users"

        # When
        users = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 17}, {"name": "Charlie", "age": 30}]
        manager.update(
            workflow_id, [{"path": "raw.users", "value": users}, {"path": "raw.department", "value": "Engineering"}]
        )
        state = manager.read(workflow_id)

        # Then
        # print(f"DEBUG: state = {state}")
        assert len(state["adult_users"]) == 2
        assert state["adult_users"][0]["name"] == "Alice"
        assert state["adult_users"][1]["name"] == "Charlie"
        assert state["user_summary"] == "Engineering: 2 adult users (Alice, Charlie)"
        assert state["average_age"] == 28  # (25 + 30) / 2 = 27.5 → 28

    def test_configuration_validation_example(self):
        """Test configuration validation and defaults"""
        # Given
        schema = {
            "raw": {"config": "object"},
            "computed": {
                "validated_config": {
                    "from": "raw.config",
                    "transform": """({
                        timeout: input.timeout || 30000,
                        retries: Math.max(0, Math.min(input.retries || 3, 10)),
                        debug: !!input.debug,
                        endpoint: input.endpoint || 'http://localhost:3000'
                    })""",
                    "on_error": "use_fallback",
                    "fallback": {"timeout": 30000, "retries": 3, "debug": False, "endpoint": "http://localhost:3000"},
                },
                "is_valid": {
                    "from": "computed.validated_config",
                    "transform": "input.endpoint.startsWith('http') && input.timeout > 0",
                },
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_config"

        # When
        partial_config = {"timeout": 5000, "retries": 15, "debug": "yes"}
        manager.update(workflow_id, [{"path": "raw.config", "value": partial_config}])
        state = manager.read(workflow_id)

        # Then
        validated = state["validated_config"]
        assert validated["timeout"] == 5000
        assert validated["retries"] == 10  # Clamped to max 10
        assert validated["debug"] is True  # "yes" is truthy
        assert validated["endpoint"] == "http://localhost:3000"  # Default
        assert state["is_valid"] is True


class TestPerformanceLargeState:
    """Test performance with large state objects"""

    def test_large_state_update_performance(self):
        """Test performance with many state fields"""
        # Given
        manager = StateManager()
        workflow_id = "wf_perf"

        # Create many updates
        updates = []
        for i in range(1000):
            updates.append({"path": f"raw.field_{i}", "value": i})

        # When
        start_time = time.time()
        manager.update(workflow_id, updates)
        end_time = time.time()

        # Then
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < 100  # Should complete in under 100ms

        # Verify data integrity
        state = manager.read(workflow_id)
        assert state["field_0"] == 0
        assert state["field_500"] == 500
        assert state["field_999"] == 999

    def test_transformation_performance(self):
        """Test transformation performance with large arrays"""
        # Given
        schema = {
            "raw": {"large_array": "array"},
            "computed": {
                "filtered": {"from": "raw.large_array", "transform": "input.filter(x => x % 2 === 0)"},
                "mapped": {"from": "computed.filtered", "transform": "input.map(x => x * 2)"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_perf_transform"

        # Create large array
        large_array = list(range(10000))

        # When
        start_time = time.time()
        manager.update(workflow_id, [{"path": "raw.large_array", "value": large_array}])
        end_time = time.time()

        # Then
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < 500  # Should complete in under 500ms

        # Verify results
        state = manager.read(workflow_id)
        assert len(state["filtered"]) == 5000  # Half the elements (even numbers)
        assert state["mapped"][0] == 0  # 0 * 2
        assert state["mapped"][1] == 4  # 2 * 2


class TestErrorHandlingStrategies:
    """Test different error handling strategies in transformations"""

    def test_use_fallback_strategy(self):
        """Test use_fallback error handling"""
        # Given
        schema = {
            "raw": {"json_string": "string"},
            "computed": {
                "parsed": {
                    "from": "raw.json_string",
                    "transform": "JSON.parse(input)",
                    "on_error": "use_fallback",
                    "fallback": {"error": "invalid_json"},
                }
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_fallback"

        # When - Invalid JSON
        manager.update(workflow_id, [{"path": "raw.json_string", "value": "invalid json"}])
        state = manager.read(workflow_id)

        # Then
        assert state["parsed"] == {"error": "invalid_json"}

    def test_propagate_strategy(self):
        """Test propagate error handling"""
        # Given
        schema = {
            "raw": {"divisor": "number"},
            "computed": {
                "result": {"from": "raw.divisor", "transform": "input.nonexistent.property", "on_error": "propagate"}
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_propagate"

        # When/Then - Should propagate error when transformation fails
        from aromcp.workflow_server.state.models import ComputedFieldError

        with pytest.raises(ComputedFieldError):
            manager.update(workflow_id, [{"path": "raw.divisor", "value": 0}])

    def test_ignore_strategy(self):
        """Test ignore error handling"""
        # Given
        schema = {
            "raw": {"data": "any"},
            "computed": {
                "processed": {"from": "raw.data", "transform": "input.nonexistent.method()", "on_error": "ignore"},
                "other": {"from": "raw.data", "transform": "input.toString()"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_ignore"

        # When
        manager.update(workflow_id, [{"path": "raw.data", "value": "test"}])
        state = manager.read(workflow_id)

        # Then
        # processed should not be set due to error being ignored
        assert "processed" not in state
        assert state["other"] == "test"  # Other transformations should still work
