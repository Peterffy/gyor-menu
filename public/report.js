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

const el = {
  restaurant: document.getElementById('report-restaurant'),
  date: document.getElementById('report-date'),
  form: document.getElementById('report-form'),
  issueType: document.getElementById('issue-type'),
  note: document.getElementById('issue-note'),
};

function formatDate(iso) {
  if (!iso) return 'Nincs megadva';
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${y}.${String(m).padStart(2, '0')}.${String(d).padStart(2, '0')}.`;
}

function buildMailto() {
  const p = params();
  const restaurantName = p.get('name') || p.get('slug') || 'Ismeretlen étterem';
  const restaurantSlug = p.get('slug') || '';
  const date = p.get('date') || '';
  const issueType = el.issueType.value || 'Más hiba';
  const note = el.note.value.trim();
  const source = p.get('source') || 'unknown';
  const reportUrl = window.location.href;

  const subject = `Győr Menü hibajelzés – ${restaurantName} – ${date || 'nincs dátum'}`;
  const body = [
    'Győr Menü hibajelzés',
    '',
    `Étterem: ${restaurantName}`,
    `Slug: ${restaurantSlug}`,
    `Dátum: ${date || 'nincs megadva'}`,
    `Hiba típusa: ${issueType}`,
    `Forrásoldal: ${source}`,
    `Jelzőoldal URL: ${reportUrl}`,
    '',
    'Megjegyzés:',
    note || '-',
  ].join('\n');

  return `mailto:shareblockholmes@gmail.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

function init() {
  const p = params();
  const restaurantName = p.get('name') || p.get('slug') || 'Ismeretlen étterem';
  const date = p.get('date') || '';
  el.restaurant.textContent = restaurantName;
  el.date.textContent = formatDate(date);

  el.form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!el.issueType.value) {
      el.issueType.focus();
      return;
    }
    window.location.href = buildMailto();
  });
}

init();
