const FAVORITES_KEY = 'gyor-menu-favorites-v2';
const WEEKDAYS_HU = ['Hétfő', 'Kedd', 'Szerda', 'Csütörtök', 'Péntek', 'Szombat', 'Vasárnap'];

const state = {
  selectedDayIndex: 0,
  favorites: new Set(),
  feed: null,
};

const el = {
  cards: document.getElementById('cards'),
  unsupported: document.getElementById('unsupported'),
  generatedAt: document.getElementById('generated-at'),
  favoriteList: document.getElementById('favorite-list'),
  favoritesReset: document.getElementById('favorites-reset'),
  weekdayTabs: Array.from(document.querySelectorAll('.weekday-tab')),
};
function loadFavorites() {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveFavorites() {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites]));
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

function readUrlState() {
  // Main list should always default to the current day.
}

function updateUrlState() {
  const next = `${window.location.pathname}`;
  window.history.replaceState({}, '', next);
}

function menuWeight(menu) {
  if (menu.certainty === 'exact' || menu.certainty === 'manual') return 0;
  if (menu.certainty === 'current_snapshot') return 1;
  return 2;
}

function restaurantWeight(record) {
  const menus = record.menus || [];
  if (!menus.length) return 99;
  return Math.min(...menus.map(menuWeight));
}

function renderTabs() {
  const current = getCurrentWeekdayIndex();
  el.weekdayTabs.forEach((btn, idx) => {
    btn.classList.toggle('active', idx === state.selectedDayIndex);
    btn.classList.toggle('past', idx < current);
    btn.classList.toggle('today', idx === current);
  });
}

function renderFavoritePicker() {
  const restaurants = [...(state.feed?.restaurants || [])].sort((a, b) => a.name.localeCompare(b.name, 'hu'));
  el.favoriteList.innerHTML = restaurants.map(r => `
    <label class="favorite-pill ${state.favorites.has(r.slug) ? 'active' : ''}">
      <input type="checkbox" data-fav="${r.slug}" ${state.favorites.has(r.slug) ? 'checked' : ''}>
      <span>${r.name}</span>
    </label>
  `).join('');

  el.favoriteList.querySelectorAll('input[data-fav]').forEach(input => {
    input.addEventListener('change', (e) => {
      const slug = e.target.dataset.fav;
      if (e.target.checked) state.favorites.add(slug);
      else state.favorites.delete(slug);
      saveFavorites();
      renderFavoritePicker();
      render();
    });
  });
}

function bestUpdatedAt(menus) {
  return menus.map(m => m.updatedAt).filter(Boolean).sort().reverse()[0] || '';
}

function restaurantHint(menus) {
  if (menus.some(m => m.certainty === 'current_snapshot')) {
    return 'Az eredeti forrás megnyitása indulás előtt ajánlott.';
  }
  if (menus.some(m => m.certainty === 'manual')) {
    return 'Ez a menü kézi ellenőrzéssel került be.';
  }
  return '';
}

function detailUrl(restaurant) {
  return `./restaurant.html?slug=${encodeURIComponent(restaurant.slug)}&day=${state.selectedDayIndex}`;
}

function sortVisible(records) {
  records.sort((a, b) => {
    const menuDiff = Number(b.hasMenu) - Number(a.hasMenu);
    if (menuDiff !== 0) return menuDiff;
    const favDiff = Number(state.favorites.has(b.restaurant.slug)) - Number(state.favorites.has(a.restaurant.slug));
    if (favDiff !== 0) return favDiff;
    const byWeight = restaurantWeight(a) - restaurantWeight(b);
    if (byWeight !== 0) return byWeight;
    return a.restaurant.name.localeCompare(b.restaurant.name, 'hu');
  });
}

function renderSummary(_visible, _missingFavs) {
  // Removed per product feedback: no status bubbles above the list.
}

function renderMenuItem(item) {
  const label = item.label ? `<strong>${item.label}</strong>` : '';
  const text = item.text ? `<div class="text">${item.text}</div>` : '';
  return `<div class="menu-item">${label}${text}</div>`;
}

function renderMenuBlock(menu) {
  return `
    <section class="menu-block">
      <div class="menu-title-wrap">
        <div class="menu-title">${menu.dayNameHu}</div>
      </div>
      <div class="menu-list">
        ${menu.items.slice(0, 5).map(renderMenuItem).join('')}
      </div>
    </section>
  `;
}

function trustClass(menus) {
  if (!menus.length) return 'trust-none';
  if (menus.some(m => m.certainty === 'manual')) return 'trust-manual';
  if (menus.some(m => m.certainty === 'exact')) return 'trust-exact';
  return 'trust-snapshot';
}

function renderRestaurantCard({ restaurant, menus, hasMenu }) {
  const hint = restaurantHint(menus);
  const trust = trustClass(menus);
  return `
    <article class="card ${state.favorites.has(restaurant.slug) ? 'favorite-card' : ''}" id="${restaurant.slug}">
      <div class="card-head simple-card-head">
        <div>
          <h2><a class="title-link" href="${detailUrl(restaurant)}">${restaurant.name}</a></h2>
          ${!hasMenu ? `<div class="sub">Nincs napi menü</div>` : ''}
        </div>
        ${hasMenu ? `<div class="trust-corner"><span class="trust-check ${trust}">✓</span></div>` : ''}
      </div>
      <div class="card-links compact-links">
        ${restaurant.sourceUrl ? `<a href="${restaurant.sourceUrl}" target="_blank" rel="noreferrer">Eredeti forrás</a>` : ''}
        <a href="${detailUrl(restaurant)}">Részletek</a>
      </div>
      ${hasMenu ? menus.map(renderMenuBlock).join('') : ''}
      ${hasMenu && hint ? `<div class="notes">${hint}</div>` : ''}
    </article>
  `;
}

function render() {
  if (!state.feed) return;
  updateUrlState();
  renderTabs();
  el.generatedAt.textContent = formatDateTime(state.feed.generatedAt);

  const wantedDate = selectedDate();
  const visible = [];

  for (const restaurant of state.feed.restaurants) {
    const menus = (restaurant.menus || []).filter(m => m.date === wantedDate);
    visible.push({ restaurant, menus, hasMenu: menus.length > 0 });
  }

  sortVisible(visible);
  renderSummary(visible, 0);
  el.cards.innerHTML = visible.length
    ? visible.map(renderRestaurantCard).join('')
    : `<div class="empty">Ehhez a naphoz most nincs betöltött menü.</div>`;
  el.unsupported.innerHTML = '';
}

async function loadFeed() {
  state.favorites = loadFavorites();
  const res = await fetch('./data/feed.json', { cache: 'no-store' });
  state.feed = await res.json();
  state.selectedDayIndex = getCurrentWeekdayIndex();
  readUrlState();
  renderFavoritePicker();
  render();
}

el.weekdayTabs.forEach(btn => btn.addEventListener('click', () => {
  state.selectedDayIndex = Number(btn.dataset.dayIndex);
  render();
}));

el.favoritesReset.addEventListener('click', () => {
  state.favorites = new Set();
  saveFavorites();
  renderFavoritePicker();
  render();
});

loadFeed().catch(err => {
  el.cards.innerHTML = `<div class="empty">Nem sikerült betölteni az oldalt. ${err}</div>`;
});
