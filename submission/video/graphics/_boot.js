// Params arrive in the URL hash as JSON. Each graphic defines build(P) and sets window.READY.
window.P = (() => { try { return JSON.parse(decodeURIComponent(location.hash.slice(1))) } catch { return {} } })();
document.documentElement.style.setProperty('--dur', (P.dur ?? 5) + 's');
window.esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
addEventListener('DOMContentLoaded', async () => { await window.build?.(P); await document.fonts.ready; window.READY = true; });
