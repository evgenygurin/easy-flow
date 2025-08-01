#!/bin/bash

# Claude Security Check Script
# This script validates user permissions before allowing Claude execution
# Usage: ./claude-security-check.sh <github_actor> <association> <event_name>

set -e

GITHUB_ACTOR="$1"
ASSOCIATION="$2" 
EVENT_NAME="$3"
CONFIG_FILE=".github/claude-config.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Check if user is in whitelist
check_whitelist() {
    if grep -q "- $GITHUB_ACTOR" "$CONFIG_FILE" 2>/dev/null; then
        log "${GREEN}✓ User $GITHUB_ACTOR is whitelisted${NC}"
        return 0
    fi
    return 1
}

# Check user association
check_association() {
    case "$ASSOCIATION" in
        "OWNER"|"MEMBER"|"COLLABORATOR")
            log "${GREEN}✓ User $GITHUB_ACTOR has valid association: $ASSOCIATION${NC}"
            return 0
            ;;
        *)
            log "${RED}✗ User $GITHUB_ACTOR has invalid association: $ASSOCIATION${NC}"
            return 1
            ;;
    esac
}

# Check rate limiting (simplified version - in production would use external storage)
check_rate_limit() {
    local rate_file="/tmp/claude-rate-$GITHUB_ACTOR"
    local current_time=$(date +%s)
    local cooldown_period=300  # 5 minutes in seconds
    
    if [[ -f "$rate_file" ]]; then
        local last_request=$(cat "$rate_file")
        local time_diff=$((current_time - last_request))
        
        if [[ $time_diff -lt $cooldown_period ]]; then
            local wait_time=$((cooldown_period - time_diff))
            log "${YELLOW}⚠ Rate limit: User $GITHUB_ACTOR must wait $wait_time seconds${NC}"
            return 1
        fi
    fi
    
    # Update last request time
    echo "$current_time" > "$rate_file"
    log "${GREEN}✓ Rate limit check passed for $GITHUB_ACTOR${NC}"
    return 0
}

# Main security check
main() {
    log "🔒 Starting security check for user: $GITHUB_ACTOR"
    log "📋 Association: $ASSOCIATION, Event: $EVENT_NAME"
    
    # Check if config file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log "${YELLOW}⚠ Config file not found, using default security settings${NC}"
    fi
    
    # Perform checks
    if check_whitelist; then
        log "${GREEN}✅ Security check passed (whitelisted user)${NC}"
        exit 0
    fi
    
    if ! check_association; then
        log "${RED}❌ Security check failed (invalid association)${NC}"
        exit 1
    fi
    
    if ! check_rate_limit; then
        log "${RED}❌ Security check failed (rate limited)${NC}"
        exit 1
    fi
    
    log "${GREEN}✅ All security checks passed for $GITHUB_ACTOR${NC}"
    exit 0
}

# Handle missing arguments
if [[ $# -lt 3 ]]; then
    log "${RED}Usage: $0 <github_actor> <association> <event_name>${NC}"
    exit 1
fi

main "$@"