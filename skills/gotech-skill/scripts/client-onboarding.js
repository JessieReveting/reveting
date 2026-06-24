#!/usr/bin/env node

/**
 * Client Onboarding Script
 * Generates client folders, SOW templates, and welcome emails for GoTechSolutions.
 * 
 * Usage:
 *   node client-onboarding.js --client "Acme Corp" --email contact@acme.com --service ai-ops --plan monthly
 *   node client-onboarding.js --client "Acme Corp" --email contact@acme.com --service bundle --plan annual --dry-run
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// ─── Configuration ───────────────────────────────────────────────────────────

const SERVICES = {
  'ai-ops': {
    name: 'AI Operations',
    price: 500,
    description: 'AI workflow automation, AI customer support, content generation',
    deliverables: [
      'AI workflow audit & setup (Week 1-2)',
      'Custom AI chatbot deployment (Week 2-3)',
      'Content generation pipeline (Week 3-4)',
      'Monthly performance report (ongoing)',
    ],
    timeline: '4 weeks initial setup, then monthly retainer',
  },
  communications: {
    name: 'Communications',
    price: 300,
    description: 'Podcast production, livestream setup, multi-platform distribution',
    deliverables: [
      'Podcast setup & branding (Week 1)',
      'Livestream configuration (Week 1-2)',
      'Multi-platform distribution (Week 2-3)',
      'Monthly analytics report (ongoing)',
    ],
    timeline: '3 weeks initial setup, then monthly retainer',
  },
  cro: {
    name: 'Conversion Rate Optimization',
    price: 750,
    description: 'Landing page optimization, A/B testing, conversion rate optimization',
    deliverables: [
      'Landing page audit & heatmap analysis (Week 1)',
      'A/B test plan & implementation (Week 2-3)',
      'Conversion funnel optimization (Week 3-4)',
      'Bi-weekly performance reports (ongoing)',
    ],
    timeline: '4 weeks initial sprint, then bi-weekly cycles',
  },
  golive: {
    name: 'GoLive Streaming',
    price: 400,
    description: 'One-click livestream to YouTube/Twitch/Facebook/TikTok',
    deliverables: [
      'Platform account setup & verification (Week 1)',
      'Streaming software configuration (Week 1)',
      'Multi-stream testing & optimization (Week 2)',
      'Monthly stream analytics report (ongoing)',
    ],
    timeline: '2 weeks setup, then monthly retainer',
  },
  bundle: {
    name: 'Full Bundle',
    price: 1750,
    description: 'All services + priority support + dedicated account manager',
    deliverables: [
      'All AI Operations deliverables',
      'All Communications deliverables',
      'All CRO deliverables',
      'All GoLive deliverables',
      'Dedicated account manager assignment',
      'Priority 24-hour support SLA',
      'Monthly strategy review call',
    ],
    timeline: '6 weeks full rollout, then ongoing priority support',
  },
};

const PLANS = {
  monthly: { label: 'Monthly', months: 1, discount: 0 },
  annual: { label: 'Annual', months: 12, discount: 2 }, // 2 months free
};

// ─── Argument Parsing ────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
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

function validateArgs(args) {
  const errors = [];
  if (!args.client) errors.push('--client is required');
  if (!args.email) errors.push('--email is required');
  if (!args.service) errors.push('--service is required');
  if (!args.plan) errors.push('--plan is required');
  if (args.service && !SERVICES[args.service]) {
    errors.push(`Invalid service "${args.service}". Valid: ${Object.keys(SERVICES).join(', ')}`);
  }
  if (args.plan && !PLANS[args.plan]) {
    errors.push(`Invalid plan "${args.plan}". Valid: ${Object.keys(PLANS).join(', ')}`);
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (args.email && !emailRegex.test(args.email)) {
    errors.push(`Invalid email format: "${args.email}"`);
  }
  return errors;
}

// ─── Utility Functions ───────────────────────────────────────────────────────

function slugify(name) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s]+/g, '-')
    .replace(/-+/g, '-');
}

function formatCurrency(amount) {
  return '$' + amount.toLocaleString('en-US');
}

function todayFormatted() {
  const d = new Date();
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}

function calculatePricing(service, plan) {
  const svc = SERVICES[service];
  const planConfig = PLANS[plan];
  const monthlyPrice = svc.price;
  const totalMonths = planConfig.months;
  const freeMonths = planConfig.discount;
  const billedMonths = totalMonths - freeMonths;
  const totalPrice = monthlyPrice * billedMonths;
  const savings = monthlyPrice * freeMonths;
  return {
    monthlyPrice,
    totalMonths,
    billedMonths,
    freeMonths,
    totalPrice,
    savings,
  };
}

// ─── Content Generation ─────────────────────────────────────────────────────

function generateSOW(clientSlug, clientName, email, service, plan) {
  const svc = SERVICES[service];
  const planConfig = PLANS[plan];
  const pricing = calculatePricing(service, plan);
  const date = todayFormatted();

  let pricingLine = '';
  if (plan === 'monthly') {
    pricingLine = `${formatCurrency(pricing.monthlyPrice)}/month, billed monthly`;
  } else {
    pricingLine = `${formatCurrency(pricing.monthlyPrice)}/month × ${pricing.billedMonths} months = ${formatCurrency(pricing.totalPrice)} (annual billing, ${pricing.freeMonths} months free, saving ${formatCurrency(pricing.savings)})`;
  }

  const deliverablesList = svc.deliverables.map((d, i) => `${i + 1}. ${d}`).join('\n');

  return `# Statement of Work (SOW)

---

## GoTechSolutions — ${svc.name}

| Field | Details |
|-------|---------|
| **Client** | ${clientName} |
| **Contact Email** | ${email} |
| **Service** | ${svc.name} |
| **Plan** | ${planConfig.label} |
| **Pricing** | ${pricingLine} |
| **Date** | ${date} |
| **Prepared By** | GoTechSolutions Team |

---

## 1. Scope of Work

GoTechSolutions ("Provider") agrees to deliver **${svc.name}** services to ${clientName} ("Client") as described below.

### Service Description
${svc.description}

### Engagement Model
- **Plan:** ${planConfig.label} (${pricing.totalMonths} month${pricing.totalMonths > 1 ? 's' : ''})
- **Service Duration:** ${svc.timeline}
- **Start Date:** Upon signed agreement and initial payment

---

## 2. Deliverables & Timeline

${deliverablesList}

---

## 3. Payment Terms

| Item | Amount |
|------|--------|
| Monthly Rate | ${formatCurrency(pricing.monthlyPrice)} |
| Billing Cycle | ${planConfig.label} |
| ${plan === 'annual' ? `Total Annual Investment (${pricing.billedMonths} months billed)` : 'Monthly Total'} | ${plan === 'annual' ? formatCurrency(pricing.totalPrice) : formatCurrency(pricing.monthlyPrice)} |
${plan === 'annual' ? `| Savings | ${formatCurrency(pricing.savings)} |` : ''}

### Payment Schedule
- Payment is due upon signing of this agreement.
- ${plan === 'annual' ? 'Full annual payment is due within 14 days of signing.' : 'Monthly payments are due on the 1st of each month.'}
- Accepted payment methods: Bank transfer, credit card, or ACH.
- Late payments (beyond 7 days) may incur a 1.5% monthly service fee.

### Renewal
- ${plan === 'annual' ? 'This agreement auto-renews annually unless either party provides 30 days written notice prior to expiration.' : 'This agreement auto-renews monthly unless either party provides 15 days written notice.'}

---

## 4. Client Responsibilities

The Client agrees to:
- Provide timely access to necessary accounts, platforms, and brand assets.
- Designate a primary point of contact for communications.
- Review and approve deliverables within 5 business days of delivery.
- Make payments according to the schedule outlined above.

---

## 5. Confidentiality

Both parties agree to maintain the confidentiality of all proprietary information, trade secrets, and business data shared during the course of this engagement. This obligation survives the termination of this agreement for a period of two (2) years.

---

## 6. Termination

Either party may terminate this agreement:
- **For convenience:** With ${plan === 'annual' ? '30' : '15'} days written notice.
- **For cause:** Immediately upon material breach that remains uncured after 7 days written notice.
- Upon termination, Client shall pay for all services rendered through the termination date.

---

## 7. Limitation of Liability

Provider's total liability under this agreement shall not exceed the total fees paid by Client in the preceding three (3) months. Provider shall not be liable for indirect, incidental, or consequential damages.

---

## 8. Signatures

By signing below, both parties agree to the terms outlined in this Statement of Work.

### Provider — GoTechSolutions

| | |
|---|---|
| **Name:** | _________________________________ |
| **Title:** | _________________________________ |
| **Signature:** | _________________________________ |
| **Date:** | _________________________________ |

### Client — ${clientName}

| | |
|---|---|
| **Name:** | _________________________________ |
| **Title:** | _________________________________ |
| **Signature:** | _________________________________ |
| **Date:** | _________________________________ |

---

*This document was generated by GoTechSolutions Client Onboarding System on ${date}.*
`;
}

function generateWelcomeEmail(clientName, email, service, plan) {
  const svc = SERVICES[service];
  const planConfig = PLANS[plan];
  const pricing = calculatePricing(service, plan);

  let pricingText = '';
  if (plan === 'monthly') {
    pricingText = `at ${formatCurrency(pricing.monthlyPrice)}/month`;
  } else {
    pricingText = `at ${formatCurrency(pricing.totalPrice)} annually (that's 2 months free!)`;
  }

  return `Subject: Welcome to GoTechSolutions — ${svc.name} Onboarding

Hi ${clientName},

Welcome to GoTechSolutions! We're thrilled to have you on board. 🎉

Your ${svc.name} service is now active ${pricingText}. Here's what you can expect:

${svc.description}

Your engagement runs on a ${planConfig.label.toLowerCase()} plan, and your dedicated team will reach out within 1-2 business days to schedule your kickoff call.

What happens next:
1. You'll receive a calendar invite for your kickoff session
2. We'll gather the assets and access we need to get started
3. Your first deliverables will begin rolling out according to the timeline in your SOW

If you have any questions before then, simply reply to this email — we're here to help.

Looking forward to doing great work together!

Best regards,
The GoTechSolutions Team
onboarding@gotechsolutions.com
`;
}

// ─── File System Operations ──────────────────────────────────────────────────

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    return true;
  }
  return false;
}

function writeFile(filePath, content) {
  const dir = path.dirname(filePath);
  ensureDir(dir);
  fs.writeFileSync(filePath, content, 'utf-8');
}

// ─── Main ────────────────────────────────────────────────────────────────────

function main() {
  const args = parseArgs(process.argv.slice(2));

  // Show help
  if (args.help || args.h) {
    console.log(`
Client Onboarding Script — GoTechSolutions

Usage:
  node client-onboarding.js --client "Client Name" --email client@example.com --service <service> --plan <plan> [--dry-run]

Options:
  --client    Client/company name (required)
  --email     Primary contact email (required)
  --service   Service tier: ai-ops | communications | cro | golive | bundle (required)
  --plan      Billing plan: monthly | annual (required)
  --dry-run   Preview actions without writing files (optional)
  --help, -h  Show this help message

Services & Pricing:
  ai-ops         $500/mo  — AI workflow automation, AI customer support, content generation
  communications $300/mo  — Podcast production, livestream setup, multi-platform distribution
  cro            $750/mo  — Landing page optimization, A/B testing, conversion rate optimization
  golive         $400/mo  — One-click livestream to YouTube/Twitch/Facebook/TikTok
  bundle         $1,750/mo — All services + priority support + dedicated account manager

Examples:
  node client-onboarding.js --client "Acme Corp" --email john@acme.com --service ai-ops --plan monthly
  node client-onboarding.js --client "Acme Corp" --email john@acme.com --service bundle --plan annual --dry-run
`);
    process.exit(0);
  }

  // Validate
  const errors = validateArgs(args);
  if (errors.length > 0) {
    console.error('❌ Validation errors:');
    errors.forEach(e => console.error(`   • ${e}`));
    console.error('\nRun with --help for usage information.');
    process.exit(1);
  }

  const clientSlug = slugify(args.client);
  const svc = SERVICES[args.service];
  const planConfig = PLANS[args.plan];
  const pricing = calculatePricing(args.service, args.plan);

  // Determine paths
  const homeDir = os.homedir();
  const clientsBase = path.join(homeDir, 'Documents', 'GoTechSolutions', 'clients');
  const clientDir = path.join(clientsBase, clientSlug);
  const sowPath = path.join(clientDir, 'statement-of-work.md');
  const emailPath = path.join(clientDir, 'welcome-email.txt');
  const summaryPath = path.join(clientDir, 'onboarding-summary.json');

  // Generate content
  const sowContent = generateSOW(clientSlug, args.client, args.email, args.service, args.plan);
  const emailContent = generateWelcomeEmail(args.client, args.email, args.service, args.plan);

  const summary = {
    client: args.client,
    clientSlug,
    email: args.email,
    service: {
      key: args.service,
      name: svc.name,
      description: svc.description,
    },
    plan: {
      key: args.plan,
      label: planConfig.label,
      totalMonths: pricing.totalMonths,
      billedMonths: pricing.billedMonths,
      freeMonths: pricing.freeMonths,
    },
    pricing: {
      monthly: pricing.monthlyPrice,
      total: pricing.totalPrice,
      savings: pricing.savings,
      formatted: plan === 'annual'
        ? `${formatCurrency(pricing.totalPrice)}/year`
        : `${formatCurrency(pricing.monthlyPrice)}/month`,
    },
    files: {
      clientDirectory: clientDir,
      statementOfWork: sowPath,
      welcomeEmail: emailPath,
      summary: summaryPath,
    },
    generatedAt: new Date().toISOString(),
    dryRun: !!args['dry-run'],
  };

  if (args['dry-run']) {
    console.log('🔍 DRY RUN — No files will be written.\n');
    console.log('─'.repeat(60));
    console.log('📁 Client Directory:', clientDir);
    console.log('📄 SOW Template:', sowPath);
    console.log('📧 Welcome Email:', emailPath);
    console.log('📊 Summary JSON:', summaryPath);
    console.log('─'.repeat(60));
    console.log('\n📋 Summary:');
    console.log(JSON.stringify(summary, null, 2));
    console.log('\n📝 SOW Preview (first 10 lines):');
    console.log(sowContent.split('\n').slice(0, 10).join('\n') + '\n...');
    console.log('\n📧 Welcome Email Preview:');
    console.log(emailContent.split('\n').slice(0, 5).join('\n') + '\n...');
    console.log('\n✅ Dry run complete. Remove --dry-run to create files.');
  } else {
    // Write files
    writeFile(sowPath, sowContent);
    writeFile(emailPath, emailContent);
    writeFile(summaryPath, JSON.stringify(summary, null, 2));

    console.log('✅ Client onboarding complete!\n');
    console.log('─'.repeat(60));
    console.log('👤 Client:', args.client);
    console.log('🏢 Slug:', clientSlug);
    console.log('📦 Service:', svc.name, `(${formatCurrency(pricing.monthlyPrice)}/mo)`);
    console.log('📅 Plan:', planConfig.label, pricing.savings > 0 ? `(Save ${formatCurrency(pricing.savings)}!)` : '');
    console.log('💰 Total:', formatCurrency(pricing.totalPrice));
    console.log('─'.repeat(60));
    console.log('\n📁 Files created:');
    console.log('   📂', clientDir);
    console.log('   📄 statement-of-work.md');
    console.log('   📧 welcome-email.txt');
    console.log('   📊 onboarding-summary.json');
    console.log('\n🎉 Welcome aboard,', args.client + '!');
  }
}

main();
