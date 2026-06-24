#!/usr/bin/env node

/**
 * GoTech Solutions - Email Outreach System
 * 
 * Usage:
 *   node email-outreach.js --to "john@example.com" --template prospecting --dry-run
 *   node email-outreach.js --to "john@example.com,jane@corp.com" --template followup --subject "Following up" --dry-run
 *   node email-outreach.js --to "client@newco.com" --template welcome --from "David" --send
 *   node email-outreach.js --stats
 * 
 * SMTP Setup (for --send mode):
 *   1. Install nodemailer: npm install nodemailer
 *   2. Create config file at scripts/email-config.json:
 *      {
 *        "host": "smtp.gmail.com",
 *        "port": 587,
 *        "secure": false,
 *        "auth": {
 *          "user": "you@gotechsolutions.com",
 *          "pass": "your-app-password"
 *        }
 *      }
 *   3. Or use environment variables: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
 *   4. Remove --dry-run flag to actually send
 * 
 * Template Variables: {{firstName}}, {{company}}, {{service}}, {{senderName}}, {{senderTitle}}
 */

const fs = require('fs');
const path = require('path');

// --- Configuration ---
const SCRIPT_DIR = __dirname;
const PROJECT_DIR = path.resolve(SCRIPT_DIR, '..');
const TEMPLATES_DIR = path.join(PROJECT_DIR, 'templates', 'email');
const LOG_FILE = path.join(SCRIPT_DIR, 'email-log.csv');
const CONFIG_FILE = path.join(SCRIPT_DIR, 'email-config.json');

// --- Parse CLI Arguments ---
function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith('--')) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    }
  }
  return args;
}

// --- Load Template ---
function loadTemplate(templateName) {
  const templatePath = path.join(TEMPLATES_DIR, `${templateName}.md`);
  if (!fs.existsSync(templatePath)) {
    console.error(`Error: Template "${templateName}" not found at ${templatePath}`);
    console.error(`Available templates: ${getAvailableTemplates().join(', ')}`);
    process.exit(1);
  }
  return fs.readFileSync(templatePath, 'utf-8');
}

function getAvailableTemplates() {
  if (!fs.existsSync(TEMPLATES_DIR)) return [];
  return fs.readdirSync(TEMPLATES_DIR)
    .filter(f => f.endsWith('.md'))
    .map(f => f.replace('.md', ''));
}

// --- Parse Template (extract subject and body) ---
function parseTemplate(raw) {
  const lines = raw.split('\n');
  let subject = '';
  let bodyStart = 0;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.toLowerCase().startsWith('subject:')) {
      subject = line.slice(8).trim();
      // Body is everything after the subject line
      bodyStart = i + 1;
      // Skip blank lines after subject
      while (bodyStart < lines.length && lines[bodyStart].trim() === '') {
        bodyStart++;
      }
      break;
    }
  }
  
  const body = lines.slice(bodyStart).join('\n').trim();
  return { subject, body };
}

// --- Render Template Variables ---
function renderTemplate(text, variables) {
  let rendered = text;
  for (const [key, value] of Object.entries(variables)) {
    const regex = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
    rendered = rendered.replace(regex, value || `{{${key}}}`);
  }
  return rendered;
}

// --- Parse Recipients ---
function parseRecipients(toArg) {
  return toArg.split(',').map(e => e.trim()).filter(Boolean);
}

// --- Extract First Name from Email ---
function extractFirstName(email) {
  const local = email.split('@')[0];
  // Handle formats like john.doe, john_doe, johndoe
  const name = local.replace(/[._-]/g, ' ').trim();
  const first = name.split(/[\s._-]/)[0] || name;
  return first.charAt(0).toUpperCase() + first.slice(1);
}

// --- Log Email to CSV ---
function logEmail(to, template, status) {
  const date = new Date().toISOString().split('T')[0];
  const row = `"${date}","${to}","${template}","${status}"\n`;
  
  if (!fs.existsSync(LOG_FILE)) {
    fs.writeFileSync(LOG_FILE, '"sent-date","to","template","status"\n');
  }
  fs.appendFileSync(LOG_FILE, row);
}

// --- Show Stats ---
function showStats() {
  if (!fs.existsSync(LOG_FILE)) {
    console.log('No emails logged yet.');
    return;
  }
  
  const content = fs.readFileSync(LOG_FILE, 'utf-8');
  const lines = content.split('\n').filter(l => l.trim() && !l.startsWith('"sent-date"'));
  
  const now = new Date();
  const today = now.toISOString().split('T')[0];
  
  // Start of week (Sunday)
  const dayOfWeek = now.getDay();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - dayOfWeek);
  weekStart.setHours(0, 0, 0, 0);
  const weekStartStr = weekStart.toISOString().split('T')[0];
  
  let todayCount = 0;
  let weekCount = 0;
  const templateCounts = {};
  
  for (const line of lines) {
    const parts = parseCSVLine(line);
    if (parts.length < 4) continue;
    
    const [date, , templateName] = parts;
    
    if (date === today) todayCount++;
    if (date >= weekStartStr) weekCount++;
    
    templateCounts[templateName] = (templateCounts[templateName] || 0) + 1;
  }
  
  console.log('\n╔══════════════════════════════════════╗');
  console.log('║     GoTech Solutions - Email Stats    ║');
  console.log('╠══════════════════════════════════════╣');
  console.log(`║  Sent today:        ${String(todayCount).padStart(16)}  ║`);
  console.log(`║  Sent this week:    ${String(weekCount).padStart(16)}  ║`);
  console.log('╠══════════════════════════════════════╣');
  console.log('║  By template:                        ║');
  for (const [name, count] of Object.entries(templateCounts)) {
    console.log(`║    ${name.padEnd(20)} ${String(count).padStart(10)}  ║`);
  }
  console.log('╚══════════════════════════════════════╝\n');
}

// --- Simple CSV Line Parser ---
function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

// --- Load SMTP Config ---
function loadSmtpConfig() {
  // Try environment variables first
  if (process.env.SMTP_HOST && process.env.SMTP_USER) {
    return {
      host: process.env.SMTP_HOST,
      port: parseInt(process.env.SMTP_PORT || '587'),
      secure: process.env.SMTP_SECURE === 'true',
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS
      }
    };
  }
  
  // Try config file
  if (fs.existsSync(CONFIG_FILE)) {
    return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
  }
  
  return null;
}

// --- Send Email via SMTP ---
async function sendEmail(to, subject, body, fromName) {
  let nodemailer;
  try {
    nodemailer = require('nodemailer');
  } catch (e) {
    console.error('Error: nodemailer is not installed. Run: npm install nodemailer');
    process.exit(1);
  }
  
  const config = loadSmtpConfig();
  if (!config) {
    console.error('Error: No SMTP config found. Create scripts/email-config.json or set SMTP env vars.');
    console.error('See setup instructions in script header comments.');
    process.exit(1);
  }
  
  const transporter = nodemailer.createTransport(config);
  
  const mailOptions = {
    from: `"${fromName}" <${config.auth.user}>`,
    to,
    subject,
    text: body
  };
  
  const info = await transporter.sendMail(mailOptions);
  return info;
}

// --- Main ---
async function main() {
  const args = parseArgs(process.argv);
  
  // --- Stats Mode ---
  if (args.stats) {
    showStats();
    return;
  }
  
  // --- Validate Required Args ---
  if (!args.to) {
    console.error('Error: --to is required. Specify recipient email(s).');
    console.error('Usage: node email-outreach.js --to "email@example.com" --template prospecting --dry-run');
    process.exit(1);
  }
  
  if (!args.template) {
    console.error('Error: --template is required. Available: ' + getAvailableTemplates().join(', '));
    process.exit(1);
  }
  
  // --- Load and Parse Template ---
  const rawTemplate = loadTemplate(args.template);
  const { subject: templateSubject, body: templateBody } = parseTemplate(rawTemplate);
  
  // --- Parse Recipients ---
  const recipients = parseRecipients(args.to);
  
  // --- Sender Info ---
  const senderName = args.senderName || args.from || 'GoTech Solutions Team';
  const senderTitle = args.senderTitle || 'Business Development';
  
  // --- Process Each Recipient ---
  for (const email of recipients) {
    const firstName = extractFirstName(email);
    const company = args.company || email.split('@')[1].split('.')[0];
    const service = args.service || 'custom software development';
    
    const variables = {
      firstName,
      company: capitalize(company),
      service,
      senderName,
      senderTitle
    };
    
    // Override subject if provided via CLI
    const subject = args.subject || renderTemplate(templateSubject, variables);
    const body = renderTemplate(templateBody, variables);
    
    // --- Output ---
    console.log('═'.repeat(60));
    console.log(`To:      ${email}`);
    console.log(`From:    ${senderName} <[sender-email]>`);
    console.log(`Subject: ${subject}`);
    console.log('─'.repeat(60));
    console.log(body);
    console.log('═'.repeat(60));
    console.log('');
    
    // --- Send or Dry-Run ---
    if (args.send) {
      try {
        await sendEmail(email, subject, body, senderName);
        logEmail(email, args.template, 'sent');
        console.log(`✓ Sent to ${email}`);
      } catch (err) {
        logEmail(email, args.template, 'failed');
        console.error(`✗ Failed to send to ${email}: ${err.message}`);
      }
    } else {
      // Default: dry-run mode
      logEmail(email, args.template, 'dry-run');
      console.log(`[DRY RUN] Would send to ${email}`);
    }
  }
  
  console.log(`\nTotal: ${recipients.length} email(s) processed.`);
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// --- Run ---
main().catch(err => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
