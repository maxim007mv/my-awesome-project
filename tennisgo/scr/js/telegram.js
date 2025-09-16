// Global Telegram form sender for all pages
// Configure: you can override via window.TG_BOT_TOKEN, window.TG_CHAT_ID,
// localStorage.TG_CHAT_ID, or <meta name="tg-chat-id" content="...">.
(function(){
  if (window.__TG_FORM_SENDER__) return;
  window.__TG_FORM_SENDER__ = true;

  // Defaults (can be overridden as described above)
  const TOKEN = (window.TG_BOT_TOKEN || '').trim() || '5826225693:AAH8ji34IeGmEa93X0O_0PDfLS7ojBGD_R0';
  let CHAT_ID = (window.TG_CHAT_ID || '').trim();
  if (!CHAT_ID) { try { CHAT_ID = (localStorage.getItem('TG_CHAT_ID') || '').trim(); } catch(_) {} }
  if (!CHAT_ID) { const meta = document.querySelector('meta[name="tg-chat-id"]'); CHAT_ID = (meta?.getAttribute('content') || '').trim(); }
  if (!CHAT_ID) { CHAT_ID = '-1002907206668'; }

  function warnOnce(msg){ if (window.__TG_WARNED__) return; window.__TG_WARNED__ = true; console.warn(msg); }

  // Optional gateway (Python backend). Sources: window.TG_GATEWAY or <meta name="tg-gateway">
  const GATEWAY = (function(){
    const meta = document.querySelector('meta[name="tg-gateway"]');
    const v = (window.TG_GATEWAY || meta?.getAttribute('content') || '').trim();
    return v || '';
  })();

  async function tgSendViaGateway(payload){
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (window.TG_INBOUND_SECRET) headers['X-Auth'] = String(window.TG_INBOUND_SECRET);
      await fetch(GATEWAY, { method: 'POST', headers, body: JSON.stringify(payload) });
    } catch (err){ console.warn('Gateway send failed:', err); }
  }

  async function tgSendDirect(text){
    if (!TOKEN || !CHAT_ID){ warnOnce('Telegram not configured: set window.TG_CHAT_ID or localStorage.TG_CHAT_ID.'); return; }
    const params = new URLSearchParams({ chat_id: CHAT_ID, text, parse_mode: 'HTML' });
    const url = `https://api.telegram.org/bot${TOKEN}/sendMessage?${params.toString()}`;
    try { await fetch(url, { method: 'GET', mode: 'no-cors', credentials: 'omit', referrerPolicy: 'no-referrer' }); } catch (err){ console.warn('Telegram send failed:', err); }
  }

  function sanitize(v){ return String(v ?? '').trim(); }

  function buildMessage(form){
    const map = {
      name: 'Имя', phone: 'Телефон', email: 'E‑mail', level: 'Уровень', topic: 'Тема',
      message: 'Сообщение', msg: 'Сообщение', location: 'Локация', loc: 'Локация'
    };
    const rows = [];
    rows.push('<b>📝 Новая заявка с сайта</b>');
    try { rows.push(`Страница: ${location.href}`); } catch(_){ }
    if (form.id) rows.push(`Форма: #${form.id}`);

    const seen = new Set();
    Array.from(form.elements || []).forEach(el => {
      if (!el || !('name' in el)) return;
      const name = sanitize(el.name || el.id);
      if (!name || seen.has(name)) return;
      if (el.type === 'button' || el.type === 'submit' || el.type === 'file') return;
      let value = '';
      if (el.tagName === 'SELECT') value = el.value;
      else if (el.type === 'checkbox') value = el.checked ? 'Да' : 'Нет';
      else value = el.value;
      value = sanitize(value);
      if (!value) return;
      seen.add(name);
      const label = map[name] || name;
      rows.push(`<b>${label}:</b> ${value}`);
    });
    return rows.join('\n');
  }

  function buildPayload(form){
    const out = { page: '', form_id: '' };
    try { out.page = location.href; } catch(_){}
    if (form?.id) out.form_id = form.id;
    const seen = new Set();
    Array.from(form?.elements || []).forEach(el => {
      const key = String(el?.name || el?.id || '').trim();
      if (!key || seen.has(key)) return;
      if (el.type === 'button' || el.type === 'submit' || el.type === 'file') return;
      let value = '';
      if (el.tagName === 'SELECT') value = el.value;
      else if (el.type === 'checkbox') value = el.checked ? 'Да' : 'Нет';
      else value = el.value;
      value = String(value ?? '').trim();
      if (!value) return;
      seen.add(key);
      out[key] = value;
    });
    return out;
  }

  document.addEventListener('submit', async (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    try {
      if (form.checkValidity && !form.checkValidity()) return;
      if (GATEWAY) {
        const payload = buildPayload(form);
        await tgSendViaGateway(payload);
      } else {
        const text = buildMessage(form);
        await tgSendDirect(text);
      }
    } catch(err){ /* already logged */ }
  }, true);
})();
