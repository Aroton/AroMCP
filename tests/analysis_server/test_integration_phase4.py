"""Integration tests for Phase 4: Code Analysis Tools completion."""

import pytest
import tempfile
from pathlib import Path

from aromcp.analysis_server.tools.analyze_component_usage import analyze_component_usage_impl
from aromcp.analysis_server.tools.extract_api_endpoints import extract_api_endpoints_impl


class TestPhase4Integration:
    """Integration tests for Phase 4 completion."""

    def test_full_project_analysis(self):
        """Test analyzing a complete project with both components and API routes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a realistic project structure
            
            # API routes
            api_file = Path(temp_dir) / "routes" / "users.js"
            api_file.parent.mkdir(parents=True)
            api_file.write_text("""
const express = require('express');
const router = express.Router();

// Get all users
router.get('/users', async (req, res) => {
  const users = await User.findAll();
  res.json(users);
});

// Create user
router.post('/users', validateUser, async (req, res) => {
  const user = await User.create(req.body);
  res.status(201).json(user);
});

module.exports = router;
            """)
            
            # React components
            button_comp = Path(temp_dir) / "components" / "Button.tsx"
            button_comp.parent.mkdir(parents=True)
            button_comp.write_text("""
import React from 'react';

export const Button = ({ children, onClick }) => {
  return <button onClick={onClick}>{children}</button>;
};

export default Button;
            """)
            
            form_comp = Path(temp_dir) / "components" / "UserForm.tsx"
            form_comp.write_text("""
import React from 'react';
import { Button } from './Button';

export const UserForm = () => {
  const handleSubmit = () => {
    // Submit logic
  };

  return (
    <form>
      <Button onClick={handleSubmit}>Submit</Button>
    </form>
  );
};
            """)
            
            # Unused component
            unused_comp = Path(temp_dir) / "components" / "UnusedComponent.tsx"
            unused_comp.write_text("""
export const UnusedComponent = () => {
  return <div>I am never used</div>;
};
            """)

            # Test component analysis
            component_result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )
            
            assert "data" in component_result
            comp_data = component_result["data"]
            
            # Should find all components
            component_names = [c["name"] for c in comp_data["components"]]
            assert "Button" in component_names
            assert "UserForm" in component_names
            assert "UnusedComponent" in component_names
            
            # Should detect unused component
            unused_names = [c["name"] for c in comp_data["unused_components"]]
            assert "UnusedComponent" in unused_names
            assert "Button" not in unused_names  # Button is used by UserForm
            
            # Should track usage properly
            button_comp = next(c for c in comp_data["components"] if c["name"] == "Button")
            assert button_comp["total_usage"] > 0
            assert len(button_comp["files_imported_in"]) > 0

            # Test API endpoint analysis
            endpoint_result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )
            
            assert "data" in endpoint_result
            api_data = endpoint_result["data"]
            
            # Should find API endpoints
            endpoints = api_data["endpoints"]
            assert len(endpoints) == 2
            
            methods = [ep["method"] for ep in endpoints]
            assert "GET" in methods
            assert "POST" in methods
            
            # Should detect middleware
            post_endpoint = next(ep for ep in endpoints if ep["method"] == "POST")
            assert "validateUser" in post_endpoint["middleware"]
            
            # Should have statistics
            summary = api_data["summary"]
            assert summary["total_endpoints"] == 2
            assert summary["files_analyzed"] == 1

    def test_both_tools_empty_project(self):
        """Test both tools handle empty projects gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Component analysis on empty project
            comp_result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )
            
            assert "data" in comp_result
            assert comp_result["data"]["components"] == []
            assert comp_result["data"]["summary"]["total_components"] == 0
            
            # API analysis on empty project
            api_result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/routes/**/*.js"],
                include_middleware=True
            )
            
            assert "data" in api_result
            assert api_result["data"]["endpoints"] == []
            assert api_result["data"]["summary"]["total_endpoints"] == 0

    def test_tools_work_with_phase1_tools(self):
        """Test that the new tools integrate well with existing Phase 1 tools."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a component file
            comp_file = Path(temp_dir) / "MyComponent.tsx"
            comp_file.write_text("""
export const MyComponent = () => {
  return <div>Hello World</div>;
};
            """)
            
            # Create an API file
            api_file = Path(temp_dir) / "api.js"
            api_file.write_text("""
app.get('/hello', (req, res) => {
  res.json({ message: 'Hello World' });
});
            """)
            
            # Test component analysis
            comp_result = analyze_component_usage_impl(
                project_root=temp_dir,
                component_patterns=["**/*.tsx"],
                include_imports=True
            )
            
            # Test API analysis  
            api_result = extract_api_endpoints_impl(
                project_root=temp_dir,
                route_patterns=["**/*.js"],
                include_middleware=True
            )
            
            # Both should work without errors
            assert "data" in comp_result
            assert "data" in api_result
            
            # Should find the component and at least one endpoint
            assert len(comp_result["data"]["components"]) == 1
            assert len(api_result["data"]["endpoints"]) >= 1
            
            # Component should be MyComponent
            component = comp_result["data"]["components"][0]
            assert component["name"] == "MyComponent"
            assert component["type"] == "component"
            
            # Should find GET /hello endpoint
            get_endpoints = [ep for ep in api_result["data"]["endpoints"] if ep["method"] == "GET" and ep["path"] == "/hello"]
            assert len(get_endpoints) >= 1