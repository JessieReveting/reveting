#!/usr/bin/env bash
#
# Go Live! - One-Click Startup Script for The David Daily Show
# ============================================================
# Usage:
#   chmod +x go-live.sh
#   ./go-live.sh
#
# Requirements: ffmpeg, yt-dlp, streamlink, OBS (optional)
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

# --- Paths ---
BASE_DIR="${HOME}/Documents/GoTechSolutions/startup"
SCRIPTS_DIR="${BASE_DIR}/scripts"
CONTENT_DIR="${BASE_DIR}/content"
DATA_TAXI="/Volumes/DATA TAXI/FILES/01 THE DAVID DAILY SHOW"
RECORDING_DIR="${DATA_TAXI}/recordings"
OBS_PROFILE_NAME="DavidDailyShow"
OBS_PROFILE_DIR="${HOME}/Library/Application Support/obs-studio/basic/profiles/${OBS_PROFILE_NAME}"
LOGS_DIR="${BASE_DIR}/output/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOCAL_RECORDING="${RECORDING_DIR}/DDS-LOCAL-BACKUP-${TIMESTAMP}.mp4"
MONITOR_LOG="${LOGS_DIR}/stream-monitor-${TIMESTAMP}.log"
PID_FILE="/tmp/golive-obs-${TIMESTAMP}.pid"

# --- StreamYard ---
STREAMYARD_URL="https://streamyard.com/broadcasts-xxxxxxx"

# --- OBS Settings ---
OBS_BIN="/Applications/OBS.app/Contents/MacOS/OBS"
OBS_STREAMING_SERVICE="stream,Yard"  # Custom service name
OBS_STARTUP_WAIT=15                  # Seconds to wait for OBS to launch

# --- FFmpeg Recording Settings ---
FFMPEG_INPUT="default"          # macOS default capture (use "Capture" for screen)
FFMPEG_FRAMERATE=30
FFMPEG_RESOLUTION="1920x1080"
FFMPEG_VIDEO_BITRATE="6000k"
FFMPEG_AUDIO_BITRATE="192k"
FFMPEG_CODEC="libx264"
FFMPEG_PRESET="veryfast"
FFMPEG_PROFILE="main"
FFMPEG_LEVEL="4.0"

# --- Monitoring ---
MONITOR_INTERVAL=10            # Check stream health every N seconds
RESTART_ATTEMPTS=3             # Auto-restart up to N times
RESTART_COOLDOWN=30            # Seconds between restart attempts

# --- Colors for terminal output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# =============================================================================
# INITIALIZATION
# =============================================================================

init() {
    # Create necessary directories
    mkdir -p "$LOGS_DIR" "$RECORDING_DIR" "$CONTENT_DIR"

    # Initialize monitor log
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stream monitor started" > "$MONITOR_LOG"

    echo -e "${BOLD}${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║          THE DAVID DAILY SHOW - GO LIVE!                ║"
    echo "║          One-Click Livestream Startup                   ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║  Timestamp: $(date '+%Y-%m-%d %H:%M:%S')                       ║"
    echo "║  Recording: ${LOCAL_RECORDING}                          "
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# =============================================================================
# LOGGING FUNCTIONS
# =============================================================================

log() {
    local level="$1"; shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_line="[${timestamp}] [${level}] ${message}"

    echo "$log_line" >> "$MONITOR_LOG"

    case "$level" in
        ERROR)   echo -e "${RED}[${level}]${NC} ${message}" ;;
        WARN)    echo -e "${YELLOW}[${level}]${NC} ${message}" ;;
        SUCCESS) echo -e "${GREEN}[${level}]${NC} ${message}" ;;
        INFO)    echo -e "${BLUE}[${level}]${NC} ${message}" ;;
        LIVE)    echo -e "${GREEN}${BOLD}[${level}]${NC} ${message}" ;;
    esac
}

notify() {
    local title="The David Daily Show"
    local message="$1"
    osascript -e "display notification \"${message}\" with title \"${title}\" subtitle \"Go Live System\""
}

# =============================================================================
# PREREQUISITE CHECKS
# =============================================================================

check_tools() {
    echo -e "\n${BOLD}【1/6】Checking required tools...${NC}\n"
    local errors=0

    # Required: ffmpeg
    if command -v ffmpeg &>/dev/null; then
        local ffmpeg_version
        ffmpeg_version=$(ffmpeg -version 2>&1 | head -1)
        log "SUCCESS" "ffmpeg found: ${ffmpeg_version}"
    else
        log "ERROR" "ffmpeg not found. Install with: brew install ffmpeg"
        ((errors++))
    fi

    # Required: ffprobe
    if command -v ffprobe &>/dev/null; then
        log "SUCCESS" "ffprobe found"
    else
        log "ERROR" "ffprobe not found (comes with ffmpeg). Install: brew install ffmpeg"
        ((errors++))
    fi

    # Optional: yt-dlp
    if command -v yt-dlp &>/dev/null; then
        local ytdlp_version
        ytdlp_version=$(yt-dlp --version 2>/dev/null || echo "unknown")
        log "SUCCESS" "yt-dlp found: ${ytdlp_version}"
        HAS_YTDLP=true
    else
        log "WARN" "yt-dlp not found. Auto-download unavailable. Install: brew install yt-dlp"
        HAS_YTDLP=false
    fi

    # Optional: streamlink
    if command -v streamlink &>/dev/null; then
        local streamlink_version
        streamlink_version=$(streamlink --version 2>/dev/null || echo "unknown")
        log "SUCCESS" "streamlink found: ${streamlink_version}"
        HAS_STREAMLINK=true
    else
        log "WARN" "streamlink not found. Install: brew install streamlink"
        HAS_STREAMLINK=false
    fi

    # Optional: OBS CLI (obs-cli via websocket or direct)
    if [[ -x "$OBS_BIN" ]]; then
        log "SUCCESS" "OBS Studio found at: ${OBS_BIN}"
        HAS_OBS=true
    elif [[ -d "/Applications/OBS.app" ]]; then
        OBS_BIN="/Applications/OBS.app/Contents/MacOS/OBS"
        HAS_OBS=true
        log "SUCCESS" "OBS Studio found"
    else
        log "WARN" "OBS Studio not found. Local OBS recording will be skipped."
        HAS_OBS=false
    fi

    # Optional: obs-cli
    if command -v obs-cli &>/dev/null || command -v obswebsocket &>/dev/null || pip3 list 2>/dev/null | grep -q obs-websocket-py; then
        log "SUCCESS" "OBS CLI/websocket found"
        HAS_OBS_CLI=true
    else
        log "WARN" "OBS CLI not found. OBS will start but cannot be controlled remotely."
        log "INFO" "Install: pip3 install obs-websocket-py"
        HAS_OBS_CLI=false
    fi

    # Check for stream monitoring tools
    if command -v streamlink &>/dev/null; then
        log "INFO" "Stream monitoring via streamlink available"
    elif ! $HAS_STREAMLINK && ! $HAS_OBS; then
        log "WARN" "No stream monitoring available. Health checks will be limited."
    fi

    # Check ffmpeg capabilities
    if command -v ffmpeg &>/dev/null; then
        if ffmpeg -filters 2>/dev/null | grep -q "capture"; then
            log "INFO" "ffmpeg screen capture filter available"
        fi
    fi

    if [[ $errors -gt 0 ]]; then
        log "ERROR" "Missing ${errors} required tool(s).
 Please install and retry."
        echo -e "\n${RED}Cannot proceed. Install required tools and run again.${NC}\n"
        exit 1
    fi

    echo -e "\n${GREEN}✓ All required tools are ready${NC}"
}

# =============================================================================
# DATA TAXI CHECK
# =============================================================================

check_data_taxi() {
    echo -e "\n${BOLD}【2/6】Checking DATA TAXI connection...${NC}\n"

    if [[ -d "$DATA_TAXI" ]]; then
        local available_space
        available_space=$(df -h "$DATA_TAXI" | awk 'NR==2 {print $4}')
        log "SUCCESS" "DATA TAXI mounted at ${DATA_TAXI}"             log "SUCCESS" "Available space: ${available_space}"
        echo -e "${GREEN}✓ DATA TAXI connected (${available_space} available)${NC}"
    else
        log "WARN" "DATA TAXI not found at ${DATA_TAXI}"
        echo -e "${YELLOW}⚠ DATA TAXI not mounted!${NC}"
        read -rp "Continue anyway? (y/N) " choice
        if [[ ! "$choice" =~ ^[Yy]$ ]]; then
            log "INFO" "Aborted by user"
            notify "Go Live aborted - DATA TAXI not connected"
            exit 0
        fi
        local fallback_dir="${HOME}/Documents/GoTechSolutions/startup/recordings"
        mkdir -p "$fallback_dir"
        LOCAL_RECORDING="${fallback_dir}/DDS-LOCAL-BACKUP-${TIMESTAMP}.mp4"
        log "WARN" "Fallback recording path: ${LOCAL_RECORDING}"
        echo -e "${YELLOW}Recording will be saved to: ${LOCAL_RECORDING}${NC}"
    fi
}

# =============================================================================
# START OBS
# =============================================================================

start_obs() {
    echo -e "\n${BOLD}【3/6】Starting OBS Studio...${NC}\n"

    if ! $HAS_OBS; then
        log "INFO" "Skipping OBS startup (not installed)"
        echo -e "${YELLOW}⚠ Skipping OBS (not installed)${NC}"
        return 0
    fi

    # Check if OBS is already running
    if pgrep -f "OBS.app" &>/dev/null; then
        log "WARN" "OBS is already running. Attempting to use existing instance..."
        echo -e "${YELLOW}⚠ OBS already running. Using existing instance.${NC}"
        notify "OBS already running - using existing instance"

        # Try to use OBS websocket to start streaming
        if $HAS_OBS_CLI; then
            start_obs_streaming_cli
        fi
        return 0
    fi

    # Start OBS with the specific profile
    log "INFO" "Launching OBS with profile: ${OBS_PROFILE_NAME}"
    echo -e "${BLUE}→ Launching OBS Studio...${NC}"

    if $HAS_OBS_CLI && command -v obs-cli &>/dev/null; then
        # Use OBS CLI to start streaming
        obs-cli --start-streaming --profile "$OBS_PROFILE_NAME" 2>> "$MONITOR_LOG" &
        echo $! > "$PID_FILE"
        log "INFO" "OBS started via CLI (PID: $(cat "$PID_FILE"))"
    else
        # Launch OBS directly - it auto-loads the last profile via config
        "$OBS_BIN" --profile "$OBS_PROFILE_NAME" --collection "DavidDailyShow" &>> "$MONITOR_LOG" &
        echo $! > "$PID_FILE"
        log "INFO" "OBS launched directly $(cat "$PID_FILE")"
    fi

    # Wait for OBS to initialize
    echo -ne "${BLUE}Waiting for OBS to initialize${NC}"
    local wait_count=0
    while [[ $wait_count -lt $OBS_STARTUP_WAIT ]]; do
        sleep 1
        echo -ne "${BLUE}.${NC}"
        ((wait_count++))

        # Check if process is still alive
        if [[ -f "$PID_FILE" ]]; then
            local pid
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
            if [[ "$pid" != "0" ]] && ! kill -0 "$pid" 2>/dev/null; then
                log "ERROR" "OBS process died during startup!"
                echo -e "\n${RED}✗ OBS crashed on startup${NC}"
                return 1
            fi
        fi
    done
    echo ""

    # Verify OBS started
    if pgrep -f "OBS.app" &>/dev/null; then
        log "SUCCESS" "OBS Studio started successfully"
        echo -e "${GREEN}✓ OBS Studio is running${NC}"
        notify "OBS is running - ready for David Daily Show"

        # Wait additional time for encoder to initialize
        sleep 5

        # Auto-start streaming if CLI available
        if $HAS_OBS_CLI; then
            start_obs_streaming_cli
        fi
    else
        log "ERROR" "OBS Studio failed to start"
        echo -e "${RED}✗ OBS Studio failed to start. Check logs: ${MONITOR_LOG}${NC}"
    fi
}

start_obs_streaming_cli() {
    echo -e "${BLUE}→ Starting OBS streaming...${NC}"

    if command -v obs-cli &>/dev/null; then
        obs-cli start-stream 2>> "$MONITOR_LOG" && {
            log "LIVE" "OBS streaming started!"
            echo -e "${GREEN}${BOLD}🔴 OBS is STREAMING${NC}"
        } || log "WARN" "Could not auto-start stream via CLI. Start manually in OBS."
    else
        log "INFO" "OBS started. Please configure streaming manually in OBS."
        echo -e "${YELLOW}⚠ Please set up StreamYard as streaming destination in OBS${NC}"
    fi
}

# =============================================================================
# START STREAMYARD
# =============================================================================

start_streamyard() {
    echo -e "\n${BOLD}【4/6】Opening StreamYard...${NC}\n"

    log "INFO" "Opening StreamYard in browser: ${STREAMYARD_URL}"
    echo -e "${BLUE}→ Opening StreamYard in Chrome...${NC}"

    # Try to open in Chrome first (better WebRTC support), then fallback to default
    local opened=false

    if [[ -a "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
        open -a "Google Chrome" "$STREAMYARD_URL" 2>/dev/null && opened=true
    elif [[ -a "/Applications/Chromium.app/Contents/MacOS/Chromium" ]]; then
        open -a "Chromium" "$STREAMYARD_URL" 2>/dev/null && opened=true
    fi

    if ! $opened; then
        open "$STREAMYARD_URL" 2>/dev/null && opened=true || {
            log "ERROR" "Could not open StreamYard URL"
            echo -e "${RED}✗ Failed to open StreamYard${NC}"
            return 1
        }
    fi

    # Wait for page to load
    sleep 8
    log "SUCCESS" "StreamYard opened in browser"
    echo -e "${GREEN}✓ StreamYard broadcast page loaded${NC}"
    notify "StreamYard is open - configure your broadcast!"
}

# =============================================================================
# START LOCAL RECORDING (BACKUP)
# =============================================================================

start_local_recording() {
    echo -e "\n${BOLD}【5/6】Starting local backup recording with ffmpeg...${NC}\n"

    if ! command -v ffmpeg &>/dev/null; then
        log "WARN" "ffmpeg not available - skipping local backup recording"
        echo -e "${RED}✗ Cannot record backup without ffmpeg${NC}"
        return 1
    fi

    # Construct the ffmpeg command
    log "INFO" "Recording output: ${LOCAL_RECORDING}"
    log "INFO" "Input: screen capture at ${FFMPEG_RESOLUTION}@${FFMPEG_FRAMERATE}fps"

    # FFmpeg command for macOS screen + audio capture
    # Uses avfoundation for macOS capture
    # Screen input index typically 0:, audio input index typically :0
    echo -e "${CYAN}FFmpeg Command:${NC}"
    echo -e "${CYAN}ffmpeg -f avfoundation -framerate ${FFMPEG_FRAMERATE} \\"
    echo -e "  -video_size ${FFMPEG_RESOLUTION} \\"
    echo -e "  -i \"${FFMPEG_INPUT}:default\" \\"
    echo -e "  -c:v ${FFMPEG_CODEC} -preset ${FFMPEG_PRESET} \\"
    echo -e "  -profile:v ${FFMPEG_PROFILE} -level ${FFMPEG_LEVEL} \\"
    echo -e "  -b:v ${FFMPEG_VIDEO_BITRATE} -maxrate ${FFMPEG_VIDEO_BITRATE} \\"
    echo -e "  -bufsize 12000k -pix_fmt yuv420p -g $((FFMPEG_FRAMERATE * 2)) \\"
    echo -e "  -c:a aac -b:a ${FFMPEG_AUDIO_BITRATE} -ar 48000 -ac 2 \\"
    echo -e "  -movflags +faststart \\"
    echo -e "  \"${LOCAL_RECORDING}\"${NC}"
    echo ""

    # Start ffmpeg in background
    ffmpeg -f avfoundation \
        -framerate "$FFMPEG_FRAMERATE" \
        -video_size "$FFMPEG_RESOLUTION" \
        -i "${FFMPEG_INPUT}:default" \
        -c:v "$FFMPEG_CODEC" \
        -preset "$FFMPEG_PRESET" \
        -profile:v "$FFMPEG_PROFILE" \
        -level "$FFMPEG_LEVEL" \
        -b:v "$FFMPEG_VIDEO_BITRATE" \
        -maxrate "$FFMPEG_VIDEO_BITRATE" \
        -bufsize 12000k \
        -pix_fmt yuv420p \
        -g $((FFMPEG_FRAMERATE * 2)) \
        -c:a aac \
        -b:a "$FFMPEG_AUDIO_BITRATE" \
        -ar 48000 \
        -ac 2 \
        -movflags +faststart \
        "$LOCAL_RECORDING" \
        >> "${RECORDING_DIR}/ffmpeg-${TIMESTAMP}.log" 2>&1 &

    local ffmpeg_pid=$!
    echo "$ffmpeg_pid" > "/tmp/golive-ffmpeg-${TIMESTAMP}.pid"
    log "INFO" "FFmpeg recording started (PID: ${ffmpeg_pid})"

    # Wait briefly and check if recording started
    sleep 3
    if kill -0 "$ffmpeg_pid" 2>/dev/null; then
        if [[ -f "$LOCAL_RECORDING" ]]; then
            local file_size
            file_size=$(du -h "$LOCAL_RECORDING" 2>/dev/null | cut -f1 || echo "unknown")
            log "SUCCESS" "Local backup recording started. File size: ${file_size}"
            echo -e "${GREEN}✓ Recording backup active → ${LOCAL_RECORDING}${NC}"
        else
            log "WARN" "FFmpeg running but output file not yet created"
            echo -e "${YELLOW}⚠ Recording starting...${NC}"
        fi
    else
        log "ERROR" "FFmpeg exited immediately. Check: ${RECORDING_DIR}/ffmpeg-${TIMESTAMP}.log"
        echo -e "${RED}✗ Recording failed to start${NC}"
    fi
}

# =============================================================================
# STREAM MONITORING
# =============================================================================

monitor_stream() {
    echo -e "\n${BOLD}【6/6】Stream monitoring active...${NC}\n"
    echo -e "${CYAN}The script will monitor stream health and auto-restart if needed.${NC}"
    echo -e "${CYAN}Press Ctrl+C to stop monitoring and trigger post-stream workflow.${NC}\n"

    log "LIVE" "=== STREAM IS LIVE ==="
    notify "🔴 The David Daily Show is LIVE!"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  🔴 THE DAVID DAILY SHOW IS NOW LIVE!            ${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BLUE}Local Recording:${NC} ${LOCAL_RECORDING}"
    echo -e "  ${BLUE}OBS PID:${NC} $(cat "$PID_FILE" 2>/dev/null || echo 'N/A')"
    echo -e "  ${BLUE}FFmpeg PID:${NC} $(cat "/tmp/golive-ffmpeg-${TIMESTAMP}.pid" 2>/dev/null || echo 'N/A')"
    echo -e "  ${BLUE}Monitor Log:${NC} ${MONITOR_LOG}"
    echo ""
    echo -e "  ${YELLOW}Monitoring every ${MONITOR_INTERVAL}s | Auto-restart: ${RESTART_ATTEMPTS}x${NC}"
    echo ""

    local check_count=0
    local restart_count=0

    # Store the start epoch for duration calculation
    local stream_start_epoch
    stream_start_epoch=$(date +%s)

    # Trap to handle Ctrl+C gracefully
    trap cleanup_stream INT TERM

    # Main monitoring loop
    while true; do
        ((check_count++))
        sleep "$MONITOR_INTERVAL"

        # Check OBS status
        local obs_alive=false
        if $HAS_OBS && [[ -f "$PID_FILE" ]]; then
            local obs_pid
            obs_pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
            if [[ "$obs_pid" != "0" ]] && kill -0 "$obs_pid" 2>/dev/null; then
                obs_alive=true
            fi
        fi

        # Check FFmpeg recording status
        local ffmpeg_alive=false
        local ffmpeg_pid_file="/tmp/golive-ffmpeg-${TIMESTAMP}.pid"
        if [[ -f "$ffmpeg_pid_file" ]]; then
            local ffmpeg_pid
            ffmpeg_pid=$(cat "$ffmpeg_pid_file" 2>/dev/null || echo "0")
            if [[ "$ffmpeg_pid" != "0" ]] && kill -0 "$ffmpeg_pid" 2>/dev/null; then
                ffmpeg_alive=true
            fi
        fi

        # Calculate stream duration
        local current_epoch
        current_epoch=$(date +%s)
        local duration=$(( current_epoch - stream_start_epoch ))
        local duration_formatted
        duration_formatted=$(printf '%02d:%02d:%02d' $((duration/3600)) $((duration%3600/60)) $((duration%60)))

        # Status line
        local status_indicator="${GREEN}●${NC}"
        $obs_alive || $ffmpeg_alive || status_indicator="${RED}○${NC}"

        echo -ne "\r  ${status_indicator} Monitoring [${duration_formatted}] Check #${check_count} | OBS: ${obs_alive} | Rec: ${ffmpeg_alive}    "

        # Log status periodically (every 60 checks = ~10 minutes)
        if (( check_count % 60 == 0 )); then
            log "INFO" "Health check #${check_count} | Duration: ${duration_formatted} | OBS: ${obs_alive} | Recording: ${ffmpeg_alive}"
        fi

        # Auto-restart logic for FFmpeg if it dies
        if ! $ffmpeg_alive && [[ -f "$ffmpeg_pid_file" ]]; then
            log "WARN" "FFmpeg recording dropped! Attempting restart..."
            echo -e "\n${YELLOW}⚠ Recording dropped! Restarting...${NC}"

            if (( restart_count < RESTART_ATTEMPTS )); then
                ((restart_count++))
                log "INFO" "Restart attempt ${restart_count}/${RESTART_ATTEMPTS}"

                sleep "$RESTART_COOLDOWN"

                # Restart FFmpeg
                start_local_recording
                echo -e "${GREEN}✓ Recording restarted (${restart_count}/${RESTART_ATTEMPTS})${NC}"
            else
                log "ERROR" "Max restart attempts reached. Recording stopped."
                echo -e "${RED}✗ Recording permanently failed after ${RESTART_ATTEMPTS} attempts${NC}"
            fi
        fi

        # Auto-restart logic for OBS if it dies
        if $HAS_OBS && ! $obs_alive && [[ -f "$PID_FILE" ]]; then
            local current_pid
            current_pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
            if [[ "$current_pid" != "0" ]] && ! kill -0 "$current_pid" 2>/dev/null; then
                log "WARN" "OBS process died! Attempting restart..."
                echo -e "\n${YELLOW}⚠ OBS dropped! Restarting...${NC}"

                if (( restart_count < RESTART_ATTEMPTS )); then
                    ((restart_count++))
                    sleep "$RESTART_COOLDOWN"
                    start_obs
                else
                    log "ERROR" "OBS max restart attempts reached."
                    echo -e "${RED}✗ OBS permanently failed${NC}"
                fi
            fi
        fi
    done
}

# =============================================================================
# CLEANUP & POST-STREAM WORKFLOW
# =============================================================================

cleanup_stream() {
    echo ""
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  Stream ended - running post-stream workflow...${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    log "INFO" "=== STREAM ENDED BY USER ==="
    notify "Stream ended - starting post-stream workflow"

    # Stop FFmpeg recording gracefully
    stop_ffmpeg_recording

    # Stop OBS streaming
    stop_obs

    # Run post-stream workflow
    post_stream_workflow

    # Final notification
    notify "✅ Post-stream workflow complete! Files on DATA TAXI."

    echo -e "\n${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}${BOLD}  ✓ POST-STREAM WORKFLOW COMPLETE                  ${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════${NC}"
    echo ""

    exit 0
}

stop_ffmpeg_recording() {
    echo -e "${BLUE}→ Stopping local recording...${NC}"

    local ffmpeg_pid_file="/tmp/golive-ffmpeg-${TIMESTAMP}.pid"
    if [[ -f "$ffmpeg_pid_file" ]]; then
        local ffmpeg_pid
        ffmpeg_pid=$(cat "$ffmpeg_pid_file" 2>/dev/null || echo "0")
        if [[ "$ffmpeg_pid" != "0" ]]; then
            # Send 'q' to ffmpeg for graceful shutdown
            kill -SIGINT "$ffmpeg_pid" 2>/dev/null || true
            sleep 2
            # If still running, force kill
            if kill -0 "$ffmpeg_pid" 2>/dev/null; then
                kill -9 "$ffmpeg_pid" 2>/dev/null || true
            fi
            log "INFO" "FFmpeg stopped (PID: ${ffmpeg_pid})"
        fi
        rm -f "$ffmpeg_pid_file" 2>/dev/null
    fi

    # Also kill any lingering ffmpeg processes related to this session
    pkill -f "golive-ffmpeg-${TIMESTAMP}" 2>/dev/null || true

    # Verify the recording file exists
    if [[ -f "$LOCAL_RECORDING" ]]; then
        local file_size
        file_size=$(du -h "$LOCAL_RECORDING" | cut -f1)
        log "SUCCESS" "Recording saved: ${LOCAL_RECORDING} (${file_size})"
        echo -e "${GREEN}✓ Recording saved (${file_size})${NC}"
    else
        log "WARN" "Recording file not found: ${LOCAL_RECORDING}"
    fi
}

stop_obs() {
    echo -e "${BLUE}→ Stopping OBS...${NC}"

    if $HAS_OBS_CLI && command -v obs-cli &>/dev/null; then
        obs-cli stop-stream 2>/dev/null || true
        log "INFO" "OBS streaming stopped via CLI"
    elif [[ -f "$PID_FILE" ]]; then
        local obs_pid
        obs_pid=$(cat "$PID_FILE" 2>/dev/null || echo "0")
        if [[ "$obs_pid" != "0" ]] && kill -0 "$obs_pid" 2>/dev/null; then
            kill "$obs_pid" 2>/dev/null || true
        fi
        rm -f "$PID_FILE" 2>/dev/null
    fi

    if pgrep -f "OBS.app" &>/dev/null; then
        pkill -f "OBS.app" 2>/dev/null || true
    fi

    log "SUCCESS" "OBS stopped"
    echo -e "${GREEN}✓ OBS stopped${NC}"
}

# =============================================================================
# POST-STREAM WORKFLOW
# =============================================================================

post_stream_workflow() {
    echo -e "\n${BOLD}[Post-Stream] Starting automated post-stream workflow...${NC}\n"

    # Step 1: Download StreamYard recording
    download_streamyard_recording

    # Step 2: Move files to DATA TAXI
    organize_files

    # Step 3: Trigger podcast workflow
    trigger_podcast_workflow
}

download_streamyard_recording() {
    echo -e "${BLUE}→ Attempting to download StreamYard recording...${NC}"

    if ! $HAS_YTDLP; then
        log "INFO" "yt-dlp not available. Please manually download StreamYard recording."
        echo -e "${YELLOW}⚠ Please download StreamYard recording manually from:${NC}"
        echo -e "${YELLOW}  https://streamyard.com/dashboard → Past Broadcasts → Download${NC}"
        echo ""
        read -rp "Enter path to downloaded recording (or skip): " manual_path

        if [[ -n "$manual_path" && -f "$manual_path" ]]; then
            mv "$manual_path" "${DATA_TAXI}/recordings/"
            log "SUCCESS" "Manual recording saved to DATA TAXI: ${DATA_TAXI}/recordings/"
            echo -e "${GREEN}✓ Manual recording accepted${NC}"
        else
            log "WARN" "No manual recording provided. Skipping to local backup."
        fi
        return 0
    fi

    # Try to download from StreamYard
    local streamyard_download="${RECORDING_DIR}/DDS-STREAMYARD-${TIMESTAMP}.mp4"
    local streamyard_downloaded=false

    # Prompt user for the actual StreamYard broadcast/ recording URL
    echo -e "${CYAN}To auto-download your StreamYard recording, provide the broadcast URL.${NC}"
    read -rp "StreamYard broadcast/recording URL (or press Enter to skip): " sy_url

    if [[ -n "$sy_url" ]]; then
        echo -e "${BLUE}→ Downloading StreamYard recording...${NC}"
        if yt-dlp --output "${streamyard_download}" --no-playlist "$sy_url" 2>> "$MONITOR_LOG"; then
            streamyard_downloaded=true
            log "SUCCESS" "StreamYard recording downloaded: ${streamyard_download}"
            echo -e "${GREEN}✓ StreamYard recording downloaded${NC}"

            local file_size
            file_size=$(du -h "$streamyard_download" | cut -f1)
            echo -e "${GREEN}  Size: ${file_size}${NC}"
        else
            log "WARN" "StreamYard download failed. Using local backup."
            echo -e "${YELLOW}⚠ Download failed. Using local recording as source.${NC}"
        fi
    else
        log "INFO" "No StreamYard URL provided. Using local recording backup."
    fi

    # Set the source file for the workflow
    if [[ "$streamyard_downloaded" == true && -f "$streamyard_download" ]]; then
        WORKFLOW_SOURCE_FILE="$streamyard_download"
    elif [[ -f "$LOCAL_RECORDING" ]]; then
        WORKFLOW_SOURCE_FILE="$LOCAL_RECORDING"
        log "INFO" "Using local backup recording as workflow input"
    else
        log "ERROR" "No recording available for workflow"
        echo -e "${RED}✗ No recording available for podcast workflow${NC}"
        return 1
    fi

    echo -e "${GREEN}→ Workflow source: ${WORKFLOW_SOURCE_FILE}${NC}"
}

organize_files() {
    echo -e "${BLUE}→ Organizing files on DATA TAXI...${NC}"

    local episode_dir="${DATA_TAXI}/episodes/episode-$(date +%Y%m%d)"
    mkdir -p "$episode_dir"

    # Move local recording
    if [[ -f "$LOCAL_RECORDING" ]]; then
        local dest_file="${episode_dir}/DDS-LOCAL-BACKUP-${TIMESTAMP}.mp4"
        cp "$LOCAL_RECORDING" "$dest_file"
        log "INFO" "Local recording copied to: ${dest_file}"
    fi

    # Ensure the primary source file is in the episode directory
    if [[ -n "${WORKFLOW_SOURCE_FILE:-}" && -f "${WORKFLOW_SOURCE_FILE}" ]]; then
        local base_name
        base_name=$(basename "$WORKFLOW_SOURCE_FILE")
        if [[ "${WORKFLOW_SOURCE_FILE}" != "${episode_dir}/${base_name}" ]]; then
            cp "$WORKFLOW_SOURCE_FILE" "${episode_dir}/${base_name}" 2>/dev/null || true
        fi
        log "INFO" "Files organized in: ${episode_dir}"
    fi

    echo -e "${GREEN}✓ Files organized in: ${episode_dir}${NC}"
}

trigger_podcast_workflow() {
    echo -e "${BLUE}→ Triggering podcast-workflow.sh...${NC}"

    local workflow_script="${SCRIPTS_DIR}/podcast-workflow.sh"

    if [[ ! -f "$workflow_script" ]]; then
        log "ERROR" "podcast-workflow.sh not found at: ${workflow_script}"
        echo -e "${RED}✗ podcast-workflow.sh not found${NC}"
        return 1
    fi

    chmod +x "$workflow_script"

    # Run the podcast workflow with the recording file
    if [[ -n "${WORKFLOW_SOURCE_FILE:-}" && -f "${WORKFLOW_SOURCE_FILE}" ]]; then
        log "INFO" "Running podcast workflow on: ${WORKFLOW_SOURCE_FILE}"

        # Run in a subshell or with user confirmation
        echo -e "${CYAN}Run podcast-workflow.sh with the recording?${NC}"
        echo -e "${CYAN}Source: ${WORKFLOW_SOURCE_FILE}${NC}"
        read -rp "Execute workflow now? (Y/n) " run_choice

        if [[ ! "$run_choice" =~ ^[Nn]$ ]]; then
            cd "$SCRIPTS_DIR" && bash "$workflow_script" "$WORKFLOW_SOURCE_FILE" --verbose 2>&1 | tee -a "$MONITOR_LOG"
            log "SUCCESS" "Podcast workflow completed"
            echo -e "${GREEN}✓ Podcast workflow completed${NC}"
        else
            log "INFO" "Podcast workflow deferred"
            echo -e "${YELLOW}Workflow skipped. Run manually:${NC}"
            echo -e "${YELLOW}  ./podcast-workflow.sh ${WORKFLOW_SOURCE_FILE}${NC}"
        fi
    else
        log "WARN" "No source file available for workflow"
        echo -e "${YELLOW}⚠ No recording available for workflow${NC}"
    fi
}

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

main() {
    init
    check_tools
    check_data_taxi
    start_obs
    start_streamyard
    start_local_recording
    monitor_stream
}

# Run if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

