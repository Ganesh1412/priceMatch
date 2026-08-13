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
}

function addMessage(text, type = 'bot') {
  const div = document.createElement('div');
  div.className = `message ${type}`;
  div.textContent = text;
  chat.appendChild(div);
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

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const rawPrompt = (formData.get('prompt') || '').toString().trim();
  const parsed = extractFieldsFromPrompt(rawPrompt);
  const payload = Object.fromEntries(formData.entries());
  payload.product = parsed.product || payload.product || 'unknown product';
  payload.customer_price = parsed.customer_price || payload.customer_price || 'unknown price';

  addMessage(rawPrompt || `Product: ${payload.product} | Price: ${payload.customer_price}`, 'user');
  addMessage('Checking the price now...', 'bot');
  verdictPanel.hidden = true;

  try {
    const response = await fetch(`${API_BASE_URL}/api/verify-price`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Request failed');
    }

    chat.removeChild(chat.lastElementChild);
    addMessage(data.reply, 'bot');
    renderVerdict(data);
  } catch (error) {
    chat.removeChild(chat.lastElementChild);
    addMessage(`Could not verify the price: ${error.message}`, 'bot');
    verdictPanel.hidden = true;
  }
});

suggestions.forEach((button) => {
  button.addEventListener('click', () => {
    promptInput.value = `Verify the price for ${button.dataset.product} at $${button.dataset.price}`;
    productInput.value = button.dataset.product;
    priceInput.value = button.dataset.price;
    form.requestSubmit();
  });
});
