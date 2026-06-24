#!/usr/bin/env node
/**
 * Lead Capture Webhook Server
 * 
 * Production-ready HTTP server for capturing leads via POST /lead
 * - Validates input
 * - Appends to Google Sheets
 * - Optionally sends to GHL (GoHighLevel)
 * - Optionally sends confirmation email via Gmail SMTP
 * 
 * Environment Variables:
 *   PORT              - Server port (default: 3456)
 *   GHL_API_KEY        - GoHighLevel API key (optional)
 *   GHL_WEBHOOK_URL   - GHL webhook URL (optional, for webhook-based integration)
 *   SMTP_HOST         - SMTP server (default: smtp.gmail.com)
 *   SMTP_PORT         - SMTP port (default: 587)
 *   SMTP_USER         - SMTP username (optional, for confirmation emails)
 *   SMTP_PASS         - SMTP password/app password (optional)
 *   CONFIRM_EMAIL_TO  - "From" address for confirmation emails (optional)
 *   CORS_ORIGIN       - Allowed CORS origin (default: *)
 */

const http = require('http');
const { google } = require('googleapis');
const nodemailer = require('nodemailer');

// --- Configuration ---
const CONFIG = {
  port: parseInt(process.env.PORT, 10) || 3456,
  googleSheets: {
    credentialsPath: process.env.GOOGLE_SHEETS_CREDENTIALS || 
      '/Users/davidgo/.hermes/auth/google_sheets_credentials.json',
    spreadsheetId: process.env.LEAD_SHEET_ID || 
      '1odwvWVKQJDQ9i74aRXFx4rArSAKqPCj3T6VximU0ZpI',
    sheetName: process.env.LEAD_SHEET_NAME || 'Leads',
  },
  ghl: {
    apiKey: process.env.GHL_API_KEY || null,
    webhookUrl: process.env.GHL_WEBHOOK_URL || null,
    enabled: !!(process.env.GHL_API_KEY || process.env.GHL_WEBHOOK_URL),
  },
  smtp: {
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: parseInt(process.env.SMTP_PORT, 10) || 587,
    secure: parseInt(process.env.SMTP_PORT, 10) === 465,
    user: process.env.SMTP_USER || null,
    pass: process.env.SMTP_PASS || null,
    from: process.env.CONFIRM_EMAIL_TO || process.env.SMTP_USER || null,
    enabled: !!(process.env.SMTP_USER && process.env.SMTP_PASS),
  },
  cors: {
    origin: process.env.CORS_ORIGIN || '*',
    methods: ['POST', 'OPTIONS'],
    headers: ['Content-Type', 'Authorization', 'X-Requested-With'],
  },
  rateLimit: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 15 * 60 * 1000, // 15 min
    maxRequests: parseInt(process.env.RATE_LIMIT_MAX, 10) || 20, // per window per IP
  },
};

// --- Rate Limiter ---
class RateLimiter {
  constructor(windowMs, maxRequests) {
    this.windowMs = windowMs;
    this.maxRequests = maxRequests;
    this.clients = new Map();
    
    // Cleanup expired entries every 5 minutes
    this.cleanupInterval = setInterval(() => this.cleanup(), 5 * 60 * 1000);
    this.cleanupInterval.unref();
  }

  isAllowed(ip) {
    const now = Date.now();
    const windowStart = now - this.windowMs;
    
    if (!this.clients.has(ip)) {
      this.clients.set(ip, []);
    }
    
    const requests = this.clients.get(ip).filter(ts => ts > windowStart);
    
    if (requests.length >= this.maxRequests) {
      return { allowed: false, remaining: 0, resetAt: requests[0] + this.windowMs };
    }
    
    requests.push(now);
    this.clients.set(ip, requests);
    return { allowed: true, remaining: this.maxRequests - requests.length - 1, resetAt: now + this.windowMs };
  }

  cleanup() {
    const now = Date.now();
    const windowStart = now - this.windowMs;
    for (const [ip, requests] of this.clients) {
      const valid = requests.filter(ts => ts > windowStart);
      if (valid.length === 0) {
        this.clients.delete(ip);
      } else {
        this.clients.set(ip, valid);
      }
    }
  }

  destroy() {
    if (this.cleanupInterval) clearInterval(this.cleanupInterval);
  }
}

// --- Google Sheets Client ---
class GoogleSheetsWriter {
  constructor(credentialsPath, spreadsheetId, sheetName) {
    this.credentialsPath = credentialsPath;
    this.spreadsheetId = spreadsheetId;
    this.sheetName = sheetName;
    this.auth = null;
    this.sheets = null;
    this.headersWritten = false;
  }

  async initialize() {
    try {
      const auth = new google.auth.GoogleAuth({
        keyFile: this.credentialsPath,
        scopes: ['https://www.googleapis.com/auth/spreadsheets'],
      });
      this.auth = auth;
      this.sheets = google.sheets({ version: 'v4', auth });
      console.log('[GoogleSheets] Initialized successfully');
    } catch (error) {
      console.error('[GoogleSheets] Initialization failed:', error.message);
      throw error;
    }
  }

  async ensureHeaders() {
    if (this.headersWritten) return;
    
    try {
      const range = `${this.sheetName}!A:G`;
      const response = await this.sheets.spreadsheets.values.get({
        spreadsheetId: this.spreadsheetId,
        range,
      });

      const rows = response.data.values;
      if (!rows || rows.length === 0) {
        // Write headers
        const headers = [['Timestamp', 'Name', 'Email', 'Phone', 'Source', 'Interest', 'Message']];
        await this.sheets.spreadsheets.values.update({
          spreadsheetId: this.spreadsheetId,
          range: `${this.sheetName}!A1:G1`,
          valueInputOption: 'RAW',
          requestBody: { values: headers },
        });
        console.log('[Google Sheets] Headers written');
      }
      this.headersWritten = true;
    } catch (error) {
      console.warn('[Google Sheets] Could not ensure headers:', error.message);
      // Might be a new sheet - headers will be written with first data row
    }
  }

  async appendLead(lead) {
    await this.ensureHeaders();
    
    const row = [
      new Date().toISOString(),
      lead.name || '',
      lead.email || '',
      lead.phone || '',
      lead.source || '',
      lead.interest || '',
      lead.message || '',
    ];

    const result = await this.sheets.spreadsheets.values.append({
      spreadsheetId: this.spreadsheetId,
      range: `${this.sheetName}!A:G`,
      valueInputOption: 'RAW',
      insertDataOption: 'INSERT_ROWS',
      requestBody: { values: [row] },
    });

    console.log(`[Google Sheets] Lead appended: ${lead.email} (row ${result.data.updates?.updatedRange})`);
    return result.data;
  }
}

// --- GHL Webhook Sender ---
async function sendToGhl(lead) {
  if (!CONFIG.ghl.enabled) return null;

  const payload = {
    name: lead.name,
    email: lead.email,
    phone: lead.phone || '',
    source: lead.source || 'website',
    interest: lead.interest || '',
    message: lead.message || '',
    tags: ['website-lead', lead.source || 'organic'],
    custom_fields: {
      lead_source: lead.source || 'website',
      interest: lead.interest || '',
    },
  };

  // Method 1: GHL Webhook URL
  if (CONFIG.ghl.webhookUrl) {
    try {
      const response = await fetch(CONFIG.ghl.webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      console.log(`[GHL Webhook] Status: ${response.status}`);
      return { success: response.ok, method: 'webhook', status: response.status };
    } catch (error) {
      console.error('[GHL Webhook] Error:', error.message);
      return { success: false, method: 'webhook', error: error.message };
    }
  }

  // Method 2: GHL REST API
  if (CONFIG.ghl.apiKey) {
    try {
      const response = await fetch('https://rest.gohighlevel.com/v1/contacts/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${CONFIG.ghl.apiKey}`,
        },
        body: JSON.stringify({
          name: lead.name,
          email: lead.email,
          phone: lead.phone || '',
          tags: ['website-lead', lead.source || 'organic'],
          customField: {
            lead_source: lead.source || 'website',
            interest: lead.interest || '',
            message: lead.message || '',
          },
        }),
      });
      const data = await response.json().catch(() => ({}));
      console.log(`[GHL API] Status: ${response.status}`, data?.contact?.id ? `(contact: ${data.contact.id})` : '');
      return { success: response.ok, method: 'api', status: response.status, data };
    } catch (error) {
      console.error('[GHL API] Error:', error.message);
      return { success: false, method: 'api', error: error.message };
    }
  }

  return null;
}

// --- Gmail Confirmation Email ---
let smtpTransporter = null;

if (CONFIG.smtp.enabled) {
  smtpTransporter = nodemailer.createTransport({
    host: CONFIG.smtp.host,
    port: CONFIG.smtp.port,
    secure: CONFIG.smtp.secure,
    auth: {
      user: CONFIG.smtp.user,
      pass: CONFIG.smtp.pass,
    },
  });
}

async function sendConfirmationEmail(lead) {
  if (!smtpTransporter || !lead.email) return null;

  const mailOptions = {
    from: `"GoTech Solutions" <${CONFIG.smtp.from}>`,
    to: lead.email,
    subject: "Welcome to GoTech Solutions!",
    html: `
      <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
          <h1 style="color: #fff; margin: 0; font-size: 24px;">GoTech Solutions</h1>
        </div>
        <div style="background: #fff; padding: 30px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 12px 12px;">
          <h2>Hi ${lead.name},</h2>
          <p>Thanks for reaching out! We've received your inquiry and will get back to you within 24 hours.</p>
          ${(lead.interest) ? `<p><strong>Your interest:</strong> ${lead.interest}</p>` : ''}
          <div style="background: #f7f7f7; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #667eea;">What happens next?</h3>
            <ol style="padding-left: 20px;">
              <li>Review your requirements</li>
              <li>Strategize the best solution</li>
              <li>Schedule a call to discuss details</li>
            </ol>
          </div>
          <p style="color: #888; font-size: 12px;">This is an automated confirmation email. Please do not reply directly.</p>
        </div>
      </div>
    `,
    text: `Hi ${lead.name},\n\nThanks for reaching out! We've received your inquiry and will get back to you within 24 hours.\n\n${lead.interest ? `Your interest: ${lead.interest}\n` : ''}\nWhat happens next?\n1. Review your requirements\n2. Strategize the best solution\n3. Schedule a call to discuss details`,
  };

  try {
    const info = await smtpTransporter.sendMail(mailOptions);
    console.log(`[Email] Confirmation sent to ${lead.email} (${info.messageId})`);
    return { success: true, messageId: info.messageId };
  } catch (error) {
    console.error('[Email] Failed to send confirmation:', error.message);
    return { success: false, error: error.message };
  }
}

// --- Validation ---
function validateLead(body) {
  const errors = [];
  
  if (!body || typeof body !== 'object') {
    return { valid: false, errors: ['Request body must be a JSON object'] };
  }

  const { name, email } = body;

  if (!name || typeof name !== 'string' || name.trim().length < 2) {
    errors.push('Name is required and must be at least 2 characters');
  }

  if (!email || typeof email !== 'string') {
    errors.push('Email is required');
  } else {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      errors.push('Email format is invalid');
    }
  }

  // Sanitize
  const sanitized = {
    name: body.name ? String(body.name).trim().substring(0, 200) : '',
    email: body.email ? String(body.email).trim().toLowerCase().substring(0, 255) : '',
    phone: body.phone ? String(body.phone).trim().replace(/[^\d+\-().\s]/g, '').substring(0, 30) : '',
    source: body.source ? String(body.source).trim().substring(0, 100) : '',
    interest: body.interest ? String(body.interest).trim().substring(0, 200) : '',
    message: body.message ? String(body.message).trim().substring(0, 2000) : '',
  };

  return {
    valid: errors.length === 0,
    errors,
    sanitized,
  };
}

// --- HTTP Helpers ---
function getClientIp(req) {
  return req.headers['x-forwarded-for']?.split(',')[0]?.trim() ||
    req.headers['x-real-ip'] ||
    req.socket.remoteAddress ||
    'unknown';
}

function sendJson(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', CONFIG.cors.origin);
  res.setHeader('Access-Control-Allow-Methods', CONFIG.cors.methods.join(', '));
  res.setHeader('Access-Control-Allow-Headers', CONFIG.cors.headers.join(', '));
  res.setHeader('Access-Control-Max-Age', '86400');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
}

// --- Main Server ---
async function createServer() {
  const rateLimiter = new RateLimiter(CONFIG.rateLimit.windowMs, CONFIG.rateLimit.maxRequests);
  const sheetsWriter = new GoogleSheetsWriter(
    CONFIG.googleSheets.credentialsPath,
    CONFIG.googleSheets.spreadsheetId,
    CONFIG.googleSheets.sheetName
  );

  // Initialize Google Sheets (fail gracefully)
  try {
    await sheetsWriter.initialize();
  } catch (error) {
    console.error('WARNING: Google Sheets not available. Leads will not be saved to Sheets.');
    console.error('Error:', error.message);
  }

  const server = http.createServer(async (req, res) => {
    setCorsHeaders(res);

    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
      sendJson(res, 204, null);
      return;
    }

    // Health check
    if (req.method === 'GET' && (req.url === '/health' || req.url === '/')) {
      sendJson(res, 200, { 
        status: 'ok', 
        service: 'lead-capture-webhook',
        uptime: process.uptime(),
        features: {
          googleSheets: sheetsWriter.sheets !== null,
          ghl: CONFIG.ghl.enabled,
          email: CONFIG.smtp.enabled,
        }
      });
      return;
    }

    // Rate limiting check (even for valid endpoints)
    const clientIp = getClientIp(req);
    const rateCheck = rateLimiter.isAllowed(clientIp);

    // Set rate limit headers
    res.setHeader('X-RateLimit-Remaining', Math.max(0, rateCheck.remaining));
    res.setHeader('X-RateLimit-Reset', new Date(rateCheck.resetAt).toISOString());

    if (!rateCheck.allowed) {
      res.setHeader('Retry-After', Math.ceil((rateCheck.resetAt - Date.now()) / 1000));
      sendJson(res, 429, { 
        error: 'Too many requests', 
        message: 'Rate limit exceeded. Please try again later.',
        retryAfter: Math.ceil((rateCheck.resetAt - Date.now()) / 1000),
      });
      return;
    }

    // POST /lead - Main endpoint
    if (req.method === 'POST' && req.url === '/lead') {
      let body = '';
      
      // Set body size limit (64KB)
      req.on('data', chunk => {
        body += chunk.toString();
        if (body.length > 65536) {
          req.destroy();
        }
      });

      req.on('end', async () => {
        // Parse JSON
        let parsedBody;
        try {
          parsedBody = JSON.parse(body);
        } catch (e) {
          sendJson(res, 400, { error: 'Invalid JSON', message: 'Request body must be valid JSON' });
          return;
        }

        // Validate
        const validation = validateLead(parsedBody);
        if (!validation.valid) {
          sendJson(res, 422, { error: 'Validation failed', details: validation.errors });
          return;
        }

        const lead = validation.sanitized;
        console.log(`[Lead] New lead captured: ${lead.name} <${lead.email}> from ${lead.source || 'direct'}`);

        // Process asynchronously (don't block response)
        const results = {
          googleSheets: null,
          ghl: null,
          email: null,
        };

        // Save to Google Sheets
        if (sheetsWriter.sheets) {
          try {
            const sheetResult = await sheetsWriter.appendLead(lead);
            results.googleSheets = { success: true, range: sheetResult.updates?.updatedRange };
          } catch (error) {
            console.error('[Lead] Google Sheets error:', error.message);
            results.googleSheets = { success: false, error: error.message };
          }
        } else {
          results.googleSheets = { success: false, error: 'Google Sheets not configured' };
        }

        // Send to GHL (async, don't block)
        if (CONFIG.ghl.enabled) {
          sendToGhl(lead).then(result => {
            results.ghl = result;
          });
        }

        // Send confirmation email (async, don't block)
        if (CONFIG.smtp.enabled) {
          sendConfirmationEmail(lead).then(result => {
            results.email = result;
          });
        }

        // Return success immediately (async processes continue)
        sendJson(res, 201, {
          success: true,
          message: 'Lead captured successfully',
          lead: {
            name: lead.name,
            email: lead.email,
          },
          details: {
            sheetsSaved: !!sheetsWriter.sheets,
            ghlSent: CONFIG.ghl.enabled,
            emailSent: CONFIG.smtp.enabled,
          },
        });
      });

      req.on('error', (error) => {
        console.error('[Server] Request error:', error.message);
        sendJson(res, 500, { error: 'Internal server error' });
      });

      return;
    }

    // 404 for unknown routes
    sendJson(res, 404, { error: 'Not found', message: `Cannot ${req.method} ${req.url}` });
  });

  return { server, sheetsWriter, rateLimiter };
}

// --- Start ---
async function main() {
  console.log('='.repeat(60));
  console.log('  LEAD CAPTURE WEBHOOK SERVER');
  console.log('='.repeat(60));
  console.log(`  Port:        ${CONFIG.port}`);
  console.log(`  Google Sheet: ${CONFIG.googleSheets.spreadsheetId}`);
  console.log(`  Sheet Name:  ${CONFIG.googleSheets.sheetName}`);
  console.log(`  GHL:         ${CONFIG.ghl.enabled ? 'Enabled' : 'Disabled'}`);
  console.log(`  Email:       ${CONFIG.smtp.enabled ? 'Enabled' : 'Disabled'}`);
  console.log(`  Rate Limit:  ${CONFIG.rateLimit.maxRequests} req / ${CONFIG.rateLimit.windowMs / 60000} min`);
  console.log('='.repeat(60));

  try {
    const { server, sheetsWriter, rateLimiter } = await createServer();

    // Graceful shutdown
    const shutdown = async (signal) => {
      console.log(`\n[Server] Received ${signal}. Shutting down gracefully...`);
      
      server.close(() => {
        console.log('[Server] HTTP server closed');
      });
      
      rateLimiter.destroy();
      
      // Force close after 10 seconds
      setTimeout(() => {
        console.log('[Server] Forcing shutdown');
        process.exit(0);
      }, 10000);

      // Close server connections
      server.closeAllConnections?.();
    };

    process.on('SIGTERM', () => shutdown('SIGTERM'));
    process.on('SIGINT', () => shutdown('SIGINT'));

    server.listen(CONFIG.port, '0.0.0.0', () => {
      console.log(`[Server] Running on http://0.0.0.0:${CONFIG.port}`);
      console.log(`[Server] POST http://localhost:${CONFIG.port}/lead`);
      console.log(`[Server] GET  http://localhost:${CONFIG.port}/health`);
      console.log('');
    });
  } catch (error) {
    console.error('[Fatal] Could not start server:', error.message);
    process.exit(1);
  }
}

main();

module.exports = { createServer, validateLead, CONFIG };
