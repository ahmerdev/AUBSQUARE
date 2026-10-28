/* Dashboard → Branding: Google Fonts picker + live Desktop/Tablet/Mobile preview of the website. Vanilla JS. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var dataEl = $("#font-data"); if (!dataEl) return;
  var fonts = []; try { fonts = JSON.parse(dataEl.textContent); } catch (e) {}
  var byName = {}; fonts.forEach(function (f) { byName[f.name] = f; });
  var loaded = {};
  function addCss(url) { if (!url || loaded[url]) return; loaded[url] = 1; var l = document.createElement("link"); l.rel = "stylesheet"; l.href = url; document.head.appendChild(l); }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }

  /* ---------------------------------------------------------------- font pickers */
  var CATS = [["all", "All"], ["sans", "Sans-serif"], ["serif", "Serif"], ["display", "Display"], ["script", "Script"], ["mono", "Monospace"]];
  function paintSamples() {
    var h = $("[name=heading_font]"), b = $("[name=body_font]");
    var hs = h && byName[h.value] ? byName[h.value].stack : "", bs = b && byName[b.value] ? byName[b.value].stack : "";
    $$("[data-sample=heading]").forEach(function (n) { if (hs) n.style.fontFamily = hs; });
    $$("[data-sample=body]").forEach(function (n) { if (bs) n.style.fontFamily = bs; });
  }
  $$("[data-fontpick]").forEach(function (root) {
    var input = $("input[type=hidden]", root), btn = $(".fontpick__btn", root), pop = $(".fontpick__pop", root), q = $(".fontpick__q", root), tabs = $(".fontpick__tabs", root), list = $(".fontpick__list", root);
    var cat = "all", io = null;
    CATS.forEach(function (c) { var t = el("button", c[0] === "all" ? "on" : "", c[1]); t.type = "button"; t.setAttribute("role", "tab"); t.dataset.cat = c[0]; tabs.appendChild(t); });
    if ("IntersectionObserver" in window) io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { var f = byName[e.target.dataset.name]; if (f) addCss(f.tiny); io.unobserve(e.target); } }); }, { root: list, rootMargin: "160px" });
    function paintButton() {
      var f = byName[input.value]; var nm = $(".fontpick__name", btn), ct = $(".fontpick__cat", btn);
      if (!f) { nm.textContent = input.value || "Choose a font"; ct.textContent = ""; return; }
      nm.textContent = f.name; nm.style.fontFamily = f.stack; ct.textContent = f.group; addCss(f.url);
    }
    function render() {
      var term = q.value.trim().toLowerCase(), cur = input.value; list.textContent = "";
      var items = fonts.filter(function (f) { return (cat === "all" || f.cat === cat) && (!term || f.name.toLowerCase().indexOf(term) > -1); });
      if (!items.length) { list.appendChild(el("div", "fontpick__none", "No fonts match “" + q.value + "”.")); return; }
      items.forEach(function (f) {
        var o = el("button", "fontpick__opt" + (f.name === cur ? " sel" : "")); o.type = "button"; o.setAttribute("role", "option"); o.setAttribute("aria-selected", f.name === cur ? "true" : "false"); o.dataset.name = f.name;
        var n = el("span", "fontpick__optname", f.name); n.style.fontFamily = f.stack; o.appendChild(n); o.appendChild(el("em", "", f.group)); list.appendChild(o);
        if (io) io.observe(o); else addCss(f.tiny);
      });
    }
    function open() { pop.hidden = false; btn.setAttribute("aria-expanded", "true"); root.classList.add("open"); q.value = ""; render(); var s = $(".fontpick__opt.sel", list); if (s) list.scrollTop = Math.max(0, s.offsetTop - 80); setTimeout(function () { q.focus(); }, 30); }
    function close() { pop.hidden = true; btn.setAttribute("aria-expanded", "false"); root.classList.remove("open"); }
    function choose(name) { if (!byName[name]) return; input.value = name; paintButton(); paintSamples(); close(); btn.focus(); input.dispatchEvent(new Event("input", { bubbles: true })); }
    btn.addEventListener("click", function () { pop.hidden ? open() : close(); });
    q.addEventListener("input", render);
    tabs.addEventListener("click", function (e) { var t = e.target.closest("button"); if (!t) return; cat = t.dataset.cat; $$("button", tabs).forEach(function (x) { x.classList.toggle("on", x === t); }); render(); });
    list.addEventListener("click", function (e) { var o = e.target.closest(".fontpick__opt"); if (o) choose(o.dataset.name); });
    root.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !pop.hidden) { e.stopPropagation(); close(); btn.focus(); return; }
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      var opts = $$(".fontpick__opt", list); if (!opts.length) return; e.preventDefault();
      var i = opts.indexOf(document.activeElement); i = e.key === "ArrowDown" ? Math.min(opts.length - 1, i + 1) : Math.max(0, i - 1);
      opts[i].focus(); opts[i].scrollIntoView({ block: "nearest" });
    });
    document.addEventListener("click", function (e) { if (!pop.hidden && !root.contains(e.target)) close(); });
    paintButton();
  });
  paintSamples();

  /* ---------------------------------------------------------------- live preview */
  var form = $("#brand-form"), pv = $("#pv"), frame = $("#pv-frame"), stage = $("#pv-stage"), device = $("#pv-device"), loading = $("#pv-loading"), sizeLbl = $("#pv-size");
  if (!form || !frame) return;
  var SIZES = { desktop: [1440, 900, "Desktop"], tablet: [820, 1100, "Tablet"], mobile: [390, 844, "Mobile"] };
  var cur = "desktop";
  function fit() {
    var d = SIZES[cur], w = d[0], h = d[1], sw = stage.clientWidth, sh = stage.clientHeight, pad = cur === "desktop" ? 0 : 20;
    if (!sw || !sh) return;
    var scale, boxW, boxH, vh;
    if (cur === "desktop") { scale = Math.min(1, sw / w); boxW = sw; boxH = sh; vh = sh / scale; }
    else { scale = Math.min(1, (sw - pad * 2) / w, (sh - pad * 2) / h); boxW = w * scale; boxH = h * scale; vh = h; }
    device.style.width = boxW + "px"; device.style.height = boxH + "px";
    frame.style.width = w + "px"; frame.style.height = vh + "px"; frame.style.transform = "scale(" + scale + ")";
    sizeLbl.textContent = d[2] + " · " + w + " px" + (scale < 1 ? " · shown at " + Math.round(scale * 100) + "%" : "");
  }
  function payload() {
    var h = ($("[name=heading_font]") || {}).value, b = ($("[name=body_font]") || {}).value, hf = byName[h], bf = byName[b];
    var logo = $("[name=logo_url]"), nm = $("[name=site_name]"), show = $("[name=header_show_name]");
    return { type: "aub-brand-preview", payload: { fontLinks: [hf && hf.url, bf && bf.url].filter(Boolean), headingStack: hf && hf.stack, bodyStack: bf && bf.stack,
      logo: logo ? logo.value : undefined, siteName: nm ? nm.value : undefined, headerShowName: show ? show.checked : undefined } };
  }
  /* The website may live on another address than the dashboard (React dev server on :3000, Django on :8000). */
  var KEY = "aub.previewbase", base = "", okReady = false, failT = null;
  function norm(v) { v = (v || "").trim(); if (!v) return ""; if (!/^https?:\/\//i.test(v)) v = "http://" + v; try { var u = new URL(v); return /^https?:$/.test(u.protocol) ? u.origin : null; } catch (e) { return null; } }
  function origin() { return base ? new URL(base).origin : window.location.origin; }
  function url(path) { return (base || "") + path; }
  try { var saved = localStorage.getItem(KEY); if (saved !== null) { var n = norm(saved); if (n !== null) base = n; } else base = norm(pv.dataset.base) || ""; } catch (e) { base = norm(pv.dataset.base) || ""; }
  if (base === window.location.origin) base = "";
  var addr = $("#pv-addr"), addrBtn = $("#pv-addr-go"), fail = $("#pv-fail");
  if (addr) addr.value = base;
  function absLogo(v) { return (typeof v === "string" && v.charAt(0) === "/" && v.charAt(1) !== "/") ? window.location.origin + v : v; }
  function send() { try { var m = payload(); m.payload.logo = absLogo(m.payload.logo); frame.contentWindow.postMessage(m, origin()); } catch (e) {} }
  function watch() { okReady = false; fail && fail.classList.add("hide"); clearTimeout(failT); failT = setTimeout(function () { if (!okReady && fail) { loading.classList.add("hide"); fail.classList.remove("hide"); var a = $("#pv-fail-addr"); if (a) a.textContent = origin(); } }, 9000); }
  function load(path) { loading.classList.remove("hide"); watch(); frame.src = url(path || (page ? page.value : "/")); }
  var t = null; function later() { clearTimeout(t); t = setTimeout(send, 120); }
  form.addEventListener("input", later); form.addEventListener("change", later);
  frame.addEventListener("load", function () { loading.classList.add("hide"); send(); });
  window.addEventListener("message", function (e) { if (e.origin === origin() && e.source === frame.contentWindow && e.data && e.data.type === "aub-preview-ready") { okReady = true; clearTimeout(failT); fail && fail.classList.add("hide"); loading.classList.add("hide"); send(); } });
  $$("[data-device]", pv).forEach(function (b) { b.addEventListener("click", function () { cur = b.dataset.device; stage.dataset.device = cur; $$("[data-device]", pv).forEach(function (x) { x.classList.toggle("on", x === b); }); fit(); }); });
  var page = $("#pv-page"); if (page) page.addEventListener("change", function () { load(page.value); });
  var rl = $("#pv-reload"); if (rl) rl.addEventListener("click", function () { load(); });
  function applyAddr() { var n = norm(addr.value); if (n === null) { addr.setCustomValidity("Enter an address like http://localhost:3000"); addr.reportValidity(); return; } addr.setCustomValidity(""); base = n === window.location.origin ? "" : n; addr.value = base; try { localStorage.setItem(KEY, base); } catch (e) {} load(); }
  if (addr && addrBtn) { addrBtn.addEventListener("click", applyAddr); addr.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); applyAddr(); } }); }
  $$("[data-addr]", pv).forEach(function (b) { b.addEventListener("click", function () { addr.value = b.dataset.addr; applyAddr(); }); });
  var vw = $("#pv-open"); if (vw) vw.addEventListener("click", function () { window.open(url(page ? page.value : "/"), "_blank", "noopener"); });
  load();
  var full = $("#pv-full");
  function setFull(on) { pv.classList.toggle("pv--full", on); document.body.classList.toggle("pv-lock", on); setTimeout(fit, 30); }
  if (full) full.addEventListener("click", function () { setFull(!pv.classList.contains("pv--full")); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && pv.classList.contains("pv--full")) setFull(false); });
  if ("ResizeObserver" in window) new ResizeObserver(fit).observe(stage); else window.addEventListener("resize", fit);
  fit();
  var rs = $("#bl-reset"); if (rs) rs.addEventListener("click", function () { window.__dirty = false; window.location.reload(); });
})();
