// Injected into every page before load: a visible cursor and a click ripple, because the
// DevTools screencast does not draw the system cursor. Pointer-events none, so it never
// intercepts a click. Hidden from the accessibility tree.
(() => {
  if (window.__demoCursor) return;
  window.__demoCursor = true;
  const install = () => {
    const style = document.createElement('style');
    style.textContent = `
      #__dc{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
        transform:translate(-100px,-100px);will-change:transform;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}
      #__dc svg{display:block}
      .__dr{position:fixed;z-index:2147483646;pointer-events:none;width:44px;height:44px;margin:-22px 0 0 -22px;
        border-radius:50%;border:3px solid rgba(232,152,40,.95);background:rgba(232,152,40,.18);
        animation:__dr .55s ease-out forwards}
      @keyframes __dr{from{transform:scale(.25);opacity:1}to{transform:scale(1.25);opacity:0}}
      #__dc.down svg{transform:scale(.88);transform-origin:3px 3px}
      @media print{#__dc,.__dr{display:none!important}}`;
    document.documentElement.appendChild(style);
    const c = document.createElement('div');
    c.id = '__dc';
    c.setAttribute('aria-hidden', 'true');
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8 16.5 L11.5 24 L14.8 22.5 L11.4 15.2 L18 15.2 Z" fill="#111827" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(c);
    let x = -100, y = -100;
    window.addEventListener('mousemove', (e) => { x = e.clientX; y = e.clientY; c.style.transform = `translate(${x - 3}px,${y - 2}px)`; }, true);
    window.addEventListener('mousedown', (e) => {
      c.classList.add('down');
      const r = document.createElement('div');
      r.className = '__dr'; r.setAttribute('aria-hidden', 'true');
      r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      document.documentElement.appendChild(r);
      setTimeout(() => r.remove(), 700);
    }, true);
    window.addEventListener('mouseup', () => c.classList.remove('down'), true);
  };
  if (document.documentElement) install(); else document.addEventListener('DOMContentLoaded', install);
})();
