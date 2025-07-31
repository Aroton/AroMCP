"""
Focused failing tests that reproduce specific implementation issues.

These tests are designed to fail and expose the exact bugs in the current tool implementations.
They should pass once the implementations are fixed.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the expected tool implementations
try:
    from aromcp.analysis_server.tools.find_references import find_references_impl
    from aromcp.analysis_server.tools.get_function_details import get_function_details_impl
    from aromcp.analysis_server.tools.get_call_trace import get_call_trace_impl
    from aromcp.analysis_server.models.typescript_models import (
        FindReferencesResponse,
        FunctionDetailsResponse,
        CallTraceResponse,
        ReferenceInfo,
        FunctionDetail,
        ExecutionPath,
        CallGraphStats,
        AnalysisError,
    )
    from aromcp.analysis_server.tools.symbol_resolver import ReferenceType
except ImportError:
    # Expected to fail initially - create placeholder functions for testing
    def find_references_impl(*args, **kwargs):
        raise NotImplementedError("Tool not yet implemented")
    
    def get_function_details_impl(*args, **kwargs):
        raise NotImplementedError("Tool not yet implemented")
    
    def get_call_trace_impl(*args, **kwargs):
        raise NotImplementedError("Tool not yet implemented")
    
    class FindReferencesResponse:
        pass
    
    class FunctionDetailsResponse:
        pass
    
    class CallTraceResponse:
        pass
    
    class ReferenceInfo:
        pass
    
    class FunctionDetail:
        pass
    
    class ExecutionPath:
        pass
    
    class CallGraphStats:
        pass
    
    class AnalysisError:
        pass


class TestFindReferencesSpecificFailures:
    """Focused tests that expose specific find_references_impl issues."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Set MCP_FILE_ROOT for testing
            import os
            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)
            
            try:
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def test_include_tests_false_should_filter_test_files_by_default(self, temp_project):
        """
        FAILING TEST: find_references_impl with include_tests=False should filter out .test.ts files by default.
        
        Current issue: The implementation does not respect the include_tests=False parameter
        and includes test files in results when it shouldn't.
        """
        # Create source file with AdminUser class
        source_file = temp_project / "src" / "user.ts"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("""
        export class AdminUser {
            constructor(public name: string) {}
            
            hasPermission(permission: string): boolean {
                return true;
            }
        }
        """)
        
        # Create test file that references AdminUser
        test_file = temp_project / "tests" / "user.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
        import { AdminUser } from '../src/user';
        
        describe('AdminUser', () => {
            test('should create admin user', () => {
                const admin = new AdminUser('Test Admin');
                expect(admin.hasPermission('read')).toBe(true);
            });
        });
        """)
        
        # Test with include_tests=False (default behavior)
        result = find_references_impl(
            symbol="AdminUser",
            file_paths=[str(source_file), str(test_file)],
            include_declarations=True,
            include_usages=True,
            include_tests=False  # This should exclude test files
        )
        
        assert isinstance(result, FindReferencesResponse)
        
        # EXPECTED BEHAVIOR: Should NOT include any references from test files
        test_references = [ref for ref in result.references 
                          if ref.file_path.endswith(".test.ts")]
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        assert len(test_references) == 0, f"Found {len(test_references)} references in test files, but include_tests=False should exclude them"
        
        # Should still find references from source files
        source_references = [ref for ref in result.references 
                           if not ref.file_path.endswith(".test.ts")]
        assert len(source_references) > 0, "Should still find references in source files"

    def test_include_tests_true_should_include_test_files(self, temp_project):
        """
        FAILING TEST: find_references_impl with include_tests=True should include .test.ts files.
        
        Current issue: The implementation may not properly handle include_tests=True parameter
        or may have inconsistent behavior with test file inclusion.
        """
        # Create source file with AdminUser class
        source_file = temp_project / "src" / "user.ts"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("""
        export class AdminUser {
            constructor(public name: string) {}
            
            hasPermission(permission: string): boolean {
                return true;
            }
        }
        """)
        
        # Create test file that references AdminUser
        test_file = temp_project / "tests" / "user.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
        import { AdminUser } from '../src/user';
        
        describe('AdminUser', () => {
            test('should create admin user', () => {
                const admin = new AdminUser('Test Admin');
                expect(admin.hasPermission('read')).toBe(true);
            });
        });
        """)
        
        # Test with include_tests=True (should include test files)
        result = find_references_impl(
            symbol="AdminUser",
            file_paths=[str(source_file), str(test_file)],
            include_declarations=True,
            include_usages=True,
            include_tests=True  # This should include test files
        )
        
        assert isinstance(result, FindReferencesResponse)
        
        # EXPECTED BEHAVIOR: Should include references from test files
        test_references = [ref for ref in result.references 
                          if ref.file_path.endswith(".test.ts")]
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        assert len(test_references) > 0, f"Expected references in test files with include_tests=True, but found {len(test_references)}"
        
        # Should also find references from source files
        source_references = [ref for ref in result.references 
                           if not ref.file_path.endswith(".test.ts")]
        assert len(source_references) > 0, "Should find references in both source and test files"

    def test_method_syntax_detection_for_class_methods_failing(self, temp_project):
        """
        FAILING TEST: find_references_impl should detect method syntax like 'ClassName#methodName'.
        
        Current issue: Method syntax detection for class methods is failing.
        The implementation doesn't properly parse or resolve the 'Class#method' syntax.
        """
        # Create class with specific method
        class_file = temp_project / "user-service.ts" 
        class_file.write_text("""
        export class UserService {
            private users: Map<number, User> = new Map();
            
            validateUser(user: User): boolean {
                return user.id > 0 && user.name.length > 0;
            }
            
            createUser(userData: UserData): User {
                const user = this.transformUserData(userData);
                if (this.validateUser(user)) {
                    this.users.set(user.id, user);
                    return user;
                }
                throw new Error('Invalid user data');
            }
            
            private transformUserData(data: UserData): User {
                return { id: Date.now(), name: data.name, email: data.email };
            }
        }
        """)
        
        # Test finding references using Class#method syntax
        result = find_references_impl(
            symbol="UserService#validateUser",  # Specific method syntax
            file_paths=str(class_file),
            include_declarations=True,
            include_usages=True,
            method_resolution=True  # Phase 2 feature for method syntax
        )
        
        assert isinstance(result, FindReferencesResponse)
        
        # EXPECTED BEHAVIOR: Should find the specific method, not other methods
        validate_user_refs = [ref for ref in result.references 
                             if ref.symbol_name == "validateUser"]
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        assert len(validate_user_refs) > 0, "Should find references to UserService#validateUser method"
        
        # Should identify this as a method with class context
        for ref in validate_user_refs:
            # THIS SHOULD PASS BUT CURRENTLY FAILS:
            # Note: The ReferenceInfo model doesn't currently have class_name/method_name attributes
            # This shows the model needs enhancement for method syntax support
            class_name = getattr(ref, 'class_name', None)
            method_name = getattr(ref, 'method_name', None)
            
            assert class_name is not None, f"Reference should have class_name attribute for method syntax, but found None"
            assert class_name == "UserService", f"Expected class_name='UserService', got '{class_name}'"
            assert method_name is not None, f"Reference should have method_name attribute for method syntax, but found None"
            assert method_name == "validateUser", f"Expected method_name='validateUser', got '{method_name}'"

    def test_performance_requirements_not_met_for_large_codebases(self, temp_project):
        """
        FAILING TEST: find_references_impl should meet performance requirements for large codebases.
        
        Current issue: Performance requirements are not met for large codebases.
        The implementation may be too slow or inefficient for realistic project sizes.
        """
        # Create multiple files to simulate a realistic codebase
        files_content = {}
        
        # Create 50 files with cross-references to simulate realistic load
        for i in range(50):
            filename = f"module_{i}.ts"
            files_content[filename] = f"""
            import {{ BaseUser }} from './base_user';
            import {{ UserService }} from './user_service';
            
            export class Module{i}Service {{
                private userService = new UserService();
                
                processUser(user: BaseUser): string {{
                    return `Module{i} processing: ${{user.name}}`;
                }}
                
                getUserData(id: number): BaseUser | null {{
                    return this.userService.getUser(id);
                }}
                
                // Multiple references to BaseUser to increase search complexity
                validateUser(user: BaseUser): boolean {{
                    return user && user.name && user.name.length > 0;
                }}
                
                transformUser(input: BaseUser): BaseUser {{
                    return {{ ...input, name: input.name.trim() }};
                }}
            }}
            """
        
        # Create the referenced files
        files_content["base_user.ts"] = """
        export interface BaseUser {
            id: number;
            name: string;
            email?: string;
        }
        """
        
        files_content["user_service.ts"] = """
        import { BaseUser } from './base_user';
        
        export class UserService {
            getUser(id: number): BaseUser | null {
                return null;
            }
        }
        """
        
        # Write all files
        file_paths = []
        for filename, content in files_content.items():
            file_path = temp_project / filename
            file_path.write_text(content)
            file_paths.append(str(file_path))
        
        # Test performance requirement
        start_time = time.perf_counter()
        
        result = find_references_impl(
            symbol="BaseUser",
            file_paths=file_paths,
            include_declarations=True,
            include_usages=True,
            resolve_inheritance=True,
            resolve_imports=True
        )
        
        end_time = time.perf_counter()
        analysis_time = end_time - start_time
        
        assert isinstance(result, FindReferencesResponse)
        
        # Phase 2 performance requirement: <30 seconds for realistic projects
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        assert analysis_time < 30.0, f"Reference finding took {analysis_time:.2f}s, should be <30s for 52 files"
        
        # Should find many references across the files
        assert len(result.references) >= 100, f"Expected many references across files, found {len(result.references)}"
        
        # Should provide performance statistics
        assert hasattr(result, 'analysis_stats'), "Should provide analysis statistics"
        assert result.analysis_stats.files_analyzed >= len(file_paths), f"Should analyze all {len(file_paths)} files"


class TestGetFunctionDetailsSpecificFailures:
    """Focused tests that expose specific get_function_details_impl issues."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Set MCP_FILE_ROOT for testing
            import os
            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)
            
            try:
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def test_missing_max_constraint_depth_parameter_support(self, temp_project):
        """
        FAILING TEST: get_function_details_impl should support max_constraint_depth parameter.
        
        Current issue: Missing max_constraint_depth parameter support.
        The implementation should handle deep generic constraint chains up to specified depth.
        """
        # Create function with deep generic constraints
        test_file = temp_project / "deep_generics.ts"
        test_file.write_text("""
        interface Level1 { id: string; }
        interface Level2<T extends Level1> { data: T; }
        interface Level3<T extends Level1, U extends Level2<T>> { nested: U; }
        interface Level4<T extends Level1, U extends Level2<T>, V extends Level3<T, U>> { deep: V; }
        interface Level5<T extends Level1, U extends Level2<T>, V extends Level3<T, U>, W extends Level4<T, U, V>> { veryDeep: W; }
        
        function deepGenericFunction<
            T extends Level1,
            U extends Level2<T>,
            V extends Level3<T, U>,
            W extends Level4<T, U, V>,
            X extends Level5<T, U, V, W>
        >(input: X): T {
            return input.veryDeep.deep.nested.data;
        }
        """)
        
        # Test with max_constraint_depth parameter
        result = get_function_details_impl(
            functions="deepGenericFunction",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=5  # THIS PARAMETER SHOULD BE SUPPORTED BUT ISN'T
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        # The function should handle the max_constraint_depth parameter without error
        assert result.success is True, "Should handle max_constraint_depth parameter without error"
        
        deep_func_list = result.functions.get("deepGenericFunction")
        assert deep_func_list is not None, "Should find the deep generic function"
        deep_func = deep_func_list[0] if deep_func_list else None
        assert deep_func is not None, "Should have at least one function detail"
        
        # Should resolve constraints up to the specified depth
        if deep_func and deep_func.types:
            # Should handle 5 levels of generic constraints
            expected_types = ["Level1", "Level2", "Level3", "Level4", "Level5"]
            found_types = [t for t in expected_types if t in deep_func.types]
            
            # THIS SHOULD PASS BUT CURRENTLY FAILS:
            assert len(found_types) >= 3, f"Should resolve at least 3 constraint levels, found: {found_types}"

    def test_imported_type_resolution_not_working_properly(self, temp_project):
        """
        FAILING TEST: get_function_details_impl should resolve imported types properly.
        
        Current issue: Imported type resolution not working properly - expects "BaseEntity" 
        to be found but only "User" is found. The implementation doesn't properly resolve
        imported types from other files.
        """
        # Create base types file
        base_file = temp_project / "base.ts"
        base_file.write_text("""
        export interface BaseEntity {
            id: string;
            createdAt: Date;
        }
        
        export interface User extends BaseEntity {
            name: string;
            email: string;
        }
        """)
        
        # Create function file that imports types
        func_file = temp_project / "processor.ts"
        func_file.write_text("""
        import { User, BaseEntity } from './base';
        
        export function processUser(user: User): User {
            return { ...user, createdAt: new Date() };
        }
        
        export function validateEntity<T extends BaseEntity>(entity: T): boolean {
            return entity.id.length > 0;
        }
        """)
        
        result = get_function_details_impl(
            functions=["processUser", "validateEntity"],
            file_paths=[str(base_file), str(func_file)],
            include_types=True,
            resolution_depth="generics",
            resolve_imports=True  # Should resolve imported types
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True, "Should successfully analyze functions with imported types"
        
        # Check processUser function
        process_user_list = result.functions.get("processUser")
        assert process_user_list is not None, "Should find processUser function"
        process_user = process_user_list[0] if process_user_list else None
        assert process_user is not None, "Should have at least one function detail"
        
        if process_user and process_user.types:
            # THIS SHOULD PASS BUT CURRENTLY FAILS:
            # Should resolve both User and BaseEntity types
            assert "User" in process_user.types, f"Should find User type, found types: {list(process_user.types.keys())}"
            assert "BaseEntity" in process_user.types, f"Should find BaseEntity type (imported), found types: {list(process_user.types.keys())}"
        
        # Check validateEntity function
        validate_entity_list = result.functions.get("validateEntity")
        if validate_entity_list:
            validate_entity = validate_entity_list[0] if validate_entity_list else None
            if validate_entity:
                # Should show the generic constraint properly
                assert "T extends BaseEntity" in validate_entity.signature, "Should show generic constraint with BaseEntity"
                
                if validate_entity.types:
                    # THIS SHOULD PASS BUT CURRENTLY FAILS:
                    assert "BaseEntity" in validate_entity.types, f"Should resolve BaseEntity in generic function, found types: {list(validate_entity.types.keys())}"


class TestGetCallTraceSpecificFailures:
    """Focused tests that expose specific get_call_trace_impl issues."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Set MCP_FILE_ROOT for testing
            import os
            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)
            
            try:
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def test_performance_constraint_issue_max_depth_exceeded(self, temp_project):
        """
        FAILING TEST: get_call_trace_impl should respect max_depth constraints.
        
        Current issue: Performance constraint issue where max_depth_reached is 6 but should be ≤ 5.
        The implementation doesn't properly limit the depth of call tracing.
        """
        # Create file with deep call chain (more than 5 levels)
        test_file = temp_project / "deep_calls.ts" 
        test_file.write_text("""
        function level0(): void {
            level1();
        }
        
        function level1(): void {
            level2();
        }
        
        function level2(): void {
            level3();
        }
        
        function level3(): void {
            level4();
        }
        
        function level4(): void {
            level5();
        }
        
        function level5(): void {
            console.log("Deep call completed");
        }
        """)
        
        # Test with max_depth=5 (should not exceed this)
        result = get_call_trace_impl(
            entry_point="level0",
            file_paths=str(test_file),
            max_depth=5,  # Should stop at depth 5
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        # max_depth_reached should be ≤ 5, not 6
        assert result.call_graph_stats.max_depth_reached <= 5, f"max_depth_reached is {result.call_graph_stats.max_depth_reached}, should be ≤ 5"
        
        # Should still find some execution paths within the depth limit
        assert len(result.execution_paths) > 0, "Should find execution paths within depth limit"

    def test_error_handling_not_working_for_non_existent_entry_points(self, temp_project):
        """
        FAILING TEST: get_call_trace_impl should report errors for non-existent entry points.
        
        Current issue: Error handling not working - should report errors for non-existent 
        entry points but returns empty errors array instead of proper error reporting.
        """
        # Create file with some functions, but test with non-existent entry point
        test_file = temp_project / "existing_functions.ts"
        test_file.write_text("""
        function actualFunction(): void {
            console.log("This function exists");
        }
        
        function anotherFunction(): void {
            actualFunction();
        }
        """)
        
        # Test with non-existent entry point
        result = get_call_trace_impl(
            entry_point="nonExistentFunction",  # This function doesn't exist
            file_paths=str(test_file),
            max_depth=5,
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        # Should report error for non-existent entry point, not return empty errors array
        assert len(result.errors) > 0, f"Should report error for non-existent entry point, but errors array is empty: {result.errors}"
        
        # Should have appropriate error information
        error = result.errors[0]
        assert isinstance(error, AnalysisError), f"Error should be AnalysisError, got {type(error)}"
        assert error.code in ["NOT_FOUND", "INVALID_ENTRY_POINT"], f"Error code should be NOT_FOUND or INVALID_ENTRY_POINT, got '{error.code}'"
        assert "nonExistentFunction" in error.message, f"Error message should mention the non-existent function name"
        
        # Should not have execution paths for non-existent entry point
        assert len(result.execution_paths) == 0, "Should not have execution paths for non-existent entry point"

    def test_error_handling_empty_entry_point_should_report_error(self, temp_project):
        """
        FAILING TEST: get_call_trace_impl should report errors for empty entry points.
        
        Current issue: Error handling doesn't properly validate empty entry point strings.
        """
        # Create test file
        test_file = temp_project / "some_functions.ts"
        test_file.write_text("""
        function validFunction(): void {
            console.log("Valid function");
        }
        """)
        
        # Test with empty entry point
        result = get_call_trace_impl(
            entry_point="",  # Empty entry point should be invalid
            file_paths=str(test_file),
            max_depth=5,
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        # Should report validation error for empty entry point
        assert len(result.errors) > 0, "Should report validation error for empty entry point"
        
        # Should have appropriate validation error
        validation_errors = [e for e in result.errors if e.code == "INVALID_ENTRY_POINT"]
        assert len(validation_errors) > 0, f"Should have INVALID_ENTRY_POINT error, found error codes: {[e.code for e in result.errors]}"
        
        validation_error = validation_errors[0]
        assert "empty" in validation_error.message.lower() or "invalid" in validation_error.message.lower(), \
            f"Error message should mention empty/invalid entry point: {validation_error.message}"

    def test_depth_limit_enforcement_with_complex_recursion(self, temp_project):
        """
        FAILING TEST: get_call_trace_impl should properly enforce depth limits with recursive calls.
        
        Current issue: Depth limit enforcement may not work properly with recursive or complex call patterns.
        """
        # Create file with recursive function that could exceed depth limits
        test_file = temp_project / "recursive_calls.ts"
        test_file.write_text("""
        function recursiveFunction(n: number): number {
            if (n <= 0) {
                return 0;
            }
            return n + recursiveFunction(n - 1);  // Direct recursion
        }
        
        function mutualA(n: number): number {
            if (n <= 0) return 0;
            return n + mutualB(n - 1);  // Mutual recursion
        }
        
        function mutualB(n: number): number {
            if (n <= 0) return 0;
            return n + mutualA(n - 1);
        }
        """)
        
        # Test with strict depth limit
        result = get_call_trace_impl(
            entry_point="recursiveFunction",
            file_paths=str(test_file),
            max_depth=3,  # Very strict depth limit
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # THIS SHOULD PASS BUT CURRENTLY FAILS:
        # Should strictly enforce depth limit even with recursion
        assert result.call_graph_stats.max_depth_reached <= 3, \
            f"max_depth_reached is {result.call_graph_stats.max_depth_reached}, should be ≤ 3 even with recursion"
        
        # Should detect that recursion/cycles exist
        assert result.call_graph_stats.cycles_detected > 0, "Should detect recursive cycles"
        
        # Should still provide some execution paths within the depth limit
        assert len(result.execution_paths) > 0, "Should provide execution paths within strict depth limit"


class TestAdditionalEdgeCaseFailures:
    """Additional edge case tests to ensure comprehensive coverage of implementation issues."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Set MCP_FILE_ROOT for testing
            import os
            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)
            
            try:
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def test_find_references_should_fail_with_test_files_when_include_tests_false(self, temp_project):
        """
        FAILING TEST: Ensure include_tests=False actually filters test files when they exist.
        
        This test is designed to fail when test files are incorrectly included.
        It creates a scenario where test files contain references that should be excluded.
        """
        # Create source file
        source_file = temp_project / "user.ts"
        source_file.write_text("""
        export class TestUser {
            name: string;
            constructor(name: string) {
                this.name = name;
            }
        }
        """)
        
        # Create multiple test files that reference TestUser
        test_files = [
            temp_project / "user.test.ts",
            temp_project / "integration.test.ts", 
            temp_project / "spec" / "user.spec.ts"
        ]
        
        test_files[2].parent.mkdir(parents=True)
        
        for i, test_file in enumerate(test_files):
            test_file.write_text(f"""
            import {{ TestUser }} from '../user' if '{test_file.name}'.endswith('.spec.ts') else './user';
            
            describe('TestUser {i}', () => {{
                test('should create TestUser', () => {{
                    const user = new TestUser('Test Name {i}');
                    expect(user.name).toBe('Test Name {i}');
                }});
            }});
            """)
        
        all_files = [str(source_file)] + [str(f) for f in test_files]
        
        # Test with include_tests=False - should exclude all test files
        result = find_references_impl(
            symbol="TestUser",
            file_paths=all_files,
            include_declarations=True,
            include_usages=True,
            include_tests=False
        )
        
        # Count references by file type
        test_refs = []
        source_refs = []
        
        for ref in result.references:
            if any(ref.file_path.endswith(ext) for ext in ['.test.ts', '.spec.ts']):
                test_refs.append(ref)
            else:
                source_refs.append(ref)
        
        # This should pass but may fail if include_tests filtering is broken
        assert len(test_refs) == 0, f"include_tests=False should exclude {len(test_refs)} test file references"
        # Should still find source references
        if len(result.references) > 0:  # Only check if implementation returns results
            assert len(source_refs) > 0, "Should find references in source files"

    def test_get_call_trace_should_handle_malformed_functions_gracefully(self, temp_project):
        """
        FAILING TEST: get_call_trace_impl should handle malformed/incomplete functions gracefully.
        
        Current issue: May not handle syntax errors or incomplete function definitions properly.
        """
        # Create file with malformed TypeScript
        malformed_file = temp_project / "malformed.ts"
        malformed_file.write_text("""
        // This file has intentional syntax errors
        function validFunction(): void {
            console.log("This function is valid");
            invalidFunction(); // This call target doesn't exist
        }
        
        function incompleteFunction( // Missing closing parenthesis and body
        
        class IncompleteClass {
            method1() {
                // Missing closing brace
        
        // Dangling function with no name
        function (): void {
            console.log("Anonymous function");
        }
        
        export { validFunction }; // Export the only valid function
        """)
        
        # Test call tracing on malformed file
        result = get_call_trace_impl(
            entry_point="validFunction",
            file_paths=str(malformed_file),
            max_depth=5,
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Should handle malformed input gracefully - either succeed with warnings or fail with clear errors
        if len(result.errors) > 0:
            # If it reports errors, they should be meaningful
            syntax_errors = [e for e in result.errors if "syntax" in e.message.lower() or "parse" in e.message.lower()]
            assert len(syntax_errors) > 0, "Should report syntax/parse errors for malformed input"
        else:
            # If it succeeds, should not crash and should provide some reasonable output
            assert isinstance(result.execution_paths, list), "Should return valid execution_paths structure"

    def test_get_function_details_should_fail_with_unsupported_parameters(self, temp_project):
        """
        FAILING TEST: get_function_details_impl should fail gracefully with unsupported parameters.
        
        Current issue: May not validate parameters properly or may accept parameters it doesn't implement.
        """
        test_file = temp_project / "simple.ts"
        test_file.write_text("""
        function simpleFunction(param: string): number {
            return param.length;
        }
        """)
        
        # Test with unsupported parameters that should cause errors
        unsupported_params = [
            # Missing parameter that should be required
            {"functions": "simpleFunction", "file_paths": str(test_file), "max_constraint_depth": 10},
            # Invalid resolution_depth value
            {"functions": "simpleFunction", "file_paths": str(test_file), "resolution_depth": "invalid_depth"},
            # Batch processing parameter without implementation
            {"functions": "simpleFunction", "file_paths": str(test_file), "batch_processing": True, "batch_size": 100},
        ]
        
        for i, params in enumerate(unsupported_params):
            try:
                result = get_function_details_impl(**params)
                
                # If it doesn't raise an exception, it should at least report errors
                if hasattr(result, 'errors') and len(result.errors) > 0:
                    # Should have parameter validation errors
                    param_errors = [e for e in result.errors if "parameter" in e.message.lower() 
                                   or "unsupported" in e.message.lower() 
                                   or "invalid" in e.message.lower()]
                    # This may fail if parameter validation is missing
                    assert len(param_errors) > 0, f"Test case {i}: Should report parameter validation errors for unsupported parameters"
                else:
                    # If no errors reported, implementation may be silently ignoring unsupported parameters
                    # This is also a bug that should be caught
                    assert False, f"Test case {i}: Implementation should validate parameters and report errors for unsupported options"
                    
            except TypeError as e:
                # This is expected for truly unsupported parameters
                assert "unexpected keyword argument" in str(e) or "argument" in str(e), f"Test case {i}: Should get meaningful TypeError for unsupported parameters"
            except Exception as e:
                # Other exceptions should be meaningful
                assert len(str(e)) > 0, f"Test case {i}: Exception should have meaningful message: {e}"