const REPORT_FORM_BASE = 'https://docs.google.com/forms/d/e/1FAIpQLSf6AunOQ15BUC4FcisN_DqhRKsKrr3oMdyyCxClZATe3Hasyg/viewform?usp=pp_url';
const WEEKDAYS_HU = ['Hétfő', 'Kedd', 'Szerda', 'Csütörtök', 'Péntek', 'Szombat', 'Vasárnap'];

const state = {
  slug: '',
  selectedDayIndex: 0,
  feed: null,
};

const el = {
  name: document.getElementById('detail-name'),
  subtitle: document.getElementById('detail-subtitle'),
  area: document.getElementById('detail-area'),
  updated: document.getElementById('detail-updated'),
  links: document.getElementById('detail-links'),
  menus: document.getElementById('detail-menus'),
  weekdayTabs: Array.from(document.querySelectorAll('.weekday-tab')),
};
function params() {
  return new URLSearchParams(window.location.search);
}

function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites]));
}

function escapeHtml(str) {
  if (!str && str !== 0) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function safeUrl(url) {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('./') || url.startsWith('/')) return url;
  return '';
}

function formatDateTime(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat('hu-HU', { dateStyle: 'medium', timeStyle: 'short' }).format(d);
}

function getCurrentWeekdayIndex() {
  if (!state.feed?.today) return 0;
  const [y, m, d] = state.feed.today.split('-').map(Number);
  const today = new Date(y, m - 1, d);
  const js = today.getDay();
  const mondayBased = js === 0 ? 6 : js - 1;
  return Math.min(Math.max(mondayBased, 0), 6);
}

function getWeekDates() {
  if (!state.feed?.weekStart) return [];
  const [y, m, d] = state.feed.weekStart.split('-').map(Number);
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const dt = new Date(y, m - 1, d + i);
    const yy = dt.getFullYear();
    const mm = String(dt.getMonth() + 1).padStart(2, '0');
    const dd = String(dt.getDate()).padStart(2, '0');
    dates.push(`${yy}-${mm}-${dd}`);
  }
  return dates;
}

function selectedDate() {
  return getWeekDates()[state.selectedDayIndex];
}

function readState() {
  const p = params();
  state.slug = p.get('slug') || '';
  const idx = Number(p.get('day'));
  if (Number.isInteger(idx) && idx >= 0 && idx <= 6) state.selectedDayIndex = idx;
}

function updateUrl() {
  const p = new URLSearchParams();
  p.set('slug', state.slug);
  p.set('day', String(state.selectedDayIndex));
  history.replaceState({}, '', `${window.location.pathname}?${p.toString()}`);
}

function reportUrl(restaurant) {
  const p = new URLSearchParams();
  p.set('entry.5bd74c55', restaurant.name || '');
  const date = selectedDate() || '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    const [year, month, day] = date.split('-');
    p.set('entry.1da9156f_year', year);
    p.set('entry.1da9156f_month', String(Number(month)));
    p.set('entry.1da9156f_day', String(Number(day)));
  }
  p.set('entry.48615b8a', restaurant.sourceUrl || window.location.href);
  return `${REPORT_FORM_BASE}&${p.toString()}`;
}

function renderTabs() {
  const current = getCurrentWeekdayIndex();
  const weekDates = getWeekDates();
  el.weekdayTabs.forEach((btn, idx) => {
    btn.classList.toggle('active', idx === state.selectedDayIndex);
    btn.classList.toggle('past', idx < current);
    btn.classList.toggle('today', idx === current);
    const dateStr = weekDates[idx] ? weekDates[idx].slice(5) : '';
    const prefix = idx === current ? 'Ma · ' : '';
    btn.innerHTML = `${prefix}${WEEKDAYS_HU[idx]} <small>${dateStr}</small>`;
  });
}

function renderMenuItem(item) {
  const label = item.label ? `<strong>${escapeHtml(item.label)}</strong>` : '';
  const text = item.text ? `<div class="text">${escapeHtml(item.text)}</div>` : '';
  return `<div class="menu-item">${label}${text}</div>`;
}

function render() {
  if (!state.feed) return;
  updateUrl();
  renderTabs();

  const restaurant = state.feed.restaurants.find(r => r.slug === state.slug);
  if (!restaurant) {
    el.name.textContent = 'Ez az étterem nem található';
    el.subtitle.textContent = 'Lehet, hogy a link hibás vagy az étterem még nincs a listában.';
    el.menus.innerHTML = `<div class="empty">Nem sikerült betölteni az étterem adatait.</div>`;
    return;
  }

  const wantedDate = selectedDate();
  const menus = (restaurant.menus || []).filter(m => m.date === wantedDate);
  const best = menus[0];

  const topUpdated = menus.map(m => m.updatedAt).filter(Boolean).sort().reverse()[0] || '';
  el.name.textContent = escapeHtml(restaurant.name);
  el.subtitle.textContent = escapeHtml(restaurant.address || 'Győr');
  el.area.textContent = escapeHtml(restaurant.area || 'Győr');
  el.updated.textContent = topUpdated ? formatDateTime(topUpdated) : 'Nincs adat';

  const linkParts = [];
  if (restaurant.sourceUrl) {
    const safeSourceUrl = safeUrl(restaurant.sourceUrl);
    if (safeSourceUrl) linkParts.push(`<a href="${safeSourceUrl}" target="_blank" rel="noreferrer">Eredeti forrás</a>`);
  }
  if (restaurant.mapUrl) {
    const safeMapUrl = safeUrl(restaurant.mapUrl);
    if (safeMapUrl) linkParts.push(`<a href="${safeMapUrl}" target="_blank" rel="noreferrer">Térkép</a>`);
  }
  linkParts.push(`<a href="${reportUrl(restaurant)}">Hiba jelzése</a>`);
  el.links.innerHTML = linkParts.join('');

  if (!menus.length) {
    el.menus.innerHTML = `<div class="empty">Ehhez a naphoz jelenleg nincs betöltött menü. Ilyenkor érdemes megnyitni az eredeti forrást.</div>`;
    return;
  }

  const trustClass = (menu) => menu.certainty === 'manual' ? 'trust-manual' : menu.certainty === 'exact' ? 'trust-exact' : 'trust-snapshot';
  const trustSymbol = (menu) => menu.certainty === 'exact' ? '✓' : menu.certainty === 'manual' ? '⚡' : '◷';
  el.menus.innerHTML = menus.map(menu => `
    <article class="card">
      <div class="card-head simple-card-head">
        <div>
          <h2>${escapeHtml(menu.dayNameHu)}</h2>
        </div>
        <div class="trust-corner"><span class="trust-check ${trustClass(menu)}">${trustSymbol(menu)}</span></div>
      </div>
      <div class="menu-list detail-menu-list">
        ${menu.items.map(renderMenuItem).join('')}
      </div>
      ${menu.notes?.length ? `<div class="notes">${menu.notes.map(n => `• ${escapeHtml(n)}`).join('<br>')}</div>` : ''}
    </article>
  `).join('');
}

async function loadFeed() {
  const res = await fetch('./data/feed.json', { cache: 'no-store' });
  state.feed = await res.json();
  state.selectedDayIndex = getCurrentWeekdayIndex();
  readState();
  render();
}

el.weekdayTabs.forEach(btn => btn.addEventListener('click', () => {
  state.selectedDayIndex = Number(btn.dataset.dayIndex);
  render();
}));

loadFeed().catch(err => {
  el.menus.innerHTML = `<div class="empty">Nem sikerült betölteni az oldalt. ${escapeHtml(err.message || err)}</div>`;
});
