#!/usr/bin/env node
'use strict';

/**
 * Calendar Connector Script
 * 
 * Unified CLI for Google Calendar and Microsoft Outlook calendars.
 * Supports: list, create, check actions with --demo mode.
 * 
 * Usage:
 *   node calendar-connector.js --action list --calendar all --days 7 --demo
 *   node calendar-connector.js --action create --title "Meeting" --duration 60 --attendees "a@b.com,c@d.com" --dry-run
 *   node calendar-connector.js --action check --date 2025-01-15 --calendar google
 * 
 * Setup Instructions:
 * 
 * === Google Calendar API ===
 * 1. Go to https://console.cloud.google.com/
 * 2. Create a new project or select existing
 * 3. Enable "Google Calendar API" from APIs & Services > Library
 * 4. Go to APIs & Services > Credentials
 * 5. Create OAuth 2.0 Client ID (Desktop application type)
 * 6. Download the client credentials JSON
 * 7. Fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET below
 * 8. Set GOOGLE_REDIRECT_URI to http://localhost:3000/oauth2callback
 * 9. Run once to authorize and get refresh token, fill GOOGLE_REFRESH_TOKEN
 * 
 * === Microsoft Outlook (Azure AD) ===
 * 1. Go to https://portal.azure.com/
 * 2. Go to Azure Active Directory > App registrations > New registration
 * 3. Name: "Calendar Connector", Supported account types: "Accounts in any organizational directory"
 * 4. Redirect URI: Web - http://localhost:3000/outlook-callback
 * 5. Click Register, note the Application (client) ID
 * 6. Go to Certificates & secrets > New client secret, note the value
 * 7. Go to API permissions > Add permission > Microsoft Graph > Delegated permissions
 *    - Add: Calendars.ReadWrite, User.Read, offline_access
 * 8. Grant admin consent if needed
 * 9. Fill in OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, OUTLOOK_TENANT_ID below
 */

const { parseArgs } = require('node:util');

// =============================================================================
// CONFIGURATION - TODO: Fill in your credentials
// =============================================================================

const CONFIG = {
  google: {
    // TODO: Replace with your Google OAuth credentials
    clientId: process.env.GOOGLE_CLIENT_ID || 'YOUR_GOOGLE_CLIENT_ID_HERE',
    clientSecret: process.env.GOOGLE_CLIENT_SECRET || 'YOUR_GOOGLE_CLIENT_SECRET_HERE',
    redirectUri: process.env.GOOGLE_REDIRECT_URI || 'http://localhost:3000/oauth2callback',
    refreshToken: process.env.GOOGLE_REFRESH_TOKEN || 'YOUR_GOOGLE_REFRESH_TOKEN_HERE',
    // TODO: Set to true once credentials are configured
    configured: false,
  },
  outlook: {
    // TODO: Replace with your Azure AD app credentials
    clientId: process.env.OUTLOOK_CLIENT_ID || 'YOUR_OUTLOOK_CLIENT_ID_HERE',
    clientSecret: process.env.OUTLOOK_CLIENT_SECRET || 'YOUR_OUTLOOK_CLIENT_SECRET_HERE',
    tenantId: process.env.OUTLOOK_TENANT_ID || 'common', // or your specific tenant ID
    redirectUri: process.env.OUTLOOK_REDIRECT_URI || 'http://localhost:3000/outlook-callback',
    // TODO: Set to true once credentials are configured
    configured: false,
  },
};

// =============================================================================
// CLI ARGUMENT PARSING
// =============================================================================

function parseCliArgs() {
  const { values } = parseArgs({
    options: {
      action: { type: 'string', default: 'list' },
      calendar: { type: 'string', default: 'all' },
      date: { type: 'string', default: undefined },
      days: { type: 'string', default: '7' },
      title: { type: 'string', default: undefined },
      duration: { type: 'string', default: '60' },
      attendees: { type: 'string', default: undefined },
      'dry-run': { type: 'boolean', default: false },
      demo: { type: 'boolean', default: false },
      help: { type: 'boolean', default: false },
    },
    strict: false,
  });

  if (values.help) {
    printHelp();
    process.exit(0);
  }

  // Validate action
  const validActions = ['list', 'create', 'check'];
  if (!validActions.includes(values.action)) {
    console.error(`Error: Invalid action "${values.action}". Must be one of: ${validActions.join(', ')}`);
    process.exit(1);
  }

  // Validate calendar
  const validCalendars = ['google', 'outlook', 'all'];
  if (!validCalendars.includes(values.calendar)) {
    console.error(`Error: Invalid calendar "${values.calendar}". Must be one of: ${validCalendars.join(', ')}`);
    process.exit(1);
  }

  return {
    action: values.action,
    calendar: values.calendar,
    date: values.date || getToday(),
    days: parseInt(values.days, 10),
    title: values.title,
    duration: parseInt(values.duration, 10),
    attendees: values.attendees ? values.attendees.split(',').map(e => e.trim()) : [],
    dryRun: values['dry-run'],
    demo: values.demo,
  };
}

function printHelp() {
  console.log(`
Calendar Connector - Unified Google & Outlook Calendar CLI

USAGE:
  node calendar-connector.js [OPTIONS]

OPTIONS:
  --action <list|create|check>   Action to perform (default: list)
  --calendar <google|outlook|all> Calendar provider (default: all)
  --date <YYYY-MM-DD>            Date for check/list operations (default: today)
  --days <number>                Number of days to list ahead (default: 7)
  --title <string>               Event title (for create action)
  --duration <minutes>            Event duration in minutes (default: 60)
  --attendees <emails>           Comma-separated attendee emails
  --dry-run                      Preview without creating (for create action)
  --demo                          Use demo/sample data
  --help                         Show this help message

EXAMPLES:
  # List all events for next 7 days (demo mode)
  node calendar-connector.js --action list --calendar all --demo

  # Check availability on a specific date
  node calendar-connector.js --action check --date 2025-01-15 --calendar google --demo

  # Create an event (dry run)
  node calendar-connector.js --action create --title "Team Standup" --duration 30 \\
    --attendees "alice@example.com,bob@example.com" --dry-run

  # List next 14 days of Google events
  node calendar-connector.js --action list --calendar google --days 14 --demo
`);
}

function getToday() {
  return new Date().toISOString().split('T')[0];
}

// =============================================================================
// DEMO DATA GENERATOR
// =============================================================================

function generateDemoEvents(source, startDate, days) {
  const events = [];
  const baseDate = new Date(startDate + 'T00:00:00');
  
  const sampleEvents = {
    google: [
      { title: 'Team Standup', hour: 9, duration: 30, attendees: ['team@gotech.com'] },
      { title: 'Client Call - Acme Corp', hour: 11, duration: 60, attendees: ['client@acme.com', 'sales@gotech.com'] },
      { title: 'Lunch & Learn', hour: 12, duration: 60, attendees: [] },
      { title: 'Sprint Planning', hour: 14, duration: 90, attendees: ['dev@gotech.com', 'pm@gotech.com'] },
      { title: '1:1 with Manager', hour: 16, duration: 30, attendees: ['manager@gotech.com'] },
    ],
    outlook: [
      { title: 'Investor Meeting', hour: 10, duration: 60, attendees: ['investor@vc.com'] },
      { title: 'Product Review', hour: 13, duration: 45, attendees: ['product@gotech.com', 'design@gotech.com'] },
      { title: 'Board Prep', hour: 15, duration: 120, attendees: ['ceo@gotech.com', 'cfo@gotech.com'] },
      { title: 'Networking Event', hour: 18, duration: 90, attendees: [] },
    ],
  };

  for (let d = 0; d < days; d++) {
    const dayOffset = (d + Math.floor(d / 5) * 2); // Skip weekends somewhat
    const currentDate = new Date(baseDate);
    currentDate.setDate(currentDate.getDate() + dayOffset);
    
    // Skip weekends
    const dayOfWeek = currentDate.getDay();
    if (dayOfWeek === 0 || dayOfWeek === 6) continue;
    
    const dateStr = currentDate.toISOString().split('T')[0];
    const dayEvents = sampleEvents[source];
    
    // Add 2-3 events per day
    const eventsForDay = dayEvents.slice(d % 3, (d % 3) + 3);
    
    for (const evt of eventsForDay) {
      const startDateTime = new Date(`${dateStr}T${String(evt.hour).padStart(2, '0')}:00:00`);
      const endDateTime = new Date(startDateTime.getTime() + evt.duration * 60000);
      
      events.push({
        id: `${source}-${d}-${evt.hour}`,
        title: evt.title,
        start: startDateTime.toISOString(),
        end: endDateTime.toISOString(),
        attendees: evt.attendees,
        source: source,
        location: source === 'google' ? 'Google Meet' : 'Teams Meeting',
        status: 'confirmed',
      });
    }
  }

  return events;
}

// =============================================================================
// GOOGLE CALENDAR CONNECTOR
// =============================================================================

class GoogleCalendarConnector {
  constructor(config) {
    this.config = config;
    this.source = 'google';
    this.baseUrl = 'https://www.googleapis.com/calendar/v3';
  }

  isConfigured() {
    return this.config.configured;
  }

  /**
   * TODO: Implement OAuth2 flow
   * 1. Use refresh token to get access token
   * 2. Make authenticated requests to Google Calendar API
   * 
   * For now, returns demo data or throws if not configured
   */

  async listEvents(timeMin, timeMax) {
    if (!this.isConfigured()) {
      throw new Error(
        'Google Calendar not configured. Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ' +
        'and GOOGLE_REFRESH_TOKEN. See setup instructions at top of this file.'
      );
    }

    // TODO: Implement actual API call
    // const token = await this.getAccessToken();
    // const response = await fetch(`${this.baseUrl}/calendars/primary/events?timeMin=${timeMin}&timeMax=${timeMax}&singleEvents=true&orderBy=startTime`, {
    //   headers: { Authorization: `Bearer ${token}` }
    // });
    // return this.normalizeEvents(await response.json());

    return [];
  }

  async checkAvailability(date, days = 1) {
    if (!this.isConfigured()) {
      throw new Error('Google Calendar not configured.');
    }

    // TODO: Implement freebusy query
    // const token = await this.getAccessToken();
    // const response = await fetch(`${this.baseUrl}/freeBusy`, {
    //   method: 'POST',
    //   headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    //   body: JSON.stringify({ timeMin: start, timeMax: end, items: [{ id: 'primary' }] })
    // });

    return { date, busy: [], free: [] };
  }

  async createEvent(eventData) {
    if (!this.isConfigured()) {
      throw new Error('Google Calendar not configured.');
    }

    // TODO: Implement event creation
    // const token = await this.getAccessToken();
    // const response = await fetch(`${this.baseUrl}/calendars/primary/events`, {
    //   method: 'POST',
    //   headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    //   body: JSON.stringify(this.formatEventForApi(eventData))
    // });
    // return await response.json();

    return null;
  }

  formatEventForApi(eventData) {
    return {
      summary: eventData.title,
      start: { dateTime: eventData.start, timeZone: 'UTC' },
      end: { dateTime: eventData.end, timeZone: 'UTC' },
      attendees: eventData.attendees?.map(email => ({ email })) || [],
    };
  }

  normalizeEvents(apiResponse) {
    return (apiResponse.items || []).map(item => ({
      id: item.id,
      title: item.summary || '(No title)',
      start: item.start.dateTime || item.start.date,
      end: item.end.dateTime || item.end.date,
      attendees: (item.attendees || []).map(a => a.email),
      source: 'google',
      status: item.status,
    }));
  }
}

// =============================================================================
// OUTLOOK CALENDAR CONNECTOR
// =============================================================================

class OutlookCalendarConnector {
  constructor(config) {
    this.config = config;
    this.source = 'outlook';
    this.baseUrl = 'https://graph.microsoft.com/v1.0/me';
  }

  isConfigured() {
    return this.config.configured;
  }

  /**
   * TODO: Implement OAuth2 flow with Microsoft Graph
   * 1. Get authorization code via browser redirect
   * 2. Exchange for access token + refresh token
   * 3. Use token for Graph API requests
   * 
   * Token endpoint: https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token
   */

  async listEvents(startDate, endDate) {
    if (!this.isConfigured()) {
      throw new Error(
        'Outlook Calendar not configured. Please set OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET, ' +
        'and OUTLOOK_TENANT_ID. See setup instructions at top of this file.'
      );
    }

    // TODO: Implement actual API call
    // const token = await this.getAccessToken();
    // const response = await fetch(`${this.baseUrl}/calendarview?startDateTime=${startDate}&endDateTime=${endDate}`, {
    //   headers: { Authorization: `Bearer ${token}` }
    // });
    // return this.normalizeEvents(await response.json());

    return [];
  }

  async checkAvailability(date, days = 1) {
    if (!this.isConfigured()) {
      throw new Error('Outlook Calendar not configured.');
    }

    // TODO: Implement getSchedule
    // POST https://graph.microsoft.com/v1.0/me/calendar/getSchedule
    // Body: { schedules: ['gotech.ai'], startTime: {...}, endTime: {...} }

    return { date, busy: [], free: [] };
  }

  async createEvent(eventData) {
    if (!this.isConfigured()) {
      throw new Error('Outlook Calendar not configured.');
    }

    // TODO: Implement event creation
    // const token = await this.getAccessToken();
    // const response = await fetch(`${this.baseUrl}/events`, {
    //   method: 'POST',
    //   headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    //   body: JSON.stringify(this.formatEventForApi(eventData))
    // });
    // return await response.json();

    return null;
  }

  formatEventForApi(eventData) {
    return {
      subject: eventData.title,
      start: { dateTime: eventData.start, timeZone: 'UTC' },
      end: { dateTime: eventData.end, timeZone: 'UTC' },
      attendees: eventData.attendees?.map(email => ({
        emailAddress: { address: email },
        type: 'required',
      })) || [],
      isOnlineMeeting: true,
      onlineMeetingProvider: 'teamsForBusiness',
    };
  }

  normalizeEvents(apiResponse) {
    return (apiResponse.value || []).map(item => ({
      id: item.id,
      title: item.subject || '(No title)',
      start: item.start.dateTime,
      end: item.end.dateTime,
      attendees: (item.attendees || []).map(a => a.emailAddress.address),
      source: 'outlook',
      status: item.showAs,
      webLink: item.webLink,
    }));
  }
}

// =============================================================================
// UNIFIED CALENDAR MANAGER
// =============================================================================

class CalendarManager {
  constructor() {
    this.connectors = {
      google: new GoogleCalendarConnector(CONFIG.google),
      outlook: new OutlookCalendarConnector(CONFIG.outlook),
    };
  }

  getConnectors(calendarArg) {
    if (calendarArg === 'all') {
      return [this.connectors.google, this.connectors.outlook];
    }
    return [this.connectors[calendarArg]];
  }

  async listEvents(args) {
    const connectors = this.getConnectors(args.calendar);
    const allEvents = [];

    for (const connector of connectors) {
      if (args.demo) {
        const events = generateDemoEvents(connector.source, args.date, args.days);
        allEvents.push(...events);
      } else {
        try {
          const timeMin = args.date + 'T00:00:00Z';
          const endDate = new Date(args.date);
          endDate.setDate(endDate.getDate() + args.days);
          const timeMax = endDate.toISOString().split('T')[0] + 'T23:59:59Z';
          
          const events = await connector.listEvents(timeMin, timeMax);
          allEvents.push(...events);
        } catch (err) {
          console.error(`[${connector.source}] Error: ${err.message}`);
        }
      }
    }

    // Sort by start time
    allEvents.sort((a, b) => new Date(a.start) - new Date(b.start));
    return allEvents;
  }

  async checkAvailability(args) {
    const connectors = this.getConnectors(args.calendar);
    const results = [];

    for (const connector of connectors) {
      if (args.demo) {
        // Generate demo availability
        const events = generateDemoEvents(connector.source, args.date, 1);
        const busySlots = events.map(e => ({
          start: e.start,
          end: e.end,
          title: e.title,
        }));
        results.push({
          source: connector.source,
          date: args.date,
          busy: busySlots,
          free: this.calculateFreeSlots(busySlots, args.date),
        });
      } else {
        try {
          const availability = await connector.checkAvailability(args.date, 1);
          results.push({ source: connector.source, ...availability });
        } catch (err) {
          console.error(`[${connector.source}] Error: ${err.message}`);
        }
      }
    }

    return results;
  }

  calculateFreeSlots(busySlots, date) {
    const workStart = new Date(`${date}T09:00:00`);
    const workEnd = new Date(`${date}T18:00:00`);
    const freeSlots = [];
    let currentStart = workStart;

    const sortedBusy = busySlots
      .map(slot => ({ start: new Date(slot.start), end: new Date(slot.end) }))
      .sort((a, b) => a.start - b.start);

    for (const busy of sortedBusy) {
      if (currentStart < busy.start) {
        freeSlots.push({
          start: currentStart.toISOString(),
          end: busy.start.toISOString(),
        });
      }
      if (currentStart < busy.end) {
        currentStart = busy.end;
      }
    }

    if (currentStart < workEnd) {
      freeSlots.push({
        start: currentStart.toISOString(),
        end: workEnd.toISOString(),
      });
    }

    return freeSlots;
  }

  async createEvent(args) {
    if (!args.title) {
      console.error('Error: --title is required for create action');
      process.exit(1);
    }

    const connectors = this.getConnectors(args.calendar);
    const results = [];

    // Calculate event times
    const startDateTime = args.date
      ? new Date(`${args.date}T09:00:00`)
      : new Date();
    const endDateTime = new Date(startDateTime.getTime() + args.duration * 60000);

    const eventData = {
      title: args.title,
      start: startDateTime.toISOString(),
      end: endDateTime.toISOString(),
      attendees: args.attendees,
    };

    for (const connector of connectors) {
      if (args.dryRun) {
        results.push({
          source: connector.source,
          status: 'dry-run',
          event: eventData,
        });
        console.log(`[DRY RUN] Would create event on ${connector.source}: "${args.title}"`);
      } else if (args.demo) {
        results.push({
          source: connector.source,
          status: 'demo-created',
          event: { ...eventData, id: `demo-${Date.now()}` },
        });
        console.log(`[DEMO] Created event on ${connector.source}: "${args.title}"`);
      } else {
        try {
          const created = await connector.createEvent(eventData);
          results.push({
            source: connector.source,
            status: 'created',
            event: created,
          });
        } catch (err) {
          console.error(`[${connector.source}] Error: ${err.message}`);
          results.push({
            source: connector.source,
            status: 'error',
            error: err.message,
          });
        }
      }
    }

    return results;
  }
}

// =============================================================================
// OUTPUT FORMATTERS
// =============================================================================

function formatEvents(events) {
  if (events.length === 0) {
    console.log('No events found.');
    return;
  }

  console.log(JSON.stringify(events, null, 2));
}

function formatAvailability(results) {
  if (results.length === 0) {
    console.log('No availability data.');
    return;
  }

  console.log(JSON.stringify(results, null, 2));
}

function formatCreateResults(results) {
  console.log(JSON.stringify(results, null, 2));
}

// =============================================================================
// MAIN
// =============================================================================

async function main() {
  const args = parseCliArgs();
  const manager = new CalendarManager();

  // Print mode indicator
  if (args.demo) {
    console.error('📅 Running in DEMO mode with sample data...\n');
  } else if (args.dryRun) {
    console.error('🔍 Running in DRY-RUN mode (no changes will be made)...\n');
  }

  switch (args.action) {
    case 'list': {
      const events = await manager.listEvents(args);
      formatEvents(events);
      break;
    }

    case 'check': {
      const availability = await manager.checkAvailability(args);
      formatAvailability(availability);
      break;
    }

    case 'create': {
      const results = await manager.createEvent(args);
      formatCreateResults(results);
      break;
    }

    default:
      console.error(`Unknown action: ${args.action}`);
      process.exit(1);
  }
}

main().catch(err => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
