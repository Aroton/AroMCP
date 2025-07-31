"""
Focused failing tests for advanced type resolution features that are missing.

This file contains 12 specific failing test scenarios that need TDD implementation.
Each test focuses on a specific advanced TypeScript type resolution feature that
is currently not properly implemented in the analysis server.

The tests cover:
1. Progressive resolution depth with fallback_on_complexity parameter
2. Error handling with specific error codes (TYPE_RESOLUTION_ERROR, UNKNOWN_TYPE, etc.)
3. Constraint depth enforcement with max_constraint_depth parameter
4. Recursive type handling with handle_recursive_types parameter
5. Generic instantiation tracking with track_instantiations parameter
6. Complex generic method resolution with resolve_class_methods parameter
7. Type inference with imports using resolve_imports parameter
8. Type guard inference with analyze_type_guards parameter
9. Conditional type inference with resolve_conditional_types parameter
10. Deep generic constraint resolution (5+ levels)
11. Complex nested type definitions with proper tracking
12. Performance under complexity with proper error categorization

All tests should FAIL initially (RED phase) to drive proper TDD implementation.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the expected implementations (will fail initially)
try:
    from aromcp.analysis_server.tools.get_function_details import get_function_details_impl
    from aromcp.analysis_server.models.typescript_models import (
        FunctionDetailsResponse,
        FunctionDetail,
        TypeDefinition,
        ParameterType,
        AnalysisError,
        TypeResolutionMetadata,
        TypeInstantiation,
        ImportTypeInfo,
        TypeGuardInfo,
        GenericConstraintInfo,
    )
except ImportError:
    # Expected to fail initially - create placeholder functions for testing
    def get_function_details_impl(*args, **kwargs):
        raise NotImplementedError("Tool not yet implemented")
    
    class FunctionDetailsResponse:
        pass
    
    class FunctionDetail:
        pass
    
    class TypeDefinition:
        pass
    
    class ParameterType:
        pass
    
    class AnalysisError:
        pass
    
    class TypeResolutionMetadata:
        pass
    
    class TypeInstantiation:
        pass
    
    class ImportTypeInfo:
        pass
    
    class TypeGuardInfo:
        pass
    
    class GenericConstraintInfo:
        pass


class TestAdvancedTypeResolutionFailures:
    """Test class for the 12 specific failing advanced type resolution scenarios."""

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

    def test_resolution_depth_content_differences(self, temp_project):
        """Test that different resolution depths provide progressively more detail."""
        test_file = temp_project / "complex_generics.ts"
        test_file.write_text("""
        interface BaseEntity { id: string; createdAt: Date; }
        
        interface ComplexGeneric<T extends BaseEntity, K extends keyof T> {
            process<U extends T[K]>(key: K, value: U): Promise<T & { [P in K]: U }>;
        }
        
        function processComplex<T extends BaseEntity>(
            data: ComplexGeneric<T, keyof T>
        ): Promise<T> {
            return Promise.resolve({} as T);
        }
        """)
        
        # Get results at different resolution levels
        basic_result = get_function_details_impl(
            functions="processComplex",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="basic"
        )
        
        generic_result = get_function_details_impl(
            functions="processComplex",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        full_result = get_function_details_impl(
            functions="processComplex", 
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="full_inference",
            fallback_on_complexity=True  # This parameter is NOT IMPLEMENTED
        )
        
        # All should succeed
        for result in [basic_result, generic_result, full_result]:
            assert isinstance(result, FunctionDetailsResponse)
            assert result.success is True
            assert "processComplex" in result.functions
            
        # Progressive depth should provide more type information
        basic_func = basic_result.functions["processComplex"][0]
        generic_func = generic_result.functions["processComplex"][0]
        full_func = full_result.functions["processComplex"][0]
        
        basic_type_count = len(basic_func.types) if basic_func.types else 0
        generic_type_count = len(generic_func.types) if generic_func.types else 0
        full_type_count = len(full_func.types) if full_func.types else 0
        
        # THIS WILL FAIL: Progressive depth should provide more type information
        assert generic_type_count >= basic_type_count, "Generic should have >= type info than basic"
        assert full_type_count >= generic_type_count, "Full should have >= type info than generic"
        
        # THIS WILL FAIL: Should include resolution_metadata about fallback usage
        assert hasattr(full_result, 'resolution_metadata')
        assert full_result.resolution_metadata is not None
        assert isinstance(full_result.resolution_metadata, TypeResolutionMetadata)
        assert hasattr(full_result.resolution_metadata, 'fallbacks_used')

    def test_type_resolution_error_handling(self, temp_project):
        """Test error handling in type resolution system with specific error codes."""
        invalid_file = temp_project / "type_errors.ts"
        invalid_file.write_text("""
        function invalidConstraint<T extends NonExistentInterface>(param: T): T {
            return param;
        }
        
        function circularReference<T extends CircularType<T>>(param: T): T {
            return param;
        }
        
        interface CircularType<T extends CircularType<T>> {
            value: T;
        }
        
        function unknownType(): UnknownType {
            return {} as UnknownType;
        }
        """)
        
        result = get_function_details_impl(
            functions=["invalidConstraint", "circularReference", "unknownType"],
            file_paths=str(invalid_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        
        # THIS WILL FAIL: Should have specific error codes for different error types
        # Accept the actual error codes generated by the implementation
        assert len(result.errors) > 0
        error_codes = {error.code for error in result.errors}
        expected_codes = {"TYPE_RESOLUTION_ERROR", "UNKNOWN_TYPE", "CIRCULAR_CONSTRAINT", "CONSTRAINT_DEPTH_EXCEEDED"}
        assert any(code in expected_codes for code in error_codes), f"Expected error codes {expected_codes}, got {error_codes}"
        
        # THIS WILL FAIL: Should categorize errors properly
        for error in result.errors:
            assert isinstance(error, AnalysisError)
            assert error.code is not None
            assert error.message is not None
            assert error.file == str(invalid_file)

    def test_type_resolution_depth_fallback(self, temp_project):
        """Test that resolution gracefully falls back when depth limits exceeded."""
        deep_file = temp_project / "deep_constraints.ts"
        deep_file.write_text("""
        interface L1 { id: string; }
        interface L2<T extends L1> { data: T; }
        interface L3<T extends L1, U extends L2<T>> { nested: U; }
        interface L4<T extends L1, U extends L2<T>, V extends L3<T, U>> { deep: V; }
        interface L5<T extends L1, U extends L2<T>, V extends L3<T, U>, W extends L4<T, U, V>> { veryDeep: W; }
        interface L6<T extends L1, U extends L2<T>, V extends L3<T, U>, W extends L4<T, U, V>, X extends L5<T, U, V, W>> { extremelyDeep: X; }
        
        function processDeepConstraints<
            T extends L1,
            U extends L2<T>,
            V extends L3<T, U>,
            W extends L4<T, U, V>,
            X extends L5<T, U, V, W>,
            Y extends L6<T, U, V, W, X>
        >(input: Y): T {
            return input.extremelyDeep.veryDeep.deep.nested.data;
        }
        """)
        
        result = get_function_details_impl(
            functions="processDeepConstraints",
            file_paths=str(deep_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=3  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # THIS WILL FAIL: Should have warning about exceeded depth limit
        depth_errors = [e for e in result.errors if "constraint depth" in e.message.lower()]
        assert len(depth_errors) > 0, "Expected constraint depth limit warning"
        assert any(e.code == "CONSTRAINT_DEPTH_EXCEEDED" for e in depth_errors), "Expected CONSTRAINT_DEPTH_EXCEEDED error code"

    def test_nested_type_resolution(self, temp_project):
        """Test resolution of deeply nested and complex type definitions."""
        nested_file = temp_project / "complex_nested.ts"
        nested_file.write_text("""
        type DeepPartial<T> = {
            [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
        };
        
        type KeysOfType<T, U> = {
            [K in keyof T]: T[K] extends U ? K : never;
        }[keyof T];
        
        interface ComplexNested {
            user: {
                profile: {
                    settings: {
                        notifications: {
                            email: boolean;
                            push: boolean;
                            sms?: boolean;
                        };
                        privacy: {
                            public: boolean;
                            friends: boolean;
                        };
                    };
                };
            };
        }
        
        function updateNestedSettings<T extends ComplexNested>(
            data: T,
            updates: DeepPartial<T['user']['profile']['settings']>,
            keys: KeysOfType<T['user']['profile']['settings'], boolean>
        ): T {
            return data;
        }
        """)
        
        result = get_function_details_impl(
            functions="updateNestedSettings",
            file_paths=str(nested_file),
            include_types=True,
            resolution_depth="full_inference",
            handle_recursive_types=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        update_settings_list = result.functions["updateNestedSettings"]
        assert update_settings_list is not None
        assert isinstance(update_settings_list, list)
        assert len(update_settings_list) >= 1

        
        update_settings = update_settings_list[0]
        assert update_settings is not None
        
        # THIS WILL FAIL: Should resolve deeply nested type access
        assert "T['user']['profile']['settings']" in update_settings.signature
        assert "DeepPartial<T['user']['profile']['settings']>" in update_settings.signature
        assert "KeysOfType<T['user']['profile']['settings'], boolean>" in update_settings.signature
        
        # THIS WILL FAIL: Should include all complex type definitions
        assert update_settings.types is not None
        assert "DeepPartial" in update_settings.types
        assert "KeysOfType" in update_settings.types
        assert "ComplexNested" in update_settings.types

    def test_generic_constraint_resolution_depth_5_levels(self, temp_project):
        """Test 5+ level generic constraint resolution with proper depth tracking."""
        deep_file = temp_project / "deep_generics_5_levels.ts"
        deep_file.write_text("""
        interface Level1 { id: string; }
        interface Level2<T extends Level1> { data: T; metadata: string; }
        interface Level3<T extends Level1, U extends Level2<T>> { nested: U; additional: T[]; }
        interface Level4<T extends Level1, U extends Level2<T>, V extends Level3<T, U>> { deep: V; cache: Map<string, T>; }
        interface Level5<T extends Level1, U extends Level2<T>, V extends Level3<T, U>, W extends Level4<T, U, V>> { veryDeep: W; transform: (input: T) => U; }
        
        function processDeepGeneric<
            T extends Level1,
            U extends Level2<T>,
            V extends Level3<T, U>,
            W extends Level4<T, U, V>,
            X extends Level5<T, U, V, W>
        >(input: X): Promise<T> {
            return Promise.resolve(input.veryDeep.deep.nested.data);
        }
        """)
        
        result = get_function_details_impl(
            functions="processDeepGeneric",
            file_paths=str(deep_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=5  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        process_deep_list = result.functions["processDeepGeneric"]
        assert process_deep_list is not None
        assert isinstance(process_deep_list, list)
        assert len(process_deep_list) >= 1

        
        process_deep = process_deep_list[0]
        assert process_deep is not None
        
        # THIS WILL FAIL: Should handle all 5 levels of generic constraints
        assert "T extends Level1" in process_deep.signature
        assert "U extends Level2<T>" in process_deep.signature
        assert "V extends Level3<T, U>" in process_deep.signature
        assert "W extends Level4<T, U, V>" in process_deep.signature
        assert "X extends Level5<T, U, V, W>" in process_deep.signature
        
        # THIS WILL FAIL: Should track constraint depth in metadata
        assert hasattr(result, 'resolution_metadata')
        assert result.resolution_metadata is not None
        assert hasattr(result.resolution_metadata, 'max_constraint_depth_reached')
        assert result.resolution_metadata.max_constraint_depth_reached == 5

    def test_generic_constraint_depth_limit_exceeded(self, temp_project):
        """Test behavior when generic constraint depth exceeds limit."""
        excessive_file = temp_project / "excessive_generics.ts"
        excessive_file.write_text("""
        interface A<T> { a: T; }
        interface B<T> extends A<T> { b: T; }
        interface C<T> extends B<T> { c: T; }
        interface D<T> extends C<T> { d: T; }
        interface E<T> extends D<T> { e: T; }
        interface F<T> extends E<T> { f: T; }
        interface G<T> extends F<T> { g: T; }
        interface H<T> extends G<T> { h: T; }
        interface I<T> extends H<T> { i: T; }
        interface J<T> extends I<T> { j: T; }
        
        function excessivelyDeep<T extends J<string>>(input: T): T {
            return input;
        }
        """)
        
        result = get_function_details_impl(
            functions="excessivelyDeep",
            file_paths=str(excessive_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=5  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # THIS WILL FAIL: Should include warning about depth limit
        assert len(result.errors) > 0
        depth_warning = None
        for error in result.errors:
            if "constraint depth limit" in error.message.lower():
                depth_warning = error
                break
        
        assert depth_warning is not None, "Expected depth limit warning"
        assert depth_warning.code == "CONSTRAINT_DEPTH_EXCEEDED"

    def test_generic_instantiation_tracking(self, temp_project):
        """Test tracking of generic type instantiations."""
        instantiation_file = temp_project / "generic_instantiations.ts"
        instantiation_file.write_text("""
        interface Repository<T> {
            save(entity: T): Promise<T>;
            findById(id: string): Promise<T | null>;
        }
        
        interface User { id: string; name: string; }
        interface Product { id: string; price: number; }
        
        function setupRepositories(): {
            userRepo: Repository<User>;
            productRepo: Repository<Product>;
            stringRepo: Repository<string>;
            numberRepo: Repository<number>;
        } {
            return {} as any;
        }
        """)
        
        result = get_function_details_impl(
            functions="setupRepositories",
            file_paths=str(instantiation_file),
            include_types=True,
            resolution_depth="generics",
            track_instantiations=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # THIS WILL FAIL: Should track different instantiations of Repository<T>
        assert hasattr(result, 'type_instantiations')
        assert result.type_instantiations is not None
        assert isinstance(result.type_instantiations, dict)
        
        repo_instantiations = result.type_instantiations.get("Repository", [])
        assert len(repo_instantiations) >= 4  # User, Product, string, number
        
        # Check specific instantiations
        instantiation_types = [
            inst.type_args[0] if hasattr(inst, 'type_args') else inst['type_args'][0] 
            for inst in repo_instantiations 
            if hasattr(inst, 'type_args') or 'type_args' in inst
        ]
        assert "User" in instantiation_types
        assert "Product" in instantiation_types
        assert "string" in instantiation_types
        assert "number" in instantiation_types

    def test_complex_generic_method_resolution(self, temp_project):
        """Test resolve_class_methods parameter for complex generic class methods.""" 
        method_file = temp_project / "complex_methods.ts"
        method_file.write_text("""
        class GenericProcessor<T extends Record<string, any>> {
            async process<U extends T, K extends keyof U>(
                data: U,
                selector: K
            ): Promise<U[K]> {
                return data[selector];
            }
            
            transform<V, K extends keyof T>(
                key: K,
                transformer: (value: T[K]) => V
            ): Promise<T & { [P in K]: V }> {
                return {} as any;
            }
            
            batch<U extends T[]>(
                items: U,
                processor: <V extends T>(item: V) => Promise<V>
            ): Promise<U> {
                return items as U;
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=["GenericProcessor.process", "GenericProcessor.transform", "GenericProcessor.batch"],
            file_paths=str(method_file),
            include_types=True,
            resolution_depth="generics",
            resolve_class_methods=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # THIS WILL FAIL: Should resolve all three methods
        assert "GenericProcessor.process" in result.functions
        assert "GenericProcessor.transform" in result.functions
        assert "GenericProcessor.batch" in result.functions
        
        # Check method-specific generic constraints
        process_method_list = result.functions["GenericProcessor.process"]
        assert process_method_list is not None
        assert isinstance(process_method_list, list)
        assert len(process_method_list) >= 1

        process_method = process_method_list[0]
        assert "U extends T" in process_method.signature
        assert "K extends keyof U" in process_method.signature

    def test_inference_accuracy_with_imported_types(self, temp_project):
        """Test type inference accuracy with cross-file type imports."""
        # Create base types file
        base_file = temp_project / "base.ts"
        base_file.write_text("""
        export interface BaseEntity {
            id: string;
            createdAt: Date;
        }
        
        export type EntityProcessor<T extends BaseEntity> = (entity: T) => Promise<T>;
        """)
        
        # Create processor file that imports and uses base types
        processor_file = temp_project / "processor.ts"
        processor_file.write_text("""
        import { BaseEntity, EntityProcessor } from './base';
        
        export interface User extends BaseEntity {
            name: string;
            email: string;
        }
        
        export function createUserProcessor(): EntityProcessor<User> {
            return async (user: User) => {
                return { ...user, createdAt: new Date() };
            };
        }
        """)
        
        result = get_function_details_impl(
            functions="createUserProcessor",
            file_paths=[str(base_file), str(processor_file)],
            include_types=True,
            resolution_depth="full_inference",
            resolve_imports=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        processor_func_list = result.functions["createUserProcessor"]
        assert processor_func_list is not None
        assert isinstance(processor_func_list, list)
        assert len(processor_func_list) >= 1

        
        processor_func = processor_func_list[0]
        assert processor_func is not None
        
        # THIS WILL FAIL: Should resolve imported types correctly
        assert processor_func.types is not None
        assert "BaseEntity" in processor_func.types
        assert "User" in processor_func.types
        assert "EntityProcessor" in processor_func.types
        
        # THIS WILL FAIL: Should track import graph
        assert hasattr(result, 'import_graph')
        assert result.import_graph is not None

    def test_inference_with_type_guards(self, temp_project):
        """Test type inference accuracy with TypeScript type guard functions."""
        guard_file = temp_project / "type_guards.ts"
        guard_file.write_text("""
        interface User { type: 'user'; name: string; email: string; }
        interface Admin { type: 'admin'; name: string; permissions: string[]; }
        
        type Person = User | Admin;
        
        function isUser(person: Person): person is User {
            return person.type === 'user';
        }
        
        function isAdmin(person: Person): person is Admin {
            return person.type === 'admin';
        }
        
        function processPersonSafely(person: Person): string {
            if (isUser(person)) {
                return person.email;  // person is now typed as User
            } else if (isAdmin(person)) {
                return person.permissions.join(', ');  // person is now typed as Admin
            }
            return 'Unknown';
        }
        """)
        
        result = get_function_details_impl(
            functions=["isUser", "isAdmin", "processPersonSafely"],
            file_paths=str(guard_file),
            include_types=True,
            resolution_depth="full_inference",
            analyze_type_guards=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # THIS WILL FAIL: Should identify type guard functions
        is_user_list = result.functions["isUser"]
        assert is_user_list is not None
        assert isinstance(is_user_list, list)
        assert len(is_user_list) >= 1

        is_user = is_user_list[0]
        assert is_user is not None
        assert "person is User" in is_user.signature
        
        # THIS WILL FAIL: Should include type guard information
        assert hasattr(is_user, 'type_guard_info')
        assert is_user.type_guard_info is not None
        assert isinstance(is_user.type_guard_info, TypeGuardInfo)
        assert is_user.type_guard_info.is_type_guard is True
        assert is_user.type_guard_info.narrows_to == 'User'
        assert is_user.type_guard_info.from_type == 'Person'

    def test_inference_with_conditional_types_and_infer(self, temp_project):
        """Test complex conditional types with infer keyword."""
        conditional_file = temp_project / "conditional_types.ts"
        conditional_file.write_text("""
        type ApiResponse<T> = T extends string 
            ? { message: T; status: 'success' }
            : T extends number
            ? { code: T; status: 'error' }
            : { data: T; status: 'unknown' };
        
        type ExtractPromiseType<T> = T extends Promise<infer U> ? U : T;
        
        type ReturnTypeExtractor<T> = T extends (...args: any[]) => infer R ? R : never;
        
        function processApiData<T>(
            input: T
        ): Promise<ApiResponse<ExtractPromiseType<T>>> {
            return Promise.resolve({} as ApiResponse<ExtractPromiseType<T>>);
        }
        
        function extractReturnType<T extends (...args: any[]) => any>(
            fn: T
        ): ReturnTypeExtractor<T> {
            return {} as ReturnTypeExtractor<T>;
        }
        """)
        
        result = get_function_details_impl(
            functions=["processApiData", "extractReturnType"],
            file_paths=str(conditional_file),
            include_types=True,
            resolution_depth="full_inference",
            resolve_conditional_types=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        process_data_list = result.functions["processApiData"]
        assert process_data_list is not None
        assert isinstance(process_data_list, list)
        assert len(process_data_list) >= 1

        
        process_data = process_data_list[0]
        assert process_data is not None
        
        # THIS WILL FAIL: Should resolve complex conditional return type
        assert "ApiResponse<ExtractPromiseType<T>>" in process_data.signature
        
        # THIS WILL FAIL: Should include conditional type definitions
        assert process_data.types is not None
        assert "ApiResponse" in process_data.types
        assert "ExtractPromiseType" in process_data.types
        
        extract_return_list = result.functions["extractReturnType"]
        assert extract_return_list is not None
        assert isinstance(extract_return_list, list)
        assert len(extract_return_list) >= 1

        
        extract_return = extract_return_list[0]
        assert extract_return is not None
        assert "ReturnTypeExtractor<T>" in extract_return.signature

    def test_inference_accuracy_with_recursive_types(self, temp_project):
        """Test type inference with recursive type definitions."""
        recursive_file = temp_project / "recursive_types.ts"
        recursive_file.write_text("""
        interface TreeNode<T> {
            value: T;
            children: TreeNode<T>[];
            parent?: TreeNode<T>;
        }
        
        type DeepReadonly<T> = {
            readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
        };
        
        type LinkedList<T> = {
            value: T;
            next: LinkedList<T> | null;
        };
        
        function traverseTree<T>(
            node: TreeNode<T>,
            visitor: (value: T, depth: number) => void,
            depth: number = 0
        ): void {
            visitor(node.value, depth);
            
            for (const child of node.children) {
                traverseTree(child, visitor, depth + 1);
            }
        }
        
        function makeDeepReadonly<T>(obj: T): DeepReadonly<T> {
            return obj as DeepReadonly<T>;
        }
        
        function processLinkedList<T>(
            list: LinkedList<T>,
            processor: (value: T) => T
        ): LinkedList<T> {
            return {
                value: processor(list.value),
                next: list.next ? processLinkedList(list.next, processor) : null
            };
        }
        """)
        
        result = get_function_details_impl(
            functions=["traverseTree", "makeDeepReadonly", "processLinkedList"],
            file_paths=str(recursive_file),
            include_types=True,
            resolution_depth="full_inference",
            handle_recursive_types=True  # This parameter is NOT IMPLEMENTED
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # THIS WILL FAIL: Should handle recursive TreeNode type
        traverse_tree_list = result.functions["traverseTree"]
        assert traverse_tree_list is not None
        assert isinstance(traverse_tree_list, list)
        assert len(traverse_tree_list) >= 1

        traverse_tree = traverse_tree_list[0]
        assert traverse_tree is not None
        assert "TreeNode<T>" in traverse_tree.signature
        
        # THIS WILL FAIL: Should resolve recursive mapped type
        make_readonly_list = result.functions["makeDeepReadonly"]
        assert make_readonly_list is not None
        assert isinstance(make_readonly_list, list)
        assert len(make_readonly_list) >= 1

        make_readonly = make_readonly_list[0]
        assert make_readonly is not None
        assert "DeepReadonly<T>" in make_readonly.signature
        
        # THIS WILL FAIL: Should handle recursive LinkedList type
        process_list_list = result.functions["processLinkedList"]
        assert process_list_list is not None
        assert isinstance(process_list_list, list)
        assert len(process_list_list) >= 1

        process_list = process_list_list[0]
        assert process_list is not None
        assert "LinkedList<T>" in process_list.signature
        
        # THIS WILL FAIL: Should include recursive type information
        assert traverse_tree.types is not None
        assert "TreeNode" in traverse_tree.types
        tree_type = traverse_tree.types["TreeNode"]
        assert "children: TreeNode<T>[]" in tree_type.definition