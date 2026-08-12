const form = document.getElementById('price-form');
const chat = document.getElementById('chat');
const suggestions = document.querySelectorAll('.suggestion');
const promptInput = document.getElementById('prompt');
const productInput = document.getElementById('product');
const priceInput = document.getElementById('customer-price');
const API_BASE_URL = 'https://pricematch-i4ccvq.fly.dev';

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
  } catch (error) {
    chat.removeChild(chat.lastElementChild);
    addMessage(`Could not verify the price: ${error.message}`, 'bot');
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
