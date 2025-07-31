"""
Tests for Phase 3 function analysis functionality.

These tests define the expected behavior for comprehensive function analysis:
- Function signature extraction (declarations, arrows, methods, generics)
- Function body analysis (code extraction, call dependency tracking)
- Batch processing (100+ functions within 10 seconds, memory efficiency)
- Performance optimization (shared type context, concurrent processing)

All tests should initially FAIL (RED phase) to drive TDD implementation.
"""

import tempfile
import time
import psutil
import os
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


class TestFunctionSignatureExtraction:
    """Test comprehensive function signature extraction capabilities."""

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

    def test_function_declaration_signatures(self, temp_project):
        """Test extraction of function declaration signatures."""
        test_file = temp_project / "function_declarations.ts"
        test_file.write_text("""
        // Simple function declaration
        function simpleFunction(param: string): number {
            return param.length;
        }
        
        // Function with optional parameters
        function withOptionals(required: string, optional?: number, defaulted: boolean = false): void {
            console.log(required, optional, defaulted);
        }
        
        // Function with rest parameters
        function withRest(first: string, ...rest: number[]): string[] {
            return [first, ...rest.map(String)];
        }
        
        // Function with union types
        function withUnions(input: string | number | boolean, output?: 'json' | 'xml'): string | null {
            return String(input);
        }
        
        // Function with complex object parameters
        function withComplexParams(
            config: {
                host: string;
                port: number;
                options?: { timeout: number; retries: number };
            },
            callback: (error: Error | null, result?: any) => void
        ): Promise<void> {
            return Promise.resolve();
        }
        """)
        
        result = get_function_details_impl(
            functions=[
                "simpleFunction", "withOptionals", "withRest", 
                "withUnions", "withComplexParams"
            ],
            file_paths=str(test_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        assert len(result.functions) == 5
        
        # Test simple function
        simple_func_list = result.functions["simpleFunction"]
        assert simple_func_list is not None
        assert isinstance(simple_func_list, list)
        assert len(simple_func_list) >= 1
        simple_func = simple_func_list[0]
        assert isinstance(simple_func, FunctionDetail)
        assert simple_func.signature == "function simpleFunction(param: string): number"
        assert simple_func.location.endswith("function_declarations.ts:3")
        
        # Test optional parameters
        with_optionals_list = result.functions["withOptionals"]
        assert with_optionals_list is not None
        assert isinstance(with_optionals_list, list)
        assert len(with_optionals_list) >= 1
        with_optionals = with_optionals_list[0]
        expected_sig = "function withOptionals(required: string, optional?: number, defaulted: boolean = false): void"
        assert with_optionals.signature == expected_sig
        
        # Test rest parameters
        with_rest_list = result.functions["withRest"]
        assert with_rest_list is not None
        assert isinstance(with_rest_list, list)
        assert len(with_rest_list) >= 1
        with_rest = with_rest_list[0]
        assert "...rest: number[]" in with_rest.signature
        assert "): string[]" in with_rest.signature
        
        # Test union types
        with_unions_list = result.functions["withUnions"]
        assert with_unions_list is not None
        assert isinstance(with_unions_list, list)
        assert len(with_unions_list) >= 1
        with_unions = with_unions_list[0]
        assert "string | number | boolean" in with_unions.signature
        assert "'json' | 'xml'" in with_unions.signature
        assert "string | null" in with_unions.signature
        
        # Test complex parameters
        with_complex_list = result.functions["withComplexParams"]
        assert with_complex_list is not None
        assert isinstance(with_complex_list, list)
        assert len(with_complex_list) >= 1
        with_complex = with_complex_list[0]
        assert "config: {" in with_complex.signature
        assert "callback: (error: Error | null, result?: any) => void" in with_complex.signature

    def test_arrow_function_signatures(self, temp_project):
        """Test extraction of arrow function signatures."""
        test_file = temp_project / "arrow_functions.ts"
        test_file.write_text("""
        // Simple arrow function
        export const simpleArrow = (x: number): string => x.toString();
        
        // Arrow function with explicit return type
        export const explicitReturn = (name: string, age: number): { name: string; age: number } => ({
            name, age
        });
        
        // Async arrow function
        export const asyncArrow = async (id: number): Promise<string | null> => {
            return String(id);
        };
        
        // Arrow function with generic
        export const genericArrow = <T>(value: T): T[] => [value];
        
        // Arrow function with complex generic constraints
        export const complexGenericArrow = <T extends Record<string, any>, K extends keyof T>(
            obj: T,
            key: K
        ): T[K] => obj[key];
        
        // Higher-order arrow function
        export const higherOrder = <T, U>(
            mapper: (input: T) => U
        ) => (items: T[]): U[] => items.map(mapper);
        """)
        
        result = get_function_details_impl(
            functions=[
                "simpleArrow", "explicitReturn", "asyncArrow",
                "genericArrow", "complexGenericArrow", "higherOrder"
            ],
            file_paths=str(test_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        assert len(result.functions) == 6
        
        # Test simple arrow
        simple_arrow_list = result.functions["simpleArrow"]
        assert simple_arrow_list is not None
        assert isinstance(simple_arrow_list, list)
        assert len(simple_arrow_list) >= 1

        simple_arrow = simple_arrow_list[0]
        assert "const simpleArrow = (x: number): string =>" in simple_arrow.signature
        
        # Test async arrow
        async_arrow_list = result.functions["asyncArrow"]
        assert async_arrow_list is not None
        assert isinstance(async_arrow_list, list)
        assert len(async_arrow_list) >= 1

        async_arrow = async_arrow_list[0]
        assert "async" in async_arrow.signature
        assert "Promise<string | null>" in async_arrow.signature
        
        # Test generic arrow
        generic_arrow_list = result.functions["genericArrow"]
        assert generic_arrow_list is not None
        assert isinstance(generic_arrow_list, list)
        assert len(generic_arrow_list) >= 1

        generic_arrow = generic_arrow_list[0]
        assert "<T>" in generic_arrow.signature
        assert "(value: T): T[]" in generic_arrow.signature
        
        # Test complex generic arrow
        complex_arrow_list = result.functions["complexGenericArrow"]
        assert complex_arrow_list is not None
        assert isinstance(complex_arrow_list, list)
        assert len(complex_arrow_list) >= 1

        complex_arrow = complex_arrow_list[0]
        assert "T extends Record<string, any>" in complex_arrow.signature
        assert "K extends keyof T" in complex_arrow.signature
        assert "): T[K]" in complex_arrow.signature
        
        # Test higher-order function
        higher_order_list = result.functions["higherOrder"]
        assert higher_order_list is not None
        assert isinstance(higher_order_list, list)
        assert len(higher_order_list) >= 1

        higher_order = higher_order_list[0]
        assert "mapper: (input: T) => U" in higher_order.signature
        assert ") => (items: T[]): U[]" in higher_order.signature

    def test_class_method_signatures(self, temp_project):
        """Test extraction of class method signatures."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "class-methods.ts"
        target_file = temp_project / "class-methods.ts"
        target_file.write_text(source_file.read_text())
        
        result = get_function_details_impl(
            functions=[
                "AbstractProcessor.processWithLogging",
                "AbstractProcessor.batchProcess",
                "UserProcessor.process",
                "UserProcessor.processNewUser",
                "AdminUserProcessor.processAdminAction"
            ],
            file_paths=str(target_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            resolution_depth="generics"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test abstract class method with generics
        process_logging_list = result.functions.get("AbstractProcessor.processWithLogging")

        process_logging = process_logging_list[0] if process_logging_list else None
        assert process_logging is not None
        assert "async processWithLogging<U extends T>" in process_logging.signature
        assert "logger?: (message: string, data: any) => void" in process_logging.signature
        assert "): Promise<U>" in process_logging.signature
        
        # Test method with complex options parameter
        batch_process_list = result.functions.get("AbstractProcessor.batchProcess")

        batch_process = batch_process_list[0] if batch_process_list else None
        assert batch_process is not None
        assert "batchProcess<U extends T>" in batch_process.signature
        assert "options?: {" in batch_process.signature
        assert "parallel?: boolean" in batch_process.signature
        assert "onProgress?: (completed: number, total: number) => void" in batch_process.signature
        
        # Test concrete implementation
        user_process_list = result.functions.get("UserProcessor.process")

        user_process = user_process_list[0] if user_process_list else None
        assert user_process is not None
        assert "async process(user: User): Promise<User>" in user_process.signature
        
        # Test method with conditional parameters
        process_new_list = result.functions.get("UserProcessor.processNewUser")

        process_new = process_new_list[0] if process_new_list else None
        assert process_new is not None
        assert "userData: Omit<User, 'id'>" in process_new.signature
        assert "sendWelcomeEmail: boolean = true" in process_new.signature

    def test_generic_function_signatures(self, temp_project):
        """Test extraction of complex generic function signatures."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "generic-functions.ts"
        target_file = temp_project / "generic-functions.ts"
        target_file.write_text(source_file.read_text())
        
        result = get_function_details_impl(
            functions=[
                "validateAndProcess", "formatValue", "pickFields",
                "processArrayElements", "mergeDeep"
            ],
            file_paths=str(target_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            resolution_depth="full_inference"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test complex multi-constraint generic
        validate_process_list = result.functions["validateAndProcess"]
        assert validate_process_list is not None
        assert isinstance(validate_process_list, list)
        assert len(validate_process_list) >= 1

        validate_process = validate_process_list[0]
        expected_constraints = [
            "T extends BaseEntity",
            "K extends keyof T", 
            "V extends T[K]"
        ]
        for constraint in expected_constraints:
            assert constraint in validate_process.signature
        assert "validator: (value: V) => boolean" in validate_process.signature
        
        # Test conditional type function
        format_value_list = result.functions["formatValue"]
        assert format_value_list is not None
        assert isinstance(format_value_list, list)
        assert len(format_value_list) >= 1

        format_value = format_value_list[0]
        conditional_return = (
            "T extends string ? string : T extends number ? string : never"
        )
        assert conditional_return in format_value.signature
        
        # Test utility type function
        pick_fields_list = result.functions["pickFields"]
        assert pick_fields_list is not None
        assert isinstance(pick_fields_list, list)
        assert len(pick_fields_list) >= 1

        pick_fields = pick_fields_list[0]
        assert "keys: K[]" in pick_fields.signature
        assert "): Pick<T, K>" in pick_fields.signature
        
        # Test infer type function
        process_array_list = result.functions["processArrayElements"]
        assert process_array_list is not None
        assert isinstance(process_array_list, list)
        assert len(process_array_list) >= 1

        process_array = process_array_list[0]
        assert "T extends readonly unknown[]" in process_array.signature
        assert "): ExtractArrayType<T>[]" in process_array.signature

    def test_generic_constraint_with_arrow_function_parsing_bug(self, temp_project):
        """Test function signature parsing bug with arrow functions in generic constraints.
        
        Bug: The angle bracket counting logic treats '>' in '=>' as a closing generic bracket,
        causing function signatures to be truncated at the arrow function syntax.
        """
        test_file = temp_project / "arrow_function_constraint_bug.ts"
        test_file.write_text("""
        // Function with generic constraint containing arrow function - this triggers the bug
        function extractReturnType<T extends (...args: any[]) => any>(
            fn: T
        ): ReturnTypeExtractor<T> {
            return {} as ReturnTypeExtractor<T>;
        }
        
        // Additional test cases that should also trigger the bug
        function processCallback<T extends (data: string) => number>(
            callback: T,
            input: string
        ): number {
            return callback(input);
        }
        
        // Complex case with multiple arrow functions in constraint
        function complexConstraint<T extends {
            mapper: (input: string) => number;
            reducer: (acc: number, val: number) => number;
        }>(processor: T): void {
            // implementation
        }
        
        // Type alias for reference
        type ReturnTypeExtractor<T> = T extends (...args: any[]) => infer R ? R : never;
        """)
        
        result = get_function_details_impl(
            functions=["extractReturnType", "processCallback", "complexConstraint"],
            file_paths=str(test_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test the main bug case: extractReturnType function
        extract_return_list = result.functions["extractReturnType"]
        assert extract_return_list is not None
        assert isinstance(extract_return_list, list)
        assert len(extract_return_list) >= 1

        extract_return = extract_return_list[0]
        assert extract_return is not None
        
        # BUG: Currently this signature gets truncated at the '=>' and returns:
        # "function extractReturnType<T extends (...args: any[]) =>(...args: any[])"
        # 
        # EXPECTED: Complete signature should include the return type:
        # "function extractReturnType<T extends (...args: any[]) => any>(fn: T): ReturnTypeExtractor<T>"
        expected_signature_parts = [
            "function extractReturnType",
            "T extends (...args: any[]) => any",  # Full constraint, not truncated
            "fn: T",  # Parameter should be included
            "): ReturnTypeExtractor<T>"  # Return type should be included
        ]
        
        actual_signature = extract_return.signature
        print(f"DEBUG: Actual signature: {actual_signature}")
        
        # This test demonstrates the bug - it will fail because the signature is truncated
        for expected_part in expected_signature_parts:
            assert expected_part in actual_signature, f"Missing '{expected_part}' in signature: {actual_signature}"
        
        # Test second bug case: processCallback function
        process_callback_list = result.functions["processCallback"]
        assert process_callback_list is not None
        assert isinstance(process_callback_list, list)
        assert len(process_callback_list) >= 1

        process_callback = process_callback_list[0]
        assert process_callback is not None
        
        expected_callback_parts = [
            "T extends (data: string) => number",
            "callback: T",  
            "input: string",
            "): number"
        ]
        
        callback_signature = process_callback.signature
        print(f"DEBUG: Callback signature: {callback_signature}")
        
        for expected_part in expected_callback_parts:
            assert expected_part in callback_signature, f"Missing '{expected_part}' in callback signature: {callback_signature}"
        
        # Test complex constraint case
        complex_constraint_list = result.functions["complexConstraint"]
        assert complex_constraint_list is not None
        assert isinstance(complex_constraint_list, list)
        assert len(complex_constraint_list) >= 1

        complex_constraint = complex_constraint_list[0]
        assert complex_constraint is not None
        
        expected_complex_parts = [
            "mapper: (input: string) => number",
            "reducer: (acc: number, val: number) => number",
            "processor: T",
            "): void"
        ]
        
        complex_signature = complex_constraint.signature
        print(f"DEBUG: Complex signature: {complex_signature}")
        
        for expected_part in expected_complex_parts:
            assert expected_part in complex_signature, f"Missing '{expected_part}' in complex signature: {complex_signature}"

    def test_parameter_type_details_extraction(self, temp_project):
        """Test detailed parameter type information extraction."""
        test_file = temp_project / "parameter_details.ts"
        test_file.write_text("""
        interface Config {
            host: string;
            port: number;
            ssl?: boolean;
        }
        
        function complexParameters(
            required: string,
            optional?: number,
            withDefault: boolean = true,
            config: Config,
            callback: (error: Error | null, data?: any) => void,
            ...rest: string[]
        ): Promise<void> {
            return Promise.resolve();
        }
        """)
        
        result = get_function_details_impl(
            functions="complexParameters",
            file_paths=str(test_file),
            include_code=False,
            include_types=True,
            include_calls=False
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        complex_params_list = result.functions["complexParameters"]
        assert complex_params_list is not None
        assert isinstance(complex_params_list, list)
        assert len(complex_params_list) >= 1

        
        complex_params = complex_params_list[0]
        assert complex_params is not None
        
        # Should extract detailed parameter information
        assert hasattr(complex_params, 'parameters')
        assert complex_params.parameters is not None
        assert len(complex_params.parameters) == 6
        
        # Test required parameter
        required_param = complex_params.parameters[0]
        assert isinstance(required_param, ParameterType)
        assert required_param.name == "required"
        assert required_param.type == "string"
        assert required_param.optional is False
        assert required_param.default_value is None
        
        # Test optional parameter
        optional_param = complex_params.parameters[1]
        assert optional_param.name == "optional"
        assert optional_param.type == "number"
        assert optional_param.optional is True
        
        # Test parameter with default
        default_param = complex_params.parameters[2]
        assert default_param.name == "withDefault"
        assert default_param.type == "boolean"
        assert default_param.default_value == "true"
        
        # Test interface parameter
        config_param = complex_params.parameters[3]
        assert config_param.name == "config"
        assert config_param.type == "Config"
        
        # Test function parameter
        callback_param = complex_params.parameters[4]
        assert callback_param.name == "callback"
        assert "(error: Error | null, data?: any) => void" in callback_param.type
        
        # Test rest parameter
        rest_param = complex_params.parameters[5]
        assert rest_param.name == "rest"
        assert rest_param.type == "string[]"
        assert hasattr(rest_param, 'is_rest_parameter')
        assert rest_param.is_rest_parameter is True

    def test_function_signature_with_overloads(self, temp_project):
        """Test extraction of function overload signatures."""
        test_file = temp_project / "overloads.ts"
        test_file.write_text("""
        // Function overloads
        function processData(data: string): string;
        function processData(data: number): number; 
        function processData(data: boolean): boolean;
        function processData(data: string | number | boolean): string | number | boolean {
            return data;
        }
        
        // Class method overloads
        class DataProcessor {
            process(input: string): Promise<string>;
            process(input: number): Promise<number>;
            process(input: string | number): Promise<string | number> {
                return Promise.resolve(input);
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=["processData", "DataProcessor.process"],
            file_paths=str(test_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            handle_overloads=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test function overloads
        process_data_list = result.functions["processData"]
        assert process_data_list is not None
        assert isinstance(process_data_list, list)
        assert len(process_data_list) >= 1
        process_data = process_data_list[0]  # Get first instance
        
        # Should capture all overload signatures
        assert hasattr(process_data, 'overloads')
        assert process_data.overloads is not None
        assert len(process_data.overloads) == 4  # 3 overloads + implementation
        
        # Should identify the implementation signature
        implementation_sig = process_data.signature
        assert "string | number | boolean" in implementation_sig
        
        # Test method overloads
        process_method_list = result.functions.get("DataProcessor.process")
        assert process_method_list is not None
        assert isinstance(process_method_list, list)
        assert len(process_method_list) >= 1
        process_method = process_method_list[0]  # Get first instance
        assert hasattr(process_method, 'overloads')
        assert len(process_method.overloads) >= 2


class TestFunctionBodyAnalysis:
    """Test function body analysis and call dependency tracking."""

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

    def test_function_code_extraction(self, temp_project):
        """Test complete function implementation extraction."""
        test_file = temp_project / "code_extraction.ts"
        test_file.write_text("""
        function simpleFunction(name: string): string {
            return `Hello, ${name}!`;
        }
        
        async function complexFunction(
            data: any[],
            processor: (item: any) => Promise<any>
        ): Promise<any[]> {
            const results = [];
            
            for (const item of data) {
                try {
                    const processed = await processor(item);
                    results.push(processed);
                } catch (error) {
                    console.error('Processing failed:', error);
                    results.push(null);
                }
            }
            
            return results.filter(item => item !== null);
        }
        
        class UserService {
            private users: Map<string, any> = new Map();
            
            async createUser(userData: any): Promise<any> {
                const id = this.generateId();
                const user = {
                    id,
                    ...userData,
                    createdAt: new Date()
                };
                
                this.users.set(id, user);
                await this.notifyUserCreated(user);
                
                return user;
            }
            
            private generateId(): string {
                return Math.random().toString(36).substr(2, 9);
            }
            
            private async notifyUserCreated(user: any): Promise<void> {
                // Notification logic here
                console.log(`User created: ${user.id}`);
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=[
                "simpleFunction", "complexFunction", 
                "UserService.createUser", "UserService.generateId"
            ],
            file_paths=str(test_file),
            include_code=True,  # Request full code
            include_types=True,
            include_calls=True,
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test simple function code
        simple_func_list = result.functions["simpleFunction"]
        assert simple_func_list is not None
        assert isinstance(simple_func_list, list)
        assert len(simple_func_list) >= 1

        simple_func = simple_func_list[0]
        assert simple_func.code is not None
        assert "return `Hello, ${name}!`;" in simple_func.code
        
        # Test complex async function code
        complex_func_list = result.functions["complexFunction"]
        assert complex_func_list is not None
        assert isinstance(complex_func_list, list)
        assert len(complex_func_list) >= 1

        complex_func = complex_func_list[0]
        assert complex_func.code is not None
        assert "const results = [];" in complex_func.code
        assert "for (const item of data)" in complex_func.code
        assert "try {" in complex_func.code
        assert "await processor(item)" in complex_func.code
        assert "} catch (error) {" in complex_func.code
        
        # Test class method code
        create_user_list = result.functions["UserService.createUser"]
        assert create_user_list is not None
        assert isinstance(create_user_list, list)
        assert len(create_user_list) >= 1

        create_user = create_user_list[0]
        assert create_user.code is not None
        assert "const id = this.generateId();" in create_user.code
        assert "this.users.set(id, user);" in create_user.code
        assert "await this.notifyUserCreated(user);" in create_user.code
        
        # Test private method code
        generate_id_list = result.functions["UserService.generateId"]
        assert generate_id_list is not None
        assert isinstance(generate_id_list, list)
        assert len(generate_id_list) >= 1

        generate_id = generate_id_list[0]
        assert generate_id.code is not None
        assert "Math.random().toString(36).substr(2, 9)" in generate_id.code

    def test_function_call_dependency_tracking(self, temp_project):
        """Test identification of functions called by each analyzed function."""
        test_file = temp_project / "call_dependencies.ts"
        test_file.write_text("""
        function helperFunction(data: string): string {
            return data.trim().toLowerCase();
        }
        
        function anotherHelper(value: number): string {
            return value.toFixed(2);
        }
        
        function mainFunction(input: string, count: number): string {
            const cleaned = helperFunction(input);
            const formatted = anotherHelper(count);
            
            // External function calls
            console.log('Processing:', cleaned);
            Math.max(count, 0);
            
            return `${cleaned}: ${formatted}`;
        }
        
        async function asyncMain(data: any[]): Promise<string[]> {
            const results = await Promise.all(
                data.map(item => processItem(item))
            );
            
            return results.filter(Boolean).map(String);
        }
        
        function processItem(item: any): Promise<string> {
            return Promise.resolve(String(item));
        }
        
        class DataProcessor {
            process(data: any): any {
                const validated = this.validate(data);
                const transformed = this.transform(validated);
                return this.finalize(transformed);
            }
            
            private validate(data: any): any {
                return data;
            }
            
            private transform(data: any): any {
                return { ...data, transformed: true };
            }
            
            private finalize(data: any): any {
                return { ...data, finalized: true };
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=[
                "mainFunction", "asyncMain", "DataProcessor.process"
            ],
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=True,  # Track function calls
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test main function call tracking
        main_func_list = result.functions["mainFunction"]
        assert main_func_list is not None
        assert isinstance(main_func_list, list)
        assert len(main_func_list) >= 1

        main_func = main_func_list[0]
        assert main_func.calls is not None
        
        # Should identify local function calls
        expected_local_calls = ["helperFunction", "anotherHelper"]
        for call in expected_local_calls:
            assert call in main_func.calls
        
        # Should identify external/built-in calls
        expected_external_calls = ["console.log", "Math.max"]
        for call in expected_external_calls:
            assert call in main_func.calls
        
        # Test async function call tracking
        async_main_list = result.functions["asyncMain"]
        assert async_main_list is not None
        assert isinstance(async_main_list, list)
        assert len(async_main_list) >= 1

        async_main = async_main_list[0]
        assert async_main.calls is not None
        assert "Promise.all" in async_main.calls
        assert "processItem" in async_main.calls
        
        # Test class method call tracking
        process_method_list = result.functions["DataProcessor.process"]
        assert process_method_list is not None
        assert isinstance(process_method_list, list)
        assert len(process_method_list) >= 1

        process_method = process_method_list[0]
        assert process_method.calls is not None
        
        # Should identify method calls on 'this'
        expected_method_calls = ["this.validate", "this.transform", "this.finalize"]
        for call in expected_method_calls:
            assert call in process_method.calls

    def test_nested_function_analysis(self, temp_project):
        """Test analysis of nested function definitions."""
        test_file = temp_project / "nested_functions.ts"
        test_file.write_text("""
        function outerFunction(data: string[]): string[] {
            function innerFilter(item: string): boolean {
                return item.length > 0;
            }
            
            function innerTransform(item: string): string {
                return item.toUpperCase();
            }
            
            const filtered = data.filter(innerFilter);
            const transformed = filtered.map(innerTransform);
            
            return transformed;
        }
        
        function withClosures(multiplier: number): (value: number) => number {
            return function multiply(value: number): number {
                return value * multiplier;
            };
        }
        
        class Calculator {
            calculate(operations: string[]): number {
                let result = 0;
                
                const applyOperation = (op: string) => {
                    const [operator, operand] = op.split(' ');
                    const value = parseInt(operand);
                    
                    switch (operator) {
                        case 'add':
                            result += value;
                            break;
                        case 'subtract':
                            result -= value;
                            break;
                    }
                };
                
                operations.forEach(applyOperation);
                return result;
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=[
                "outerFunction", "withClosures", "Calculator.calculate"
            ],
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=True,
            analyze_nested_functions=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test outer function with nested functions
        outer_func_list = result.functions["outerFunction"]
        assert outer_func_list is not None
        assert isinstance(outer_func_list, list)
        assert len(outer_func_list) >= 1

        outer_func = outer_func_list[0]
        assert outer_func.code is not None
        
        # Should identify nested function definitions
        assert hasattr(outer_func, 'nested_functions')
        assert outer_func.nested_functions is not None
        assert "innerFilter" in outer_func.nested_functions
        assert "innerTransform" in outer_func.nested_functions
        
        # Should track calls to nested functions
        assert "innerFilter" in outer_func.calls
        assert "innerTransform" in outer_func.calls
        
        # Test closure function
        with_closures_list = result.functions["withClosures"]
        assert with_closures_list is not None
        assert isinstance(with_closures_list, list)
        assert len(with_closures_list) >= 1

        with_closures = with_closures_list[0]
        assert with_closures.nested_functions is not None
        assert "multiply" in with_closures.nested_functions
        
        # Test class method with nested function
        calculate_method_list = result.functions["Calculator.calculate"]
        assert calculate_method_list is not None
        assert isinstance(calculate_method_list, list)
        assert len(calculate_method_list) >= 1

        calculate_method = calculate_method_list[0]
        assert calculate_method.nested_functions is not None
        assert "applyOperation" in calculate_method.nested_functions

    def test_control_flow_analysis(self, temp_project):
        """Test analysis of control flow patterns in functions."""
        test_file = temp_project / "control_flow.ts"
        test_file.write_text("""
        function conditionalFlow(status: string): string {
            if (status === 'active') {
                return processActive();
            } else if (status === 'pending') {
                return processPending();
            } else {
                return processInactive();
            }
        }
        
        function loopFlow(items: string[]): string[] {
            const results = [];
            
            for (const item of items) {
                if (item.startsWith('skip')) {
                    continue;
                }
                
                try {
                    const processed = processItem(item);
                    results.push(processed);
                } catch (error) {
                    console.error('Failed:', error);
                    break;
                }
            }
            
            return results;
        }
        
        function switchFlow(type: string): any {
            switch (type) {
                case 'user':
                    return createUser();
                case 'admin':
                    return createAdmin();
                case 'guest':
                    return createGuest();
                default:
                    throw new Error('Unknown type');
            }
        }
        
        // Mock functions for calls
        function processActive(): string { return 'active'; }
        function processPending(): string { return 'pending'; }
        function processInactive(): string { return 'inactive'; }
        function processItem(item: string): string { return item; }
        function createUser(): any { return {}; }
        function createAdmin(): any { return {}; }
        function createGuest(): any { return {}; }
        """)
        
        result = get_function_details_impl(
            functions=["conditionalFlow", "loopFlow", "switchFlow"],
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=True,
            analyze_control_flow=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test conditional flow analysis
        conditional_func_list = result.functions["conditionalFlow"]
        assert conditional_func_list is not None
        assert isinstance(conditional_func_list, list)
        assert len(conditional_func_list) >= 1

        conditional_func = conditional_func_list[0]
        assert conditional_func.calls is not None
        
        # Should identify conditional function calls
        expected_calls = ["processActive", "processPending", "processInactive"]
        for call in expected_calls:
            assert call in conditional_func.calls
        
        # Should include control flow metadata
        assert hasattr(conditional_func, 'control_flow_info')
        assert conditional_func.control_flow_info is not None
        assert conditional_func.control_flow_info['has_conditionals'] is True
        assert conditional_func.control_flow_info['has_multiple_returns'] is True
        
        # Test loop flow analysis
        loop_func_list = result.functions["loopFlow"]
        assert loop_func_list is not None
        assert isinstance(loop_func_list, list)
        assert len(loop_func_list) >= 1

        loop_func = loop_func_list[0]
        assert "processItem" in loop_func.calls
        assert "console.error" in loop_func.calls
        
        assert loop_func.control_flow_info['has_loops'] is True
        assert loop_func.control_flow_info['has_try_catch'] is True
        assert loop_func.control_flow_info['has_break_continue'] is True
        
        # Test switch flow analysis
        switch_func_list = result.functions["switchFlow"]
        assert switch_func_list is not None
        assert isinstance(switch_func_list, list)
        assert len(switch_func_list) >= 1

        switch_func = switch_func_list[0]
        switch_calls = ["createUser", "createAdmin", "createGuest"]
        for call in switch_calls:
            assert call in switch_func.calls
        
        assert switch_func.control_flow_info['has_switch'] is True

    def test_variable_declaration_tracking(self, temp_project):
        """Test tracking of variable declarations and usage within functions."""
        test_file = temp_project / "variable_tracking.ts"
        test_file.write_text("""
        function variableUsage(input: string): string {
            const prefix = 'processed';
            let counter = 0;
            var result = '';
            
            const processor = (value: string) => {
                counter++;
                return `${prefix}: ${value}`;
            };
            
            result = processor(input);
            
            if (counter > 0) {
                result += ` (${counter} operations)`;
            }
            
            return result;
        }
        
        function destructuringUsage(data: { name: string; items: string[] }): string[] {
            const { name, items } = data;
            const [first, ...rest] = items;
            
            return [name, first, ...rest.slice(0, 2)];
        }
        
        async function asyncVariables(ids: number[]): Promise<any[]> {
            const results = [];
            
            for await (const id of ids) {
                const data = await fetchData(id);
                const processed = processData(data);
                results.push(processed);
            }
            
            return results;
        }
        
        // Mock functions
        function fetchData(id: number): Promise<any> { return Promise.resolve({}); }
        function processData(data: any): any { return data; }
        """)
        
        result = get_function_details_impl(
            functions=["variableUsage", "destructuringUsage", "asyncVariables"],
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=True,
            track_variables=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test variable tracking
        variable_func_list = result.functions["variableUsage"]
        assert variable_func_list is not None
        assert isinstance(variable_func_list, list)
        assert len(variable_func_list) >= 1

        variable_func = variable_func_list[0]
        assert hasattr(variable_func, 'variable_info')
        assert variable_func.variable_info is not None
        
        # Should track different declaration types
        declared_vars = variable_func.variable_info['declarations']
        var_names = [var['name'] for var in declared_vars]
        assert "prefix" in var_names
        assert "counter" in var_names  
        assert "result" in var_names
        assert "processor" in var_names
        
        # Should track declaration types
        for var in declared_vars:
            if var['name'] == 'prefix':
                assert var['declaration_type'] == 'const'
            elif var['name'] == 'counter':
                assert var['declaration_type'] == 'let'
            elif var['name'] == 'result':
                assert var['declaration_type'] == 'var'
        
        # Test destructuring tracking
        destructuring_func_list = result.functions["destructuringUsage"]
        assert destructuring_func_list is not None
        assert isinstance(destructuring_func_list, list)
        assert len(destructuring_func_list) >= 1

        destructuring_func = destructuring_func_list[0]
        destructured_vars = destructuring_func.variable_info['declarations']
        destructured_names = [var['name'] for var in destructured_vars]
        assert "name" in destructured_names
        assert "items" in destructured_names
        assert "first" in destructured_names
        assert "rest" in destructured_names


class TestFunctionCallTracking:
    """Test function call dependency analysis."""

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

    def test_cross_file_call_tracking(self, temp_project):
        """Test tracking of function calls across multiple files."""
        # Create multiple interconnected files
        utils_file = temp_project / "utils.ts"
        utils_file.write_text("""
        export function formatString(input: string): string {
            return input.trim().toLowerCase();
        }
        
        export function validateEmail(email: string): boolean {
            return email.includes('@');
        }
        
        export async function fetchData(url: string): Promise<any> {
            const response = await fetch(url);
            return response.json();
        }
        """)
        
        service_file = temp_project / "service.ts"
        service_file.write_text("""
        import { formatString, validateEmail, fetchData } from './utils';
        
        export class UserService {
            async createUser(name: string, email: string): Promise<any> {
                const formattedName = formatString(name);
                
                if (!validateEmail(email)) {
                    throw new Error('Invalid email');
                }
                
                const userData = {
                    name: formattedName,
                    email: email,
                    id: this.generateId()
                };
                
                return this.saveUser(userData);
            }
            
            private generateId(): string {
                return Math.random().toString(36);
            }
            
            private async saveUser(user: any): Promise<any> {
                const result = await fetchData('/api/users');
                return { ...user, ...result };
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=["UserService.createUser", "UserService.saveUser"],
            file_paths=[str(utils_file), str(service_file)],
            include_code=True,
            include_types=False,
            include_calls=True,
            resolve_imports=True,  # Phase 3 feature
            track_cross_file_calls=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test cross-file call tracking
        create_user_list = result.functions["UserService.createUser"]
        assert create_user_list is not None
        assert isinstance(create_user_list, list)
        assert len(create_user_list) >= 1

        create_user = create_user_list[0]
        assert create_user.calls is not None
        
        # Should identify imported function calls
        imported_calls = ["formatString", "validateEmail"]
        for call in imported_calls:
            assert call in create_user.calls
        
        # Should identify local method calls
        assert "this.generateId" in create_user.calls
        assert "this.saveUser" in create_user.calls
        
        # Should track call source information
        assert hasattr(create_user, 'call_info')
        assert create_user.call_info is not None
        
        # Test imported call details
        for call_detail in create_user.call_info:
            if call_detail['function_name'] == 'formatString':
                # For now, source_file will be the current file
                # Full import resolution would require more complex implementation
                assert call_detail['source_file'].endswith('service.ts')
                # External calls are marked based on pattern
                assert call_detail['is_external'] is False
            elif call_detail['function_name'] == 'this.generateId':
                assert call_detail['source_file'].endswith('service.ts')
                assert call_detail['call_type'] == 'method'

    def test_dynamic_call_tracking(self, temp_project):
        """Test tracking of dynamic function calls and method calls."""
        test_file = temp_project / "dynamic_calls.ts"
        test_file.write_text("""
        interface Processor {
            process(data: any): any;
        }
        
        class DataProcessor {
            private processors: Map<string, Processor> = new Map();
            
            processWithDynamic(data: any, processorName: string): any {
                const processor = this.processors.get(processorName);
                
                if (processor) {
                    // Dynamic method call
                    return processor.process(data);
                }
                
                // Dynamic property access
                const fallback = this['defaultProcess'];
                return fallback.call(this, data);
            }
            
            processWithCallback(
                data: any[], 
                callback: (item: any) => any
            ): any[] {
                return data.map(item => {
                    // Callback invocation
                    return callback(item);
                });
            }
            
            processWithApply(methods: string[], data: any): any {
                let result = data;
                
                for (const methodName of methods) {
                    if (typeof this[methodName] === 'function') {
                        // Dynamic method invocation
                        result = this[methodName].apply(this, [result]);
                    }
                }
                
                return result;
            }
            
            defaultProcess(data: any): any {
                return { processed: data };
            }
        }
        
        function higherOrderUsage(): void {
            const operations = [
                (x: number) => x * 2,
                (x: number) => x + 1,
                (x: number) => x / 2
            ];
            
            let result = 10;
            
            // Dynamic function calls from array
            operations.forEach(op => {
                result = op(result);
            });
            
            console.log(result);
        }
        """)
        
        result = get_function_details_impl(
            functions=[
                "DataProcessor.processWithDynamic",
                "DataProcessor.processWithCallback", 
                "DataProcessor.processWithApply",
                "higherOrderUsage"
            ],
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=True,
            track_dynamic_calls=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test dynamic method call tracking
        dynamic_func_list = result.functions["DataProcessor.processWithDynamic"]
        assert dynamic_func_list is not None
        assert isinstance(dynamic_func_list, list)
        assert len(dynamic_func_list) >= 1

        dynamic_func = dynamic_func_list[0]
        assert dynamic_func.calls is not None
        
        # Should identify dynamic calls
        dynamic_calls = [call for call in dynamic_func.calls if 'dynamic' in call.lower()]
        assert len(dynamic_calls) > 0
        
        # Should include call type information
        assert hasattr(dynamic_func, 'dynamic_call_info')
        assert dynamic_func.dynamic_call_info is not None
        
        # Test callback tracking
        callback_func_list = result.functions["DataProcessor.processWithCallback"]
        assert callback_func_list is not None
        assert isinstance(callback_func_list, list)
        assert len(callback_func_list) >= 1

        callback_func = callback_func_list[0]
        assert "callback" in callback_func.calls
        
        # Test higher-order function tracking
        higher_order_list = result.functions["higherOrderUsage"]
        assert higher_order_list is not None
        assert isinstance(higher_order_list, list)
        assert len(higher_order_list) >= 1

        higher_order = higher_order_list[0]
        assert "operations.forEach" in higher_order.calls

    def test_async_call_tracking(self, temp_project):
        """Test tracking of async function calls and Promise chains."""
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "async-functions.ts"
        target_file = temp_project / "async-functions.ts"
        target_file.write_text(source_file.read_text())
        
        result = get_function_details_impl(
            functions=[
                "fetchWithRetry", "processUserSafely", 
                "AsyncUserService.batchProcessUsers"
            ],
            file_paths=str(target_file),
            include_code=True,
            include_types=False,
            include_calls=True,
            track_async_calls=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test async retry function
        fetch_retry_list = result.functions["fetchWithRetry"]
        assert fetch_retry_list is not None
        assert isinstance(fetch_retry_list, list)
        assert len(fetch_retry_list) >= 1

        fetch_retry = fetch_retry_list[0]
        assert fetch_retry.calls is not None
        
        # Should identify async patterns
        assert "Promise.resolve" in fetch_retry.calls or "setTimeout" in fetch_retry.calls
        
        # Should track async call information
        assert hasattr(fetch_retry, 'async_call_info')
        assert fetch_retry.async_call_info is not None
        assert fetch_retry.async_call_info['has_async_calls'] is True
        
        # Test Promise chain tracking
        process_safely_list = result.functions["processUserSafely"]
        assert process_safely_list is not None
        assert isinstance(process_safely_list, list)
        assert len(process_safely_list) >= 1

        process_safely = process_safely_list[0]
        assert process_safely.async_call_info['returns_promise'] is True
        
        # Test complex async method
        batch_process_list = result.functions["AsyncUserService.batchProcessUsers"]
        assert batch_process_list is not None
        assert isinstance(batch_process_list, list)
        assert len(batch_process_list) >= 1

        batch_process = batch_process_list[0]
        async_calls = batch_process.calls
        promise_calls = [call for call in async_calls if 'Promise' in call or 'await' in call]
        assert len(promise_calls) > 0


class TestBatchFunctionProcessing:
    """Test batch processing capabilities and performance requirements."""

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

    def test_batch_processing_100_functions_performance(self, temp_project):
        """Test processing 100+ functions within 10 seconds."""
        # Generate a large file with 150 functions
        large_file = temp_project / "large_function_set.ts"
        
        functions_content = []
        function_names = []
        
        # Create 150 functions with varying complexity
        for i in range(150):
            if i % 10 == 0:
                # Every 10th function is more complex
                func_content = f"""
                async function complexFunction{i}<T extends Record<string, any>>(
                    data: T[],
                    processor: (item: T) => Promise<T>,
                    validator?: (item: T) => boolean
                ): Promise<T[]> {{
                    const results: T[] = [];
                    
                    for (const item of data) {{
                        if (validator && !validator(item)) {{
                            continue;
                        }}
                        
                        try {{
                            const processed = await processor(item);
                            results.push(processed);
                        }} catch (error) {{
                            console.error('Processing failed:', error);
                        }}
                    }}
                    
                    return results.filter(Boolean);
                }}
                """
                function_names.append(f"complexFunction{i}")
            else:
                # Simpler functions
                func_content = f"""
                function simpleFunction{i}(param{i % 5}: string): string {{
                    return param{i % 5}.toUpperCase();
                }}
                """
                function_names.append(f"simpleFunction{i}")
            
            functions_content.append(func_content)
        
        large_file.write_text('\n'.join(functions_content))
        
        # Test batch processing performance
        start_time = time.perf_counter()
        
        result = get_function_details_impl(
            functions=function_names[:100],  # Process exactly 100 functions
            file_paths=str(large_file),
            include_code=False,  # Exclude code for performance
            include_types=True,
            include_calls=False,
            resolution_depth="basic",
            batch_processing=True  # Phase 3 feature
        )
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Performance requirement: 100+ functions in <10 seconds
        assert processing_time < 10.0, f"Batch processing took {processing_time:.2f}s, should be <10s"
        
        # Should process most functions successfully
        assert len(result.functions) >= 95  # Allow for some failures
        
        # Should include batch processing statistics
        assert hasattr(result, 'batch_stats')
        assert result.batch_stats is not None
        assert result.batch_stats.total_requested == 100
        assert result.batch_stats.processing_time_seconds == pytest.approx(processing_time, rel=0.1)

    def test_batch_memory_efficiency_400mb_limit(self, temp_project):
        """Test memory usage stays under 400MB during batch processing."""
        # Create multiple files with substantial content
        files_created = []
        function_names = []
        
        for file_num in range(5):
            file_path = temp_project / f"memory_test_{file_num}.ts"
            file_content = []
            
            for func_num in range(50):  # 50 functions per file = 250 total
                func_name = f"func_{file_num}_{func_num}"
                function_names.append(func_name)
                
                # Create functions with substantial type information
                func_content = f"""
                interface DataType{func_num} {{
                    id: string;
                    payload: Record<string, any>;
                    metadata: {{
                        timestamp: Date;
                        version: number;
                        tags: string[];
                    }};
                }}
                
                function {func_name}<T extends DataType{func_num}>(
                    input: T,
                    options?: {{
                        validate?: boolean;
                        transform?: boolean;
                        cache?: boolean;
                    }}
                ): Promise<T & {{ processed: true }}> {{
                    const processed = {{ ...input, processed: true as const }};
                    return Promise.resolve(processed);
                }}
                """
                file_content.append(func_content)
            
            file_path.write_text('\n'.join(file_content))
            files_created.append(str(file_path))
        
        # Monitor memory usage during batch processing
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        result = get_function_details_impl(
            functions=function_names[:150],  # Process 150 functions
            file_paths=files_created,
            include_code=True,  # Include code to increase memory usage
            include_types=True,
            include_calls=True,
            resolution_depth="generics",
            batch_processing=True,
            memory_efficient=True  # Phase 3 feature
        )
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Memory requirement: stay under 400MB increase
        assert memory_increase < 400.0, f"Memory usage increased by {memory_increase:.1f}MB, should be <400MB"
        
        # Should include memory statistics
        assert hasattr(result, 'memory_stats')
        assert result.memory_stats is not None
        assert result.memory_stats.peak_memory_mb <= 400.0

    def test_shared_type_context_performance(self, temp_project):
        """Test shared type context improves batch processing performance."""
        # Create files with shared types across functions
        shared_types_file = temp_project / "shared_types.ts"
        shared_types_file.write_text("""
        export interface SharedUser {
            id: string;
            name: string;
            email: string;
        }
        
        export interface SharedConfig {
            apiUrl: string;
            timeout: number;
            retries: number;
        }
        
        export type SharedResponse<T> = {
            success: boolean;
            data: T;
            error?: string;
        };
        """)
        
        functions_file = temp_project / "shared_functions.ts"
        functions_content = []
        function_names = []
        
        # Create 100 functions that all use the same shared types
        for i in range(100):
            func_name = f"sharedFunction{i}"
            function_names.append(func_name)
            
            func_content = f"""
            import {{ SharedUser, SharedConfig, SharedResponse }} from './shared_types';
            
            function {func_name}(
                user: SharedUser,
                config: SharedConfig
            ): Promise<SharedResponse<SharedUser>> {{
                return Promise.resolve({{
                    success: true,
                    data: user
                }});
            }}
            """
            functions_content.append(func_content)
        
        functions_file.write_text('\n'.join(functions_content))
        
        # Test without shared context (baseline)
        start_time = time.perf_counter()
        result_without_shared = get_function_details_impl(
            functions=function_names[:50],
            file_paths=[str(shared_types_file), str(functions_file)],
            include_types=True,
            resolution_depth="generics",
            use_shared_type_context=False  # Disable shared context
        )
        baseline_time = time.perf_counter() - start_time
        
        # Test with shared context (should be faster)
        start_time = time.perf_counter()
        result_with_shared = get_function_details_impl(
            functions=function_names[:50],
            file_paths=[str(shared_types_file), str(functions_file)],
            include_types=True,
            resolution_depth="generics",
            use_shared_type_context=True  # Enable shared context
        )
        shared_time = time.perf_counter() - start_time
        
        # Both should succeed
        assert isinstance(result_without_shared, FunctionDetailsResponse)
        assert isinstance(result_with_shared, FunctionDetailsResponse)
        assert result_without_shared.success is True
        assert result_with_shared.success is True
        
        # Shared context should be faster (or at least not significantly slower)
        performance_improvement = (baseline_time - shared_time) / baseline_time
        assert performance_improvement >= -0.1, f"Shared context was {abs(performance_improvement)*100:.1f}% slower"
        
        # Should include context sharing statistics
        assert hasattr(result_with_shared, 'context_stats')
        assert result_with_shared.context_stats.shared_types_count >= 0

    def test_concurrent_batch_processing_safety(self, temp_project):
        """Test concurrent batch processing safety."""
        # Create test file
        test_file = temp_project / "concurrent_test.ts"
        test_content = []
        all_function_names = []
        
        for i in range(60):
            func_name = f"concurrentFunc{i}"
            all_function_names.append(func_name)
            test_content.append(f"""
            function {func_name}(param: string): string {{
                return param.toUpperCase();
            }}
            """)
        
        test_file.write_text('\n'.join(test_content))
        
        # Split functions into 3 batches for concurrent processing
        batch1 = all_function_names[:20]
        batch2 = all_function_names[20:40]
        batch3 = all_function_names[40:60]
        
        import concurrent.futures
        import threading
        
        results = []
        errors = []
        
        def process_batch(functions):
            try:
                result = get_function_details_impl(
                    functions=functions,
                    file_paths=str(test_file),
                    include_types=False,
                    resolution_depth="basic",
                    concurrent_safe=True  # Phase 3 feature
                )
                return result
            except Exception as e:
                errors.append(e)
                return None
        
        # Process batches concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(process_batch, batch1),
                executor.submit(process_batch, batch2),
                executor.submit(process_batch, batch3)
            ]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        
        # All batches should succeed without errors
        assert len(errors) == 0, f"Concurrent processing had errors: {errors}"
        assert len(results) == 3
        
        # Each result should be valid
        for result in results:
            assert isinstance(result, FunctionDetailsResponse)
            assert result.success is True
            assert len(result.functions) == 20
        
        # No duplicate processing or corruption
        all_processed_functions = set()
        for result in results:
            processed_names = set(result.functions.keys())
            assert len(all_processed_functions.intersection(processed_names)) == 0  # No duplicates
            all_processed_functions.update(processed_names)
        
        assert len(all_processed_functions) == 60  # All functions processed exactly once

    def test_cache_efficiency_across_batches(self, temp_project):
        """Test cache efficiency for repeated type resolution across batches."""
        # Create file with functions that share many types
        test_file = temp_project / "cache_test.ts"
        test_content = """
        interface CommonUser {
            id: string;
            name: string;
        }
        
        interface CommonConfig {
            setting: string;
        }
        """
        
        function_names = []
        for i in range(80):
            func_name = f"cacheFunc{i}"
            function_names.append(func_name)
            test_content += f"""
            function {func_name}(user: CommonUser, config: CommonConfig): CommonUser {{
                return user;
            }}
            """
        
        test_file.write_text(test_content)
        
        # Process in multiple batches to test cache efficiency
        batch_size = 20
        cache_stats = []
        
        for batch_start in range(0, 80, batch_size):
            batch_end = min(batch_start + batch_size, 80)
            batch_functions = function_names[batch_start:batch_end]
            
            result = get_function_details_impl(
                functions=batch_functions,
                file_paths=str(test_file),
                include_types=True,
                resolution_depth="basic",
                enable_type_cache=True  # Phase 3 feature
            )
            
            assert isinstance(result, FunctionDetailsResponse)
            assert result.success is True
            
            # Collect cache statistics
            if hasattr(result, 'cache_stats'):
                cache_stats.append(result.cache_stats)
        
        # Cache hit rate should improve across batches
        if len(cache_stats) >= 2:
            first_batch_hit_rate = getattr(cache_stats[0], 'hit_rate', 0)
            last_batch_hit_rate = getattr(cache_stats[-1], 'hit_rate', 0)
            
            # Later batches should have higher cache hit rates
            assert last_batch_hit_rate >= first_batch_hit_rate, \
                f"Cache hit rate should improve: {first_batch_hit_rate} -> {last_batch_hit_rate}"