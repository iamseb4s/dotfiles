// NAME: Sleek Sidebar State
// DESCRIPTION: Marks <html> with .sleek-sb-collapsed only when the library sidebar hides the item names.

(function sleekSidebarState() {
  function sidebar() {
    return document.querySelector('nav');
  }

  function hasVisibleNames(nav) {
    const rows = [...nav.querySelectorAll('[role="row"]')];
    for (const row of rows.slice(0, 12)) {
      const nodes = row.querySelectorAll('span, div, a');
      for (const el of nodes) {
        if (el.children.length) continue;
        const text = (el.textContent || '').trim();
        if (text.length < 2) continue;
        const r = el.getBoundingClientRect();
        const visible = el.checkVisibility
          ? el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
          : getComputedStyle(el).display !== 'none';
        if (visible && r.width > 12 && r.height > 6) {
          return true;
        }
      }
    }
    return false;
  }

  function apply() {
    const nav = sidebar();
    const collapsed = nav ? !hasVisibleNames(nav) : false;
    document.documentElement.classList.toggle('sleek-sb-collapsed', collapsed);
  }

  setInterval(apply, 700);
  window.addEventListener('resize', apply);
  apply();
})();
