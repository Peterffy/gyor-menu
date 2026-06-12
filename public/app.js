const FAVORITES_KEY = 'gyor-menu-favorites-v2';
const REPORT_FORM_BASE = 'https://docs.google.com/forms/d/e/1FAIpQLSf6AunOQ15BUC4FcisN_DqhRKsKrr3oMdyyCxClZATe3Hasyg/viewform?usp=pp_url';
const WEEKDAYS_HU = ['Hétfő', 'Kedd', 'Szerda', 'Csütörtök', 'Péntek', 'Szombat', 'Vasárnap'];
const DEFAULT_MAP_CENTER = { lat: 47.6874, lng: 17.6351 };
const DEMO_LOCATION = { lat: 47.6874, lng: 17.6351, label: 'Győr belváros demó' };

const state = {
  selectedDayIndex: 0,
  favorites: new Set(),
  feed: null,
  viewMode: 'list',
  sortMode: 'default',
  userLocation: null,
  locationState: 'idle',
  locationSource: '',
  map: null,
  mapLayer: null,
  userLayer: null,
  lastRecords: [],
};

const el = {
  cards: document.getElementById('cards'),
  unsupported: document.getElementById('unsupported'),
  generatedAt: document.getElementById('updated-at') || document.getElementById('generated-at'),
  favoriteList: document.getElementById('favorite-list'),
  favoritesReset: document.getElementById('favorites-reset'),
  suggestionLink: document.getElementById('restaurant-suggestion-link'),
  weekdayTabs: Array.from(document.querySelectorAll('.weekday-tab')),
  nearMeBtn: document.getElementById('near-me-btn'),
  demoLocationBtn: document.getElementById('demo-location-btn'),
  sortResetBtn: document.getElementById('sort-reset-btn'),
  viewToggleBtns: Array.from(document.querySelectorAll('[data-view-mode]')),
  locationStatus: document.getElementById('location-status'),
  mapSection: document.getElementById('map-section'),
  mapCanvas: document.getElementById('map-canvas'),
  mapEmpty: document.getElementById('map-empty'),
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

function buildDetailPath(slug, dayIndex = null) {
  const safeSlug = encodeURIComponent(slug || '');
  if (!safeSlug) return './restaurant.html';
  if (Number.isInteger(dayIndex) && dayIndex >= 0 && dayIndex <= 6) {
    return `/restaurant/${safeSlug}/day/${dayIndex + 1}/`;
  }
  return `/restaurant/${safeSlug}/`;
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

function parseCoordinate(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getRestaurantCoords(restaurant) {
  const lat = parseCoordinate(restaurant.lat);
  const lng = parseCoordinate(restaurant.lng);
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null;
}

function toRadians(value) {
  return value * (Math.PI / 180);
}

function haversineDistanceMeters(a, b) {
  const R = 6371000;
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const sinLat = Math.sin(dLat / 2);
  const sinLng = Math.sin(dLng / 2);
  const h = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng;
  return 2 * R * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

function formatDistance(meters) {
  if (!Number.isFinite(meters)) return '';
  if (meters < 1000) {
    const rounded = Math.max(50, Math.round(meters / 50) * 50);
    return `${rounded} m`;
  }
  return `${(meters / 1000).toFixed(meters < 3000 ? 1 : 0).replace('.', ',')} km`;
}

function locationModeLabel() {
  if (!state.userLocation) return '';
  return state.locationSource === 'demo' ? 'Belváros demó alapján' : 'Saját helyed alapján';
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

function renderFavoritePicker() {
  const restaurants = [...(state.feed?.restaurants || [])].sort((a, b) => a.name.localeCompare(b.name, 'hu'));
  el.favoriteList.innerHTML = restaurants.map(r => `
    <label class="favorite-pill ${state.favorites.has(r.slug) ? 'active' : ''}">
      <input type="checkbox" data-fav="${escapeHtml(r.slug)}" ${state.favorites.has(r.slug) ? 'checked' : ''}>
      <span>${escapeHtml(r.name)}</span>
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

function restaurantHint(menus) {
  if (menus.some(m => m.certainty === 'current_snapshot')) {
    return 'Indulás előtt nézz rá az eredeti forrásra.';
  }
  return '';
}

function detailUrl(restaurant) {
  return buildDetailPath(restaurant.slug, state.selectedDayIndex);
}

function absoluteDetailUrl(restaurant) {
  return `https://ebedmenuk.hu${detailUrl(restaurant)}`;
}

function shareTitle(restaurant) {
  return `${restaurant.name} – ${WEEKDAYS_HU[state.selectedDayIndex]} menü | Mi a menü?`;
}

function shareText(restaurant) {
  return `${restaurant.name} – ${WEEKDAYS_HU[state.selectedDayIndex]} menü Győr`;
}

function reportUrl(restaurant) {
  const params = new URLSearchParams();
  params.set('entry.5bd74c55', restaurant.name || '');
  const date = selectedDate() || '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    const [year, month, day] = date.split('-');
    params.set('entry.1da9156f_year', year);
    params.set('entry.1da9156f_month', String(Number(month)));
    params.set('entry.1da9156f_day', String(Number(day)));
  }
  params.set('entry.48615b8a', restaurant.sourceUrl || window.location.href);
  return `${REPORT_FORM_BASE}&${params.toString()}`;
}

function restaurantSuggestionUrl() {
  const params = new URLSearchParams();
  params.set('entry.208dde45', 'Étterem javaslása');
  params.set('entry.48615b8a', window.location.href);
  return `${REPORT_FORM_BASE}&${params.toString()}`;
}

function setMeta(name, content) {
  const meta = document.querySelector(`meta[name="${name}"]`);
  if (meta) meta.setAttribute('content', content);
}

function setOg(property, content) {
  const meta = document.querySelector(`meta[property="${property}"]`);
  if (meta) meta.setAttribute('content', content);
}

function setIndexSeo(records) {
  if (!state.feed) return;
  const visibleWithMenu = records.filter(r => r.hasMenu).length;
  const totalRestaurants = state.feed.restaurants?.length || 0;
  const dayLabel = WEEKDAYS_HU[state.selectedDayIndex];
  const isToday = state.selectedDayIndex === getCurrentWeekdayIndex();
  const title = isToday
    ? `Mai napi menü Győr – ${visibleWithMenu} étterem | Mi a menü?`
    : `${dayLabel} napi menü Győr – ${visibleWithMenu} étterem | Mi a menü?`;
  const description = isToday
    ? `Mai napi menü Győr városában: ${visibleWithMenu} elérhető ebédmenü ${totalRestaurants} győri étteremtől, forráslinkekkel és gyors mobilos áttekintéssel.`
    : `${dayLabel} napi menü Győr városában: ${visibleWithMenu} elérhető ebédmenü ${totalRestaurants} győri étteremtől, forráslinkekkel és gyors mobilos áttekintéssel.`;
  document.title = title;
  setMeta('description', description);
  setMeta('twitter:title', title);
  setMeta('twitter:description', description);
  setOg('og:title', title);
  setOg('og:description', description);
}

function sortVisible(records) {
  records.sort((a, b) => {
    const menuDiff = Number(b.hasMenu) - Number(a.hasMenu);
    if (menuDiff !== 0) return menuDiff;

    if (state.sortMode === 'distance' && state.userLocation) {
      const aDist = Number.isFinite(a.distanceMeters) ? a.distanceMeters : Number.POSITIVE_INFINITY;
      const bDist = Number.isFinite(b.distanceMeters) ? b.distanceMeters : Number.POSITIVE_INFINITY;
      if (aDist !== bDist) return aDist - bDist;
      const favDiff = Number(state.favorites.has(b.restaurant.slug)) - Number(state.favorites.has(a.restaurant.slug));
      if (favDiff !== 0) return favDiff;
    } else {
      const favDiff = Number(state.favorites.has(b.restaurant.slug)) - Number(state.favorites.has(a.restaurant.slug));
      if (favDiff !== 0) return favDiff;
    }

    const byWeight = restaurantWeight(a) - restaurantWeight(b);
    if (byWeight !== 0) return byWeight;
    return a.restaurant.name.localeCompare(b.restaurant.name, 'hu');
  });
}

function renderSummary(_visible, _missingFavs) {
  // Removed per product feedback: no status bubbles above the list.
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

function renderMenuBlock(menu, detailHref) {
  const visibleItems = menu.items.slice(0, 5);
  const pricedCount = visibleItems.filter(item => item.priceHuf || item.priceText).length;
  const hiddenCount = Math.max(0, menu.items.length - visibleItems.length);
  const priceNote = visibleItems.length > 0 && pricedCount < visibleItems.length
    ? `<div class="menu-price-note">Az árak csak ott jelennek meg, ahol a forrás külön feltünteti.</div>`
    : '';
  const moreLink = hiddenCount > 0
    ? `<div class="menu-more-link"><a href="${detailHref}">+${hiddenCount} további tétel a részleteknél →</a></div>`
    : '';
  return `
    <section class="menu-block">
      <div class="menu-title-wrap">
        <div class="menu-title">${menu.dayNameHu}</div>
      </div>
      <div class="menu-list">
        ${visibleItems.map(renderMenuItem).join('')}
      </div>
      ${priceNote}
      ${moreLink}
    </section>
  `;
}

function trustMeta(menus) {
  if (!menus.length) return { cls: 'trust-none', label: '', symbol: '' };
  if (menus.some(m => m.certainty === 'exact')) return { cls: 'trust-exact', label: 'Ellenőrzött', symbol: '✓' };
  if (menus.some(m => m.certainty === 'manual')) return { cls: 'trust-manual', label: 'Kézi', symbol: '⚡' };
  if (menus.some(m => m.certainty === 'current_snapshot')) return { cls: 'trust-snapshot', label: 'Élő forrás', symbol: '◷' };
  return { cls: 'trust-none', label: '', symbol: '' };
}

function renderDistanceChip(record) {
  if (!state.userLocation || !Number.isFinite(record.distanceMeters)) return '';
  const modeLabel = state.locationSource === 'demo' ? 'Belváros' : 'Közelben';
  return `<span class="distance-chip" title="${escapeHtml(locationModeLabel())}">📍 ${modeLabel}: ${escapeHtml(formatDistance(record.distanceMeters))}</span>`;
}

function renderRestaurantCard(record) {
  const { restaurant, menus, hasMenu } = record;
  const hint = restaurantHint(menus);
  const trust = trustMeta(menus);
  const safeName = escapeHtml(restaurant.name);
  const safeSlug = escapeHtml(restaurant.slug);
  const safeDetail = detailUrl(restaurant);
  const safeReport = reportUrl(restaurant);
  const safeHint = escapeHtml(hint);
  const safeArea = escapeHtml(restaurant.area || '');
  return `
    <article class="card ${state.favorites.has(restaurant.slug) ? 'favorite-card' : ''}" id="${safeSlug}">
      <div class="card-head simple-card-head">
        <div>
          <h2><a class="title-link" href="${safeDetail}">${safeName}</a></h2>
          <div class="card-meta-row">
            ${safeArea ? `<span class="area-chip">${safeArea}</span>` : ''}
            ${renderDistanceChip(record)}
          </div>
          ${!hasMenu ? `<div class="sub">Nincs napi menü</div>` : ''}
        </div>
        ${hasMenu && trust.label ? `<div class="trust-corner"><span class="trust-check ${trust.cls}" title="${trust.label}">${trust.symbol}</span></div>` : ''}
      </div>
      <div class="card-links compact-links">
        <a href="${safeDetail}">Részletek</a>
        <button class="card-action-btn share-action-btn share-text-btn" type="button" data-share-slug="${safeSlug}" aria-label="${safeName} megosztása" title="Megosztás">Megosztás</button>
        <a href="${safeReport}" target="_blank" rel="noreferrer">Hiba jelzése</a>
      </div>
      ${hasMenu ? menus.map(menu => renderMenuBlock(menu, safeDetail)).join('') : ''}
      ${hasMenu && safeHint ? `<div class="notes">${safeHint}</div>` : ''}
    </article>
  `;
}

function buildVisibleRecords() {
  const wantedDate = selectedDate();
  const visible = [];

  for (const restaurant of state.feed.restaurants) {
    const menus = (restaurant.menus || []).filter(m => m.date === wantedDate);
    const coords = getRestaurantCoords(restaurant);
    const distanceMeters = state.userLocation && coords ? haversineDistanceMeters(state.userLocation, coords) : null;
    visible.push({
      restaurant,
      menus,
      hasMenu: menus.length > 0,
      coords,
      distanceMeters,
    });
  }

  const filteredVisible = state.favorites.size
    ? visible.filter(record => state.favorites.has(record.restaurant.slug))
    : visible;

  sortVisible(filteredVisible);
  return filteredVisible;
}

function ensureMap() {
  if (state.map || !el.mapCanvas || typeof L === 'undefined') return;
  state.map = L.map(el.mapCanvas, { zoomControl: true, attributionControl: true }).setView([DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> közreműködők',
  }).addTo(state.map);
  state.mapLayer = L.layerGroup().addTo(state.map);
  state.userLayer = L.layerGroup().addTo(state.map);
}

function markerColor(record) {
  if (!record.hasMenu) return '#98a3b3';
  if (record.menus.some(m => m.certainty === 'exact')) return '#0c7c74';
  if (record.menus.some(m => m.certainty === 'manual')) return '#2f80ed';
  return '#b06a00';
}

function markerPopupHtml(record) {
  const { restaurant, hasMenu } = record;
  const detail = detailUrl(restaurant);
  const source = safeUrl(restaurant.sourceUrl);
  const distance = Number.isFinite(record.distanceMeters) ? `<div><strong>${escapeHtml(formatDistance(record.distanceMeters))}</strong></div>` : '';
  return `
    <div class="map-popup">
      <strong>${escapeHtml(restaurant.name)}</strong>
      <div>${escapeHtml(restaurant.area || 'Győr')}</div>
      ${distance}
      <div>${hasMenu ? 'Van ma menü' : 'Nincs ma menü'}</div>
      <div class="map-popup-links">
        <a href="${detail}">Részletek</a>
        ${source ? `<a href="${source}" target="_blank" rel="noreferrer">Forrás</a>` : ''}
      </div>
    </div>
  `;
}

function showToast(message) {
  let toast = document.querySelector('.app-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'app-toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => {
    toast.classList.remove('visible');
  }, 2200);
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'absolute';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } finally {
    textarea.remove();
  }
  return ok;
}

async function shareRestaurantBySlug(slug) {
  const record = (state.lastRecords || []).find(item => item.restaurant.slug === slug);
  if (!record) return;

  const { restaurant } = record;
  const url = absoluteDetailUrl(restaurant);
  const title = shareTitle(restaurant);
  const text = shareText(restaurant);

  if (navigator.share) {
    try {
      await navigator.share({ title, text, url });
      return;
    } catch (err) {
      if (err?.name === 'AbortError') return;
    }
  }

  const copied = await copyText(url);
  showToast(copied ? 'Megosztható link kimásolva' : 'Megosztás: ' + url);
}

function renderMap(records) {
  if (!el.mapSection || !el.mapCanvas) return;
  ensureMap();
  if (!state.map || !state.mapLayer || !state.userLayer) return;

  const showMap = state.viewMode === 'map';
  el.mapSection.hidden = !showMap;
  if (!showMap) return;

  state.mapLayer.clearLayers();
  state.userLayer.clearLayers();

  const bounds = [];
  let markerCount = 0;

  for (const record of records) {
    if (!record.coords) continue;
    markerCount += 1;
    const marker = L.circleMarker([record.coords.lat, record.coords.lng], {
      radius: record.hasMenu ? 9 : 7,
      color: markerColor(record),
      weight: 2,
      fillColor: markerColor(record),
      fillOpacity: record.hasMenu ? 0.82 : 0.5,
    }).bindPopup(markerPopupHtml(record));
    marker.addTo(state.mapLayer);
    bounds.push([record.coords.lat, record.coords.lng]);
  }

  if (state.userLocation) {
    L.circle([state.userLocation.lat, state.userLocation.lng], {
      radius: 70,
      color: '#2f80ed',
      fillColor: '#2f80ed',
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(state.userLayer);
    L.circleMarker([state.userLocation.lat, state.userLocation.lng], {
      radius: 8,
      color: '#2f80ed',
      fillColor: '#2f80ed',
      fillOpacity: 0.95,
      weight: 2,
    }).bindPopup(state.locationSource === 'demo' ? 'Belváros demó helyzet' : 'Jelenlegi helyzeted').addTo(state.userLayer);
    bounds.push([state.userLocation.lat, state.userLocation.lng]);
  }

  if (el.mapEmpty) {
    el.mapEmpty.hidden = markerCount > 0;
  }

  setTimeout(() => {
    state.map.invalidateSize();
    if (!bounds.length) {
      state.map.setView([DEFAULT_MAP_CENTER.lat, DEFAULT_MAP_CENTER.lng], 13);
      return;
    }
    if (bounds.length === 1) {
      state.map.setView(bounds[0], 15);
      return;
    }
    state.map.fitBounds(bounds, { padding: [28, 28] });
  }, 0);
}

function renderLocationUi(records) {
  if (el.nearMeBtn) {
    el.nearMeBtn.disabled = state.locationState === 'requesting';
    el.nearMeBtn.textContent = state.locationState === 'requesting' ? 'Helyzet lekérése…' : 'Közelemben';
  }
  if (el.sortResetBtn) {
    el.sortResetBtn.hidden = state.sortMode !== 'distance';
  }
  if (el.viewToggleBtns.length) {
    el.viewToggleBtns.forEach(btn => {
      const active = btn.dataset.viewMode === state.viewMode;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }
  if (!el.locationStatus) return;

  const closestWithMenu = records.find(record => record.hasMenu && Number.isFinite(record.distanceMeters));
  if (state.locationState === 'ready' && state.userLocation) {
    const sourceText = state.locationSource === 'demo' ? 'Belváros demó alapján' : 'Saját helyed alapján';
    const nearestText = closestWithMenu ? ` Legközelebbi mai menü: ${closestWithMenu.restaurant.name} (${formatDistance(closestWithMenu.distanceMeters)}).` : '';
    el.locationStatus.textContent = `${sourceText} távolság szerint rendezve.${nearestText}`;
    return;
  }
  if (state.locationState === 'denied') {
    el.locationStatus.textContent = 'A helyhozzáférést elutasítottad. A lista maradt normál sorrendben — kipróbálhatod a Belváros demót is.';
    return;
  }
  if (state.locationState === 'unsupported') {
    el.locationStatus.textContent = 'Ez a böngésző vagy előnézeti környezet nem ad helyhozzáférést. A Belváros demóval ettől még kipróbálhatod a közelben módot.';
    return;
  }
  if (state.locationState === 'error') {
    el.locationStatus.textContent = 'Most nem sikerült lekérni a helyzetedet. Próbáld újra, vagy használd a Belváros demót.';
    return;
  }
  el.locationStatus.textContent = 'Mobilon akkor a leghasznosabb, ha engedélyezed a helyzetedet. Ha ezt most nem szeretnéd, kipróbálhatod a Belváros demót.';
}

function renderViewMode() {
  const showList = state.viewMode === 'list';
  if (el.cards) el.cards.hidden = !showList;
  if (el.unsupported) el.unsupported.hidden = !showList;
}

function render() {
  if (!state.feed) return;
  updateUrlState();
  renderTabs();
  if (el.generatedAt) el.generatedAt.textContent = formatDateTime(state.feed.generatedAt);

  const filteredVisible = buildVisibleRecords();
  state.lastRecords = filteredVisible;

  setIndexSeo(filteredVisible);
  renderSummary(filteredVisible, 0);
  if (el.cards) {
    el.cards.innerHTML = filteredVisible.length
      ? filteredVisible.map(renderRestaurantCard).join('')
      : `<div class="empty">Ehhez a naphoz most nincs betöltött menü.</div>`;
  }
  if (el.unsupported) el.unsupported.innerHTML = '';
  renderViewMode();
  renderLocationUi(filteredVisible);
  renderMap(filteredVisible);
}

function setUserLocation(location, source) {
  state.userLocation = location;
  state.locationSource = source;
  state.locationState = 'ready';
  state.sortMode = 'distance';
  render();
}

function requestLocation() {
  if (!navigator.geolocation || !window.isSecureContext) {
    state.locationState = 'unsupported';
    render();
    return;
  }
  state.locationState = 'requesting';
  renderLocationUi(state.lastRecords || []);
  navigator.geolocation.getCurrentPosition(
    (position) => {
      setUserLocation({ lat: position.coords.latitude, lng: position.coords.longitude }, 'gps');
    },
    (error) => {
      state.locationState = error && error.code === 1 ? 'denied' : 'error';
      render();
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
  );
}

function useDemoLocation() {
  setUserLocation({ lat: DEMO_LOCATION.lat, lng: DEMO_LOCATION.lng }, 'demo');
}

function resetSortMode() {
  state.sortMode = 'default';
  render();
}

async function loadFeed() {
  state.favorites = loadFavorites();
  const res = await fetch('./data/feed.json', { cache: 'no-store' });
  state.feed = await res.json();
  state.selectedDayIndex = getCurrentWeekdayIndex();
  readUrlState();
  if (el.suggestionLink) el.suggestionLink.href = restaurantSuggestionUrl();
  renderFavoritePicker();
  render();
}

el.weekdayTabs.forEach(btn => btn.addEventListener('click', () => {
  state.selectedDayIndex = Number(btn.dataset.dayIndex);
  render();
}));

if (el.favoritesReset) {
  el.favoritesReset.addEventListener('click', () => {
    state.favorites = new Set();
    saveFavorites();
    renderFavoritePicker();
    render();
  });
}

if (el.cards) {
  el.cards.addEventListener('click', async (event) => {
    const btn = event.target.closest('button[data-share-slug]');
    if (!btn) return;
    event.preventDefault();
    btn.disabled = true;
    try {
      await shareRestaurantBySlug(btn.dataset.shareSlug || '');
    } finally {
      btn.disabled = false;
    }
  });
}

if (el.nearMeBtn) {
  el.nearMeBtn.addEventListener('click', requestLocation);
}

if (el.demoLocationBtn) {
  el.demoLocationBtn.addEventListener('click', useDemoLocation);
}

if (el.sortResetBtn) {
  el.sortResetBtn.addEventListener('click', resetSortMode);
}

if (el.viewToggleBtns.length) {
  el.viewToggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      state.viewMode = btn.dataset.viewMode === 'map' ? 'map' : 'list';
      render();
    });
  });
}

loadFeed().catch(err => {
  if (el.cards) {
    el.cards.innerHTML = `<div class="empty">Nem sikerült betölteni az oldalt. ${escapeHtml(err.message || err)}</div>`;
  }
});
