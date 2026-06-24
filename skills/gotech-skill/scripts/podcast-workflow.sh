#!/usr/bin/env bash
#
# Podcast-to-YouTube Automation Workflow
# ========================================
# Automates the pipeline: recording -> editing -> YouTube upload -> Shorts extraction
#
# Usage:
#   ./podcast-workflow.sh <video_file_or_youtube_url> [options]
#   ./podcast-workflow.sh --help
#
# Options:
#   --demo              Run in demo mode (no actual uploads/API calls)
#   --shorts-only       Only extract shorts (skip full upload)
#   --upload-only       Only upload (skip processing)
#   --skip-short        Skip shorts extraction
#   --config <file>     Use custom config file
#   --dry-run           Show what would be done without executing
#   --help              Show this help message
#
# Requirements: ffmpeg, yt-dlp (optional), imagemagick (optional)
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

# --- Paths ---
BASE_DIR="${HOME}/Documents/GoTechSolutions/startup"
OUTPUT_DIR="${BASE_DIR}/output"
AUDIO_DIR="${BASE_DIR}/output/audio"
CLIPS_DIR="${BASE_DIR}/output/shorts"
LOGS_DIR="${BASE_DIR}/output/logs"
METADATA_DIR="${BASE_DIR}/output/metadata"

# --- Processing ---
MAX_SHORTS=5                          # Maximum number of shorts to extract
CLIP_DURATION=60                      # Duration of each short in seconds
CLIP_RESOLUTION="1080x1920"           # Vertical video for Shorts
AUDIO_BITRATE="192k"                  # Audio extraction bitrate
SILENCE_THRESHOLD="-40dB"             # Silence detection threshold
SILENCE_DURATION="1.0"                # Minimum silence duration for chapter breaks
MIN_SEGMENT_DURATION=30               # Minimum segment duration in seconds

# --- YouTube Upload ---
YOUTUBE_CATEGORY="24"                  # Entertainment
YOUTUBE_PRIVACY="private"             # private, unlisted, public
YOUTUBE_TAGS="podcast,tech,startup"   # Default tags
YOUTUBE_DESCRIPTION_TEMPLATE="Episode auto-generated from podcast recording."

# --- Social Media ---
LINKEDIN_WEBHOOK_URL="${LINKEDIN_WEBHOOK_URL:-}"
FACEBOOK_PAGE_TOKEN="${FACEBOOK_PAGE_TOKEN:-}"
FACEBOOK_PAGE_ID="${FACEBOOK_PAGE_ID:-}"
TWITTER_BEARER_TOKEN="${TWITTER_BEARER_TOKEN:-}"
TWITTER_API_KEY="${TWITTER_API_KEY:-}"
TWITTER_API_SECRET="${TWITTER_API_SECRET:-}"

# --- Branding ---
CAPTION_TEXT="THE DAVID DAILY SHOW"
CAPTION_FONT_COLOR="white"
CAPTION_FONT_BORDER="black"
CAPTION_FONT_SIZE="42"
BRAND_COLOR="#FF6600"

# --- Behavior ---
DEMO_MODE=false
DRY_RUN=false
VERBOSE=false
SKIP_SHORTS=false
SHORTS_ONLY=false
UPLOAD_ONLY=false
INPUT_SOURCE=""
CONFIG_FILE=""

# --- Logging ---
LOG_FILE=""
TIMESTAMP_FORMAT="+%Y-%m-%d %H:%M:%S"

# =============================================================================
# INITIALIZATION
# =============================================================================

init() {
    mkdir -p "$OUTPUT_DIR" "$AUDIO_DIR" "$CLIPS_DIR" "$LOGS_DIR" "$METADATA_DIR"
    LOG_FILE="${LOGS_DIR}/podcast-workflow-$(date +%Y%m%d-%H%M%S).log"
    touch "$LOG_FILE"
    log "INFO" "=== Podcast Workflow Started ==="
    log "INFO" "Output directory: ${OUTPUT_DIR}"
    log "INFO" "Log file: ${LOG_FILE}"
}

# =============================================================================
# LOGGING FUNCTIONS
# =============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date "$TIMESTAMP_FORMAT")
    local log_line="[${timestamp}] [${level}] ${message}"
    
    echo "$log_line" >> "$LOG_FILE"
    
    case "$level" in
        ERROR)   echo -e "\033[31m${log_line}\033[0m" ;;
        WARN)    echo -e "\033[33m${log_line}\033[0m" ;;
        SUCCESS) echo -e "\033[32m${log_line}\033[0m" ;;
        INFO)    echo "$log_line" ;;
        DEBUG)   [[ "$VERBOSE" == true ]] && echo -e "\033[36m${log_line}\033[0m" ;;
    esac
}

log_separator() {
    log "INFO" "────────────────────────────────────────"
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

check_tool() {
    local tool="$1"
    local required="$2"
    local install_hint="$3"
    
    if command -v "$tool" &>/dev/null; then
        local version
        version=$("$tool" --version 2>&1 | head -1 || echo "unknown")
        log "DEBUG" "Found ${tool}: ${version}"
        return 0
    else
        if [[ "$required" == "required" ]]; then
            log "ERROR" "${tool} is required but not found. Install: ${install_hint}"
            return 1
        else
            log "WARN" "${tool} not found (optional). Install: ${install_hint}"
            return 2
        fi
    fi
}

check_tool_version() {
    local tool="$1"
    if command -v "$tool" &>/dev/null; then
        return 0
    fi
    return 1
}

duration_to_seconds() {
    local duration="$1"
    local hours minutes seconds
    IFS=: read -r hours minutes seconds <<< "$duration"
    echo $(( 10#$hours * 3600 + 10#$minutes * 60 + 10#$seconds ))
}

seconds_to_duration() {
    local total_seconds="$1"
    local hours=$(( total_seconds / 3600 ))
    local minutes=$(( (total_seconds % 3600) / 60 ))
    local seconds=$(( total_seconds % 60 ))
    printf "%02d:%02d:%02d" "$hours" "$minutes" "$seconds"
}

sanitize_filename() {
    local name="$1"
    echo "$name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//'
}

generate_id() {
    date +%Y%m%d-%H%M%S
}

# =============================================================================
# SETUP & PREREQUISITES CHECK
# =============================================================================

check_prerequisites() {
    log_separator
    log "INFO" "Checking prerequisites..."
    
    local errors=0
    
    # Required tools
    check_tool "ffmpeg" "required" "brew install ffmpeg" || ((errors++))
    check_tool "ffprobe" "required" "brew install ffmpeg" || ((errors++))
    
    # Optional tools
    check_tool "yt-dlp" "optional" "brew install yt-dlp" || true
    check_tool "convert" "optional" "brew install imagemagick" || true
    check_tool "jq" "optional" "brew install jq" || true
    check_tool "curl" "optional" "system provided" || true
    
    # Check ffmpeg capabilities
    if command -v ffmpeg &>/dev/null; then
        if ffmpeg -filters 2>/dev/null | grep -q "silencedetect"; then
            log "DEBUG" "ffmpeg has silencedetect filter"
        else
            log "WARN" "ffmpeg missing silencedetect filter"
        fi
        
        if ffmpeg -filters 2>/dev/null | grep -q "drawtext"; then
            log "DEBUG" "ffmpeg has drawtext filter"
        else
            log "WARN" "ffmpeg missing drawtext filter (captions will be skipped)"
        fi
    fi
    
    if [[ $errors -gt 0 ]]; then
        log "ERROR" "Missing ${errors} required tool(s). Please install and retry."
        exit 1
    fi
    
    log "SUCCESS" "Prerequisites check passed"
}

# =============================================================================
# ARGUMENT PARSING
# =============================================================================

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --demo)
                DEMO_MODE=true
                log "INFO" "Demo mode enabled"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                log "INFO" "Dry-run mode enabled"
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --shorts-only)
                SHORTS_ONLY=true
                shift
                ;;
            --upload-only)
                UPLOAD_ONLY=true
                shift
                ;;
            --skip-shorts)
                SKIP_SHORTS=true
                shift
                ;;
            --config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                log "ERROR" "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$INPUT_SOURCE" ]]; then
                    INPUT_SOURCE="$1"
                else
                    log "ERROR" "Unexpected argument: $1"
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    if [[ -z "$INPUT_SOURCE" ]]; then
        log "ERROR" "No input source provided"
        show_help
        exit 1
    fi
    
    # Load custom config if specified
    if [[ -n "$CONFIG_FILE" && -f "$CONFIG_FILE" ]]; then
        log "INFO" "Loading config from: ${CONFIG_FILE}"
        # shellcheck source=/dev/null
        source "$CONFIG_FILE"
    fi
}

show_help() {
    head -30 "$0" | grep '^#' | sed 's/^#//' | sed 's/^!//'
}

# =============================================================================
# STEP 1: INPUT HANDLING & DOWNLOAD
# =============================================================================

is_youtube_url() {
    local input="$1"
    if [[ "$input" =~ ^https?://(www\.)?(youtube\.com|youtu\.be) ]]; then
        return 0
    fi
    return 1
}

is_streamyard_url() {
    local input="$1"
    if [[ "$input" =~ ^https?://(www\.)?streamyard\.com ]]; then
        return 0
    fi
    return 1
}

download_youtube_video() {
    local url="$1"
    local output_file="$2"
    
    log "INFO" "Downloading YouTube video: ${url}"
    
    if ! check_tool_version "yt-dlp"; then
        log "ERROR" "yt-dlp is required to download YouTube videos"
        log "INFO" "Install with: brew install yt-dlp"
        return 1
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would download: ${url} -> ${output_file}"
        return 0
    fi
    
    local download_opts=(
        --format "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        --merge-output-format mp4
        --output "$output_file"
        --no-playlist
        --no-warnings
    )
    
    if [[ "$DEMO_MODE" == true ]]; then
        log "INFO" "[DEMO] Simulating download..."
        touch "$output_file"
        return 0
    fi
    
    if yt-dlp "${download_opts[@]}" "$url" 2>> "$LOG_FILE"; then
        log "SUCCESS" "Download complete: ${output_file}"
        return 0
    else
        log "ERROR" "Download failed for: ${url}"
        return 1
    fi
}

resolve_input() {
    local input="$1"
    local episode_id
    episode_id=$(generate_id)
    
    EPISODE_ID="$episode_id"
    EPISODE_DIR="${OUTPUT_DIR}/${episode_id}"
    mkdir -p "$EPISODE_DIR"
    
    log_separator
    log "INFO" "Step 1: Resolving input source"
    log "INFO" "Episode ID: ${episode_id}"
    
    if is_youtube_url "$input"; then
        EPISODE_TYPE="youtube"
        EPISODE_URL="$input"
        EPISODE_VIDEO="${EPISODE_DIR}/full-video.mp4"
        
        log "INFO" "Input type: YouTube URL"
        download_youtube_video "$input" "$EPISODE_VIDEO" || exit 1
        
    elif is_streamyard_url "$input"; then
        EPISODE_TYPE="streamyard"
        EPISODE_URL="$input"
        EPISODE_VIDEO="${EPISODE_DIR}/full-video.mp4"
        
        log "INFO" "Input type: StreamYard URL"
        log "WARN" "StreamYard recordings may require manual download"
        download_youtube_video "$input" "$EPISODE_VIDEO" || {
            log "WARN" "Could not auto-download StreamYard URL"
            log "INFO" "Please manually place the video at: ${EPISODE_VIDEO}"
            exit 1
        }
        
    elif [[ -f "$input" ]]; then
        EPISODE_TYPE="local"
        EPISODE_URL=""
        EPISODE_VIDEO="$input"
        
        log "INFO" "Input type: Local file"
        log "INFO" "File: ${input}"
        log "INFO" "Size: $(du -h "$input" | cut -f1)"
        
        # Validate video file
        if ! ffprobe -v quiet "$input" 2>/dev/null; then
            log "ERROR" "Invalid or corrupted video file: ${input}"
            exit 1
        fi
    else
        log "ERROR" "Input not found: ${input}"
        exit 1
    fi
    
    # Get video info
    VIDEO_DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$EPISODE_VIDEO" 2>/dev/null || echo "0")
    VIDEO_WIDTH=$(ffprobe -v quiet -select_streams v:0 -show_entries stream=width -of csv=p=0 "$EPISODE_VIDEO" 2>/dev/null || echo "0")
    VIDEO_HEIGHT=$(ffprobe -v quiet -select_streams v:0 -show_entries stream=height -of csv=p=0 "$EPISODE_VIDEO" 2>/dev/null || echo "0")
    
    log "INFO" "Duration: $(seconds_to_duration "${VIDEO_DURATION%.*}")"
    log "INFO" "Resolution: ${VIDEO_WIDTH}x${VIDEO_HEIGHT}"
}

# =============================================================================
# STEP 2: AUDIO EXTRACTION
# =============================================================================

extract_audio() {
    log_separator
    log "INFO" "Step 2: Extracting audio"
    
    EPISODE_AUDIO="${EPISODE_DIR}/audio.wav"
    EPISODE_AUDIO_MP3="${EPISODE_DIR}/audio.mp3"
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would extract audio from ${EPISODE_VIDEO}"
        return 0
    fi
    
    # Extract WAV for analysis
    log "INFO" "Extracting WAV for analysis..."
    if ffmpeg -y -i "$EPISODE_VIDEO" -vn -acodec pcm_s16le -ar 16000 -ac 1 "$EPISODE_AUDIO" 2>> "$LOG_FILE"; then
        log "SUCCESS" "WAV audio extracted: ${EPISODE_AUDIO}"
    else
        log "ERROR" "Audio extraction (WAV) failed"
        return 1
    fi
    
    # Extract MP3 for publishing
    log "INFO" "Extracting MP3 for publishing..."
    if ffmpeg -y -i "$EPISODE_VIDEO" -vn -acodec libmp3lame -b:a "$AUDIO_BITRATE" "$EPISODE_AUDIO_MP3" 2>> "$LOG_FILE"; then
        log "SUCCESS" "MP3 audio extracted: ${EPISODE_AUDIO_MP3}"
    else
        log "WARN" "MP3 extraction failed (non-fatal)"
    fi
}

# =============================================================================
# STEP 3: TIMESTAMPS / CHAPTER GENERATION
# =============================================================================

generate_chapters() {
    log_separator
    log "INFO" "Step 3: Generating chapters/timestamps"
    
    EPISODE_CHAPTERS="${EPISODE_DIR}/chapters.txt"
    EPISODE_CHAPTERS_JSON="${EPISODE_DIR}/chapters.json"
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would detect silence and generate chapters"
        return 0
    fi
    
    # Detect silence points
    log "INFO" "Running silence detection (threshold: ${SILENCE_THRESHOLD})..."
    
    local silence_output
    silence_output=$(ffmpeg -i "$EPISODE_VIDEO" -af silencedetect=noise="${SILENCE_THRESHOLD}":d="${SILENCE_DURATION}" -f null - 2>&1 || true)
    
    # Parse silence endpoints to find chapter boundaries
    local silence_starts=()
    local silence_ends=()
    
    while IFS= read -r line; do
        if [[ "$line" =~ silence_start:\ ([0-9.]+) ]]; then
            silence_starts+=("${BASH_REMATCH[1]}")
        fi
        if [[ "$line" =~ silence_end:\ ([0-9.]+) ]]; then
            silence_ends+=("${BASH_REMATCH[1]}")
        fi
    done <<< "$silence_output"
    
    # Generate chapter markers (use silence midpoints as chapter boundaries)
    local chapters=()
    local last_chapter_end=0
    local chapter_num=1
    
    for i in "${!silence_starts[@]}"; do
        local midpoint
        midpoint=$(echo "scale=2; (${last_chapter_end} + ${silence_starts[$i]}) / 2" | bc 2>/dev/null || echo "${silence_starts[$i]}")
        
        local gap_duration
        if [[ $i -gt 0 ]]; then
            gap_duration=$(echo "scale=2; ${silence_starts[$i]} - ${silence_ends[$((i-1))]:-0}" | bc 2>/dev/null || echo "0")
        else
            gap_duration=0
        fi
        
        # Only create chapter if gap is significant (> 5 seconds)
        if (( $(echo "$gap_duration > 5" | bc -l 2>/dev/null || echo 0) )); then
            local start_time
            start_time=$(seconds_to_duration "${midpoint%.*}")
            chapters+=("${start_time} Chapter ${chapter_num}")
            last_chapter_end="${silence_ends[$i]:-${silence_starts[$i]}}"
            ((chapter_num++))
        fi
    done
    
    # If no chapters detected, create default ones every 5 minutes
    if [[ ${#chapters[@]} -eq 0 ]]; then
        log "WARN" "No silence detected, creating chapters every 5 minutes"
        local total_sec="${VIDEO_DURATION%.*}"
        local interval=300  # 5 minutes
        local current=0
        while [[ $current -lt $total_sec ]]; do
            chapters+=("$(seconds_to_duration "$current") Chapter ${chapter_num}")
            ((current += interval))
            ((chapter_num++))
        done
    fi
    
    # Write chapters to file
    {
        echo "# Chapters for Episode ${EPISODE_ID}"
        echo "# Generated: $(date "$TIMESTAMP_FORMAT")"
        echo "# Source: ${EPISODE_VIDEO}"
        echo ""
        printf '%s\n' "${chapters[@]}"
    } > "$EPISODE_CHAPTERS"
    
    # Write chapters as JSON
    {
        echo "{"
        echo "  \"episode_id\": \"${EPISODE_ID}\","
        echo "  \"title\": \"Episode ${EPISODE_ID}\","
        echo "  \"chapters\": ["
        local first=true
        for chapter in "${chapters[@]}"; do
            local time_part="${chapter%% *}"
            local title_part="${chapter#* }"
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            printf '    {"start": "%s", "title": "%s"}' "$time_part" "$title_part"
        done
        echo ""
        echo "  ]"
        echo "}"
    } > "$EPISODE_CHAPTERS_JSON"
    
    log "SUCCESS" "Generated $((chapter_num - 1)) chapters"
    log "INFO" "Chapters file: ${EPISODE_CHAPTERS}"
}

# =============================================================================
# STEP 4: DETECT BEST SHORTS CLIPS
# =============================================================================

detect_best_clips() {
    log_separator
    log "INFO" "Step 4: Detecting best ${CLIP_DURATION}s clips for Shorts"
    
    EPISODE_CLIPS_LIST="${EPISODE_DIR}/clips.txt"
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would analyze audio energy and select top ${MAX_SHORTS} clips"
        return 0
    fi
    
    # Analyze audio energy levels using ffmpeg ebur128 filter
    log "INFO" "Analyzing audio energy levels..."
    
    local loudness_output
    loudness_output=$(ffmpeg -i "$EPISODE_AUDIO" -af ebur128=peak=true -f null - 2>&1 || true)
    
    # Split audio into segments and measure energy
    local total_duration="${VIDEO_DURATION%.*}"
    local segment_duration=$CLIP_DURATION
    local segments=()
    local energies=()
    
    # Use audio volume detection per segment
    local offset=0
    local segment_idx=0
    local step=15  # Check every 15 seconds
    
    while [[ $((offset + segment_duration)) -le $total_duration ]]; do
        local segment_energy
        segment_energy=$(ffmpeg -ss "$offset" -t "$segment_duration" -i "$EPISODE_AUDIO" -af "volumedetect" -f null - 2>&1 | grep "mean_volume:" | awk '{print $5}' || echo "0")
        
        if [[ -n "$segment_energy" && "$segment_energy" != "0" ]]; then
            segments+=("$offset")
            energies+=("$segment_energy")
            log "DEBUG" "Segment ${offset}s: energy=${segment_energy}dB"
        fi
        
        ((offset += step))
        ((segment_idx++))
    done
    
    # Sort by energy (highest first) and pick top N
    local sorted_indices=()
    if [[ ${#energies[@]} -gt 0 ]]; then
        # Create index-energy pairs and sort
        local pairs=""
        for i in "${!energies[@]}"; do
            pairs+="${i}:${energies[$i]}"$'\n'
        done
        sorted_indices=($(echo "$pairs" | sort -t: -k2 -rn | head -n "$MAX_SHORTS" | cut -d: -f1))
    fi
    
    # If no energy data, pick evenly spaced segments
    if [[ ${#sorted_indices[@]} -eq 0 ]]; then
        log "WARN" "Could not analyze energy, selecting evenly spaced segments"
        local interval=$(( total_duration / (MAX_SHORTS + 1) ))
        for ((i=1; i<=MAX_SHORTS; i++)); do
            local offset=$(( interval * i - segment_duration / 2 ))
            [[ $offset -lt 0 ]] && offset=0
            echo "${offset}" >> "$EPISODE_CLIPS_LIST"
        done
    else
        # Write selected clip start times
        > "$EPISODE_CLIPS_LIST"
        for idx in "${sorted_indices[@]}"; do
            echo "${segments[$idx]}" >> "$EPISODE_CLIPS_LIST"
        done
    fi
    
    local clip_count
    clip_count=$(wc -l < "$EPISODE_CLIPS_LIST")
    log "SUCCESS" "Selected ${clip_count} clips for Shorts"
    log "INFO" "Clips list: ${EPISODE_CLIPS_LIST}"
}

# =============================================================================
# STEP 5: EXPORT CLIPS WITH CAPTIONS
# =============================================================================

export_clips() {
    log_separator
    log "INFO" "Step 5: Exporting clips with burn-in captions"
    
    if [[ ! -f "$EPISODE_CLIPS_LIST" ]]; then
        log "WARN" "No clips list found, skipping clip export"
        return 0
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would export $(wc -l < "$EPISODE_CLIPS_LIST") clips"
        return 0
    fi
    
    local clip_idx=0
    while IFS= read -r start_time; do
        ((clip_idx++))
        local clip_name="short-${EPISODE_ID}-${clip_idx}"
        local clip_output="${CLIPS_DIR}/${clip_name}.mp4"
        local clip_caption="Clip ${clip_idx} | ${CAPTION_TEXT}"
        
        log "INFO" "Exporting clip ${clip_idx}: start=${start_time}s, duration=${CLIP_DURATION}s"
        
        # Build drawtext filter for captions
        local drawtext_filter=""
        if ffmpeg -filters 2>/dev/null | grep -q "drawtext"; then
            drawtext_filter="drawtext=text='${clip_caption}':fontcolor=${CAPTION_FONT_COLOR}:fontsize=${CAPTION_FONT_SIZE}:borderw=2:bordercolor=${CAPTION_FONT_BORDER}:x=(w-text_w)/2:y=h-th-50:enable='lt(t,3)'"
        fi
        
        # Extract and format clip for vertical Shorts
        local filter_complex="[0:v]scale=${CLIP_RESOLUTION}:force_original_aspect_ratio=decrease,pad=${CLIP_RESOLUTION}:(ow-iw)/2:(oh-ih)/2:black${drawtext_filter:+,${drawtext_filter}}[v]"
        
        if ffmpeg -y -ss "$start_time" -t "$CLIP_DURATION" -i "$EPISODE_VIDEO" \
            -filter_complex "$filter_complex" \
            -map "[v]" -map 0:a? \
            -c:v libx264 -preset fast -crf 23 \
            -c:a aac -b:a 128k \
            -movflags +faststart \
            "$clip_output" 2>> "$LOG_FILE"; then
            
            log "SUCCESS" "Clip exported: ${clip_output}"
            
            # Generate thumbnail for each clip
            generate_clip_thumbnail "$clip_output" "${CLIPS_DIR}/${clip_name}-thumb.jpg"
        else
            log "ERROR" "Failed to export clip ${clip_idx}"
        fi
        
    done < "$EPISODE_CLIPS_LIST"
    
    log "SUCCESS" "Exported ${clip_idx} clips to ${CLIPS_DIR}"
}

generate_clip_thumbnail() {
    local video="$1"
    local output="$2"
    
    if [[ "$DRY_RUN" == true ]]; then
        return 0
    fi
    
    # Extract frame at 2 seconds
    ffmpeg -y -ss 2 -i "$video" -frames:v 1 -q:v 2 "$output" 2>/dev/null || true
}

# =============================================================================
# STEP 6: GENERATE SEO METADATA
# =============================================================================

generate_metadata() {
    log_separator
    log "INFO" "Step 6: Generating SEO-optimized metadata"
    
    EPISODE_TITLE="${EPISODE_DIR}/title.txt"
    EPISODE_DESCRIPTION="${EPISODE_DIR}/description.txt"
    EPISODE_TAGS="${EPISODE_DIR}/tags.txt"
    EPISODE_METADATA="${EPISODE_DIR}/metadata.json"
    
    local episode_num
    episode_num=$(date +%j)
    local date_str
    date_str=$(date "+%B %d, %Y")
    
    # Generate title
    cat > "$EPISODE_TITLE" << EOF
The David Daily Show - Episode #${episode_num} | ${date_str}
EOF
    
    # Generate description
    cat > "$EPISODE_DESCRIPTION" << EOF
🎙️ The David Daily Show - Episode #${episode_num}

Published: ${date_str}
Duration: $(seconds_to_duration "${VIDEO_DURATION%.*}")

Description:
Join us for another episode of The David Daily Show where we dive into the latest in tech, startups, and everything in between.

📌 Timestamps:
$(cat "$EPISODE_CHAPTERS" 2>/dev/null | grep -v '^#' | grep -v '^$' || echo "Coming soon")

🔗 Follow us:
• Website: https://gotechsolutions.com
• Twitter: @daviddailyshow
• LinkedIn: /company/gotechsolutions

#TheDavidDailyShow #Podcast #Tech #Startup #Innovation

---
Auto-generated by Podcast Workflow on $(date "$TIMESTAMP_FORMAT")
EOF
    
    # Generate tags
    cat > "$EPISODE_TAGS" << EOF
the david daily show,david daily show,podcast,tech podcast,startup podcast,technology,innovation,entrepreneurship,business podcast,episode ${episode_num},$(date +%Y)
EOF
    
    # Generate full metadata JSON
    cat > "$EPISODE_METADATA" << EOF
{
  "episode_id": "${EPISODE_ID}",
  "title": "The David Daily Show - Episode #${episode_num}",
  "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_seconds": ${VIDEO_DURATION},
  "duration_human": "$(seconds_to_duration "${VIDEO_DURATION%.*}")",
  "type": "${EPISODE_TYPE}",
  "source_url": "${EPISODE_URL}",
  "youtube_category": "${YOUTUBE_CATEGORY}",
  "youtube_privacy": "${YOUTUBE_PRIVACY}",
  "tags": [
    "the david daily show",
    "david daily show",
    "podcast",
    "tech podcast",
    "startup podcast",
    "technology",
    "innovation",
    "entrepreneurship",
    "business podcast"
  ],
  "files": {
    "video": "${EPISODE_VIDEO}",
    "audio_mp3": "${EPISODE_AUDIO_MP3}",
    "chapters": "${EPISODE_CHAPTERS}",
    "clips_dir": "${CLIPS_DIR}",
    "title": "${EPISODE_TITLE}",
    "description": "${EPISODE_DESCRIPTION}",
    "tags": "${EPISODE_TAGS}"
  },
  "shorts_count": $(wc -l < "$EPISODE_CLIPS_LIST" 2>/dev/null || echo 0),
  "workflow_version": "1.0.0"
}
EOF
    
    log "SUCCESS" "Metadata generated"
    log "INFO" "Title: $(cat "$EPISODE_TITLE")"
    log "INFO" "Tags: $(wc -l < "$EPISODE_TAGS") tag(s)"
}

# =============================================================================
# STEP 7: UPLOAD TO YOUTUBE
# =============================================================================

upload_to_youtube() {
    log_separator
    log "INFO" "Step 7: Uploading to YouTube"
    
    if [[ "$DEMO_MODE" == true ]]; then
        log "INFO" "[DEMO] Would upload to YouTube with settings:"
        log "INFO" "  Title: $(cat "$EPISODE_TITLE")"
        log "INFO" "  Category: ${YOUTUBE_CATEGORY}"
        log "INFO" "  Privacy: ${YOUTUBE_PRIVACY}"
        log "INFO" "  File: ${EPISODE_VIDEO}"
        return 0
    fi
    
    if [[ "$DRY_RUN" == true ]]; then
        log "INFO" "[DRY RUN] Would upload to YouTube"
        return 0
    fi
    
    # Check if yt-dlp supports upload
    if check_tool_version "yt-dlp"; then
        log "INFO" "Attempting YouTube upload via yt-dlp..."
        
        # yt-dlp upload (requires browser cookies or OAuth)
        local upload_opts=(
            --title "$(cat "$EPISODE_TITLE")"
            --description "$(cat "$EPISODE_DESCRIPTION")"
            --tags "$(cat "$EPISODE_TAGS" | tr '\n' ',')"
            --category "$YOUTUBE_CATEGORY"
            --privacy "$YOUTUBE_PRIVACY"
            --default-language "en"
        )
        
        # Check for credentials
        if [[ -n "${YOUTUBE_COOKIES_FILE:-}" && -f "$YOUTUBE_COOKIES_FILE" ]]; then
            upload_opts+=(--cookies "$YOUTUBE_COOKIES_FILE")
        elif [[ -n "${YOUTUBE_OAUTH_TOKEN:-}" ]]; then
            upload_opts+=(--username oauth2 --password "$YOUTUBE_OAUTH_TOKEN")
        else
            log "WARN" "No YouTube credentials configured"
            log "INFO" "Set YOUTUBE_COOKIES_FILE or YOUTUBE_OAUTH_TOKEN for auto-upload"
            log "INFO" "Falling back to manual upload preparation..."
            prepare_manual_upload
            return 0
        fi
        
        if yt-dlp upload "${upload_opts[@]}" "$EPISODE_VIDEO" 2>> "$LOG_FILE"; then
            log "SUCCESS" "YouTube upload complete"
        else
            log "WARN" "YouTube upload failed, preparing manual upload..."
            prepare_manual_upload
        fi
    else
        log "INFO" "yt-dlp not available, preparing files for manual upload..."
        prepare_manual_upload
    fi
}

prepare_manual_upload() {
    local upload_dir="${EPISODE_DIR}/upload-ready"
    mkdir -p "$upload_dir"
    
    # Copy all relevant files
    cp "$EPISODE_VIDEO" "$upload_dir/"
    cp "$EPISODE_TITLE" "$upload_dir/"
    cp "$EPISODE_DESCRIPTION" "$upload_dir/"
    cp "$EPISODE_TAGS" "$upload_dir/"
    cp "$EPISODE_CHAPTERS" "$upload_dir/"
    cp "$EPISODE_METADATA" "$upload_dir/"
    
    # Copy shorts
    if [[ -d "$CLIPS_DIR" ]]; then
        mkdir -p "$upload_dir/shorts"
        cp "$CLIPS_DIR"/short-"${EPISODE_ID}"-* "$upload_dir/shorts/" 2>/dev/null || true
    fi
    
    log "SUCCESS" "Files prepared for manual upload: ${upload_dir}"
    log "INFO" "Upload folder contents:"
    ls -la "$upload_dir" >> "$LOG_FILE" 2>&1
}

# =============================================================================
# STEP 8: SOCIAL MEDIA POSTING
# =============================================================================

post_to_social_media() {
    log_separator
    log "INFO" "Step 8: Posting to social media"
    
    local episode_title
    episode_title=$(cat "$EPISODE_TITLE")
    local post_url="${EPISODE_URL:-https://youtube.com}"
    
    # LinkedIn
    post_to_linkedin "$episode_title" "$post_url"
    
    # Facebook
    post_to_facebook "$episode_title" "$post_url"
    
    # Twitter/X
    post_to_twitter "$episode_title" "$post_url"
}

post_to_linkedin() {
    local title="$1"
    local url="$2"
    
    log "INFO" "Posting to LinkedIn..."
    
    if [[ -z "$LINKEDIN_WEBHOOK_URL" ]]; then
        log "INFO" "[SKIP] LinkedIn webhook not configured (set LINKEDIN_WEBHOOK_URL)"
        return 0
    fi
    
    if [[ "$DEMO_MODE" == true ]]; then
        log "INFO" "[DEMO] LinkedIn post: ${title} - ${url}"
        return 0
    fi
    
    local payload
    payload=$(cat << EOF
{
  "text": "🎙️ New Episode: ${title}\n\nWatch now: ${url}\n\n#TheDavidDailyShow #Podcast #Tech #Startup"
}
EOF
)
    
    if curl -s -X POST -H "Content-Type: application/json" \
        -d "$payload" "$LINKEDIN_WEBHOOK_URL" >> "$LOG_FILE" 2>&1; then
        log "SUCCESS" "LinkedIn post sent"
    else
        log "WARN" "LinkedIn post failed"
    fi
}

post_to_facebook() {
    local title="$1"
    local url="$2"
    
    log "INFO" "Posting to Facebook..."
    
    if [[ -z "$FACEBOOK_PAGE_TOKEN" || -z "$FACEBOOK_PAGE_ID" ]]; then
        log "INFO" "[SKIP] Facebook credentials not configured (set FACEBOOK_PAGE_TOKEN, FACEBOOK_PAGE_ID)"
        return 0
    fi
    
    if [[ "$DEMO_MODE" == true ]]; then
        log "INFO" "[DEMO] Facebook post: ${title} - ${url}"
        return 0
    fi
    
    local message="🎙️ New Episode: ${title}\n\nWatch now: ${url}\n\n#TheDavidDailyShow #Podcast"
    
    if curl -s -X POST \
        "https://graph.facebook.com/v18.0/${FACEBOOK_PAGE_ID}/feed" \
        -d "message=${message}" \
        -d "link=${url}" \
        -d "access_token=${FACEBOOK_PAGE_TOKEN}" >> "$LOG_FILE" 2>&1; then
        log "SUCCESS" "Facebook post sent"
    else
        log "WARN" "Facebook post failed"
    fi
}

post_to_twitter() {
    local title="$1"
    local url="$2"
    
    log "INFO" "Posting to Twitter/X..."
    
    if [[ -z "$TWITTER_BEARER_TOKEN" ]]; then
        log "INFO" "[SKIP] Twitter credentials not configured (set TWITTER_BEARER_TOKEN)"
        return 0
    fi
    
    if [[ "$DEMO_MODE" == true ]]; then
        log "INFO" "[DEMO] Twitter post: 🎙️ New Episode: ${title} ${url} #TheDavidDailyShow"
        return 0
    fi
    
    # Truncate title if needed (Twitter limit)
    local tweet_text="🎙️ New Episode: ${title} ${url} #TheDavidDailyShow #Podcast"
    if [[ ${#tweet_text} -gt 280 ]]; then
        tweet_text="${tweet_text:0:277}..."
    fi
    
    local payload
    payload=$(jq -n --arg text "$tweet_text" '{text: $text}' 2>/dev/null || echo "{\"text\": \"${tweet_text}\"}")
    
    if curl -s -X POST \
        "https://api.twitter.com/2/tweets" \
        -H "Authorization: Bearer ${TWITTER_BEARER_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$payload" >> "$LOG_FILE" 2>&1; then
        log "SUCCESS" "Twitter post sent"
    else
        log "WARN" "Twitter post failed"
    fi
}

# =============================================================================
# STEP 9: CLEANUP & SUMMARY
# =============================================================================

generate_summary() {
    log_separator
    log "INFO" "Step 9: Generating workflow summary"
    
    local summary_file="${EPISODE_DIR}/SUMMARY.md"
    
    cat > "$summary_file" << EOF
# Podcast Workflow Summary

## Episode: $(cat "$EPISODE_TITLE")

| Field | Value |
|-------|-------|
| Episode ID | ${EPISODE_ID} |
| Type | ${EPISODE_TYPE} |
| Duration | $(seconds_to_duration "${VIDEO_DURATION%.*}") |
| Resolution | ${VIDEO_WIDTH}x${VIDEO_HEIGHT} |
| Date | $(date "$TIMESTAMP_FORMAT") |

## Files Generated

- **Full Video:** \`${EPISODE_VIDEO}\`
- **Audio (WAV):** \`${EPISODE_AUDIO}\`
- **Audio (MP3):** \`${EPISODE_AUDIO_MP3}\`
- **Chapters:** \`${EPISODE_CHAPTERS}\`
- **Clips List:** \`${EPISODE_CLIPS_LIST}\`
- **Title:** \`${EPISODE_TITLE}\`
- **Description:** \`${EPISODE_DESCRIPTION}\`
- **Tags:** \`${EPISODE_TAGS}\`
- **Metadata:** \`${EPISODE_METADATA}\`

## Shorts

$(if [[ -d "$CLIPS_DIR" ]]; then
    ls "$CLIPS_DIR"/short-"${EPISODE_ID}"-*.mp4 2>/dev/null | while read -r f; do
        echo "- \`$(basename "$f")\` ($(du -h "$f" | cut -f1))"
    done
else
    echo "No shorts generated."
fi)

## Next Steps

1. Review the full video and audio for quality
2. Check chapter timestamps for accuracy
3. Preview shorts clips and adjust if needed
4. Upload to YouTube (or use prepared files in upload-ready/)
5. Share on social media

---
Generated by Podcast Workflow v1.0.0
EOF
    
    log "SUCCESS" "Summary saved: ${summary_file}"
    
    # Print final summary to console
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║         PODCAST WORKFLOW COMPLETE                ║"
    echo "╠══════════════════════════════════════════════════╣"
    echo "║ Episode: ${EPISODE_ID}"
    echo "║ Output:  ${EPISODE_DIR}"
    echo "║ Shorts:  $(wc -l < "$EPISODE_CLIPS_LIST" 2>/dev/null || echo 0) clips"
    echo "║ Log:     ${LOG_FILE}"
    echo "╚══════════════════════════════════════════════════╝"
}

cleanup() {
    log "INFO" "Cleaning up temporary files..."
    # Remove any temp files if needed
    # Keep all output files for review
    log "SUCCESS" "Cleanup complete"
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    # Parse command line arguments
    parse_args "$@"
    
    # Initialize
    init
    
    # Check prerequisites
    check_prerequisites
    
    # Step 1: Resolve input (download if needed)
    resolve_input "$INPUT_SOURCE"
    
    # Step 2: Extract audio
    extract_audio
    
    # Step 3: Generate chapters
    generate_chapters
    
    # Step 4-5: Detect and export shorts (unless skipped)
    if [[ "$SKIP_SHORTS" != true && "$UPLOAD_ONLY" != true ]]; then
        detect_best_clips
        export_clips
    fi
    
    # Step 6: Generate metadata
    generate_metadata
    
    # Step 7: Upload to YouTube (unless shorts-only)
    if [[ "$SHORTS_ONLY" != true ]]; then
        upload_to_youtube
    fi
    
    # Step 8: Post to social media
    if [[ "$SHORTS_ONLY" != true ]]; then
        post_to_social_media
    fi
    
    # Step 9: Summary and cleanup
    generate_summary
    cleanup
    
    log "SUCCESS" "=== Workflow Complete ==="
}

# Run main function with all arguments
main "$@"

