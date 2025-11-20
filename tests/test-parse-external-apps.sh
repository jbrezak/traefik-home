#!/bin/bash
# Unit tests for parse-external-apps.sh

set -e

source tests/test-helpers.sh

# Test 1: Empty config returns empty array
test_empty_config() {
    test_case "Empty config file"
    setup_test_env
    
    echo "" > "$TRAEFIK_DYNAMIC_CONFIG"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null || echo "[]")
    
    assert_equals "[]" "$output" "Returns empty array for empty config"
    
    cleanup_test_env
}

# Test 2: Basic parsing without labels
test_basic_parsing_no_labels() {
    test_case "Basic parsing without labels"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local count=$(echo "$output" | jq 'length' 2>/dev/null || echo "0")
    assert_equals "2" "$count" "Finds 2 routers"
    
    local omv_name=$(echo "$output" | jq -r '.[0].Name')
    assert_equals "omv" "$omv_name" "First router name is 'omv'"
    
    local omv_url=$(echo "$output" | jq -r '.[0].URL')
    assert_equals "http://omv.locker.local/" "$omv_url" "OMV URL is correct"
    
    cleanup_test_env
}

# Test 3: Parsing with labels
test_parsing_with_labels() {
    test_case "Parsing with label overrides"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS="traefik-home.app.omv.enable=true
traefik-home.app.omv.alias=OpenMediaVault NAS
traefik-home.app.omv.icon=https://www.openmediavault.org/favicon.ico
traefik-home.app.rclone.enable=true
traefik-home.app.rclone.alias=Rclone WebUI
traefik-home.app.rclone.admin=true"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local omv_alias=$(echo "$output" | jq -r '.[0].Alias')
    assert_equals "OpenMediaVault NAS" "$omv_alias" "OMV alias is applied"
    
    local omv_icon=$(echo "$output" | jq -r '.[0].Icon')
    assert_equals "https://www.openmediavault.org/favicon.ico" "$omv_icon" "OMV icon is applied"
    
    local rclone_admin=$(echo "$output" | jq -r '.[1].Admin')
    assert_equals "true" "$rclone_admin" "Rclone admin flag is applied"
    
    cleanup_test_env
}

# Test 4: Disabled apps are included but marked
test_disabled_apps() {
    test_case "Disabled apps handling"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS="traefik-home.app.omv.enable=false"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    # Disabled apps should not be in output (filtered by entrypoint)
    local count=$(echo "$output" | jq 'length' 2>/dev/null || echo "0")
    assert_equals "1" "$count" "Disabled app not included"
    
    cleanup_test_env
}

# Test 5: HTTPS protocol detection
test_https_protocol() {
    test_case "HTTPS protocol detection"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    local rclone_url=$(echo "$output" | jq -r '.[1].URL')
    assert_contains "$rclone_url" "https://" "Websecure uses HTTPS"
    
    cleanup_test_env
}

# Test 6: Path extraction
test_path_extraction() {
    test_case "Path extraction from rules"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    api:
      entryPoints:
        - web
      rule: "Host(`example.com`) && PathPrefix(`/api`)"
      service: api

  services:
    api:
      loadBalancer:
        servers:
          - url: "http://192.168.0.30:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local api_url=$(echo "$output" | jq -r '.[0].URL')
    assert_equals "http://example.com/api" "$api_url" "Path is extracted correctly"
    
    cleanup_test_env
}

# Test 7: Special characters in aliases
test_special_characters() {
    test_case "Special characters in aliases"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS='traefik-home.app.omv.alias=Test "App" & More'
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON with special chars"
    
    local alias=$(echo "$output" | jq -r '.[0].Alias')
    assert_contains "$alias" "Test" "Alias contains 'Test'"
    
    cleanup_test_env
}

# Test 8: Missing service handling
test_missing_service() {
    test_case "Missing service definition"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    broken:
      entryPoints:
        - web
      rule: "Host(`broken.local`)"
      service: nonexistent

  services: {}
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local count=$(echo "$output" | jq 'length')
    assert_equals "0" "$count" "Router without service is skipped"
    
    cleanup_test_env
}

# Test 9: Multiple hosts in rule (should use first)
test_multiple_hosts() {
    test_case "Multiple hosts in rule"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    multi:
      entryPoints:
        - web
      rule: "Host(`first.local`) || Host(`second.local`)"
      service: multi

  services:
    multi:
      loadBalancer:
        servers:
          - url: "http://192.168.0.40:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Output is valid JSON"
    
    local url=$(echo "$output" | jq -r '.[0].URL')

    assert_contains "$url" "first.local" "Uses first host in multi-host rule"
    
    cleanup_test_env
}

# Test 10: External flag is always set
test_external_flag() {
    test_case "External flag is set"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    local is_external=$(echo "$output" | jq -r '.[0].External')
    assert_equals "true" "$is_external" "External flag is true"
    
    local is_running=$(echo "$output" | jq -r '.[0].Running')
    assert_equals "true" "$is_running" "Running flag is true"
    
    cleanup_test_env
}

# Run all tests
echo "========================================"
echo "  parse-external-apps.sh Unit Tests"
echo "========================================"
echo ""

test_empty_config
test_basic_parsing_no_labels
test_parsing_with_labels
test_disabled_apps
test_https_protocol
test_path_extraction
test_special_characters
test_missing_service
test_multiple_hosts
test_external_flag

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
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
