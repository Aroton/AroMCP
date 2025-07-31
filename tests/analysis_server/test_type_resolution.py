"""
Tests for Phase 3 TypeScript type resolution functionality.

These tests define the expected behavior for the progressive type resolution system:
- Basic Resolution: Explicitly declared types only
- Generic Resolution: Generic constraints and instantiations  
- Full Inference: Deep type analysis with TypeScript compiler integration

All tests should initially FAIL (RED phase) to drive TDD implementation.
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


class TestProgressiveTypeResolution:
    """Test the 3-tier progressive type resolution system."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with Phase 3 test files."""
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

    @pytest.fixture
    def basic_types_file(self, temp_project):
        """Copy basic-types.ts fixture to temp project."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "basic-types.ts"
        target_file = temp_project / "basic-types.ts"
        target_file.write_text(source_file.read_text())
        return str(target_file)

    @pytest.fixture
    def generic_functions_file(self, temp_project):
        """Copy generic-functions.ts fixture to temp project."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "generic-functions.ts"
        target_file = temp_project / "generic-functions.ts"
        target_file.write_text(source_file.read_text())
        return str(target_file)

    @pytest.fixture
    def complex_types_file(self, temp_project):
        """Copy complex-types.ts fixture to temp project."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "complex-types.ts"
        target_file = temp_project / "complex-types.ts"
        target_file.write_text(source_file.read_text())
        return str(target_file)

    def test_basic_type_resolution_level_1(self, basic_types_file):
        """Test Level 1: Basic resolution with explicitly declared types only."""
        result = get_function_details_impl(
            functions=["createUser", "updateUserEmail", "isUserActive"],
            file_paths=basic_types_file,
            include_code=False,
            include_types=True,
            include_calls=False,
            resolution_depth="basic"  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        assert len(result.functions) == 3
        
        # Test createUser function
        create_user_list = result.functions.get("createUser")

        create_user = create_user_list[0] if create_user_list else None
        assert create_user is not None
        assert isinstance(create_user, FunctionDetail)
        
        # Should resolve basic parameter types
        assert "name: string" in create_user.signature
        assert "email: string" in create_user.signature
        assert "): User" in create_user.signature
        
        # Should include type definitions for User interface
        assert create_user.types is not None
        assert "User" in create_user.types
        
        user_type = create_user.types["User"]
        assert isinstance(user_type, TypeDefinition)
        assert user_type.kind == "interface"
        assert "id: number" in user_type.definition
        assert "name: string" in user_type.definition
        assert "email: string" in user_type.definition
        assert "isActive: boolean" in user_type.definition
        
        # Test updateUserEmail function
        update_email_list = result.functions.get("updateUserEmail")

        update_email = update_email_list[0] if update_email_list else None
        assert update_email is not None
        assert "user: User" in update_email.signature
        assert "newEmail: string" in update_email.signature
        
        # Test isUserActive function  
        is_active_list = result.functions.get("isUserActive")
  
        is_active = is_active_list[0] if is_active_list else None
        assert is_active is not None
        assert "user: User" in is_active.signature
        assert "): boolean" in is_active.signature

    def test_basic_type_resolution_with_optional_parameters(self, basic_types_file):
        """Test basic resolution handles optional and default parameters."""
        result = get_function_details_impl(
            functions=["getUserProfile", "createApiResponse"],
            file_paths=basic_types_file,
            include_types=True,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test optional parameters
        get_profile_list = result.functions.get("getUserProfile")

        get_profile = get_profile_list[0] if get_profile_list else None
        assert get_profile is not None
        assert "id: number" in get_profile.signature
        assert "includeInactive?: boolean" in get_profile.signature
        assert "format?: 'json' | 'xml'" in get_profile.signature
        assert "): User | null" in get_profile.signature
        
        # Test default parameters
        create_response_list = result.functions.get("createApiResponse")

        create_response = create_response_list[0] if create_response_list else None
        assert create_response is not None
        assert "success: boolean = true" in create_response.signature
        assert "message: string = 'Success'" in create_response.signature
        assert "timestamp: Date = new Date()" in create_response.signature

    def test_basic_type_resolution_with_union_and_array_types(self, basic_types_file):
        """Test basic resolution handles union types and arrays."""
        result = get_function_details_impl(
            functions=["processUserInput", "getActiveUsers", "getUserIds"],
            file_paths=basic_types_file,
            include_types=True,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test union types
        process_input_list = result.functions.get("processUserInput")

        process_input = process_input_list[0] if process_input_list else None
        assert process_input is not None
        assert "input: string | number | boolean" in process_input.signature
        assert "): string" in process_input.signature
        
        # Test array types
        get_active_list = result.functions.get("getActiveUsers")

        get_active = get_active_list[0] if get_active_list else None
        assert get_active is not None
        assert "users: User[]" in get_active.signature
        assert "): User[]" in get_active.signature
        
        get_ids_list = result.functions.get("getUserIds")

        
        get_ids = get_ids_list[0] if get_ids_list else None
        assert get_ids is not None
        assert "users: User[]" in get_ids.signature
        assert "): number[]" in get_ids.signature

    def test_generic_type_resolution_level_2(self, generic_functions_file):
        """Test Level 2: Generic resolution with constraints and instantiations."""
        result = get_function_details_impl(
            functions=["processEntity", "mergeEntities", "validateAndProcess"],
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="generics"  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        assert len(result.functions) == 3
        
        # Test basic generic function
        process_entity_list = result.functions.get("processEntity")

        process_entity = process_entity_list[0] if process_entity_list else None
        assert process_entity is not None
        assert "<T extends BaseEntity>" in process_entity.signature
        assert "entity: T" in process_entity.signature
        assert "): Promise<T>" in process_entity.signature
        
        # Should resolve BaseEntity constraint
        assert process_entity.types is not None
        assert "BaseEntity" in process_entity.types
        base_entity_type = process_entity.types["BaseEntity"]
        assert base_entity_type.kind == "interface"
        assert "id: string" in base_entity_type.definition
        assert "createdAt: Date" in base_entity_type.definition
        
        # Test multiple generic constraints
        merge_entities_list = result.functions.get("mergeEntities")

        merge_entities = merge_entities_list[0] if merge_entities_list else None
        assert merge_entities is not None
        assert "<T extends BaseEntity, U extends Partial<T>>" in merge_entities.signature
        assert "base: T" in merge_entities.signature
        assert "updates: U" in merge_entities.signature
        assert "): T & U" in merge_entities.signature
        
        # Should resolve Partial<T> utility type
        assert "Partial" in merge_entities.types
        
        # Test complex generic constraints
        validate_process_list = result.functions.get("validateAndProcess")

        validate_process = validate_process_list[0] if validate_process_list else None
        assert validate_process is not None
        assert "T extends BaseEntity" in validate_process.signature
        assert "K extends keyof T" in validate_process.signature
        assert "V extends T[K]" in validate_process.signature

    def test_generic_type_resolution_with_conditional_types(self, generic_functions_file):
        """Test generic resolution handles conditional types."""
        result = get_function_details_impl(
            functions=["formatValue"],
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        format_value_list = result.functions.get("formatValue")

        
        format_value = format_value_list[0] if format_value_list else None
        assert format_value is not None
        
        # Should resolve conditional return type
        assert "T extends string ? string : T extends number ? string : never" in format_value.signature
        
        # Should include conditional type information
        assert format_value.types is not None
        # Conditional types should be tracked as complex type constructs

    def test_generic_type_resolution_with_utility_types(self, generic_functions_file):
        """Test generic resolution handles TypeScript utility types."""
        result = get_function_details_impl(
            functions=["makePartial", "pickFields", "omitFields"],
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test Partial<T>
        make_partial_list = result.functions.get("makePartial")

        make_partial = make_partial_list[0] if make_partial_list else None
        assert make_partial is not None
        assert "): Partial<T>" in make_partial.signature
        assert "Partial" in make_partial.types
        
        # Test Pick<T, K>
        pick_fields_list = result.functions.get("pickFields")

        pick_fields = pick_fields_list[0] if pick_fields_list else None
        assert pick_fields is not None
        assert "keys: K[]" in pick_fields.signature
        assert "): Pick<T, K>" in pick_fields.signature
        assert "Pick" in pick_fields.types
        
        # Test Omit<T, K>
        omit_fields_list = result.functions.get("omitFields")

        omit_fields = omit_fields_list[0] if omit_fields_list else None
        assert omit_fields is not None
        assert "): Omit<T, K>" in omit_fields.signature
        assert "Omit" in omit_fields.types

    def test_full_type_inference_level_3(self, complex_types_file):
        """Test Level 3: Full inference with deep type analysis."""
        result = get_function_details_impl(
            functions=["processData", "createValidator", "transformObject"],
            file_paths=complex_types_file,
            include_types=True,
            resolution_depth="full_inference"  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test complex conditional types with inference
        process_data_list = result.functions.get("processData")

        process_data = process_data_list[0] if process_data_list else None
        assert process_data is not None
        
        # Should infer complex conditional return type
        conditional_return = (
            "T extends string ? { text: string; length: number } : "
            "T extends number ? { value: number; formatted: string } : "
            "T extends boolean ? { flag: boolean; display: 'Yes' | 'No' } : "
            "{ raw: T; type: string }"
        )
        assert conditional_return in process_data.signature
        
        # Test complex generic function with inferred constraints
        create_validator_list = result.functions.get("createValidator")

        create_validator = create_validator_list[0] if create_validator_list else None
        assert create_validator is not None
        assert "T extends Record<string, any>" in create_validator.signature
        
        # Should infer mapped type for schema parameter
        assert "{ [K in keyof T]: (value: unknown) => value is T[K] }" in create_validator.signature
        
        # Test complex mapped type transformations
        transform_object_list = result.functions.get("transformObject")

        transform_object = transform_object_list[0] if transform_object_list else None
        assert transform_object is not None
        assert "K extends keyof T" in transform_object.signature
        
        # Should infer complex mapped return type
        mapped_return = "{ [P in keyof T]: P extends K ? U : T[P] }"
        assert mapped_return in transform_object.signature

    def test_full_type_inference_with_template_literals(self, complex_types_file):
        """Test full inference handles template literal types."""
        result = get_function_details_impl(
            functions=["createEventHandler"],
            file_paths=complex_types_file,
            include_types=True,
            resolution_depth="full_inference"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        create_handler_list = result.functions.get("createEventHandler")

        
        create_handler = create_handler_list[0] if create_handler_list else None
        assert create_handler is not None
        
        # Should resolve template literal type
        assert "EventName<T>" in create_handler.signature
        
        # Should include template literal type definition
        assert create_handler.types is not None
        assert "EventName" in create_handler.types
        
        event_name_type = create_handler.types["EventName"]
        assert "`on${Capitalize<T>}`" in event_name_type.definition

    def test_progressive_resolution_performance_comparison(self, generic_functions_file):
        """Test that progressive resolution levels have appropriate performance characteristics."""
        functions_to_test = [
            "processEntity", "mergeEntities", "validateAndProcess",
            "formatValue", "makePartial", "pickFields"
        ]
        
        # Test basic resolution (should be fastest)
        start_time = time.perf_counter()
        basic_result = get_function_details_impl(
            functions=functions_to_test,
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="basic"
        )
        basic_time = time.perf_counter() - start_time
        
        # Test generic resolution (should be slower than basic)
        start_time = time.perf_counter()
        generic_result = get_function_details_impl(
            functions=functions_to_test,
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="generics"
        )
        generic_time = time.perf_counter() - start_time
        
        # Test full inference (should be slowest)
        start_time = time.perf_counter()
        full_result = get_function_details_impl(
            functions=functions_to_test,
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="full_inference"
        )
        full_time = time.perf_counter() - start_time
        
        # Performance requirements
        assert basic_time < 1.0, f"Basic resolution took {basic_time:.2f}s, should be <1s"
        assert generic_time < 3.0, f"Generic resolution took {generic_time:.2f}s, should be <3s"
        assert full_time < 10.0, f"Full inference took {full_time:.2f}s, should be <10s"
        
        # Progressive complexity should show in timing
        # Note: In initial implementation this may not hold, but it's the target
        assert basic_time <= generic_time, "Basic should be fastest or equal to generic"
        
        # All should return valid results
        for result in [basic_result, generic_result, full_result]:
            assert isinstance(result, FunctionDetailsResponse)
            assert result.success is True
            assert len(result.functions) == len(functions_to_test)

    def test_resolution_depth_content_differences(self, generic_functions_file):
        """Test that different resolution depths provide progressively more detail."""
        test_function = "mergeEntities"
        
        # Get results at different resolution levels
        basic_result = get_function_details_impl(
            functions=test_function,
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="basic"
        )
        
        generic_result = get_function_details_impl(
            functions=test_function,
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="generics"
        )
        
        full_result = get_function_details_impl(
            functions=test_function,
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="full_inference"
        )
        
        # All should succeed
        for result in [basic_result, generic_result, full_result]:
            assert isinstance(result, FunctionDetailsResponse)
            assert result.success is True
            assert test_function in result.functions
        
        basic_func = basic_result.functions[test_function][0]
        generic_func = generic_result.functions[test_function][0]
        full_func = full_result.functions[test_function][0]
        
        # Basic should have least type information
        basic_type_count = len(basic_func.types) if basic_func.types else 0
        generic_type_count = len(generic_func.types) if generic_func.types else 0
        full_type_count = len(full_func.types) if full_func.types else 0
        
        # Progressive depth should provide more type information
        assert generic_type_count >= basic_type_count, "Generic should have >= type info than basic"
        assert full_type_count >= generic_type_count, "Full should have >= type info than generic"
        
        # Generic resolution should include constraint information
        assert generic_func.types is not None
        assert "BaseEntity" in generic_func.types
        
        # Full inference should include the most comprehensive type analysis
        assert full_func.types is not None
        # Should have resolved intersection types, utility types, etc.

    def test_type_resolution_error_handling(self, temp_project):
        """Test error handling in type resolution system."""
        # Create file with invalid TypeScript
        invalid_file = temp_project / "invalid.ts"
        invalid_file.write_text("""
        function invalidFunction<T extends NonExistentType>(param: T): T {
            return param;
        }
        
        function anotherFunction(): UnknownType {
            return {} as UnknownType;
        }
        """)
        
        result = get_function_details_impl(
            functions=["invalidFunction", "anotherFunction"],
            file_paths=str(invalid_file),
            include_types=True,
            resolution_depth="full_inference"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        
        # Should handle errors gracefully
        assert len(result.errors) > 0
        
        for error in result.errors:
            assert isinstance(error, AnalysisError)
            assert error.code in ["TYPE_RESOLUTION_ERROR", "UNKNOWN_TYPE", "PARSE_ERROR", "CONSTRAINT_DEPTH_EXCEEDED"]
            assert error.message is not None
            assert error.file == str(invalid_file)

    def test_type_resolution_depth_fallback(self, generic_functions_file):
        """Test that resolution gracefully falls back on complex types."""
        result = get_function_details_impl(
            functions=["processEntity"],
            file_paths=generic_functions_file,
            include_types=True,
            resolution_depth="basic",  # Request basic but function has generics
            fallback_on_complexity=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        process_entity_list = result.functions.get("processEntity")

        
        process_entity = process_entity_list[0] if process_entity_list else None
        assert process_entity is not None
        
        # Should include metadata about fallback
        assert hasattr(result, 'resolution_metadata')
        assert result.resolution_metadata is not None
        assert hasattr(result.resolution_metadata, 'fallbacks_used')
        assert result.resolution_metadata.fallbacks_used > 0


class TestTypeDefinitionExtraction:
    """Test extraction and resolution of type definitions."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with Phase 3 test files."""
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

    def test_interface_definition_extraction(self, temp_project):
        """Test extraction of interface definitions."""
        test_file = temp_project / "interfaces.ts"
        test_file.write_text("""
        interface User {
            id: number;
            name: string;
            email: string;
            profile?: {
                avatar: string;
                bio?: string;
            };
        }
        
        function createUser(data: User): User {
            return data;
        }
        """)
        
        result = get_function_details_impl(
            functions="createUser",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        create_user_list = result.functions["createUser"]
        assert create_user_list is not None
        assert isinstance(create_user_list, list)
        assert len(create_user_list) >= 1

        
        create_user = create_user_list[0]
        assert create_user.types is not None
        assert "User" in create_user.types
        
        user_type = create_user.types["User"]
        assert isinstance(user_type, TypeDefinition)
        assert user_type.kind == "interface"
        assert "id: number" in user_type.definition
        assert "profile?: {" in user_type.definition
        assert user_type.location.endswith("interfaces.ts:2")  # Line where interface starts

    def test_type_alias_definition_extraction(self, temp_project):
        """Test extraction of type alias definitions."""
        test_file = temp_project / "type_aliases.ts"
        test_file.write_text("""
        type Status = 'pending' | 'approved' | 'rejected';
        type UserRole = 'admin' | 'user' | 'guest';
        
        type ComplexType = {
            id: string;
            status: Status;
            role: UserRole;
            metadata: Record<string, any>;
        };
        
        function processStatus(status: Status): ComplexType {
            return {
                id: '1',
                status,
                role: 'user',
                metadata: {}
            };
        }
        """)
        
        result = get_function_details_impl(
            functions="processStatus",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        process_status_list = result.functions["processStatus"]
        assert process_status_list is not None
        assert isinstance(process_status_list, list)
        assert len(process_status_list) >= 1

        
        process_status = process_status_list[0]
        assert process_status.types is not None
        
        # Should extract Status type alias
        assert "Status" in process_status.types
        status_type = process_status.types["Status"]
        assert status_type.kind == "type"
        assert "'pending' | 'approved' | 'rejected'" in status_type.definition
        
        # Should extract ComplexType
        assert "ComplexType" in process_status.types
        complex_type = process_status.types["ComplexType"]
        assert complex_type.kind == "type"
        assert "status: Status" in complex_type.definition
        assert "Record<string, any>" in complex_type.definition

    def test_class_definition_extraction(self, temp_project):
        """Test extraction of class definitions."""
        test_file = temp_project / "classes.ts"
        test_file.write_text("""
        class BaseEntity {
            constructor(public id: string) {}
            
            getId(): string {
                return this.id;
            }
        }
        
        class User extends BaseEntity {
            constructor(id: string, public name: string) {
                super(id);
            }
            
            getName(): string {
                return this.name;
            }
        }
        
        function createUser(id: string, name: string): User {
            return new User(id, name);
        }
        """)
        
        result = get_function_details_impl(
            functions="createUser",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        create_user_list = result.functions["createUser"]
        assert create_user_list is not None
        assert isinstance(create_user_list, list)
        assert len(create_user_list) >= 1

        
        create_user = create_user_list[0]
        assert create_user.types is not None
        
        # Should extract User class
        assert "User" in create_user.types
        user_type = create_user.types["User"]
        assert user_type.kind == "class"
        assert "extends BaseEntity" in user_type.definition
        assert "constructor(id: string, public name: string)" in user_type.definition
        
        # Should extract BaseEntity as well (inheritance)
        assert "BaseEntity" in create_user.types
        base_type = create_user.types["BaseEntity"]
        assert base_type.kind == "class"

    def test_enum_definition_extraction(self, temp_project):
        """Test extraction of enum definitions."""
        test_file = temp_project / "enums.ts"
        test_file.write_text("""
        enum UserRole {
            ADMIN = 'admin',
            USER = 'user',
            GUEST = 'guest'
        }
        
        enum Status {
            PENDING,
            APPROVED,
            REJECTED
        }
        
        function assignRole(role: UserRole, status: Status): string {
            return `${role}_${status}`;
        }
        """)
        
        result = get_function_details_impl(
            functions="assignRole",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        assign_role_list = result.functions["assignRole"]
        assert assign_role_list is not None
        assert isinstance(assign_role_list, list)
        assert len(assign_role_list) >= 1

        
        assign_role = assign_role_list[0]
        assert assign_role.types is not None
        
        # Should extract both enums
        assert "UserRole" in assign_role.types
        role_type = assign_role.types["UserRole"]
        assert role_type.kind == "enum"
        assert "ADMIN = 'admin'" in role_type.definition
        
        assert "Status" in assign_role.types
        status_type = assign_role.types["Status"]
        assert status_type.kind == "enum"
        assert "PENDING" in status_type.definition

    def test_nested_type_resolution(self, temp_project):
        """Test resolution of nested and complex type references."""
        test_file = temp_project / "nested_types.ts"
        test_file.write_text("""
        interface Address {
            street: string;
            city: string;
            country: string;
        }
        
        interface Profile {
            avatar: string;
            bio?: string;
            address: Address;
        }
        
        interface User {
            id: number;
            name: string;
            profile: Profile;
            tags: string[];
            metadata: Record<string, any>;
        }
        
        function updateUserProfile(
            user: User, 
            profileUpdates: Partial<Profile>
        ): User {
            return {
                ...user,
                profile: { ...user.profile, ...profileUpdates }
            };
        }
        """)
        
        result = get_function_details_impl(
            functions="updateUserProfile",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        update_profile_list = result.functions["updateUserProfile"]
        assert update_profile_list is not None
        assert isinstance(update_profile_list, list)
        assert len(update_profile_list) >= 1

        
        update_profile = update_profile_list[0]
        assert update_profile.types is not None
        
        # Should resolve all nested types
        expected_types = ["User", "Profile", "Address", "Partial"]
        for type_name in expected_types:
            assert type_name in update_profile.types
        
        # Check nested relationships are preserved
        user_type = update_profile.types["User"]
        assert "profile: Profile" in user_type.definition
        
        profile_type = update_profile.types["Profile"]
        assert "address: Address" in profile_type.definition


class TestGenericTypeResolution:
    """Test resolution of generic types and constraints."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with Phase 3 test files."""
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

    def test_generic_constraint_resolution_depth_5_levels(self, temp_project):
        """Test generic constraint resolution up to 5 levels deep."""
        test_file = temp_project / "deep_generics.ts"
        test_file.write_text("""
        interface Level1 {
            id: string;
        }
        
        interface Level2<T extends Level1> {
            data: T;
            metadata: string;
        }
        
        interface Level3<T extends Level1, U extends Level2<T>> {
            nested: U;
            additional: T[];
        }
        
        interface Level4<
            T extends Level1,
            U extends Level2<T>,
            V extends Level3<T, U>
        > {
            deep: V;
            cache: Map<string, T>;
        }
        
        interface Level5<
            T extends Level1,
            U extends Level2<T>,
            V extends Level3<T, U>,
            W extends Level4<T, U, V>
        > {
            veryDeep: W;
            transform: (input: T) => U;
        }
        
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
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=5  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        process_deep_list = result.functions["processDeepGeneric"]
        assert process_deep_list is not None
        assert isinstance(process_deep_list, list)
        assert len(process_deep_list) >= 1

        
        process_deep = process_deep_list[0]
        assert process_deep is not None
        
        # Should handle 5 levels of generic constraints
        assert "T extends Level1" in process_deep.signature
        assert "U extends Level2<T>" in process_deep.signature
        assert "V extends Level3<T, U>" in process_deep.signature
        assert "W extends Level4<T, U, V>" in process_deep.signature
        assert "X extends Level5<T, U, V, W>" in process_deep.signature
        
        # Should resolve all constraint types
        assert process_deep.types is not None
        for level in ["Level1", "Level2", "Level3", "Level4", "Level5"]:
            assert level in process_deep.types
        
        # Should track constraint depth
        assert hasattr(result, 'resolution_metadata')
        assert result.resolution_metadata.max_constraint_depth_reached <= 5

    def test_generic_constraint_depth_limit_exceeded(self, temp_project):
        """Test behavior when generic constraint depth exceeds limit."""
        test_file = temp_project / "excessive_generics.ts"
        test_file.write_text("""
        interface A<T> { a: T; }
        interface B<T> extends A<T> { b: T; }
        interface C<T> extends B<T> { c: T; }
        interface D<T> extends C<T> { d: T; }
        interface E<T> extends D<T> { e: T; }
        interface F<T> extends E<T> { f: T; }
        interface G<T> extends F<T> { g: T; }
        interface H<T> extends G<T> { h: T; }
        
        function excessivelyDeep<T extends H<string>>(input: T): T {
            return input;
        }
        """)
        
        result = get_function_details_impl(
            functions="excessivelyDeep",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=5  # Limit to 5 levels
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Should handle gracefully with depth limit
        excessive_deep_list = result.functions["excessivelyDeep"]
        assert excessive_deep_list is not None
        assert isinstance(excessive_deep_list, list)
        assert len(excessive_deep_list) >= 1

        excessive_deep = excessive_deep_list[0]
        assert excessive_deep is not None
        
        # Should include warning about depth limit
        assert len(result.errors) > 0
        depth_warning = None
        for error in result.errors:
            if "constraint depth limit" in error.message.lower():
                depth_warning = error
                break
        
        assert depth_warning is not None
        assert depth_warning.code == "CONSTRAINT_DEPTH_EXCEEDED"

    def test_generic_instantiation_tracking(self, temp_project):
        """Test tracking of generic type instantiations."""
        test_file = temp_project / "generic_instantiations.ts"
        test_file.write_text("""
        interface Repository<T> {
            save(entity: T): Promise<T>;
            find(id: string): Promise<T | null>;
            findAll(): Promise<T[]>;
        }
        
        interface User {
            id: string;
            name: string;
        }
        
        interface Product {
            id: string;
            name: string;
            price: number;
        }
        
        function createUserRepo(): Repository<User> {
            return {} as Repository<User>;
        }
        
        function createProductRepo(): Repository<Product> {
            return {} as Repository<Product>;
        }
        
        function processRepositories<T>(
            userRepo: Repository<User>,
            productRepo: Repository<Product>,
            genericRepo: Repository<T>
        ): Promise<void> {
            return Promise.resolve();
        }
        """)
        
        result = get_function_details_impl(
            functions=["createUserRepo", "createProductRepo", "processRepositories"],
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics",
            track_instantiations=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Should track different instantiations of Repository<T>
        assert hasattr(result, 'type_instantiations')
        assert result.type_instantiations is not None
        
        # Should find Repository<User> and Repository<Product>
        repo_instantiations = result.type_instantiations.get("Repository", [])
        assert len(repo_instantiations) >= 2
        
        instantiation_types = [inst.type_args[0] for inst in repo_instantiations if inst.type_args]
        assert "User" in instantiation_types
        assert "Product" in instantiation_types

    def test_complex_generic_method_resolution(self, temp_project):
        """Test resolution of complex generic class methods."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "generic-functions.ts"
        target_file = temp_project / "generic-functions.ts"
        target_file.write_text(source_file.read_text())
        
        result = get_function_details_impl(
            functions=["Repository.save", "Repository.findById", "Repository.updateField"],
            file_paths=str(target_file),
            include_types=True,
            resolution_depth="generics",
            resolve_class_methods=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test generic method with different generic parameter
        save_method_list = result.functions.get("Repository.save")

        save_method = save_method_list[0] if save_method_list else None
        assert save_method is not None
        assert "<U extends T>" in save_method.signature
        assert "item: U" in save_method.signature
        assert "): Promise<U>" in save_method.signature
        
        # Test method with keyof constraint
        update_field_list = result.functions.get("Repository.updateField")

        update_field = update_field_list[0] if update_field_list else None
        assert update_field is not None
        assert "K extends keyof T" in update_field.signature
        assert "key: K" in update_field.signature
        assert "value: T[K]" in update_field.signature


class TestTypeInferenceAccuracy:
    """Test accuracy of type inference across complex scenarios."""

    @pytest.fixture
    def temp_project(self):
        """Create temporary project with Phase 3 test files."""
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

    def test_inference_accuracy_with_imported_types(self, temp_project):
        """Test type inference accuracy with cross-file type imports."""
        # Create multiple files with type dependencies
        base_types_file = temp_project / "base.ts"
        base_types_file.write_text("""
        export interface BaseEntity {
            id: string;
            createdAt: Date;
        }
        
        export interface User extends BaseEntity {
            name: string;
            email: string;
        }
        """)
        
        processor_file = temp_project / "processor.ts"
        processor_file.write_text("""
        import { User, BaseEntity } from './base';
        
        export function processUser<T extends User>(user: T): Promise<T & { processed: true }> {
            return Promise.resolve({ ...user, processed: true as const });
        }
        
        export function validateEntity<T extends BaseEntity>(entity: T): entity is T & { valid: true } {
            return entity.id.length > 0;
        }
        """)
        
        result = get_function_details_impl(
            functions=["processUser", "validateEntity"],
            file_paths=[str(base_types_file), str(processor_file)],
            include_types=True,
            resolution_depth="full_inference",
            resolve_imports=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Should resolve imported types correctly
        process_user_list = result.functions["processUser"]
        assert process_user_list is not None
        assert isinstance(process_user_list, list)
        assert len(process_user_list) >= 1

        process_user = process_user_list[0]
        assert process_user is not None
        assert "T extends User" in process_user.signature
        assert "T & { processed: true }" in process_user.signature
        
        # Should include imported type definitions
        assert process_user.types is not None
        assert "User" in process_user.types
        assert "BaseEntity" in process_user.types
        
        # Should track import relationships
        assert hasattr(result, 'import_graph')
        assert result.import_graph is not None

    def test_inference_with_type_guards(self, temp_project):
        """Test type inference accuracy with TypeScript type guards."""
        test_file = temp_project / "type_guards.ts"
        test_file.write_text("""
        interface User {
            type: 'user';
            name: string;
            email: string;
        }
        
        interface Admin {
            type: 'admin';
            name: string;
            permissions: string[];
        }
        
        type Person = User | Admin;
        
        function isUser(person: Person): person is User {
            return person.type === 'user';
        }
        
        function isAdmin(person: Person): person is Admin {
            return person.type === 'admin';
        }
        
        function processPersonSafely(person: Person): string {
            if (isUser(person)) {
                return `User: ${person.email}`;  // person is now typed as User
            } else if (isAdmin(person)) {
                return `Admin: ${person.permissions.join(', ')}`;  // person is now typed as Admin
            }
            return 'Unknown person type';
        }
        """)
        
        result = get_function_details_impl(
            functions=["isUser", "isAdmin", "processPersonSafely"],
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="full_inference",
            analyze_type_guards=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Should identify type guard functions
        is_user_list = result.functions["isUser"]
        assert is_user_list is not None
        assert isinstance(is_user_list, list)
        assert len(is_user_list) >= 1

        is_user = is_user_list[0]
        assert is_user is not None
        assert "person is User" in is_user.signature
        
        # Should track type narrowing effects
        assert hasattr(is_user, 'type_guard_info')
        assert is_user.type_guard_info is not None
        assert is_user.type_guard_info.narrows_to == 'User'
        assert is_user.type_guard_info.from_type == 'Person'

    def test_inference_with_conditional_types_and_infer(self, temp_project):
        """Test complex conditional types with infer keyword."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "complex-types.ts"
        target_file = temp_project / "complex-types.ts"
        target_file.write_text(source_file.read_text())
        
        result = get_function_details_impl(
            functions=["processWithRetry"],
            file_paths=str(target_file),
            include_types=True,
            resolution_depth="full_inference",
            resolve_conditional_types=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        process_retry_list = result.functions["processWithRetry"]
        assert process_retry_list is not None
        assert isinstance(process_retry_list, list)
        assert len(process_retry_list) >= 1

        
        process_retry = process_retry_list[0]
        assert process_retry is not None
        
        # Should resolve complex conditional return type
        conditional_return = "Promise<U extends undefined ? T : U>"
        assert conditional_return in process_retry.signature
        
        # Should track infer relationships
        assert process_retry.types is not None
        # Should include information about inferred types

    def test_inference_accuracy_with_recursive_types(self, temp_project):
        """Test type inference with recursive type definitions."""
        test_file = temp_project / "recursive_types.ts"
        test_file.write_text("""
        interface TreeNode<T> {
            value: T;
            children: TreeNode<T>[];
            parent?: TreeNode<T>;
        }
        
        type DeepReadonly<T> = {
            readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
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
        """)
        
        result = get_function_details_impl(
            functions=["traverseTree", "makeDeepReadonly"],
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="full_inference",
            handle_recursive_types=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Should handle recursive TreeNode type
        traverse_tree_list = result.functions["traverseTree"]
        assert traverse_tree_list is not None
        assert isinstance(traverse_tree_list, list)
        assert len(traverse_tree_list) >= 1

        traverse_tree = traverse_tree_list[0]
        assert traverse_tree is not None
        assert "TreeNode<T>" in traverse_tree.signature
        
        # Should resolve recursive mapped type
        make_readonly_list = result.functions["makeDeepReadonly"]
        assert make_readonly_list is not None
        assert isinstance(make_readonly_list, list)
        assert len(make_readonly_list) >= 1

        make_readonly = make_readonly_list[0]
        assert make_readonly is not None
        assert "DeepReadonly<T>" in make_readonly.signature
        
        # Should include recursive type information
        assert traverse_tree.types is not None
        assert "TreeNode" in traverse_tree.types
        tree_type = traverse_tree.types["TreeNode"]
        assert "children: TreeNode<T>[]" in tree_type.definition

    def test_type_inference_performance_under_complexity(self, temp_project):
        """Test that type inference maintains reasonable performance under complexity."""
        # Create file with many complex interdependent types
        complex_file = temp_project / "performance_test.ts"
        
        # Generate 50 interdependent interfaces and functions
        complex_content = []
        
        # Create base interfaces
        for i in range(10):
            complex_content.append(f"""
            interface Entity{i} {{
                id: string;
                data{i}: string;
                related: Entity{(i + 1) % 10}[];
            }}
            """)
        
        # Create complex generic functions
        for i in range(20):
            complex_content.append(f"""
            function process{i}<T extends Entity{i % 10}>(
                input: T,
                processor: (item: T) => T,
                validator: (item: T) => boolean
            ): Promise<T[]> {{
                return Promise.resolve([]);
            }}
            """)
        
        complex_file.write_text('\n'.join(complex_content))
        
        # Test performance with many functions
        function_names = [f"process{i}" for i in range(20)]
        
        start_time = time.perf_counter()
        result = get_function_details_impl(
            functions=function_names,
            file_paths=str(complex_file),
            include_types=True,
            resolution_depth="full_inference"
        )
        end_time = time.perf_counter()
        
        analysis_time = end_time - start_time
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Performance requirement: should handle complex scenarios in reasonable time
        assert analysis_time < 30.0, f"Complex inference took {analysis_time:.2f}s, should be <30s"
        
        # Should have resolved most functions
        assert len(result.functions) >= 15  # Allow for some failures in complex scenarios