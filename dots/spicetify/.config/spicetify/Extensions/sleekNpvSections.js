// NAME: Sleek Npv Sections
// DESCRIPTION: Tags now-playing-view blocks by their text so CSS can hide them (artist, credits, on tour).

(function sleekNpvSections() {
  const MARK =
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

  function apply() {
    const found = new Set();

    document.querySelectorAll("h1,h2,h3,h4,span,p,div").forEach((el) => {
      if (el.children.length) return;
      const text = (el.textContent || "").trim();
      if (!text || !MARK.test(text)) return;
      const section = sectionFor(el);
      if (section) found.add(section);
    });

    document.querySelectorAll("." + CLASS).forEach((el) => {
      if (!found.has(el)) el.classList.remove(CLASS);
    });
    found.forEach((el) => el.classList.add(CLASS));
  }

  setInterval(apply, 1000);
  window.addEventListener("resize", apply);
  apply();
})();
