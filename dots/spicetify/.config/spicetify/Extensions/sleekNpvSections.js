// NAME: Sleek Npv Sections
// DESCRIPTION: Tags now-playing-view blocks by their text so CSS can hide or reorder them.

(function sleekNpvSections() {
  const HIDE_MARK =
    /credits|créditos|about the artist|acerca del artista|monthly listeners|oyentes mensuales|^on tour$|^en gira$|related music videos|videos musicales relacionados|^music videos$|^videos musicales$/i;
  const SECTION_TOKEN = "nL2a9KOrkvOlg4iyuRDL";
  const CLASS = "sleek-hide-section";

  function sectionFor(node) {
    let el = node;
    for (let i = 0; i < 10 && el; i++, el = el.parentElement) {
      const cls = typeof el.className === "string" ? el.className : "";
      if (cls.includes(SECTION_TOKEN)) return el;
    }
    return node.closest("section");
  }

  function tagBlocks() {
    // lyrics
    document.querySelectorAll("h2,h3").forEach((h) => {
      const t = (h.textContent || "").trim();
      if (!/^(lyrics|letra)/i.test(t)) return;
      const block = sectionFor(h);
      const container = block && block.parentElement;
      if (container) container.classList.add("sleek-npv-lyrics");
      if (block) expand(block);
    });

    // queue
    document.querySelectorAll("h2,h3").forEach((h) => {
      const t = (h.textContent || "").trim();
      if (!/^(next in queue|a continuación|en cola)/i.test(t)) return;
      const section = h.closest("section");
      const container = section && section.parentElement;
      if (container) container.classList.add("sleek-npv-queue");
    });
  }

  function expand(block) {
    const btn = [...block.querySelectorAll("button")].find((b) =>
      /^(show more|mostrar más)$/i.test((b.textContent || "").trim())
    );
    if (btn) btn.click();
  }

  function apply() {
    const found = new Set();
    document.querySelectorAll("h1,h2,h3,h4,span,p,div").forEach((el) => {
      if (el.children.length) return;
      const text = (el.textContent || "").trim();
      if (!text || !HIDE_MARK.test(text)) return;
      const section = sectionFor(el);
      if (section) found.add(section);
    });

    document.querySelectorAll("." + CLASS).forEach((el) => {
      if (!found.has(el)) el.classList.remove(CLASS);
    });
    found.forEach((el) => el.classList.add(CLASS));

    tagBlocks();
  }

  setInterval(apply, 1000);
  window.addEventListener("resize", apply);
  apply();
})();
