const REPORT_FORM_BASE = 'https://docs.google.com/forms/d/e/1FAIpQLSf6AunOQ15BUC4FcisN_DqhRKsKrr3oMdyyCxClZATe3Hasyg/viewform?usp=pp_url';
const WEEKDAYS_HU = ['Hétfő', 'Kedd', 'Szerda', 'Csütörtök', 'Péntek', 'Szombat', 'Vasárnap'];
const DEFAULT_MAP_CENTER = { lat: 47.6874, lng: 17.6351 };

const state = {
  slug: '',
  selectedDayIndex: 0,
  feed: null,
  map: null,
  markerLayer: null,
};

const el = {
  name: document.getElementById('detail-name'),
  subtitle: document.getElementById('detail-address') || document.getElementById('detail-subtitle'),
  area: document.getElementById('detail-area'),
  updated: document.getElementById('detail-updated'),
  links: document.getElementById('detail-links'),
  menus: document.getElementById('detail-menus'),
  mapSection: document.getElementById('detail-map-section'),
  mapCanvas: document.getElementById('detail-map-canvas'),
  weekdayTabs: Array.from(document.querySelectorAll('.weekday-tab')),
};

function params() {
  return new URLSearchParams(window.location.search);
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

function getBudapestTodayIso() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Budapest',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const byType = Object.fromEntries(parts.filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
  return `${byType.year}-${byType.month}-${byType.day}`;
}

function getReferenceTodayIso() {
  return state.feed?.today || getBudapestTodayIso();
}

function getCurrentWeekdayIndex() {
  const [y, m, d] = getReferenceTodayIso().split('-').map(Number);
  const today = new Date(y, m - 1, d);
  const js = today.getDay();
  const mondayBased = js === 0 ? 6 : js - 1;
  return Math.min(Math.max(mondayBased, 0), 6);
}

function getWeekDates() {
  const [y, m, d] = getReferenceTodayIso().split('-').map(Number);
  const today = new Date(y, m - 1, d);
  const mondayOffset = today.getDay() === 0 ? -6 : 1 - today.getDay();
  const monday = new Date(y, m - 1, d + mondayOffset);
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const dt = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
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

function setMetaById(id, content) {
  const meta = document.getElementById(id);
  if (meta) meta.setAttribute('content', content);
}

function setDetailSeo(restaurant) {
  const canonicalUrl = `https://ebedmenuk.hu/restaurant.html?slug=${encodeURIComponent(restaurant.slug)}`;
  const title = `${restaurant.name} napi menü Győr | Mi a menü?`;
  const description = `${restaurant.name} napi és heti menüje Győrben${restaurant.address ? ` – ${restaurant.address}` : ''}. Eredeti forrás, térkép és részletes menük a Mi a menü? oldalon.`;
  document.title = title;
  setMetaById('meta-description', description);
  setMetaById('meta-twitter-title', title);
  setMetaById('meta-twitter-description', description);
  setMetaById('meta-og-title', title);
  setMetaById('meta-og-description', description);
  setMetaById('meta-og-url', canonicalUrl);
  const canonical = document.getElementById('canonical-link');
  if (canonical) canonical.setAttribute('href', canonicalUrl);
}

function renderTabs() {
  const current = getCurrentWeekdayIndex();
  const weekDates = getWeekDates();
  const actualTodayIso = getBudapestTodayIso();
  el.weekdayTabs.forEach((btn, idx) => {
    btn.classList.toggle('active', idx === state.selectedDayIndex);
    btn.classList.toggle('past', idx < current);
    btn.classList.toggle('today', weekDates[idx] === actualTodayIso);
    const dateStr = weekDates[idx] ? weekDates[idx].slice(5) : '';
    const prefix = weekDates[idx] === actualTodayIso ? 'Ma · ' : '';
    btn.innerHTML = `${prefix}${WEEKDAYS_HU[idx]} <small>${dateStr}</small>`;
  });
}

function formatDisplayPrice(item) {
  if (Number.isFinite(item.priceHuf) && item.priceHuf > 0) {
    return `${new Intl.NumberFormat('hu-HU').format(item.priceHuf)} Ft`;
  }
  if (item.priceText) return escapeHtml(item.priceText);
  return '';
}

function renderMenuItem(item) {
  const label = item.label ? `<strong>${escapeHtml(item.label)}</strong>` : '';
  const price = formatDisplayPrice(item);
  const header = (label || price)
    ? `<div class="menu-item-head">${label}${price ? `<span class="menu-price">${price}</span>` : ''}</div>`
    : '';
  const text = item.text ? `<div class="text">${escapeHtml(item.text)}</div>` : '';
  return `<div class="menu-item">${header}${text}</div>`;
}

function parseCoordinate(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getCoords(restaurant) {
  const lat = parseCoordinate(restaurant.lat);
  const lng = parseCoordinate(restaurant.lng);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
}

function ensureMap() {
  if (state.map || !el.mapCanvas || typeof L === 'undefined') return;
  state.map = L.map(el.mapCanvas, { zoomControl: true, attributionControl: true }).setView([DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> közreműködők',
  }).addTo(state.map);
  state.markerLayer = L.layerGroup().addTo(state.map);
}

function mapPopupHtml(restaurant, isCurrent) {
  const source = safeUrl(restaurant.sourceUrl);
  const detail = `./restaurant.html?slug=${encodeURIComponent(restaurant.slug)}&day=${state.selectedDayIndex}`;
  return `
    <div class="map-popup">
      <strong>${escapeHtml(restaurant.name)}</strong>
      <div>${escapeHtml(restaurant.area || 'Győr')}</div>
      ${isCurrent ? `<div class="map-popup-state">Ez az aktuális étterem</div>` : ''}
      <div class="map-popup-links">
        ${!isCurrent ? `<a href="${detail}">Részletek</a>` : ''}
        ${source ? `<a href="${source}" target="_blank" rel="noreferrer">Forrás</a>` : ''}
      </div>
    </div>
  `;
}

function renderRestaurantMap(currentRestaurant) {
  if (!el.mapSection || !el.mapCanvas) return;
  ensureMap();
  if (!state.map || !state.markerLayer) return;

  state.markerLayer.clearLayers();
  const bounds = [];

  for (const restaurant of state.feed.restaurants || []) {
    const coords = getCoords(restaurant);
    if (!coords) continue;
    const isCurrent = restaurant.slug === currentRestaurant.slug;
    const marker = L.circleMarker([coords.lat, coords.lng], {
      radius: isCurrent ? 10 : 7,
      color: isCurrent ? '#0c7c74' : '#5c6b7a',
      weight: isCurrent ? 3 : 2,
      fillColor: isCurrent ? '#0c7c74' : '#a4afb9',
      fillOpacity: isCurrent ? 0.9 : 0.65,
    }).bindPopup(mapPopupHtml(restaurant, isCurrent));
    marker.addTo(state.markerLayer);
    bounds.push([coords.lat, coords.lng]);
    if (isCurrent) marker.openPopup();
  }

  setTimeout(() => {
    state.map.invalidateSize();
    const currentCoords = getCoords(currentRestaurant);
    if (currentCoords) {
      state.map.setView([currentCoords.lat, currentCoords.lng], 14);
    }
    if (bounds.length > 1) {
      state.map.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
    }
  }, 0);
}

function visibleMenuNotes(menu) {
  const notes = Array.isArray(menu?.notes) ? menu.notes : [];
  return notes.filter(note => /zárva|áramszünet|technikai ok|ünnepi|mai menü|ma nincs/i.test(String(note)));
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
  const topUpdated = menus.map(m => m.updatedAt).filter(Boolean).sort().reverse()[0] || '';

  setDetailSeo(restaurant);
  el.name.textContent = restaurant.name || '';
  if (el.subtitle) el.subtitle.textContent = restaurant.address || 'Győr';
  if (el.area) el.area.textContent = restaurant.area || 'Győr';
  if (el.updated) el.updated.textContent = topUpdated ? formatDateTime(topUpdated) : 'Nincs adat';

  const linkParts = [];
  if (restaurant.sourceUrl) {
    const safeSourceUrl = safeUrl(restaurant.sourceUrl);
    if (safeSourceUrl) linkParts.push(`<a href="${safeSourceUrl}" target="_blank" rel="noreferrer">Eredeti forrás</a>`);
  }
  if (restaurant.mapUrl) {
    const safeMapUrl = safeUrl(restaurant.mapUrl);
    if (safeMapUrl) linkParts.push(`<a href="${safeMapUrl}" target="_blank" rel="noreferrer">Térkép</a>`);
  }
  linkParts.push(`<a href="${reportUrl(restaurant)}" target="_blank" rel="noreferrer">Hiba jelzése</a>`);
  el.links.innerHTML = linkParts.join('');

  renderRestaurantMap(restaurant);

  if (!menus.length) {
    el.menus.innerHTML = `<div class="empty">Ehhez a naphoz jelenleg nincs betöltött menü. Ilyenkor érdemes megnyitni az eredeti forrást.</div>`;
    return;
  }

  const trustMetaForMenu = (menu) => {
    if (menu.certainty === 'exact') return { cls: 'trust-exact', symbol: '✓', label: 'Ellenőrzött' };
    if (menu.certainty === 'manual') return { cls: 'trust-manual', symbol: '⚡', label: 'Kézi' };
    return { cls: 'trust-snapshot', symbol: '◷', label: 'Élő forrás' };
  };

  el.menus.innerHTML = menus.map(menu => {
    const trust = trustMetaForMenu(menu);
    const pricedCount = menu.items.filter(item => item.priceHuf || item.priceText).length;
    const priceNote = menu.items.length > 0 && pricedCount < menu.items.length
      ? `<div class="menu-price-note">Az árak csak ott jelennek meg, ahol a forrás külön feltünteti.</div>`
      : '';
    const notes = visibleMenuNotes(menu);
    return `
    <article class="card">
      <div class="card-head simple-card-head">
        <div>
          <h2>${escapeHtml(menu.dayNameHu)}</h2>
        </div>
        <div class="trust-corner"><span class="trust-check ${trust.cls}" title="${trust.label}">${trust.symbol}</span></div>
      </div>
      <div class="menu-list detail-menu-list">
        ${menu.items.map(renderMenuItem).join('')}
      </div>
      ${priceNote}
      ${notes.length ? `<div class="notes">${notes.map(n => `• ${escapeHtml(n)}`).join('<br>')}</div>` : ''}
    </article>
  `;
  }).join('');
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
