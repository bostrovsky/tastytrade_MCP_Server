#!/bin/bash
# Test runner script with various options

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Export Poetry path
export PATH="$HOME/.local/bin:$PATH"

# Main test runner
run_tests() {
    case "$1" in
        all)
            print_info "Running all tests with coverage..."
            poetry run pytest
            ;;
            
        unit)
            print_info "Running unit tests only..."
            poetry run pytest -m unit --cov-fail-under=0
            ;;
            
        integration)
            print_info "Running integration tests..."
            poetry run pytest -m integration --cov-fail-under=0
            ;;
            
        fast)
            print_info "Running fast tests (no coverage)..."
            poetry run pytest -m "not slow" --no-cov -q
            ;;
            
        coverage)
            print_info "Running tests with coverage report..."
            poetry run pytest --cov-report=html
            print_status "Coverage report generated at htmlcov/index.html"
            ;;
            
        watch)
            print_info "Running tests in watch mode..."
            poetry run pytest-watch -- -q
            ;;
            
        specific)
            if [ -z "$2" ]; then
                print_error "Please specify a test file or pattern"
                exit 1
            fi
            print_info "Running specific tests: $2"
            poetry run pytest "$2" --no-cov
            ;;
            
        verbose)
            print_info "Running tests with verbose output..."
            poetry run pytest -vv --tb=long
            ;;
            
        failed)
            print_info "Running only previously failed tests..."
            poetry run pytest --lf --no-cov
            ;;
            
        parallel)
            print_info "Running tests in parallel..."
            poetry run pytest -n auto
            ;;
            
        lint)
            print_info "Running linters and type checks..."
            
            print_info "Black (formatter)..."
            poetry run black --check src tests
            
            print_info "Ruff (linter)..."
            poetry run ruff check src tests
            
            print_info "MyPy (type checker)..."
            poetry run mypy src
            
            print_status "All checks passed!"
            ;;
            
        format)
            print_info "Formatting code..."
            poetry run black src tests
            poetry run ruff check --fix src tests
            print_status "Code formatted!"
            ;;
            
        clean)
            print_info "Cleaning test artifacts..."
            rm -rf .pytest_cache
            rm -rf htmlcov
            rm -rf .coverage
            rm -rf .mypy_cache
            rm -rf .ruff_cache
            find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
            print_status "Test artifacts cleaned!"
            ;;
            
        *)
            echo "TastyTrade MCP Test Runner"
            echo ""
            echo "Usage: $0 {command} [options]"
            echo ""
            echo "Commands:"
            echo "  all         - Run all tests with coverage (default)"
            echo "  unit        - Run unit tests only"
            echo "  integration - Run integration tests only"
            echo "  fast        - Run fast tests without coverage"
            echo "  coverage    - Run tests and generate HTML coverage report"
            echo "  watch       - Run tests in watch mode (requires pytest-watch)"
            echo "  specific    - Run specific test file or pattern"
            echo "  verbose     - Run tests with verbose output"
            echo "  failed      - Run only previously failed tests"
            echo "  parallel    - Run tests in parallel (requires pytest-xdist)"
            echo "  lint        - Run linters and type checks"
            echo "  format      - Format code with black and ruff"
            echo "  clean       - Clean test artifacts"
            echo ""
            echo "Examples:"
            echo "  $0 all                    # Run all tests"
            echo "  $0 unit                   # Run unit tests only"
            echo "  $0 specific test_mcp      # Run tests matching 'test_mcp'"
            echo "  $0 coverage               # Generate coverage report"
            exit 1
            ;;
    esac
}

# Run the tests
run_tests "$@"

# Exit with test status
exit $?