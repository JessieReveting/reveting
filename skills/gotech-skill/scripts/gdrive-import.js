#!/usr/bin/env node

/**
 * Google Drive Import Script
 * 
 * Searches and downloads files from Google Drive using service account credentials.
 * 
 * Usage:
 *   node gdrive-import.js --query "search term" [--folder ID] [--limit 10] [--download] [--output ./downloads] [--csv] [--list-folders]
 *   node gdrive-import.js --billion-dollar-skill
 *   node gdrive-import.js --list-folders
 */

const { google } = require('googleapis');
const fs = require('fs');
const path = require('path');
const os = require('os');

const CREDENTIALS_PATH = path.join(os.homedir(), '.hermes', 'auth', 'google_sheets_credentials.json');
const DEFAULT_OUTPUT_DIR = path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'startup', 'assets', 'downloads');
const BILLION_DOLLAR_SKILL_DIR = path.join(os.homedir(), 'Documents', 'GoTechSolutions', 'startup', 'assets', 'billion-dollar-skill');

// Rate limiting configuration
const RATE_LIMIT_DELAY_MS = 100; // ms between API calls
const MAX_RETRIES = 3;
const RETRY_BACKOFF_MS = 1000;

/**
 * Parse CLI arguments into an options object
 */
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    query: null,
    folder: null,
    limit: 100,
    download: false,
    output: DEFAULT_OUTPUT_DIR,
    csv: false,
    listFolders: false,
    billionDollarSkill: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--query':
        options.query = args[++i];
        break;
      case '--folder':
        options.folder = args[++i];
        break;
      case '--limit':
        options.limit = parseInt(args[++i], 10) || 100;
        break;
      case '--download':
        options.download = true;
        break;
      case '--output':
        options.output = args[++i];
        break;
      case '--csv':
        options.csv = true;
        break;
      case '--list-folders':
        options.listFolders = true;
        break;
      case '--billion-dollar-skill':
        options.billionDollarSkill = true;
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
Google Drive Import Script

Usage:
  node gdrive-import.js [options]

Options:
  --query <term>          Search for files matching name or mime type
  --folder <id>           Restrict search to a specific folder ID
  --limit <n>             Maximum number of results (default: 100)
  --download              Download matching files
  --output <path>         Output directory for downloads (default: ~/Documents/GoTechSolutions/startup/assets/downloads)
  --csv                   Export file list as CSV
  --list-folders          List all accessible folders with their IDs
  --billion-dollar-skill  Import files matching 'Billion Dollar Skill'
  --help, -h              Show this help message

Examples:
  node gdrive-import.js --query "report" --limit 20
  node gdrive-import.js --query "Billion Dollar Skill" --download --output ./my-files
  node gdrive-import.js --billion-dollar-skill --download
  node gdrive-import.js --list-folders
  node gdrive-import.js --query "spreadsheet" --folder "1a2b3c" --csv
`);
}

/**
 * Load service account credentials from file
 */
function loadCredentials() {
  if (!fs.existsSync(CREDENTIALS_PATH)) {
    throw new Error(`Credentials file not found at: ${CREDENTIALS_PATH}`);
  }

  const content = fs.readFileSync(CREDENTIALS_PATH, 'utf8');
  const credentials = JSON.parse(content);

  if (credentials.type !== 'service_account') {
    throw new Error('Credentials must be a service account key');
  }

  return credentials;
}

/**
 * Create an authenticated Google Drive client
 */
async function createDriveClient() {
  const credentials = loadCredentials();
  
  const auth = new google.auth.GoogleAuth({
    credentials,
    scopes: ['https://www.googleapis.com/auth/drive.readonly'],
  });

  const drive = google.drive({ version: 'v3', auth });
  return drive;
}

/**
 * Sleep for rate limiting
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Execute with retry logic for rate limiting and transient errors
 */
async function withRetry(fn, retries = MAX_RETRIES) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      const isRateLimit = error.code === 429 || error.code === 403;
      const isServerError = error.code >= 500;
      
      if (attempt < retries && (isRateLimit || isServerError)) {
        const delay = RETRY_BACKOFF_MS * Math.pow(2, attempt - 1);
        console.warn(`Rate limited or server error, retrying in ${delay}ms (attempt ${attempt}/${retries})...`);
        await sleep(delay);
      } else {
        throw error;
      }
    }
  }
}

/**
 * Build a search query string for Google Drive API
 */
function buildSearchQuery(options) {
  const conditions = [];

  // Exclude trashed files
  conditions.push('trashed = false');

  // Name/mime type query
  if (options.query) {
    const term = options.query.replace(/'/g, "\\'");
    // Try both name contains and fullText contains
    conditions.push(`(name contains '${term}' or fullText contains '${term}')`);
  }

  // Folder restriction
  if (options.folder) {
    conditions.push(`'${options.folder}' in parents`);
  }

  return conditions.join(' and ');
}

/**
 * Search for files in Google Drive
 */
async function searchFiles(drive, options) {
  const query = buildSearchQuery(options);
  const allFiles = [];
  let pageToken = null;

  console.log(`Searching Google Drive...${query ? `\n  Query: ${query}` : ''}`);

  do {
    const response = await withRetry(async () => {
      const params = {
        q: query,
        fields: 'nextPageToken, files(id, name, mimeType, size, modifiedTime, parents, webViewLink)',
        pageSize: Math.min(100, options.limit - allFiles.length),
        orderBy: 'modifiedTime desc',
      };

      if (pageToken) {
        params.pageToken = pageToken;
      }

      if (options.folder) {
        params.corpora = 'allDrives';
        params.includeItemsFromAllDrives = true;
        params.supportsAllDrives = true;
      }

      return drive.files.list(params);
    });

    const files = response.data.files || [];
    allFiles.push(...files);
    pageToken = response.data.nextPageToken || null;

    // Rate limiting between pages
    if (pageToken) {
      await sleep(RATE_LIMIT_DELAY_MS);
    }

  } while (pageToken && allFiles.length < options.limit);

  return allFiles.slice(0, options.limit);
}

/**
 * List all accessible folders
 */
async function listFolders(drive) {
  const query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false";
  const allFolders = [];
  let pageToken = null;

  console.log('Listing all accessible folders...\n');

  do {
    const response = await withRetry(async () => {
      const params = {
        q: query,
        fields: 'nextPageToken, files(id, name, modifiedTime)',
        pageSize: 100,
        orderBy: 'name',
      };

      if (pageToken) {
        params.pageToken = pageToken;
      }

      return drive.files.list(params);
    });

    const folders = response.data.files || [];
    allFolders.push(...folders);
    pageToken = response.data.nextPageToken || null;

    if (pageToken) {
      await sleep(RATE_LIMIT_DELAY_MS);
    }

  } while (pageToken);

  return allFolders;
}

/**
 * Download a single file from Google Drive
 */
async function downloadFile(drive, file, outputDir) {
  const filePath = path.join(outputDir, file.name);
  
  // Handle name collisions
  let finalPath = filePath;
  let counter = 1;
  const ext = path.extname(file.name);
  const baseName = path.basename(file.name, ext);
  
  while (fs.existsSync(finalPath)) {
    finalPath = path.join(outputDir, `${baseName}_${counter}${ext}`);
    counter++;
  }

  console.log(`  Downloading: ${file.name} -> ${path.basename(finalPath)}`);

  const dest = fs.createWriteStream(finalPath);
  
  const response = await withRetry(async () => {
    return drive.files.get(
      { fileId: file.id, alt: 'media' },
      { responseType: 'stream' }
    );
  });

  return new Promise((resolve, reject) => {
    let downloadedSize = 0;
    
    response.data
      .on('data', (chunk) => {
        downloadedSize += chunk.length;
      })
      .on('end', () => {
        dest.close();
        resolve({
          path: finalPath,
          size: downloadedSize,
        });
      })
      .on('error', (err) => {
        dest.close();
        // Clean up partial file
        if (fs.existsSync(finalPath)) {
          fs.unlinkSync(finalPath);
        }
        reject(err);
      })
      .pipe(dest);
  });
}

/**
 * Download multiple files with rate limiting
 */
async function downloadFiles(drive, files, outputDir) {
  // Ensure output directory exists
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
    console.log(`Created output directory: ${outputDir}`);
  }

  const results = [];
  const errors = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    
    // Skip folders
    if (file.mimeType === 'application/vnd.google-apps.folder') {
      console.log(`  Skipping folder: ${file.name}`);
      continue;
    }

    try {
      const result = await downloadFile(drive, file, outputDir);
      results.push({
        file: file.name,
        id: file.id,
        path: result.path,
        size: result.size,
        status: 'success',
      });
    } catch (error) {
      errors.push({
        file: file.name,
        id: file.id,
        error: error.message,
        status: 'failed',
      });
    }

    // Rate limiting between downloads
    if (i < files.length - 1) {
      await sleep(RATE_LIMIT_DELAY_MS);
    }
  }

  return { results, errors };
}

/**
 * Format file list as JSON
 */
function formatAsJSON(files) {
  return files.map(file => ({
    name: file.name,
    id: file.id,
    mimeType: file.mimeType,
    size: file.size || null,
    modifiedTime: file.modifiedTime,
    webViewLink: file.webViewLink || null,
  }));
}

/**
 * Format file list as CSV
 */
function formatAsCSV(files) {
  const headers = ['name', 'id', 'mimeType', 'size', 'modifiedTime', 'webViewLink'];
  const rows = [headers.join(',')];

  for (const file of files) {
    const row = headers.map(header => {
      let value = file[header] || '';
      // Escape CSV values containing commas, quotes, or newlines
      if (typeof value === 'string' && (value.includes(',') || value.includes('"') || value.includes('\n'))) {
        value = `"${value.replace(/"/g, '""')}"`;
      }
      return value;
    });
    rows.push(row.join(','));
  }

  return rows.join('\n');
}

/**
 * Handle the Billion Dollar Skill import
 */
async function importBillionDollarSkill(drive, options) {
  console.log('=== Billion Dollar Skill Import ===\n');

  // Search for files matching Billion Dollar Skill patterns
  const queries = [
    'Billion Dollar Skill',
    'BillionDollarSkill',
    'BillionDollar',
  ];

  const allFiles = [];
  const seenIds = new Set();

  for (const query of queries) {
    const searchOptions = { ...options, query };
    const files = await searchFiles(drive, { ...searchOptions, limit: 50 });
    
    for (const file of files) {
      if (!seenIds.has(file.id)) {
        seenIds.add(file.id);
        allFiles.push(file);
      }
    }

    // Rate limiting between searches
    await sleep(RATE_LIMIT_DELAY_MS);
  }

  console.log(`\nFound ${allFiles.length} unique files matching 'Billion Dollar Skill'\n`);

  if (allFiles.length === 0) {
    console.log('No files found. Try --list-folders to find the correct folder ID.');
    return [];
  }

  // Display found files
  const jsonOutput = formatAsJSON(allFiles);
  console.log('Files found:');
  console.log(JSON.stringify(jsonOutput, null, 2));

  // Download if requested
  if (options.download) {
    console.log(`\nDownloading to: ${BILLION_DOLLAR_SKILL_DIR}`);
    const { results, errors } = await downloadFiles(drive, allFiles, BILLION_DOLLAR_SKILL_DIR);
    
    console.log(`\nDownload complete: ${results.length} succeeded, ${errors.length} failed`);
    
    if (errors.length > 0) {
      console.log('\nFailed downloads:');
      errors.forEach(e => console.log(`  - ${e.file}: ${e.error}`));
    }
  }

  // Export CSV if requested
  if (options.csv) {
    const csvPath = path.join(BILLION_DOLLAR_SKILL_DIR, 'billion-dollar-skill-files.csv');
    fs.mkdirSync(BILLION_DOLLAR_SKILL_DIR, { recursive: true });
    fs.writeFileSync(csvPath, formatAsCSV(allFiles));
    console.log(`\nCSV exported to: ${csvPath}`);
  }

  return allFiles;
}

/**
 * Main execution
 */
async function main() {
  const options = parseArgs();

  try {
    // Create authenticated Drive client
    const drive = await createDriveClient();

    // Handle --list-folders
    if (options.listFolders) {
      const folders = await listFolders(drive);
      
      if (folders.length === 0) {
        console.log('No accessible folders found. Make sure the service account has access to the Drive.');
        return;
      }

      console.log(`Found ${folders.length} folders:\n`);
      console.log('Name'.padEnd(50) + 'ID'.padEnd(40) + 'Modified');
      console.log('-'.repeat(110));
      
      for (const folder of folders) {
        const name = folder.name.length > 48 ? folder.name.substring(0, 48) + '..' : folder.name;
        console.log(name.padEnd(50) + folder.id.padEnd(40) + (folder.modifiedTime || 'N/A'));
      }
      
      console.log('\nUse --folder <ID> to search within a specific folder.');
      return;
    }

    // Handle --billion-dollar-skill
    if (options.billionDollarSkill) {
      await importBillionDollarSkill(drive, { ...options, download: true });
      return;
    }

    // Standard search
    if (!options.query) {
      console.error('Error: --query is required (or use --billion-dollar-skill or --list-folders)');
      printHelp();
      process.exit(1);
    }

    const files = await searchFiles(drive, options);

    if (files.length === 0) {
      console.log('\nNo files found matching your query.');
      return;
    }

    // Output file list as JSON
    const jsonOutput = formatAsJSON(files);
    console.log(`\nFound ${files.length} files:\n`);
    console.log(JSON.stringify(jsonOutput, null, 2));

    // Export CSV if requested
    if (options.csv) {
      const csvOutput = formatAsCSV(files);
      const csvPath = path.join(options.output, 'file-list.csv');
      
      if (!fs.existsSync(options.output)) {
        fs.mkdirSync(options.output, { recursive: true });
      }
      
      fs.writeFileSync(csvPath, csvOutput);
      console.log(`\nCSV exported to: ${csvPath}`);
    }

    // Download if requested
    if (options.download) {
      console.log(`\nDownloading to: ${options.output}`);
      const { results, errors } = await downloadFiles(drive, files, options.output);
      
      console.log(`\nDownload complete: ${results.length} succeeded, ${errors.length} failed`);
      
      if (errors.length > 0) {
        console.log('\nFailed downloads:');
        errors.forEach(e => console.log(`  - ${e.file}: ${e.error}`));
      }
    }

  } catch (error) {
    if (error.code === 401 || error.code === 403) {
      console.error('\nAuthentication error: The service account does not have access.');
      console.error('Make sure:');
      console.error('  1. The Google Drive API is enabled in your Google Cloud project');
      console.error('  2. The service account email has access to the files/folders');
      console.error(`  3. Service account: ${JSON.parse(fs.readFileSync(CREDENTIALS_PATH, 'utf8')).client_email}`);
    } else if (error.code === 404) {
      console.error('\nFolder or file not found. Use --list-folders to find valid folder IDs.');
    } else {
      console.error(`\nError: ${error.message}`);
    }
    
    process.exit(1);
  }
}

// Run main
main();
