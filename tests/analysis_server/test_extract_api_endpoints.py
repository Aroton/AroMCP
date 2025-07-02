"""Tests for extract_api_endpoints tool."""

import pytest
import tempfile
from pathlib import Path

from aromcp.analysis_server.tools.extract_api_endpoints import extract_api_endpoints_impl


class TestExtractApiEndpoints:
    """Test cases for API endpoint extraction."""

    def test_express_routes_extraction(self):
        """Test extraction of Express.js routes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            routes_file = Path(temp_dir) / "routes" / "users.js"
            routes_file.parent.mkdir(parents=True)
            routes_file.write_text("""
const express = require('express');
const router = express.Router();

// Get all users
router.get('/users', async (req, res) => {
  const users = await User.findAll();
  res.json(users);
});

// Create new user
router.post('/users', validateUser, async (req, res) => {
  const user = await User.create(req.body);
  res.status(201).json(user);
});

// Get user by ID
router.get('/users/:id', getUserById);

// Update user
router.put('/users/:id', updateUser);

// Delete user
router.delete('/users/:id', deleteUser);

module.exports = router;
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            endpoints = data["endpoints"]
            assert len(endpoints) == 5
            
            # Check GET /users
            get_users = next(ep for ep in endpoints if ep["method"] == "GET" and ep["path"] == "/users")
            assert get_users["is_async"] == True
            assert get_users["parameters"] == []
            
            # Check POST /users with middleware
            post_users = next(ep for ep in endpoints if ep["method"] == "POST" and ep["path"] == "/users")
            assert "validateUser" in post_users["middleware"]
            
            # Check parameterized routes
            get_user_by_id = next(ep for ep in endpoints if ep["method"] == "GET" and "id" in ep["path"])
            assert "id" in get_user_by_id["parameters"]

    def test_fastapi_routes_extraction(self):
        """Test extraction of FastAPI routes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            api_file = Path(temp_dir) / "api" / "main.py"
            api_file.parent.mkdir(parents=True)
            api_file.write_text("""
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    name: str
    email: str

@app.get("/")
async def root():
    '''Root endpoint'''
    return {"message": "Hello World"}

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    '''Get user by ID'''
    return {"user_id": user_id}

@app.post("/users")
async def create_user(user: UserCreate):
    '''Create a new user'''
    return {"message": "User created", "user": user}

@app.put("/users/{user_id}")
async def update_user(user_id: int, user: UserCreate):
    return {"user_id": user_id, "user": user}
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/api/**/*.py"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            endpoints = data["endpoints"]
            # May find more due to regex patterns, so check we find at least the expected ones
            assert len(endpoints) >= 4
            
            # Check root endpoint
            root_endpoint = next(ep for ep in endpoints if ep["path"] == "/")
            assert root_endpoint["method"] == "GET"
            assert "Root endpoint" in root_endpoint["description"]
            
            # Check parameterized endpoint
            get_user = next(ep for ep in endpoints if ep["method"] == "GET" and "user_id" in ep["path"])
            assert "user_id" in get_user["parameters"]

    def test_nextjs_api_routes(self):
        """Test extraction of Next.js API routes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            api_file = Path(temp_dir) / "pages" / "api" / "users" / "[id].ts"
            api_file.parent.mkdir(parents=True)
            api_file.write_text("""
import { NextApiRequest, NextApiResponse } from 'next';

export async function GET(request: Request) {
  // Get user by ID
  return Response.json({ user: "details" });
}

export async function PUT(request: Request) {
  // Update user
  return Response.json({ updated: true });
}

export async function DELETE(request: Request) {
  // Delete user
  return Response.json({ deleted: true });
}
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/api/**/*.ts"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            endpoints = data["endpoints"]
            # May find more due to regex patterns, so check we find at least the expected ones
            assert len(endpoints) >= 3
            
            # Check that all endpoints have derived paths
            methods = [ep["method"] for ep in endpoints]
            assert "GET" in methods
            assert "PUT" in methods
            assert "DELETE" in methods

    def test_nestjs_routes_extraction(self):
        """Test extraction of NestJS routes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            controller_file = Path(temp_dir) / "controllers" / "user.controller.ts"
            controller_file.parent.mkdir(parents=True)
            controller_file.write_text("""
import { Controller, Get, Post, Put, Delete, Param, Body } from '@nestjs/common';

@Controller('users')
export class UserController {
  
  @Get()
  findAll(): string {
    return 'All users';
  }

  @Get(':id')
  findOne(@Param('id') id: string): string {
    return `User #${id}`;
  }

  @Post()
  create(@Body() createUserDto: any): string {
    return 'User created';
  }

  @Put(':id')
  update(@Param('id') id: string, @Body() updateUserDto: any): string {
    return `User #${id} updated`;
  }

  @Delete(':id')
  remove(@Param('id') id: string): string {
    return `User #${id} deleted`;
  }
}
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/controllers/**/*.ts"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            endpoints = data["endpoints"]
            # May find more due to regex patterns, so check we find at least the expected ones
            assert len(endpoints) >= 5
            
            # Check various HTTP methods
            methods = [ep["method"] for ep in endpoints]
            assert "GET" in methods
            assert "POST" in methods
            assert "PUT" in methods
            assert "DELETE" in methods

    def test_middleware_extraction(self):
        """Test middleware extraction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            app_file = Path(temp_dir) / "app.js"
            app_file.write_text("""
const express = require('express');
const app = express();

// Global middleware
app.use(express.json());
app.use(cors());

// Path-specific middleware
app.use('/api', authMiddleware);
app.use('/admin', adminMiddleware);

// Route with inline middleware
app.get('/protected', authenticateToken, (req, res) => {
  res.json({ message: 'Protected route' });
});

module.exports = app;
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            middleware = data["middleware"]
            assert len(middleware) >= 2  # Should find global and path-specific middleware
            
            # Check for global middleware
            global_middleware = [mw for mw in middleware if mw["type"] == "global"]
            assert len(global_middleware) >= 2
            
            # Check for path-specific middleware
            path_middleware = [mw for mw in middleware if mw["type"] == "path-specific"]
            assert len(path_middleware) >= 2

    def test_endpoint_descriptions(self):
        """Test extraction of endpoint descriptions from comments."""
        with tempfile.TemporaryDirectory() as temp_dir:
            routes_file = Path(temp_dir) / "routes" / "api.js"
            routes_file.parent.mkdir(parents=True)
            routes_file.write_text("""
const router = require('express').Router();

/**
 * Get all products
 * Returns a list of all available products
 */
router.get('/products', getProducts);

// Create a new product
// Requires authentication
router.post('/products', createProduct);

/*
 * Update product by ID
 * Requires admin privileges
 */
router.put('/products/:id', updateProduct);

module.exports = router;
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            endpoints = result["data"]["endpoints"]
            
            # Check that descriptions are extracted
            get_products = next(ep for ep in endpoints if ep["method"] == "GET")
            assert len(get_products["description"]) > 0
            
            post_products = next(ep for ep in endpoints if ep["method"] == "POST")
            assert "authentication" in post_products["description"].lower()

    def test_path_parameters_extraction(self):
        """Test extraction of path parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            routes_file = Path(temp_dir) / "routes" / "complex.js"
            routes_file.parent.mkdir(parents=True)
            routes_file.write_text("""
// Express.js style parameters
router.get('/users/:userId/posts/:postId', getPost);

// Multiple parameters
router.get('/categories/:category/items/:id/details/:detailId', getDetails);

// FastAPI style parameters (in a .py file, but testing regex)
// app.get("/items/{item_id}/users/{user_id}")
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            endpoints = result["data"]["endpoints"]
            
            # Check parameter extraction
            post_endpoint = next(ep for ep in endpoints if "posts" in ep["path"])
            assert "userId" in post_endpoint["parameters"]
            assert "postId" in post_endpoint["parameters"]
            
            details_endpoint = next(ep for ep in endpoints if "details" in ep["path"])
            assert len(details_endpoint["parameters"]) == 3

    def test_summary_statistics(self):
        """Test generation of summary statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple route files
            users_file = Path(temp_dir) / "routes" / "users.js"
            users_file.parent.mkdir(parents=True)
            users_file.write_text("""
router.get('/users', getUsers);
router.post('/users', createUser);
            """)
            
            products_file = Path(temp_dir) / "routes" / "products.js"
            products_file.write_text("""
router.get('/products', getProducts);
router.put('/products/:id', updateProduct);
router.delete('/products/:id', deleteProduct);
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            summary = data["summary"]
            assert summary["total_endpoints"] == 5
            assert summary["files_analyzed"] == 2
            
            # Check HTTP method statistics
            http_methods = summary["http_methods"]
            assert http_methods.get("GET", 0) >= 2
            assert http_methods.get("POST", 0) >= 1
            assert http_methods.get("PUT", 0) >= 1
            assert http_methods.get("DELETE", 0) >= 1
            
            # Check route grouping
            route_groups = summary["route_groups"]
            assert "/users" in route_groups
            assert "/products" in route_groups

    def test_empty_project(self):
        """Test handling of project with no API routes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a non-route file
            readme_file = Path(temp_dir) / "README.md"
            readme_file.write_text("# Project README")

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            data = result["data"]
            
            assert data["endpoints"] == []
            assert data["middleware"] == []
            assert data["summary"]["total_endpoints"] == 0
            assert data["summary"]["files_analyzed"] == 0

    def test_custom_route_patterns(self):
        """Test custom route patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create route in non-standard location
            custom_file = Path(temp_dir) / "custom" / "handlers" / "api.js"
            custom_file.parent.mkdir(parents=True)
            custom_file.write_text("""
app.get('/custom-endpoint', customHandler);
            """)

            # Test with default patterns (should not find it)
            result1 = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )
            
            assert result1["data"]["summary"]["total_endpoints"] == 0

            # Test with custom patterns (should find it)
            result2 = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/handlers/**/*.js"],
                include_middleware=True
            )
            
            assert result2["data"]["summary"]["total_endpoints"] >= 1

    def test_middleware_disabled(self):
        """Test when middleware extraction is disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            routes_file = Path(temp_dir) / "routes" / "api.js"
            routes_file.parent.mkdir(parents=True)
            routes_file.write_text("""
app.use(globalMiddleware);
router.get('/test', localMiddleware, handler);
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=False
            )

            assert "data" in result
            data = result["data"]
            
            # Middleware should be empty when disabled
            assert data["middleware"] == []

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        # Test with non-existent directory
        result = extract_api_endpoints_impl(
            project_root="/non/existent/path",
            route_patterns=["**/*.js"],
            include_middleware=True
        )

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_complex_route_patterns(self):
        """Test complex routing patterns and edge cases."""
        with tempfile.TemporaryDirectory() as temp_dir:
            complex_file = Path(temp_dir) / "routes" / "complex.js"
            complex_file.parent.mkdir(parents=True)
            complex_file.write_text("""
// Nested routers
const userRouter = express.Router();
userRouter.get('/:id', getUserById);
app.use('/users', userRouter);

// Multiple middleware
router.get('/protected', 
  authenticate, 
  authorize, 
  rateLimit, 
  getProtectedResource
);

// Route with regex
router.get(/.*fly$/, flyHandler);

// Route with array of handlers
router.post('/bulk', [validateBulk, processBulk, sendResponse]);
            """)

            result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )

            assert "data" in result
            # Should handle complex patterns gracefully without errors
            assert len(result["data"]["endpoints"]) >= 1