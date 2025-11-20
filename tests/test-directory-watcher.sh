#!/bin/bash
# Unit tests for directory watcher functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

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

# Test: Single YAML file in directory
test_single_yaml_file() {
    test_case "Single YAML file in directory"
    
    TEST_DIR=$(mktemp -d)
    
    cat > "$TEST_DIR/rules.yml" << 'EOF'
http:
  routers:
    app1:
      entryPoints: [web]
      rule: "Host(`app1.local`)"
      service: app1
  services:
    app1:
      loadBalancer:
        servers:
          - url: "http://192.168.0.10:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    export TRAEFIK_DYNAMIC_CONFIG_DIR="$TEST_DIR"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local count=$(echo "$output" | jq 'length' 2>/dev/null || echo "0")
    assert_equals "1" "$count" "Finds 1 router from single file"
    
    rm -rf "$TEST_DIR"
}

# Test: Multiple YAML files in directory
test_multiple_yaml_files() {
    test_case "Multiple YAML files in directory"
    
    TEST_DIR=$(mktemp -d)
    
    cat > "$TEST_DIR/apps.yml" << 'EOF'
http:
  routers:
    app1:
      entryPoints: [web]
      rule: "Host(`app1.local`)"
      service: app1
  services:
    app1:
      loadBalancer:
        servers:
          - url: "http://192.168.0.10:8080"
EOF
    
    cat > "$TEST_DIR/services.yaml" << 'EOF'
http:
  routers:
    app2:
      entryPoints: [web]
      rule: "Host(`app2.local`)"
      service: app2
  services:
    app2:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    export TRAEFIK_DYNAMIC_CONFIG_DIR="$TEST_DIR"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local count=$(echo "$output" | jq 'length' 2>/dev/null || echo "0")
    assert_equals "2" "$count" "Finds routers from multiple files"
    
    rm -rf "$TEST_DIR"
}

# Test: Mixed .yml and .yaml extensions
test_mixed_extensions() {
    test_case "Mixed .yml and .yaml extensions"
    
    TEST_DIR=$(mktemp -d)
    
    cat > "$TEST_DIR/file1.yml" << 'EOF'
http:
  routers:
    app1:
      entryPoints: [web]
      rule: "Host(`app1.local`)"
      service: app1
  services:
    app1:
      loadBalancer:
        servers:
          - url: "http://192.168.0.10:8080"
EOF
    
    cat > "$TEST_DIR/file2.yaml" << 'EOF'
http:
  routers:
    app2:
      entryPoints: [web]
      rule: "Host(`app2.local`)"
      service: app2
  services:
    app2:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    export TRAEFIK_DYNAMIC_CONFIG_DIR="$TEST_DIR"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local count=$(echo "$output" | jq 'length' 2>/dev/null || echo "0")
    assert_equals "2" "$count" "Handles both .yml and .yaml extensions"
    
    rm -rf "$TEST_DIR"
}

# Test: Empty directory
test_empty_directory() {
    test_case "Empty directory"
    
    TEST_DIR=$(mktemp -d)
    
    export HOME_CONTAINER_LABELS=""
    export TRAEFIK_DYNAMIC_CONFIG_DIR="$TEST_DIR"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null || echo "[]")
    
    assert_json_valid "$output" "Output is valid JSON"
    assert_equals "[]" "$output" "Returns empty array for empty directory"
    
    rm -rf "$TEST_DIR"
}

# Test: Duplicate router names across files
test_duplicate_routers() {
    test_case "Duplicate router names across files"
    
    TEST_DIR=$(mktemp -d)
    
    cat > "$TEST_DIR/file1.yml" << 'EOF'
http:
  routers:
    app:
      entryPoints: [web]
      rule: "Host(`app1.local`)"
      service: app1
  services:
    app1:
      loadBalancer:
        servers:
          - url: "http://192.168.0.10:8080"
EOF
    
    cat > "$TEST_DIR/file2.yml" << 'EOF'
http:
  routers:
    app:
      entryPoints: [websecure]
      rule: "Host(`app2.local`)"
      service: app2
  services:
    app2:
      loadBalancer:
        servers:
          - url: "http://192.168.0.20:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    export TRAEFIK_DYNAMIC_CONFIG_DIR="$TEST_DIR"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    # yq will merge/override duplicate keys
    assert_json_valid "$output" "Output is valid JSON for duplicate routers"
    
    rm -rf "$TEST_DIR"
}

# Test: Non-YAML files in directory
test_ignore_non_yaml() {
    test_case "Ignore non-YAML files"
    
    TEST_DIR=$(mktemp -d)
    
    cat > "$TEST_DIR/rules.yml" << 'EOF'
http:
  routers:
    app1:
      entryPoints: [web]
      rule: "Host(`app1.local`)"
      service: app1
  services:
    app1:
      loadBalancer:
        servers:
          - url: "http://192.168.0.10:8080"
EOF
    
    # Create non-YAML files
    echo "some text" > "$TEST_DIR/readme.txt"
    echo "#!/bin/bash" > "$TEST_DIR/script.sh"
    
    export HOME_CONTAINER_LABELS=""
    export TRAEFIK_DYNAMIC_CONFIG_DIR="$TEST_DIR"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local count=$(echo "$output" | jq 'length' 2>/dev/null || echo "0")
    assert_equals "1" "$count" "Only parses YAML files, ignores others"
    
    rm -rf "$TEST_DIR"
}

# Run all tests
echo "========================================"
echo "  Directory Watcher Tests"
echo "========================================"
echo ""

test_single_yaml_file
test_multiple_yaml_files
test_mixed_extensions
test_empty_directory
test_duplicate_routers
test_ignore_non_yaml

# Summary
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo -e "Tests run:    ${TESTS_RUN}"
echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All directory watcher tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some directory watcher tests failed!${NC}"
    exit 1
fi
