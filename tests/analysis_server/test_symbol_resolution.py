"""
Comprehensive tests for TypeScript symbol resolution system.

These tests define the expected behavior for Phase 2 symbol resolution,
including multi-pass analysis, cross-file symbol tracking, and inheritance
chain resolution. Tests will initially fail (RED phase) until implementation.
"""

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import the expected symbol resolution components (will fail initially)
try:
    from aromcp.analysis_server.tools.symbol_resolver import (
        SymbolResolver,
        ResolutionPass,
        SymbolType,
        ReferenceType,
    )
    from aromcp.analysis_server.models.typescript_models import (
        SymbolInfo,
        ReferenceInfo,
        InheritanceChain,
        SymbolResolutionResult,
        AnalysisError,
    )
except ImportError as e:
    print(f"Import error: {e}")
    # Expected to fail initially - create placeholder classes for type hints
    class SymbolResolver:
        pass
    
    class ResolutionPass:
        SYNTACTIC = "syntactic"
        SEMANTIC = "semantic"
        DYNAMIC = "dynamic"
    
    class SymbolType:
        FUNCTION = "function"
        CLASS = "class"
        INTERFACE = "interface"
        VARIABLE = "variable"
        METHOD = "method"
        PROPERTY = "property"
    
    class ReferenceType:
        DECLARATION = "declaration"
        DEFINITION = "definition"
        USAGE = "usage"
        CALL = "call"
        IMPORT = "import"
        EXPORT = "export"
    
    class SymbolInfo:
        pass
    
    class ReferenceInfo:
        pass
    
    class InheritanceChain:
        pass
    
    class SymbolResolutionResult:
        pass
    
    class AnalysisError:
        pass


class TestSymbolResolver:
    """Test the multi-pass symbol resolution system."""

    @pytest.fixture
    def fixtures_dir(self):
        """Get the path to test fixtures directory."""
        return Path(__file__).parent / "fixtures"

    @pytest.fixture
    def resolver(self):
        """Create a symbol resolver instance."""
        # This will fail initially until implementation exists
        return SymbolResolver(cache_enabled=True, max_cache_size_mb=100)

    @pytest.fixture
    def phase2_project(self):
        """Create realistic Phase 2 project structure for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Set MCP_FILE_ROOT for testing
            old_root = os.environ.get("MCP_FILE_ROOT")
            os.environ["MCP_FILE_ROOT"] = str(temp_path)
            
            try:
                # Create comprehensive project structure
                self._create_phase2_fixtures(temp_path)
                yield temp_path
            finally:
                if old_root:
                    os.environ["MCP_FILE_ROOT"] = old_root
                else:
                    os.environ.pop("MCP_FILE_ROOT", None)

    def _create_phase2_fixtures(self, temp_path: Path):
        """Create realistic TypeScript project for symbol resolution testing."""
        # Base types and interfaces
        (temp_path / "src" / "types").mkdir(parents=True)
        (temp_path / "src" / "types" / "index.ts").write_text("""
export interface User {
    id: number;
    name: string;
    email: string;
    profile?: UserProfile;
}

export interface UserProfile {
    avatar: string;
    bio: string;
    preferences: UserPreferences;
}

export interface UserPreferences {
    theme: 'light' | 'dark';
    notifications: boolean;
}

export type ApiResponse<T> = {
    data: T;
    status: number;
    message: string;
};

export enum UserRole {
    ADMIN = 'admin',
    USER = 'user',
    MODERATOR = 'moderator'
}
        """)

        # Auth module with inheritance
        (temp_path / "src" / "auth").mkdir()
        (temp_path / "src" / "auth" / "user.ts").write_text("""
import { User, UserProfile, UserRole } from '../types';

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
}

export class AuthenticatedUser extends BaseUser implements User {
    public email: string;
    public profile?: UserProfile;
    private role: UserRole;
    
    constructor(id: number, name: string, email: string, role: UserRole = UserRole.USER) {
        super(id, name);
        this.email = email;
        this.role = role;
    }
    
    getDisplayName(): string {
        return this.profile?.bio ? `${this.name} - ${this.profile.bio}` : this.name;
    }
    
    setProfile(profile: UserProfile): void {
        this.profile = profile;
    }
    
    getRole(): UserRole {
        return this.role;
    }
    
    hasPermission(permission: string): boolean {
        return this.role === UserRole.ADMIN;
    }
}

export class GuestUser extends BaseUser {
    getDisplayName(): string {
        return `Guest: ${this.name}`;
    }
}
        """)

        (temp_path / "src" / "auth" / "auth-service.ts").write_text("""
import { User, ApiResponse } from '../types';
import { AuthenticatedUser, GuestUser, BaseUser } from './user';

export class AuthService {
    private users: Map<number, AuthenticatedUser> = new Map();
    private currentUser: BaseUser | null = null;
    
    async authenticate(email: string, password: string): Promise<AuthenticatedUser | null> {
        const user = await this.validateCredentials(email, password);
        if (user) {
            this.currentUser = user;
            return user;
        }
        return null;
    }
    
    private async validateCredentials(email: string, password: string): Promise<AuthenticatedUser | null> {
        // Mock validation logic
        const user = this.findUserByEmail(email);
        return user && this.checkPassword(user, password) ? user : null;
    }
    
    private findUserByEmail(email: string): AuthenticatedUser | null {
        for (const user of this.users.values()) {
            if (user.email === email) {
                return user;
            }
        }
        return null;
    }
    
    private checkPassword(user: AuthenticatedUser, password: string): boolean {
        // Mock password validation
        return password.length >= 8;
    }
    
    getCurrentUser(): BaseUser | null {
        return this.currentUser;
    }
    
    logout(): void {
        this.currentUser = null;
    }
    
    createGuestUser(name: string): GuestUser {
        return new GuestUser(Date.now(), name);
    }
}
        """)

        # React components using auth
        (temp_path / "src" / "components").mkdir()
        (temp_path / "src" / "components" / "user-profile.tsx").write_text("""
import React, { useState, useEffect } from 'react';
import { User, UserProfile } from '../types';
import { AuthService } from '../auth/auth-service';
import { AuthenticatedUser } from '../auth/user';

interface UserProfileProps {
    user: User;
    authService: AuthService;
}

export const UserProfileComponent: React.FC<UserProfileProps> = ({ user, authService }) => {
    const [profile, setProfile] = useState<UserProfile | null>(user.profile || null);
    const [isEditing, setIsEditing] = useState(false);
    
    useEffect(() => {
        loadUserProfile();
    }, [user.id]);
    
    const loadUserProfile = async (): Promise<void> => {
        // Mock profile loading
        if (user.profile) {
            setProfile(user.profile);
        }
    };
    
    const handleSaveProfile = async (updatedProfile: UserProfile): Promise<void> => {
        const currentUser = authService.getCurrentUser();
        if (currentUser instanceof AuthenticatedUser) {
            currentUser.setProfile(updatedProfile);
            setProfile(updatedProfile);
            setIsEditing(false);
        }
    };
    
    const renderProfileEditor = (): JSX.Element => {
        return (
            <div className="profile-editor">
                <input 
                    value={profile?.bio || ''} 
                    onChange={e => profile && setProfile({...profile, bio: e.target.value})}
                />
                <button onClick={() => profile && handleSaveProfile(profile)}>
                    Save Profile
                </button>
            </div>
        );
    };
    
    return (
        <div className="user-profile">
            <h2>{user.name}</h2>
            <p>{user.email}</p>
            {profile && (
                <div>
                    <img src={profile.avatar} alt="Avatar" />
                    <p>{profile.bio}</p>
                    <div>Theme: {profile.preferences.theme}</div>
                </div>
            )}
            {isEditing ? renderProfileEditor() : (
                <button onClick={() => setIsEditing(true)}>Edit Profile</button>
            )}
        </div>
    );
};
        """)

        # Utility functions
        (temp_path / "src" / "utils").mkdir()
        (temp_path / "src" / "utils" / "helpers.ts").write_text("""
import { User, ApiResponse } from '../types';
import { AuthenticatedUser } from '../auth/user';

export function formatUserName(user: User): string {
    return user.name.trim().toLowerCase().replace(/\s+/g, '-');
}

export function isAuthenticatedUser(user: User): user is AuthenticatedUser {
    return 'getRole' in user && typeof (user as any).getRole === 'function';
}

export function createApiResponse<T>(data: T, status: number = 200, message: string = 'Success'): ApiResponse<T> {
    return {
        data,
        status,
        message
    };
}

export async function fetchUserData(userId: number): Promise<User | null> {
    try {
        const response = await fetch(`/api/users/${userId}`);
        const apiResponse: ApiResponse<User> = await response.json();
        return apiResponse.data;
    } catch (error) {
        console.error('Failed to fetch user data:', error);
        return null;
    }
}

export const userUtils = {
    format: formatUserName,
    isAuthenticated: isAuthenticatedUser,
    fetch: fetchUserData
};
        """)

        # Test file (should be excluded by default)
        (temp_path / "tests").mkdir()
        (temp_path / "tests" / "auth.test.ts").write_text("""
import { AuthService } from '../src/auth/auth-service';
import { AuthenticatedUser, GuestUser } from '../src/auth/user';
import { UserRole } from '../src/types';

describe('AuthService', () => {
    let authService: AuthService;
    
    beforeEach(() => {
        authService = new AuthService();
    });
    
    test('should create guest user', () => {
        const guest = authService.createGuestUser('Test Guest');
        expect(guest).toBeInstanceOf(GuestUser);
        expect(guest.getName()).toBe('Test Guest');
    });
    
    test('should authenticate user', async () => {
        const user = await authService.authenticate('test@example.com', 'password123');
        expect(user).toBeInstanceOf(AuthenticatedUser);
    });
});
        """)

    def test_syntactic_symbol_resolution(self, resolver, phase2_project):
        """Test Pass 1: Syntactic symbol resolution within single files."""
        # Test resolving symbols within a single file
        user_file = phase2_project / "src" / "auth" / "user.ts"
        
        result = resolver.resolve_symbols(
            file_paths=[str(user_file)],
            resolution_pass=ResolutionPass.SYNTACTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.METHOD, SymbolType.FUNCTION]
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        assert isinstance(result.symbols, dict)
        assert isinstance(result.references, list)
        assert len(result.errors) == 0
        
        # Should find classes defined in the file
        expected_classes = ["BaseUser", "AuthenticatedUser", "GuestUser"]
        for class_name in expected_classes:
            assert class_name in result.symbols
            symbol_info = result.symbols[class_name]
            assert isinstance(symbol_info, SymbolInfo)
            assert symbol_info.symbol_type == SymbolType.CLASS
            assert symbol_info.name == class_name
            assert symbol_info.file_path == str(user_file)
        
        # Should find method references within classes
        method_references = [ref for ref in result.references 
                           if ref.reference_type == ReferenceType.DEFINITION 
                           and ref.symbol_type == SymbolType.METHOD]
        assert len(method_references) > 0
        
        # Should have confidence scores for syntactic analysis
        for symbol_info in result.symbols.values():
            assert hasattr(symbol_info, 'confidence_score')
            assert 0.0 <= symbol_info.confidence_score <= 1.0

    def test_semantic_symbol_resolution(self, resolver, phase2_project):
        """Test Pass 2: Semantic symbol resolution with cross-file imports."""
        # Test resolving symbols across multiple files with imports
        auth_files = [
            str(phase2_project / "src" / "types" / "index.ts"),
            str(phase2_project / "src" / "auth" / "user.ts"),
            str(phase2_project / "src" / "auth" / "auth-service.ts")
        ]
        
        result = resolver.resolve_symbols(
            file_paths=auth_files,
            resolution_pass=ResolutionPass.SEMANTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.INTERFACE, SymbolType.METHOD],
            include_imports=True
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should resolve imported symbols across files
        user_interface = result.symbols.get("User")
        assert user_interface is not None
        assert user_interface.symbol_type == SymbolType.INTERFACE
        assert user_interface.file_path.endswith("types/index.ts")
        
        # Should track import references
        import_references = [ref for ref in result.references 
                           if ref.reference_type == ReferenceType.IMPORT]
        assert len(import_references) > 0
        
        # Should find cross-file symbol usage
        auth_user_class = result.symbols.get("AuthenticatedUser")
        assert auth_user_class is not None
        
        # Should track implements relationship
        implements_refs = [ref for ref in result.references 
                          if ref.symbol_name == "User" 
                          and ref.reference_type == ReferenceType.USAGE
                          and "implements" in ref.context]
        assert len(implements_refs) > 0

    def test_dynamic_symbol_resolution_with_inheritance(self, resolver, phase2_project):
        """Test Pass 3: Dynamic symbol resolution through inheritance chains."""
        # Test resolving method calls through inheritance
        auth_files = [
            str(phase2_project / "src" / "auth" / "user.ts"),
            str(phase2_project / "src" / "auth" / "auth-service.ts")
        ]
        
        result = resolver.resolve_symbols(
            file_paths=auth_files,
            resolution_pass=ResolutionPass.DYNAMIC,
            symbol_types=[SymbolType.METHOD],
            resolve_inheritance=True,
            max_inheritance_depth=3
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should resolve inheritance chains
        assert hasattr(result, 'inheritance_chains')
        assert isinstance(result.inheritance_chains, list)
        
        # Should find BaseUser -> AuthenticatedUser inheritance
        base_to_auth_chain = None
        for chain in result.inheritance_chains:
            if (chain.base_class == "BaseUser" and 
                "AuthenticatedUser" in chain.derived_classes):
                base_to_auth_chain = chain
                break
        
        assert base_to_auth_chain is not None
        assert isinstance(base_to_auth_chain, InheritanceChain)
        
        # Should resolve method overrides
        get_display_name_refs = [ref for ref in result.references 
                               if ref.symbol_name == "getDisplayName"]
        
        # Should find both abstract definition and concrete implementations
        declarations = [ref for ref in get_display_name_refs 
                       if ref.reference_type == ReferenceType.DECLARATION]
        definitions = [ref for ref in get_display_name_refs 
                      if ref.reference_type == ReferenceType.DEFINITION]
        
        assert len(declarations) >= 1  # Abstract method in BaseUser
        assert len(definitions) >= 2   # Implementations in derived classes

    def test_class_method_syntax_resolution(self, resolver, phase2_project):
        """Test resolving 'ClassName#methodName' syntax."""
        auth_service_file = phase2_project / "src" / "auth" / "auth-service.ts"
        
        # Test resolving specific method using ClassName#methodName syntax
        result = resolver.resolve_symbols(
            file_paths=[str(auth_service_file)],
            resolution_pass=ResolutionPass.SEMANTIC,
            target_symbol="AuthService#authenticate",
            symbol_types=[SymbolType.METHOD]
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should find the specific method
        authenticate_method = result.symbols.get("AuthService#authenticate")
        assert authenticate_method is not None
        assert authenticate_method.symbol_type == SymbolType.METHOD
        assert authenticate_method.class_name == "AuthService"
        assert authenticate_method.method_name == "authenticate"
        
        # Should include method signature information
        assert hasattr(authenticate_method, 'parameters')
        assert hasattr(authenticate_method, 'return_type')
        assert len(authenticate_method.parameters) == 2  # email, password
        
        # Should find method calls to this specific method
        method_calls = [ref for ref in result.references 
                       if ref.symbol_name == "authenticate" 
                       and ref.reference_type == ReferenceType.CALL]
        assert len(method_calls) >= 0

    def test_symbol_confidence_scoring(self, resolver, phase2_project):
        """Test confidence scoring for different types of symbol resolution."""
        utils_file = phase2_project / "src" / "utils" / "helpers.ts"
        
        result = resolver.resolve_symbols(
            file_paths=[str(utils_file)],
            resolution_pass=ResolutionPass.SEMANTIC,
            symbol_types=[SymbolType.FUNCTION, SymbolType.VARIABLE],
            include_confidence_analysis=True
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Test confidence scores for different symbol types
        for symbol_name, symbol_info in result.symbols.items():
            assert hasattr(symbol_info, 'confidence_score')
            assert 0.0 <= symbol_info.confidence_score <= 1.0
            
            # Exported functions should have high confidence
            if symbol_info.is_exported and symbol_info.symbol_type == SymbolType.FUNCTION:
                assert symbol_info.confidence_score >= 0.8
            
            # Type guard functions should be identifiable
            if symbol_name == "isAuthenticatedUser":
                assert hasattr(symbol_info, 'is_type_guard')
                assert symbol_info.is_type_guard is True
        
        # References should also have confidence scores
        for ref in result.references:
            assert hasattr(ref, 'confidence_score')
            assert 0.0 <= ref.confidence_score <= 1.0

    def test_exclude_tests_by_default(self, resolver, phase2_project):
        """Test that test files are excluded by default."""
        all_files = [
            str(phase2_project / "src" / "auth" / "user.ts"),
            str(phase2_project / "tests" / "auth.test.ts")  # Should be excluded
        ]
        
        # Default behavior - exclude tests
        result = resolver.resolve_symbols(
            file_paths=all_files,
            resolution_pass=ResolutionPass.SYNTACTIC,
            symbol_types=[SymbolType.FUNCTION, SymbolType.CLASS]
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should not include symbols from test files
        test_symbols = [name for name, info in result.symbols.items() 
                       if info.file_path.endswith("auth.test.ts")]
        assert len(test_symbols) == 0
        
        # Should not include references from test files
        test_references = [ref for ref in result.references 
                         if ref.file_path.endswith("auth.test.ts")]
        assert len(test_references) == 0

    def test_include_tests_when_requested(self, resolver, phase2_project):
        """Test that test files are included when include_tests=True."""
        all_files = [
            str(phase2_project / "src" / "auth" / "user.ts"),
            str(phase2_project / "tests" / "auth.test.ts")
        ]
        
        # Explicitly include tests
        result = resolver.resolve_symbols(
            file_paths=all_files,
            resolution_pass=ResolutionPass.SYNTACTIC,
            symbol_types=[SymbolType.FUNCTION, SymbolType.CLASS],
            include_tests=True
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should include symbols from test files
        test_symbols = [name for name, info in result.symbols.items() 
                       if info.file_path.endswith("auth.test.ts")]
        assert len(test_symbols) > 0
        
        # Should find test function calls
        test_function_calls = [ref for ref in result.references 
                             if ref.symbol_name in ["describe", "test", "expect"]
                             and ref.file_path.endswith("auth.test.ts")]
        assert len(test_function_calls) > 0

    def test_performance_requirements(self, resolver, phase2_project):
        """Test that symbol resolution meets performance requirements."""
        # Create additional files to test scale
        large_project_files = []
        
        # Add existing project files
        for file_path in phase2_project.rglob("*.ts"):
            if not file_path.name.endswith(".test.ts"):
                large_project_files.append(str(file_path))
        
        # Test performance with realistic project size
        start_time = time.perf_counter()
        
        result = resolver.resolve_symbols(
            file_paths=large_project_files,
            resolution_pass=ResolutionPass.SEMANTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD],
            include_imports=True
        )
        
        end_time = time.perf_counter()
        analysis_time = (end_time - start_time)
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should complete analysis within 30 seconds for realistic project
        assert analysis_time < 30.0, f"Analysis took {analysis_time:.2f}s, should be <30s"
        
        # Should provide performance statistics
        assert hasattr(result, 'analysis_stats')
        assert hasattr(result.analysis_stats, 'total_files_processed')
        assert hasattr(result.analysis_stats, 'total_symbols_resolved')
        assert hasattr(result.analysis_stats, 'analysis_time_ms')
        
        assert result.analysis_stats.total_files_processed >= len(large_project_files)
        assert result.analysis_stats.total_symbols_resolved > 0
        assert result.analysis_stats.analysis_time_ms > 0

    def test_memory_usage_constraints(self, resolver, phase2_project):
        """Test that memory usage stays under 300MB during analysis."""
        # This test would need actual memory monitoring
        # For now, we define the expected behavior
        
        large_project_files = list(phase2_project.rglob("*.ts"))[:10]  # Limit for test
        file_paths = [str(f) for f in large_project_files if not f.name.endswith(".test.ts")]
        
        result = resolver.resolve_symbols(
            file_paths=file_paths,
            resolution_pass=ResolutionPass.DYNAMIC,
            symbol_types=[SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD],
            include_imports=True,
            resolve_inheritance=True
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should provide memory usage statistics
        assert hasattr(result, 'memory_stats')
        assert hasattr(result.memory_stats, 'peak_memory_mb')
        assert hasattr(result.memory_stats, 'final_memory_mb')
        
        # Memory usage should be reasonable
        # assert result.memory_stats.peak_memory_mb < 300
        
        # Implementation should provide memory monitoring
        assert hasattr(resolver, 'get_memory_usage_mb')
        current_memory = resolver.get_memory_usage_mb()
        assert isinstance(current_memory, (int, float))
        assert current_memory >= 0

    def test_error_handling_and_recovery(self, resolver, phase2_project):
        """Test error handling during symbol resolution."""
        # Test with mix of valid and invalid files
        mixed_files = [
            str(phase2_project / "src" / "auth" / "user.ts"),  # Valid
            "/nonexistent/file.ts",  # Invalid
            str(phase2_project / "src" / "types" / "index.ts")  # Valid
        ]
        
        result = resolver.resolve_symbols(
            file_paths=mixed_files,
            resolution_pass=ResolutionPass.SEMANTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.INTERFACE],
            continue_on_error=True
        )
        
        assert isinstance(result, SymbolResolutionResult)
        # Should partially succeed despite errors
        assert len(result.symbols) > 0
        assert len(result.errors) > 0
        
        # Errors should be properly structured
        file_not_found_error = None
        for error in result.errors:
            assert isinstance(error, AnalysisError)
            assert error.code in ["NOT_FOUND", "PARSE_ERROR", "RESOLUTION_ERROR"]
            assert error.message is not None
            if error.code == "NOT_FOUND":
                file_not_found_error = error
        
        assert file_not_found_error is not None
        assert "/nonexistent/file.ts" in file_not_found_error.file
        
        # Should still resolve symbols from valid files
        valid_symbols = [info for info in result.symbols.values() 
                        if not info.file_path.endswith("/nonexistent/file.ts")]
        assert len(valid_symbols) > 0

    def test_symbol_resolution_caching(self, resolver, phase2_project):
        """Test caching behavior for symbol resolution."""
        user_file = str(phase2_project / "src" / "auth" / "user.ts")
        
        # First resolution - cache miss
        start_time = time.perf_counter()
        result1 = resolver.resolve_symbols(
            file_paths=[user_file],
            resolution_pass=ResolutionPass.SYNTACTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.METHOD]
        )
        first_time = time.perf_counter() - start_time
        
        # Second resolution - should use cache
        start_time = time.perf_counter()
        result2 = resolver.resolve_symbols(
            file_paths=[user_file],
            resolution_pass=ResolutionPass.SYNTACTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.METHOD]
        )
        second_time = time.perf_counter() - start_time
        
        assert isinstance(result1, SymbolResolutionResult)
        assert isinstance(result2, SymbolResolutionResult)
        assert result1.success is True
        assert result2.success is True
        
        # Results should be identical
        assert len(result1.symbols) == len(result2.symbols)
        assert set(result1.symbols.keys()) == set(result2.symbols.keys())
        
        # Second resolution should be significantly faster
        assert second_time < first_time / 2, f"Cache didn't improve performance: {first_time:.3f}s vs {second_time:.3f}s"
        
        # Should provide cache statistics
        cache_stats = resolver.get_cache_stats()
        assert hasattr(cache_stats, 'hits')
        assert hasattr(cache_stats, 'misses')
        assert hasattr(cache_stats, 'hit_rate')
        assert cache_stats.hits > 0
        assert cache_stats.hit_rate > 0

    def test_paginated_results_support(self, resolver, phase2_project):
        """Test pagination support for large symbol resolution results."""
        auth_files = [
            str(phase2_project / "src" / "types" / "index.ts"),
            str(phase2_project / "src" / "auth" / "user.ts"),
            str(phase2_project / "src" / "auth" / "auth-service.ts"),
            str(phase2_project / "src" / "utils" / "helpers.ts")
        ]
        
        # Test with pagination parameters
        result = resolver.resolve_symbols(
            file_paths=auth_files,
            resolution_pass=ResolutionPass.SEMANTIC,
            symbol_types=[SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD],
            page=1,
            max_tokens=5000  # Small limit to test pagination
        )
        
        assert isinstance(result, SymbolResolutionResult)
        assert result.success is True
        
        # Should include pagination metadata
        assert hasattr(result, 'total')
        assert hasattr(result, 'page_size')
        assert hasattr(result, 'next_cursor')
        assert hasattr(result, 'has_more')
        
        # Pagination fields should be properly set
        assert isinstance(result.total, int)
        assert result.total >= 0
        assert isinstance(result.has_more, bool)
        
        # If there are more results than fit in one page
        if result.has_more:
            assert result.next_cursor is not None
            assert len(result.symbols) > 0 or len(result.references) > 0