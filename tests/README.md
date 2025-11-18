# Tests for llm-do

This directory contains the test suite for the llm-do plugin.

## Test Structure

- `conftest.py` - Shared pytest fixtures used across test files
- `test_executor.py` - Tests for the executor module, including ToolApprovalCallback
- `test_plugin.py` - Tests for CLI integration and command registration

## Running Tests

### Install Development Dependencies

```bash
uv pip install -e ".[dev]"
# or
pip install -e ".[dev]"
```

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_executor.py
pytest tests/test_plugin.py
```

### Run Specific Test

```bash
pytest tests/test_executor.py::TestToolApprovalCallback::test_approve_all_bypasses_prompting
```

### Run with Coverage

```bash
pytest --cov=llm_do --cov-report=term-missing
```

### Run with Coverage HTML Report

```bash
pytest --cov=llm_do --cov-report=html
# Open htmlcov/index.html in your browser
```

## Test Coverage

Current test coverage focuses on:

### ToolApprovalCallback (test_executor.py)
- Approval flow with different user inputs (y/yes, n/no, a/always, q/quit)
- Session-based "approve all" functionality
- Input validation and error handling
- Case-insensitive and whitespace-tolerant input
- Tool call information display

### CLI Integration (test_plugin.py)
- `--ta` / `--tools-approve` flag registration
- Flag passing from CLI to executor
- Callback creation and type verification
- Integration with execute_spec function

## Test Fixtures

### Shared Fixtures (conftest.py)

- `temp_workspace` - Temporary directory for test isolation
- `sample_spec` - Sample specification file for testing
- `mock_toolbox` - Mock toolbox instance
- `mock_tool` - Mock tool object for callback testing
- `mock_tool_call` - Mock tool call object for callback testing

## Writing New Tests

When adding new tests, follow these patterns:

1. **Use pytest class-based organization:**
   ```python
   class TestFeature:
       """Tests for Feature"""

       def test_specific_behavior(self):
           """Test that specific behavior works"""
           # Arrange, Act, Assert
   ```

2. **Use fixtures for setup:**
   ```python
   def test_with_fixture(self, temp_workspace, sample_spec):
       # Use fixtures for clean test setup
   ```

3. **Use descriptive test names:**
   ```python
   def test_approval_callback_raises_cancel_when_user_declines(self):
       # Clear description of what's being tested
   ```

4. **Mock external dependencies:**
   ```python
   with patch('llm.get_model') as mock_get_model:
       # Test with mocked LLM model
   ```

## CI/CD

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=llm_do --cov-report=xml
```
