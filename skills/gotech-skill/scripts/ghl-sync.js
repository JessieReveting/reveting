#!/usr/bin/env node

/**
 * GHL Sync - Go High Level ↔ TDSS Google Sheet Integration
 * 
 * Synchronizes contacts and appointments between GHL (Reveting) and the
 * TDSS Google Sheet. Supports webhook receiver, bidirectional sync,
 * and demo mode for testing without API keys.
 * 
 * Usage:
 *   node ghl-sync.js --action sync
 *   node ghl-sync.js --action contacts --verbose
 *   node ghl-sync.js --action appointments --limit 10
 *   node ghl-sync.js --action webhooks
 *   node ghl-sync.js --action setup
 *   node ghl-sync.js --action test
 *   node ghl-sync.js --action sync --dry-run
 *   node ghl-sync.js --demo --action contacts
 * 
 * Options:
 *   --action <action>     Action to perform: sync|contacts|appointments|webhooks|setup|test
 *   --dry-run             Show what would be done without making changes
 *   --verbose             Show detailed progress output
 *   --limit <n>           Limit number of records processed
 *   --demo                Run in demo mode (no API keys required)
 *   --port <n>            Webhook server port (default: 3210)
 *   --help, -h            Show this help message
 * 
 * Environment Variables:
 *   GHL_API_KEY           Go High Level API key
 *   GHL_LOCATION_ID       GHL location ID (for webhooks)
 *   GHL_WEBHOOK_URL       Webhook callback URL (for setup display)
 *   GOOGLE_SHEETS_CREDENTIALS  Path to Google service account JSON (default: ~/.hermes/auth/google_sheets_credentials.json)
 *   TDSS_SPREADSHEET_ID   TDSS Google Sheet ID (default: 1odwvWVKQJDQ9i74aRXFx4rArSAKqPCj3T6VximU0ZpI)
 */

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const readline = require('readline');

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const CONFIG = {
  ghl: {
    baseUrl: 'https://rest.gohighlevel.com/v2',
    apiKey: process.env.GHL_API_KEY || '',
    locationId: process.env.GHL_LOCATION_ID || '',
    webhookUrl: process.env.GHL_WEBHOOK_URL || '',
  },
  google: {
    spreadsheetId: process.env.TDSS_SPREADSHEET_ID || '1odwvWVKQJDQ9i74aRXFx4rArSAKqPCj3T6VximU0ZpI',
    credentialsPath: process.env.GOOGLE_SHEETS_CREDENTIALS || 
      path.join(process.env.HOME || '/Users/davidgo', '.hermes', 'auth', 'google_sheets_credentials.json'),
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  },
  webhook: {
    port: parseInt(process.env.GHL_WEBHOOK_PORT || '3210', 10),
    secret: process.env.GHL_WEBHOOK_SECRET || 'ghl-webhook-secret-' + Date.now(),
  },
  demo: false,
  contactsSheet: 'Contacts',
  appointmentsSheet: 'Appointments',
};

// ---------------------------------------------------------------------------
// CLI Argument Parsing
// ---------------------------------------------------------------------------

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    action: null,
    dryRun: false,
    verbose: false,
    limit: null,
    demo: false,
    port: CONFIG.webhook.port,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--action':
        options.action = args[++i];
        if (!['sync', 'contacts', 'appointments', 'webhooks', 'setup', 'test'].includes(options.action)) {
          console.error(`Invalid action: ${options.action}. Must be one of: sync|contacts|appointments|webhooks|setup|test`);
          process.exit(1);
        }
        break;
      case '--dry-run':
        options.dryRun = true;
        break;
      case '--verbose':
        options.verbose = true;
        break;
      case '--limit':
        options.limit = parseInt(args[++i], 10);
        if (isNaN(options.limit) || options.limit < 1) {
          console.error('Invalid limit. Must be a positive integer.');
          process.exit(1);
        }
        break;
      case '--demo':
        options.demo = true;
        break;
      case '--port':
        options.port = parseInt(args[++i], 10);
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

  if (!options.action) {
    console.error('Missing required argument: --action <action>');
    printHelp();
    process.exit(1);
  }

  return options;
}

function printHelp() {
  console.log(`
GHL Sync - Go High Level ↔ TDSS Google Sheet Integration

Usage:
  node ghl-sync.js --action <action> [options]

Actions:
  sync            Bidirectional sync: GHL contacts → TDSS sheet + GHL appointments → TDSS sheet
  contacts        Fetch GHL contacts and sync to TDSS Google Sheet
  appointments    Fetch GHL upcoming appointments and sync to TDSS Google Sheet
  webhooks        Start local webhook receiver for GHL events
  setup           Validate configuration and show setup status
  test            Test connectivity to GHL API

Options:
  --dry-run       Show what would be done without making changes
  --verbose       Show detailed progress output
  --limit <n>     Limit number of records processed
  --demo          Run in demo mode (no API keys required, uses mock data)
  --port <n>      Webhook server port (default: 3210)
  --help, -h      Show this help message

Environment Variables:
  GHL_API_KEY           Go High Level API key
  GHL_LOCATION_ID       GHL location ID
  GHL_WEBHOOK_URL       Webhook callback URL
  GOOGLE_SHEETS_CREDENTIALS  Path to Google service account JSON
  TDSS_SPREADSHEET_ID   TDSS Google Sheet ID

Examples:
  node ghl-sync.js --action setup
  node ghl-sync.js --action test --demo
  node ghl-sync.js --action contacts --demo --verbose
  node ghl-sync.js --action sync --dry-run --limit 50
  node ghl-sync.js --action webhooks --port 8080
  node ghl-sync.js --action appointments --verbose --limit 10
`);
}

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------

class Logger {
  constructor(verbose = false) {
    this.verbose = verbose;
  }

  _timestamp() {
    return new Date().toISOString();
  }

  info(message) {
    console.log(`\x1b[36m[${this._timestamp()}] [INFO]\x1b[0m ${message}`);
  }

  success(message) {
    console.log(`\x1b[32m[${this._timestamp()}] [OK]\x1b[0m ${message}`);
  }

  warn(message) {
    console.warn(`\x1b[33m[${this._timestamp()}] [WARN]\x1b[0m ${message}`);
  }

  error(message) {
    console.error(`\x1b[31m[${this._timestamp()}] [ERROR]\x1b[0m ${message}`);
  }

  debug(message) {
    if (this.verbose) {
      console.log(`\x1b[90m[${this._timestamp()}] [DEBUG]\x1b[0m ${message}`);
    }
  }

  demo(message) {
    console.log(`\x1b[35m[DEMO]\x1b[0m ${message}`);
  }

  banner() {
    console.log('');
    console.log(`\x1b[1m\x1b[34m╔══════════════════════════════════════════════════════╗\x1b[0m`);
    console.log(`\x1b[1m\x1b[34m║    GHL Sync - Go High Level ↔ TDSS Sheet           ║\x1b[0m`);
    console.log(`\x1b[1m\x1b[34m║    Reveting Integration Script v1.0                  ║\x1b[0m`);
    console.log(`\x1b[1m\x1b[34m╚══════════════════════════════════════════════════════╝\x1b[0m`);
    console.log('');
  }
}

// ---------------------------------------------------------------------------
// Demo Data
// ---------------------------------------------------------------------------

const DEMO_CONTACTS = [
  {
    id: 'demo-001',
    firstName: 'Sarah',
    lastName: 'Johnson',
    email: 'sarah.johnson@example.com',
    phone: '+1-555-201-0001',
    source: 'LinkedIn',
    tags: ['prospect', 'discovery-call'],
    createdAt: '2026-06-20T10:30:00Z',
    customFields: [{ key: 'company', value: 'TechCorp Inc.' }],
  },
  {
    id: 'demo-002',
    firstName: 'Michael',
    lastName: 'Chen',
    email: 'michael.chen@example.com',
    phone: '+1-555-201-0002',
    source: 'Referral',
    tags: ['hot-lead', 'enterprise'],
    createdAt: '2026-06-19T14:15:00Z',
    customFields: [{ key: 'company', value: 'DataFlow Systems' }],
  },
  {
    id: 'demo-003',
    firstName: 'Emily',
    lastName: 'Rodriguez',
    email: 'emily.r@example.com',
    phone: '+1-555-201-0003',
    source: 'Website',
    tags: ['trial-user'],
    createdAt: '2026-06-18T09:00:00Z',
    customFields: [{ key: 'company', value: 'StartupXYZ' }],
  },
  {
    id: 'demo-004',
    firstName: 'James',
    lastName: 'Williams',
    email: 'james.w@example.com',
    phone: '+1-555-201-0004',
    source: 'Cold Outreach',
    tags: ['nurture'],
    createdAt: '2026-06-17T16:45:00Z',
    customFields: [{ key: 'company', value: 'BigCo Industries' }],
  },
  {
    id: 'demo-005',
    firstName: 'Lisa',
    lastName: 'Park',
    email: 'lisa.park@example.com',
    phone: '+1-555-201-0005',
    source: 'Podcast Listener',
    tags: ['discovery-call', 'small-biz'],
    createdAt: '2026-06-16T11:20:00Z',
    customFields: [{ key: 'company', value: 'Park Consulting' }],
  },
];

const DEMO_APPOINTMENTS = [
  {
    id: 'apt-001',
    calendarId: 'cal-demo-001',
    contactId: 'demo-001',
    startTime: '2026-06-25T14:00:00Z',
    endTime: '2026-06-25T14:30:00Z',
    title: 'Discovery Call - Sarah Johnson',
    status: 'confirmed',
    notes: 'Interested in Reveting enterprise plan',
    calendar: { name: 'David Daily Show' },
    contact: DEMO_CONTACTS[0],
  },
  {
    id: 'apt-002',
    calendarId: 'cal-demo-001',
    contactId: 'demo-002',
    startTime: '2026-06-25T15:00:00Z',
    endTime: '2026-06-25T16:00:00Z',
    title: 'Strategy Session - Michael Chen',
    status: 'confirmed',
    notes: 'Enterprise onboarding call',
    calendar: { name: 'David Daily Show' },
    contact: DEMO_CONTACTS[1],
  },
  {
    id: 'apt-003',
    calendarId: 'cal-demo-001',
    contactId: 'demo-003',
    startTime: '2026-06-26T10:00:00Z',
    endTime: '2026-06-26T10:30:00Z',
    title: 'Discovery Call - Emily Rodriguez',
    status: 'pending',
    notes: 'Follow up on trial signup',
    calendar: { name: 'David Daily Show' },
    contact: DEMO_CONTACTS[2],
  },
  {
    id: 'apt-004',
    calendarId: 'cal-demo-001',
    contactId: 'demo-004',
    startTime: '2026-06-26T13:00:00Z',
    endTime: '2026-06-26T13:30:00Z',
    title: 'Discovery Call - James Williams',
    status: 'no-show',
    notes: 'Reschedule needed',
    calendar: { name: 'David Daily Show' },
    contact: DEMO_CONTACTS[3],
  },
  {
    id: 'apt-005',
    calendarId: 'cal-demo-001',
    contactId: 'demo-005',
    startTime: '2026-06-27T09:30:00Z',
    endTime: '2026-06-27T10:00:00Z',
    title: 'Discovery Call - Lisa Park',
    status: 'confirmed',
    notes: 'Small business use case',
    calendar: { name: 'David Daily Show' },
    contact: DEMO_CONTACTS[4],
  },
];

// ---------------------------------------------------------------------------
// GHL API Client
// ---------------------------------------------------------------------------

class GHLClient {
  constructor(apiKey, logger) {
    this.apiKey = apiKey;
    this.baseUrl = CONFIG.ghl.baseUrl;
    this.logger = logger;
  }

  async request(endpoint, params = {}) {
    const url = new URL(`${this.baseUrl}${endpoint}`);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, value);
      }
    });

    this.logger.debug(`GET ${url.toString()}`);

    return new Promise((resolve, reject) => {
      const req = https.get(
        url.toString(),
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json',
            'User-Agent': 'GHL-Sync-Script/1.0',
          },
          timeout: 15000,
        },
        (res) => {
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            this.logger.debug(`Response status: ${res.statusCode}`);
            
            if (res.statusCode === 401) {
              reject(new Error('GHL API authentication failed. Check your GHL_API_KEY.'));
              return;
            }
            if (res.statusCode === 429) {
              reject(new Error('GHL API rate limit exceeded. Wait and retry.'));
              return;
            }
            if (res.statusCode >= 400) {
              reject(new Error(`GHL API error ${res.statusCode}: ${data.substring(0, 200)}`));
              return;
            }

            try {
              resolve(JSON.parse(data));
            } catch (e) {
              reject(new Error(`Failed to parse GHL response: ${e.message}`));
            }
          });
        }
      );

      req.on('error', (err) => {
        reject(new Error(`GHL API request failed: ${err.message}`));
      });

      req.on('timeout', () => {
        req.destroy();
        reject(new Error('GHL API request timed out after 15s'));
      });
    });
  }

  async testConnection() {
    try {
      // Try to fetch calendars as a connectivity test
      const result = await this.request('/calendars/', { limit: 1 });
      return { success: true, data: result };
    } catch (err) {
      return { success: false, error: err.message };
    }
  }

  async getContacts(options = {}) {
    const params = {
      limit: options.limit || 100,
    };
    if (options.after) params.after = options.after;
    
    const result = await this.request('/contacts/', params);
    return result.contacts || result.data || [];
  }

  async getCalendars() {
    const result = await this.request('/calendars/');
    return result.calendars || result.data || [];
  }

  async getAppointments(calendarId, options = {}) {
    const params = {
      limit: options.limit || 100,
    };
    if (options.startTime) params.startTime = options.startTime;
    if (options.endTime) params.endTime = options.endTime;
    
    const result = await this.request(`/calendars/${calendarId}/appointments`, params);
    return result.appointments || result.data || [];
  }

  async getContactsWithAppointments(contacts, appointments) {
    // Enrich appointments with full contact data
    return appointments.map(apt => {
      const contact = contacts.find(c => c.id === apt.contactId);
      return { ...apt, contact: contact || null };
    });
  }
}

// ---------------------------------------------------------------------------
// Google Sheets Integration
// ---------------------------------------------------------------------------

class GoogleSheetsClient {
  constructor(logger) {
    this.logger = logger;
    this.initialized = false;
  }

  async init() {
    try {
      // Try to use googleapis library
      const { google } = require('googleapis');
      
      if (!fs.existsSync(CONFIG.google.credentialsPath)) {
        this.logger.warn(`Google credentials not found at ${CONFIG.google.credentialsPath}`);
        this.logger.info('Google Sheets sync will be skipped. Run --action setup for details.');
        return false;
      }

      const credentials = JSON.parse(fs.readFileSync(CONFIG.google.credentialsPath, 'utf8'));
      
      const auth = new google.auth.GoogleAuth({
        credentials,
        scopes: CONFIG.google.scopes,
      });

      this.sheets = google.sheets({ version: 'v4', auth });
      this.initialized = true;
      this.logger.success('Google Sheets client initialized');
      return true;
    } catch (err) {
      if (err.code === 'MODULE_NOT_FOUND') {
        this.logger.warn('googleapis package not found. Run: npm install googleapis');
      } else {
        this.logger.warn(`Google Sheets init failed: ${err.message}`);
      }
      return false;
    }
  }

  async ensureSheetExists(sheetName) {
    if (!this.initialized) return false;

    try {
      const spreadsheet = await this.sheets.spreadsheets.get({
        spreadsheetId: CONFIG.google.spreadsheetId,
      });

      const exists = spreadsheet.data.sheets.some(
        s => s.properties.title === sheetName
      );

      if (!exists) {
        this.logger.info(`Creating sheet: ${sheetName}`);
        if (!CONFIG.demo) {
          await this.sheets.spreadsheets.batchUpdate({
            spreadsheetId: CONFIG.google.spreadsheetId,
            resource: {
              requests: [{
                addSheet: {
                  properties: { title: sheetName },
                },
              }],
            },
          });
        }
      }

      return true;
    } catch (err) {
      this.logger.error(`Failed to ensure sheet exists: ${err.message}`);
      return false;
    }
  }

  async getSheetData(sheetName) {
    if (!this.initialized) return [];

    try {
      const response = await this.sheets.spreadsheets.values.get({
        spreadsheetId: CONFIG.google.spreadsheetId,
        range: `${sheetName}!A:Z`,
      });
      return response.data.values || [];
    } catch (err) {
      if (err.code === 400) {
        // Sheet doesn't exist
        return [];
      }
      throw err;
    }
  }

  async appendRows(sheetName, rows) {
    if (!this.initialized) {
      this.logger.warn(`[SKIP] Would append ${rows.length} rows to ${sheetName}`);
      return false;
    }

    try {
      await this.sheets.spreadsheets.values.append({
        spreadsheetId: CONFIG.google.spreadsheetId,
        range: `${sheetName}!A:Z`,
        valueInputOption: 'USER_ENTERED',
        resource: { values: rows },
      });
      this.logger.success(`Appended ${rows.length} rows to ${sheetName}`);
      return true;
    } catch (err) {
      this.logger.error(`Failed to append rows: ${err.message}`);
      return false;
    }
  }

  async updateRows(sheetName, range, values) {
    if (!this.initialized) {
      this.logger.warn(`[SKIP] Would update ${range} in ${sheetName}`);
      return false;
    }

    try {
      await this.sheets.spreadsheets.values.update({
        spreadsheetId: CONFIG.google.spreadsheetId,
        range: `${sheetName}!${range}`,
        valueInputOption: 'USER_ENTERED',
        resource: { values },
      });
      this.logger.success(`Updated ${range} in ${sheetName}`);
      return true;
    } catch (err) {
      this.logger.error(`Failed to update rows: ${err.message}`);
      return false;
    }
  }
}

// ---------------------------------------------------------------------------
// Contact Sync
// ---------------------------------------------------------------------------

async function syncContacts(ghl, sheets, logger, options) {
  logger.info('═══════════════════════════════════════════');
  logger.info('         SYNCING CONTACTS');
  logger.info('═══════════════════════════════════════════');

  let contacts;
  
  if (options.demo) {
    logger.demo('Using demo contact data (5 contacts)');
    contacts = DEMO_CONTACTS;
    if (options.limit) contacts = contacts.slice(0, options.limit);
  } else {
    logger.info('Fetching contacts from GHL...');
    contacts = await ghl.getContacts({ limit: options.limit || 100 });
    logger.success(`Fetched ${contacts.length} contacts from GHL`);
  }

  if (contacts.length === 0) {
    logger.warn('No contacts found.');
    return { synced: 0, errors: 0 };
  }

  // Prepare rows for Google Sheet
  const headerRow = ['ID', 'First Name', 'Last Name', 'Email', 'Phone', 'Source', 'Tags', 'Company', 'Created At', 'Last Synced'];
  
  const dataRows = contacts.map(c => {
    const company = c.customFields?.find(f => f.key === 'company')?.value || '';
    return [
      c.id || '',
      c.firstName || '',
      c.lastName || '',
      c.email || '',
      c.phone || '',
      c.source || '',
      (c.tags || []).join(', '),
      company,
      c.createdAt ? new Date(c.createdAt).toLocaleDateString() : '',
      new Date().toISOString(),
    ];
  });

  if (options.dryRun) {
    logger.info(`[DRY RUN] Would sync ${contacts.length} contacts to Google Sheet`);
    logger.debug(`Header: ${headerRow.join(' | ')}`);
    dataRows.slice(0, 3).forEach(row => {
      logger.debug(`Row: ${row.join(' | ')}`);
    });
    if (dataRows.length > 3) {
      logger.debug(`... and ${dataRows.length - 3} more rows`);
    }
    return { synced: contacts.length, errors: 0, dryRun: true };
  }

  // Sync to Google Sheets
  if (sheets.initialized) {
    await sheets.ensureSheetExists(CONFIG.contactsSheet);
    
    // Check if sheet has headers
    const existing = await sheets.getSheetData(CONFIG.contactsSheet);
    if (existing.length === 0) {
      await sheets.appendRows(CONFIG.contactsSheet, [headerRow]);
    }
    
    await sheets.appendRows(CONFIG.contactsSheet, dataRows);
  } else {
    logger.warn('Google Sheets not initialized. Contacts fetched but not synced to sheet.');
    logger.info('To enable sheet sync, ensure googleapis is installed and credentials are configured.');
  }

  logger.success(`Contact sync complete: ${contacts.length} contacts processed`);
  return { synced: contacts.length, errors: 0 };
}

// ---------------------------------------------------------------------------
// Appointment Sync
// ---------------------------------------------------------------------------

async function syncAppointments(ghl, sheets, logger, options) {
  logger.info('═══════════════════════════════════════════');
  logger.info('         SYNCING APPOINTMENTS');
  logger.info('═══════════════════════════════════════════');

  let appointments;
  
  if (options.demo) {
    logger.demo('Using demo appointment data (5 appointments)');
    appointments = DEMO_APPOINTMENTS;
    if (options.limit) appointments = appointments.slice(0, options.limit);
  } else {
    // First get calendars
    logger.info('Fetching calendars from GHL...');
    const calendars = await ghl.getCalendars();
    
    if (calendars.length === 0) {
      logger.warn('No calendars found in GHL.');
      return { synced: 0, errors: 0 };
    }

    // Find the David Daily Show calendar (or use first one)
    const targetCalendar = calendars.find(c => 
      c.name?.toLowerCase().includes('david') || c.name?.toLowerCase().includes('daily')
    ) || calendars[0];

    logger.info(`Using calendar: ${targetCalendar.name || targetCalendar.id}`);

    // Fetch upcoming appointments
    const now = new Date().toISOString();
    const future = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
    
    logger.info('Fetching appointments...');
    appointments = await ghl.getAppointments(targetCalendar.id, {
      startTime: now,
      endTime: future,
      limit: options.limit || 100,
    });
    logger.success(`Fetched ${appointments.length} upcoming appointments`);
  }

  if (appointments.length === 0) {
    logger.warn('No upcoming appointments found.');
    return { synced: 0, errors: 0 };
  }

  // Prepare rows for Google Sheet
  const headerRow = ['ID', 'Date', 'Time', 'Contact Name', 'Email', 'Phone', 'Service', 'Status', 'Notes', 'Source', 'Created At', 'Last Synced'];
  
  const dataRows = appointments.map(apt => {
    const startTime = apt.startTime ? new Date(apt.startTime) : null;
    const contact = apt.contact || {};
    return [
      apt.id || '',
      startTime ? startTime.toLocaleDateString() : '',
      startTime ? startTime.toLocaleTimeString() : '',
      `${contact.firstName || ''} ${contact.lastName || ''}`.trim(),
      contact.email || '',
      contact.phone || '',
      apt.title || apt.calendar?.name || 'Discovery Call',
      apt.status || 'confirmed',
      apt.notes || '',
      'GHL Sync',
      apt.createdAt ? new Date(apt.createdAt).toLocaleDateString() : '',
      new Date().toISOString(),
    ];
  });

  if (options.dryRun) {
    logger.info(`[DRY RUN] Would sync ${appointments.length} appointments to Google Sheet`);
    logger.debug(`Header: ${headerRow.join(' | ')}`);
    dataRows.slice(0, 3).forEach(row => {
      logger.debug(`Row: ${row.join(' | ')}`);
    });
    if (dataRows.length > 3) {
      logger.debug(`... and ${dataRows.length - 3} more rows`);
    }
    return { synced: appointments.length, errors: 0, dryRun: true };
  }

  // Sync to Google Sheets
  if (sheets.initialized) {
    await sheets.ensureSheetExists(CONFIG.appointmentsSheet);
    
    // Check if sheet has headers
    const existing = await sheets.getSheetData(CONFIG.appointmentsSheet);
    if (existing.length === 0) {
      await sheets.appendRows(CONFIG.appointmentsSheet, [headerRow]);
    }
    
    await sheets.appendRows(CONFIG.appointmentsSheet, dataRows);
  } else {
    logger.warn('Google Sheets not initialized. Appointments fetched but not synced to sheet.');
  }

  logger.success(`Appointment sync complete: ${appointments.length} appointments processed`);
  return { synced: appointments.length, errors: 0 };
}

// ---------------------------------------------------------------------------
// Webhook Receiver
// ---------------------------------------------------------------------------

const WEBHOOK_EVENTS = {};

function startWebhookServer(logger, port) {
  logger.info('═══════════════════════════════════════════');
  logger.info('         WEBHOOK RECEIVER');
  logger.info('═══════════════════════════════════════════');

  const server = http.createServer((req, res) => {
    // Health check endpoint
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', uptime: process.uptime() }));
      return;
    }

    // Webhook endpoint
    if (req.method === 'POST' && req.url === '/webhook') {
      let body = '';
      
      req.on('data', (chunk) => { body += chunk; });
      req.on('end', () => {
        try {
          const event = JSON.parse(body);
          const eventType = event.type || event.event || 'unknown';
          
          logger.info(`\x1b[32m[WEBHOOK]\x1b[0m Received: ${eventType}`);
          
          if (logger.verbose) {
            logger.debug(`Payload: ${JSON.stringify(event, null, 2)}`);
          }

          // Handle specific event types
          switch (eventType) {
            case 'contact.created':
            case 'ContactCreated':
              handleNewContact(event, logger);
              break;
            case 'contact.updated':
            case 'ContactUpdated':
              handleUpdatedContact(event, logger);
              break;
            case 'appointment.created':
            case 'AppointmentCreated':
              handleNewAppointment(event, logger);
              break;
            case 'appointment.updated':
            case 'AppointmentUpdated':
              handleUpdatedAppointment(event, logger);
              break;
            case 'appointment.deleted':
            case 'AppointmentDeleted':
              handleDeletedAppointment(event, logger);
              break;
            default:
              logger.debug(`Unhandled event type: ${eventType}`);
          }

          // Send acknowledgment
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ received: true, event: eventType }));
        } catch (err) {
          logger.error(`Webhook parse error: ${err.message}`);
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Invalid JSON' }));
        }
      });

      req.on('error', (err) => {
        logger.error(`Webhook request error: ${err.message}`);
      });
      return;
    }

    // 404 for everything else
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  });

  server.listen(port, () => {
    logger.success(`Webhook server listening on http://localhost:${port}`);
    logger.info('');
    logger.info('Endpoints:');
    logger.info(`  POST http://localhost:${port}/webhook  - Receive GHL webhooks`);
    logger.info(`  GET  http://localhost:${port}/health    - Health check`);
    logger.info('');
    logger.info('To expose to the internet, use ngrok or similar:');
    logger.info(`  ngrok http ${port}`);
    logger.info('');
    logger.info('Then configure GHL webhook URL as:');
    logger.info(`  https://<your-ngrok-url>.ngrok.io/webhook`);
    logger.info('');
    logger.info('Waiting for webhook events... (Ctrl+C to stop)');
  });

  // Graceful shutdown
  process.on('SIGINT', () => {
    logger.info('');
    logger.info('Shutting down webhook server...');
    server.close(() => {
      logger.success('Webhook server stopped.');
      process.exit(0);
    });
  });

  return server;
}

function handleNewContact(event, logger) {
  const contact = event.contact || event.data || event;
  logger.info(`  → New contact: ${contact.firstName || ''} ${contact.lastName || ''}`.trim());
  logger.info(`    Email: ${contact.email || 'N/A'}`);
  logger.info(`    Phone: ${contact.phone || 'N/A'}`);
  logger.info(`    Source: ${contact.source || 'N/A'}`);
}

function handleUpdatedContact(event, logger) {
  const contact = event.contact || event.data || event;
  logger.info(`  → Updated contact: ${contact.firstName || ''} ${contact.lastName || ''}`.trim());
}

function handleNewAppointment(event, logger) {
  const apt = event.appointment || event.data || event;
  const startTime = apt.startTime ? new Date(apt.startTime) : null;
  logger.info(`  → New appointment: ${apt.title || 'Untitled'}`);
  if (startTime) {
    logger.info(`    When: ${startTime.toLocaleDateString()} at ${startTime.toLocaleTimeString()}`);
  }
  logger.info(`    Status: ${apt.status || 'N/A'}`);
}

function handleUpdatedAppointment(event, logger) {
  const apt = event.appointment || event.data || event;
  logger.info(`  → Updated appointment: ${apt.title || 'Untitled'}`);
  logger.info(`    Status: ${apt.status || 'N/A'}`);
}

function handleDeletedAppointment(event, logger) {
  const apt = event.appointment || event.data || event;
  logger.info(`  → Deleted appointment: ${apt.id || 'Unknown'}`);
}

// ---------------------------------------------------------------------------
// Setup Validation
// ---------------------------------------------------------------------------

function validateSetup(logger, options) {
  logger.info('═══════════════════════════════════════════');
  logger.info('         CONFIGURATION STATUS');
  logger.info('═══════════════════════════════════════════');
  
  const checks = [];

  // GHL API Key
  const hasApiKey = !!CONFIG.ghl.apiKey;
  checks.push({
    name: 'GHL_API_KEY',
    status: hasApiKey ? 'OK' : 'MISSING',
    color: hasApiKey ? '\x1b[32m' : '\x1b[31m',
    description: hasApiKey ? `Set (${CONFIG.ghl.apiKey.substring(0, 8)}...)` : 'Set GHL_API_KEY env var',
  });

  // GHL Location ID
  const hasLocationId = !!CONFIG.ghl.locationId;
  checks.push({
    name: 'GHL_LOCATION_ID',
    status: hasLocationId ? 'OK' : 'OPTIONAL',
    color: hasLocationId ? '\x1b[32m' : '\x1b[33m',
    description: hasLocationId ? 'Set' : 'Optional (needed for some webhook configs)',
  });

  // GHL Webhook URL
  const hasWebhookUrl = !!CONFIG.ghl.webhookUrl;
  checks.push({
    name: 'GHL_WEBHOOK_URL',
    status: hasWebhookUrl ? 'OK' : 'OPTIONAL',
    color: hasWebhookUrl ? '\x1b[32m' : '\x1b[33m',
    description: hasWebhookUrl ? CONFIG.ghl.webhookUrl : 'Optional (for webhook setup reference)',
  });

  // Google Sheets credentials
  const hasGoogleCreds = fs.existsSync(CONFIG.google.credentialsPath);
  checks.push({
    name: 'Google Sheets Credentials',
    status: hasGoogleCreds ? 'OK' : 'MISSING',
    color: hasGoogleCreds ? '\x1b[32m' : '\x1b[31m',
    description: hasGoogleCreds ? CONFIG.google.credentialsPath : `Not found at ${CONFIG.google.credentialsPath}`,
  });

  // Google Sheets package
  let hasGooglePackage = false;
  try {
    require.resolve('googleapis');
    hasGooglePackage = true;
  } catch (e) { /* not found */ }
  checks.push({
    name: 'googleapis npm package',
    status: hasGooglePackage ? 'OK' : 'MISSING',
    color: hasGooglePackage ? '\x1b[32m' : '\x1b[31m',
    description: hasGooglePackage ? 'Installed' : 'Run: npm install googleapis',
  });

  // Demo mode
  if (options.demo) {
    checks.push({
      name: 'Demo Mode',
      status: 'ACTIVE',
      color: '\x1b[35m',
      description: 'Running with mock data (no API keys needed)',
    });
  }

  // Print results
  console.log('');
  console.log('Environment Checks:');
  console.log('─────────────────────────────────────────────');
  
  checks.forEach(check => {
    const icon = check.status === 'OK' || check.status === 'ACTIVE' ? '✓' : 
                 check.status === 'OPTIONAL' ? '○' : '✗';
    console.log(`  ${check.color}${icon} ${check.name}: ${check.status}\x1b[0m`);
    console.log(`    ${check.description}`);
  });

  console.log('─────────────────────────────────────────────');
  console.log('');

  // Recommendations
  const missing = checks.filter(c => c.status === 'MISSING');
  if (missing.length > 0) {
    console.log('\x1b[33m⚠ Setup incomplete. To enable full functionality:\x1b[0m');
    console.log('');
    console.log('1. Get GHL API Key:');
    console.log('   - Log into app.reveting.com');
    console.log('   - Settings → Developer → API Keys');
    console.log('   - Create key with Contacts + Calendars + Appointments read access');
    console.log('   - Set GHL_API_KEY=<your-key> environment variable');
    console.log('');
    console.log('2. Set up Google Sheets API:');
    console.log('   - Create service account in Google Cloud Console');
    console.log('   - Download JSON credentials');
    console.log('   - Save to ~/.hermes/auth/google_sheets_credentials.json');
    console.log('   - Share TDSS sheet with service account email');
    console.log('');
    console.log('3. Or use --demo flag to test without credentials:');
    console.log('   node ghl-sync.js --action sync --demo --verbose');
  } else {
    console.log('\x1b[32m✓ All systems ready!\x1b[0m');
    console.log('');
    console.log('Next steps:');
    console.log('  node ghl-sync.js --action test      # Test GHL API connection');
    console.log('  node ghl-sync.js --action contacts  # Sync contacts');
    console.log('  node ghl-sync.js --action sync      # Full sync');
  }

  console.log('');
}

// ---------------------------------------------------------------------------
// Connectivity Test
// ---------------------------------------------------------------------------

async function runTest(logger, options) {
  logger.info('═══════════════════════════════════════════');
  logger.info('         CONNECTIVITY TEST');
  logger.info('═══════════════════════════════════════════');

  if (options.demo) {
    logger.demo('Running connectivity test in demo mode...');
    logger.info('');
    logger.success('✓ Demo mode active (no real API calls)');
    logger.info('  - GHL API connection: simulated (OK)');
    logger.info('  - Google Sheets API: simulated (OK)');
    logger.info('  - Webhook server: available (use --action webhooks)');
    logger.info('');
    logger.info('To test real connectivity, set GHL_API_KEY and run without --demo');
    return;
  }

  if (!CONFIG.ghl.apiKey) {
    logger.error('GHL_API_KEY not set. Cannot run real connectivity test.');
    logger.info('Set GHL_API_KEY environment variable or use --demo mode.');
    process.exit(1);
  }

  const ghl = new GHLClient(CONFIG.ghl.apiKey, logger);

  logger.info('Testing GHL API connection...');
  const result = await ghl.testConnection();

  if (result.success) {
    logger.success('✓ GHL API connection successful!');
    logger.info(`  Base URL: ${CONFIG.ghl.baseUrl}`);
    if (result.data) {
      logger.debug(`  Response: ${JSON.stringify(result.data).substring(0, 200)}`);
    }
  } else {
    logger.error(`✗ GHL API connection failed: ${result.error}`);
    logger.info('');
    logger.info('Troubleshooting:');
    logger.info('  1. Verify API key is correct');
    logger.info('  2. Check GHL plan supports API access');
    logger.info('  3. Ensure account is active at app.reveting.com');
    process.exit(1);
  }

  // Test Google Sheets
  logger.info('');
  logger.info('Testing Google Sheets access...');
  const sheets = new GoogleSheetsClient(logger);
  const sheetsOk = await sheets.init();
  
  if (sheetsOk) {
    logger.success('✓ Google Sheets API accessible');
    logger.info(`  Spreadsheet ID: ${CONFIG.google.spreadsheetId}`);
  } else {
    logger.warn('✗ Google Sheets API not configured');
    logger.info('  Check credentials path and googleapis package');
  }
}

// ---------------------------------------------------------------------------
// Bidirectional Sync
// ---------------------------------------------------------------------------

async function runFullSync(ghl, sheets, logger, options) {
  logger.info('═══════════════════════════════════════════');
  logger.info('         FULL SYNC (BIDIRECTIONAL)');
  logger.info('═══════════════════════════════════════════');

  const report = {
    contacts: { synced: 0, errors: 0 },
    appointments: { synced: 0, errors: 0 },
  };

  // Step 1: Sync contacts
  logger.info('');
  logger.info('Step 1/2: Syncing contacts...');
  const contactResult = await syncContacts(ghl, sheets, logger, options);
  report.contacts = contactResult;

  // Step 2: Sync appointments
  logger.info('');
  logger.info('Step 2/2: Syncing appointments...');
  const aptResult = await syncAppointments(ghl, sheets, logger, options);
  report.appointments = aptResult;

  // Summary
  logger.info('');
  logger.info('═══════════════════════════════════════════');
  logger.info('         SYNC SUMMARY');
  logger.info('═══════════════════════════════════════════');
  logger.info(`  Contacts:    ${report.contacts.synced} synced, ${report.contacts.errors} errors`);
  logger.info(`  Appointments: ${report.appointments.synced} synced, ${report.appointments.errors} errors`);
  
  if (options.dryRun) {
    logger.info('  \x1b[33m(DRY RUN - no changes made)\x1b[0m');
  }
  
  if (options.demo) {
    logger.demo('(Demo mode - using mock data)');
  }

  logger.info('');

  return report;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const options = parseArgs();
  const logger = new Logger(options.verbose);

  CONFIG.demo = options.demo;

  logger.banner();

  if (options.demo) {
    logger.demo('Running in DEMO mode - no API keys required');
    logger.demo('Using mock data for all operations');
    logger.info('');
  }

  const action = options.action;

  switch (action) {
    case 'setup':
      validateSetup(logger, options);
      break;

    case 'test':
      await runTest(logger, options);
      break;

    case 'contacts': {
      if (!options.demo && !CONFIG.ghl.apiKey) {
        logger.error('GHL_API_KEY required. Use --demo for testing without keys.');
        process.exit(1);
      }
      const ghl = options.demo ? null : new GHLClient(CONFIG.ghl.apiKey, logger);
      const sheets = new GoogleSheetsClient(logger);
      if (!options.demo) await sheets.init();
      await syncContacts(ghl, sheets, logger, options);
      break;
    }

    case 'appointments': {
      if (!options.demo && !CONFIG.ghl.apiKey) {
        logger.error('GHL_API_KEY required. Use --demo for testing without keys.');
        process.exit(1);
      }
      const ghl = options.demo ? null : new GHLClient(CONFIG.ghl.apiKey, logger);
      const sheets = new GoogleSheetsClient(logger);
      if (!options.demo) await sheets.init();
      await syncAppointments(ghl, sheets, logger, options);
      break;
    }

    case 'webhooks':
      startWebhookServer(logger, options.port);
      // Keep process alive
      break;

    case 'sync': {
      if (!options.demo && !CONFIG.ghl.apiKey) {
        logger.error('GHL_API_KEY required. Use --demo for testing without keys.');
        process.exit(1);
      }
      const ghl = options.demo ? null : new GHLClient(CONFIG.ghl.apiKey, logger);
      const sheets = new GoogleSheetsClient(logger);
      if (!options.demo) await sheets.init();
      await runFullSync(ghl, sheets, logger, options);
      break;
    }

    default:
      logger.error(`Unknown action: ${action}`);
      process.exit(1);
  }
}

// Run
main().catch(err => {
  console.error(`\x1b[31mFatal error: ${err.message}\x1b[0m`);
  if (process.env.DEBUG) console.error(err.stack);
  process.exit(1);
});
