// NAME: Sleep Timer Button (1.3.9 compat)
// DESCRIPTION: Adds a visible trigger for SleepTimer's menu next to the player's mic (Lyrics) button.

(function sleepTimerTrigger() {
  const CLOCK = `<svg role="img" aria-hidden="true" viewBox="0 0 16 16" width="16" height="16" fill="currentColor"><path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8Zm7.25-3.75v3.5c0 .2.08.38.22.53l2.25 2.25a.75.75 0 1 0 1.06-1.06L8.75 7.44V4.25a.75.75 0 0 0-1.5 0Z"/></svg>`;

  let btn = null;

  // Ajustes visuales del menú de SleepTimer para 1.3.9
  if (!document.getElementById('sleek-sleep-style')) {
    const st = document.createElement('style');
    st.id = 'sleek-sleep-style';
    st.textContent = `
      /* flecha del globo centrada */
      #sleep-timer-menu.popup-menu:before {
        left: 50% !important;
        right: auto !important;
        margin-left: -10px !important;
        margin-right: 0 !important;
      }
      /* números legibles (el chip es blanco) */
      #sleep-timer-menu input[id$="input_spinner"] {
        color: var(--spice-main, #191724) !important;
        background-color: #fcfcfc !important;
      }
      /* separar el icono de la etiqueta (songs / minutes) */
      #sleep-timer-menu label > svg {
        margin-right: 8px !important;
        flex: 0 0 auto;
      }
      /* el título marcaba el ancho del globo: lo ajustamos */
      #sleep-timer-menu h3 {
        font-size: 17px !important;
      }
      /* el stepper un poco más estrecho para que no crezca el globo */
      #sleep-timer-menu label > div {
        width: 162px !important;
      }
      /* etiqueta en flujo (estaba absoluta y chocaba con el icono) */
      #sleep-timer-menu label > span {
        display: none !important;
      }
      /* ancho al contenido, sin hueco a la derecha */
      #sleep-timer-menu.popup-menu {
        width: max-content !important;
        min-width: 200px !important;
        max-width: 320px !important;
      }
    `;
    document.head.appendChild(st);
  }

  function makeButton() {
    const el = document.createElement('button');
    el.id = 'sleek-sleep-btn';
    el.type = 'button';
    el.title = 'Sleep Timer';
    el.setAttribute('aria-label', 'Sleep Timer');
    el.innerHTML = CLOCK;
    el.style.cssText = [
      'width:32px',
      'height:32px',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'padding:0',
      'border:0',
      'border-radius:50%',
      'background:transparent',
      'color:var(--spice-subtext,rgba(255,255,255,.7))',
      'cursor:pointer',
      'flex:0 0 auto',
    ].join(';');
    // SleepTimer cierra el menú en su listener de mouseup del document: lo cortamos aquí
    el.addEventListener('mousedown', (e) => e.stopPropagation());
    el.addEventListener('mouseup', (e) => e.stopPropagation());
    el.addEventListener('mouseenter', () => { el.style.color = 'var(--spice-text, #fff)'; });
    el.addEventListener('mouseleave', () => { el.style.color = 'var(--spice-subtext, rgba(255,255,255,.7))'; });

    const getMenu = () => document.getElementById('sleep-timer-menu');

    const placeMenu = (m) => {
      const r = el.getBoundingClientRect();
      const mw = m.offsetWidth || 200;
      let left = r.left + r.width / 2 - mw / 2;
      left = Math.max(6, Math.min(left, window.innerWidth - mw - 6));
      m.style.position = 'fixed';
      m.style.left = left + 'px';
      m.style.right = 'auto';
      m.style.top = 'auto';
      m.style.bottom = (window.innerHeight - r.top + 10) + 'px';
    };
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      const m = getMenu();
      if (!m) return;
      const visible = m.classList.contains('popup-menu--is-visible');
      if (visible) {
        m.classList.remove('popup-menu--is-visible');
      } else {
        m.classList.add('popup-menu--is-visible');
        placeMenu(m);
      }
    });
    return el;
  }

  function attach() {
    const menu = document.getElementById('sleep-timer-menu');
    const mic = document.querySelector('button[aria-label="Lyrics"]');
    if (!menu || !mic || !mic.parentElement) return;

    if (!btn || !btn.isConnected) btn = makeButton();

    // Debe quedar justo a la IZQUIERDA del micrófono
    if (mic.previousElementSibling === btn) return;

    mic.parentElement.insertBefore(btn, mic);
  }

  // Reintenta siempre: Spotify re-renderiza el player y el botón se pierde
  setInterval(attach, 800);
  attach();
})();
