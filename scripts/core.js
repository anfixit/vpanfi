const state = {
  theme: localStorage.getItem('vpanfi-theme') || 'light',
  loggedIn: localStorage.getItem('vpanfi-demo-session') === '1',
  platform: 'android',
  devices: [
    { id: 1, name: 'Honor Magic 7 Pro', type: 'Android', icon: '📱', lastSeen: 'Сейчас', active: true },
    { id: 2, name: 'MacBook Air', type: 'macOS', icon: '💻', lastSeen: '5 минут назад', active: true },
    { id: 3, name: 'Домашний телевизор', type: 'Android TV', icon: '📺', lastSeen: 'Вчера, 22:14', active: true },
  ],
  extraSlots: 1,
  autoRenew: true,
  chat: [
    { who: 'bot', text: 'Здравствуйте! Я Анфиса 👋 Чем могу помочь?' },
    { who: 'bot', text: 'Можно просто описать проблему своими словами.' },
  ],
};

document.documentElement.dataset.theme = state.theme;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const platforms = {
  android: { label: 'Android', icon: '🤖', app: 'HAPP', store: 'Google Play', alternatives: ['Hiddify', 'v2RayTun', 'NekoBox'] },
  ios: { label: 'iPhone / iPad', icon: '●', app: 'HAPP', store: 'App Store', alternatives: ['Shadowrocket', 'Quantumult X', 'FoXray'] },
  windows: { label: 'Windows', icon: '⊞', app: 'HAPP', store: 'Скачать установщик', alternatives: ['v2rayN', 'Hiddify', 'NekoRay'] },
  macos: { label: 'macOS', icon: '◆', app: 'HAPP', store: 'Скачать приложение', alternatives: ['Hiddify', 'FoXray', 'NekoRay'] },
  linux: { label: 'Linux', icon: '◒', app: 'HAPP', store: 'Скачать пакет', alternatives: ['NekoRay', 'Hiddify', 'sing-box'] },
  'android-tv': { label: 'Android TV', icon: '▣', app: 'HAPP', store: 'Google Play', alternatives: ['Hiddify', 'v2RayTun'] },
  'apple-tv': { label: 'Apple TV', icon: '◆', app: 'HAPP', store: 'App Store', alternatives: ['Shadowrocket', 'FoXray'] },
};

const pageMeta = {
  app: ['Главная', 'Здесь всё самое важное.'],
  connect: ['Подключение', 'Выберите устройство и следуйте короткой инструкции.'],
  devices: ['Устройства', 'Все подключённые устройства в одном месте.'],
  plans: ['Тарифы', 'Продлевайте заранее, оплаченные дни суммируются.'],
  payments: ['Платежи', 'Баланс, автопродление и история операций.'],
  support: ['Поддержка', 'Анфиса рядом и готова помочь.'],
  profile: ['Профиль', 'Настройки аккаунта и способы входа.'],
  admin: ['Панель управления', 'Пользователи, подписки и состояние сервиса.'],
};

function setTheme(theme) {
  state.theme = theme;
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('vpanfi-theme', theme);
  $$('.theme-icon').forEach((el) => { el.textContent = theme === 'dark' ? '☾' : '☀'; });
}
setTheme(state.theme);

function toast(title, text = '') {
  const root = $('#toast-root');
  const node = document.createElement('div');
  node.className = 'toast';
  node.innerHTML = `<i>✓</i><div><strong>${escapeHtml(title)}</strong>${text ? `<span>${escapeHtml(text)}</span>` : ''}</div>`;
  root.appendChild(node);
  setTimeout(() => node.remove(), 3600);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
}

function closeModal() { $('#modal-root').innerHTML = ''; }
function modal(content) {
  $('#modal-root').innerHTML = `<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" onclick="event.stopPropagation()"><button class="modal-close" data-action="close-modal" aria-label="Закрыть">×</button>${content}</div></div>`;
}

function loginModal(trial = false) {
  modal(`
    <div class="modal-header">
      <img src="./assets/mascot/${trial ? 'success' : 'welcome'}.svg" alt="Анфиса" />
      <h2>${trial ? 'Начнём бесплатную неделю' : 'Вход в кабинет'}</h2>
      <p>${trial ? 'Создайте аккаунт удобным способом. Оплата не нужна.' : 'Используйте привычный способ входа.'}</p>
    </div>
    <div class="login-options">
      <button class="login-option" data-login="telegram">✈ Войти через Telegram</button>
      <button class="login-option" data-login="yandex">Я Войти через Яндекс</button>
      <button class="login-option" data-login="vk">VK Войти через VK</button>
    </div>
    <div class="login-separator">или логин и пароль</div>
    <form class="login-form" id="login-form">
      <input name="login" autocomplete="username" placeholder="Логин или email" required />
      <input name="password" type="password" autocomplete="current-password" placeholder="Пароль" required minlength="4" />
      <button class="button button-primary full" type="submit">${trial ? 'Создать аккаунт' : 'Войти'}</button>
    </form>
    <p class="modal-note">Продолжая, Вы соглашаетесь с условиями использования и политикой конфиденциальности.</p>
  `);
}

function countriesModal() {
  const countries = ['Нидерланды','Германия','Финляндия','Франция','Польша','Казахстан','США','Канада','Великобритания','Испания','Италия','Швеция','Швейцария','Австрия','Чехия','Япония','Сингапур','Турция'];
  modal(`<div class="modal-header"><img src="./assets/mascot/jungle.svg" alt="Анфиса" /><h2>Страны подключения</h2><p>Полный список будет обновляться автоматически из панели управления.</p></div><div class="flag-cloud" style="margin-top:18px">${countries.map((x) => `<span>${x}</span>`).join('')}</div>`);
}

function paymentModal(plan = 'month') {
  const plans = { month: ['1 месяц', '300 ₽'], quarter: ['3 месяца', '800 ₽'], 'half-year': ['6 месяцев', '1 500 ₽'] };
  const [title, price] = plans[plan] || plans.month;
  modal(`<div class="modal-header"><img src="./assets/mascot/banana.svg" alt="Анфиса с бананом" /><h2>${title}</h2><p>Оплата через СБП. После подтверждения дни добавятся автоматически.</p></div><div class="panel" style="margin-top:18px;text-align:center"><span class="panel-subtitle">К оплате</span><div class="balance-amount">${price}</div><div class="qr-fake" style="width:180px;height:180px"></div><button class="button button-primary full" data-action="demo-payment">Я оплатил(а)</button></div>`);
}

function platformModal(key) {
  const p = platforms[key] || platforms.android;
  modal(`<div class="modal-header"><img src="./assets/mascot/phone.svg" alt="Анфиса с телефоном" /><h2>${p.label}</h2><p>Мы рекомендуем ${p.app}. Другие варианты доступны в кабинете.</p></div><button class="button button-primary full" style="margin-top:18px" data-action="start-trial">Начать бесплатно</button>`);
}

function routeName() {
  const hash = location.hash || '#/';
  return hash.startsWith('#/') ? hash.slice(2).split('?')[0] || '' : '';
}

function navigate(route) { location.hash = `#/${route}`; }

function showPublic() {
  $('#public-app').hidden = false;
  $('#site-header').hidden = false;
  $('#site-footer').hidden = false;
  $('#cabinet-app').hidden = true;
  document.body.classList.remove('in-cabinet');
}

function showCabinet(route) {
  $('#public-app').hidden = true;
  $('#site-header').hidden = true;
  $('#site-footer').hidden = true;
  $('#cabinet-app').hidden = false;
  document.body.classList.add('in-cabinet');
  const [title, subtitle] = pageMeta[route] || pageMeta.app;
  $('#page-title').innerHTML = `<h1>${title}</h1><p>${subtitle}</p>`;
  $$('#cabinet-nav a').forEach((a) => a.classList.toggle('active', a.dataset.route === route));
  $('#cabinet-view').innerHTML = renderCabinet(route);
  bindDynamic();
}
