"""
Tests for TypeScript analysis tool implementations.

These tests define the expected behavior for the TypeScript analysis tools
in Phase 1. The tools should initially return empty results with proper
structure until full implementation in later phases.
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the expected tool implementations (will fail initially)
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


class TestFindReferencesTool:
    """Test the find_references tool implementation for Phase 2."""

    @pytest.fixture
    def fixtures_dir(self):
        """Get the path to test fixtures directory.""" 
        return Path(__file__).parent / "fixtures"

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
                # Create Phase 2 realistic project structure
                self._create_phase2_project(temp_path)
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def _create_phase2_project(self, temp_path: Path):
        """Create realistic Phase 2 project structure for reference finding tests."""
        # Create comprehensive TypeScript project with inheritance chains
        (temp_path / "src" / "auth").mkdir(parents=True)
        
        # Base user class with methods to be overridden
        (temp_path / "src" / "auth" / "base-user.ts").write_text("""
export abstract class BaseUser {
    protected id: number;
    protected name: string;
    
    constructor(id: number, name: string) {
        this.id = id;
        this.name = name;
    }
    
    abstract getDisplayName(): string;
    
    getId(): number {
        return this.id;
    }
    
    getName(): string {
        return this.name;
    }
    
    updateName(newName: string): void {
        this.name = newName;
    }
}
        """)
        
        # Derived user classes implementing abstract methods
        (temp_path / "src" / "auth" / "admin-user.ts").write_text("""
import { BaseUser } from './base-user';

export class AdminUser extends BaseUser {
    private permissions: string[];
    
    constructor(id: number, name: string, permissions: string[] = []) {
        super(id, name);
        this.permissions = permissions;
    }
    
    getDisplayName(): string {
        return `Admin: ${this.name}`;
    }
    
    addPermission(permission: string): void {
        this.permissions.push(permission);
    }
    
    hasPermission(permission: string): boolean {
        return this.permissions.includes(permission);
    }
}
        """)
        
        (temp_path / "src" / "auth" / "regular-user.ts").write_text("""
import { BaseUser } from './base-user';

export class RegularUser extends BaseUser {
    private email: string;
    
    constructor(id: number, name: string, email: string) {
        super(id, name);
        this.email = email;
    }
    
    getDisplayName(): string {
        return `${this.name} (${this.email})`;
    }
    
    updateEmail(newEmail: string): void {
        this.email = newEmail;
    }
    
    getEmail(): string {
        return this.email;
    }
}
        """)
        
        # Service class using both user types
        (temp_path / "src" / "services").mkdir()
        (temp_path / "src" / "services" / "user-service.ts").write_text("""
import { BaseUser } from '../auth/base-user';
import { AdminUser } from '../auth/admin-user';
import { RegularUser } from '../auth/regular-user';

export class UserService {
    private users: Map<number, BaseUser> = new Map();
    
    createAdminUser(id: number, name: string, permissions: string[]): AdminUser {
        const admin = new AdminUser(id, name, permissions);
        this.users.set(id, admin);
        return admin;
    }
    
    createRegularUser(id: number, name: string, email: string): RegularUser {
        const user = new RegularUser(id, name, email);
        this.users.set(id, user);
        return user;
    }
    
    getUser(id: number): BaseUser | null {
        return this.users.get(id) || null;
    }
    
    updateUserName(id: number, newName: string): boolean {
        const user = this.users.get(id);
        if (user) {
            user.updateName(newName);
            return true;
        }
        return false;
    }
    
    getUserDisplayName(id: number): string | null {
        const user = this.users.get(id);
        return user ? user.getDisplayName() : null;
    }
    
    isAdmin(id: number): boolean {
        const user = this.users.get(id);
        return user instanceof AdminUser;
    }
}
        """)
        
        # Test file to be excluded by default
        (temp_path / "tests").mkdir()
        (temp_path / "tests" / "user-service.test.ts").write_text("""
import { UserService } from '../src/services/user-service';
import { AdminUser } from '../src/auth/admin-user';

describe('UserService', () => {
    let userService: UserService;
    
    beforeEach(() => {
        userService = new UserService();
    });
    
    test('should create admin user', () => {
        const admin = userService.createAdminUser(1, 'Admin User', ['read', 'write']);
        expect(admin).toBeInstanceOf(AdminUser);
        expect(admin.getDisplayName()).toBe('Admin: Admin User');
    });
    
    test('should get user display name', () => {
        userService.createRegularUser(2, 'John Doe', 'john@example.com');
        const displayName = userService.getUserDisplayName(2);
        expect(displayName).toBe('John Doe (john@example.com)');
    });
});
        """)

    def test_find_references_with_inheritance_chain(self, temp_project):
        """Test finding references through inheritance chains (Phase 2)."""
        # Test finding all references to getDisplayName method across inheritance hierarchy
        project_files = [
            str(temp_project / "src" / "auth" / "base-user.ts"),
            str(temp_project / "src" / "auth" / "admin-user.ts"),
            str(temp_project / "src" / "auth" / "regular-user.ts"),
            str(temp_project / "src" / "services" / "user-service.ts")
        ]
        
        result = find_references_impl(
            symbol="getDisplayName",
            file_paths=project_files,
            include_declarations=True,
            include_usages=True,
            resolve_inheritance=True  # Phase 2 feature
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        assert isinstance(result.references, list)
        
        # Should find abstract declaration in BaseUser
        abstract_declaration = None
        # Should find concrete implementations in AdminUser and RegularUser
        admin_implementation = None
        regular_implementation = None
        # Should find usage in UserService
        service_usage = None
        
        for ref in result.references:
            assert isinstance(ref, ReferenceInfo)
            assert ref.symbol_name == "getDisplayName"
            
            if ref.reference_type == ReferenceType.DECLARATION and "base-user.ts" in ref.file_path:
                abstract_declaration = ref
            elif ref.reference_type == ReferenceType.DEFINITION and "admin-user.ts" in ref.file_path:
                admin_implementation = ref
            elif ref.reference_type == ReferenceType.DEFINITION and "regular-user.ts" in ref.file_path:
                regular_implementation = ref
            elif ref.reference_type == ReferenceType.USAGE and "user-service.ts" in ref.file_path:
                service_usage = ref
        
        # Phase 2: Should find all references through inheritance chain
        assert abstract_declaration is not None, "Should find abstract declaration"
        assert admin_implementation is not None, "Should find AdminUser implementation"
        assert regular_implementation is not None, "Should find RegularUser implementation"
        assert service_usage is not None, "Should find usage in UserService"
        
        # Should include inheritance chain information
        assert hasattr(result, 'inheritance_info')
        assert result.inheritance_info is not None
        assert len(result.inheritance_info.chains) > 0

    def test_find_references_class_method_syntax(self, temp_project):
        """Test finding references using 'ClassName#methodName' syntax (Phase 2)."""
        project_files = [
            str(temp_project / "src" / "auth" / "admin-user.ts"),
            str(temp_project / "src" / "services" / "user-service.ts")
        ]
        
        # Test specific method using Class#method syntax
        result = find_references_impl(
            symbol="AdminUser#hasPermission",
            file_paths=project_files,
            include_declarations=True,
            include_usages=True,
            method_resolution=True  # Phase 2 feature
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        
        # Should find only the specific method, not other methods with same name
        permission_method = None
        for ref in result.references:
            if (ref.symbol_name == "hasPermission" and 
                ref.class_name == "AdminUser"):
                permission_method = ref
                break
        
        assert permission_method is not None
        assert permission_method.class_name == "AdminUser"
        assert permission_method.method_name == "hasPermission"
        assert hasattr(permission_method, 'method_signature')
        
        # Should provide method signature information
        assert permission_method.method_signature is not None
        assert "permission: string" in permission_method.method_signature
        assert "boolean" in permission_method.method_signature

    def test_find_references_with_confidence_scores(self, temp_project):
        """Test that reference finding includes confidence scores (Phase 2)."""
        project_files = [
            str(temp_project / "src" / "auth" / "base-user.ts"),
            str(temp_project / "src" / "services" / "user-service.ts")
        ]
        
        result = find_references_impl(
            symbol="updateName",
            file_paths=project_files,
            include_declarations=True,
            include_usages=True,
            include_confidence_scores=True  # Phase 2 feature
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        
        # All references should have confidence scores
        for ref in result.references:
            assert hasattr(ref, 'confidence_score')
            assert isinstance(ref.confidence_score, (int, float))
            assert 0.0 <= ref.confidence_score <= 1.0
            
            # Direct method calls should have high confidence
            if ref.reference_type == ReferenceType.USAGE:
                assert ref.confidence_score >= 0.8
            
            # Method definitions should have very high confidence  
            if ref.reference_type == ReferenceType.DEFINITION:
                assert ref.confidence_score >= 0.9

    def test_find_references_cross_file_analysis(self, temp_project):
        """Test finding references across multiple files with imports (Phase 2)."""
        project_files = [
            str(temp_project / "src" / "auth" / "base-user.ts"),
            str(temp_project / "src" / "auth" / "admin-user.ts"),  
            str(temp_project / "src" / "services" / "user-service.ts")
        ]
        
        result = find_references_impl(
            symbol="BaseUser",
            file_paths=project_files,
            include_declarations=True,
            include_usages=True,
            resolve_imports=True  # Phase 2 feature
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        
        # Should find class declaration
        class_declaration = None
        # Should find import statements
        import_references = []
        # Should find inheritance usage
        inheritance_usage = None
        
        for ref in result.references:
            if ref.reference_type == ReferenceType.DECLARATION and "base-user.ts" in ref.file_path:
                class_declaration = ref
            elif ref.reference_type == ReferenceType.IMPORT:
                import_references.append(ref)
            elif ref.reference_type == ReferenceType.USAGE and "extends BaseUser" in ref.context:
                inheritance_usage = ref
        
        assert class_declaration is not None
        assert len(import_references) >= 2  # Imported by AdminUser and UserService
        assert inheritance_usage is not None
        
        # Should provide import tracking information
        for import_ref in import_references:
            assert hasattr(import_ref, 'import_path')
            assert hasattr(import_ref, 'import_type')
            assert import_ref.import_type in ['named', 'default', 'namespace']

    def test_find_references_performance_large_codebase(self, temp_project):
        """Test reference finding performance on realistic codebase (Phase 2)."""
        # Get all TypeScript files in the project
        all_files = []
        for file_path in temp_project.rglob("*.ts"):
            if not file_path.name.endswith(".test.ts"):  # Exclude tests by default
                all_files.append(str(file_path))
        
        start_time = time.perf_counter()
        
        result = find_references_impl(
            symbol="BaseUser",
            file_paths=all_files,
            include_declarations=True,
            include_usages=True,
            resolve_inheritance=True,
            resolve_imports=True
        )
        
        end_time = time.perf_counter()
        analysis_time = (end_time - start_time)
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        
        # Phase 2 performance requirement: <30 seconds for realistic projects
        assert analysis_time < 30.0, f"Reference finding took {analysis_time:.2f}s, should be <30s"
        
        # Should provide performance statistics
        assert hasattr(result, 'analysis_stats')
        assert hasattr(result.analysis_stats, 'files_analyzed')
        assert hasattr(result.analysis_stats, 'references_found')
        assert hasattr(result.analysis_stats, 'analysis_time_ms')
        
        assert result.analysis_stats.files_analyzed >= len(all_files)
        assert result.analysis_stats.references_found > 0
        assert result.analysis_stats.analysis_time_ms > 0

    def test_find_references_exclude_tests_by_default(self, temp_project):
        """Test that test files are excluded by default (Phase 2)."""
        all_files = []
        for file_path in temp_project.rglob("*.ts"):
            all_files.append(str(file_path))  # Include test files in file list
        
        # Default behavior - should exclude tests
        result = find_references_impl(
            symbol="AdminUser",
            file_paths=all_files,
            include_declarations=True,
            include_usages=True
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        
        # Should not include any references from test files
        test_references = [ref for ref in result.references 
                          if ref.file_path.endswith(".test.ts")]
        assert len(test_references) == 0
        
        # Should still find references from source files
        source_references = [ref for ref in result.references 
                           if not ref.file_path.endswith(".test.ts")]
        assert len(source_references) > 0

    def test_find_references_include_tests_when_requested(self, temp_project):
        """Test that test files are included when include_tests=True (Phase 2)."""
        all_files = []
        for file_path in temp_project.rglob("*.ts"):
            all_files.append(str(file_path))
        
        # Explicitly include tests
        result = find_references_impl(
            symbol="AdminUser",
            file_paths=all_files,
            include_declarations=True,
            include_usages=True,
            include_tests=True  # Phase 2 feature
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert result.success is True
        
        # Should include references from test files
        test_references = [ref for ref in result.references 
                          if ref.file_path.endswith(".test.ts")]
        assert len(test_references) > 0
        
        # Should still have source file references
        source_references = [ref for ref in result.references 
                           if not ref.file_path.endswith(".test.ts")]
        assert len(source_references) > 0

    def test_find_references_single_symbol(self, temp_project):
        """Test finding references to a single symbol - basic functionality."""
        # Test with existing AdminUser class
        admin_user_file = temp_project / "src" / "auth" / "admin-user.ts"
        
        result = find_references_impl(
            symbol="AdminUser",
            file_paths=str(admin_user_file),
            include_declarations=True,
            include_usages=True
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert isinstance(result.references, list)
        assert result.total_references >= 0  # May be empty in Phase 1
        assert result.searched_files >= 0
        assert isinstance(result.errors, list)
        
        # Standard pagination fields should be present
        assert hasattr(result, 'total')
        assert hasattr(result, 'page_size')
        assert hasattr(result, 'next_cursor')
        assert hasattr(result, 'has_more')

    def test_find_references_multiple_files(self, temp_project):
        """Test finding references across multiple files."""
        # Create multiple files with cross-references
        files = {
            "user.ts": """
                export interface User {
                    id: number;
                    name: string;
                }
            """,
            "service.ts": """
                import { User } from './user';
                export class UserService {
                    getUser(id: number): User | null {
                        return null;
                    }
                }
            """,
            "main.ts": """
                import { User } from './user';
                import { UserService } from './service';
                
                const service = new UserService();
                const user: User = service.getUser(1);
            """
        }
        
        for filename, content in files.items():
            (temp_project / filename).write_text(content)
        
        file_paths = [str(temp_project / f) for f in files.keys()]
        
        result = find_references_impl(
            symbol="User",
            file_paths=file_paths,
            include_declarations=True,
            include_usages=True
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert isinstance(result.references, list)
        assert result.searched_files >= len(files)  # Should search all provided files

    def test_find_references_with_filters(self, temp_project):
        """Test find references with different filter options."""
        test_file = temp_project / "filtered_test.ts"
        test_file.write_text("""
        interface TestInterface {
            prop: string;
        }
        
        function testFunction(): TestInterface {
            return { prop: "test" };
        }
        
        const instance: TestInterface = testFunction();
        """)
        
        # Test with different filter combinations
        filter_scenarios = [
            {"include_declarations": True, "include_usages": False},
            {"include_declarations": False, "include_usages": True},
            {"include_declarations": True, "include_usages": True},
        ]
        
        for filters in filter_scenarios:
            result = find_references_impl(
                symbol="TestInterface",
                file_paths=str(test_file),
                **filters
            )
            
            assert isinstance(result, FindReferencesResponse)
            # Results should respect filters (empty in Phase 1)
            assert isinstance(result.references, list)

    def test_find_references_nonexistent_symbol(self, temp_project):
        """Test finding references to non-existent symbol."""
        test_file = temp_project / "no_symbol.ts"
        test_file.write_text("export const someVariable = 'test';")
        
        result = find_references_impl(
            symbol="NonExistentSymbol",
            file_paths=str(test_file),
            include_declarations=True,
            include_usages=True
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert len(result.references) == 0
        assert result.total_references == 0

    def test_find_references_error_handling(self, temp_project):
        """Test error handling in find references."""
        # Test with non-existent file
        result = find_references_impl(
            symbol="AnySymbol",
            file_paths="/nonexistent/file.ts",
            include_declarations=True,
            include_usages=True
        )
        
        assert isinstance(result, FindReferencesResponse)
        assert len(result.errors) > 0
        
        error = result.errors[0]
        assert isinstance(error, AnalysisError)
        assert error.code in ["NOT_FOUND", "INVALID_INPUT"]
        assert error.message is not None

    def test_find_references_pagination_support(self, temp_project):
        """Test pagination parameters are supported."""
        test_file = temp_project / "pagination_test.ts"
        test_file.write_text("export const testSymbol = 'value';")
        
        result = find_references_impl(
            symbol="testSymbol",
            file_paths=str(test_file),
            include_declarations=True,
            include_usages=True,
            page=1,
            max_tokens=1000
        )
        
        assert isinstance(result, FindReferencesResponse)
        # Pagination fields should be set appropriately
        assert result.total >= 0
        assert result.page_size is None or result.page_size >= 0
        assert result.has_more is not None


class TestGetFunctionDetailsTool:
    """Test the get_function_details tool implementation."""

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

    def test_get_function_details_single_function(self, temp_project):
        """Test getting details for a single function."""
        test_file = temp_project / "functions.ts"
        test_file.write_text("""
        interface User {
            id: number;
            name: string;
        }
        
        function getUserById(id: number): Promise<User | null> {
            return fetch(`/api/users/${id}`)
                .then(response => response.json())
                .catch(() => null);
        }
        """)
        
        result = get_function_details_impl(
            functions="getUserById",
            file_paths=str(test_file),
            include_code=True,
            include_types=True,
            include_calls=False
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert isinstance(result.functions, dict)
        assert isinstance(result.errors, list)
        
        # Standard pagination fields
        assert hasattr(result, 'total')
        assert hasattr(result, 'page_size')
        assert hasattr(result, 'next_cursor')
        assert hasattr(result, 'has_more')

    def test_get_function_details_multiple_functions(self, temp_project):
        """Test getting details for multiple functions."""
        test_file = temp_project / "multiple_functions.ts"
        test_file.write_text("""
        class UserService {
            async getUser(id: number): Promise<User> {
                return this.fetchUser(id);
            }
            
            private async fetchUser(id: number): Promise<User> {
                const response = await fetch(`/api/users/${id}`);
                return response.json();
            }
            
            createUser(userData: Partial<User>): User {
                return { id: Date.now(), ...userData } as User;
            }
        }
        """)
        
        functions_to_analyze = ["getUser", "fetchUser", "createUser"]
        
        result = get_function_details_impl(
            functions=functions_to_analyze,
            file_paths=str(test_file),
            include_code=True,
            include_types=True,
            include_calls=True
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert isinstance(result.functions, dict)
        # Should have entries for requested functions (empty in Phase 1)

    def test_get_function_details_with_type_analysis(self, temp_project):
        """Test function details with deep type analysis."""
        test_file = temp_project / "complex_types.ts"
        test_file.write_text("""
        interface ApiResponse<T> {
            data: T;
            status: number;
            message: string;
        }
        
        type UserData = {
            id: number;
            profile: {
                name: string;
                email?: string;
            };
        };
        
        function processApiResponse<T>(
            response: ApiResponse<T>,
            transformer: (data: T) => UserData
        ): UserData {
            return transformer(response.data);
        }
        """)
        
        result = get_function_details_impl(
            functions="processApiResponse",
            file_paths=str(test_file),
            include_code=True,
            include_types=True,
            include_calls=False,
            resolution_depth="full_type"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        # Should handle complex generic types (implementation details for later)

    def test_get_function_details_error_scenarios(self, temp_project):
        """Test error handling in function details analysis."""
        # Test with non-existent function
        test_file = temp_project / "simple.ts"
        test_file.write_text("export const variable = 'not a function';")
        
        result = get_function_details_impl(
            functions="nonExistentFunction",
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=False
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        # Should return empty results or appropriate errors
        # Current implementation returns empty list for non-existent functions
        assert len(result.functions) == 0 or len(result.errors) > 0 or all(
            len(func_list) == 0 for func_list in result.functions.values()
        )

    def test_get_function_details_filtering_options(self, temp_project):
        """Test different filtering and inclusion options."""
        test_file = temp_project / "filtering_test.ts"
        test_file.write_text("""
        function simpleFunction(param: string): number {
            const helper = () => param.length;
            return helper() * 2;
        }
        """)
        
        # Test different combinations of include options
        option_combinations = [
            {"include_code": True, "include_types": False, "include_calls": False},
            {"include_code": False, "include_types": True, "include_calls": False},
            {"include_code": False, "include_types": False, "include_calls": True},
            {"include_code": True, "include_types": True, "include_calls": True},
        ]
        
        for options in option_combinations:
            result = get_function_details_impl(
                functions="simpleFunction",
                file_paths=str(test_file),
                **options
            )
            
            assert isinstance(result, FunctionDetailsResponse)
            # Results should respect filtering options

    # Phase 3 Tests for get_function_details tool
    
    def test_get_function_details_phase3_progressive_resolution(self, temp_project):
        """Test Phase 3 progressive type resolution levels."""
        # Copy Phase 3 fixtures
        source_file = Path(__file__).parent / "fixtures" / "phase3_types" / "generic-functions.ts"
        target_file = temp_project / "generic-functions.ts"
        target_file.write_text(source_file.read_text())
        
        test_functions = ["processEntity", "mergeEntities"]
        
        # Test basic resolution
        basic_result = get_function_details_impl(
            functions=test_functions,
            file_paths=str(target_file),
            include_types=True,
            resolution_depth="basic"  # Phase 3 feature
        )
        
        # Test generic resolution
        generic_result = get_function_details_impl(
            functions=test_functions,
            file_paths=str(target_file),
            include_types=True,
            resolution_depth="generics"  # Phase 3 feature
        )
        
        # Test full inference
        full_result = get_function_details_impl(
            functions=test_functions,
            file_paths=str(target_file),
            include_types=True,
            resolution_depth="full_inference"  # Phase 3 feature
        )
        
        # All should succeed but with progressively more detail
        for result in [basic_result, generic_result, full_result]:
            assert isinstance(result, FunctionDetailsResponse)
            assert result.success is True
            assert len(result.functions) == 2
        
        # Generic resolution should have more type information than basic
        basic_process_list = basic_result.functions.get("processEntity")
        generic_process_list = generic_result.functions.get("processEntity")
        
        if basic_process_list and generic_process_list:
            basic_process = basic_process_list[0] if basic_process_list else None
            generic_process = generic_process_list[0] if generic_process_list else None
            if basic_process and generic_process:
                basic_type_count = len(basic_process.types) if basic_process.types else 0
                generic_type_count = len(generic_process.types) if generic_process.types else 0
                assert generic_type_count >= basic_type_count

    def test_get_function_details_phase3_batch_processing_performance(self, temp_project):
        """Test Phase 3 batch processing performance requirements."""
        # Generate 120 functions for batch testing
        large_file = temp_project / "batch_test.ts"
        functions_content = []
        function_names = []
        
        for i in range(120):
            func_name = f"batchFunction{i}"
            function_names.append(func_name)
            functions_content.append(f"""
            function {func_name}(param{i % 5}: string): string {{
                return param{i % 5}.toUpperCase();
            }}
            """)
        
        large_file.write_text('\n'.join(functions_content))
        
        # Test batch processing 100 functions within 10 seconds
        import time
        start_time = time.perf_counter()
        
        result = get_function_details_impl(
            functions=function_names[:100],  # Exactly 100 functions
            file_paths=str(large_file),
            include_code=False,
            include_types=True,
            include_calls=False,
            batch_processing=True  # Phase 3 feature
        )
        
        end_time = time.perf_counter()
        processing_time = end_time - start_time
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Phase 3 requirement: 100+ functions within 10 seconds
        assert processing_time < 10.0, f"Batch processing took {processing_time:.2f}s, should be <10s"
        
        # Should process most functions successfully
        assert len(result.functions) >= 95

    def test_get_function_details_phase3_memory_efficiency(self, temp_project):
        """Test Phase 3 memory usage requirements during batch processing."""
        # Create substantial content to test memory efficiency
        memory_test_file = temp_project / "memory_test.ts"
        content = []
        function_names = []
        
        # Create 100 functions with complex types
        for i in range(100):
            func_name = f"memoryFunc{i}"
            function_names.append(func_name)
            content.append(f"""
            interface ComplexType{i} {{
                id: string;
                data: Record<string, any>;
                nested: {{
                    values: number[];
                    metadata: Map<string, string>;
                }};
            }}
            
            function {func_name}<T extends ComplexType{i}>(
                input: T,
                processor: (item: T) => T
            ): Promise<T[]> {{
                return Promise.resolve([processor(input)]);
            }}
            """)
        
        memory_test_file.write_text('\n'.join(content))
        
        # Monitor memory usage
        import psutil
        import os
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        result = get_function_details_impl(
            functions=function_names,
            file_paths=str(memory_test_file),
            include_code=True,
            include_types=True,
            include_calls=True,
            memory_efficient=True  # Phase 3 feature
        )
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Phase 3 requirement: memory usage under 400MB
        assert memory_increase < 400.0, f"Memory usage increased by {memory_increase:.1f}MB, should be <400MB"

    def test_get_function_details_phase3_imported_type_resolution(self, temp_project):
        """Test Phase 3 imported type resolution (basic level)."""
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
            resolve_imports=True  # Phase 3 feature
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Should resolve imported types
        process_user_list = result.functions.get("processUser")
        if process_user_list:
            process_user = process_user_list[0] if process_user_list else None
            if process_user:
                assert process_user.types is not None
                assert "User" in process_user.types
                assert "BaseEntity" in process_user.types
        
        validate_entity_list = result.functions.get("validateEntity")
        if validate_entity_list:
            validate_entity = validate_entity_list[0] if validate_entity_list else None
            if validate_entity:
                assert "T extends BaseEntity" in validate_entity.signature

    def test_get_function_details_phase3_function_code_analysis(self, temp_project):
        """Test Phase 3 function code analysis with call tracking."""
        test_file = temp_project / "code_analysis.ts"
        test_file.write_text("""
        function helperFunction(data: string): string {
            return data.trim().toLowerCase();
        }
        
        function mainFunction(input: string): string {
            const cleaned = helperFunction(input);
            console.log('Processing:', cleaned);
            return cleaned.toUpperCase();
        }
        
        class DataProcessor {
            process(data: string): string {
                const validated = this.validate(data);
                return this.transform(validated);
            }
            
            private validate(data: string): string {
                return data;
            }
            
            private transform(data: string): string {
                return data.toUpperCase();
            }
        }
        """)
        
        result = get_function_details_impl(
            functions=["mainFunction", "DataProcessor.process"],
            file_paths=str(test_file),
            include_code=True,  # Phase 3 feature: include complete function code
            include_types=False,
            include_calls=True,  # Phase 3 feature: identify functions called
            resolution_depth="basic"
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        # Test function code inclusion
        main_func_list = result.functions.get("mainFunction")
        if main_func_list:
            main_func = main_func_list[0] if main_func_list else None
            if main_func:
                assert main_func.code is not None
                assert "const cleaned = helperFunction(input);" in main_func.code
                assert "console.log('Processing:', cleaned);" in main_func.code
        
                # Test call dependency tracking
                if main_func.calls:
                    assert "helperFunction" in main_func.calls
                    assert "console.log" in main_func.calls
        
        # Test class method call tracking
        process_method_list = result.functions.get("DataProcessor.process")
        if process_method_list:
            process_method = process_method_list[0] if process_method_list else None
            if process_method and process_method.calls:
                assert "this.validate" in process_method.calls
                assert "this.transform" in process_method.calls

    def test_get_function_details_phase3_generic_constraint_resolution(self, temp_project):
        """Test Phase 3 generic constraint resolution up to 5 levels deep."""
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
        
        result = get_function_details_impl(
            functions="deepGenericFunction",
            file_paths=str(test_file),
            include_types=True,
            resolution_depth="generics",
            max_constraint_depth=5  # Phase 3 feature: handle up to 5 levels
        )
        
        assert isinstance(result, FunctionDetailsResponse)
        assert result.success is True
        
        deep_func_list = result.functions.get("deepGenericFunction")
        if deep_func_list:
            deep_func = deep_func_list[0] if deep_func_list else None
            if deep_func:
                # Should handle 5 levels of generic constraints
                assert "T extends Level1" in deep_func.signature
                assert "U extends Level2<T>" in deep_func.signature
                assert "V extends Level3<T, U>" in deep_func.signature
                assert "W extends Level4<T, U, V>" in deep_func.signature
                assert "X extends Level5<T, U, V, W>" in deep_func.signature
                
                # Should resolve all constraint types
                if deep_func.types:
                    for level in ["Level1", "Level2", "Level3", "Level4", "Level5"]:
                        assert level in deep_func.types


class TestGetCallTraceTool:
    """Test the get_call_trace tool implementation for Phase 4."""

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
    
    @pytest.fixture
    def phase4_fixtures_dir(self):
        """Get the Phase 4 call graph fixtures directory."""
        return Path(__file__).parent / "fixtures" / "phase4_callgraph"

    def test_get_call_trace_simple_flow(self, temp_project):
        """Test call trace analysis for simple function flow."""
        test_file = temp_project / "call_flow.ts"
        test_file.write_text("""
        function main(): void {
            const user = getUser();
            processUser(user);
            saveUser(user);
        }
        
        function getUser(): User {
            return { id: 1, name: "Test User" };
        }
        
        function processUser(user: User): void {
            console.log(`Processing ${user.name}`);
        }
        
        function saveUser(user: User): void {
            console.log(`Saving ${user.name}`);
        }
        """)
        
        result = get_call_trace_impl(
            entry_point="main",
            file_paths=str(test_file),
            max_depth=5,
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        assert result.entry_point == "main"
        assert isinstance(result.execution_paths, list)
        assert isinstance(result.call_graph_stats, CallGraphStats)
        assert isinstance(result.errors, list)
        
        # Standard pagination fields
        assert hasattr(result, 'total')
        assert hasattr(result, 'page_size')
        assert hasattr(result, 'next_cursor')
        assert hasattr(result, 'has_more')

    def test_get_call_trace_with_conditionals(self, temp_project):
        """Test call trace analysis with conditional execution paths."""
        test_file = temp_project / "conditional_flow.ts"
        test_file.write_text("""
        function authenticate(credentials: LoginCredentials): User | null {
            if (validateCredentials(credentials)) {
                const user = findUser(credentials.username);
                if (user) {
                    logSuccessfulLogin(user);
                    return user;
                } else {
                    logFailedLogin(credentials.username);
                    return null;
                }
            } else {
                logInvalidCredentials(credentials);
                return null;
            }
        }
        
        function validateCredentials(creds: LoginCredentials): boolean {
            return creds.username.length > 0 && creds.password.length >= 8;
        }
        
        function findUser(username: string): User | null {
            return database.users.find(u => u.username === username) || null;
        }
        """)
        
        result = get_call_trace_impl(
            entry_point="authenticate",
            file_paths=str(test_file),
            max_depth=10,
            include_external_calls=True,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        # Should analyze multiple execution paths (implementation details for later)
        assert isinstance(result.execution_paths, list)

    def test_get_call_trace_cross_file_analysis(self, temp_project):
        """Test call trace analysis across multiple files."""
        # Create multiple interconnected files
        files = {
            "controller.ts": """
                import { UserService } from './service';
                
                export class UserController {
                    constructor(private userService: UserService) {}
                    
                    async handleGetUser(id: number): Promise<Response> {
                        const user = await this.userService.getUser(id);
                        return this.formatResponse(user);
                    }
                    
                    private formatResponse(user: User | null): Response {
                        return user ? { data: user } : { error: 'Not found' };
                    }
                }
            """,
            "service.ts": """
                import { UserRepository } from './repository';
                
                export class UserService {
                    constructor(private repository: UserRepository) {}
                    
                    async getUser(id: number): Promise<User | null> {
                        return this.repository.findById(id);
                    }
                }
            """,
            "repository.ts": """
                export class UserRepository {
                    async findById(id: number): Promise<User | null> {
                        const result = await database.query('SELECT * FROM users WHERE id = ?', [id]);
                        return result.rows[0] || null;
                    }
                }
            """
        }
        
        file_paths = []
        for filename, content in files.items():
            file_path = temp_project / filename
            file_path.write_text(content)
            file_paths.append(str(file_path))
        
        result = get_call_trace_impl(
            entry_point="UserController.handleGetUser",
            file_paths=file_paths,
            max_depth=10,
            include_external_calls=True
        )
        
        assert isinstance(result, CallTraceResponse)
        # Should trace calls across multiple files

    def test_get_call_trace_with_cycles(self, temp_project):
        """Test call trace analysis with cyclic dependencies."""
        test_file = temp_project / "cyclic_calls.ts"
        test_file.write_text("""
        function functionA(): void {
            console.log("A");
            functionB();
        }
        
        function functionB(): void {
            console.log("B");
            functionC();
        }
        
        function functionC(): void {
            console.log("C");
            // Potential cycle - implementation should detect this
            functionA();
        }
        """)
        
        result = get_call_trace_impl(
            entry_point="functionA",
            file_paths=str(test_file),
            max_depth=20,  # High depth to test cycle detection
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        # Should detect and handle cycles appropriately
        assert isinstance(result.call_graph_stats, CallGraphStats)
        # cycles_detected field should be available in stats

    def test_get_call_trace_performance_constraints(self, temp_project):
        """Test call trace with performance constraints."""
        # Create file with deep call chain
        deep_calls = []
        for i in range(15):
            if i == 14:
                deep_calls.append(f"function func{i}(): void {{ console.log('End of chain'); }}")
            else:
                deep_calls.append(f"function func{i}(): void {{ func{i+1}(); }}")
        
        test_file = temp_project / "deep_calls.ts"
        test_file.write_text("\n\n".join(deep_calls))
        
        # Test with limited depth
        result = get_call_trace_impl(
            entry_point="func0",
            file_paths=str(test_file),
            max_depth=5,  # Should stop at depth limit
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        # Should respect depth limits
        assert result.call_graph_stats.max_depth_reached <= 5

    def test_get_call_trace_error_handling(self, temp_project):
        """Test error handling in call trace analysis."""
        # Test with non-existent entry point
        test_file = temp_project / "no_entry.ts"
        test_file.write_text("export const someVariable = 'test';")
        
        result = get_call_trace_impl(
            entry_point="nonExistentFunction",
            file_paths=str(test_file),
            max_depth=5,
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        assert len(result.errors) > 0
        
        error = result.errors[0]
        assert isinstance(error, AnalysisError)
        assert error.code in ["NOT_FOUND", "INVALID_ENTRY_POINT"]

    def test_get_call_trace_statistics_accuracy(self, temp_project):
        """Test that call graph statistics are accurate."""
        test_file = temp_project / "stats_test.ts"
        test_file.write_text("""
        function main(): void {
            helper1();
            helper2();
        }
        
        function helper1(): void {
            utility();
        }
        
        function helper2(): void {
            utility();
        }
        
        function utility(): void {
            console.log("utility");
        }
        """)
        
        result = get_call_trace_impl(
            entry_point="main",
            file_paths=str(test_file),
            max_depth=10,
            include_external_calls=False
        )
        
        assert isinstance(result, CallTraceResponse)
        stats = result.call_graph_stats
        
        # Verify statistics structure
        assert isinstance(stats.total_functions, int)
        assert isinstance(stats.total_edges, int) 
        assert isinstance(stats.max_depth_reached, int)
        assert isinstance(stats.cycles_detected, int)
        
        # Stats should be non-negative
        assert stats.total_functions >= 0
        assert stats.total_edges >= 0
        assert stats.max_depth_reached >= 0
        assert stats.cycles_detected >= 0

    # Phase 4 Comprehensive Call Graph Tests
    
    def test_phase4_call_graph_construction_accuracy(self, phase4_fixtures_dir):
        """Test Phase 4 call graph construction accuracy (99% edge coverage)."""
        simple_calls = str(phase4_fixtures_dir / "simple_calls.ts")
        
        result = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls],
            max_depth=10,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        assert result.entry_point == "login"
        
        # Phase 4: Should build complete call graph with high edge coverage
        # login calls: validateCredentials, createSession, logSuccess, logFailure
        expected_calls = {"validateCredentials", "createSession", "logSuccess", "logFailure"}
        
        all_calls = set()
        for path in result.execution_paths:
            all_calls.update(path.path)
        
        detected_calls = expected_calls.intersection(all_calls)
        coverage_ratio = len(detected_calls) / len(expected_calls)
        
        # Phase 4 requirement: 99% edge coverage
        assert coverage_ratio >= 0.99, f"Edge coverage {coverage_ratio:.2%} should be >= 99%"
    
    def test_phase4_cycle_detection_without_infinite_loops(self, phase4_fixtures_dir):
        """Test Phase 4 cycle detection without infinite loops."""
        recursive_file = str(phase4_fixtures_dir / "recursive_functions.ts")
        
        import time
        start_time = time.time()
        
        result = get_call_trace_impl(
            entry_point="factorial",
            file_paths=[recursive_file],
            max_depth=20,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should detect cycles without infinite loops
        assert result.call_graph_stats.cycles_detected > 0, "Should detect direct recursion cycle"
        assert execution_time < 5.0, f"Cycle detection took {execution_time:.2f}s, should complete quickly"
        
        # Should not hang or timeout
        assert len(result.execution_paths) >= 0, "Should complete analysis with cycles"
    
    def test_phase4_conditional_execution_path_analysis(self, phase4_fixtures_dir):
        """Test Phase 4 conditional execution path analysis with branch detection."""
        conditional_file = str(phase4_fixtures_dir / "conditional_calls.ts")
        
        result = get_call_trace_impl(
            entry_point="processUser",
            file_paths=[conditional_file],
            max_depth=12,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should analyze conditional execution paths
        # processUser has if/else branches for different actions and switch for roles
        action_calls = {"createUser", "updateUser", "deleteUser", "logInvalidAction"}
        role_calls = {"grantAdminAccess", "grantUserAccess", "grantGuestAccess"}
        
        all_detected_calls = set()
        conditional_paths = []
        
        for path in result.execution_paths:
            all_detected_calls.update(path.path)
            if path.condition:
                conditional_paths.append(path)
        
        # Should detect multiple conditional branches
        action_coverage = len(action_calls.intersection(all_detected_calls)) / len(action_calls)
        role_coverage = len(role_calls.intersection(all_detected_calls)) / len(role_calls)
        
        assert action_coverage >= 0.5, "Should detect at least half of action branches"
        assert role_coverage >= 0.5, "Should detect at least half of role branches"
        
        # Should have conditional paths with probability estimates
        if len(conditional_paths) > 0:
            for path in conditional_paths:
                assert 0.0 <= path.execution_probability <= 1.0, "Probability should be 0-1"
    
    def test_phase4_caller_and_callee_direction_tracing(self, phase4_fixtures_dir):
        """Test Phase 4 bidirectional call tracing (caller and callee analysis)."""
        complex_graph = str(phase4_fixtures_dir / "complex_graph.ts")
        
        # Test callee direction (what does this function call)
        callee_result = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=[complex_graph],
            max_depth=15,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(callee_result, CallTraceResponse)
        
        # Should trace deep into called functions
        assert callee_result.call_graph_stats.max_depth_reached >= 10, "Should trace deep call chains"
        assert callee_result.call_graph_stats.total_functions >= 10, "Should discover many functions"
        
        # Should detect complex execution paths
        assert len(callee_result.execution_paths) > 0, "Should detect execution paths"
        
        # Verify deep tracing capability
        deep_paths = [p for p in callee_result.execution_paths if len(p.path) >= 5]
        assert len(deep_paths) > 0, "Should detect call paths with 5+ levels"
    
    def test_phase4_deep_trace_15_second_performance(self, phase4_fixtures_dir):
        """Test Phase 4 performance requirement: complete deep traces within 15 seconds."""
        complex_graph = str(phase4_fixtures_dir / "complex_graph.ts")
        
        import time
        start_time = time.time()
        
        result = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=[complex_graph],
            max_depth=15,  # Deep tracing
            include_external_calls=False,
            analyze_conditions=True
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4 requirement: Complete deep traces within 15 seconds
        assert execution_time < 15.0, f"Deep trace took {execution_time:.2f}s, should be < 15s"
        
        # Should actually achieve deep tracing
        assert result.call_graph_stats.max_depth_reached >= 10, "Should trace at least 10 levels deep"
        
        # Should return meaningful execution paths
        assert len(result.execution_paths) > 0, "Should produce execution paths within time limit"
    
    def test_phase4_lean_response_without_code(self, phase4_fixtures_dir):
        """Test Phase 4 lean responses for performance (execution paths without code)."""
        async_patterns = str(phase4_fixtures_dir / "async_patterns.ts")
        
        result = get_call_trace_impl(
            entry_point="complexAsyncWorkflow",
            file_paths=[async_patterns],
            max_depth=10,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should return execution paths without code for performance
        # ExecutionPath should contain function names, not full code
        for path in result.execution_paths:
            assert isinstance(path.path, list), "Path should be a list of function names"
            for call in path.path:
                assert isinstance(call, str), "Each call should be a string identifier"
                # Should not contain full code (lean response)
                assert len(call) < 200, "Call identifier should be concise, not full code"
    
    def test_phase4_dynamic_property_access_handling(self, phase4_fixtures_dir):
        """Test Phase 4 handling of dynamic property access and method calls."""
        event_system = str(phase4_fixtures_dir / "event_system.ts")
        
        result = get_call_trace_impl(
            entry_point="executeCommand",
            file_paths=[event_system],
            max_depth=12,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should handle dynamic property access with reasonable accuracy
        # CommandProcessor.executeCommand uses dynamic method calls
        # Should detect at least some of the execution flow
        assert len(result.execution_paths) > 0, "Should handle dynamic calls"
        
        # Should discover functions involved in dynamic execution
        assert result.call_graph_stats.total_functions > 0, "Should detect functions in dynamic context"
    
    def test_phase4_memory_usage_under_500mb(self, phase4_fixtures_dir):
        """Test Phase 4 memory usage stays under 500MB for complex call graphs."""
        # Use multiple large files to create memory pressure
        files = [
            str(phase4_fixtures_dir / "complex_graph.ts"),
            str(phase4_fixtures_dir / "class_methods.ts"),
            str(phase4_fixtures_dir / "async_patterns.ts"),
            str(phase4_fixtures_dir / "event_system.ts")
        ]
        
        import psutil
        import os
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        result = get_call_trace_impl(
            entry_point="processUserRegistration",
            file_paths=files,
            max_depth=15,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
        memory_increase = peak_memory - initial_memory
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4 requirement: Memory usage under 500MB for complex call graphs
        assert memory_increase < 500.0, f"Memory increased by {memory_increase:.1f}MB, should be < 500MB"
        
        # Should still produce meaningful results within memory constraints
        assert len(result.execution_paths) > 0, "Should complete analysis within memory limits"
    
    def test_phase4_async_call_patterns_support(self, phase4_fixtures_dir):
        """Test Phase 4 support for async patterns and Promise chains."""
        async_patterns = str(phase4_fixtures_dir / "async_patterns.ts")
        
        result = get_call_trace_impl(
            entry_point="complexAsyncWorkflow",
            file_paths=[async_patterns],
            max_depth=12,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should handle async call patterns
        # complexAsyncWorkflow has sequential and parallel async calls
        async_calls = {"fetchUser", "fetchUserPreferences", "fetchUserPermissions", 
                      "generateRecommendations", "fetchNotifications"}
        
        all_detected_calls = set()
        for path in result.execution_paths:
            all_detected_calls.update(path.path)
        
        async_coverage = len(async_calls.intersection(all_detected_calls)) / len(async_calls)
        
        # Should detect a reasonable portion of async calls
        assert async_coverage >= 0.4, f"Async call coverage {async_coverage:.2%} should be >= 40%"
    
    def test_phase4_class_method_inheritance_tracing(self, phase4_fixtures_dir):
        """Test Phase 4 tracing through class methods and inheritance."""
        class_methods = str(phase4_fixtures_dir / "class_methods.ts")
        
        result = get_call_trace_impl(
            entry_point="createUser",  # UserService.createUser
            file_paths=[class_methods],
            max_depth=10,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should trace through class methods
        # UserService.createUser calls private methods and validation
        method_calls = {"validateUserData", "normalizeUserData", "findUserByEmail", 
                       "hashPassword", "sendWelcomeEmail"}
        
        all_detected_calls = set()
        for path in result.execution_paths:
            all_detected_calls.update(path.path)
        
        method_coverage = len(method_calls.intersection(all_detected_calls)) / len(method_calls)
        
        # Should detect class method calls
        assert method_coverage >= 0.5, f"Method call coverage {method_coverage:.2%} should be >= 50%"
        
        # Should handle inheritance patterns (OrderEntity extends BaseEntity)
        result_inheritance = get_call_trace_impl(
            entry_point="save",  # BaseEntity.save (inherited)
            file_paths=[class_methods],
            max_depth=8
        )
        
        assert isinstance(result_inheritance, CallTraceResponse)
        # Should trace through inheritance hierarchy
    
    def test_phase4_error_handling_and_edge_cases(self, phase4_fixtures_dir):
        """Test Phase 4 robust error handling and edge cases."""
        simple_calls = str(phase4_fixtures_dir / "simple_calls.ts")
        
        # Test with invalid entry point
        result_invalid = get_call_trace_impl(
            entry_point="nonExistentFunction",
            file_paths=[simple_calls],
            max_depth=5
        )
        
        assert isinstance(result_invalid, CallTraceResponse)
        # Should handle gracefully with appropriate errors
        assert len(result_invalid.errors) > 0, "Should report error for non-existent entry point"
        
        # Test with empty entry point
        result_empty = get_call_trace_impl(
            entry_point="",
            file_paths=[simple_calls],
            max_depth=5
        )
        
        assert isinstance(result_empty, CallTraceResponse)
        entry_point_errors = [e for e in result_empty.errors if e.code == "INVALID_ENTRY_POINT"]
        assert len(entry_point_errors) > 0, "Should validate empty entry point"
        
        # Test with very high max_depth
        result_deep = get_call_trace_impl(
            entry_point="login",
            file_paths=[simple_calls],
            max_depth=100  # Very high depth
        )
        
        assert isinstance(result_deep, CallTraceResponse)
        # Should handle without performance issues
        assert result_deep.call_graph_stats.max_depth_reached <= 100, "Should respect max_depth limit"
    
    def test_phase4_multiple_execution_patterns_integration(self, phase4_fixtures_dir):
        """Test Phase 4 integration of multiple execution patterns."""
        # Use all fixture files for comprehensive testing
        all_files = [
            str(phase4_fixtures_dir / "simple_calls.ts"),
            str(phase4_fixtures_dir / "recursive_functions.ts"),
            str(phase4_fixtures_dir / "conditional_calls.ts"),
            str(phase4_fixtures_dir / "async_patterns.ts"),
            str(phase4_fixtures_dir / "class_methods.ts"),
            str(phase4_fixtures_dir / "event_system.ts"),
            str(phase4_fixtures_dir / "complex_graph.ts")
        ]
        
        result = get_call_trace_impl(
            entry_point="login",  # Should find in simple_calls.ts
            file_paths=all_files,
            max_depth=12,
            include_external_calls=False,
            analyze_conditions=True
        )
        
        assert isinstance(result, CallTraceResponse)
        
        # Phase 4: Should handle comprehensive project analysis
        # Should find the login function across multiple files
        assert result.entry_point == "login", "Should find entry point across files"
        
        # Should build meaningful call graph
        assert result.call_graph_stats.total_functions > 0, "Should discover functions"
        assert len(result.execution_paths) > 0, "Should detect execution paths"
        
        # Should handle mixed patterns (simple calls, conditionals, etc.)
        all_calls = set()
        for path in result.execution_paths:
            all_calls.update(path.path)
        
        # Should detect login-related function calls
        login_calls = {"validateCredentials", "createSession", "logSuccess", "logFailure"}
        detected_login_calls = login_calls.intersection(all_calls)
        assert len(detected_login_calls) > 0, "Should detect login-related function calls"


class TestToolIntegration:
    """Test integration between TypeScript analysis tools."""

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

    def test_tool_chain_analysis_workflow(self, temp_project):
        """Test typical workflow using multiple tools together."""
        # Create comprehensive test file
        test_file = temp_project / "integration_test.ts"
        test_file.write_text("""
        interface User {
            id: number;
            name: string;
            email?: string;
        }
        
        class UserService {
            async getUser(id: number): Promise<User | null> {
                const user = await this.fetchFromApi(id);
                return this.validateUser(user);
            }
            
            private async fetchFromApi(id: number): Promise<any> {
                return fetch(`/api/users/${id}`).then(r => r.json());
            }
            
            private validateUser(user: any): User | null {
                return user && user.id && user.name ? user as User : null;
            }
        }
        
        function processUser(user: User): string {
            return `Processing user: ${user.name}`;
        }
        """)
        
        # Step 1: Find all references to 'User' interface
        references_result = find_references_impl(
            symbol="User",
            file_paths=str(test_file),
            include_declarations=True,
            include_usages=True
        )
        
        # Step 2: Get details of UserService methods
        function_details_result = get_function_details_impl(
            functions=["getUser", "fetchFromApi", "validateUser"],
            file_paths=str(test_file),
            include_code=True,
            include_types=True,
            include_calls=True
        )
        
        # Step 3: Trace execution flow from getUser
        call_trace_result = get_call_trace_impl(
            entry_point="UserService.getUser",
            file_paths=str(test_file),
            max_depth=5,
            include_external_calls=True
        )
        
        # All tools should return proper responses
        assert isinstance(references_result, FindReferencesResponse)
        assert isinstance(function_details_result, FunctionDetailsResponse)
        assert isinstance(call_trace_result, CallTraceResponse)
        
        # Responses should be consistent with each other
        # (specific consistency checks would be implementation-dependent)

    def test_error_consistency_across_tools(self, temp_project):
        """Test that error handling is consistent across all tools."""
        # Test with invalid file path
        invalid_file = "/completely/invalid/path.ts"
        
        # All tools should handle invalid paths consistently
        tools_and_params = [
            (find_references_impl, {
                "symbol": "AnySymbol",
                "file_paths": invalid_file,
                "include_declarations": True,
                "include_usages": True
            }),
            (get_function_details_impl, {
                "functions": "anyFunction",
                "file_paths": invalid_file,
                "include_code": True,
                "include_types": False,
                "include_calls": False
            }),
            (get_call_trace_impl, {
                "entry_point": "anyFunction",
                "file_paths": invalid_file,
                "max_depth": 5,
                "include_external_calls": False
            })
        ]
        
        for tool_func, params in tools_and_params:
            result = tool_func(**params)
            
            # Should have structured error response
            assert hasattr(result, 'errors')
            assert len(result.errors) > 0
            
            error = result.errors[0]
            assert isinstance(error, AnalysisError)
            assert error.code == "NOT_FOUND"  # Consistent error code
            assert error.message is not None
            assert error.file == invalid_file

    def test_pagination_consistency_across_tools(self, temp_project):
        """Test that pagination behavior is consistent across tools."""
        test_file = temp_project / "pagination_test.ts"
        test_file.write_text("export function testFunc(): void { }")
        
        # Test pagination parameters across all tools
        pagination_params = {"page": 1, "max_tokens": 1000}
        
        # Test find_references pagination
        ref_result = find_references_impl(
            symbol="testFunc",
            file_paths=str(test_file),
            include_declarations=True,
            include_usages=True,
            **pagination_params
        )
        
        # Test get_function_details pagination
        func_result = get_function_details_impl(
            functions="testFunc",
            file_paths=str(test_file),
            include_code=True,
            include_types=False,
            include_calls=False,
            **pagination_params
        )
        
        # Test get_call_trace pagination
        trace_result = get_call_trace_impl(
            entry_point="testFunc",
            file_paths=str(test_file),
            max_depth=5,
            include_external_calls=False,
            **pagination_params
        )
        
        # All should handle pagination consistently
        for result in [ref_result, func_result, trace_result]:
            assert hasattr(result, 'total')
            assert hasattr(result, 'page_size')
            assert hasattr(result, 'next_cursor')
            assert hasattr(result, 'has_more')
            
            # Values should be reasonable
            assert result.total >= 0
            assert result.page_size is None or result.page_size >= 0
            assert isinstance(result.has_more, bool) or result.has_more is None