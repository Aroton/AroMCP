"""
Tests for enhanced type resolution functionality.

Tests the new capabilities for resolving TypeScript path aliases,
extracting type definitions from imported files, and following import chains.
"""

import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from aromcp.analysis_server.tools.import_tracker import ModuleResolver
from aromcp.analysis_server.tools.type_resolver import TypeResolver
from aromcp.analysis_server.tools.typescript_parser import TypeScriptParser
from aromcp.analysis_server.tools.symbol_resolver import SymbolResolver
from aromcp.analysis_server.tools.get_function_details import get_function_details_impl


class TestModuleResolverPathAliases:
    """Test TypeScript path alias resolution."""

    def test_tsconfig_path_alias_loading(self):
        """Test loading path aliases from tsconfig.json."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json with path aliases
            tsconfig_content = {
                "compilerOptions": {
                    "paths": {
                        "@/*": ["./src/*"],
                        "@lib/*": ["./lib/*"],
                        "@components/*": ["./src/components/*"]
                    }
                }
            }
            
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump(tsconfig_content, f)
            
            resolver = ModuleResolver(temp_dir)
            
            expected_aliases = {
                "@": "./src",
                "@lib": "./lib", 
                "@components": "./src/components"
            }
            
            assert resolver.path_aliases == expected_aliases

    def test_tsconfig_with_trailing_commas(self):
        """Test handling tsconfig.json with trailing commas (JSON5 format)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create tsconfig.json with trailing comma (common in TypeScript projects)
            tsconfig_content = '''{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@lib/*": ["./lib/*"],
    }
  },
}'''
            
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                f.write(tsconfig_content)
            
            resolver = ModuleResolver(temp_dir)
            
            expected_aliases = {
                "@": "./src",
                "@lib": "./lib"
            }
            
            assert resolver.path_aliases == expected_aliases

    def test_path_alias_resolution(self):
        """Test resolving import paths using aliases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            components_dir = src_dir / "components"
            components_dir.mkdir()
            
            # Create files
            target_file = components_dir / "Button.tsx"
            target_file.write_text("export function Button() {}")
            
            # Create tsconfig.json
            tsconfig_content = {
                "compilerOptions": {
                    "paths": {
                        "@/*": ["./src/*"]
                    }
                }
            }
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump(tsconfig_content, f)
            
            resolver = ModuleResolver(temp_dir)
            
            # Test resolving @/components/Button
            from_file = str(src_dir / "App.tsx")
            resolved = resolver.resolve_path("@/components/Button", from_file)
            
            assert resolved == str(target_file)
            assert Path(resolved).exists()

    def test_relative_path_resolution_still_works(self):
        """Test that relative paths still work alongside aliases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Create files
            utils_file = src_dir / "utils.ts"
            utils_file.write_text("export const helper = () => {}")
            
            resolver = ModuleResolver(temp_dir)
            
            # Test resolving ./utils from src/App.tsx
            from_file = str(src_dir / "App.tsx")
            resolved = resolver.resolve_path("./utils", from_file)
            
            assert resolved == str(utils_file)


class TestTypeResolverImportResolution:
    """Test type resolver's ability to extract types from imported files."""

    def test_interface_extraction_from_imported_file(self):
        """Test extracting interface definitions from imported files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up project structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Create interface definition file
            types_file = src_dir / "types.ts"
            types_file.write_text('''
export interface UserInfo {
  id: number;
  name: string;
  email: string;
}

export type Status = 'active' | 'inactive';
''')
            
            # Create file that imports the interface
            main_file = src_dir / "main.ts"
            main_file.write_text('''
import { UserInfo } from './types';

export function getUser(): UserInfo {
  return { id: 1, name: 'Test', email: 'test@example.com' };
}
''')
            
            # Create tsconfig.json for path resolution
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump({"compilerOptions": {}}, f)
            
            # Test type resolution
            parser = TypeScriptParser()
            symbol_resolver = SymbolResolver(parser)
            type_resolver = TypeResolver(parser, symbol_resolver, temp_dir)
            
            # Should find UserInfo in the imported file
            result = type_resolver._find_type_definition("UserInfo", str(main_file))
            
            assert result is not None
            assert result.kind == "interface"
            assert "interface UserInfo" in result.definition
            assert "id: number" in result.definition
            assert "name: string" in result.definition
            assert str(types_file) in result.location

    def test_type_alias_extraction_from_imported_file(self):
        """Test extracting type aliases from imported files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Create type alias definition file
            types_file = src_dir / "status.ts"
            types_file.write_text('''
export type UserStatus = 'pending' | 'approved' | 'rejected';
export type ApiResponse<T> = {
  data: T;
  success: boolean;
  message?: string;
};
''')
            
            # Create file that imports the type
            main_file = src_dir / "api.ts"
            main_file.write_text('''
import type { UserStatus, ApiResponse } from './status';

export function updateStatus(): UserStatus {
  return 'approved';
}
''')
            
            # Create tsconfig.json
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump({"compilerOptions": {}}, f)
            
            parser = TypeScriptParser()
            symbol_resolver = SymbolResolver(parser)
            type_resolver = TypeResolver(parser, symbol_resolver, temp_dir)
            
            # Should find UserStatus type alias
            result = type_resolver._find_type_definition("UserStatus", str(main_file))
            
            assert result is not None
            assert result.kind == "type"
            assert "type UserStatus" in result.definition
            assert "'pending' | 'approved' | 'rejected'" in result.definition
            assert str(types_file) in result.location

    def test_path_alias_import_resolution(self):
        """Test resolving types imported via path aliases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up project structure
            src_dir = Path(temp_dir) / "src"
            types_dir = src_dir / "types" 
            src_dir.mkdir()
            types_dir.mkdir()
            
            # Create interface in types directory
            user_types_file = types_dir / "user.ts"
            user_types_file.write_text('''
export interface UserProfile {
  userId: string;
  displayName: string;
  avatar?: string;
}
''')
            
            # Create file that imports via path alias
            hooks_dir = src_dir / "hooks"
            hooks_dir.mkdir()
            hook_file = hooks_dir / "useUser.ts"
            hook_file.write_text('''
import type { UserProfile } from '@/types/user';

export function useUser(): UserProfile | null {
  return null;
}
''')
            
            # Create tsconfig.json with path aliases
            tsconfig_content = {
                "compilerOptions": {
                    "paths": {
                        "@/*": ["./src/*"]
                    }
                }
            }
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump(tsconfig_content, f)
            
            parser = TypeScriptParser()
            symbol_resolver = SymbolResolver(parser)
            type_resolver = TypeResolver(parser, symbol_resolver, temp_dir)
            
            # Should resolve UserProfile via @/ alias
            result = type_resolver._find_type_definition("UserProfile", str(hook_file))
            
            assert result is not None
            assert result.kind == "interface"
            assert "interface UserProfile" in result.definition
            assert "userId: string" in result.definition
            assert str(user_types_file) in result.location


class TestGetFunctionDetailsTypeResolution:
    """Integration tests for get_function_details with enhanced type resolution."""

    def test_function_with_imported_types(self):
        """Test get_function_details includes imported type definitions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up project structure
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Create type definition file
            types_file = src_dir / "types.ts"
            types_file.write_text('''
export interface Product {
  id: number;
  name: string;
  price: number;
  category: string;
}

export type ProductStatus = 'available' | 'out_of_stock' | 'discontinued';
''')
            
            # Create function file that uses imported types
            service_file = src_dir / "productService.ts"
            service_file.write_text('''
import { Product, ProductStatus } from './types';

export function createProduct(data: Partial<Product>): Product {
  return {
    id: Math.floor(Math.random() * 1000),
    name: data.name || 'Unknown',
    price: data.price || 0,
    category: data.category || 'General'
  };
}

export function getProductStatus(): ProductStatus {
  return 'available';
}
''')
            
            # Create tsconfig.json
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump({"compilerOptions": {}}, f)
            
            # Test get_function_details
            with patch.dict(os.environ, {'MCP_FILE_ROOT': str(temp_dir)}):
                result = get_function_details_impl(
                    functions="createProduct",
                    file_paths=str(service_file),
                    include_code=True,
                    include_types=True,
                    include_calls=False
                )
                
                assert result.success is True
                assert len(result.errors) == 0
                assert "createProduct" in result.functions
                
                func_list = result.functions["createProduct"]
                assert func_list is not None
                assert isinstance(func_list, list)
                assert len(func_list) >= 1

                
                func = func_list[0]
                assert func.types is not None
                
                # Should include the imported Product interface
                assert "Product" in func.types
                product_type = func.types["Product"]
                assert product_type.kind == "interface"
                assert "interface Product" in product_type.definition
                assert "id: number" in product_type.definition
                assert "name: string" in product_type.definition
                assert str(types_file) in product_type.location

    def test_function_with_path_alias_imports(self):
        """Test get_function_details resolves types imported via path aliases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up project structure
            src_dir = Path(temp_dir) / "src"
            models_dir = src_dir / "models"
            services_dir = src_dir / "services"
            src_dir.mkdir()
            models_dir.mkdir()
            services_dir.mkdir()
            
            # Create model definition
            user_model_file = models_dir / "User.ts"
            user_model_file.write_text('''
export interface User {
  id: string;
  email: string;
  profile: UserProfile;
}

export interface UserProfile {
  firstName: string;
  lastName: string;
  avatar?: string;
}
''')
            
            # Create service that uses path alias imports
            user_service_file = services_dir / "userService.ts"
            user_service_file.write_text('''
import type { User, UserProfile } from '@/models/User';

export function getCurrentUser(): User | null {
  return null;
}

export function updateProfile(profile: UserProfile): void {
  // Implementation
}
''')
            
            # Create tsconfig.json with path aliases
            tsconfig_content = {
                "compilerOptions": {
                    "paths": {
                        "@/*": ["./src/*"]
                    }
                }
            }
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump(tsconfig_content, f)
            
            # Test get_function_details
            with patch.dict(os.environ, {'MCP_FILE_ROOT': str(temp_dir)}):
                result = get_function_details_impl(
                    functions="getCurrentUser",
                    file_paths=str(user_service_file),
                    include_code=True,
                    include_types=True,
                    include_calls=False
                )
                
                assert result.success is True
                assert len(result.errors) == 0
                assert "getCurrentUser" in result.functions
                
                func_list = result.functions["getCurrentUser"]
                assert func_list is not None
                assert isinstance(func_list, list)
                assert len(func_list) >= 1

                
                func = func_list[0]
                assert func.types is not None
                
                # Should resolve User interface via @/ alias
                assert "User" in func.types
                user_type = func.types["User"]
                assert user_type.kind == "interface"
                assert "interface User" in user_type.definition
                assert "id: string" in user_type.definition
                assert "email: string" in user_type.definition
                assert str(user_model_file) in user_type.location

    def test_chained_type_imports(self):
        """Test resolving types that import other types (import chains)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Base types file
            base_types_file = src_dir / "base.ts"
            base_types_file.write_text('''
export interface BaseEntity {
  id: string;
  createdAt: Date;
  updatedAt: Date;
}
''')
            
            # User types file that extends base types
            user_types_file = src_dir / "user.ts"
            user_types_file.write_text('''
import { BaseEntity } from './base';

export interface User extends BaseEntity {
  email: string;
  username: string;
}
''')
            
            # Service file that uses user types
            service_file = src_dir / "service.ts"
            service_file.write_text('''
import { User } from './user';

export function findUser(id: string): User | null {
  return null;
}
''')
            
            # Create tsconfig.json
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump({"compilerOptions": {}}, f)
            
            # Test get_function_details
            with patch.dict(os.environ, {'MCP_FILE_ROOT': str(temp_dir)}):
                result = get_function_details_impl(
                    functions="findUser",
                    file_paths=str(service_file),
                    include_code=True,
                    include_types=True,
                    include_calls=False
                )
                
                assert result.success is True
                assert len(result.errors) == 0
                assert "findUser" in result.functions
                
                func_list = result.functions["findUser"]
                assert func_list is not None
                assert isinstance(func_list, list)
                assert len(func_list) >= 1

                
                func = func_list[0]
                assert func.types is not None
                
                # Should resolve User interface
                assert "User" in func.types
                user_type = func.types["User"]
                assert user_type.kind == "interface"
                assert "interface User extends BaseEntity" in user_type.definition
                assert "email: string" in user_type.definition
                assert str(user_types_file) in user_type.location

    def test_response_size_remains_reasonable(self):
        """Test that including type definitions doesn't make responses too large."""
        with tempfile.TemporaryDirectory() as temp_dir:
            src_dir = Path(temp_dir) / "src"
            src_dir.mkdir()
            
            # Create a file with multiple type definitions
            types_file = src_dir / "types.ts"
            types_file.write_text('''
export interface SmallInterface {
  id: string;
  name: string;
}

export type SimpleType = 'a' | 'b' | 'c';
''')
            
            # Create function file
            func_file = src_dir / "func.ts"
            func_file.write_text('''
import { SmallInterface, SimpleType } from './types';

export function testFunc(param: SmallInterface): SimpleType {
  return 'a';
}
''')
            
            # Create tsconfig.json
            tsconfig_path = Path(temp_dir) / "tsconfig.json"
            with open(tsconfig_path, 'w') as f:
                json.dump({"compilerOptions": {}}, f)
            
            # Test response size
            with patch.dict(os.environ, {'MCP_FILE_ROOT': str(temp_dir)}):
                result = get_function_details_impl(
                    functions="testFunc",
                    file_paths=str(func_file),
                    include_code=True,
                    include_types=True,
                    include_calls=False
                )
                
                # Convert to JSON to estimate size
                json_str = json.dumps(result.__dict__, default=str)
                approx_tokens = len(json_str) // 4
                
                # Should be reasonable size (well under 25k tokens)
                assert approx_tokens < 5000, f"Response too large: ~{approx_tokens} tokens"
                assert result.success is True
                assert len(result.functions) == 1