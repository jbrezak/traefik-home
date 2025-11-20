
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
test_case() {
    local test_name="$1"
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -e "${YELLOW}Running test: ${test_name}${NC}"
}

assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="$3"
    
    # Handle empty/null values
    [ -z "$actual" ] && actual="0"
    [ "$actual" = "null" ] && actual="0"
    
    if [ "$expected" = "$actual" ]; then
        echo -e "${GREEN}  ✓ ${message}${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}  ✗ ${message}${NC}"
        echo -e "${RED}    Expected: ${expected}${NC}"
        echo -e "${RED}    Got:      ${actual}${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_json_valid() {
    local json="$1"
    local message="$2"
    
    if echo "$json" | jq empty 2>/dev/null; then
        echo -e "${GREEN}  ✓ ${message}${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}  ✗ ${message} - Invalid JSON${NC}"
        echo -e "${RED}    JSON: ${json}${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="$3"
    
    if echo "$haystack" | grep -q "$needle"; then
        echo -e "${GREEN}  ✓ ${message}${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}  ✗ ${message}${NC}"
        echo -e "${RED}    Expected to find: ${needle}${NC}"
        echo -e "${RED}    In: ${haystack}${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Setup test environment
setup_test_env() {
    TEST_DIR=$(mktemp -d)
    export TRAEFIK_DYNAMIC_CONFIG="$TEST_DIR/rules.yml"
    export HOME_CONTAINER_LABELS=""
}

# Cleanup test environment
cleanup_test_env() {
    rm -rf "$TEST_DIR"
}

# Create test rules.yml
create_test_rules() {
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    omv:
      entryPoints:
        - web
      rule: "Host(`omv.locker.local`)"
      service: omv
      
    rclone:
      entryPoints:
        - websecure
      rule: "Host(`rclone.locker.local`)"
      service: rclone

  services:
    omv:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:8085"
    
    rclone:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:5572"
EOF
}

