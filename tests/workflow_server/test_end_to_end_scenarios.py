"""
End-to-end test scenarios for workflow_server.

Tests real-world workflow scenarios that exercise the full system capabilities.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

from aromcp.workflow_server.workflow.models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance
)
from aromcp.workflow_server.models.workflow_models import WorkflowStatusResponse
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.loader import WorkflowLoader


class TestECommerceOrderProcessing:
    """Test e-commerce order processing workflow scenario."""
    
    @pytest.fixture
    def ecommerce_workflow(self):
        """Create a realistic e-commerce order processing workflow."""
        return WorkflowDefinition(
            name="ecommerce_order_processing",
            version="2.0",
            metadata={
                "description": "Process customer orders from placement to fulfillment",
                "timeout": 3600,  # 1 hour timeout
                "monitor_performance": True
            },
            triggers=[
                {"type": "webhook", "config": {"path": "/orders/new"}},
                {"type": "manual"}
            ],
            input_schema={
                "type": "object",
                "required": ["order_id", "customer_id", "items", "payment_method"],
                "properties": {
                    "order_id": {"type": "string"},
                    "customer_id": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "price": {"type": "number"}
                            }
                        }
                    },
                    "payment_method": {"type": "string"},
                    "shipping_address": {"type": "object"}
                }
            },
            steps=[
                # Validate order
                WorkflowStep(
                    id="validate_order",
                    type="agent_prompt",
                    config={
                        "prompt": """Validate order details:
                        Order ID: {{ inputs.order_id }}
                        Customer ID: {{ inputs.customer_id }}
                        Items: {{ inputs.items | json }}
                        
                        Check for:
                        1. Valid customer ID
                        2. All products in stock
                        3. Pricing accuracy
                        """,
                        "timeout": 30,
                        "error_handling": {
                            "strategy": "fail",
                            "message": "Order validation failed"
                        }
                    }
                ),
                
                # Calculate totals
                WorkflowStep(
                    id="calculate_totals",
                    type="state_update",
                    config={
                        "updates": {
                            "subtotal": "{{ inputs.items | map(attribute='price') | map('multiply', attribute='quantity') | sum }}",
                            "tax": "{{ state.subtotal * 0.08 }}",
                            "shipping": "{{ 10 if state.subtotal < 50 else 0 }}",
                            "total": "{{ state.subtotal + state.tax + state.shipping }}"
                        }
                    }
                ),
                
                # Process payment
                WorkflowStep(
                    id="process_payment",
                    type="mcp_call",
                    config={
                        "server": "payment_gateway",
                        "tool": "charge_payment",
                        "arguments": {
                            "amount": "{{ state.total }}",
                            "currency": "USD",
                            "customer_id": "{{ inputs.customer_id }}",
                            "payment_method": "{{ inputs.payment_method }}",
                            "order_id": "{{ inputs.order_id }}"
                        },
                        "timeout": 60,
                        "error_handling": {
                            "strategy": "retry",
                            "max_retries": 3,
                            "backoff": "exponential"
                        }
                    }
                ),
                
                # Check payment status
                WorkflowStep(
                    id="check_payment",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ steps.process_payment.output.status == 'success' }}",
                                "then": [
                                    {
                                        "id": "update_inventory",
                                        "type": "foreach",
                                        "config": {
                                            "items": "{{ inputs.items }}",
                                            "parallel": True,
                                            "steps": [
                                                {
                                                    "id": "decrement_stock",
                                                    "type": "mcp_call",
                                                    "config": {
                                                        "server": "inventory_service",
                                                        "tool": "update_stock",
                                                        "arguments": {
                                                            "product_id": "{{ item.product_id }}",
                                                            "quantity_change": "{{ -item.quantity }}"
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                "if": "{{ steps.process_payment.output.status == 'declined' }}",
                                "then": [
                                    {
                                        "id": "notify_payment_failure",
                                        "type": "agent_prompt",
                                        "config": {
                                            "prompt": "Send payment failure notification to customer {{ inputs.customer_id }}",
                                            "sub_agent": {
                                                "id": "notification_agent",
                                                "capabilities": ["email", "sms"]
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ),
                
                # Create shipping label
                WorkflowStep(
                    id="create_shipping",
                    type="agent_prompt",
                    config={
                        "prompt": """Create shipping label for:
                        Order: {{ inputs.order_id }}
                        Address: {{ inputs.shipping_address | json }}
                        Items: {{ inputs.items | length }} items
                        Weight: Calculate based on products
                        """,
                        "depends_on": ["update_inventory"],
                        "timeout": 45
                    }
                ),
                
                # Send confirmation
                WorkflowStep(
                    id="send_confirmation",
                    type="agent_prompt",
                    config={
                        "prompt": """Send order confirmation to customer:
                        Order ID: {{ inputs.order_id }}
                        Total: ${{ state.total }}
                        Tracking: {{ steps.create_shipping.output.tracking_number }}
                        Estimated Delivery: {{ steps.create_shipping.output.estimated_delivery }}
                        """,
                        "sub_agent": {
                            "id": "notification_agent",
                            "capabilities": ["email", "sms", "push_notification"]
                        }
                    }
                ),
                
                # Update order status
                WorkflowStep(
                    id="finalize_order",
                    type="state_update",
                    config={
                        "updates": {
                            "order_status": "confirmed",
                            "payment_id": "{{ steps.process_payment.output.transaction_id }}",
                            "tracking_number": "{{ steps.create_shipping.output.tracking_number }}",
                            "completed_at": "{{ now() }}"
                        }
                    }
                )
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "status": {"type": "string"},
                    "total": {"type": "number"},
                    "tracking_number": {"type": "string"}
                }
            }
        )
    
    @pytest.mark.asyncio
    async def test_successful_order_processing(self, ecommerce_workflow):
        """Test successful order processing from start to finish."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # Sample order data
        order_data = {
            "order_id": f"ORD-{uuid.uuid4().hex[:8]}",
            "customer_id": "CUST-12345",
            "items": [
                {"product_id": "PROD-001", "quantity": 2, "price": 29.99},
                {"product_id": "PROD-002", "quantity": 1, "price": 49.99}
            ],
            "payment_method": "credit_card",
            "shipping_address": {
                "street": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94105"
            }
        }
        
        # Start workflow
        result = await executor.start_workflow(ecommerce_workflow, order_data)
        workflow_id = result['workflow_id']
        
        # Mock external services
        mock_mcp = AsyncMock()
        
        # Mock responses for different tools
        def mock_tool_response(tool, arguments):
            if tool == "charge_payment":
                return {
                    "status": "success",
                    "transaction_id": f"TXN-{uuid.uuid4().hex[:8]}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            elif tool == "update_stock":
                return {
                    "product_id": arguments["product_id"],
                    "new_stock_level": 100 - arguments["quantity_change"]
                }
            elif "notification" in str(arguments.get("prompt", "")):
                return {
                    "content": "Notification sent successfully",
                    "delivery_status": "delivered"
                }
            elif "shipping" in str(arguments.get("prompt", "")):
                return {
                    "content": json.dumps({
                        "tracking_number": f"TRACK-{uuid.uuid4().hex[:8]}",
                        "estimated_delivery": (datetime.utcnow() + timedelta(days=3)).isoformat()
                    })
                }
            else:
                return {"content": "Validation successful"}
        
        mock_mcp.call_tool.side_effect = lambda tool, arguments: mock_tool_response(tool, arguments)
        
        # Execute workflow
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            while executor.has_pending_workflows():
                await executor.execute_next()
                await asyncio.sleep(0.1)
        
        # Verify final state
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state['status'] == WorkflowStatusResponse.COMPLETED.value
        
        # Check calculated values
        workflow_state = final_state['state']
        expected_subtotal = 2 * 29.99 + 49.99
        assert abs(workflow_state['subtotal'] - expected_subtotal) < 0.01
        assert abs(workflow_state['tax'] - expected_subtotal * 0.08) < 0.01
        assert workflow_state['shipping'] == 0  # Free shipping for > $50
        
        # Verify order completion
        assert workflow_state['order_status'] == 'confirmed'
        assert 'payment_id' in workflow_state
        assert 'tracking_number' in workflow_state
        assert 'completed_at' in workflow_state
    
    @pytest.mark.asyncio
    async def test_order_with_payment_failure_recovery(self, ecommerce_workflow):
        """Test order processing with payment failure and recovery."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        order_data = {
            "order_id": f"ORD-{uuid.uuid4().hex[:8]}",
            "customer_id": "CUST-67890",
            "items": [
                {"product_id": "PROD-003", "quantity": 1, "price": 199.99}
            ],
            "payment_method": "debit_card",
            "shipping_address": {
                "street": "456 Oak Ave",
                "city": "New York",
                "state": "NY",
                "zip": "10001"
            }
        }
        
        result = await executor.start_workflow(ecommerce_workflow, order_data)
        workflow_id = result['workflow_id']
        
        # Mock with payment failures then success
        mock_mcp = AsyncMock()
        payment_attempts = 0
        
        def mock_tool_response(tool, arguments):
            nonlocal payment_attempts
            
            if tool == "charge_payment":
                payment_attempts += 1
                if payment_attempts < 3:
                    # Fail first two attempts
                    return {
                        "status": "error",
                        "error_code": "INSUFFICIENT_FUNDS",
                        "message": "Payment declined"
                    }
                else:
                    # Succeed on third attempt
                    return {
                        "status": "success",
                        "transaction_id": f"TXN-{uuid.uuid4().hex[:8]}"
                    }
            else:
                return {"content": "Success"}
        
        mock_mcp.call_tool.side_effect = lambda tool, arguments: mock_tool_response(tool, arguments)
        
        # Execute with retries
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            execution_count = 0
            while executor.has_pending_workflows() and execution_count < 20:
                await executor.execute_next()
                await asyncio.sleep(0.1)
                execution_count += 1
        
        # Verify retry behavior
        assert payment_attempts == 3
        
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state['status'] == WorkflowStatusResponse.COMPLETED.value


class TestDataPipelineProcessing:
    """Test data pipeline workflow scenarios."""
    
    @pytest.fixture
    def data_pipeline_workflow(self):
        """Create a data processing pipeline workflow."""
        return WorkflowDefinition(
            name="data_pipeline",
            version="1.0",
            metadata={
                "description": "ETL pipeline for processing data files",
                "batch_size": 100,
                "parallel_workers": 4
            },
            triggers=[
                {"type": "schedule", "config": {"cron": "0 2 * * *"}},
                {"type": "file_watch", "config": {"path": "/data/incoming"}}
            ],
            input_schema={
                "type": "object",
                "required": ["source_path", "destination_path"],
                "properties": {
                    "source_path": {"type": "string"},
                    "destination_path": {"type": "string"},
                    "file_pattern": {"type": "string", "default": "*.csv"},
                    "processing_options": {"type": "object"}
                }
            },
            steps=[
                # Discover files
                WorkflowStep(
                    id="discover_files",
                    type="mcp_call",
                    config={
                        "server": "filesystem",
                        "tool": "list_files",
                        "arguments": {
                            "path": "{{ inputs.source_path }}",
                            "pattern": "{{ inputs.file_pattern }}",
                            "recursive": True
                        }
                    }
                ),
                
                # Validate files
                WorkflowStep(
                    id="validate_files",
                    type="foreach",
                    config={
                        "items": "{{ steps.discover_files.output.files }}",
                        "parallel": True,
                        "max_concurrent": 10,
                        "steps": [
                            {
                                "id": "check_file",
                                "type": "agent_prompt",
                                "config": {
                                    "prompt": "Validate data file: {{ item.path }}\n- Check format\n- Verify schema\n- Detect anomalies",
                                    "timeout": 15
                                }
                            }
                        ]
                    }
                ),
                
                # Process in batches
                WorkflowStep(
                    id="batch_process",
                    type="foreach",
                    config={
                        "items": "{{ steps.discover_files.output.files | batch(metadata.batch_size) }}",
                        "parallel": True,
                        "max_concurrent": "{{ metadata.parallel_workers }}",
                        "steps": [
                            {
                                "id": "process_batch",
                                "type": "agent_prompt",
                                "config": {
                                    "prompt": """Process batch of {{ item | length }} files:
                                    {% for file in item %}
                                    - {{ file.name }}: {{ file.size }} bytes
                                    {% endfor %}
                                    
                                    Apply transformations:
                                    1. Clean data
                                    2. Apply business rules
                                    3. Aggregate metrics
                                    """,
                                    "sub_agent": {
                                        "id": "data_processor_{{ loop.index }}",
                                        "capabilities": ["data_processing", "analytics"],
                                        "resource_limits": {
                                            "memory": "2GB",
                                            "cpu": "2"
                                        }
                                    }
                                }
                            }
                        ]
                    }
                ),
                
                # Merge results
                WorkflowStep(
                    id="merge_results",
                    type="agent_prompt",
                    config={
                        "prompt": """Merge all processed batches:
                        Total batches: {{ steps.batch_process.output | length }}
                        
                        Create unified dataset with:
                        - Consistent schema
                        - Deduplication
                        - Quality metrics
                        """,
                        "timeout": 120
                    }
                ),
                
                # Generate report
                WorkflowStep(
                    id="generate_report",
                    type="agent_prompt",
                    config={
                        "prompt": """Generate processing report:
                        - Files processed: {{ steps.discover_files.output.files | length }}
                        - Total records: {{ steps.merge_results.output.total_records }}
                        - Processing time: {{ workflow.duration }}
                        - Data quality score: {{ steps.merge_results.output.quality_score }}
                        """
                    }
                ),
                
                # Store results
                WorkflowStep(
                    id="store_results",
                    type="mcp_call",
                    config={
                        "server": "filesystem",
                        "tool": "write_files",
                        "arguments": {
                            "files": [
                                {
                                    "path": "{{ inputs.destination_path }}/processed_data.parquet",
                                    "content": "{{ steps.merge_results.output.data }}"
                                },
                                {
                                    "path": "{{ inputs.destination_path }}/report.json",
                                    "content": "{{ steps.generate_report.output | json }}"
                                }
                            ]
                        }
                    }
                )
            ]
        )
    
    @pytest.mark.asyncio
    async def test_large_scale_data_processing(self, data_pipeline_workflow):
        """Test processing large number of files in parallel."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # Input configuration
        pipeline_inputs = {
            "source_path": "/data/raw",
            "destination_path": "/data/processed",
            "file_pattern": "*.csv",
            "processing_options": {
                "remove_duplicates": True,
                "normalize_dates": True,
                "validate_schema": True
            }
        }
        
        result = await executor.start_workflow(data_pipeline_workflow, pipeline_inputs)
        workflow_id = result['workflow_id']
        
        # Mock file discovery and processing
        mock_mcp = AsyncMock()
        
        # Generate mock files
        mock_files = [
            {"name": f"data_{i:04d}.csv", "path": f"/data/raw/data_{i:04d}.csv", "size": 1024 * (i + 1)}
            for i in range(250)  # 250 files to process
        ]
        
        def mock_tool_response(tool, arguments):
            if tool == "list_files":
                return {"files": mock_files}
            elif tool == "write_files":
                return {"success": True, "files_written": len(arguments["files"])}
            else:
                # Mock processing responses
                return {
                    "content": json.dumps({
                        "processed": True,
                        "total_records": 10000,
                        "quality_score": 0.95,
                        "data": "mock_processed_data"
                    })
                }
        
        mock_mcp.call_tool.side_effect = lambda tool, arguments: mock_tool_response(tool, arguments)
        
        # Execute pipeline
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            execution_start = datetime.utcnow()
            
            while executor.has_pending_workflows():
                await executor.execute_next()
                
                # Check parallel execution
                workflow_state = state_manager.get_workflow_state(workflow_id)
                active_steps = [
                    s for s in workflow_state.get('step_states', {}).values()
                    if s.get('status') == 'running'
                ]
                
                # Verify parallelism constraints
                assert len(active_steps) <= 10  # max_concurrent for validation
                
                await asyncio.sleep(0.05)
        
        # Verify completion
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state['status'] == WorkflowStatusResponse.COMPLETED.value
        
        # Check all files were processed
        execution_duration = (datetime.utcnow() - execution_start).total_seconds()
        print(f"Processed {len(mock_files)} files in {execution_duration:.2f} seconds")


class TestMultiStepApprovalWorkflow:
    """Test multi-step approval workflow scenarios."""
    
    @pytest.fixture
    def approval_workflow(self):
        """Create a multi-step approval workflow."""
        return WorkflowDefinition(
            name="multi_step_approval",
            version="1.0",
            metadata={
                "description": "Multi-level approval process for requests",
                "sla_hours": 48
            },
            input_schema={
                "type": "object",
                "required": ["request_id", "request_type", "amount", "requester"],
                "properties": {
                    "request_id": {"type": "string"},
                    "request_type": {"type": "string", "enum": ["purchase", "travel", "hire"]},
                    "amount": {"type": "number"},
                    "requester": {"type": "object"},
                    "justification": {"type": "string"}
                }
            },
            steps=[
                # Determine approval chain
                WorkflowStep(
                    id="determine_approvers",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ inputs.amount < 1000 }}",
                                "then": [
                                    {
                                        "id": "set_single_approver",
                                        "type": "state_update",
                                        "config": {
                                            "updates": {
                                                "approval_chain": ["manager"],
                                                "approval_threshold": 1
                                            }
                                        }
                                    }
                                ]
                            },
                            {
                                "if": "{{ inputs.amount >= 1000 and inputs.amount < 10000 }}",
                                "then": [
                                    {
                                        "id": "set_dual_approvers",
                                        "type": "state_update",
                                        "config": {
                                            "updates": {
                                                "approval_chain": ["manager", "director"],
                                                "approval_threshold": 2
                                            }
                                        }
                                    }
                                ]
                            },
                            {
                                "if": "{{ inputs.amount >= 10000 }}",
                                "then": [
                                    {
                                        "id": "set_executive_approvers",
                                        "type": "state_update",
                                        "config": {
                                            "updates": {
                                                "approval_chain": ["manager", "director", "vp", "cfo"],
                                                "approval_threshold": 3
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ),
                
                # Initialize approval tracking
                WorkflowStep(
                    id="init_approvals",
                    type="state_update",
                    config={
                        "updates": {
                            "approvals": [],
                            "rejections": [],
                            "current_level": 0,
                            "status": "pending"
                        }
                    }
                ),
                
                # Approval loop
                WorkflowStep(
                    id="approval_loop",
                    type="while",
                    config={
                        "condition": "{{ state.current_level < state.approval_chain | length and state.status == 'pending' }}",
                        "max_iterations": 10,
                        "steps": [
                            {
                                "id": "request_approval",
                                "type": "user_input",
                                "config": {
                                    "prompt": """Approval Request:
                                    Type: {{ inputs.request_type }}
                                    Amount: ${{ inputs.amount }}
                                    Requester: {{ inputs.requester.name }}
                                    Justification: {{ inputs.justification }}
                                    
                                    Current Approver: {{ state.approval_chain[state.current_level] }}
                                    Previous Approvals: {{ state.approvals | length }}
                                    
                                    Please review and provide decision.
                                    """,
                                    "schema": {
                                        "type": "object",
                                        "required": ["decision", "comments"],
                                        "properties": {
                                            "decision": {"type": "string", "enum": ["approve", "reject", "request_info"]},
                                            "comments": {"type": "string"}
                                        }
                                    },
                                    "timeout": 86400  # 24 hours
                                }
                            },
                            {
                                "id": "process_decision",
                                "type": "conditional",
                                "config": {
                                    "conditions": [
                                        {
                                            "if": "{{ steps.request_approval.output.decision == 'approve' }}",
                                            "then": [
                                                {
                                                    "id": "record_approval",
                                                    "type": "state_update",
                                                    "config": {
                                                        "updates": {
                                                            "approvals": "{{ state.approvals + [{'approver': state.approval_chain[state.current_level], 'timestamp': now(), 'comments': steps.request_approval.output.comments}] }}",
                                                            "current_level": "{{ state.current_level + 1 }}"
                                                        }
                                                    }
                                                }
                                            ]
                                        },
                                        {
                                            "if": "{{ steps.request_approval.output.decision == 'reject' }}",
                                            "then": [
                                                {
                                                    "id": "record_rejection",
                                                    "type": "state_update",
                                                    "config": {
                                                        "updates": {
                                                            "rejections": "{{ state.rejections + [{'approver': state.approval_chain[state.current_level], 'timestamp': now(), 'reason': steps.request_approval.output.comments}] }}",
                                                            "status": "rejected"
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ),
                
                # Final decision
                WorkflowStep(
                    id="final_decision",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ state.approvals | length >= state.approval_threshold }}",
                                "then": [
                                    {
                                        "id": "approve_request",
                                        "type": "state_update",
                                        "config": {
                                            "updates": {
                                                "status": "approved",
                                                "approved_at": "{{ now() }}"
                                            }
                                        }
                                    },
                                    {
                                        "id": "notify_approval",
                                        "type": "agent_prompt",
                                        "config": {
                                            "prompt": "Send approval notification to {{ inputs.requester.email }}"
                                        }
                                    }
                                ]
                            },
                            {
                                "if": "{{ state.status == 'rejected' }}",
                                "then": [
                                    {
                                        "id": "notify_rejection",
                                        "type": "agent_prompt",
                                        "config": {
                                            "prompt": "Send rejection notification with reasons: {{ state.rejections | json }}"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                )
            ]
        )
    
    @pytest.mark.asyncio
    async def test_complex_approval_chain(self, approval_workflow):
        """Test approval workflow with multiple approvers."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # High-value request requiring multiple approvals
        request_data = {
            "request_id": f"REQ-{uuid.uuid4().hex[:8]}",
            "request_type": "purchase",
            "amount": 25000,
            "requester": {
                "name": "John Doe",
                "email": "john.doe@company.com",
                "department": "Engineering"
            },
            "justification": "New server infrastructure for scaling"
        }
        
        result = await executor.start_workflow(approval_workflow, request_data)
        workflow_id = result['workflow_id']
        
        # Mock approvals
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = {"content": "Notification sent"}
        
        approval_sequence = [
            {"decision": "approve", "comments": "Necessary for growth"},
            {"decision": "approve", "comments": "Budget available"},
            {"decision": "approve", "comments": "Strategic priority"}
        ]
        approval_index = 0
        
        # Mock user input for approvals
        async def mock_user_input(*args, **kwargs):
            nonlocal approval_index
            if approval_index < len(approval_sequence):
                response = approval_sequence[approval_index]
                approval_index += 1
                return response
            return {"decision": "approve", "comments": "Auto-approved"}
        
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            with patch('src.aromcp.workflow_server.workflow.steps.user_input.get_user_input', side_effect=mock_user_input):
                # Execute approval workflow
                while executor.has_pending_workflows():
                    await executor.execute_next()
                    await asyncio.sleep(0.1)
        
        # Verify final state
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state['status'] == WorkflowStatusResponse.COMPLETED.value
        
        workflow_state = final_state['state']
        assert workflow_state['status'] == 'approved'
        assert len(workflow_state['approvals']) >= 3
        assert 'approved_at' in workflow_state


class TestLongRunningWorkflowWithCheckpoints:
    """Test long-running workflows with checkpoint support."""
    
    @pytest.fixture
    def batch_processing_workflow(self):
        """Create a long-running batch processing workflow with checkpoints."""
        return WorkflowDefinition(
            name="batch_data_migration",
            version="1.0",
            metadata={
                "description": "Migrate large dataset with checkpoint support",
                "enable_checkpoints": True,
                "checkpoint_interval": 100
            },
            input_schema={
                "type": "object",
                "required": ["source_db", "target_db", "batch_size"],
                "properties": {
                    "source_db": {"type": "string"},
                    "target_db": {"type": "string"},
                    "batch_size": {"type": "integer", "default": 1000},
                    "total_records": {"type": "integer"}
                }
            },
            steps=[
                # Initialize migration
                WorkflowStep(
                    id="init_migration",
                    type="state_update",
                    config={
                        "updates": {
                            "processed_count": 0,
                            "failed_count": 0,
                            "last_checkpoint": 0,
                            "start_time": "{{ now() }}"
                        }
                    }
                ),
                
                # Migration loop with checkpoints
                WorkflowStep(
                    id="migration_loop",
                    type="while",
                    config={
                        "condition": "{{ state.processed_count < inputs.total_records }}",
                        "steps": [
                            {
                                "id": "fetch_batch",
                                "type": "mcp_call",
                                "config": {
                                    "server": "database",
                                    "tool": "query",
                                    "arguments": {
                                        "connection": "{{ inputs.source_db }}",
                                        "query": "SELECT * FROM migration_table LIMIT {{ inputs.batch_size }} OFFSET {{ state.processed_count }}"
                                    },
                                    "timeout": 60
                                }
                            },
                            {
                                "id": "transform_data",
                                "type": "agent_prompt",
                                "config": {
                                    "prompt": """Transform batch data:
                                    Records: {{ steps.fetch_batch.output.row_count }}
                                    Apply transformations:
                                    - Schema mapping
                                    - Data validation
                                    - Format conversion
                                    """,
                                    "timeout": 120
                                }
                            },
                            {
                                "id": "insert_batch",
                                "type": "mcp_call",
                                "config": {
                                    "server": "database",
                                    "tool": "bulk_insert",
                                    "arguments": {
                                        "connection": "{{ inputs.target_db }}",
                                        "table": "migration_table_new",
                                        "data": "{{ steps.transform_data.output.transformed_data }}"
                                    },
                                    "error_handling": {
                                        "strategy": "continue",
                                        "on_error": [
                                            {
                                                "id": "log_failed_batch",
                                                "type": "state_update",
                                                "config": {
                                                    "updates": {
                                                        "failed_count": "{{ state.failed_count + steps.fetch_batch.output.row_count }}"
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            },
                            {
                                "id": "update_progress",
                                "type": "state_update",
                                "config": {
                                    "updates": {
                                        "processed_count": "{{ state.processed_count + steps.fetch_batch.output.row_count }}",
                                        "last_update": "{{ now() }}"
                                    }
                                }
                            },
                            {
                                "id": "checkpoint_check",
                                "type": "conditional",
                                "config": {
                                    "conditions": [
                                        {
                                            "if": "{{ state.processed_count - state.last_checkpoint >= metadata.checkpoint_interval }}",
                                            "then": [
                                                {
                                                    "id": "save_checkpoint",
                                                    "type": "state_update",
                                                    "config": {
                                                        "updates": {
                                                            "last_checkpoint": "{{ state.processed_count }}",
                                                            "checkpoint_time": "{{ now() }}"
                                                        },
                                                        "persist": True
                                                    }
                                                },
                                                {
                                                    "id": "report_progress",
                                                    "type": "agent_prompt",
                                                    "config": {
                                                        "prompt": """Progress Report:
                                                        Processed: {{ state.processed_count }} / {{ inputs.total_records }}
                                                        Failed: {{ state.failed_count }}
                                                        Percentage: {{ (state.processed_count / inputs.total_records * 100) | round(2) }}%
                                                        Rate: {{ (state.processed_count / ((now() - state.start_time).total_seconds() / 3600)) | round(0) }} records/hour
                                                        """
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ),
                
                # Final report
                WorkflowStep(
                    id="migration_summary",
                    type="agent_prompt",
                    config={
                        "prompt": """Migration Complete:
                        Total Records: {{ inputs.total_records }}
                        Successfully Migrated: {{ state.processed_count - state.failed_count }}
                        Failed Records: {{ state.failed_count }}
                        Success Rate: {{ ((state.processed_count - state.failed_count) / inputs.total_records * 100) | round(2) }}%
                        Total Duration: {{ (now() - state.start_time) }}
                        """
                    }
                )
            ]
        )
    
    @pytest.mark.asyncio
    async def test_checkpoint_recovery(self, batch_processing_workflow):
        """Test workflow recovery from checkpoint after interruption."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # Large migration job
        migration_config = {
            "source_db": "legacy_db",
            "target_db": "new_db",
            "batch_size": 50,
            "total_records": 1000
        }
        
        result = await executor.start_workflow(batch_processing_workflow, migration_config)
        workflow_id = result['workflow_id']
        
        # Mock database operations
        mock_mcp = AsyncMock()
        processed_batches = 0
        
        def mock_tool_response(tool, arguments):
            nonlocal processed_batches
            
            if tool == "query":
                # Simulate fetching batch
                offset = arguments.get("query", "").split("OFFSET")[-1].strip()
                remaining = 1000 - int(offset)
                row_count = min(50, remaining)
                return {
                    "row_count": row_count,
                    "data": [{"id": i, "value": f"record_{i}"} for i in range(row_count)]
                }
            elif tool == "bulk_insert":
                # Simulate successful insert
                processed_batches += 1
                # Simulate interruption after 6 batches
                if processed_batches == 6:
                    raise Exception("Simulated system interruption")
                return {"inserted": 50}
            else:
                return {"content": "Success", "transformed_data": "mock_data"}
        
        mock_mcp.call_tool.side_effect = lambda tool, arguments: mock_tool_response(tool, arguments)
        
        # Execute until interruption
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            try:
                while executor.has_pending_workflows():
                    await executor.execute_next()
                    await asyncio.sleep(0.05)
            except Exception as e:
                if "interruption" not in str(e):
                    raise
        
        # Check checkpoint was saved
        workflow_state = state_manager.get_workflow_state(workflow_id)
        assert workflow_state['state']['last_checkpoint'] > 0
        assert workflow_state['state']['processed_count'] >= 250  # At least 5 batches
        
        # Simulate recovery from checkpoint
        processed_batches = 6  # Reset counter
        
        # Resume workflow from checkpoint
        executor_resumed = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # Continue execution
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            while executor_resumed.has_pending_workflows():
                await executor_resumed.execute_next()
                await asyncio.sleep(0.05)
        
        # Verify completion
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state['status'] == WorkflowStatusResponse.COMPLETED.value
        assert final_state['state']['processed_count'] == 1000


class TestInteractiveWizardWorkflow:
    """Test interactive wizard workflow with validations."""
    
    @pytest.fixture
    def setup_wizard_workflow(self):
        """Create an interactive setup wizard workflow."""
        return WorkflowDefinition(
            name="application_setup_wizard",
            version="1.0",
            metadata={
                "description": "Interactive setup wizard for application configuration",
                "interactive": True
            },
            steps=[
                # Welcome message
                WorkflowStep(
                    id="welcome",
                    type="user_message",
                    config={
                        "message": """Welcome to Application Setup Wizard!
                        
                        This wizard will guide you through:
                        1. Basic configuration
                        2. Database setup
                        3. Security settings
                        4. Integration options
                        
                        Let's get started!"""
                    }
                ),
                
                # Basic configuration
                WorkflowStep(
                    id="basic_config",
                    type="user_input",
                    config={
                        "prompt": "Please provide basic application configuration:",
                        "schema": {
                            "type": "object",
                            "required": ["app_name", "environment", "port"],
                            "properties": {
                                "app_name": {
                                    "type": "string",
                                    "pattern": "^[a-zA-Z0-9-_]+$",
                                    "minLength": 3,
                                    "maxLength": 50
                                },
                                "environment": {
                                    "type": "string",
                                    "enum": ["development", "staging", "production"]
                                },
                                "port": {
                                    "type": "integer",
                                    "minimum": 1024,
                                    "maximum": 65535
                                },
                                "enable_ssl": {
                                    "type": "boolean",
                                    "default": True
                                }
                            }
                        },
                        "validation_message": "Please ensure app name contains only letters, numbers, hyphens, and underscores."
                    }
                ),
                
                # Database configuration
                WorkflowStep(
                    id="database_config",
                    type="user_input",
                    config={
                        "prompt": """Database Configuration:
                        
                        Current settings:
                        - Application: {{ steps.basic_config.output.app_name }}
                        - Environment: {{ steps.basic_config.output.environment }}
                        
                        Please provide database details:""",
                        "schema": {
                            "type": "object",
                            "required": ["db_type", "host", "port", "database_name"],
                            "properties": {
                                "db_type": {
                                    "type": "string",
                                    "enum": ["postgresql", "mysql", "mongodb", "redis"]
                                },
                                "host": {
                                    "type": "string",
                                    "format": "hostname"
                                },
                                "port": {
                                    "type": "integer"
                                },
                                "database_name": {
                                    "type": "string",
                                    "pattern": "^[a-zA-Z0-9_]+$"
                                },
                                "username": {
                                    "type": "string"
                                },
                                "use_connection_pool": {
                                    "type": "boolean",
                                    "default": True
                                }
                            }
                        }
                    }
                ),
                
                # Test database connection
                WorkflowStep(
                    id="test_connection",
                    type="agent_prompt",
                    config={
                        "prompt": """Test database connection:
                        Type: {{ steps.database_config.output.db_type }}
                        Host: {{ steps.database_config.output.host }}:{{ steps.database_config.output.port }}
                        Database: {{ steps.database_config.output.database_name }}
                        """,
                        "timeout": 30
                    }
                ),
                
                # Connection validation
                WorkflowStep(
                    id="validate_connection",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ 'success' in steps.test_connection.output.content }}",
                                "then": [
                                    {
                                        "id": "connection_success",
                                        "type": "user_message",
                                        "config": {
                                            "message": "✅ Database connection successful!"
                                        }
                                    }
                                ]
                            },
                            {
                                "if": "{{ 'failed' in steps.test_connection.output.content }}",
                                "then": [
                                    {
                                        "id": "connection_retry",
                                        "type": "user_input",
                                        "config": {
                                            "prompt": "Database connection failed. Would you like to retry with different settings?",
                                            "schema": {
                                                "type": "object",
                                                "required": ["retry"],
                                                "properties": {
                                                    "retry": {
                                                        "type": "boolean"
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "id": "retry_check",
                                        "type": "conditional",
                                        "config": {
                                            "conditions": [
                                                {
                                                    "if": "{{ steps.connection_retry.output.retry }}",
                                                    "then": [
                                                        {
                                                            "type": "goto",
                                                            "target": "database_config"
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ),
                
                # Security settings
                WorkflowStep(
                    id="security_config",
                    type="user_input",
                    config={
                        "prompt": "Configure security settings:",
                        "schema": {
                            "type": "object",
                            "required": ["auth_method", "session_timeout"],
                            "properties": {
                                "auth_method": {
                                    "type": "string",
                                    "enum": ["jwt", "oauth2", "saml", "basic"]
                                },
                                "session_timeout": {
                                    "type": "integer",
                                    "minimum": 300,
                                    "maximum": 86400,
                                    "default": 3600
                                },
                                "enable_2fa": {
                                    "type": "boolean",
                                    "default": False
                                },
                                "allowed_origins": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "uri"
                                    }
                                }
                            }
                        }
                    }
                ),
                
                # Generate configuration
                WorkflowStep(
                    id="generate_config",
                    type="agent_prompt",
                    config={
                        "prompt": """Generate application configuration file:
                        
                        Basic Config:
                        {{ steps.basic_config.output | json }}
                        
                        Database Config:
                        {{ steps.database_config.output | json }}
                        
                        Security Config:
                        {{ steps.security_config.output | json }}
                        
                        Generate appropriate configuration files for the environment.
                        """
                    }
                ),
                
                # Confirmation
                WorkflowStep(
                    id="confirm_setup",
                    type="user_input",
                    config={
                        "prompt": """Setup Summary:
                        
                        {{ steps.generate_config.output.content }}
                        
                        Would you like to save this configuration?""",
                        "schema": {
                            "type": "object",
                            "required": ["confirm", "config_path"],
                            "properties": {
                                "confirm": {
                                    "type": "boolean"
                                },
                                "config_path": {
                                    "type": "string",
                                    "default": "./config.json"
                                }
                            }
                        }
                    }
                ),
                
                # Save configuration
                WorkflowStep(
                    id="save_config",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ steps.confirm_setup.output.confirm }}",
                                "then": [
                                    {
                                        "id": "write_config",
                                        "type": "mcp_call",
                                        "config": {
                                            "server": "filesystem",
                                            "tool": "write_files",
                                            "arguments": {
                                                "files": [{
                                                    "path": "{{ steps.confirm_setup.output.config_path }}",
                                                    "content": "{{ steps.generate_config.output.config_content }}"
                                                }]
                                            }
                                        }
                                    },
                                    {
                                        "id": "setup_complete",
                                        "type": "user_message",
                                        "config": {
                                            "message": "✅ Setup complete! Configuration saved to {{ steps.confirm_setup.output.config_path }}"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                )
            ]
        )
    
    @pytest.mark.asyncio
    async def test_interactive_wizard_with_validation_and_retry(self, setup_wizard_workflow):
        """Test interactive wizard with validation and retry logic."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        result = await executor.start_workflow(setup_wizard_workflow, {})
        workflow_id = result['workflow_id']
        
        # Mock user inputs
        user_inputs = [
            # Basic config
            {
                "app_name": "my-awesome-app",
                "environment": "production",
                "port": 8080,
                "enable_ssl": True
            },
            # Database config (first attempt - will fail)
            {
                "db_type": "postgresql",
                "host": "invalid-host",
                "port": 5432,
                "database_name": "myapp_db",
                "username": "admin",
                "use_connection_pool": True
            },
            # Retry prompt
            {"retry": True},
            # Database config (second attempt - will succeed)
            {
                "db_type": "postgresql",
                "host": "db.example.com",
                "port": 5432,
                "database_name": "myapp_db",
                "username": "admin",
                "use_connection_pool": True
            },
            # Security config
            {
                "auth_method": "jwt",
                "session_timeout": 7200,
                "enable_2fa": True,
                "allowed_origins": ["https://app.example.com", "https://api.example.com"]
            },
            # Confirmation
            {
                "confirm": True,
                "config_path": "./app-config.json"
            }
        ]
        input_index = 0
        
        async def mock_user_input(*args, **kwargs):
            nonlocal input_index
            if input_index < len(user_inputs):
                response = user_inputs[input_index]
                input_index += 1
                return response
            return {}
        
        # Mock other services
        mock_mcp = AsyncMock()
        
        def mock_tool_response(tool, arguments):
            if tool == "write_files":
                return {"success": True}
            else:
                prompt = arguments.get("prompt", "")
                if "Test database connection" in prompt and "invalid-host" in prompt:
                    return {"content": "Connection failed: Could not resolve hostname"}
                elif "Test database connection" in prompt:
                    return {"content": "Connection test successful"}
                elif "Generate application configuration" in prompt:
                    return {
                        "content": "Configuration generated successfully",
                        "config_content": json.dumps({
                            "app": {
                                "name": "my-awesome-app",
                                "environment": "production",
                                "port": 8080,
                                "ssl": True
                            },
                            "database": {
                                "type": "postgresql",
                                "host": "db.example.com",
                                "port": 5432,
                                "database": "myapp_db"
                            },
                            "security": {
                                "auth": "jwt",
                                "session_timeout": 7200,
                                "twofa_enabled": True
                            }
                        }, indent=2)
                    }
                return {"content": "Success"}
        
        mock_mcp.call_tool.side_effect = lambda tool, arguments: mock_tool_response(tool, arguments)
        
        # Execute wizard
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            with patch('src.aromcp.workflow_server.workflow.steps.user_input.get_user_input', side_effect=mock_user_input):
                while executor.has_pending_workflows():
                    await executor.execute_next()
                    await asyncio.sleep(0.05)
        
        # Verify completion
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state['status'] == WorkflowStatusResponse.COMPLETED.value
        
        # Verify retry logic was executed
        assert input_index == len(user_inputs)  # All inputs consumed
        
        # Check that configuration was saved
        step_states = final_state['step_states']
        assert 'write_config' in step_states
        assert step_states['write_config']['status'] == 'completed'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])