const form = document.getElementById('price-form');
const chat = document.getElementById('chat');
const suggestions = document.querySelectorAll('.suggestion');
const promptInput = document.getElementById('prompt');
const productInput = document.getElementById('product');
const priceInput = document.getElementById('customer-price');
const API_BASE_URL = 'https://pricematch-i4ccvq.fly.dev';

const verdictPanel = document.getElementById('verdict-panel');
const verdictBadge = document.getElementById('verdict-badge');
const confidenceLine = document.getElementById('confidence-line');
const verdictExplanation = document.getElementById('verdict-explanation');
const cmpCustomerPrice = document.getElementById('cmp-customer-price');
const cmpMarketAverage = document.getElementById('cmp-market-average');
const cmpRange = document.getElementById('cmp-range');
const cmpLowest = document.getElementById('cmp-lowest');
const cmpDifference = document.getElementById('cmp-difference');
const listingsList = document.getElementById('listings-list');
const limitationsFootnote = document.getElementById('limitations-footnote');

const disambiguationPanel = document.getElementById('disambiguation-panel');
const disambiguationBadge = document.getElementById('disambiguation-badge');
const disambiguationText = document.getElementById('disambiguation-text');
const tiersList = document.getElementById('tiers-list');
const candidatesList = document.getElementById('candidates-list');
const agentPipeline = document.getElementById('agent-pipeline');
const agentStages = document.getElementById('agent-stages');
const pipelineStatus = document.getElementById('pipeline-status');

let lastPayload = null;

function formatMoney(value) {
  return value === null || value === undefined ? '—' : `$${Number(value).toFixed(2)}`;
}

function renderVerdict(data) {
  if (!data || !data.verdict) {
    verdictPanel.hidden = true;
    return;
  }

  verdictPanel.hidden = false;
  verdictPanel.dataset.code = data.verdict.code;
  verdictBadge.textContent = data.verdict.label;
  verdictExplanation.textContent = data.verdict.explanation;

  const confidence = data.confidence || {};
  const matchLabel = {
    confirmed: 'confirmed match',
    likely: 'likely match',
    keyword_match: 'keyword match only',
    unknown: 'match unknown',
  }[confidence.productMatch] || 'match unknown';
  confidenceLine.textContent = `Confidence: ${confidence.level || 'low'} · Product match: ${matchLabel}`;

  const cmp = data.comparison || {};
  cmpCustomerPrice.textContent = formatMoney(cmp.customerPrice);
  cmpMarketAverage.textContent = formatMoney(cmp.marketAverage);
  const range = cmp.comparableRange || {};
  cmpRange.textContent =
    range.low !== null && range.low !== undefined
      ? `${formatMoney(range.low)} – ${formatMoney(range.high)}`
      : '—';
  const lowest = cmp.lowestComparable || {};
  cmpLowest.textContent = formatMoney(lowest.price);
  cmpDifference.textContent =
    lowest.difference !== null && lowest.difference !== undefined
      ? `${lowest.difference >= 0 ? '+' : ''}${formatMoney(lowest.difference)} (${lowest.percentageDifference}%)`
      : '—';

  listingsList.innerHTML = '';
  (data.listings || []).forEach((listing) => {
    const li = document.createElement('li');
    li.className = 'listing-item';
    li.innerHTML = `
      <span class="listing-name">${listing.name}</span>
      <span class="listing-price">${formatMoney(listing.price)}</span>
      <span class="listing-source">${listing.source}</span>
      <span class="listing-match">keyword match</span>
    `;
    listingsList.appendChild(li);
  });

  limitationsFootnote.textContent = (data.limitations || []).join(' ');

  renderDisambiguation(data.disambiguation);
}

function renderDisambiguation(disambiguation) {
  if (!disambiguation) {
    disambiguationPanel.hidden = true;
    return;
  }

  disambiguationPanel.hidden = false;
  disambiguationPanel.dataset.status = disambiguation.status;
  disambiguationBadge.textContent = disambiguation.confidence;
  disambiguationText.textContent = disambiguation.verdict_text;

  tiersList.innerHTML = '';
  const tiers = disambiguation.tiers || [];
  if (disambiguation.status === 'tier_ambiguous' && tiers.length) {
    tiersList.hidden = false;
    tiers.forEach((tier) => {
      const li = document.createElement('li');
      li.className = 'tier-item';
      li.innerHTML = `
        <div class="tier-header">
          <span class="tier-label">${tier.label}</span>
          <span class="tier-range">${formatMoney(tier.low)} – ${formatMoney(tier.high)}</span>
        </div>
        <span class="tier-examples">${tier.examples.join(', ')}</span>
      `;
      tiersList.appendChild(li);
    });
  } else {
    tiersList.hidden = true;
  }

  candidatesList.innerHTML = '';
  const candidates = disambiguation.candidates || [];
  if ((disambiguation.status === 'ambiguous' || disambiguation.status === 'tier_ambiguous') && candidates.length) {
    candidatesList.hidden = false;
    candidates.forEach((candidate) => {
      const li = document.createElement('li');
      li.className = 'candidate-item';
      li.innerHTML = `
        <span class="candidate-name">${candidate.name}</span>
        <span class="candidate-price">${formatMoney(candidate.price)}</span>
        <span class="candidate-source">${candidate.source}</span>
      `;
      li.addEventListener('click', () => selectCandidate(candidate.index));
      candidatesList.appendChild(li);
    });
  } else {
    candidatesList.hidden = true;
  }
}

async function selectCandidate(index) {
  if (!lastPayload) return;
  const payload = { ...lastPayload, selected_listing_index: index };
  addMessage(`I have this one.`, 'user');
  addMessage('Confirming against that listing...', 'bot');
  await submitPayload(payload);
}

function addMessage(text, type = 'bot') {
  const div = document.createElement('div');
  div.className = `message ${type}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function resetPipeline() {
  agentPipeline.hidden = false;
  agentStages.innerHTML = '';
  pipelineStatus.textContent = 'Running';
}

function renderAgentStage(stage) {
  const card = document.createElement('article');
  card.className = 'agent-stage';

  const header = document.createElement('div');
  header.className = 'agent-stage-header';
  const title = document.createElement('strong');
  title.textContent = stage.title || stage.agent;
  const badge = document.createElement('span');
  badge.className = 'agent-stage-badge';
  badge.textContent = 'Complete';
  header.append(title, badge);

  const summary = document.createElement('p');
  summary.className = 'agent-stage-summary';
  summary.textContent = stage.summary || 'No summary returned.';

  const output = document.createElement('pre');
  output.className = 'agent-stage-output';
  output.textContent = JSON.stringify(stage, null, 2);

  card.append(header, summary, output);
  agentStages.appendChild(card);
  chat.scrollTop = chat.scrollHeight;
}

function extractFieldsFromPrompt(text) {
  const lower = text.toLowerCase();
  const productMatch = text.match(/for\s+(.+?)(?:\s+at\s+|\s+for\s+\$|\s+price\s+of\s+|\s+at\s+\$)/i);
  const priceMatch = text.match(/\$?([0-9]+(?:\.[0-9]{1,2})?)/);

  return {
    product: productMatch ? productMatch[1].trim() : productInput.value.trim(),
    customer_price: priceMatch ? priceMatch[1] : priceInput.value.trim(),
  };
}

async function submitPayload(payload) {
  try {
    resetPipeline();
    const response = await fetch(`${API_BASE_URL}/api/verify-price/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }

    if (!response.body) throw new Error('The live pipeline is unavailable.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let data = null;
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === 'agent') {
          renderAgentStage(event.stage);
        } else if (event.type === 'complete') {
          data = event.result;
          pipelineStatus.textContent = 'Complete';
        } else if (event.type === 'error') {
          throw new Error(event.message || 'Pipeline failed');
        }
      }
      if (done) break;
    }
    if (!data) throw new Error('The pipeline ended without a final answer.');

    lastPayload = { product: payload.product, customer_price: payload.customer_price, zipcode: payload.zipcode };
    chat.removeChild(chat.lastElementChild);
    addMessage(data.reply, 'bot');
    renderVerdict(data);
  } catch (error) {
    chat.removeChild(chat.lastElementChild);
    addMessage(`Could not verify the price: ${error.message}`, 'bot');
    verdictPanel.hidden = true;
    disambiguationPanel.hidden = true;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const rawPrompt = (formData.get('prompt') || '').toString().trim();
  const parsed = extractFieldsFromPrompt(rawPrompt);
  const payload = Object.fromEntries(formData.entries());
  payload.product = parsed.product || payload.product || 'unknown product';
  payload.customer_price = parsed.customer_price || payload.customer_price || 'unknown price';
  delete payload.selected_listing_index;

  addMessage(rawPrompt || `Product: ${payload.product} | Price: ${payload.customer_price}`, 'user');
  addMessage('Checking the price now...', 'bot');
  verdictPanel.hidden = true;
  disambiguationPanel.hidden = true;

  await submitPayload(payload);
});

suggestions.forEach((button) => {
  button.addEventListener('click', () => {
    promptInput.value = `Verify the price for ${button.dataset.product} at $${button.dataset.price}`;
    productInput.value = button.dataset.product;
    priceInput.value = button.dataset.price;
    form.requestSubmit();
  });
});
