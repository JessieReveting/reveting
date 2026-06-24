#!/usr/bin/env node
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ============================================================
// CLI Argument Parsing
// ============================================================
const args = process.argv.slice(2);

function getArg(name, defaultValue = null) {
  const idx = args.indexOf(`--${name}`);
  if (idx === -1) return defaultValue;
  if (idx + 1 >= args.length) return true;
  const val = args[idx + 1];
  if (val.startsWith('--')) return true;
  return val;
}

function hasArg(name) {
  return args.includes(`--${name}`);
}

const config = {
  path: getArg('path', '/Volumes/DATA TAXI/FILES/01 THE DAVID DAILY SHOW/'),
  days: parseInt(getArg('days', '7'), 10),
  type: getArg('type', 'video'),
  limit: parseInt(getArg('limit', '0'), 10),
  format: getArg('format', 'table'),
  sort: getArg('sort', 'date'),
  cloud: hasArg('cloud'),
  ext: getArg('ext', 'mp4,mov,mp3,wav,pdf,md,json'),
  minSize: parseInt(getArg('minSize', '0'), 10),
  maxSize: parseInt(getArg('maxSize', '0'), 10),
};

// ============================================================
// Constants
// ============================================================
const VIDEO_EXTENSIONS = new Set(['mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm', 'm4v', 'mpg', 'mpeg', '3gp', 'ts', 'm2ts']);
const AUDIO_EXTENSIONS = new Set(['mp3', 'wav', 'flac', 'aac', 'ogg', 'wma', 'm4a', 'aiff', 'alac', 'opus']);
const DOC_EXTENSIONS = new Set(['pdf', 'md', 'json', 'txt', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv']);

const ALL_EXTENSIONS = new Set([...VIDEO_EXTENSIONS, ...AUDIO_EXTENSIONS, ...DOC_EXTENSIONS]);

// ============================================================
// Utility Functions
// ============================================================
function humanReadableSize(bytes) {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const size = (bytes / Math.pow(k, i)).toFixed(i > 0 ? 1 : 0);
  return `${size} ${units[i]}`;
}

function formatDate(date) {
  return date.toISOString().replace('T', ' ').substring(0, 19);
}

function formatDateShort(date) {
  return date.toISOString().substring(0, 10);
}

function getFileExtension(filename) {
  const ext = path.extname(filename).toLowerCase().replace('.', '');
  return ext;
}

function getFileCategory(ext) {
  if (VIDEO_EXTENSIONS.has(ext)) return 'video';
  if (AUDIO_EXTENSIONS.has(ext)) return 'audio';
  if (DOC_EXTENSIONS.has(ext)) return 'document';
  return 'other';
}

function parseSizeFilter(value) {
  if (!value || value === '0') return 0;
  const str = String(value).toUpperCase();
  const match = str.match(/^(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB|B)?$/);
  if (!match) return parseInt(str, 10) || 0;
  const num = parseFloat(match[1]);
  const unit = match[2] || 'B';
  const multipliers = { 'B': 1, 'KB': 1024, 'MB': 1048576, 'GB': 1073741824, 'TB': 1099511627776 };
  return Math.round(num * (multipliers[unit] || 1));
}

// ============================================================
// File Scanner
// ============================================================
function scanDirectory(dirPath, config) {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - config.days);

  const minBytes = parseSizeFilter(config.minSize);
  const maxBytes = parseSizeFilter(config.maxSize);

  // Determine allowed extensions
  let allowedExts = null;
  if (config.ext && config.ext !== 'all') {
    allowedExts = new Set(config.ext.split(',').map(e => e.trim().toLowerCase().replace('.', '')));
  }

  // Determine allowed types
  let allowedTypes = new Set();
  if (config.type === 'video') allowedTypes.add('video');
  else if (config.type === 'audio') allowedTypes.add('audio');
  else if (config.type === 'all') {
    allowedTypes.add('video');
    allowedTypes.add('audio');
    allowedTypes.add('document');
    allowedTypes.add('other');
  } else {
    allowedTypes.add(config.type);
  }

  const results = [];

  function walkDir(dir) {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (err) {
      // Permission denied or other error - skip
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        // Skip hidden directories and common non-media dirs
        if (entry.name.startsWith('.') || entry.name === '__MACOSX' || entry.name === 'node_modules') continue;
        walkDir(fullPath);
      } else if (entry.isFile()) {
        const ext = getFileExtension(entry.name);

        // Filter by extension
        if (allowedExts && !allowedExts.has(ext)) continue;

        // Filter by type
        const category = getFileCategory(ext);
        if (config.type !== 'all' && !allowedTypes.has(category)) continue;

        try {
          const stat = fs.statSync(fullPath);

          // Filter by date
          if (stat.mtime < cutoffDate) continue;

          // Filter by size
          if (minBytes > 0 && stat.size < minBytes) continue;
          if (maxBytes > 0 && stat.size > maxBytes) continue;

          results.push({
            name: entry.name,
            path: fullPath,
            relativePath: path.relative(config.path, fullPath),
            size: stat.size,
            sizeHuman: humanReadableSize(stat.size),
            modified: stat.mtime,
            modifiedStr: formatDate(stat.mtime),
            extension: ext,
            category: category,
            dir: path.relative(config.path, dir),
          });
        } catch (err) {
          // Skip files we can't stat
        }
      }
    }
  }

  walkDir(dirPath);
  return results;
}

// ============================================================
// Sorting
// ============================================================
function sortResults(results, sortBy) {
  const sortFns = {
    name: (a, b) => a.name.localeCompare(b.name),
    size: (a, b) => b.size - a.size,
    date: (a, b) => b.modified.getTime() - a.modified.getTime(),
  };
  const fn = sortFns[sortBy] || sortFns.date;
  return results.sort(fn);
}

// ============================================================
// Grouping
// ============================================================
function groupByFolder(results) {
  const groups = {};
  for (const file of results) {
    const group = file.dir || '.';
    if (!groups[group]) groups[group] = [];
    groups[group].push(file);
  }
  return groups;
}

// ============================================================
// Cloud Storage Status
// ============================================================
function checkCloudStatus() {
  const status = {
    dataTaxi: checkDataTaxi(),
    googleDrive: checkGoogleDrive(),
    iCloud: checkICloud(),
    oneDrive: checkOneDrive(),
  };
  return status;
}

function checkDataTaxi() {
  const mountPath = '/Volumes/DATA TAXI';
  try {
    const stat = fs.statSync(mountPath);
    // Check if it's a mount point
    let freeSpace = null;
    try {
      if (process.platform === 'darwin') {
        const output = execSync(`df -h "${mountPath}" 2>/dev/null`, { encoding: 'utf8', timeout: 5000 });
        const lines = output.trim().split('\n');
        if (lines.length >= 2) {
          const parts = lines[1].split(/\s+/);
          if (parts.length >= 4) {
            freeSpace = parts[3];
          }
        }
      }
    } catch (e) {
      // df not available
    }
    return {
      mounted: true,
      path: mountPath,
      freeSpace: freeSpace || 'unknown',
      status: 'connected',
    };
  } catch (e) {
    return {
      mounted: false,
      path: mountPath,
      freeSpace: null,
      status: 'not found',
      error: e.message,
    };
  }
}

function checkGoogleDrive() {
  // Check for Google Drive File Stream / Drive for Desktop
  const possiblePaths = [
    '/Volumes/Google Drive',
    '/Volumes/GoogleDrive',
    path.join(process.env.HOME, 'Google Drive'),
    path.join(process.env.HOME, 'My Drive'),
  ];

  let mountedPath = null;
  for (const p of possiblePaths) {
    try {
      fs.accessSync(p, fs.constants.R_OK);
      mountedPath = p;
      break;
    } catch (e) {
      // not found
    }
  }

  // Check for service account credentials
  let hasServiceAccount = false;
  const credPaths = [
    path.join(process.env.HOME, '.config/gcloud/service_account.json'),
    path.join(process.env.HOME, '.config/gcloud/application_default_credentials.json'),
    '/Users/davidgo/Documents/GoTechSolutions/credentials/gdrive-service-account.json',
    path.join(__dirname, '../credentials/gdrive-service-account.json'),
  ];

  for (const cp of credPaths) {
    try {
      fs.accessSync(cp, fs.constants.R_OK);
      hasServiceAccount = true;
      break;
    } catch (e) {
      // not found
    }
  }

  // Check if Google Drive process is running
  let processRunning = false;
  try {
    if (process.platform === 'darwin' || process.platform === 'linux') {
      const output = execSync('ps aux | grep -i "google drive" | grep -v grep', { encoding: 'utf8', timeout: 3000 });
      processRunning = output.trim().length > 0;
    }
  } catch (e) {
    processRunning = false;
  }

  return {
    mounted: !!mountedPath,
    path: mountedPath || null,
    processRunning,
    hasServiceAccount,
    status: mountedPath ? 'connected' : (processRunning ? 'process running' : 'not found'),
  };
}

function checkICloud() {
  // Check for iCloud Drive
  const iCloudPath = path.join(process.env.HOME, 'Library/Mobile Documents');
  let available = false;
  try {
    fs.accessSync(iCloudPath, fs.constants.R_OK);
    available = true;
  } catch (e) {
    available = false;
  }

  // Check if cloudd process is running
  let processRunning = false;
  try {
    if (process.platform === 'darwin') {
      const output = execSync('ps aux | grep -E "cloudd|bird" | grep -v grep', { encoding: 'utf8', timeout: 3000 });
      processRunning = output.trim().length > 0;
    }
  } catch (e) {
    processRunning = false;
  }

  return {
    available,
    path: available ? iCloudPath : null,
    processRunning,
    status: available ? 'connected' : 'not available',
  };
}

function checkOneDrive() {
  // Check for OneDrive
  const possiblePaths = [
    path.join(process.env.HOME, 'OneDrive'),
    path.join(process.env.HOME, 'OneDrive - Personal'),
  ];

  let mountedPath = null;
  for (const p of possiblePaths) {
    try {
      fs.accessSync(p, fs.constants.R_OK);
      mountedPath = p;
      break;
    } catch (e) {
      // not found
    }
  }

  // Check if OneDrive process is running
  let processRunning = false;
  try {
    if (process.platform === 'darwin' || process.platform === 'linux') {
      const output = execSync('ps aux | grep -i "onedrive" | grep -v grep', { encoding: 'utf8', timeout: 3000 });
      processRunning = output.trim().length > 0;
    }
  } catch (e) {
    processRunning = false;
  }

  return {
    mounted: !!mountedPath,
    path: mountedPath || null,
    processRunning,
    status: mountedPath ? 'connected' : (processRunning ? 'process running' : 'not found'),
  };
}

// ============================================================
// Output Formatters
// ============================================================
function outputJson(results, groups, cloudStatus) {
  const output = {
    scan: {
      path: config.path,
      days: config.days,
      type: config.type,
      scannedAt: new Date().toISOString(),
    },
    summary: computeSummary(results),
    cloud: cloudStatus,
    groups: Object.keys(groups).sort().map(folder => ({
      folder,
      files: groups[folder].map(f => ({
        name: f.name,
        path: f.relativePath,
        size: f.sizeHuman,
        modified: f.modifiedStr,
        type: f.category,
        extension: f.extension,
      })),
    })),
  };
  console.log(JSON.stringify(output, null, 2));
}

function outputCsv(results) {
  const header = 'Name,Path,Size,SizeBytes,Modified,Type,Extension';
  console.log(header);
  for (const f of results) {
    const name = `"${f.name.replace(/"/g, '""')}"`;
    const relPath = `"${f.relativePath.replace(/"/g, '""')}"`;
    console.log(`${name},${relPath},${f.sizeHuman},${f.size},${f.modifiedStr},${f.category},${f.extension}`);
  }
}

function outputTable(results, groups) {
  // Print header
  console.log('');
  console.log('╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗');
  console.log('║                              RECENT FILES SCANNER - RESULTS                                       ║');
  console.log('╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝');
  console.log('');

  // Print scan info
  console.log(`  📁 Path:    ${config.path}`);
  console.log(`  📅 Period:  Last ${config.days} day(s) (since ${formatDateShort(new Date(Date.now() - config.days * 86400000))})`);
  console.log(`  🎯 Type:    ${config.type}`);
  if (config.ext) console.log(`  📎 Extensions: ${config.ext}`);
  console.log('');

  const summary = computeSummary(results);

  // Print summary
  console.log('  ┌─────────────────────────────────────────────┐');
  console.log('  │  SUMMARY                                    │');
  console.log('  ├─────────────────────────────────────────────┤');
  console.log(`  │  Total Files:  ${String(summary.totalFiles).padStart(25)} │`);
  console.log(`  │  Total Size:   ${summary.totalSize.padStart(25)} │`);
  console.log(`  │  Earliest:     ${summary.earliest.padStart(25)} │`);
  console.log(`  │  Latest:       ${summary.latest.padStart(25)} │`);
  console.log(`  │  Folders:      ${String(summary.folderCount).padStart(25)} │`);
  console.log('  └─────────────────────────────────────────────┘');
  console.log('');

  if (results.length === 0) {
    console.log('  ⚠️  No files found matching the criteria.');
    console.log('');
    return;
  }

  // Print grouped results
  const sortedFolders = Object.keys(groups).sort();
  for (const folder of sortedFolders) {
    const files = groups[folder];
    const folderSize = files.reduce((sum, f) => sum + f.size, 0);

    console.log(`  📂 ${folder}/  (${files.length} files, ${humanReadableSize(folderSize)})`);
    console.log('  ' + '─'.repeat(100));

    // Table header
    console.log(`  ${'Name'.padEnd(40)} ${'Size'.padStart(12)} ${'Modified'.padStart(20)} ${'Type'.padStart(8)}`);
    console.log(`  ${'─'.repeat(40)} ${'─'.repeat(12)} ${'─'.repeat(20)} ${'─'.repeat(8)}`);

    for (const f of files) {
      const name = f.name.length > 38 ? f.name.substring(0, 35) + '...' : f.name;
      console.log(`  ${name.padEnd(40)} ${f.sizeHuman.padStart(12)} ${f.modifiedStr.padStart(20)} ${f.category.padStart(8)}`);
    }
    console.log('');
  }
}

function computeSummary(results) {
  if (results.length === 0) {
    return {
      totalFiles: 0,
      totalSize: '0 B',
      earliest: 'N/A',
      latest: 'N/A',
      folderCount: 0,
    };
  }

  const totalBytes = results.reduce((sum, f) => sum + f.size, 0);
  const dates = results.map(f => f.modified.getTime());
  const earliest = new Date(Math.min(...dates));
  const latest = new Date(Math.max(...dates));
  const folders = new Set(results.map(f => f.dir));

  return {
    totalFiles: results.length,
    totalSize: humanReadableSize(totalBytes),
    earliest: formatDateShort(earliest),
    latest: formatDateShort(latest),
    folderCount: folders.size,
  };
}

// ============================================================
// Cloud Status Output
// ============================================================
function printCloudStatus(status) {
  console.log('');
  console.log('╔══════════════════════════════════════════════════════════════════╗');
  console.log('║                     CLOUD STORAGE STATUS                        ║');
  console.log('╚══════════════════════════════════════════════════════════════════╝');
  console.log('');

  // DATA TAXI
  const dt = status.dataTaxi;
  const dtIcon = dt.mounted ? '✅' : '❌';
  console.log(`  ${dtIcon} DATA TAXI Drive`);
  console.log(`     Status: ${dt.status}`);
  console.log(`     Path: ${dt.path}`);
  if (dt.freeSpace) console.log(`     Free Space: ${dt.freeSpace}`);
  if (dt.error) console.log(`     Error: ${dt.error}`);
  console.log('');

  // Google Drive
  const gd = status.googleDrive;
  const gdIcon = gd.mounted ? '✅' : (gd.processRunning ? '⚠️' : '❌');
  console.log(`  ${gdIcon} Google Drive`);
  console.log(`     Status: ${gd.status}`);
  if (gd.path) console.log(`     Path: ${gd.path}`);
  console.log(`     Process Running: ${gd.processRunning ? 'Yes' : 'No'}`);
  console.log(`     Service Account: ${gd.hasServiceAccount ? 'Found' : 'Not found'}`);
  console.log('');

  // iCloud
  const ic = status.iCloud;
  const icIcon = ic.available ? '✅' : '⚪';
  console.log(`  ${icIcon} iCloud Drive`);
  console.log(`     Status: ${ic.status}`);
  if (ic.path) console.log(`     Path: ${ic.path}`);
  console.log(`     Process Running: ${ic.processRunning ? 'Yes' : 'No'}`);
  console.log('');

  // OneDrive
  const od = status.oneDrive;
  const odIcon = od.mounted ? '✅' : (od.processRunning ? '⚠️' : '❌');
  console.log(`  ${odIcon} OneDrive`);
  console.log(`     Status: ${od.status}`);
  if (od.path) console.log(`     Path: ${od.path}`);
  console.log(`     Process Running: ${od.processRunning ? 'Yes' : 'No'}`);
  console.log('');
}

// ============================================================
// Help
// ============================================================
function printHelp() {
  console.log(`
Recent Files Scanner + Cloud Storage Status
Usage: node recent-files.js [options]

Options:
  --path <dir>       Directory to scan (default: /Volumes/DATA TAXI/FILES/01 THE DAVID DAILY SHOW/)
  --days <n>         Number of recent days to include (default: 7)
  --type <type>      File type filter: video|audio|all (default: video)
  --limit <n>        Limit results to N files
  --format <fmt>     Output format: json|csv|table (default: table)
  --sort <field>     Sort by: name|size|date (default: date)
  --ext <exts>       Comma-separated extensions (default: mp4,mov,mp3,wav,pdf,md,json)
  --min-size <size>  Minimum file size (e.g., 10MB, 1GB)
  --max-size <size>  Maximum file size (e.g., 500MB)
  --cloud            Check cloud storage status
  --help             Show this help message

Examples:
  node recent-files.js
  node recent-files.js --days 30 --type all --format json
  node recent-files.js --path ~/Desktop --days 14 --type video --sort size
  node recent-files.js --cloud --format table
  node recent-files.js --ext mp4,mov --min-size 100MB --max-size 2GB
`);
}

// ============================================================
// Main
// ============================================================
function main() {
  if (hasArg('help') || hasArg('h')) {
    printHelp();
    process.exit(0);
  }

  // Validate path
  if (!fs.existsSync(config.path)) {
    console.error(`Error: Path does not exist: ${config.path}`);
    console.error('Use --path to specify a valid directory.');
    process.exit(1);
  }

  const stat = fs.statSync(config.path);
  if (!stat.isDirectory()) {
    console.error(`Error: Path is not a directory: ${config.path}`);
    process.exit(1);
  }

  // Scan
  const startTime = Date.now();
  let results = scanDirectory(config.path, config);
  results = sortResults(results, config.sort);

  // Apply limit
  if (config.limit > 0) {
    results = results.slice(0, config.limit);
  }

  // Group by folder
  const groups = groupByFolder(results);

  // Check cloud status if requested
  let cloudStatus = null;
  if (config.cloud) {
    cloudStatus = checkCloudStatus();
  }

  // Output
  switch (config.format) {
    case 'json':
      outputJson(results, groups, cloudStatus);
      break;
    case 'csv':
      outputCsv(results);
      if (cloudStatus) printCloudStatus(cloudStatus);
      break;
    case 'table':
    default:
      outputTable(results, groups);
      if (cloudStatus) printCloudStatus(cloudStatus);
      break;
  }

  // Print scan time
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
  if (config.format === 'table') {
    console.log(`  ⏱  Scanned in ${elapsed}s`);
    console.log('');
  }
}

main();
