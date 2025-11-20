#!/bin/bash
# test-setup.sh - Standalone test environment for traefik-home
# This script creates a complete test environment with mock Docker socket data
# and Traefik dynamic configuration for unit testing
#
# DIFFERENCE FROM test-parse-external-apps.sh:
# - test-parse-external-apps.sh: Unit tests that run inside Docker container
# - test-setup.sh: Creates standalone environment + copies existing test files
#
# This setup:
# 1. Creates directory structure and mock data
# 2. Copies app scripts and existing test files
# 3. Provides wrapper to run all tests outside container
# 4. Useful for local development and CI/CD pipelines

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test environment paths
TEST_ROOT="test-env"
TEST_APP_DIR="$TEST_ROOT/app"
TEST_DATA_DIR="$TEST_ROOT/data"
TEST_TRAEFIK_DIR="$TEST_DATA_DIR/traefik"
TEST_RESULTS_DIR="$TEST_ROOT/results"

echo -e "${BLUE}========================================"
echo "  Traefik-Home Test Environment Setup"
echo "========================================${NC}"
echo ""

# Clean previous test environment
if [ -d "$TEST_ROOT" ]; then
    echo -e "${YELLOW}Cleaning previous test environment...${NC}"
    rm -rf "$TEST_ROOT"
fi

# Create directory structure
echo -e "${GREEN}Creating test directory structure...${NC}"
mkdir -p "$TEST_APP_DIR"
mkdir -p "$TEST_DATA_DIR"
mkdir -p "$TEST_TRAEFIK_DIR"
mkdir -p "$TEST_RESULTS_DIR"

# Copy application scripts
echo -e "${GREEN}Copying application scripts...${NC}"
if [ -f "app/parse-external-apps.sh" ]; then
    cp app/parse-external-apps.sh "$TEST_APP_DIR/"
    chmod +x "$TEST_APP_DIR/parse-external-apps.sh"
else
    echo -e "${RED}Error: app/parse-external-apps.sh not found${NC}"
    exit 1
fi

if [ -f "app/docker-entrypoint.sh" ]; then
    cp app/docker-entrypoint.sh "$TEST_APP_DIR/"
    chmod +x "$TEST_APP_DIR/docker-entrypoint.sh"
else
    echo -e "${YELLOW}Warning: app/docker-entrypoint.sh not found${NC}"
fi

if [ -f "app/home.tmpl" ]; then
    cp app/home.tmpl "$TEST_APP_DIR/"
else
    echo -e "${YELLOW}Warning: app/home.tmpl not found${NC}"
fi

# Copy existing test files
echo -e "${GREEN}Copying existing test files...${NC}"
TEST_TESTS_DIR="$TEST_ROOT/tests"
mkdir -p "$TEST_TESTS_DIR"

if [ -f "tests/test-parse-external-apps.sh" ]; then
    cp tests/test-parse-external-apps.sh "$TEST_TESTS_DIR/"
    chmod +x "$TEST_TESTS_DIR/test-parse-external-apps.sh"
    echo -e "  ${GREEN}✓${NC} test-parse-external-apps.sh"
else
    echo -e "  ${YELLOW}⚠${NC} tests/test-parse-external-apps.sh not found"
fi

if [ -f "tests/test-parser-edge-cases.sh" ]; then
    cp tests/test-parser-edge-cases.sh "$TEST_TESTS_DIR/"
    chmod +x "$TEST_TESTS_DIR/test-parser-edge-cases.sh"
    echo -e "  ${GREEN}✓${NC} test-parser-edge-cases.sh"
else
    echo -e "  ${YELLOW}⚠${NC} tests/test-parser-edge-cases.sh not found"
fi

if [ -f "tests/test-directory-watcher.sh" ]; then
    cp tests/test-directory-watcher.sh "$TEST_TESTS_DIR/"
    chmod +x "$TEST_TESTS_DIR/test-directory-watcher.sh"
    echo -e "  ${GREEN}✓${NC} test-directory-watcher.sh"
else
    echo -e "  ${YELLOW}⚠${NC} tests/test-directory-watcher.sh not found"
fi

# Create mock Docker socket data
echo -e "${GREEN}Creating mock Docker container data...${NC}"
cat > "$TEST_DATA_DIR/docker-containers.json" << 'EOF'
[
  {
    "ID": "abc123home",
    "Name": "traefik-home",
    "State": {
      "Running": true
    },
    "Labels": {
      "traefik.enable": "true",
      "traefik.http.routers.traefik-home.rule": "Host(`home.locker.local`)",
      "traefik.http.routers.traefik-home.entrypoints": "web",
      "traefik.http.services.traefik-home.loadbalancer.server.port": "80",
      "traefik-home.show-footer": "true",
      "traefik-home.show-status-dot": "true",
      "traefik-home.sort-by": "name",
      "traefik-home.app.omv.enable": "true",
      "traefik-home.app.omv.alias": "OpenMediaVault NAS",
      "traefik-home.app.omv.icon": "https://www.openmediavault.org/favicon.ico",
      "traefik-home.app.omv.admin": "true",
      "traefik-home.app.rclone.enable": "true",
      "traefik-home.app.rclone.alias": "Rclone WebUI",
      "traefik-home.app.rclone.icon": "https://rclone.org/img/logo_on_light__horizontal_color.svg",
      "traefik-home.app.rclone.admin": "true",
      "traefik-home.app.traefik-ui.enable": "true",
      "traefik-home.app.traefik-ui.alias": "Traefik Dashboard",
      "traefik-home.app.traefik-ui.icon": "https://traefik.io/favicon.ico",
      "traefik-home.app.traefik-ui.admin": "true",
      "traefik-home.app.router.enable": "false"
    }
  },
  {
    "ID": "def456whoami",
    "Name": "whoami",
    "State": {
      "Running": true
    },
    "Labels": {
      "traefik.enable": "true",
      "traefik.http.routers.whoami.rule": "Host(`whoami.locker.local`)",
      "traefik.http.routers.whoami.entrypoints": "web",
      "traefik.http.services.whoami.loadbalancer.server.port": "80",
      "traefik-home.icon": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/traefik.png",
      "traefik-home.alias": "Who Am I"
    }
  },
  {
    "ID": "ghi789portainer",
    "Name": "portainer",
    "State": {
      "Running": true
    },
    "Labels": {
      "traefik.enable": "true",
      "traefik.http.routers.portainer.rule": "Host(`portainer.locker.local`)",
      "traefik.http.routers.portainer.entrypoints": "websecure",
      "traefik.http.services.portainer.loadbalancer.server.port": "9000",
      "traefik-home.icon": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/portainer.png",
      "traefik-home.alias": "Container Management",
      "traefik-home.admin": "true"
    }
  },
  {
    "ID": "jkl012nginx",
    "Name": "nginx",
    "State": {
      "Running": false
    },
    "Labels": {
      "traefik.enable": "true",
      "traefik.http.routers.nginx.rule": "Host(`nginx.locker.local`)",
      "traefik.http.routers.nginx.entrypoints": "web",
      "traefik.http.services.nginx.loadbalancer.server.port": "80",
      "traefik-home.icon": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/nginx.png",
      "traefik-home.alias": "Nginx Test"
    }
  },
  {
    "ID": "mno345hidden",
    "Name": "hidden-service",
    "State": {
      "Running": true
    },
    "Labels": {
      "traefik.enable": "true",
      "traefik.http.routers.hidden.rule": "Host(`hidden.locker.local`)",
      "traefik.http.routers.hidden.entrypoints": "web",
      "traefik-home.hide": "true"
    }
  }
]
EOF

# Create Traefik dynamic configuration
echo -e "${GREEN}Creating Traefik dynamic configuration...${NC}"
cat > "$TEST_TRAEFIK_DIR/rules.yml" << 'EOF'
# Traefik dynamic configuration for external services
http:
  routers:
    # OpenMediaVault NAS
    omv:
      entryPoints:
        - web
      rule: "Host(`omv.locker.local`)"
      service: omv

    # Rclone WebUI
    rclone:
      entryPoints:
        - websecure
      rule: "Host(`rclone.locker.local`)"
      service: rclone

    # Traefik Dashboard
    traefik-ui:
      entryPoints:
        - websecure
      rule: "Host(`traefik.locker.local`) && PathPrefix(`/dashboard`)"
      service: traefik-ui

    # pfSense Firewall (disabled)
    router:
      entryPoints:
        - web
      rule: "Host(`router.locker.local`)"
      service: router

    # Home Assistant
    homeassistant:
      entryPoints:
        - websecure
      rule: "Host(`ha.locker.local`)"
      service: homeassistant

    # Proxmox VE
    proxmox:
      entryPoints:
        - websecure
      rule: "Host(`proxmox.locker.local`)"
      service: proxmox

  services:
    omv:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:8085"

    rclone:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:5572"

    traefik-ui:
      loadBalancer:
        servers:
          - url: "http://traefik:8080"

    router:
      loadBalancer:
        servers:
          - url: "http://192.168.0.1"

    homeassistant:
      loadBalancer:
        servers:
          - url: "http://192.168.0.30:8123"

    proxmox:
      loadBalancer:
        servers:
          - url: "https://192.168.0.10:8006"
EOF

# Create alternative configuration with edge cases
cat > "$TEST_TRAEFIK_DIR/rules-edge-cases.yml" << 'EOF'
# Edge case configurations for testing
http:
  routers:
    # Multiple hosts
    multi-host:
      entryPoints:
        - web
      rule: "Host(`primary.local`) || Host(`secondary.local`)"
      service: multi-host

    # Path with special characters
    special-path:
      entryPoints:
        - web
      rule: "Host(`app.local`) && PathPrefix(`/api/v1`)"
      service: special-path

    # No entrypoints defined
    no-entry:
      rule: "Host(`noentry.local`)"
      service: no-entry

    # Whitespace in rule
    spaces:
      entryPoints:
        - web
      rule: "Host(  `spaces.local`  ) && PathPrefix(  `/api`  )"
      service: spaces

  services:
    multi-host:
      loadBalancer:
        servers:
          - url: "http://192.168.0.100:8080"

    special-path:
      loadBalancer:
        servers:
          - url: "http://192.168.0.101:8080"

    no-entry:
      loadBalancer:
        servers:
          - url: "http://192.168.0.102:8080"

    spaces:
      loadBalancer:
        servers:
          - url: "http://192.168.0.103:8080"
EOF

# Create mock template output with labels
echo -e "${GREEN}Creating mock template data...${NC}"
cat > "$TEST_DATA_DIR/home-container-labels.txt" << 'EOF'
traefik-home.app.omv.enable=true
traefik-home.app.omv.alias=OpenMediaVault NAS
traefik-home.app.omv.icon=https://www.openmediavault.org/favicon.ico
traefik-home.app.omv.admin=true
traefik-home.app.rclone.enable=true
traefik-home.app.rclone.alias=Rclone WebUI
traefik-home.app.rclone.icon=https://rclone.org/img/logo_on_light__horizontal_color.svg
traefik-home.app.rclone.admin=true
traefik-home.app.traefik-ui.enable=true
traefik-home.app.traefik-ui.alias=Traefik Dashboard
traefik-home.app.traefik-ui.icon=https://traefik.io/favicon.ico
traefik-home.app.traefik-ui.admin=true
traefik-home.app.router.enable=false
EOF

# Create test runner script
echo -e "${GREEN}Creating test runner script...${NC}"
cat > "$TEST_ROOT/run-tests.sh" << 'TESTRUNNER'
#!/bin/bash
# Master test runner - executes all test suites

set -e

# Get the directory where this script is located
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================"
echo "  Traefik-Home Test Suite Runner"
echo "========================================${NC}"
echo ""

# Track overall results
TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0

run_test_suite() {
    local test_file="$1"
    local test_name="$2"
    
    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    
    echo -e "${BLUE}Running: ${test_name}${NC}"
    echo "----------------------------------------"
    
    if [ ! -f "$test_file" ]; then
        echo -e "${YELLOW}  ⚠ Test file not found: $test_file${NC}"
        echo ""
        return
    fi
    
    if bash "$test_file"; then
        echo -e "${GREEN}  ✓ $test_name PASSED${NC}"
        PASSED_SUITES=$((PASSED_SUITES + 1))
    else
        echo -e "${RED}  ✗ $test_name FAILED${NC}"
        FAILED_SUITES=$((FAILED_SUITES + 1))
    fi
    echo ""
}

# Run all test suites
echo -e "${BLUE}Searching for test files...${NC}"
echo ""

# Run existing unit tests
run_test_suite "$TEST_DIR/tests/test-parse-external-apps.sh" "Parser Unit Tests"
run_test_suite "$TEST_DIR/tests/test-parser-edge-cases.sh" "Parser Edge Cases"
run_test_suite "$TEST_DIR/tests/test-directory-watcher.sh" "Directory Watcher Tests"

# Run integration tests (custom tests in this runner)
echo -e "${BLUE}Running: Integration Tests${NC}"
echo "----------------------------------------"
TOTAL_SUITES=$((TOTAL_SUITES + 1))

# Integration test code from original run-tests.sh
APP_DIR="$TEST_DIR/app"
DATA_DIR="$TEST_DIR/data"
TRAEFIK_DIR="$DATA_DIR/traefik"
RESULTS_DIR="$TEST_DIR/results"

# Test counters for integration tests
INT_TESTS=0
INT_PASSED=0
INT_FAILED=0

log_test() {
    echo -e "${YELLOW}  TEST: $1${NC}"
    INT_TESTS=$((INT_TESTS + 1))
}

log_pass() {
    echo -e "${GREEN}    ✓ $1${NC}"
    INT_PASSED=$((INT_PASSED + 1))
}

log_fail() {
    echo -e "${RED}    ✗ $1${NC}"
    INT_FAILED=$((INT_FAILED + 1))
}

# Integration Test 1: Full pipeline with labels
log_test "Full pipeline with label overrides"

export TRAEFIK_DYNAMIC_CONFIG="$TRAEFIK_DIR/rules.yml"
export HOME_CONTAINER_LABELS=$(cat "$DATA_DIR/home-container-labels.txt")

output=$("$APP_DIR/parse-external-apps.sh" 2>/dev/null)

if echo "$output" | jq empty 2>/dev/null; then
    log_pass "Valid JSON with full pipeline"
    
    # Check specific values
    omv_alias=$(echo "$output" | jq -r '.[] | select(.Name=="omv") | .Alias')
    if [ "$omv_alias" = "OpenMediaVault NAS" ]; then
        log_pass "Label overrides working"
    else
        log_fail "Label overrides not applied"
    fi
    
    echo "$output" | jq '.' > "$RESULTS_DIR/integration-full-pipeline.json"
else
    log_fail "Invalid JSON output"
fi

# Integration Test 2: Protocol handling
log_test "Protocol detection across all services"

export HOME_CONTAINER_LABELS=""
output=$("$APP_DIR/parse-external-apps.sh" 2>/dev/null)

http_count=$(echo "$output" | jq '[.[] | select(.URL | startswith("http://"))] | length')
https_count=$(echo "$output" | jq '[.[] | select(.URL | startswith("https://"))] | length')

if [ "$http_count" -gt 0 ] && [ "$https_count" -gt 0 ]; then
    log_pass "Both HTTP and HTTPS protocols detected"
else
    log_fail "Protocol detection incomplete (HTTP: $http_count, HTTPS: $https_count)"
fi

# Integration summary
echo ""
echo "  Integration Tests: $INT_TESTS total, $INT_PASSED passed, $INT_FAILED failed"

if [ $INT_FAILED -eq 0 ]; then
    echo -e "${GREEN}  ✓ Integration Tests PASSED${NC}"
    PASSED_SUITES=$((PASSED_SUITES + 1))
else
    echo -e "${RED}  ✗ Integration Tests FAILED${NC}"
    FAILED_SUITES=$((FAILED_SUITES + 1))
fi
echo ""

# Overall summary
echo -e "${BLUE}========================================"
echo "  Overall Test Summary"
echo "========================================${NC}"
echo "Test suites run:    $TOTAL_SUITES"
echo -e "Suites passed:      ${GREEN}$PASSED_SUITES${NC}"
echo -e "Suites failed:      ${RED}$FAILED_SUITES${NC}"
echo ""

if [ $FAILED_SUITES -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TEST SUITES PASSED! 🎉${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TEST SUITES FAILED${NC}"
    echo "Check individual test outputs above for details"
    echo "Results saved in: $RESULTS_DIR/"
    exit 1
fi
TESTRUNNER

chmod +x "$TEST_ROOT/run-tests.sh"

# Create README for test environment
cat > "$TEST_ROOT/README.md" << 'README'
# Traefik-Home Test Environment

This is a standalone test environment for testing traefik-home scripts without requiring Docker or Traefik infrastructure.

## What This Test Setup Does

This test setup (`test-setup.sh`) is a **wrapper and infrastructure builder** that:

1. Creates a complete test environment structure
2. Copies application scripts and existing test files
3. Generates comprehensive mock data
4. Provides a master test runner that executes all test suites
5. Enables testing outside Docker containers

## Difference from Other Test Files

### `test-parse-external-apps.sh` (Unit Tests)
- **What**: Focused unit tests for parse-external-apps.sh
- **Runs**: Inside Docker container (expects `/app/parse-external-apps.sh`)
- **Creates**: Temporary test data per test
- **Purpose**: Validate parser logic, label handling, protocol detection

### `test-parser-edge-cases.sh` (Edge Case Tests)
- **What**: Tests malformed configs, special characters, edge conditions
- **Runs**: Inside Docker container
- **Creates**: Temporary test data for edge cases
- **Purpose**: Ensure robustness against unusual inputs

### `test-directory-watcher.sh` (Directory Tests)
- **What**: Tests multiple YAML file handling
- **Runs**: Inside Docker container
- **Creates**: Temporary directories with multiple config files
- **Purpose**: Validate dynamic config directory watching

### `test-setup.sh` (This File)
- **What**: Environment builder and test orchestrator
- **Runs**: On host machine, creates infrastructure
- **Creates**: Persistent test environment with all mock data
- **Purpose**: 
  - Set up testing infrastructure
  - Copy all scripts and tests to isolated environment
  - Provide master runner that executes all test suites
  - Enable CI/CD integration
  - Allow local testing without Docker

## Directory Structure

```
test-env/
├── app/                          # Application scripts under test
│   ├── parse-external-apps.sh   # External app parser
│   ├── docker-entrypoint.sh     # Docker entrypoint (if available)
│   └── home.tmpl                # Template file (if available)
├── tests/                        # Existing test suites (copied)
│   ├── test-parse-external-apps.sh
│   ├── test-parser-edge-cases.sh
│   └── test-directory-watcher.sh
├── data/                         # Test data
│   ├── docker-containers.json   # Mock Docker container data
│   ├── home-container-labels.txt # Mock container labels
│   └── traefik/                 # Traefik configurations
│       ├── rules.yml            # Standard config
│       └── rules-edge-cases.yml # Edge case config
├── results/                      # Test results and outputs
├── run-tests.sh                 # Master test runner
└── README.md                    # This file
```

## Running Tests

```bash
# Initial setup (run once)
./test-setup.sh

# Run all test suites
cd test-env
./run-tests.sh

# Run specific test suite
./tests/test-parse-external-apps.sh
./tests/test-parser-edge-cases.sh
./tests/test-directory-watcher.sh

# Check specific test results
cat results/integration-full-pipeline.json
```

## Test Coverage

### Unit Tests (test-parse-external-apps.sh)
- Empty config handling
- Basic parsing without labels
- Label override application
- Disabled app handling
- HTTPS protocol detection
- Path extraction
- Special characters in aliases
- Missing service handling
- Multiple hosts in rules
- External flag validation

### Edge Cases (test-parser-edge-cases.sh)
- Malformed YAML
- URLs with special characters
- Labels with quotes and backslashes
- Empty aliases
- Very long values
- Unicode characters
- Rules without Host
- Case sensitivity
- Multiple backend servers
- Missing entrypoints
- BusyBox grep compatibility
- Whitespace in rules

### Directory Watcher (test-directory-watcher.sh)
- Single YAML file
- Multiple YAML files
- Mixed .yml and .yaml extensions
- Empty directories
- Duplicate router names
- Non-YAML files (ignored)

### Integration Tests (in run-tests.sh)
- Full pipeline with label overrides
- Protocol detection across all services

## Mock Data

### Docker Containers
`data/docker-containers.json` includes:
- **traefik-home**: Container with app labels for external services
- **whoami**: Regular service (running)
- **portainer**: Admin-only service (running, HTTPS)
- **nginx**: Stopped service (offline state testing)
- **hidden-service**: Hidden service (should not appear)

### Traefik Configuration
**Standard config** (`data/traefik/rules.yml`):
- OMV (HTTP, admin-only)
- Rclone (HTTPS, admin-only)
- Traefik UI (HTTPS with path, admin-only)
- Router (HTTP, disabled)
- Home Assistant (HTTPS)
- Proxmox (HTTPS)

**Edge case config** (`data/traefik/rules-edge-cases.yml`):
- Multiple hosts in single rule
- Special characters in paths
- Missing entrypoints
- Extra whitespace in rules

### Container Labels
`data/home-container-labels.txt` includes label overrides for:
- OMV: Custom alias, icon, admin flag
- Rclone: Custom alias, icon, admin flag
- Traefik UI: Custom alias, icon, admin flag
- Router: Explicitly disabled

## Usage Patterns

### Local Development
```bash
# Set up once
./test-setup.sh

# Make changes to app/parse-external-apps.sh
vim app/parse-external-apps.sh

# Copy updated script
cp app/parse-external-apps.sh test-env/app/

# Run tests
cd test-env && ./run-tests.sh
```

### CI/CD Integration
```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - name: Install dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y jq yq
    - name: Setup test environment
      run: ./test-setup.sh
    - name: Run tests
      run: cd test-env && ./run-tests.sh
```

### Docker-based Testing
```bash
# Build Docker image with tests
docker build -t traefik-home:test .

# Run tests in container
docker run --rm traefik-home:test /tests/test-parse-external-apps.sh
docker run --rm traefik-home:test /tests/test-parser-edge-cases.sh
```

## Troubleshooting

### Dependencies
- **jq not found**: `apt-get install jq` or `brew install jq`
- **yq not found**: `pip install yq` or `brew install yq`
- **Permission denied**: `chmod +x test-setup.sh test-env/*.sh test-env/tests/*.sh`

### Test Failures
- Check `results/` directory for detailed JSON outputs
- Run individual test suites for focused debugging
- Review DEBUG output in parser script

### Environment Issues
- Ensure you're in the project root when running `test-setup.sh`
- Verify `app/parse-external-apps.sh` exists before setup
- Check that copied files are executable

## Extending Tests

### Add New Test Suite
1. Create test file in `tests/` directory
2. Follow existing test patterns
3. Re-run `test-setup.sh` to copy new test
4. Update `run-tests.sh` to include new suite

### Add New Mock Data
1. Edit data generation section in `test-setup.sh`
2. Add new containers to `docker-containers.json`
3. Add new services to `rules.yml` or create new config file
4. Re-run setup to regenerate environment

### Add New Integration Test
Edit the integration test section in `run-tests.sh`:
```bash
log_test "My new integration test"
export TRAEFIK_DYNAMIC_CONFIG="$TRAEFIK_DIR/my-config.yml"
output=$("$APP_DIR/parse-external-apps.sh" 2>/dev/null)
# Add assertions...
```

## Summary

**test-setup.sh creates the foundation, existing tests provide the validation:**

```
test-setup.sh  →  Creates environment + mock data
                 ↓
             test-env/
                 ↓
          run-tests.sh  →  Orchestrates all tests
                 ↓
        ┌────────┴────────┬──────────────────┐
        ↓                 ↓                   ↓
Unit Tests      Edge Case Tests    Integration Tests
(existing)         (existing)          (custom)
```

This approach lets you:
- Test locally without Docker
- Run in CI/CD pipelines
- Keep existing test logic intact
- Add comprehensive integration testing
- Debug with persistent test data
README

echo ""
echo -e "${GREEN}========================================"
echo "  Test Environment Setup Complete"
echo "========================================${NC}"
echo ""
echo "Test environment created at: $TEST_ROOT"
echo ""
echo "To run tests:"
echo "  cd $TEST_ROOT"
echo "  ./run-tests.sh"
echo ""
echo "Test data locations:"
echo "  - Docker containers:     $TEST_DATA_DIR/docker-containers.json"
echo "  - Container labels:      $TEST_DATA_DIR/home-container-labels.txt"
echo "  - Traefik config:        $TEST_TRAEFIK_DIR/rules.yml"
echo "  - Edge case config:      $TEST_TRAEFIK_DIR/rules-edge-cases.yml"
echo "  - Test results:          $TEST_RESULTS_DIR/"
echo ""
echo -e "${BLUE}Run './run-tests.sh' to execute all tests${NC}"
