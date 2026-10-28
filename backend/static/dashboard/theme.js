/* AUB SQUARE dashboard – theme switch (light / dark) with a circular reveal, plus brand-logo fallback.
   Loaded on every dashboard and sign-in page. The saved choice lives in localStorage ("aub.theme"). */
(function () {
  "use strict";
  var root = document.documentElement;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function save(t) { try { localStorage.setItem("aub.theme", t); } catch (e) {} }
  function apply(t) {
    root.setAttribute("data-theme", t);
    var m = document.querySelector('meta[name="theme-color"]'); if (m) m.setAttribute("content", t === "dark" ? "#09080E" : "#EEECF1");
    try { window.dispatchEvent(new CustomEvent("themechange", { detail: t })); } catch (e) {}
  }
  function setTheme(t, ev) {
    if (root.getAttribute("data-theme") === t) return;
    save(t);
    if (reduced) { apply(t); return; }
    if (!document.startViewTransition) {
      root.classList.add("theme-fade"); apply(t); setTimeout(function () { root.classList.remove("theme-fade"); }, 450); return;
    }
    var x = ev && ev.clientX != null ? ev.clientX : window.innerWidth / 2, y = ev && ev.clientY != null ? ev.clientY : 40;
    root.classList.add("theme-vt");
    var tr = document.startViewTransition(function () { apply(t); });
    tr.ready.then(function () {
      var r = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
      root.animate({ clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + r + "px at " + x + "px " + y + "px)"] },
        { duration: 650, easing: "cubic-bezier(.2,.8,.2,1)", pseudoElement: "::view-transition-new(root)" });
    }).catch(function () {});
    tr.finished.then(function () { root.classList.remove("theme-vt"); }, function () { root.classList.remove("theme-vt"); });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-theme-set]"); if (b) { e.preventDefault(); setTheme(b.getAttribute("data-theme-set"), e); }
  });
  window.AubTheme = { set: setTheme, get: function () { return root.getAttribute("data-theme"); } };

  /* If the uploaded logo can't be loaded, fall back to the initials mark instead of a broken image. */
  document.addEventListener("error", function (e) {
    var img = e.target;
    if (img && img.tagName === "IMG" && img.closest && img.closest("[data-brand-mark]")) {
      var box = img.closest("[data-brand-mark]"); box.classList.remove("brand__mark--img");
      box.textContent = box.getAttribute("data-initials") || "AS";
    }
  }, true);
})();
