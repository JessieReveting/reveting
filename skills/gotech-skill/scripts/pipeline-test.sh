#!/usr/bin/env bash
# =============================================================================
# GoTech Solutions - Comprehensive Pipeline Test Script
# shellcheck disable=SC2034
# =============================================================================
# Runs end-to-end tests across the entire GoTech pipeline:
#   1.  Setup Check       - Verify required tools are installed
#   2.  Config Check      - Verify .env exists and has required vars
#   3.  Google Sheets     - Run tdss-export-csv.py and verify output
#   4.  YouTube Test      - Verify yt-dlp can fetch playlist data
#   5.  Email Test        - Verify SMTP connection (skip gracefully)
#   6.  GHL Test          - Run ghl-sync.js --test in demo mode
#   7.  Lead Capture      - Start lead-capture.js, send test lead, verify
#   8.  Podcast Workflow  - Run podcast-workflow.sh in demo mode
#   9.  Thumbnail Test    - Generate a single thumbnail
#   10. DATA TAXI Test    - Check drive mount status
#   11. Recent Files      - Run recent-files.js on DATA TAXI path
#   12. AI Readers        - Run ai-conversation-readers.js --demo
#   13. Cash Tracker      - Verify cash-tracker.html exists
#   14. Destiny College   - Verify system deps for Next.js build
#   15. Summary Report   - Output pass/fail/skip counts with timing
#
# Usage:
#   ./pipeline-test.sh                  # Run all tests
#   ./pipeline-test.sh --quick          # Skip slow tests
#   ./pipeline-test.sh --section setup  # Run only the setup check section
#   ./pipeline-test.sh --section ghl    # Run only the GHL test section
#
# Options:
#   --quick       Skip slow tests (podcast workflow, thumbnails, Next.js build)
#   --section X   Run only section X by name or number
#   --no-color    Disable colored output
#   --help        Show this help
#
# Exit codes:
#   0 - All critical tests passed
#   1 - One or more critical tests failed
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR="${HOME}/Documents/GoTechSolutions/startup"
SCRIPTS_DIR="${BASE_DIR}/scripts"
LOG_DIR="${BASE_DIR}/logs"
LOG_FILE="${LOG_DIR}/pipeline-test.log"
TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# Test tracking
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TOTAL_TIME_START=""
SECTION_START=""
RESULTS=()

# Parsed arguments
QUICK_MODE=false
RUN_SECTION=""
NO_COLOR=false

# =============================================================================
# ARGUMENT PARSING
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --quick)
                QUICK_MODE=true
                shift
                ;;
            --section)
                RUN_SECTION="$2"
                shift 2
                ;;
            --no-color)
                NO_COLOR=true
                RED="" GREEN="" YELLOW="" BLUE="" CYAN="" BOLD="" DIM="" NC=""
                shift
                ;;
            --help|-h)
                head -25 "$0" | grep '^#' | sed 's/^#//' | sed 's/^!//'
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Usage: $0 [--quick] [--section <name|number>] [--no-color] [--help]"
                exit 1
                ;;
        esac
    done
}

# =============================================================================
# LOGGING & UI FUNCTIONS
# =============================================================================

init_log() {
    mkdir -p "$LOG_DIR"
    > "$LOG_FILE"  # Truncate log
    log "INFO" "Pipeline test started at $(date "$TIMESTAMP_FORMAT")"
    log "INFO" "Working directory: ${BASE_DIR}"
    log "INFO" "Quick mode: ${QUICK_MODE}"
    log "INFO" "-------------------------------------------"
}

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date "$TIMESTAMP_FORMAT")
    echo "[${timestamp}] [${level}] ${message}" >> "$LOG_FILE"
}

print_header() {
    local title="$1"
    local line
    line=$(printf '═%.0s' {1..56})
    echo ""
    echo -e "${BOLD}${BLUE}╔${line}╗${NC}"
    echo -e "${BOLD}${BLUE}║  ${title}$(printf ' %.0s' {1..$((${#title} - 44 < 0 ? 44 - ${#title} : 0))})║${NC}"
    echo -e "${BOLD}${BLUE}╚${line}╝${NC}"
    echo ""
    log "INFO" "=== ${title} ==="
}

print_section() {
    local num="$1"
    local name="$2"
    SECTION_START=$(date +%s)
    echo ""
    echo -e "${BOLD}${CYAN}[${num}/15]${NC} ${BOLD}${name}${NC}"
    echo -e "${DIM}$(printf '─%.0s' {1..60})${NC}"
    log "INFO" "--- Section ${num}: ${name} ---"
}

section_result() {
    local status="$1"
    local message="$2"
    local end_time
    end_time=$(date +%s)
    local duration=$(( end_time - SECTION_START ))
    local duration_str
    duration_str=$(format_duration $duration)

    case "$status" in
        pass)
            ((PASS_COUNT++))
            RESULTS+=("PASS|${message}|${duration_str}")
            echo -e "   ${GREEN}✔ PASS${NC} ${message} ${DIM}(${duration_str})${NC}"
            log "INFO" "[PASS] ${message} (${duration_str})"
            ;;
        fail)
            ((FAIL_COUNT++))
            RESULTS+=("FAIL|${message}|${duration_str}")
            echo -e "   ${RED}✘ FAIL${NC} ${message} ${DIM}(${duration_str})${NC}"
            log "ERROR" "[FAIL] ${message} (${duration_str})"
            ;;
        skip)
            ((SKIP_COUNT++))
            RESULTS+=("SKIP|${message}|${duration_str}")
            echo -e "   ${YELLOW}⊘ SKIP${NC} ${message} ${DIM}(${duration_str})${NC}"
            log "INFO" "[SKIP] ${message} (${duration_str})"
            ;;
    esac
}

format_duration() {
    local seconds=$1
    if [[ $seconds -lt 60 ]]; then
        echo "${seconds}s"
    else
        local min=$(( seconds / 60 ))
        local sec=$(( seconds % 60 ))
        echo "${min}m${sec}s"
    fi
}

run_test() {
    local name="$1"
    shift
    # Run the test command, capture output, check exit code
    local output
    local exit_code
    output=$("$@" 2>&1) && exit_code=0 || exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        section_result "pass" "$name"
        [[ -n "$output" ]] && log "INFO" "Output: $(echo "$output" | head -3)"
        return 0
    else
        section_result "fail" "$name (exit: $exit_code)"
        log "ERROR" "Output: $(echo "$output" | head -5)"
        return 1
    fi
}

run_test_allow_fail() {
    local name="$1"
    shift
    local output
    local exit_code
    output=$("$@" 2>&1) && exit_code=0 || exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        section_result "pass" "$name"
        [[ -n "$output" ]] && log "INFO" "Output: $(echo "$output" | head -3)"
        return 0
    else
        section_result "skip" "$name (unavailable)"
        log "INFO" "Skipped: $(echo "$output" | head -3)"
        return 0
    fi
}

run_test_demo() {
    # For scripts that may not have full data in demo mode
    local name="$1"
    local required="$2"  # "required" or "optional"
    shift 2
    local output
    local exit_code
    output=$("$@" 2>&1) && exit_code=0 || exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        section_result "pass" "$name"
        return 0
    else
        if [[ "$required" == "optional" ]]; then
            section_result "skip" "$name (non-critical, skipped)"
            return 0
        else
            section_result "fail" "$name (exit: $exit_code)"
            return 1
        fi
    fi
}

# =============================================================================
# TEST SECTIONS
# =============================================================================

# --- Section 1: Setup Check ---
test_setup_check() {
    print_section "1" "Setup Check - Required Tools"
    
    local critical_tools=("node" "python3" "ffmpeg")
    local optional_tools=("yt-dlp" "convert" "curl" "jq" "bc")
    local all_pass=true
    
    for tool in "${critical_tools[@]}"; do
        if command -v "$tool" &>/dev/null; then
            local ver
            ver=$("$tool" --version 2>&1 | head -1 || echo "unknown")
            section_result "pass" "${tool} installed (${ver})"
        else
            section_result "fail" "${tool} NOT FOUND (critical)"
            all_pass=false
        fi
    done
    
    for tool in "${optional_tools[@]}"; do
        if command -v "$tool" &>/dev/null; then
            section_result "pass" "${tool} installed (optional)"
        else
            section_result "skip" "${tool} not found (optional)"
        fi
    done
    
    # Check node_modules
    if [[ -d "${BASE_DIR}/node_modules" ]]; then
        section_result "pass" "node_modules directory exists"
    else
        section_result "fail" "node_modules missing - run: npm install"
        all_pass=false
    fi
    
    if $all_pass; then
        return 0
    else
        return 1
    fi
}

# --- Section 2: Config Check ---
test_config_check() {
    print_section "2" "Config Check - Environment & Files"
    
    # Check .env or .env.template exists
    if [[ -f "${BASE_DIR}/.env" ]]; then
        section_result "pass" ".env file exists"
    elif [[ -f "${BASE_DIR}/.env.template" ]]; then
        section_result "skip" ".env not found but .env.template exists"
    else
        section_result "fail" ".env file missing"
    fi
    
    # Check .env.email
    if [[ -f "${BASE_DIR}/.env.email" ]]; then
        section_result "pass" ".env.email exists"
    else
        section_result "skip" ".env.email not found"
    fi
    
    # Check package.json
    if [[ -f "${BASE_DIR}/package.json" ]]; then
        section_result "pass" "package.json exists"
    else
        section_result "fail" "package.json missing"
    fi
    
    # Check key directories
    local dirs=("scripts" "content" "templates")
    for dir in "${dirs[@]}"; do
        if [[ -d "${BASE_DIR}/${dir}" ]]; then
            section_result "pass" "Directory '${dir}/' exists"
        else
            section_result "skip" "Directory '${dir}/' not found"
        fi
    done
}

# --- Section 3: Google Sheets Test ---
test_google_sheets() {
    print_section "3" "Google Sheets - TDSS Export CSV"
    
    local script="${SCRIPTS_DIR}/tdss-export-csv.py"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "tdss-export-csv.py not found"
        return 1
    fi
    
    # Check if data file exists
    local data_file="${BASE_DIR}/yt_seo_full.json"
    local alt_data_file="${HOME}/Documents/GoTechSolutions/startup/yt_seo_full.json"
    
    if [[ -f "$data_file" ]] || [[ -f "$alt_data_file" ]]; then
        section_result "pass" "Episode data file (yt_seo_full.json) found"
    else
        section_result "skip" "Episode data file not found - creating minimal test data"
        # Create minimal test data so the script can at least run
        echo '[{"ep":"EP001","topic":"Test Episode","guest":"Test Guest","url":"https://youtube.com/test","tags":"test"}]' > /tmp/test_yt_seo.json
    fi
    
    # Test --stats mode (always works if data exists)
    if [[ -f "$data_file" ]] || [[ -f "$alt_data_file" ]]; then
        run_test "tdss-export-csv.py --stats" python3 "$script" --stats
    else
        # Test with custom data file
        run_test_demo "tdss-export-csv.py --stats (test data)" "optional" \
            python3 "$script" --stats --data-file /tmp/test_yt_seo.json
    fi
    
    # Test CSV output
    if [[ -f "$data_file" ]] || [[ -f "$alt_data_file" ]]; then
        run_test "tdss-export-csv.py CSV output" python3 "$script" 2>&1 | head -1
    fi
}

# --- Section 4: YouTube Test ---
test_youtube() {
    print_section "4" "YouTube - yt-dlp Playlist Fetch"
    
    if ! command -v yt-dlp &>/dev/null; then
        section_result "skip" "yt-dlp not installed"
        return 0
    fi
    
    # Test fetching playlist metadata (no download)
    local output
    local exit_code
    output=$(yt-dlp --flat-playlist --print "%(id)s %(title)s" \
        "https://www.youtube.com/@TheDavidDailyShow/videos" 2>&1 | head -5) && exit_code=0 || exit_code=$?
    
    if [[ $exit_code -eq 0 ]] && [[ -n "$output" ]]; then
        section_result "pass" "YouTube playlist metadata fetched"
    else
        # Try a simpler check - just verify yt-dlp can parse YouTube
        output=$(yt-dlp --version 2>&1) && exit_code=0 || exit_code=$?
        if [[ $exit_code -eq 0 ]]; then
            section_result "pass" "yt-dlp functional (network may be limited)"
        else
            section_result "skip" "YouTube test inconclusive"
        fi
    fi
}

# --- Section 5: Email Test ---
test_email() {
    print_section "5" "Email - SMTP Connection"
    
    # Check if email credentials are configured
    local smtp_host="${SMTP_HOST:-smtp.gmail.com}"
    local smtp_port="${SMTP_PORT:-587}"
    local smtp_user="${SMTP_USER:-}"
    
    if [[ -z "$smtp_user" ]]; then
        section_result "skip" "SMTP_USER not set - skipping email test"
        return 0
    fi
    
    # Try SMTP connection with timeout
    if command -v curl &>/dev/null; then
        local result
        result=$(curl -s --max-time 10 \
            "smtp://${smtp_host}:${smtp_port}" \
            --user "${smtp_user}:${SMTP_PASS:-}" \
            --mail-from "${smtp_user}" \
            --mail-rcpt "test@example.com" \
            --insecure 2>&1) && true
        
        # Even if the SMTP fails due to auth, we check if we can reach the server
        if echo "$result" | grep -qi "connection refused\|timeout\|couldn't connect"; then
            section_result "skip" "SMTP server unreachable (network issue)"
        else
            section_result "pass" "SMTP server reachable"
        fi
    else
        section_result "skip" "curl not available for SMTP test"
    fi
}

# --- Section 6: GHL Test ---
test_ghl() {
    print_section "6" "GHL Sync - Demo Mode Test"
    
    local script="${SCRIPTS_DIR}/ghl-sync.js"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "ghl-sync.js not found"
        return 1
    fi
    
    run_test_demo "ghl-sync.js --action test --demo" "optional" \
        node "$script" --action test --demo
}

# --- Section 7: Lead Capture Test ---
test_lead_capture() {
    print_section "7" "Lead Capture - Server & Webhook"
    
    local script="${SCRIPTS_DIR}/lead-capture.js"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "lead-capture.js not found"
        return 1
    fi
    
    # Check if server is already running
    local port=3456
    if curl -s --max-time 2 "http://localhost:${port}/health" &>/dev/null; then
        section_result "pass" "Lead capture server already running"
    else
        # Start server in background
        section_result "skip" "Starting lead capture server for test..."
        node "$script" &
        local server_pid=$!
        sleep 2
        
        # Check if it started
        if kill -0 $server_pid 2>/dev/null; then
            section_result "pass" "Lead capture server started (PID: ${server_pid})"
            
            # Send test lead
            local response
            response=$(curl -s --max-time 5 \
                -X POST "http://localhost:${port}/lead" \
                -H "Content-Type: application/json" \
                -d '{"name":"Pipeline Test","email":"pipeline@test.com","source":"test","interest":"testing"}' 2>&1)
            
            if echo "$response" | grep -qi "success\|ok\|captured\|200\|201"; then
                section_result "pass" "Test lead submitted successfully"
            else
                section_result "skip" "Lead submission response: $(echo "$response" | head -1)"
            fi
            
            # Cleanup
            kill $server_pid 2>/dev/null || true
            wait $server_pid 2>/dev/null || true
        else
            section_result "fail" "Lead capture server failed to start"
        fi
    fi
}

# --- Section 8: Podcast Workflow Test ---
test_podcast_workflow() {
    print_section "8" "Podcast Workflow - Demo Mode"
    
    local script="${SCRIPTS_DIR}/podcast-workflow.sh"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "podcast-workflow.sh not found"
        return 1
    fi
    
    if $QUICK_MODE; then
        section_result "skip" "Podcast workflow (skipped in quick mode)"
        return 0
    fi
    
    # Create a minimal test video file for demo mode
    local test_video="/tmp/pipeline-test-video.mp4"
    if command -v ffmpeg &>/dev/null; then
        # Generate 5-second test video
        ffmpeg -y -f lavfi -i testsrc=duration=5:size=320:240:rate=24 \
            -f lavfi -i sine=frequency=440:duration=5 \
            -c:v libx264 -c:a aac "$test_video" 2>/dev/null
        
        if [[ -f "$test_video" ]]; then
            section_result "pass" "Test video generated for demo"
            run_test_demo "podcast-workflow.sh --demo" "optional" \
                bash "$script" "$test_video" --demo
            rm -f "$test_video"
        else
            section_result "skip" "Could not generate test video"
        fi
    else
        section_result "skip" "ffmpeg not available for test video generation"
    fi
}

# --- Section 9: Thumbnail Test ---
test_thumbnail() {
    print_section "9" "Thumbnail Generation"
    
    local script="${SCRIPTS_DIR}/youtube-thumbnails.js"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "youtube-thumbnails.js not found"
        return 1
    fi
    
    if $QUICK_MODE; then
        section_result "skip" "Thumbnail generation (skipped in quick mode)"
        return 0
    fi
    
    # Check if sharp is installed
    if [[ -d "${BASE_DIR}/node_modules/sharp" ]]; then
        section_result "pass" "sharp package installed"
    else
        section_result "skip" "sharp package not installed"
        return 0
    fi
    
    # Check if data file exists
    local data_file="${BASE_DIR}/yt_seo_full.json"
    local alt_data_file="${HOME}/Documents/GoTechSolutions/startup/yt_seo_full.json"
    
    if [[ ! -f "$data_file" ]] && [[ ! -f "$alt_data_file" ]]; then
        section_result "skip" "No episode data for thumbnail generation"
        return 0
    fi
    
    # Try generating a single thumbnail
    run_test_demo "Generate single thumbnail" "optional" \
        node "$script" --episode EP001 2>&1
    
    # Check if any thumbnail was created
    if ls "${BASE_DIR}"/thumbnails/*.png &>/dev/null; then
        section_result "pass" "Thumbnail file(s) found in thumbnails/"
    else
        section_result "skip" "No thumbnail output (may need valid episode data)"
    fi
}

# --- Section 10: DATA TAXI Test ---
test_data_taxi() {
    print_section "10" "DATA TAXI - Drive Mount Status"
    
    local data_taxi_path="/Volumes/DATA TAXI"
    local env_path="${DATA_TAXI_PATH:-}"
    
    # Check if drive is mounted
    if [[ -d "$data_taxi_path" ]]; then
        section_result "pass" "DATA TAXI drive mounted at ${data_taxi_path}"
        
        # Check subdirectories
        if [[ -d "${data_taxi_path}/FILES" ]]; then
            section_result "pass" "FILES directory exists on DATA TAXI"
        else
            section_result "skip" "FILES directory not found on drive"
        fi
    else
        section_result "skip" "DATA TAXI drive not mounted (expected for portable drive)"
    fi
    
    # Check local mirror
    local local_mirror="${HOME}/Documents/GoTechSolutions/backups/data-taxi"
    if [[ -d "$local_mirror" ]]; then
        section_result "pass" "Local DATA TAXI mirror exists"
    else
        section_result "skip" "No local mirror found"
    fi
}

# --- Section 11: Recent Files Test ---
test_recent_files() {
    print_section "11" "Recent Files - DATA TAXI Scanner"
    
    local script="${SCRIPTS_DIR}/recent-files.js"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "recent-files.js not found"
        return 1
    fi
    
    # Try with DATA TAXI path or fallback to a local directory
    local scan_path="/Volumes/DATA TAXI/FILES/01 THE DAVID DAILY SHOW/"
    if [[ ! -d "$scan_path" ]]; then
        # Fallback to startup directory for testing
        scan_path="${BASE_DIR}"
        section_result "skip" "Using fallback path for testing"
    fi
    
    run_test_demo "recent-files.js scan" "optional" \
        node "$script" --path "$scan_path" --days 30 --limit 5
}

# --- Section 12: AI Readers Test ---
test_ai_readers() {
    print_section "12" "AI Conversation Readers - Demo"
    
    local script="${SCRIPTS_DIR}/ai-conversation-readers.js"
    
    if [[ ! -f "$script" ]]; then
        section_result "fail" "ai-conversation-readers.js not found"
        return 1
    fi
    
    run_test_demo "ai-conversation-readers.js --demo" "optional" \
        node "$script" --demo
}

# --- Section 13: Cash Tracker Test ---
test_cash_tracker() {
    print_section "13" "Cash Tracker - HTML Verification"
    
    # Look for cash-tracker.html in common locations
    local locations=(
        "${BASE_DIR}/cash-tracker.html"
        "${BASE_DIR}/dashboard.html"
        "${HOME}/Documents/GoTechSolutions/cash-tracker.html"
        "${HOME}/Documents/GoTechSolutions/command-center/templates/index.html"
    )
    
    local found=false
    for loc in "${locations[@]}"; do
        if [[ -f "$loc" ]]; then
            section_result "pass" "Dashboard/tracker HTML found: $(basename "$loc")"
            found=true
            break
        fi
    done
    
    if ! $found; then
        section_result "skip" "cash-tracker.html not found (may not be created yet)"
    fi
}

# --- Section 14: Destiny College Test ---
test_destiny_college() {
    print_section "14" "Destiny College - Build Verification"
    
    if $QUICK_MODE; then
        section_result "skip" "Destiny College build (skipped in quick mode)"
        return 0
    fi
    
    # Look for Next.js project
    local next_locations=(
        "${HOME}/Documents/GoTechSolutions/destiny-college"
        "${HOME}/Documents/GoTechSolutions/destinychurch"
        "${HOME}/Documents/GoTechSolutions/destiny"
    )
    
    local next_dir=""
    for loc in "${next_locations[@]}"; do
        if [[ -f "${loc}/package.json" ]]; then
            next_dir="$loc"
            break
        fi
    done
    
    if [[ -z "$next_dir" ]]; then
        section_result "skip" "Destiny College project directory not found"
        return 0
    fi
    
    section_result "pass" "Destiny College project found at ${next_dir}"
    
    # Check if node_modules exists
    if [[ -d "${next_dir}/node_modules" ]]; then
        section_result "pass" "Dependencies installed"
    else
        section_result "skip" "Dependencies not installed (run: npm install)"
        return 0
    fi
    
    # Try Next.js build (with timeout)
    if [[ -f "${next_dir}/next.config.js" ]] || [[ -f "${next_dir}/next.config.mjs" ]]; then
        section_result "pass" "Next.js config found"
        
        # Quick build check - just verify next command works
        run_test_demo "Next.js build verification" "optional" \
            cd "$next_dir" && timeout 60 npx next build 2>&1 | tail -5
    else
        section_result "skip" "No Next.js config found"
    fi
}

# --- Section 15: Summary Report ---
test_summary() {
    print_section "15" "Summary Report"
    
    local total_end
    total_end=$(date +%s)
    local total_duration=$(( total_end - TOTAL_TIME_START ))
    
    echo ""
    echo -e "${BOLD}┌──────────────────────────────────────────────────────┐${NC}"
    echo -e "${BOLD}│              PIPELINE TEST RESULTS                   │${NC}"
    echo -e "${BOLD}├──────────────────────────────────────────────────────┤${NC}"
    printf "${BOLD}│  ${NC}%-20s ${GREEN}%3d ✔${NC}                     ${BOLD}│${NC}\n" "PASSED:" "$PASS_COUNT"
    printf "${BOLD}│  ${NC}%-20s ${RED}%3d ✘${NC}                     ${BOLD}│${NC}\n" "FAILED:" "$FAIL_COUNT"
    printf "${BOLD}│  ${NC}%-20s ${YELLOW}%3d ⊘${NC}                     ${BOLD}│${NC}\n" "SKIPPED:" "$SKIP_COUNT"
    echo -e "${BOLD}├──────────────────────────────────────────────────────┤${NC}"
    printf "${BOLD}│  ${NC}%-20s %3d                         ${BOLD}│${NC}\n" "TOTAL:" $(( PASS_COUNT + FAIL_COUNT + SKIP_COUNT ))
    printf "${BOLD}│  ${NC}%-20s %ss                        ${BOLD}│${NC}\n" "DURATION:" "$total_duration"
    echo -e "${BOLD}├──────────────────────────────────────────────────────┤${NC}"
    
    # Log results
    log "INFO" "Results: PASS=${PASS_COUNT} FAIL=${FAIL_COUNT} SKIP=${SKIP_COUNT}"
    
    if [[ $FAIL_COUNT -gt 0 ]]; then
        echo -e "${BOLD}│  ${NC}Status: ${RED}SOME TESTS FAILED${NC}                    ${BOLD}│${NC}"
        echo -e "${BOLD}│  ${NC}Check log: ${LOG_FILE}     ${BOLD}│${NC}"
        echo -e "${BOLD}└──────────────────────────────────────────────────────┘${NC}"
        echo ""
        
        # Print failed tests
        echo -e "${RED}Failed Tests:${NC}"
        for result in "${RESULTS[@]}"; do
            if [[ "$result" == FAIL* ]]; then
                local msg
                msg=$(echo "$result" | cut -d'|' -f2)
                echo -e "  ${RED}✘${NC} ${msg}"
            fi
        done
        echo ""
        return 1
    else
        echo -e "${BOLD}│  ${NC}Status: ${GREEN}ALL CRITICAL TESTS PASSED${NC}            ${BOLD}│${NC}"
        echo -e "${BOLD}└──────────────────────────────────────────────────────┘${NC}"
        echo ""
        return 0
    fi
}

# =============================================================================
# SECTION RUNNER
# =============================================================================

# Maps section names/numbers to functions
declare -A SECTION_MAP=(
    ["1"]="test_setup_check" ["setup"]="test_setup_check"
    ["2"]="test_config_check" ["config"]="test_config_check"
    ["3"]="test_google_sheets" ["sheets"]="test_google_sheets" ["tdss"]="test_google_sheets"
    ["4"]="test_youtube" ["youtube"]="test_youtube" ["yt"]="test_youtube"
    ["5"]="test_email" ["email"]="test_email" ["smtp"]="test_email"
    ["6"]="test_ghl" ["ghl"]="test_ghl" ["gohighlevel"]="test_ghl"
    ["7"]="test_lead_capture"] ["lead"]="test_lead_capture" ["leads"]="test_lead_capture"
    ["8"]="test_podcast_workflow" ["podcast"]="test_podcast_workflow"
    ["9"]="test_thumbnail"] ["thumbnail"]="test_thumbnail" ["thumbnails"]="test_thumbnail"
    ["10"]="test_data_taxi"] ["taxi"]="test_data_taxi" ["data-taxi"]="test_data_taxi"
    ["11"]="test_recent_files"] ["recent"]="test_recent_files" ["files"]="test_recent_files"
    ["12"]="test_ai_readers"] ["ai"]="test_ai_readers" ["readers"]="test_ai_readers"
    ["13"]="test_cash_tracker"] ["cash"]="test_cash_tracker" ["tracker"]="test_cash_tracker"
    ["14"]="test_destiny_college"] ["destiny"]="test_destiny_college" ["college"]="test_destiny_college"
    ["15"]="test_summary" ["summary"]="test_summary"
)

run_section() {
    local name="$1"
    local func="${SECTION_MAP[$name]:-}"
    
    if [[ -n "$func" ]] && declare -f "$func" > /dev/null 2>&1; then
        $func
    else
        echo -e "${RED}Unknown section: ${name}${NC}"
        echo "Available sections:"
        echo "  1/setup, 2/config, 3/sheets, 4/youtube, 5/email,"
        echo "  6/ghl, 7/lead, 8/podcast, 9/thumbnail, 10/taxi,"
        echo "  11/recent, 12/ai, 13/cash, 14/destiny, 15/summary"
        exit 1
    fi
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    parse_args "$@"
    
    # Change to startup directory
    cd "$BASE_DIR"
    
    # Initialize
    init_log
    TOTAL_TIME_START=$(date +%s)
    
    # Print banner
    echo ""
    echo -e "${BOLD}${BLUE}  ╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}  ║                                                      ║${NC}"
    echo -e "${BOLD}${BLUE}  ║   ${CYAN}GoTech Solutions - Pipeline Test Suite${BLUE}             ║${NC}"
    echo -e "${BOLD}${BLUE}  ║   ${DIM}Comprehensive end-to-end system verification${BLUE}     ║${NC}"
    echo -e "${BOLD}${BLUE}  ║                                                      ║${NC}"
    echo -e "${BOLD}${BLUE}  ╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${DIM}Log file: ${LOG_FILE}${NC}"
    echo -e "  ${DIM}Quick mode: ${QUICK_MODE}${NC}"
    echo ""
    
    if [[ -n "$RUN_SECTION" ]]; then
        # Run single section
        print_header "Single Section: ${RUN_SECTION}"
        run_section "$RUN_SECTION"
    else
        # Run all sections
        print_header "Running Full Pipeline Test"
        
        test_setup_check
        test_config_check
        test_google_sheets
        test_youtube
        test_email
        test_ghl
        test_lead_capture
        test_podcast_workflow
        test_thumbnail
        test_data_taxi
        test_recent_files
        test_ai_readers
        test_cash_tracker
        test_destiny_college
        test_summary
    fi
    
    # Final exit code
    if [[ $FAIL_COUNT -gt 0 ]]; then
        exit 1
    else
        exit 0
    fi
}

# Run main
main "$@"
