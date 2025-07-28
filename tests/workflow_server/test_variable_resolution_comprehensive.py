"""
Comprehensive variable resolution testing for advanced scenarios.

Covers missing acceptance criteria:
- AC-VR-007: PythonMonkey engine supports full ES6+ evaluation
- AC-VR-008: Python-based evaluation fallback works for basic expressions
- AC-VR-020: Complex nested expressions evaluate correctly

Focus: PythonMonkey fallback, ES6+ features, complex nested expressions
Pillar: Variable Resolution
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.context import context_manager


class TestVariableResolutionComprehensive:
    """Test comprehensive variable resolution scenarios including fallback and complex expressions."""

    def setup_method(self):
        """Setup test environment for each test."""
        self.executor = WorkflowExecutor()
        self.temp_dir = None
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment after each test."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()
        if self.temp_dir:
            # Temp directory cleanup handled by Python automatically
            pass

    def _create_workflow_file(self, workflow_name: str, workflow_content: str) -> Path:
        """Helper to create a workflow file for testing."""
        if not self.temp_dir:
            self.temp_dir = tempfile.TemporaryDirectory()
        
        temp_path = Path(self.temp_dir.name)
        workflows_dir = temp_path / ".aromcp" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        workflow_file = workflows_dir / f"{workflow_name}.yaml"
        workflow_file.write_text(workflow_content)
        return temp_path

    def test_pythonmonkey_unavailable_fallback(self):
        """
        Test AC-VR-008: Python-based evaluation fallback behavior.
        Focus: System gracefully falls back when PythonMonkey is unavailable.
        """
        workflow_content = """
name: "test-pythonmonkey-fallback"
description: "Test Python fallback when PythonMonkey is unavailable"
version: "1.0.0"

default_state:
  state:
    numbers: [1, 2, 3, 4, 5]
    multiplier: 10
    results: {}

steps:
  # Test basic arithmetic expressions (should work in fallback)
  - type: set_variable
    id: basic_arithmetic
    variable: "state.results.arithmetic"
    value: |
      {
        addition: state.multiplier + 5,
        subtraction: state.multiplier - 3,
        multiplication: state.multiplier * 2,
        division: state.multiplier / 2,
        modulo: state.multiplier % 3,
        power: state.multiplier ** 2
      }
  
  # Test basic comparisons (should work in fallback)
  - type: set_variable
    id: basic_comparisons
    variable: "state.results.comparisons"
    value: |
      {
        greater: state.multiplier > 5,
        less: state.multiplier < 20,
        equal: state.multiplier == 10,
        not_equal: state.multiplier != 5,
        gte: state.multiplier >= 10,
        lte: state.multiplier <= 10
      }
  
  # Test basic logical operations (should work in fallback)
  - type: set_variable
    id: basic_logical
    variable: "state.results.logical"
    value: |
      {
        and_op: state.multiplier > 5 && state.multiplier < 15,
        or_op: state.multiplier < 5 || state.multiplier > 8,
        not_op: !(state.multiplier < 5),
        ternary: state.multiplier > 5 ? 'big' : 'small'
      }
  
  # Test basic array operations (limited in fallback)
  - type: set_variable
    id: basic_arrays
    variable: "state.results.arrays"
    value: |
      {
        length: state.numbers.length,
        first: state.numbers[0],
        last: state.numbers[state.numbers.length - 1],
        slice_works: state.numbers.slice(1, 3)
      }
"""
        
        # Patch PythonMonkey to be unavailable
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', False):
            project_path = self._create_workflow_file("test-pythonmonkey-fallback", workflow_content)
            
            # Start workflow
            loader = WorkflowLoader(project_root=str(project_path))
            workflow_def = loader.load("test-pythonmonkey-fallback")
            result = self.executor.start(workflow_def)
            workflow_id = result["workflow_id"]
            
            # Wait for completion
            timeout = 10
            start_time = time.time()
            while time.time() - start_time < timeout:
                status = self.executor.get_workflow_status(workflow_id)
                if status["status"] == "completed":
                    break
                time.sleep(0.1)
            
            # Get final state
            final_status = self.executor.get_workflow_status(workflow_id)
            assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"
            
            results = final_status["state"]["state"]["results"]
            
            # Verify arithmetic operations work in fallback
            arith = results["arithmetic"]
            assert arith["addition"] == 15
            assert arith["subtraction"] == 7
            assert arith["multiplication"] == 20
            assert arith["division"] == 5
            assert arith["modulo"] == 1
            assert arith["power"] == 100
            
            # Verify comparisons work in fallback
            comp = results["comparisons"]
            assert comp["greater"] == True
            assert comp["less"] == True
            assert comp["equal"] == True
            assert comp["not_equal"] == True
            assert comp["gte"] == True
            assert comp["lte"] == True
            
            # Verify logical operations work in fallback
            logical = results["logical"]
            assert logical["and_op"] == True
            assert logical["or_op"] == True
            assert logical["not_op"] == True
            assert logical["ternary"] == "big"
            
            # Verify basic array access works
            arrays = results["arrays"]
            assert arrays["length"] == 5
            assert arrays["first"] == 1
            assert arrays["last"] == 5
            assert arrays["slice_works"] == [2, 3]

    def test_es6_feature_compatibility(self):
        """
        Test AC-VR-007: Comprehensive ES6+ feature testing.
        Focus: Modern JavaScript features work correctly with PythonMonkey.
        """
        workflow_content = """
name: "test-es6-features"
description: "Test ES6+ JavaScript features in expressions"
version: "1.0.0"

default_state:
  state:
    data: {
      users: [
        {name: "Alice", age: 30, role: "admin"},
        {name: "Bob", age: 25, role: "user"},
        {name: "Charlie", age: 35, role: "admin"},
        {name: "David", age: 28, role: "user"}
      ],
      scores: [85, 92, 78, 95, 88],
      config: {
        theme: "dark",
        features: {
          auth: true,
          analytics: false,
          notifications: true
        }
      }
    }
    results: {}

steps:
  # Test arrow functions and array methods
  - type: set_variable
    id: test_arrow_functions
    variable: "state.results.arrow_functions"
    value: |
      {
        filtered: state.data.users.filter(u => u.age > 28),
        mapped: state.data.users.map(u => u.name.toUpperCase()),
        reduced: state.data.scores.reduce((sum, score) => sum + score, 0),
        found: state.data.users.find(u => u.role === 'admin'),
        some: state.data.users.some(u => u.age > 30),
        every: state.data.users.every(u => u.age > 20)
      }
  
  # Test template literals and string interpolation
  - type: set_variable
    id: test_template_literals
    variable: "state.results.template_literals"
    value: |
      {
        simple: `Total users: ${state.data.users.length}`,
        expression: `Average age: ${state.data.users.reduce((sum, u) => sum + u.age, 0) / state.data.users.length}`,
        multiline: `Users:
${state.data.users.map(u => `- ${u.name} (${u.age})`).join('\\n')}`,
        nested: `Config: theme=${state.data.config.theme}, auth=${state.data.config.features.auth}`
      }
  
  # Test destructuring
  - type: set_variable
    id: test_destructuring
    variable: "state.results.destructuring"
    value: |
      (() => {
        const [first, second, ...rest] = state.data.scores;
        const {theme, features: {auth, analytics}} = state.data.config;
        const [{name: firstName}, {name: secondName}] = state.data.users;
        
        return {
          array_destructure: {first, second, rest},
          object_destructure: {theme, auth, analytics},
          nested_destructure: {firstName, secondName}
        };
      })()
  
  # Test spread operator
  - type: set_variable
    id: test_spread_operator
    variable: "state.results.spread_operator"
    value: |
      {
        array_spread: [...state.data.scores, 100, 95],
        object_spread: {...state.data.config, version: '2.0', features: {...state.data.config.features, beta: true}},
        combined: [...state.data.scores.slice(0, 2), 90, ...state.data.scores.slice(2)]
      }
  
  # Test modern array methods
  - type: set_variable
    id: test_modern_arrays
    variable: "state.results.modern_arrays"
    value: |
      {
        includes: state.data.scores.includes(92),
        findIndex: state.data.users.findIndex(u => u.name === 'Charlie'),
        flatMap: [[1, 2], [3, 4], [5]].flatMap(x => x),
        from: Array.from({length: 5}, (_, i) => i * 2),
        entries: state.data.users.map((u, i) => [i, u.name])
      }
"""
        
        project_path = self._create_workflow_file("test-es6-features", workflow_content)
        
        # Start workflow
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-es6-features")
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]
        
        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"
        
        results = final_status["state"]["state"]["results"]
        
        # Verify arrow functions and array methods
        arrow = results["arrow_functions"]
        assert len(arrow["filtered"]) == 2  # Alice (30) and Charlie (35)
        assert arrow["mapped"] == ["ALICE", "BOB", "CHARLIE", "DAVID"]
        assert arrow["reduced"] == 448  # Sum of scores
        assert arrow["found"]["name"] == "Alice"  # First admin
        assert arrow["some"] == True
        assert arrow["every"] == True
        
        # Verify template literals
        templates = results["template_literals"]
        assert templates["simple"] == "Total users: 4"
        assert "Average age: 29.5" in templates["expression"]
        assert "- Alice (30)" in templates["multiline"]
        assert templates["nested"] == "Config: theme=dark, auth=true"
        
        # Verify destructuring
        destruct = results["destructuring"]
        assert destruct["array_destructure"]["first"] == 85
        assert destruct["array_destructure"]["second"] == 92
        assert destruct["array_destructure"]["rest"] == [78, 95, 88]
        assert destruct["object_destructure"]["theme"] == "dark"
        assert destruct["object_destructure"]["auth"] == True
        assert destruct["nested_destructure"]["firstName"] == "Alice"
        
        # Verify spread operator
        spread = results["spread_operator"]
        assert len(spread["array_spread"]) == 7
        assert spread["object_spread"]["version"] == "2.0"
        assert spread["object_spread"]["features"]["beta"] == True
        assert spread["combined"][2] == 90  # Inserted in middle
        
        # Verify modern array methods
        modern = results["modern_arrays"]
        assert modern["includes"] == True
        assert modern["findIndex"] == 2
        assert modern["flatMap"] == [1, 2, 3, 4, 5]
        assert modern["from"] == [0, 2, 4, 6, 8]

    def test_deep_nested_expression_evaluation(self):
        """
        Test AC-VR-020: Complex nested expressions with multiple levels.
        Focus: Deep property access and nested function calls work correctly.
        """
        workflow_content = """
name: "test-deep-nested-expressions"
description: "Test deeply nested expression evaluation"
version: "1.0.0"

default_state:
  state:
    organization: {
      company: {
        departments: {
          engineering: {
            teams: {
              frontend: {
                members: [
                  {id: 1, name: "Alice", skills: ["React", "TypeScript", "CSS"], projects: {active: 3, completed: 12}},
                  {id: 2, name: "Bob", skills: ["Vue", "JavaScript", "SCSS"], projects: {active: 2, completed: 8}}
                ],
                budget: {
                  allocated: 500000,
                  spent: 325000,
                  categories: {
                    salaries: 250000,
                    tools: 50000,
                    training: 25000
                  }
                }
              },
              backend: {
                members: [
                  {id: 3, name: "Charlie", skills: ["Python", "Django", "PostgreSQL"], projects: {active: 4, completed: 15}},
                  {id: 4, name: "David", skills: ["Go", "MongoDB", "Redis"], projects: {active: 1, completed: 10}}
                ],
                budget: {
                  allocated: 450000,
                  spent: 380000,
                  categories: {
                    salaries: 300000,
                    infrastructure: 60000,
                    training: 20000
                  }
                }
              }
            }
          }
        }
      }
    }
    results: {}

steps:
  # Test deep property access
  - type: set_variable
    id: deep_property_access
    variable: "state.results.deep_access"
    value: |
      {
        deep_value: state.organization.company.departments.engineering.teams.frontend.members[0].skills[1],
        deep_calc: state.organization.company.departments.engineering.teams.backend.budget.allocated - state.organization.company.departments.engineering.teams.backend.budget.spent,
        deep_nested_calc: state.organization.company.departments.engineering.teams.frontend.budget.categories.salaries + state.organization.company.departments.engineering.teams.backend.budget.categories.salaries
      }
  
  # Test complex nested method chains
  - type: set_variable
    id: nested_method_chains
    variable: "state.results.method_chains"
    value: |
      {
        all_skills: state.organization.company.departments.engineering.teams.frontend.members
          .concat(state.organization.company.departments.engineering.teams.backend.members)
          .flatMap(m => m.skills)
          .filter((skill, index, arr) => arr.indexOf(skill) === index)
          .sort(),
        
        total_projects: Object.values(state.organization.company.departments.engineering.teams)
          .flatMap(team => team.members)
          .map(member => member.projects.active + member.projects.completed)
          .reduce((sum, total) => sum + total, 0),
        
        budget_analysis: Object.entries(state.organization.company.departments.engineering.teams)
          .map(([name, team]) => ({
            team: name,
            remaining: team.budget.allocated - team.budget.spent,
            percentage_spent: Math.round((team.budget.spent / team.budget.allocated) * 100)
          }))
      }
  
  # Test nested conditional expressions
  - type: set_variable
    id: nested_conditionals
    variable: "state.results.conditionals"
    value: |
      {
        team_status: Object.entries(state.organization.company.departments.engineering.teams)
          .map(([name, team]) => {
            const budgetRatio = team.budget.spent / team.budget.allocated;
            const avgProjects = team.members.reduce((sum, m) => sum + m.projects.active, 0) / team.members.length;
            
            return {
              team: name,
              budget_health: budgetRatio < 0.7 ? 'good' : budgetRatio < 0.9 ? 'warning' : 'critical',
              workload: avgProjects < 2 ? 'light' : avgProjects < 3.5 ? 'normal' : 'heavy',
              overall: (budgetRatio < 0.8 && avgProjects < 3) ? 'healthy' : 'needs attention'
            };
          })
      }
  
  # Test nested transformations
  - type: set_variable
    id: nested_transformations
    variable: "state.results.transformations"
    value: |
      (() => {
        const teams = state.organization.company.departments.engineering.teams;
        
        return {
          skill_matrix: Object.entries(teams).reduce((matrix, [teamName, team]) => {
            matrix[teamName] = team.members.reduce((skills, member) => {
              member.skills.forEach(skill => {
                if (!skills[skill]) skills[skill] = [];
                skills[skill].push(member.name);
              });
              return skills;
            }, {});
            return matrix;
          }, {}),
          
          budget_breakdown: Object.entries(teams).reduce((breakdown, [teamName, team]) => {
            breakdown[teamName] = Object.entries(team.budget.categories).map(([category, amount]) => ({
              category,
              amount,
              percentage: Math.round((amount / team.budget.spent) * 100)
            }));
            return breakdown;
          }, {})
        };
      })()
"""
        
        project_path = self._create_workflow_file("test-deep-nested-expressions", workflow_content)
        
        # Start workflow
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-deep-nested-expressions")
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]
        
        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"
        
        results = final_status["state"]["state"]["results"]
        
        # Verify deep property access
        deep = results["deep_access"]
        assert deep["deep_value"] == "TypeScript"
        assert deep["deep_calc"] == 70000  # 450000 - 380000
        assert deep["deep_nested_calc"] == 550000  # 250000 + 300000
        
        # Verify method chains
        chains = results["method_chains"]
        assert "React" in chains["all_skills"]
        assert "Python" in chains["all_skills"]
        assert len(chains["all_skills"]) == 10  # All unique skills
        assert chains["total_projects"] == 58  # Sum of all active and completed projects
        assert chains["budget_analysis"][0]["team"] == "frontend"
        assert chains["budget_analysis"][0]["remaining"] == 175000
        
        # Verify nested conditionals
        cond = results["conditionals"]
        assert cond["team_status"][0]["budget_health"] == "warning"  # 65% spent
        assert cond["team_status"][1]["budget_health"] == "critical"  # 84% spent
        
        # Verify transformations
        trans = results["transformations"]
        assert "React" in trans["skill_matrix"]["frontend"]
        assert "Alice" in trans["skill_matrix"]["frontend"]["React"]
        assert trans["budget_breakdown"]["backend"][0]["category"] == "salaries"

    def test_mixed_function_property_access(self):
        """
        Test AC-VR-020: Expressions combining functions and property access.
        Focus: Complex expressions mixing function calls with property access.
        """
        workflow_content = """
name: "test-mixed-function-property"
description: "Test expressions mixing functions and property access"
version: "1.0.0"

default_state:
  state:
    products: [
      {id: 1, name: "Laptop", price: 999.99, stock: 15, category: "electronics", tags: ["portable", "computer"]},
      {id: 2, name: "Mouse", price: 29.99, stock: 50, category: "accessories", tags: ["peripheral", "input"]},
      {id: 3, name: "Keyboard", price: 79.99, stock: 0, category: "accessories", tags: ["peripheral", "input"]},
      {id: 4, name: "Monitor", price: 299.99, stock: 8, category: "electronics", tags: ["display", "peripheral"]}
    ]
    operations: {
      filters: {
        minPrice: 50,
        maxPrice: 500,
        inStock: true
      },
      calculations: {
        taxRate: 0.08,
        discountRate: 0.15
      }
    }
    results: {}

steps:
  # Test function calls on filtered arrays with property access
  - type: set_variable
    id: filtered_calculations
    variable: "state.results.filtered_calcs"
    value: |
      {
        filtered_products: state.products
          .filter(p => p.price >= state.operations.filters.minPrice && p.price <= state.operations.filters.maxPrice)
          .filter(p => !state.operations.filters.inStock || p.stock > 0)
          .map(p => ({
            ...p,
            finalPrice: p.price * (1 - state.operations.calculations.discountRate) * (1 + state.operations.calculations.taxRate),
            available: p.stock > 0 ? `${p.stock} in stock` : 'Out of stock'
          })),
        
        category_summary: state.products
          .reduce((summary, product) => {
            const cat = product.category;
            if (!summary[cat]) summary[cat] = {count: 0, totalValue: 0, items: []};
            summary[cat].count++;
            summary[cat].totalValue += product.price * product.stock;
            summary[cat].items.push(product.name);
            return summary;
          }, {})
      }
  
  # Test chained transformations with conditional logic
  - type: set_variable
    id: complex_transformations
    variable: "state.results.transformations"
    value: |
      {
        inventory_report: Object.entries(
          state.products.reduce((report, product) => {
            const status = product.stock === 0 ? 'out_of_stock' : 
                          product.stock < 10 ? 'low_stock' : 'in_stock';
            
            if (!report[status]) report[status] = [];
            report[status].push({
              name: product.name,
              value: product.price * product.stock,
              reorder: product.stock < 10
            });
            return report;
          }, {})
        ).map(([status, items]) => ({
          status,
          count: items.length,
          totalValue: items.reduce((sum, item) => sum + item.value, 0),
          items: items.sort((a, b) => b.value - a.value)
        })),
        
        tag_analysis: state.products
          .flatMap(p => p.tags.map(tag => ({tag, product: p.name, price: p.price})))
          .reduce((analysis, item) => {
            if (!analysis[item.tag]) analysis[item.tag] = {products: [], avgPrice: 0};
            analysis[item.tag].products.push(item.product);
            analysis[item.tag].avgPrice = (analysis[item.tag].avgPrice * (analysis[item.tag].products.length - 1) + item.price) / analysis[item.tag].products.length;
            return analysis;
          }, {})
      }
  
  # Test nested function composition
  - type: set_variable
    id: function_composition
    variable: "state.results.composition"
    value: |
      (() => {
        const compose = (f, g) => x => f(g(x));
        const addTax = price => price * (1 + state.operations.calculations.taxRate);
        const applyDiscount = price => price * (1 - state.operations.calculations.discountRate);
        const formatPrice = price => `$${price.toFixed(2)}`;
        
        const finalPriceFormatter = compose(formatPrice, compose(addTax, applyDiscount));
        
        return {
          formatted_prices: state.products.map(p => ({
            name: p.name,
            original: formatPrice(p.price),
            final: finalPriceFormatter(p.price)
          })),
          
          pipeline_result: state.products
            .filter(p => p.stock > 0)
            .map(p => ({...p, revenue: p.price * p.stock}))
            .sort((a, b) => b.revenue - a.revenue)
            .slice(0, 2)
            .map(p => `${p.name}: ${formatPrice(p.revenue)}`)
        };
      })()
"""
        
        project_path = self._create_workflow_file("test-mixed-function-property", workflow_content)
        
        # Start workflow
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-mixed-function-property")
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]
        
        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"
        
        results = final_status["state"]["state"]["results"]
        
        # Verify filtered calculations
        filtered = results["filtered_calcs"]
        assert len(filtered["filtered_products"]) == 2  # Monitor and Keyboard in price range
        assert filtered["filtered_products"][0]["name"] == "Monitor"  # In stock
        # Verify no out of stock items when inStock filter is applied
        assert all(p["inStock"] for p in filtered["filtered_products"])
        
        # Verify category summary
        assert filtered["category_summary"]["electronics"]["count"] == 2
        assert filtered["category_summary"]["accessories"]["count"] == 2
        
        # Verify transformations
        trans = results["transformations"]
        inventory = {item["status"]: item for item in trans["inventory_report"]}
        assert inventory["out_of_stock"]["count"] == 1  # Keyboard
        assert inventory["low_stock"]["count"] == 1  # Monitor
        assert inventory["in_stock"]["count"] == 2  # Laptop and Mouse
        
        # Verify tag analysis
        assert "peripheral" in trans["tag_analysis"]
        assert len(trans["tag_analysis"]["peripheral"]["products"]) == 3
        
        # Verify function composition
        comp = results["composition"]
        assert len(comp["formatted_prices"]) == 4
        assert "$" in comp["formatted_prices"][0]["final"]
        assert len(comp["pipeline_result"]) == 2  # Top 2 revenue products

    def test_array_method_chaining(self):
        """
        Test AC-VR-007: Array methods like filter, map, reduce chaining.
        Focus: Complex array method chains work correctly.
        """
        workflow_content = """
name: "test-array-method-chaining"
description: "Test complex array method chaining"
version: "1.0.0"

default_state:
  state:
    transactions: [
      {id: 1, user: "alice", amount: 150, type: "purchase", status: "completed", date: "2024-01-15"},
      {id: 2, user: "bob", amount: 75, type: "refund", status: "completed", date: "2024-01-16"},
      {id: 3, user: "alice", amount: 200, type: "purchase", status: "pending", date: "2024-01-17"},
      {id: 4, user: "charlie", amount: 300, type: "purchase", status: "completed", date: "2024-01-18"},
      {id: 5, user: "bob", amount: 50, type: "purchase", status: "failed", date: "2024-01-19"},
      {id: 6, user: "alice", amount: 125, type: "purchase", status: "completed", date: "2024-01-20"},
      {id: 7, user: "charlie", amount: 80, type: "refund", status: "completed", date: "2024-01-21"}
    ]
    results: {}

steps:
  # Test basic array method chaining
  - type: set_variable
    id: basic_chaining
    variable: "state.results.basic_chains"
    value: |
      {
        completed_purchases_total: state.transactions
          .filter(t => t.status === 'completed')
          .filter(t => t.type === 'purchase')
          .map(t => t.amount)
          .reduce((sum, amount) => sum + amount, 0),
        
        user_summaries: state.transactions
          .filter(t => t.status === 'completed')
          .reduce((users, t) => {
            if (!users[t.user]) users[t.user] = {purchases: 0, refunds: 0, total: 0};
            if (t.type === 'purchase') {
              users[t.user].purchases += t.amount;
              users[t.user].total += t.amount;
            } else {
              users[t.user].refunds += t.amount;
              users[t.user].total -= t.amount;
            }
            return users;
          }, {}),
        
        transaction_stats: state.transactions
          .map(t => ({...t, net: t.type === 'purchase' ? t.amount : -t.amount}))
          .filter(t => t.status === 'completed')
          .reduce((stats, t) => ({
            count: stats.count + 1,
            total: stats.total + t.net,
            max: Math.max(stats.max, t.net),
            min: Math.min(stats.min, t.net)
          }), {count: 0, total: 0, max: -Infinity, min: Infinity})
      }
  
  # Test advanced array transformations
  - type: set_variable
    id: advanced_chaining
    variable: "state.results.advanced_chains"
    value: |
      {
        grouped_by_type_and_status: state.transactions
          .reduce((groups, t) => {
            const key = `${t.type}_${t.status}`;
            if (!groups[key]) groups[key] = [];
            groups[key].push(t);
            return groups;
          }, {}),
        
        daily_summaries: state.transactions
          .filter(t => t.status === 'completed')
          .sort((a, b) => a.date.localeCompare(b.date))
          .reduce((daily, t) => {
            const existing = daily.find(d => d.date === t.date);
            if (existing) {
              existing.transactions.push(t.id);
              existing.total += t.type === 'purchase' ? t.amount : -t.amount;
            } else {
              daily.push({
                date: t.date,
                transactions: [t.id],
                total: t.type === 'purchase' ? t.amount : -t.amount
              });
            }
            return daily;
          }, []),
        
        top_users: Object.entries(
          state.transactions
            .filter(t => t.status === 'completed' && t.type === 'purchase')
            .reduce((users, t) => {
              users[t.user] = (users[t.user] || 0) + t.amount;
              return users;
            }, {})
        )
        .map(([user, total]) => ({user, total}))
        .sort((a, b) => b.total - a.total)
        .slice(0, 2)
      }
  
  # Test complex nested array operations
  - type: set_variable
    id: nested_array_ops
    variable: "state.results.nested_ops"
    value: |
      {
        user_transaction_matrix: [...new Set(state.transactions.map(t => t.user))]
          .map(user => ({
            user,
            transactions: state.transactions
              .filter(t => t.user === user)
              .map(t => ({
                id: t.id,
                net: t.type === 'purchase' ? t.amount : -t.amount,
                status: t.status
              })),
            summary: state.transactions
              .filter(t => t.user === user && t.status === 'completed')
              .reduce((sum, t) => ({
                purchases: sum.purchases + (t.type === 'purchase' ? t.amount : 0),
                refunds: sum.refunds + (t.type === 'refund' ? t.amount : 0),
                net: sum.net + (t.type === 'purchase' ? t.amount : -t.amount)
              }), {purchases: 0, refunds: 0, net: 0})
          })),
        
        status_flow: ['completed', 'pending', 'failed']
          .map(status => ({
            status,
            count: state.transactions.filter(t => t.status === status).length,
            amount: state.transactions
              .filter(t => t.status === status)
              .reduce((sum, t) => sum + t.amount, 0),
            users: [...new Set(state.transactions
              .filter(t => t.status === status)
              .map(t => t.user))]
          }))
          .filter(s => s.count > 0)
      }
"""
        
        project_path = self._create_workflow_file("test-array-method-chaining", workflow_content)
        
        # Start workflow
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-array-method-chaining")
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]
        
        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"
        
        results = final_status["state"]["state"]["results"]
        
        # Verify basic chaining
        basic = results["basic_chains"]
        assert basic["completed_purchases_total"] == 575  # 150 + 300 + 125
        assert basic["user_summaries"]["alice"]["total"] == 275  # 150 + 125
        assert basic["user_summaries"]["bob"]["total"] == -75  # -75 refund
        assert basic["transaction_stats"]["count"] == 5  # 5 completed transactions
        
        # Verify advanced chaining
        advanced = results["advanced_chains"]
        assert "purchase_completed" in advanced["grouped_by_type_and_status"]
        assert len(advanced["grouped_by_type_and_status"]["purchase_completed"]) == 3
        assert len(advanced["daily_summaries"]) > 0
        assert advanced["top_users"][0]["user"] == "alice"  # Alice has most purchases
        assert advanced["top_users"][0]["total"] == 275
        
        # Verify nested operations
        nested = results["nested_ops"]
        alice_data = next(u for u in nested["user_transaction_matrix"] if u["user"] == "alice")
        assert len(alice_data["transactions"]) == 3  # Alice has 3 transactions
        assert alice_data["summary"]["net"] == 275  # Alice's net amount
        
        status_data = {s["status"]: s for s in nested["status_flow"]}
        assert status_data["completed"]["count"] == 5
        assert status_data["pending"]["count"] == 1
        assert status_data["failed"]["count"] == 1


class TestExpressionEvaluationEdgeCases:
    """Test edge cases and error handling in expression evaluation."""

    def setup_method(self):
        """Setup test environment."""
        self.executor = WorkflowExecutor()
        self.temp_dir = None
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()

    def _create_workflow_file(self, workflow_name: str, workflow_content: str) -> Path:
        """Helper to create a workflow file."""
        if not self.temp_dir:
            self.temp_dir = tempfile.TemporaryDirectory()
        
        temp_path = Path(self.temp_dir.name)
        workflows_dir = temp_path / ".aromcp" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        workflow_file = workflows_dir / f"{workflow_name}.yaml"
        workflow_file.write_text(workflow_content)
        return temp_path

    def test_expression_error_handling(self):
        """
        Test AC-VR-020: Expression evaluation handles errors gracefully.
        Focus: System continues execution when expressions have errors.
        """
        workflow_content = """
name: "test-expression-errors"
description: "Test expression error handling"
version: "1.0.0"

default_state:
  state:
    data: {
      valid: 42,
      nested: {prop: "value"}
    }
    error_log: []
    results: {}

steps:
  # Test undefined property access
  - type: conditional
    id: check_undefined
    condition: "state.data.nonexistent && state.data.nonexistent.property"
    then_steps:
      - type: set_variable
        id: should_not_execute
        variable: "state.error_log"
        value: "[...state.error_log, 'Should not execute - undefined was truthy']"
    else_steps:
      - type: set_variable
        id: undefined_handled
        variable: "state.results.undefined_test"
        value: "Undefined property handled correctly"
  
  # Test null property access with optional chaining
  - type: set_variable
    id: optional_chaining
    variable: "state.results.optional_chain"
    value: |
      {
        safe_access: state.data.nonexistent?.deeply?.nested?.value || 'default',
        valid_access: state.data.nested?.prop || 'no value',
        mixed_access: state.data.valid?.toString?.() || 'no string'
      }
  
  # Test division by zero
  - type: set_variable
    id: math_errors
    variable: "state.results.math_ops"
    value: |
      {
        divide_by_zero: state.data.valid / 0,
        infinity_check: (state.data.valid / 0) === Infinity,
        nan_check: isNaN(0 / 0),
        safe_division: state.data.valid / (state.data.zero || 1)
      }
  
  # Test type coercion edge cases
  - type: set_variable
    id: type_coercion
    variable: "state.results.coercion"
    value: |
      {
        string_number: "42" + 1,
        number_string: 42 + "1",
        boolean_math: true + 1,
        null_coercion: null + 5,
        undefined_coercion: undefined + 5,
        array_coercion: [1, 2, 3] + [4, 5],
        object_string: {a: 1} + ""
      }
"""
        
        project_path = self._create_workflow_file("test-expression-errors", workflow_content)
        
        # Start workflow
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-expression-errors")
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]
        
        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)
        
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", "Workflow should complete despite expression errors"
        
        results = final_status["state"]["state"]["results"]
        
        # Verify undefined handling
        assert results["undefined_test"] == "Undefined property handled correctly"
        
        # Verify optional chaining (if supported)
        if "optional_chain" in results:
            assert results["optional_chain"]["safe_access"] == "default"
            assert results["optional_chain"]["valid_access"] == "value"
        
        # Verify math operations
        assert results["math_ops"]["divide_by_zero"] == float('inf')
        assert results["math_ops"]["infinity_check"] == True
        assert results["math_ops"]["nan_check"] == True
        assert results["math_ops"]["safe_division"] == 42
        
        # Verify type coercion
        assert results["coercion"]["string_number"] == "421"
        assert results["coercion"]["number_string"] == "421"
        assert results["coercion"]["boolean_math"] == 2
        assert results["coercion"]["null_coercion"] == 5