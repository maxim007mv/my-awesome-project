document.addEventListener('DOMContentLoaded', () => {
  // Current year in footer
  const y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  // Mobile nav toggle
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.main-nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const wasHidden = nav.classList.contains('hidden');
      nav.classList.toggle('hidden');
      const isOpen = wasHidden;
      toggle.setAttribute('aria-expanded', String(isOpen));
    });
    // Close on link click (mobile)
    nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
      nav.classList.add('hidden');
      toggle.setAttribute('aria-expanded', 'false');
    }));
  }

  // If URL has #form or #gen, jump to form
  if (location.hash === '#form' || location.hash === '#gen') {
    const formAnchor = document.getElementById('form');
    if (formAnchor) {
      setTimeout(() => formAnchor.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
      // Focus first control (wizard or legacy form)
      const first = document.querySelector('#route-wizard input, #route-wizard textarea, #route-form input');
      if (first) setTimeout(() => first.focus(), 300);
    }
  }

  // Contact form (on contacts.html)
  // Route generation form
  const form = document.querySelector('#route-form');
  if (form) {
    const fields = [
      form.querySelector('[name="name"]'),
      form.querySelector('[name="email"]'),
      form.querySelector('[name="message"]')
    ];
    const markInvalid = (el) => {
      el.classList.add('ring-2','ring-red-500/60','border-red-500/60');
    };
    const clearInvalid = (el) => {
      el.classList.remove('ring-2','ring-red-500/60','border-red-500/60');
    };

    fields.forEach(f => f && f.addEventListener('input', () => clearInvalid(f)));

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = fields[0];
      const email = fields[1];
      const message = fields[2];

      let valid = true;
      [name, email, message].forEach(f => {
        if (!f.value.trim()) { markInvalid(f); valid = false; }
        else clearInvalid(f);
      });
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
        markInvalid(email); valid = false;
      }
      if (!valid) return;

      // Try server-side generation first
      const progress = document.getElementById('route-progress');
      const out = document.getElementById('route-result');
      if (out) out.classList.add('hidden');
      if (progress) {
        progress.classList.remove('hidden');
        progress.textContent = `🔄 Генерирую ваш персональный маршрут...`;
        try {
          const res = await fetch('http://localhost:8000/api/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              name: name.value.trim(),
              email: email.value.trim(),
              message: message.value.trim(),
            })
          });
          if (!res.ok) throw new Error('Server error');
          const data = await res.json();
          if (out) {
            out.innerHTML = renderServerItinerary(data);
            out.classList.remove('hidden');
            out.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
          setTimeout(() => progress.classList.add('hidden'), 400);
          form.reset();
          return;
        } catch (err) {
          // Fallback to client demo
          let p = 10;
          const tick = setInterval(() => {
            p += 10;
            if (p >= 100) {
              p = 100;
              clearInterval(tick);
              const itinerary = generateItinerary({
                name: name.value.trim(),
                email: email.value.trim(),
                message: message.value.trim(),
              });
              if (out) {
                out.innerHTML = renderItinerary(itinerary);
                out.classList.remove('hidden');
                out.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
              setTimeout(() => progress.classList.add('hidden'), 800);
              form.reset();
            }
          }, 160);
        }
      }
    });
  }

  // --- 10-step wizard on generate.html ---
  const wizard = document.getElementById('route-wizard');
  if (wizard) {
    const total = 10;
    let step = 1;
    const state = {
      time: '', duration: '', type: '', start_point: '', budget: '',
      preferences: '', activities: [], food: '', food_special: '', transport: '', limits: ''
    };
    const stepLabel = document.getElementById('wizard-step-label');
    const progressBar = document.getElementById('wizard-progress');
    const prevBtn = document.getElementById('wizard-prev');
    const nextBtn = document.getElementById('wizard-next');
    const out = document.getElementById('route-result');
    const progress = document.getElementById('route-progress');

    function showStep(i) {
      wizard.querySelectorAll('[data-step]').forEach(el => el.classList.add('hidden'));
      const current = wizard.querySelector(`[data-step="${i}"]`);
      if (current) current.classList.remove('hidden');
      if (stepLabel) stepLabel.textContent = `Шаг ${i} из ${total}`;
      if (progressBar) progressBar.style.width = `${Math.max(10, Math.round(i/total*100))}%`;
      prevBtn.disabled = i === 1;
      nextBtn.textContent = i === total ? 'Сгенерировать' : 'Далее';
    }

    function markInvalid(el) {
      if (!el) return; el.classList.add('ring-2','ring-red-500/60','border-red-500/60');
      setTimeout(() => el.classList.remove('ring-2','ring-red-500/60','border-red-500/60'), 1200);
    }

    function getRadio(name) {
      const el = wizard.querySelector(`input[name="${name}"]:checked`);
      return el ? el.value : '';
    }
    function getChecked(name) {
      return Array.from(wizard.querySelectorAll(`input[name="${name}"]:checked`)).map(i => i.value);
    }

    function collect(i) {
      switch (i) {
        case 1: {
          const r = getRadio('time');
          const free = wizard.querySelector('#time-free');
          state.time = (free && free.value.trim()) || r;
          if (!state.time) { markInvalid(free); return false; }
          return true;
        }
        case 2: {
          state.duration = getRadio('duration');
          if (!state.duration) { markInvalid(wizard.querySelector('[name="duration"]')); return false; }
          return true;
        }
        case 3: {
          state.type = getRadio('type');
          if (!state.type) { markInvalid(wizard.querySelector('[name="type"]')); return false; }
          return true;
        }
        case 4: {
          const sp = wizard.querySelector('#start-point');
          state.start_point = sp ? sp.value.trim() : '';
          if (!state.start_point) { markInvalid(sp); return false; }
          return true;
        }
        case 5: {
          state.budget = getRadio('budget');
          if (!state.budget) { markInvalid(wizard.querySelector('[name="budget"]')); return false; }
          return true;
        }
        case 6: {
          const p = wizard.querySelector('#preferences');
          state.preferences = p ? p.value.trim() : '';
          return true;
        }
        case 7: {
          state.activities = getChecked('activities');
          return true;
        }
        case 8: {
          state.food = getRadio('food');
          const fs = wizard.querySelector('#food-special');
          state.food_special = fs ? fs.value.trim() : '';
          return true;
        }
        case 9: {
          state.transport = getRadio('transport');
          if (!state.transport) { markInvalid(wizard.querySelector('[name="transport"]')); return false; }
          return true;
        }
        case 10: {
          const l = wizard.querySelector('#limits');
          state.limits = l ? l.value.trim() : '';
          return true;
        }
      }
      return true;
    }

    function composeMessage(s) {
      return (
        `Город и стартовая точка: ${s.start_point}\n` +
        `Время начала: ${s.time}\n` +
        `Длительность: ${s.duration}\n` +
        `Тип прогулки: ${s.type}\n` +
        `Бюджет: ${s.budget}\n` +
        `Предпочтения (места/районы): ${s.preferences || 'нет'}\n` +
        `Активности: ${(s.activities && s.activities.length ? s.activities.join(', ') : 'по выбору') }\n` +
        `Питание: ${s.food}${s.food_special ? ` (особые: ${s.food_special})` : ''}\n` +
        `Транспорт: ${s.transport}\n` +
        `Ограничения: ${s.limits || 'нет'}`
      );
    }

    async function generateNow() {
      const message = composeMessage(state);
      if (out) out.classList.add('hidden');
      if (progress) progress.classList.remove('hidden');
      try {
        const res = await fetch('http://localhost:8000/api/route', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message })
        });
        if (!res.ok) throw new Error('Server error');
        const data = await res.json();
        if (out) {
          out.innerHTML = renderServerItinerary(data);
          out.classList.remove('hidden');
          out.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      } catch (e) {
        // fallback
        const itinerary = generateItinerary({ name:'', email:'', message });
        if (out) {
          out.innerHTML = renderItinerary(itinerary);
          out.classList.remove('hidden');
          out.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      } finally {
        if (progress) setTimeout(() => progress.classList.add('hidden'), 600);
      }
    }

    prevBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (step > 1) { step -= 1; showStep(step); }
    });
    nextBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!collect(step)) return;
      if (step < total) {
        step += 1; showStep(step);
      } else {
        // finish and generate
        wizard.classList.add('hidden');
        await generateNow();
      }
    });

    // Initial
    showStep(step);
  }

  // Feedback form
  const feedbackForm = document.querySelector('#feedback-form');
  if (feedbackForm) {
    const get = (sel) => feedbackForm.querySelector(sel);
    const fields = [get('[name="name"]'), get('[name="email"]'), get('[name="subject"]'), get('[name="message"]')];
    const markInvalid = (el) => el && el.classList.add('ring-2','ring-red-500/60','border-red-500/60');
    const clearInvalid = (el) => el && el.classList.remove('ring-2','ring-red-500/60','border-red-500/60');
    fields.forEach(f => f && f.addEventListener('input', () => clearInvalid(f)));

    feedbackForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = get('[name="name"]').value.trim();
      const email = get('[name="email"]').value.trim();
      const subject = get('[name="subject"]').value.trim();
      const message = get('[name="message"]').value.trim();
      let valid = true;
      if (!message) { markInvalid(get('[name="message"]')); valid = false; }
      const emailField = get('[name="email"]');
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { markInvalid(emailField); valid = false; }
      if (!valid) return;

      const result = document.getElementById('feedback-result');
      if (result) {
        result.classList.remove('hidden');
        result.textContent = '🔄 Отправляю отзыв...';
      }
      try {
        const res = await fetch('http://localhost:8000/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, email, subject, message })
        });
        if (!res.ok) throw new Error('Server error');
        if (result) result.textContent = '✅ Спасибо! Отзыв отправлен.';
        feedbackForm.reset();
      } catch (err) {
        if (result) result.textContent = '⚠️ Не удалось отправить. Проверьте, что сервер запущен.';
      } finally {
        setTimeout(() => result && result.classList.add('hidden'), 3500);
      }
    });
  }
});

// --- Simple client-side itinerary builder (no external APIs) ---
function pick(arr, n = 3) {
  const copy = [...arr];
  const result = [];
  while (copy.length && result.length < n) {
    const i = Math.floor(Math.random() * copy.length);
    result.push(copy.splice(i, 1)[0]);
  }
  return result;
}

function parseCity(text) {
  const t = text.toLowerCase();
  if (/(санкт|питер|спб|petersburg)/i.test(t)) return 'Санкт‑Петербург';
  if (/(moscow|москва)/i.test(t)) return 'Москва';
  return 'Москва';
}

function detectTopics(text) {
  const t = text.toLowerCase();
  const topics = [];
  if (/(стрит|граффити|андеграунд|сквот)/.test(t)) topics.push('street');
  if (/(архит|брутал|конструктив)/.test(t)) topics.push('arch');
  if (/(парк|набереж|прогулк)/.test(t)) topics.push('parks');
  if (/(музе|галер|выстав)/.test(t)) topics.push('museums');
  if (/(клуб|бар|ноч)/.test(t)) topics.push('clubs');
  if (topics.length === 0) topics.push('parks','museums');
  return topics.slice(0,3);
}

const PLACES = {
  'Москва': {
    street: [
      { name: 'Арт‑кластер «Флакон»', addr: 'Москва, Большая Новодмитровская, 36' },
      { name: 'Артплей', addr: 'Москва, Нижняя Сыромятническая, 10' },
      { name: 'Винзавод', addr: 'Москва, 4-й Сыромятнический пер., 1/8' },
    ],
    arch: [
      { name: 'Дом Наркомфина', addr: 'Москва, Новинский бульвар, 25 корпус 1' },
      { name: 'Дом культуры имени Зуева', addr: 'Москва, ул. Лесная, 18' },
      { name: 'Шуховская башня', addr: 'Москва, ул. Шаболовка, 37' },
    ],
    parks: [
      { name: 'Парк Горького', addr: 'Москва, Крымский Вал, 9' },
      { name: 'Музеон', addr: 'Москва, Крымский Вал, 2' },
      { name: 'Зарядье', addr: 'Москва, ул. Варварка, 6' },
    ],
    museums: [
      { name: 'Третьяковская галерея', addr: 'Москва, Лаврушинский пер., 10' },
      { name: 'Новая Третьяковка', addr: 'Москва, Крымский Вал, 10' },
      { name: 'ГЭС‑2', addr: 'Москва, Болотная наб., 15' },
    ],
    clubs: [
      { name: 'Mutabor', addr: 'Москва, Шарикоподшипниковская, 13' },
      { name: 'Powerhouse', addr: 'Москва, Гончарная ул., 7' },
      { name: '16 ТОНН', addr: 'Москва, Пресненский Вал, 6' },
    ]
  },
  'Санкт‑Петербург': {
    street: [
      { name: 'Севкабель Порт', addr: 'Санкт‑Петербург, Кожевенная линия, 40' },
      { name: 'Новая Голландия', addr: 'Санкт‑Петербург, наб. Адмиралтейского канала, 2' },
      { name: 'Берег Ткачи', addr: 'Санкт‑Петербург, наб. Обводного канала, 60' },
    ],
    arch: [
      { name: 'Казармы Новой Голландии', addr: 'Санкт‑Петербург, наб. Адмиралтейского канала, 2' },
      { name: 'Дом Зингера', addr: 'Санкт‑Петербург, Невский проспект, 28' },
      { name: 'Эрарта квартал', addr: 'Санкт‑Петербург, 29-я линия В.О., 2' },
    ],
    parks: [
      { name: 'Летний сад', addr: 'Санкт‑Петербург, Летний сад' },
      { name: 'Михайловский сад', addr: 'Санкт‑Петербург, Инженерная ул., 4' },
      { name: 'Набережная Мойки', addr: 'Санкт‑Петербург, наб. р. Мойки' },
    ],
    museums: [
      { name: 'Русский музей', addr: 'Санкт‑Петербург, Инженерная ул., 4' },
      { name: 'Эрмитаж', addr: 'Санкт‑Петербург, Дворцовая пл., 2' },
      { name: 'Эрарта', addr: 'Санкт‑Петербург, 29-я линия В.О., 2' },
    ],
    clubs: [
      { name: 'Грибоедов', addr: 'Санкт‑Петербург, ул. Воронежская, 2а' },
      { name: 'Бар 812', addr: 'Санкт‑Петербург, Наб. Фонтанки, 90' },
      { name: 'Stackenschneider', addr: 'Санкт‑Петербург, Владимирский пр., 19' },
    ]
  }
};

function generateItinerary({ name, email, message }) {
  const city = parseCity(message || '');
  const topics = detectTopics(message || '');
  const pool = PLACES[city];
  const selections = [];
  topics.forEach(t => {
    if (pool[t]) selections.push(...pick(pool[t], 2));
  });
  const start = new Date();
  start.setMinutes(0, 0, 0);
  let hour = start.getHours() < 9 ? 12 : start.getHours();
  const stops = selections.slice(0, 5).map((p, idx) => {
    const from = `${String(hour).padStart(2,'0')}:00`;
    hour += 1;
    const to = `${String(hour).padStart(2,'0')}:00`;
    return { ...p, time: `${from} – ${to}` };
  });
  const routeLink = buildYandexRoute(city, stops);
  return { city, name, stops, routeLink };
}

function buildYandexRoute(city, stops) {
  if (!stops || !stops.length) return '';
  const parts = stops.map(s => encodeURIComponent(`${city}, ${s.addr}`)).join('~');
  return `https://yandex.ru/maps/?rtext=${parts}&rtt=auto`;
}

function renderItinerary({ city, name, stops, routeLink }) {
  const hi = name ? `, ${name}` : '';
  const items = stops.map(s => {
    const link = `https://yandex.ru/maps/?text=${encodeURIComponent(`${city} ${s.name}`)}`;
    return `<li class="flex flex-col md:flex-row md:items-center md:justify-between gap-1 p-2 rounded-lg hover:bg-white/5">
      <div>
        <div class="font-semibold">${s.time} | ${s.name}</div>
        <div class="text-slate-400 text-sm">${s.addr}</div>
      </div>
      <a class="text-cyan-300 hover:text-cyan-200" href="${link}" target="_blank" rel="noopener">Открыть на карте</a>
    </li>`;
  }).join('');
  const openAll = routeLink ? `<a class="inline-block mt-3 px-3 py-2 rounded-xl font-semibold text-slate-900 bg-gradient-to-r from-violet-500 to-cyan-400 shadow-[0_0_24px_rgba(124,58,237,0.35)] hover:shadow-[0_0_40px_rgба(124,58,237,0.45)] transition" href="${routeLink}" target="_blank" rel="noopener">Открыть маршрут в Яндекс.Картах</a>` : '';
  return `
    <div class="rounded-2xl p-4 bg-white/5 backdrop-blur-xl ring-1 ring-white/15 shadow-xl">
      <div class="font-unbounded text-xl mb-2">Твой маршрут${hi}</div>
      <ul class="divide-y divide-white/10">${items}</ul>
      ${openAll}
      <div class="mt-2 text-slate-400 text-xs">Демо‑генерация на клиенте без внешних API.</div>
    </div>
  `;
}

function renderServerItinerary(data) {
  const city = data.city || '';
  const stops = Array.isArray(data.stops) ? data.stops : [];
  const items = stops.map(s => {
    const time = s.time ? `${s.time} | ` : '';
    const addr = s.address || '';
    const link = `https://yandex.ru/maps/?text=${encodeURIComponent(`${city} ${s.name||''}`)}`;
    return `<li class="flex flex-col md:flex-row md:items-center md:justify-between gap-1 p-2 rounded-lg hover:bg-white/5">
      <div>
        <div class="font-semibold">${time}${s.name||''}</div>
        <div class="text-slate-400 text-sm">${addr}</div>
      </div>
      <a class="text-cyan-300 hover:text-cyan-200" href="${link}" target="_blank" rel="noopener">Открыть на карте</a>
    </li>`;
  }).join('');
  const openAll = data.map_url ? `<a class="inline-block mt-3 px-3 py-2 rounded-xl font-semibold text-slate-900 bg-gradient-to-r from-violet-500 to-cyan-400 shadow-[0_0_24px_rgba(124,58,237,0.35)] hover:shadow-[0_0_40px_rgba(124,58,237,0.45)] transition" href="${data.map_url}" target="_blank" rel="noopener">Открыть маршрут в Яндекс.Картах</a>` : '';
  return `
    <div class="rounded-2xl p-4 bg-white/5 backdrop-blur-xl ring-1 ring-white/15 shadow-xl">
      <div class="font-unbounded text-xl mb-2">Твой маршрут</div>
      <ul class="divide-y divide-white/10">${items}</ul>
      ${openAll}
      <div class="mt-2 text-slate-400 text-xs">Сгенерировано с использованием DeepSeek + Яндекс Геокодер (локальный сервер).</div>
    </div>
  `;
}
