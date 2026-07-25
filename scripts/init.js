function bindDynamic() {
  $$('[data-route-go]').forEach((el) => el.addEventListener('click', () => navigate(el.dataset.routeGo)));
  $$('[data-select-platform]').forEach((el) => el.addEventListener('click', () => { state.platform = el.dataset.selectPlatform; showCabinet('connect'); }));
  $$('[data-plan]').forEach((el) => el.addEventListener('click', () => paymentModal(el.dataset.plan)));
  $$('[data-remove-device]').forEach((el) => el.addEventListener('click', () => {
    const id = Number(el.dataset.removeDevice); state.devices = state.devices.filter((d) => d.id !== id); toast('Устройство отключено', 'При необходимости его можно подключить снова.'); showCabinet('devices');
  }));
  $$('[data-rename-device]').forEach((el) => el.addEventListener('click', () => {
    const id = Number(el.dataset.renameDevice); const d = state.devices.find((x) => x.id === id); const value = prompt('Новое название устройства', d?.name || ''); if (value && d) { d.name = value.trim(); showCabinet('devices'); }
  }));
  $('#chat-form')?.addEventListener('submit', (e) => {
    e.preventDefault(); const fd = new FormData(e.currentTarget); const text = String(fd.get('message') || '').trim(); if (!text) return; state.chat.push({ who: 'user', text }); showCabinet('support'); setTimeout(() => { state.chat.push({ who: 'bot', text: 'Поняла Вас. Сначала проверим самое простое: интернет на устройстве работает без приложения?' }); showCabinet('support'); $('#chat-messages')?.scrollTo({ top: 9999, behavior: 'smooth' }); }, 700);
  });
  $('#profile-form')?.addEventListener('submit', (e) => { e.preventDefault(); toast('Профиль сохранён'); });
}

function authenticate(source = 'account') {
  state.loggedIn = true; localStorage.setItem('vpanfi-demo-session', '1'); closeModal(); toast('Добро пожаловать!', source === 'trial' ? 'Бесплатная неделя уже активна.' : 'Рады снова Вас видеть.'); navigate('app');
}

function handleAction(action) {
  switch (action) {
    case 'toggle-theme': setTheme(state.theme === 'dark' ? 'light' : 'dark'); break;
    case 'open-login': loginModal(false); break;
    case 'start-trial': loginModal(true); break;
    case 'close-modal': closeModal(); break;
    case 'toggle-mobile-menu': $('#mobile-menu').hidden = !$('#mobile-menu').hidden; break;
    case 'show-countries': countriesModal(); break;
    case 'open-support': state.loggedIn ? navigate('support') : loginModal(false); break;
    case 'open-telegram': toast('Telegram откроется после настройки', 'Ссылка задаётся переменной окружения.'); break;
    case 'logout': state.loggedIn = false; localStorage.removeItem('vpanfi-demo-session'); navigate(''); toast('Вы вышли из аккаунта'); break;
    case 'open-profile': navigate('profile'); break;
    case 'toggle-sidebar': $('.sidebar').classList.toggle('open'); break;
    case 'show-qr': state.platform = 'android'; navigate('connect'); break;
    case 'pay-half-year': paymentModal('half-year'); break;
    case 'demo-payment': closeModal(); toast('Оплата подтверждена', 'Дни добавлены к подписке.'); break;
    case 'toggle-renew': state.autoRenew = !state.autoRenew; toast(state.autoRenew ? 'Автопродление включено' : 'Автопродление выключено'); showCabinet(routeName() || 'app'); break;
    case 'top-up': paymentModal('quarter'); break;
    case 'add-device': toast('Место добавлено', 'В демонстрационном режиме без оплаты.'); state.extraSlots += 1; break;
    case 'install-app': toast('Открываем страницу приложения', 'В рабочей версии ссылка зависит от устройства.'); break;
    case 'copy-link': navigator.clipboard?.writeText('https://example.invalid/subscription/demo'); toast('Ключ скопирован'); break;
    case 'ticket': toast('Форма обращения готовится', 'Поля и API-контракт уже предусмотрены.'); break;
    case 'faq': toast('Открываем базу знаний'); break;
    default: break;
  }
}

document.addEventListener('click', (e) => {
  const actionNode = e.target.closest('[data-action]'); if (actionNode) handleAction(actionNode.dataset.action);
  const planNode = e.target.closest('[data-plan]'); if (planNode) paymentModal(planNode.dataset.plan);
  const platformNode = e.target.closest('[data-platform]'); if (platformNode) platformModal(platformNode.dataset.platform);
  const loginNode = e.target.closest('[data-login]'); if (loginNode) authenticate(loginNode.dataset.login);
});

document.addEventListener('submit', (e) => {
  if (e.target.id === 'login-form') { e.preventDefault(); authenticate('account'); }
});

window.addEventListener('hashchange', renderRoute);
function renderRoute() {
  const route = routeName();
  if (!route) { showPublic(); return; }
  if (!state.loggedIn) { showPublic(); loginModal(false); history.replaceState(null, '', '#/'); return; }
  showCabinet(pageMeta[route] ? route : 'app');
  window.scrollTo(0, 0);
}

const revealObserver = new IntersectionObserver((entries) => entries.forEach((entry) => { if (entry.isIntersecting) entry.target.classList.add('visible'); }), { threshold: .08 });
$$('.reveal').forEach((el) => revealObserver.observe(el));
renderRoute();
