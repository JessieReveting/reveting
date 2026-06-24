#!/usr/bin/env node

/**
 * DATA TAXI Sync Script
 * 
 * Synchronizes files between the DATA TAXI drive and local mirror.
 * Supports push, pull, and bi-directional sync with conflict resolution.
 * Generates episode inventory CSV from TDSS spreadsheet data.
 * 
 * Usage:
 *   node data-taxi-sync.js --direction pull
 *   node data-taxi-sync.js --direction push --dry-run
 *   node data-taxi-sync.js --direction bi --verbose
 *   node data-taxi-sync.js --direction pull --episodes EP001-EP020
 *   node data-taxi-sync.js --direction push --exclude "*.tmp"
 *   node data-taxi-sync.js --inventory
 * 
 * Options:
 *   --direction <push|pull|bi>   Sync direction (default: pull)
 *   --dry-run                   Show what would be done without making changes
 *   --verbose                   Show detailed progress output
 *   --episodes <range>          Limit to specific episodes (e.g., EP001-EP020)
 *   --exclude <pattern>         Glob pattern to exclude files (repeatable)
 *   --inventory                 Generate episode inventory CSV only
 *   --log-file <path>           Custom log file path (default: scripts/sync-log.txt)
 *   --help, -h                  Show this help message
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const CONFIG = {
  // DATA TAXI drive paths
  dataTaxiRoot: '/Volumes/DATA TAXI',
  dataTaxiFiles: '/Volumes/DATA TAXI/FILES/01 THE DAVID DAILY SHOW',
  
  // Local mirror
  localMirror: path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'backups', 'data-taxi'),
  
  // Episode folders base (local)
  episodesBase: path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'startup', 'episodes'),
  
  // TDSS data source for YouTube URLs
  tddsDataPath: path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'startup', 'yt_seo_full.json'),
  
  // Google Sheets config for TDSS lookup
  spreadsheetId: '1odwvWVKQJDQ9i74aRXFx4rArSAKqPCj3T6VximU0ZpI',
  credentialsPath: path.join(os.homedir(), '.hermes', 'auth', 'google_sheets_credentials.json'),
  
  // Logging
  defaultLogFile: path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'startup', 'scripts', 'sync-log.txt'),
  
  // Sync settings
  maxRetries: 3,
  retryDelayMs: 1000,
  progressInterval: 10, // Show progress every N files
};

// ---------------------------------------------------------------------------
// CLI Argument Parsing
// ---------------------------------------------------------------------------

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    direction: 'pull',
    dryRun: false,
    verbose: false,
    episodes: null,
    exclude: [],
    inventoryOnly: false,
    logFile: CONFIG.defaultLogFile,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--direction':
        options.direction = args[++i];
        if (!['push', 'pull', 'bi'].includes(options.direction)) {
          console.error(`Invalid direction: ${options.direction}. Must be push, pull, or bi.`);
          process.exit(1);
        }
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--verbose':
        options.verbose = true;
        break;
      case '--episodes':
        options.episodes = args[++i];
        break;
      case '--exclude':
        options.exclude.push(args[++i]);
        break;
      case '--inventory':
        options.inventoryOnly = true;
        break;
      case '--log-file':
        options.logFile = args[++i];
        break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
        break;
      default:
        console.error(`Unknown argument: ${arg}`);
        printHelp();
        process.exit(1);
    }
  }

  return options;
}

function printHelp() {
  console.log(`
DATA TAXI Sync Script

Usage:
  node data-taxi-sync.js [options]

Options:
  --direction <push|pull|bi>   Sync direction (default: pull)
                              pull = download from DATA TAXI to local
                              push = upload from local to DATA TAXI
                              bi = bidirectional sync (newer wins)
  --dry-run                   Show what would be done without making changes
  --verbose                   Show detailed progress output
  --episodes <range>          Limit to specific episodes (e.g., EP001-EP020)
  --exclude <pattern>         Glob pattern to exclude files (repeatable)
  --inventory                 Generate episode inventory CSV only
  --log-file <path>           Custom log file path
  --help, -h                  Show this help message

Examples:
  node data-taxi-sync.js --direction pull
  node data-taxi-sync.js --direction push --dry-run --verbose
  node data-taxi-sync.js --direction bi --episodes EP001-EP020
  node data-taxi-sync.js --direction pull --exclude "*.tmp" --exclude "*.DS_Store"
  node data-taxi-sync.js --inventory
`);
}

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------

class Logger {
  constructor(logFilePath, verbose = false) {
    this.logFilePath = logFilePath;
    this.verbose = verbose;
    this.logStream = null;
    
    // Ensure log directory exists
    const logDir = path.dirname(logFilePath);
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    
    this.logStream = fs.createWriteStream(logFilePath, { flags: 'a' });
  }

  _timestamp() {
    return new Date().toISOString();
  }

  _write(level, message) {
    const line = `[${this._timestamp()}] [${level}] ${message}`;
    
    // Write to log file
    if (this.logStream) {
      this.logStream.write(line + '\n');
    }
    
    // Console output based on level and verbosity
    if (level === 'ERROR') {
      console.error(`\x1b[31m${line}\x1b[0m`);
    } else if (level === 'WARN') {
      console.warn(`\x1b[33m${line}\x1b[0m`);
    } else if (this.verbose || level === 'INFO') {
      if (level === 'INFO') {
        console.log(`\x1b[36m${line}\x1b[0m`);
      } else {
        console.log(`\x1b[90m${line}\x1b[0m`);
      }
    }
  }

  info(message) { this._write('INFO', message); }
  warn(message) { this._write('WARN', message); }
  error(message) { this._write('ERROR', message); }
  debug(message) { this._write('DEBUG', message); }
  
  progress(current, total, message) {
    const pct = Math.round((current / total) * 100);
    const bar = '█'.repeat(Math.floor(pct / 5)) + '░'.repeat(20 - Math.floor(pct / 5));
    const line = `\r[${bar}] ${pct}% (${current}/${total}) ${message || ''}`;
    
    if (this.verbose) {
      process.stdout.write(line);
      if (current === total) process.stdout.write('\n');
    }
  }

  close() {
    if (this.logStream) {
      this.logStream.end();
    }
  }
}

// ---------------------------------------------------------------------------
// Utility Functions
// ---------------------------------------------------------------------------

/**
 * Check if DATA TAXI drive is mounted
 */
function isDriveMounted() {
  return fs.existsSync(CONFIG.dataTaxiRoot) && fs.existsSync(CONFIG.dataTaxiFiles);
}

/**
 * Ensure local backup directory exists
 */
function ensureLocalDir(dirPath, logger) {
  if (!fs.existsSync(dirPath)) {
    if (options.dryRun) {
      logger.info(`[DRY RUN] Would create directory: ${dirPath}`);
    } else {
      fs.mkdirSync(dirPath, { recursive: true });
      logger.info(`Created directory: ${dirPath}`);
    }
  }
  return true;
}

/**
 * Parse episode range string like "EP001-EP020" into start/end numbers
 */
function parseEpisodeRange(rangeStr) {
  const match = rangeStr.match(/^(EP\d+)-(EP\d+)$/i);
  if (!match) {
    // Try single episode
    const singleMatch = rangeStr.match(/^(EP\d+)$/i);
    if (singleMatch) {
      const num = parseInt(singleMatch[1].replace('EP', ''), 10);
      return { start: num, end: num };
    }
    console.error(`Invalid episode range format: ${rangeStr}. Use EP001-EP020 or EP001.`);
    process.exit(1);
  }
  
  const start = parseInt(match[1].replace('EP', ''), 10);
  const end = parseInt(match[2].replace('EP', ''), 10);
  
  if (start > end) {
    console.error(`Invalid range: start (${start}) > end (${end})`);
    process.exit(1);
  }
  
  return { start, end };
}

/**
 * Format episode number to EPXXX format
 */
function formatEpisode(num) {
  return `EP${String(num).padStart(3, '0')}`;
}

/**
 * Check if a file matches any exclude pattern
 */
function isExcluded(filePath, excludePatterns) {
  if (!excludePatterns || excludePatterns.length === 0) return false;
  
  const fileName = path.basename(filePath);
  return excludePatterns.some(pattern => {
    // Simple glob matching
    const regex = pattern
      .replace(/[.+^${}()|[\]\\]/g, '\\$&')  // Escape special chars except * and ?
      .replace(/\*/g, '.*')
      .replace(/\?/g, '.');
    return new RegExp(`^${regex}$`, 'i').test(fileName);
  });
}

/**
 * Get file stats safely
 */
function safeStat(filePath) {
  try {
    return fs.statSync(filePath);
  } catch {
    return null;
  }
}

/**
 * Recursively list all files in a directory
 */
function listFilesRecursive(dirPath, basePath = dirPath) {
  const files = [];
  
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);
      const relativePath = path.relative(basePath, fullPath);
      
      if (entry.isDirectory()) {
        files.push(...listFilesRecursive(fullPath, basePath));
      } else if (entry.isFile()) {
        const stat = safeStat(fullPath);
        files.push({
          fullPath,
          relativePath: relativePath.split(path.sep).join('/'), // Normalize separators
          size: stat ? stat.size : 0,
          modified: stat ? stat.mtime : null,
        });
      }
    }
  } catch (error) {
    // Directory might not exist or be accessible
  }
  
  return files;
}

/**
 * Copy file with directory creation
 */
function copyFile(src, dest, dryRun) {
  if (dryRun) {
    return { success: true, dryRun: true };
  }
  
  try {
    const destDir = path.dirname(dest);
    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }
    fs.copyFileSync(src, dest);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Delete file safely
 */
function deleteFile(filePath, dryRun) {
  if (dryRun) {
    return { success: true, dryRun: true };
  }
  
  try {
    fs.unlinkSync(filePath);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Format bytes to human-readable string
 */
function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Load TDSS episode data for YouTube URL lookup
 */
function loadTDSSData(logger) {
  try {
    if (!fs.existsSync(CONFIG.tddsDataPath)) {
      logger.warn(`TDSS data file not found at ${CONFIG.tddsDataPath}. YouTube URLs will be empty.`);
      return {};
    }
    
    const raw = fs.readFileSync(CONFIG.tddsDataPath, 'utf8');
    const data = JSON.parse(raw);
    
    if (!Array.isArray(data)) {
      logger.warn('TDSS data is not an array. Skipping YouTube URL lookup.');
      return {};
    }
    
    // Build episode -> youtube_url map
    const map = {};
    for (const ep of data) {
      const epNum = ep.ep || ep.episode || '';
      const url = ep.url || ep.youtube_url || '';
      if (epNum && url && url !== 'N/A') {
        map[epNum.toUpperCase()] = url;
      }
    }
    
    logger.info(`Loaded ${Object.keys(map).length} episode URLs from TDSS data.`);
    return map;
  } catch (error) {
    logger.warn(`Failed to load TDSS data: ${error.message}`);
    return {};
  }
}

// ---------------------------------------------------------------------------
// Sync Report
// ---------------------------------------------------------------------------

class SyncReport {
  constructor() {
    this.added = [];
    this.updated = [];
    this.deleted = [];
    this.conflicts = [];
    this.skipped = [];
    this.errors = [];
    this.totalSize = 0;
  }

  addAdded(file, size) {
    this.added.push(file);
    this.totalSize += size;
  }

  addUpdated(file, size) {
    this.updated.push(file);
    this.totalSize += size;
  }

  addDeleted(file) {
    this.deleted.push(file);
  }

  addConflict(file, resolution) {
    this.conflicts.push({ file, resolution });
  }

  addSkipped(file, reason) {
    this.skipped.push({ file, reason });
  }

  addError(file, error) {
    this.errors.push({ file, error });
  }

  printSummary(logger) {
    logger.info('');
    logger.info('═══════════════════════════════════════════');
    logger.info('         DATA TAXI SYNC REPORT');
    logger.info('═══════════════════════════════════════════');
    logger.info(`  Files added:    ${this.added.length}`);
    logger.info(`  Files updated:  ${this.updated.length}`);
    logger.info(`  Files deleted:  ${this.deleted.length}`);
    logger.info(`  Conflicts:      ${this.conflicts.length}`);
    logger.info(`  Skipped:        ${this.skipped.length}`);
    logger.info(`  Errors:         ${this.errors.length}`);
    logger.info(`  Total size:     ${formatBytes(this.totalSize)}`);
    logger.info('═══════════════════════════════════════════');
    
    if (this.conflicts.length > 0) {
      logger.info('');
      logger.info('Conflicts resolved:');
      this.conflicts.forEach(c => logger.info(`  ${c.file} -> ${c.resolution}`));
    }
    
    if (this.errors.length > 0) {
      logger.warn('');
      logger.warn('Errors encountered:');
      this.errors.forEach(e => logger.warn(`  ${e.file}: ${e.error}`));
    }
  }
}

// ---------------------------------------------------------------------------
// Episode Filter
// ---------------------------------------------------------------------------

function filterByEpisodes(files, episodeRange) {
  if (!episodeRange) return files;
  
  const { start, end } = parseEpisodeRange(episodeRange);
  const includeSet = new Set();
  
  for (let i = start; i <= end; i++) {
    includeSet.add(formatEpisode(i));
  }
  
  return files.filter(file => {
    // Check if the file path contains any of the episode folder names
    const parts = file.relativePath.split('/');
    return parts.some(part => includeSet.has(part.toUpperCase()));
  });
}

// ---------------------------------------------------------------------------
// Sync Operations
// ---------------------------------------------------------------------------

/**
 * PULL: Download from DATA TAXI to local mirror
 */
async function syncPull(logger, options) {
  if (!isDriveMounted()) {
    logger.error('DATA TAXI drive is not mounted!');
    logger.error(`Expected at: ${CONFIG.dataTaxiRoot}`);
    logger.error('Please connect the DATA TAXI drive and try again.');
    process.exit(1);
  }
  
  logger.info('═══════════════════════════════════════════');
  logger.info('  PULL: DATA TAXI → Local Mirror');
  logger.info('═══════════════════════════════════════════');
  logger.info(`Source: ${CONFIG.dataTaxiFiles}`);
  logger.info(`Destination: ${CONFIG.localMirror}`);
  if (options.dryRun) logger.info('\x1b[33m*** DRY RUN MODE - No files will be modified ***\x1b[0m');
  logger.info('');
  
  const report = new SyncReport();
  
  // List remote files
  logger.info('Scanning DATA TAXI drive...');
  let remoteFiles = listFilesRecursive(CONFIG.dataTaxiFiles);
  logger.info(`Found ${remoteFiles.length} files on DATA TAXI drive.`);
  
  // Apply episode filter
  if (options.episodes) {
    remoteFiles = filterByEpisodes(remoteFiles, options.episodes);
    logger.info(`After episode filter: ${remoteFiles.length} files.`);
  }
  
  // Apply exclude patterns
  if (options.exclude.length > 0) {
    const before = remoteFiles.length;
    remoteFiles = remoteFiles.filter(f => !isExcluded(f.relativePath, options.exclude));
    logger.info(`After exclude filter: ${remoteFiles.length} files (removed ${before - remoteFiles.length}).`);
  }
  
  // List local files
  logger.info('Scanning local mirror...');
  const localFiles = listFilesRecursive(CONFIG.localMirror);
  logger.info(`Found ${localFiles.length} files in local mirror.`);
  
  // Build local file map for quick lookup
  const localFileMap = new Map();
  for (const f of localFiles) {
    localFileMap.set(f.relativePath, f);
  }
  
  // Ensure local directory exists
  ensureLocalDir(CONFIG.localMirror, logger);
  
  // Process each remote file
  let processed = 0;
  for (const remoteFile of remoteFiles) {
    processed++;
    logger.progress(processed, remoteFiles.length, `Processing: ${remoteFile.relativePath}`);
    
    const localFile = localFileMap.get(remoteFile.relativePath);
    const destPath = path.join(CONFIG.localMirror, remoteFile.relativePath);
    
    if (localFile) {
      // File exists locally - check if it needs updating
      const remoteModTime = remoteFile.modified ? Math.floor(remoteFile.modified.getTime() / 1000) : 0;
      const localModTime = localFile.modified ? Math.floor(localFile.modified.getTime() / 1000) : 0;
      
      if (remoteFile.size !== localFile.size || remoteModTime > localModTime) {
        logger.debug(`Updated: ${remoteFile.remotePath}`);
        const result = copyFile(remoteFile.fullPath, destPath, options.dryRun);
        if (result.success) {
          report.addUpdated(remoteFile.relativePath, remoteFile.size);
        } else {
          report.addError(remoteFile.relativePath, result.error);
        }
      } else {
        logger.debug(`Unchanged: ${remoteFile.relativePath}`);
      }
    } else {
      // New file - download
      logger.debug(`New: ${remoteFile.relativePath}`);
      const result = copyFile(remoteFile.fullPath, destPath, options.dryRun);
      if (result.success) {
        report.addAdded(remoteFile.relativePath, remoteFile.size);
      } else {
        report.addError(remoteFile.relativePath, result.error);
      }
    }
  }
  
  // Check for files that exist locally but not on remote (potential deletions)
  const remotePaths = new Set(remoteFiles.map(f => f.relativePath));
  for (const localFile of localFiles) {
    if (!remotePaths.has(localFile.relativePath)) {
      const filePath = path.join(CONFIG.localMirror, localFile.relativePath);
      logger.debug(`Orphaned (local only): ${localFile.relativePath}`);
      // In pull mode, we don't delete local files that aren't on remote
      // unless explicitly requested. Just note it.
      report.addSkipped(localFile.relativePath, 'File exists locally but not on DATA TAXI');
    }
  }
  
  logger.progress(remoteFiles.length, remoteFiles.length, 'Complete');
  report.printSummary(logger);
  
  return report;
}

/**
 * PUSH: Upload from local mirror to DATA TAXI
 */
async function syncPush(logger, options) {
  if (!isDriveMounted()) {
    logger.error('DATA TAXI drive is not mounted!');
    logger.error(`Expected at: ${CONFIG.dataTaxiRoot}`);
    logger.error('Please connect the DATA TAXI drive and try again.');
    process.exit(1);
  }
  
  logger.info('═══════════════════════════════════════════');
  logger.info('  PUSH: Local Mirror → DATA TAXI');
  logger.info('═══════════════════════════════════════════');
  logger.info(`Source: ${CONFIG.localMirror}`);
  logger.info(`Destination: ${CONFIG.dataTaxiFiles}`);
  if (options.dryRun) logger.info('\x1b[33m*** DRY RUN MODE - No files will be modified ***\x1b[0m');
  logger.info('');
  
  const report = new SyncReport();
  
  // Check local mirror exists
  if (!fs.existsSync(CONFIG.localMirror)) {
    logger.error(`Local mirror does not exist: ${CONFIG.localMirror}`);
    logger.error('Run a pull sync first to create the local mirror.');
    process.exit(1);
  }
  
  // List local files
  logger.info('Scanning local mirror...');
  let localFiles = listFilesRecursive(CONFIG.localMirror);
  logger.info(`Found ${localFiles.length} files in local mirror.`);
  
  // Apply episode filter
  if (options.episodes) {
    localFiles = filterByEpisodes(localFiles, options.episodes);
    logger.info(`After episode filter: ${localFiles.length} files.`);
  }
  
  // Apply exclude patterns
  if (options.exclude.length > 0) {
    const before = localFiles.length;
    localFiles = localFiles.filter(f => !isExcluded(f.relativePath, options.exclude));
    logger.info(`After exclude filter: ${localFiles.length} files (removed ${before - localFiles.length}).`);
  }
  
  // List remote files
  logger.info('Scanning DATA TAXI drive...');
  const remoteFiles = listFilesRecursive(CONFIG.dataTaxiFiles);
  logger.info(`Found ${remoteFiles.length} files on DATA TAXI drive.`);
  
  // Build remote file map
  const remoteFileMap = new Map();
  for (const f of remoteFiles) {
    remoteFileMap.set(f.relativePath, f);
  }
  
  // Process each local file
  let processed = 0;
  for (const localFile of localFiles) {
    processed++;
    logger.progress(processed, localFiles.length, `Processing: ${localFile.relativePath}`);
    
    const remoteFile = remoteFileMap.get(localFile.relativePath);
    const destPath = path.join(CONFIG.dataTaxiFiles, localFile.relativePath);
    
    if (remoteFile) {
      // File exists remotely - check if it needs updating
      const localModTime = localFile.modified ? Math.floor(localFile.modified.getTime() / 1000) : 0;
      const remoteModTime = remoteFile.modified ? Math.floor(remoteFile.modified.getTime() / 1000) : 0;
      
      if (localFile.size !== remoteFile.size || localModTime > remoteModTime) {
        logger.debug(`Updated: ${localFile.relativePath}`);
        const result = copyFile(localFile.fullPath, destPath, options.dryRun);
        if (result.success) {
          report.addUpdated(localFile.relativePath, localFile.size);
        } else {
          report.addError(localFile.relativePath, result.error);
        }
      } else {
        logger.debug(`Unchanged: ${localFile.relativePath}`);
      }
    } else {
      // New file - upload
      logger.debug(`New: ${localFile.relativePath}`);
      const result = copyFile(localFile.fullPath, destPath, options.dryRun);
      if (result.success) {
        report.addAdded(localFile.relativePath, localFile.size);
      } else {
        report.addError(localFile.relativePath, result.error);
      }
    }
  }
  
  logger.progress(localFiles.length, localFiles.length, 'Complete');
  report.printSummary(logger);
  
  return report;
}

/**
 * BI-DIR: Bidirectional sync with conflict resolution (newer wins)
 */
async function syncBi(logger, options) {
  if (!isDriveMounted()) {
    logger.error('DATA TAXI drive is not mounted!');
    logger.error(`Expected at: ${CONFIG.dataTaxiRoot}`);
    logger.error('Please connect the DATA TAXI drive and try again.');
    process.exit(1);
  }
  
  logger.info('═══════════════════════════════════════════');
  logger.info('  BI-DIRECTIONAL SYNC');
  logger.info('═══════════════════════════════════════════');
  logger.info(`Local: ${CONFIG.localMirror}`);
  logger.info(`Remote: ${CONFIG.dataTaxiFiles}`);
  if (options.dryRun) logger.info('\x1b[33m*** DRY RUN MODE - No files will be modified ***\x1b[0m');
  logger.info('');
  
  const report = new SyncReport();
  
  // List all files from both sides
  logger.info('Scanning DATA TAXI drive...');
  let remoteFiles = listFilesRecursive(CONFIG.dataTaxiFiles);
  logger.info(`Found ${remoteFiles.length} files on DATA TAXI drive.`);
  
  logger.info('Scanning local mirror...');
  let localFiles = listFilesRecursive(CONFIG.localMirror);
  logger.info(`Found ${localFiles.length} files in local mirror.`);
  
  // Apply episode filter
  if (options.episodes) {
    remoteFiles = filterByEpisodes(remoteFiles, options.episodes);
    localFiles = filterByEpisodes(localFiles, options.episodes);
    logger.info(`After episode filter: ${remoteFiles.length} remote, ${localFiles.length} local files.`);
  }
  
  // Apply exclude patterns
  if (options.exclude.length > 0) {
    const beforeR = remoteFiles.length;
    const beforeL = localFiles.length;
    remoteFiles = remoteFiles.filter(f => !isExcluded(f.relativePath, options.exclude));
    localFiles = localFiles.filter(f => !isExcluded(f.relativePath, options.exclude));
    logger.info(`After exclude filter: ${remoteFiles.length} remote (-${beforeR - remoteFiles.length}), ${localFiles.length} local (-${beforeL - localFiles.length}).`);
  }
  
  // Build maps
  const remoteMap = new Map();
  for (const f of remoteFiles) {
    remoteMap.set(f.relativePath, f);
  }
  
  const localMap = new Map();
  for (const f of localFiles) {
    localMap.set(f.relativePath, f);
  }
  
  // Ensure local directory exists
  ensureLocalDir(CONFIG.localMirror, logger);
  
  // Get all unique file paths
  const allPaths = new Set([...remoteMap.keys(), ...localMap.keys()]);
  const totalFiles = allPaths.size;
  let processed = 0;
  
  for (const filePath of allPaths) {
    processed++;
    logger.progress(processed, totalFiles, `Syncing: ${filePath}`);
    
    const remote = remoteMap.get(filePath);
    const local = localMap.get(filePath);
    
    if (remote && !local) {
      // File only on remote - pull
      const destPath = path.join(CONFIG.localMirror, filePath);
      logger.debug(`Pull (remote only): ${filePath}`);
      const result = copyFile(remote.fullPath, destPath, options.dryRun);
      if (result.success) {
        report.addAdded(filePath, remote.size);
      } else {
        report.addError(filePath, result.error);
      }
    } else if (local && !remote) {
      // File only on local - push
      const destPath = path.join(CONFIG.dataTaxiFiles, filePath);
      logger.debug(`Push (local only): ${filePath}`);
      const result = copyFile(local.fullPath, destPath, options.dryRun);
      if (result.success) {
        report.addAdded(filePath, local.size);
      } else {
        report.addError(filePath, result.error);
      }
    } else {
      // File on both sides - compare and resolve
      const remoteModTime = remote.modified ? remote.modified.getTime() : 0;
      const localModTime = local.modified ? local.modified.getTime() : 0;
      
      if (remote.size === local.size && Math.abs(remoteModTime - localModTime) < 2000) {
        // Files are essentially the same (within 2 second tolerance for FAT32)
        logger.debug(`In sync: ${filePath}`);
      } else if (remoteModTime > localModTime) {
        // Remote is newer - pull
        const destPath = path.join(CONFIG.localMirror, filePath);
        logger.debug(`Conflict - remote newer: ${filePath}`);
        const result = copyFile(remote.fullPath, destPath, options.dryRun);
        if (result.success) {
          report.addUpdated(filePath, remote.size);
          report.addConflict(filePath, 'remote (newer) wins');
        } else {
          report.addError(filePath, result.error);
        }
      } else if (localModTime > remoteModTime) {
        // Local is newer - push
        const destPath = path.join(CONFIG.dataTaxiFiles, filePath);
        logger.debug(`Conflict - local newer: ${filePath}`);
        const result = copyFile(local.fullPath, destPath, options.dryRun);
        if (result.success) {
          report.addUpdated(filePath, local.size);
          report.addConflict(filePath, 'local (newer) wins');
        } else {
          report.addError(filePath, result.error);
        }
      } else {
        // Same time but different size - use larger file
        if (remote.size > local.size) {
          const destPath = path.join(CONFIG.localMirror, filePath);
          logger.debug(`Conflict - remote larger: ${filePath}`);
          const result = copyFile(remote.fullPath, destPath, options.dryRun);
          if (result.success) {
            report.addUpdated(filePath, remote.size);
            report.addConflict(filePath, 'remote (larger) wins');
          } else {
            report.addError(filePath, result.error);
          }
        } else {
          const destPath = path.join(CONFIG.dataTaxiFiles, filePath);
          logger.debug(`Conflict - local larger: ${filePath}`);
          const result = copyFile(local.fullPath, destPath, options.dryRun);
          if (result.success) {
            report.addUpdated(filePath, local.size);
            report.addConflict(filePath, 'local (larger) wins');
          } else {
            report.addError(filePath, result.error);
          }
        }
      }
    }
  }
  
  logger.progress(totalFiles, totalFiles, 'Complete');
  report.printSummary(logger);
  
  return report;
}

// ---------------------------------------------------------------------------
// Episode Inventory CSV
// ---------------------------------------------------------------------------

function generateEpisodeInventory(logger, options) {
  logger.info('═══════════════════════════════════════════');
  logger.info('  Generating Episode Inventory CSV');
  logger.info('═══════════════════════════════════════════');
  
  // Load TDSS data for YouTube URLs
  const youtubeUrls = loadTDSSData(logger);
  
  // Scan local mirror for episode folders
  const inventory = [];
  
  // Check both local mirror and episodes base
  const scanDirs = [];
  if (fs.existsSync(CONFIG.localMirror)) {
    scanDirs.push({ base: CONFIG.localMirror, label: 'mirror' });
  }
  if (fs.existsSync(CONFIG.episodesBase)) {
    scanDirs.push({ base: CONFIG.episodesBase, label: 'episodes' });
  }
  
  if (scanDirs.length === 0) {
    logger.warn('No episode directories found. Run a pull sync first.');
    return;
  }
  
  // Collect all episode folder names
  const episodeFolders = new Map();
  
  for (const scanDir of scanDirs) {
    try {
      const entries = fs.readdirSync(scanDir.base, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory() && entry.name.match(/^EP\d+$/i)) {
          const epNum = entry.name.toUpperCase();
          if (!episodeFolders.has(epNum)) {
            episodeFolders.set(epNum, { path: path.join(scanDir.base, entry.name), sources: [scanDir.label] });
          } else {
            episodeFolders.get(epNum).sources.push(scanDir.label);
          }
        }
      }
    } catch (error) {
      logger.warn(`Could not scan ${scanDir.base}: ${error.message}`);
    }
  }
  
  // Also check DATA TAXI if mounted
  if (isDriveMounted()) {
    try {
      const entries = fs.readdirSync(CONFIG.dataTaxiFiles, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory() && entry.name.match(/^EP\d+$/i)) {
          const epNum = entry.name.toUpperCase();
          if (!episodeFolders.has(epNum)) {
            episodeFolders.set(epNum, { path: path.join(CONFIG.dataTaxiFiles, entry.name), sources: ['data-taxi'] });
          }
        }
      }
    } catch (error) {
      logger.warn(`Could not scan DATA TAXI: ${error.message}`);
    }
  }
  
  // Build inventory rows
  for (const [epNum, info] of episodeFolders) {
    const stat = safeStat(info.path);
    let fileCount = 0;
    let totalSize = 0;
    let lastModified = null;
    
    // Count files in episode folder
    const files = listFilesRecursive(info.path);
    fileCount = files.length;
    for (const f of files) {
      totalSize += f.size;
      if (f.modified && (!lastModified || f.modified > lastModified)) {
        lastModified = f.modified;
      }
    }
    
    inventory.push({
      episode: epNum,
      folder_exists: true,
      file_count: fileCount,
      total_size: totalSize,
      total_size_human: formatBytes(totalSize),
      last_modified: lastModified ? lastModified.toISOString() : '',
      youtube_url: youtubeUrls[epNum] || '',
      sources: info.sources.join(','),
    });
  }
  
  // Sort by episode number
  inventory.sort((a, b) => {
    const numA = parseInt(a.episode.replace('EP', ''), 10);
    const numB = parseInt(b.episode.replace('EP', ''), 10);
    return numA - numB;
  });
  
  // Apply episode filter
  let filtered = inventory;
  if (options.episodes) {
    const { start, end } = parseEpisodeRange(options.episodes);
    filtered = inventory.filter(item => {
      const num = parseInt(item.episode.replace('EP', ''), 10);
      return num >= start && num <= end;
    });
  }
  
  // Output CSV
  const headers = ['episode', 'folder_exists', 'file_count', 'total_size', 'total_size_human', 'last_modified', 'youtube_url', 'sources'];
  const csvLines = [headers.join(',')];
  
  for (const row of filtered) {
    const values = headers.map(h => {
      let val = row[h] || '';
      if (typeof val === 'string' && (val.includes(',') || val.includes('"') || val.includes('\n'))) {
        val = `"${val.replace(/"/g, '""')}"`;
      }
      return val;
    });
    csvLines.push(values.join(','));
  }
  
  const csvContent = csvLines.join('\n');
  
  // Output to stdout
  console.log(csvContent);
  
  // Also save to file
  const outputPath = path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'startup', 'scripts', 'episode-inventory.csv');
  if (!options.dryRun) {
    fs.writeFileSync(outputPath, csvContent);
    logger.info(`\nInventory saved to: ${outputPath}`);
  }
  
  logger.info(`Total episodes in inventory: ${filtered.length}`);
  
  return filtered;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

let options;

async function main() {
  options = parseArgs();
  
  // Create logger
  const logger = new Logger(options.logFile, options.verbose);
  
  logger.info('═══════════════════════════════════════════');
  logger.info('  DATA TAXI Sync Script Started');
  logger.info(`  Direction: ${options.direction}`);
  logger.info(`  Dry Run: ${options.dryRun}`);
  logger.info(`  Verbose: ${options.verbose}`);
  if (options.episodes) logger.info(`  Episodes: ${options.episodes}`);
  if (options.exclude.length > 0) logger.info(`  Exclude: ${options.exclude.join(', ')}`);
  logger.info('═══════════════════════════════════════════');
  
  const startTime = Date.now();
  
  try {
    // Handle inventory-only mode
    if (options.inventoryOnly) {
      generateEpisodeInventory(logger, options);
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      logger.info(`\nCompleted in ${elapsed}s`);
      logger.close();
      return;
    }
    
    // Check drive mount status for non-inventory operations
    if (!isDriveMounted() && !options.dryRun) {
      // For inventory, we can work without the drive
    }
    
    // Run sync based on direction
    let report;
    switch (options.direction) {
      case 'pull':
        report = await syncPull(logger, options);
        break;
      case 'push':
        report = await syncPush(logger, options);
        break;
      case 'bi':
        report = await syncBi(logger, options);
        break;
      default:
        logger.error(`Unknown direction: ${options.direction}`);
        process.exit(1);
    }
    
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    logger.info(`\nSync completed in ${elapsed}s`);
    
    // Generate inventory after successful sync
    if (!options.dryRun && report) {
      logger.info('\nGenerating episode inventory...');
      generateEpisodeInventory(logger, options);
    }
    
    // Exit with error code if there were errors
    if (report && report.errors.length > 0) {
      logger.warn(`\nCompleted with ${report.errors.length} error(s).`);
      process.exit(2);
    }
    
  } catch (error) {
    logger.error(`Fatal error: ${error.message}`);
    if (options.verbose) {
      logger.error(error.stack);
    }
    process.exit(1);
  } finally {
    logger.close();
  }
}

// Handle unhandled rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection:', reason);
  process.exit(1);
});

// Handle SIGINT
process.on('SIGINT', () => {
  console.log('\n\nSync interrupted by user.');
  process.exit(130);
});

main();
