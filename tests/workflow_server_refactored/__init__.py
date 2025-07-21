"""Refactored workflow server tests with hybrid matrix architecture.

This test package implements a hybrid test matrix that balances:
1. Tool contract validation for all 10 workflow tools
2. Complete real workflow execution (test:simple.yaml and test:sub-agents.yaml)  
3. Execution pattern testing (sequential, parallel, control flow, state)
4. System integration testing (concurrency, error recovery, performance)
5. Shared test infrastructure (fixtures, mocks, utilities)

The architecture ensures comprehensive coverage while maintaining clear organization
and avoiding duplication across test domains.
"""