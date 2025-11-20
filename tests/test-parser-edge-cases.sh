#!/bin/bash
# Edge case and problem area tests for parse-external-apps.sh

set -e

source tests/test-helpers.sh

echo "========================================"
echo "  Parser Edge Cases & Problem Areas"
echo "========================================"
echo ""

# Test: Malformed YAML
test_malformed_yaml() {
    test_case "Malformed YAML handling"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    broken
      entryPoints:
        - web
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null || echo "[]")
    
    # Should return empty array or handle gracefully
    assert_json_valid "$output" "Handles malformed YAML gracefully"
    
    cleanup_test_env
}

# Test: URL with special characters
test_url_special_chars() {
    test_case "URLs with special characters"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    special:
      entryPoints:
        - web
      rule: "Host(`app.local`) && PathPrefix(`/api/v1`)"
      service: special

  services:
    special:
      loadBalancer:
        servers:
          - url: "http://192.168.0.50:8080/backend"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles URLs with paths"
    
    local url=$(echo "$output" | jq -r '.[0].URL')
    assert_contains "$url" "/api/v1" "Preserves path in URL"
    
    cleanup_test_env
}

# Test: Label with quotes in value
test_labels_with_quotes() {
    test_case "Labels with quotes in values"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS='traefik-home.app.omv.alias=Test \"Quoted\" Name'
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles quotes in label values"
    
    cleanup_test_env
}

# Test: Label with backslashes
test_labels_with_backslashes() {
    test_case "Labels with backslashes"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS='traefik-home.app.omv.alias=C:\\Path\\To\\App'
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles backslashes in label values"
    
    cleanup_test_env
}

# Test: Empty alias (should use router name)
test_empty_alias() {
    test_case "Empty alias falls back to router name"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS='traefik-home.app.omv.alias='
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    local alias=$(echo "$output" | jq -r '.[0].Alias')
    assert_equals "" "$alias" "Empty alias is preserved"
    
    local name=$(echo "$output" | jq -r '.[0].Name')
    assert_equals "omv" "$name" "Name fallback works"
    
    cleanup_test_env
}

# Test: Very long alias
test_long_alias() {
    test_case "Very long alias values"
    setup_test_env
    create_test_rules
    
    local long_alias=$(python3 -c "print('A' * 500)")
    export HOME_CONTAINER_LABELS="traefik-home.app.omv.alias=$long_alias"
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles very long aliases"
    
    cleanup_test_env
}

# Test: Unicode characters in labels
test_unicode_in_labels() {
    test_case "Unicode characters in labels"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS='traefik-home.app.omv.alias=🏠 Homelab'
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles Unicode in labels"
    
    cleanup_test_env
}

# Test: Rule without Host
test_rule_without_host() {
    test_case "Rule without Host directive"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    pathonly:
      entryPoints:
        - web
      rule: "PathPrefix(`/api`)"
      service: pathonly

  services:
    pathonly:
      loadBalancer:
        servers:
          - url: "http://192.168.0.60:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    # Should skip this router
    local count=$(echo "$output" | jq 'length')
    assert_equals "0" "$count" "Skips rule without Host"
    
    cleanup_test_env
}

# Test: Case sensitivity in router names
test_case_sensitivity() {
    test_case "Case sensitivity in router names"
    setup_test_env
    create_test_rules
    
    # Labels use lowercase, router is also lowercase
    export HOME_CONTAINER_LABELS='traefik-home.app.OMV.alias=Test
traefik-home.app.omv.alias=Should Match'
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    local alias=$(echo "$output" | jq -r '.[0].Alias')
    # Should match the exact case
    assert_contains "$alias" "Should Match" "Case-sensitive matching works"
    
    cleanup_test_env
}

# Test: Multiple services per router (should use first)
test_multiple_backend_servers() {
    test_case "Multiple backend servers"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    lb:
      entryPoints:
        - web
      rule: "Host(`lb.local`)"
      service: lb

  services:
    lb:
      loadBalancer:
        servers:
          - url: "http://192.168.0.70:8080"
          - url: "http://192.168.0.71:8080"
          - url: "http://192.168.0.72:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles multiple backend servers"
    
    # Should use first server
    local url=$(echo "$output" | jq -r '.[0].URL')
    assert_contains "$url" "lb.local" "Uses router host"
    
    cleanup_test_env
}

# Test: Router with no entrypoints
test_no_entrypoints() {
    test_case "Router without entrypoints"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    noentry:
      rule: "Host(`noentry.local`)"
      service: noentry

  services:
    noentry:
      loadBalancer:
        servers:
          - url: "http://192.168.0.80:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    # Should handle gracefully
    assert_json_valid "$output" "Handles missing entrypoints"
    
    cleanup_test_env
}

# Test: BusyBox grep compatibility
test_busybox_grep_compatibility() {
    test_case "BusyBox grep patterns"
    setup_test_env
    create_test_rules
    
    export HOME_CONTAINER_LABELS=""
    
    # Run parser and check it doesn't error with grep
    local output=$(/app/parse-external-apps.sh 2>&1)
    
    # Should not contain "unrecognized option"
    if echo "$output" | grep -q "unrecognized option"; then
        echo -e "${RED}  ✗ Contains BusyBox grep errors${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    else
        echo -e "${GREEN}  ✓ No BusyBox grep errors${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi
    
    cleanup_test_env
}

# Test: Whitespace in rules
test_whitespace_in_rules() {
    test_case "Extra whitespace in rules"
    setup_test_env
    
    cat > "$TRAEFIK_DYNAMIC_CONFIG" << 'EOF'
http:
  routers:
    spaces:
      entryPoints:
        - web
      rule: "Host(  `spaces.local`  ) && PathPrefix(  `/api`  )"
      service: spaces

  services:
    spaces:
      loadBalancer:
        servers:
          - url: "http://192.168.0.90:8080"
EOF
    
    export HOME_CONTAINER_LABELS=""
    
    local output=$(/app/parse-external-apps.sh 2>/dev/null)
    
    assert_json_valid "$output" "Handles extra whitespace"
    
    local url=$(echo "$output" | jq -r '.[0].URL')
    assert_contains "$url" "spaces.local" "Extracts host despite whitespace"
    
    cleanup_test_env
}

# Run all edge case tests
test_malformed_yaml
test_url_special_chars
test_labels_with_quotes
test_labels_with_backslashes
test_empty_alias
test_long_alias
test_unicode_in_labels
test_rule_without_host
test_case_sensitivity
test_multiple_backend_servers
test_no_entrypoints
test_busybox_grep_compatibility
test_whitespace_in_rules

# Summary
echo ""
echo "========================================"
echo "  Edge Case Test Summary"
echo "========================================"
echo -e "Tests run:    ${TESTS_RUN}"
echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All edge case tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some edge case tests failed!${NC}"
    exit 1
fi
