// NAME: Quick Queue (1.3.9 compat)
// DESCRIPTION: Adds the original add/remove-from-queue button to every tracklist row (visible on hover).

(function quickQueueFix() {
  const ICON_REMOVE = `<path d="M5.25 3v-.917C5.25.933 6.183 0 7.333 0h1.334c1.15 0 2.083.933 2.083 2.083V3h4.75v1.5h-.972l-1.257 9.544A2.25 2.25 0 0 1 11.041 16H4.96a2.25 2.25 0 0 1-2.23-1.956L1.472 4.5H.5V3h4.75zm1.5-.917V3h2.5v-.917a.583.583 0 0 0-.583-.583H7.333a.583.583 0 0 0-.583.583zM2.986 4.5l1.23 9.348a.75.75 0 0 0 .744.652h6.08a.75.75 0 0 0 .744-.652L13.015 4.5H2.985z"></path>`;
  const ICON_ADD = `<path d="M16 15H2v-1.5h14V15zm0-4.5H2V9h14v1.5zm-8.034-6A5.484 5.484 0 0 1 7.187 6H13.5a2.5 2.5 0 0 0 0-5H7.966c.159.474.255.978.278 1.5H13.5a1 1 0 1 1 0 2H7.966zM2 2V0h1.5v2h2v1.5h-2v2H2v-2H0V2h2z"></path>`;

  const ROW_SELECTOR = '.main-trackList-trackListRow, [data-testid="tracklist-row"]';

  // CSS de visibilidad: solo en hover, salvo que ya esté en la cola
  if (!document.getElementById('qq-fix-style')) {
    const style = document.createElement('style');
    style.id = 'qq-fix-style';
    style.textContent = `
      .qq-fix-btn { opacity: 0 !important; transition: opacity .08s linear; }
      .main-trackList-trackListRow:hover .qq-fix-btn,
      .main-trackList-trackListRow:focus-within .qq-fix-btn,
      [data-testid="tracklist-row"]:hover .qq-fix-btn,
      .qq-fix-btn[data-queued="1"] { opacity: 1 !important; }
      .qq-fix-btn:hover { color: var(--spice-text, #fff) !important; }
    `;
    document.head.appendChild(style);
  }

  function getUri(row) {
    const key = Object.keys(row).find((k) => k.startsWith('__reactFiber$') || k.startsWith('__reactInternalInstance$'));
    let fiber = key ? row[key] : null;
    for (let i = 0; i < 20 && fiber; i++, fiber = fiber.return) {
      const props = fiber.memoizedProps;
      if (!props) continue;
      const candidates = [props.uri, props.item && props.item.uri, props.track && props.track.uri, props.data && props.data.uri];
      const hit = candidates.find((x) => typeof x === 'string' && x.startsWith('spotify:'));
      if (hit) return hit;
    }
    return null;
  }

  function isQueued(uri) {
    try {
      const q = Spicetify.Platform.PlayerAPI.getQueue();
      const all = [...(q.queued || []), ...(q.nextUp || [])];
      return all.some((x) => x && x.uri === uri);
    } catch {
      return false;
    }
  }

  function render(btn, queued) {
    btn.dataset.queued = queued ? '1' : '0';
    btn.setAttribute('aria-checked', queued ? 'true' : 'false');
    btn.title = queued ? 'Remove from queue' : 'Add to queue';
    btn.setAttribute('aria-label', btn.title);
    btn.innerHTML = `<svg role="img" aria-hidden="true" height="16" width="16" viewBox="0 0 16 16" fill="currentColor">${queued ? ICON_REMOVE : ICON_ADD}</svg>`;
    btn.style.color = queued ? 'var(--spice-button, #1ed760)' : 'var(--spice-subtext, rgba(255,255,255,.6))';
  }

  function createButton(uri, moreBtn) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'qq-fix-btn';
    btn.style.cssText = [
      'background:transparent',
      'border:0',
      'padding:0',
      'cursor:pointer',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'margin-right:8px',
      'flex:0 0 auto',
    ].join(';');
    render(btn, isQueued(uri));

    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      e.preventDefault();
      const wasQueued = isQueued(uri);
      const target = !wasQueued;

      // Pintamos el estado esperado de inmediato (la cola tarda en reflejarlo)
      render(btn, target);

      try {
        if (wasQueued) {
          await Spicetify.Platform.PlayerAPI.removeFromQueue([{ uri }]);
          Spicetify.showNotification('Removed from queue');
        } else {
          await Spicetify.Platform.PlayerAPI.addToQueue([{ uri }]);
          Spicetify.showNotification('Added to queue');
        }
      } catch (err) {
        console.error('[quickQueue]', err);
        render(btn, wasQueued); // revertimos si falló
        Spicetify.showNotification('Queue action failed', true);
        return;
      }

      // Sincronizamos con la cola real, esperando a que refleje el cambio
      (async () => {
        for (let i = 0; i < 10; i++) {
          await new Promise((r) => setTimeout(r, 300));
          if (isQueued(uri) === target) break;
        }
        render(btn, isQueued(uri));
      })();
    });
    return btn;
  }

  function enhance(row) {
    if (!row || row.dataset.qqEnhanced === '1') return;
    const uri = getUri(row);
    if (!uri) return;

    const cells = row.children;
    if (!cells.length) return;

    // Primero de la columna derecha: antes de la duración
    const endCell = cells[cells.length - 1];
    const btn = createButton(uri, null);
    endCell.insertBefore(btn, endCell.firstElementChild);
    row.dataset.qqEnhanced = '1';
  }

  document.addEventListener('mouseover', (e) => {
    const row = e.target.closest && e.target.closest(ROW_SELECTOR);
    if (row) enhance(row);
  }, true);

  function sweep() {
    document.querySelectorAll(ROW_SELECTOR).forEach(enhance);
  }
  setInterval(sweep, 1500);
  sweep();
})();
