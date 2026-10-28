/* AUB SQUARE dashboard behaviour. Vanilla JS, no framework. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]; }); };
  function api(url, opts) {
    opts = opts || {};
    opts.credentials = "same-origin";
    opts.headers = Object.assign({ "X-Requested-With": "fetch", "X-CSRFToken": csrf, "Accept": "application/json" }, opts.headers || {});
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) { if (!r.ok) { var e = new Error((d.error && d.error.message) || d.error || "Request failed"); e.data = d; throw e; } return d; });
    });
  }
  window.Dash = { api: api, esc: esc, toast: toast, csrf: csrf };

  /* ---------- toasts ---------- */
  function toast(msg, level) {
    var box = $("#toasts"); if (!box) return;
    var t = document.createElement("div"); t.className = "toast " + (level || "info"); t.setAttribute("role", level === "error" ? "alert" : "status");
    t.innerHTML = "<div>" + esc(msg) + "</div>"; box.appendChild(t);
    setTimeout(function () { t.style.opacity = "0"; t.style.transition = "opacity .3s"; setTimeout(function () { t.remove(); }, 320); }, level === "error" ? 9000 : 5200);
  }
  var dm = $("#django-messages");
  if (dm) { try { JSON.parse(dm.textContent).forEach(function (m) { toast(m.text, m.level); }); } catch (e) {} }

  /* ---------- side menu: labelled (open) or icons only (closed) ---------- */
  $$("[data-rail-toggle]").forEach(function (b) { b.addEventListener("click", function () {
    var root = document.documentElement, next = root.getAttribute("data-rail") === "open" ? "closed" : "open";
    root.setAttribute("data-rail", next); store.set("aub.rail", next);
  }); });
  /* keep the page list where the user left it between page loads; first visit centres the current page */
  var railnav = $("#railnav");
  if (railnav) {
    var saved = null; try { saved = sessionStorage.getItem("aub.railscroll"); } catch (e) {}
    var cur = $("a.active", railnav);
    if (saved !== null && !isNaN(+saved)) railnav.scrollTop = +saved;
    if (cur) { var top = cur.offsetTop, h = railnav.clientHeight; if (top < railnav.scrollTop + 40 || top + cur.offsetHeight > railnav.scrollTop + h - 40) railnav.scrollTop = Math.max(0, top - h / 2 + cur.offsetHeight / 2); }
    var keep = function () { try { sessionStorage.setItem("aub.railscroll", String(railnav.scrollTop)); } catch (e) {} };
    railnav.addEventListener("scroll", keep, { passive: true }); window.addEventListener("pagehide", keep);
  }
  /* tooltips for the icon-only menu */
  var tip = $("#railtip");
  if (tip) {
    var showTip = function (el) {
      if (document.documentElement.getAttribute("data-rail") !== "closed") return;
      var r = el.getBoundingClientRect(); tip.textContent = el.getAttribute("data-tip") || el.getAttribute("aria-label") || "";
      tip.style.left = Math.round(r.right + 14) + "px"; tip.style.top = Math.round(r.top + r.height / 2 - tip.offsetHeight / 2) + "px"; tip.classList.add("show");
    };
    var hideTip = function () { tip.classList.remove("show"); };
    $$(".rail [data-tip]").forEach(function (el) {
      el.addEventListener("mouseenter", function () { showTip(el); }); el.addEventListener("mouseleave", hideTip);
      el.addEventListener("focus", function () { showTip(el); }); el.addEventListener("blur", hideTip);
    });
    if (railnav) railnav.addEventListener("scroll", hideTip, { passive: true });
    $$("[data-rail-toggle]").forEach(function (b) { b.addEventListener("click", hideTip); });
    var tt = $(".theme-toggle");
    $$(".theme-toggle button").forEach(function (b) { b.addEventListener("mouseenter", function () { if (document.documentElement.getAttribute("data-rail") === "closed") { b.setAttribute("data-tip", b.getAttribute("data-theme-set") === "dark" ? "Switch to dark" : "Switch to light"); showTip(b); } }); b.addEventListener("mouseleave", hideTip); });
  }

  /* ---------- mobile menu sheet + keyboard ---------- */
  var sheet = $("#menu-sheet");
  function closeSheet() { if (sheet) sheet.classList.remove("open"); }
  $$("[data-menu-sheet]").forEach(function (b) { b.addEventListener("click", function () { if (sheet) sheet.classList.add("open"); }); });
  $$("[data-menu-sheet-close]").forEach(function (b) { b.addEventListener("click", closeSheet); });
  if (sheet) sheet.addEventListener("click", function (e) { if (e.target === sheet) closeSheet(); });
  var spot = $("#spotlight");
  function openSpot() { if (!spot) return; closeMenus(); spot.classList.add("open"); var i = $("#global-search"); if (i) setTimeout(function () { i.focus(); i.select(); }, 40); }
  function closeSpot() { if (spot) spot.classList.remove("open"); }
  $$("[data-spotlight]").forEach(function (b) { b.addEventListener("click", openSpot); });
  if (spot) spot.addEventListener("click", function (e) { if (e.target === spot) closeSpot(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { closeSheet(); closeSpot(); closeMenus(); closeModals(); } });

  /* ---------- count-up numbers ---------- */
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    $$(".stat__value").forEach(function (el) {
      var raw = el.textContent.trim(); var m = raw.match(/^([^\d-]*)([\d,]+(?:\.\d+)?)(.*)$/); if (!m) return;
      var target = parseFloat(m[2].replace(/,/g, "")); if (!isFinite(target) || target === 0 || target > 1e9) return;
      var dec = (m[2].split(".")[1] || "").length, t0 = null, dur = 900;
      function fmt(v) { return v.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec }); }
      el.textContent = m[1] + fmt(0) + m[3];
      function step(ts) { if (t0 === null) t0 = ts; var p = Math.min(1, (ts - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = m[1] + fmt(target * e) + m[3]; if (p < 1) requestAnimationFrame(step); else el.textContent = raw; }
      requestAnimationFrame(step);
    });
  }

  /* ---------- dropdowns ---------- */
  function closeMenus(except) { $$(".menu.open").forEach(function (m) { if (m !== except) m.classList.remove("open"); }); $$("[data-menu-btn][aria-expanded=true]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); }); }
  $$("[data-menu-btn]").forEach(function (btn) {
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", function (e) {
      e.stopPropagation(); var menu = btn.parentElement.querySelector(".menu"); var open = menu.classList.contains("open");
      closeMenus(); if (!open) { menu.classList.add("open"); btn.setAttribute("aria-expanded", "true"); btn.dispatchEvent(new CustomEvent("menu:open")); }
    });
  });
  document.addEventListener("click", function (e) { if (!e.target.closest(".dropdown")) closeMenus(); });

  /* ---------- modals & confirm ---------- */
  function closeModals() { $$(".modal.open").forEach(function (m) { m.classList.remove("open"); }); }
  window.Dash.openModal = function (id) { var m = document.getElementById(id); if (m) { m.classList.add("open"); var f = m.querySelector("input,button,textarea,select"); if (f) setTimeout(function () { f.focus(); }, 30); } };
  window.Dash.closeModals = closeModals;
  document.addEventListener("click", function (e) {
    var o = e.target.closest("[data-open-modal]"); if (o) { e.preventDefault(); window.Dash.openModal(o.getAttribute("data-open-modal")); }
    if (e.target.closest("[data-close-modal]") || (e.target.classList && e.target.classList.contains("modal"))) closeModals();
  });
  var pendingConfirm = null;
  function askConfirm(msg, title, danger, then) {
    var m = $("#confirm-modal"); if (!m) { if (window.confirm(msg)) then(); return; }
    $("#confirm-title").textContent = title || "Please confirm"; $("#confirm-text").textContent = msg;
    var ok = $("#confirm-ok"); ok.className = "btn " + (danger ? "btn-danger" : "btn-primary"); pendingConfirm = then; window.Dash.openModal("confirm-modal");
  }
  var okBtn = $("#confirm-ok"); if (okBtn) okBtn.addEventListener("click", function () { closeModals(); if (pendingConfirm) { var f = pendingConfirm; pendingConfirm = null; f(); } });
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-confirm]"); if (!el || el.tagName === "FORM") return;
    if (el.dataset.confirmed) { delete el.dataset.confirmed; return; }
    e.preventDefault(); var form = el.form || el.closest("form");
    askConfirm(el.getAttribute("data-confirm"), el.getAttribute("data-confirm-title"), el.classList.contains("btn-danger") || el.hasAttribute("data-danger"), function () {
      if (el.tagName === "A") { window.location = el.href; return; }
      if (form) { if (el.name) { var h = document.createElement("input"); h.type = "hidden"; h.name = el.name; h.value = el.value; form.appendChild(h); } form.submit(); }
    });
  });

  /* ---------- prevent double submit ---------- */
  document.addEventListener("submit", function (e) {
    var f = e.target; if (f.method && f.method.toLowerCase() !== "post") return;
    f.setAttribute("data-submitting", "1");
    $$("button[type=submit]:not([data-keep]), input[type=submit]", f).forEach(function (b) { setTimeout(function () { b.disabled = true; b.classList.add("disabled"); }, 0); });
    window.__dirty = false;
  });

  /* ---------- tilt ---------- */
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && window.matchMedia("(hover: hover)").matches) {
    $$(".tilt").forEach(function (el) {
      el.addEventListener("pointermove", function (e) { var r = el.getBoundingClientRect(); var x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5; el.style.transform = "perspective(900px) rotateX(" + (-y * 5).toFixed(2) + "deg) rotateY(" + (x * 6).toFixed(2) + "deg) translateY(-2px)"; });
      el.addEventListener("pointerleave", function () { el.style.transform = ""; });
    });
  }

  /* ---------- global search ---------- */
  var sIn = $("#global-search"), sOut = $("#search-results"), sTimer;
  if (sIn && sOut) {
    sIn.addEventListener("input", function () {
      clearTimeout(sTimer); var q = sIn.value.trim();
      var hint = $("#spot-hint"); if (hint) hint.style.display = q.length < 2 ? "" : "none";
      if (q.length < 2) { sOut.classList.remove("open"); return; }
      sTimer = setTimeout(function () {
        api(sIn.dataset.url + "?q=" + encodeURIComponent(q)).then(function (d) {
          if (!d.results.length) { sOut.innerHTML = '<div class="empty small">No matches for “' + esc(q) + '”</div>'; }
          else { var g = "", h = ""; d.results.forEach(function (r) { if (r.group !== g) { g = r.group; h += "<h6>" + esc(g) + "</h6>"; } h += '<a href="' + esc(r.url) + '">' + esc(r.label) + "</a>"; }); sOut.innerHTML = h; }
          sOut.classList.add("open");
        }).catch(function () { sOut.innerHTML = '<div class="empty small">Search is unavailable right now.</div>'; sOut.classList.add("open"); });
      }, 220);
    });
    document.addEventListener("keydown", function (e) { if ((e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !document.activeElement.isContentEditable) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) { e.preventDefault(); openSpot(); } });
  }

  /* ---------- notifications ---------- */
  var nBtn = $("#notif-btn"), nList = $("#notif-list"), nDot = $("#notif-dot");
  function setUnread(n) { if (!nBtn) return; if (n > 0) { if (!nDot) { nDot = document.createElement("span"); nDot.className = "dot"; nDot.id = "notif-dot"; nBtn.appendChild(nDot); } nDot.textContent = n > 99 ? "99+" : n; } else if (nDot) { nDot.remove(); nDot = null; } }
  function loadNotifs() {
    api(nBtn.dataset.feed).then(function (d) {
      setUnread(d.unread);
      nList.innerHTML = d.items.length ? d.items.map(function (n) { return '<a class="notif ' + (n.read ? "" : "unread") + '" href="' + esc(n.url || "#") + '" data-id="' + n.id + '"><b>' + esc(n.title) + "</b><span>" + esc(n.body) + "</span></a>"; }).join("") : '<div class="empty small">You\'re all caught up.</div>';
    }).catch(function () { nList.innerHTML = '<div class="empty small">Couldn\'t load notifications.</div>'; });
  }
  if (nBtn && nList) {
    nBtn.addEventListener("menu:open", loadNotifs);
    setInterval(function () { if (!document.hidden) api(nBtn.dataset.feed).then(function (d) { setUnread(d.unread); }).catch(function () {}); }, 60000);
    nList.addEventListener("click", function (e) { var a = e.target.closest("a.notif"); if (a) { navigator.sendBeacon && navigator.sendBeacon("/dashboard/notifications/" + a.dataset.id + "/read/", new URLSearchParams({ csrfmiddlewaretoken: csrf })); } });
    var mr = $("#notif-markall"); if (mr) mr.addEventListener("click", function () { api(mr.dataset.url, { method: "POST" }).then(function () { setUnread(0); loadNotifs(); }); });
  }

  /* ---------- fieldset collapse ---------- */
  $$(".fieldset > .fsec__head, .fieldset > .card__head").forEach(function (h) { h.addEventListener("click", function () { h.parentElement.classList.toggle("collapsed"); }); });
  $$(".fieldset.has-errors").forEach(function (f) { f.classList.remove("collapsed"); });

  /* ---------- SEO counters + preview, slug helper ---------- */
  function counter(input, min, max) {
    if (!input) return; var c = document.createElement("span"); c.className = "counter"; input.parentElement.insertBefore(c, input);
    function upd() { var n = input.value.length; c.textContent = n + " / " + max; c.className = "counter " + (n > max ? "over" : n >= min ? "good" : ""); }
    input.addEventListener("input", upd); upd();
  }
  var st = $("#id_seo_title"), md = $("#id_meta_description");
  counter(st, 40, 60); counter(md, 110, 160);
  var serp = $("#serp");
  if (serp && (st || md)) {
    var tt = $("#id_title") || $("#id_name") || $("#id_label"), sl = $("#id_slug");
    var upd = function () { $(".t", serp).textContent = (st && st.value) || (tt && tt.value) || "Page title"; $(".d", serp).textContent = (md && md.value) || "Add a meta description to control how this page appears in search results."; $(".u", serp).textContent = serp.dataset.base + ((sl && sl.value) || ""); };
    [st, md, tt, sl].forEach(function (i) { if (i) i.addEventListener("input", upd); }); upd();
  }
  var tIn = $("#id_title"), sIn2 = $("#id_slug");
  if (tIn && sIn2 && !sIn2.value) {
    var touched = false; sIn2.addEventListener("input", function () { touched = true; });
    tIn.addEventListener("input", function () { if (!touched) sIn2.value = tIn.value.toLowerCase().replace(/[^a-z0-9\s-]/g, "").trim().replace(/\s+/g, "-").slice(0, 80); });
  }

  /* ---------- unsaved changes ---------- */
  var wf = $("form[data-warn-unsaved]");
  if (wf) { wf.addEventListener("input", function () { window.__dirty = true; wf.classList.add("is-dirty"); }); wf.addEventListener("change", function () { wf.classList.add("is-dirty"); }); window.addEventListener("beforeunload", function (e) { if (window.__dirty) { e.preventDefault(); e.returnValue = ""; } }); }

  /* ---------- form: highlight the section being read in "On this page" ---------- */
  var tocLinks = $$(".fl__toc a[data-spy]");
  if (tocLinks.length) {
    var secs = tocLinks.map(function (a) { return document.getElementById(a.getAttribute("data-spy")); }).filter(Boolean), ticking = false;
    var spy = function () {
      ticking = false; var line = Math.min(window.innerHeight * 0.32, 300), cur = secs[0];
      secs.forEach(function (s) { if (s.getBoundingClientRect().top <= line) cur = s; });
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) cur = secs[secs.length - 1];
      tocLinks.forEach(function (a) { a.classList.toggle("on", cur && a.getAttribute("data-spy") === cur.id); });
    };
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(spy); } }, { passive: true });
    window.addEventListener("resize", spy); spy();
    tocLinks.forEach(function (a) { a.addEventListener("click", function () { var t = document.getElementById(a.getAttribute("data-spy")); if (t) t.classList.remove("collapsed"); }); });
  }

  /* ---------- bulk selection ---------- */
  var master = $("#check-all");
  function updateBulk() {
    var checked = $$(".js-row-check:checked"); var bar = $("#bulkbar"); if (!bar) return;
    bar.classList.toggle("show", checked.length > 0); var c = $("#bulk-count"); if (c) c.textContent = checked.length;
    var ids = $("#bulk-ids"); if (ids) ids.innerHTML = checked.map(function (x) { return '<input type="hidden" name="ids" value="' + esc(x.value) + '">'; }).join("");
    var ex = $("#bulk-export"); if (ex) ex.href = ex.dataset.base + (ex.dataset.base.indexOf("?") > -1 ? "&" : "?") + "ids=" + checked.map(function (x) { return x.value; }).join(",");
  }
  if (master) master.addEventListener("change", function () { $$(".js-row-check").forEach(function (c) { c.checked = master.checked; }); updateBulk(); });
  document.addEventListener("change", function (e) { if (e.target.classList && e.target.classList.contains("js-row-check")) updateBulk(); });

  /* ---------- copy ---------- */
  document.addEventListener("click", function (e) { var b = e.target.closest("[data-copy]"); if (!b) return; var t = b.getAttribute("data-copy"); (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () { toast("Copied to clipboard", "success"); }).catch(function () { toast("Couldn't copy — select and copy manually.", "warning"); }); });

  /* ---------- repeater ---------- */
  $$("[data-repeater]").forEach(function (rp) {
    var spec = JSON.parse(rp.dataset.spec), store_ = $("[data-repeater-store]", rp), rows = $("[data-repeater-rows]", rp), data = [];
    try { data = JSON.parse(store_.value || "[]"); } catch (e) { data = []; }
    function save() { var out = []; $$(".repeater__row", rows).forEach(function (r) { var o = {}; $$("[data-k]", r).forEach(function (i) { o[i.dataset.k] = i.value; }); out.push(o); }); store_.value = JSON.stringify(out); store_.dispatchEvent(new Event("input", { bubbles: true })); }
    function row(v) {
      var d = document.createElement("div"); d.className = "repeater__row";
      d.innerHTML = '<div class="repeater__cols">' + spec.map(function (s) { var val = esc(v && v[s.key] != null ? v[s.key] : ""); return "<div><label>" + esc(s.label) + "</label>" + (s.type === "textarea" ? '<textarea class="input" rows="3" data-k="' + s.key + '">' + val + "</textarea>" : '<input class="input" data-k="' + s.key + '" value="' + val + '">') + "</div>"; }).join("") + '</div><div class="repeater__tools"><button type="button" class="btn btn-sm btn-ghost" data-up title="Move up">↑</button><button type="button" class="btn btn-sm btn-ghost" data-down title="Move down">↓</button><button type="button" class="btn btn-sm btn-danger" data-del title="Remove">✕</button></div>';
      rows.appendChild(d);
    }
    data.forEach(row);
    rp.addEventListener("input", function (e) { if (e.target !== store_) save(); });
    rp.addEventListener("click", function (e) {
      var r = e.target.closest(".repeater__row");
      if (e.target.closest("[data-del]") && r) { r.remove(); save(); }
      else if (e.target.closest("[data-up]") && r && r.previousElementSibling) { rows.insertBefore(r, r.previousElementSibling); save(); }
      else if (e.target.closest("[data-down]") && r && r.nextElementSibling) { rows.insertBefore(r.nextElementSibling, r); save(); }
      else if (e.target.closest("[data-repeater-add]")) { row({}); }
    });
  });

  /* ---------- media picker ---------- */
  var pickerTarget = null, pickerPage = 1, pickerQ = "";
  function loadPicker() {
    var grid = $("#picker-grid"); if (!grid) return; grid.innerHTML = '<div class="skeleton" style="height:150px"></div>'.repeat(6);
    api("/dashboard/media/picker/?page=" + pickerPage + "&q=" + encodeURIComponent(pickerQ) + (pickerTarget && pickerTarget.dataset.kind === "image" ? "&kind=image" : "")).then(function (d) {
      grid.innerHTML = d.items.length ? d.items.map(function (a) { return '<button type="button" class="media-item" data-url="' + esc(a.url) + '" data-alt="' + esc(a.alt) + '"><div class="img" style="' + (a.kind === "image" ? "background-image:url('" + esc(a.url) + "')" : "") + '">' + (a.kind === "image" ? "" : "📄") + '</div><div class="meta"><b>' + esc(a.title) + "</b></div></button>"; }).join("") : '<div class="empty" style="grid-column:1/-1"><h3>No files yet</h3><p>Upload an image above.</p></div>';
      var p = $("#picker-pages"); if (p) p.textContent = "Page " + d.page + " of " + d.pages; $("#picker-prev").disabled = d.page <= 1; $("#picker-next").disabled = d.page >= d.pages;
    }).catch(function () { grid.innerHTML = '<div class="empty" style="grid-column:1/-1">Couldn\'t load the library.</div>'; });
  }
  function setPreview(box, url) { var pv = $(".media-picker__preview", box); pv.innerHTML = url ? '<img src="' + esc(url) + '" alt="" onerror="this.style.display=\'none\'">' : ""; }
  document.addEventListener("click", function (e) {
    var open = e.target.closest("[data-media-open]"), clr = e.target.closest("[data-media-clear]");
    if (open) { pickerTarget = open.closest(".media-picker"); pickerPage = 1; window.Dash.openModal("picker-modal"); loadPicker(); }
    if (clr) { var b = clr.closest(".media-picker"); $("input", b).value = ""; setPreview(b, ""); $("input", b).dispatchEvent(new Event("input", { bubbles: true })); }
    var item = e.target.closest("#picker-grid .media-item");
    if (item && (pickerTarget || window.__quillPick)) {
      if (window.__quillPick) { window.__quillPick(item.dataset.url, item.dataset.alt); window.__quillPick = null; }
      else { var inp = $("input", pickerTarget); inp.value = item.dataset.url; setPreview(pickerTarget, item.dataset.url); inp.dispatchEvent(new Event("input", { bubbles: true })); }
      closeModals();
    }
  });
  var pq = $("#picker-q"); if (pq) { var pt; pq.addEventListener("input", function () { clearTimeout(pt); pt = setTimeout(function () { pickerQ = pq.value; pickerPage = 1; loadPicker(); }, 250); }); }
  var pp = $("#picker-prev"), pn = $("#picker-next"); if (pp) pp.addEventListener("click", function () { pickerPage = Math.max(1, pickerPage - 1); loadPicker(); }); if (pn) pn.addEventListener("click", function () { pickerPage++; loadPicker(); });
  $$(".media-picker input[type=text]").forEach(function (i) { i.addEventListener("input", function () { setPreview(i.closest(".media-picker"), i.value); }); });

  function uploadFiles(files, onDone, bar) {
    var fd = new FormData(); Array.prototype.forEach.call(files, function (f) { fd.append("files", f); });
    var xhr = new XMLHttpRequest(); xhr.open("POST", "/dashboard/media/upload/"); xhr.setRequestHeader("X-CSRFToken", csrf); xhr.setRequestHeader("X-Requested-With", "fetch");
    if (bar) { bar.style.display = "block"; xhr.upload.onprogress = function (e) { if (e.lengthComputable) $("i", bar).style.width = (e.loaded / e.total * 100) + "%"; }; }
    xhr.onload = function () { if (bar) { setTimeout(function () { bar.style.display = "none"; $("i", bar).style.width = "0"; }, 400); } var d = {}; try { d = JSON.parse(xhr.responseText); } catch (e) {} (d.errors || []).forEach(function (er) { toast(er.name + ": " + er.message, "error"); }); if (xhr.status === 403) toast("You don't have permission to upload.", "error"); if (d.items && d.items.length) { toast(d.items.length + " file(s) uploaded", "success"); onDone && onDone(d.items); } };
    xhr.onerror = function () { toast("Upload failed — check your connection.", "error"); if (bar) bar.style.display = "none"; };
    xhr.send(fd);
  }
  window.Dash.upload = uploadFiles;
  $$("[data-dropzone]").forEach(function (dz) {
    var input = $("input[type=file]", dz), bar = $(".progress", dz.parentElement) || $(".progress");
    dz.addEventListener("click", function (e) { if (e.target !== input) input.click(); });
    ["dragenter", "dragover"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("over"); }); });
    dz.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files, after, bar); });
    input.addEventListener("change", function () { if (input.files.length) uploadFiles(input.files, after, bar); });
    function after() { if (dz.dataset.dropzone === "picker") { pickerPage = 1; loadPicker(); } else { setTimeout(function () { location.reload(); }, 700); } }
  });

  /* ---------- rich text (Quill) ---------- */
  $$("[data-richtext]").forEach(function (box) {
    if (!window.Quill) { var ta = $("textarea", box); ta.hidden = false; ta.className = "input"; ta.rows = 14; return; }
    var src = $(".rt__source", box), ed = $(".rt__editor", box);
    var q = new Quill(ed, { theme: "snow", placeholder: "Start writing…", modules: { toolbar: { container: [[{ header: [2, 3, false] }], ["bold", "italic", "underline", "strike"], ["blockquote", "code-block"], [{ list: "ordered" }, { list: "bullet" }], ["link", "image"], ["clean"]], handlers: {
      image: function () {
        var range = q.getSelection(true);
        window.__quillPick = function (url, alt) { q.insertEmbed(range.index, "image", url, "user"); q.setSelection(range.index + 1); };
        pickerTarget = null; window.Dash.openModal("picker-modal"); loadPicker();
      } } } } });
    q.clipboard.dangerouslyPasteHTML(src.value || "");
    function sync() { var h = q.root.innerHTML; src.value = (h === "<p><br></p>") ? "" : h; }
    q.on("text-change", function () { sync(); window.__dirty = true; });
    box.closest("form").addEventListener("submit", sync);
  });

  /* ---------- charts (re-coloured when the theme changes) ---------- */
  if (window.Chart) {
    var PAL = ["#EC008C", "#7B2FFF", "#9333EA", "#38BDF8", "#34D399", "#FBBF24", "#F87171", "#C99BFF"], charts = [];
    var cssv = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
    function chartTheme() {
      Chart.defaults.color = cssv("--muted") || "#A9A4C2"; Chart.defaults.font.family = getComputedStyle(document.body).fontFamily; Chart.defaults.borderColor = cssv("--grid-line") || "rgba(255,255,255,.07)";
      Chart.defaults.plugins.legend.labels.usePointStyle = true; Chart.defaults.plugins.tooltip.backgroundColor = cssv("--tt-bg") || "#221a42"; Chart.defaults.plugins.tooltip.titleColor = cssv("--text"); Chart.defaults.plugins.tooltip.bodyColor = cssv("--muted");
      Chart.defaults.plugins.tooltip.borderColor = cssv("--line-2"); Chart.defaults.plugins.tooltip.borderWidth = 1; Chart.defaults.plugins.tooltip.padding = 10; Chart.defaults.plugins.tooltip.cornerRadius = 12;
    }
    chartTheme();
    $$("canvas[data-chart]").forEach(function (cv) {
      var cfg; try { cfg = JSON.parse(document.getElementById(cv.dataset.chart).textContent); } catch (e) { return; }
      var ctx = cv.getContext("2d"), type = cfg.type || "line";
      var datasets = cfg.datasets.map(function (d, i) {
        var col = d.color || PAL[i % PAL.length];
        if (type === "line") { var g = ctx.createLinearGradient(0, 0, 0, cv.height || 260); g.addColorStop(0, col + "55"); g.addColorStop(1, col + "00"); return Object.assign({ borderColor: col, backgroundColor: g, fill: true, tension: .38, pointRadius: 0, pointHoverRadius: 5, borderWidth: 2.4 }, d); }
        if (type === "bar") return Object.assign({ backgroundColor: col, borderRadius: 10, maxBarThickness: 34 }, d);
        return Object.assign({ backgroundColor: PAL, borderWidth: 0 }, d);
      });
      charts.push(new Chart(ctx, { type: type, data: { labels: cfg.labels, datasets: datasets }, options: Object.assign({ responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, animation: { duration: 900, easing: "easeOutQuart" },
        plugins: { legend: { display: datasets.length > 1 || type === "doughnut", position: "bottom", labels: { usePointStyle: true, color: Chart.defaults.color } } },
        scales: (type === "doughnut" || type === "pie") ? {} : { x: { grid: { display: false }, ticks: { maxTicksLimit: 8, color: Chart.defaults.color } }, y: { beginAtZero: true, grid: { color: Chart.defaults.borderColor }, ticks: { precision: 0, color: Chart.defaults.color } } },
        cutout: type === "doughnut" ? "68%" : undefined }, cfg.options || {}) }));
    });
    window.addEventListener("themechange", function () {
      chartTheme();
      charts.forEach(function (c) {
        var o = c.config.options, col = Chart.defaults.color;   // edit the raw config: resolved options are cached by Chart.js
        if (o.plugins && o.plugins.legend && o.plugins.legend.labels) o.plugins.legend.labels.color = col;
        Object.keys(o.scales || {}).forEach(function (k) { var sc = o.scales[k]; if (sc.ticks) sc.ticks.color = col; if (sc.grid && sc.grid.color) sc.grid.color = Chart.defaults.borderColor; });
        c.update("none");
      });
    });
  }

  /* ---------- admin live chat ---------- */
  var chat = $("#chat-log");
  if (chat) {
    var last = parseInt(chat.dataset.last || "0", 10), pollUrl = chat.dataset.poll, form = $("#chat-form"), ta2 = form && $("textarea", form);
    var scroll = function () { chat.scrollTop = chat.scrollHeight; }; scroll();
    function render(m) { if ($("[data-mid='" + m.id + "']", chat)) return; var d = document.createElement("div"); d.className = "msg msg--" + m.sender; d.dataset.mid = m.id; var t = new Date(m.at); d.innerHTML = esc(m.body) + "<small>" + (m.agent ? esc(m.agent) + " · " : m.sender === "bot" ? "Bot · " : "") + t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) + "</small>"; chat.appendChild(d); last = Math.max(last, m.id); }
    function poll() { if (document.hidden) return; api(pollUrl + "?after=" + last).then(function (d) { var near = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 140; d.messages.forEach(render); if (d.messages.length && near) scroll(); var s = $("#chat-status"); if (s && d.status) s.textContent = d.status; }).catch(function () {}); }
    setInterval(poll, 3500);
    if (form) {
      form.addEventListener("submit", function (e) { e.preventDefault(); var body = ta2.value.trim(); if (!body) return; var btn = $("button[type=submit]", form); btn.disabled = true; api(form.action, { method: "POST", body: new URLSearchParams({ body: body }) }).then(function (d) { render(d.message); ta2.value = ""; scroll(); }).catch(function (er) { toast(er.message, "error"); }).then(function () { btn.disabled = false; ta2.focus(); }); });
      ta2.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
    }
  }

  /* ---------- home builder ---------- */
  var hb = $("#builder");
  if (hb) {
    $$(".builder-head", hb).forEach(function (h) { h.addEventListener("click", function (e) { if (e.target.closest(".switch,.handle,.mv,button,a")) return; h.parentElement.classList.toggle("open"); }); });
    function move(item, dir) { var sib = dir < 0 ? item.previousElementSibling : item.nextElementSibling; if (!sib || sib.dataset.fixed || item.dataset.fixed) return; hb.insertBefore(dir < 0 ? item : sib, dir < 0 ? sib : item); window.__dirty = true; }
    hb.addEventListener("click", function (e) { var up = e.target.closest(".mv-up"), dn = e.target.closest(".mv-down"); if (up) move(up.closest(".builder-item"), -1); if (dn) move(dn.closest(".builder-item"), 1); });
    $$(".switch input", hb).forEach(function (s) { s.addEventListener("change", function () { s.closest(".builder-item").classList.toggle("hidden-section", !s.checked); }); });
    var drag = null;
    $$(".builder-item:not([data-fixed]) .handle", hb).forEach(function (hd) {
      var it = hd.closest(".builder-item"); hd.draggable = true;
      hd.addEventListener("dragstart", function (e) { drag = it; it.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setDragImage(it, 20, 20); } catch (x) {} });
      hd.addEventListener("dragend", function () { it.classList.remove("dragging"); drag = null; });
    });
    hb.addEventListener("dragover", function (e) { if (!drag) return; e.preventDefault(); var over = e.target.closest(".builder-item"); if (!over || over === drag || over.dataset.fixed) return; var r = over.getBoundingClientRect(); hb.insertBefore(drag, e.clientY < r.top + r.height / 2 ? over : over.nextSibling); window.__dirty = true; });
  }

  /* ---------- permission matrix helpers ---------- */
  $$("[data-row-all]").forEach(function (b) { b.addEventListener("click", function () { var tr = b.closest("tr"); var boxes = $$("input[type=checkbox]", tr); var all = boxes.every(function (x) { return x.checked; }); boxes.forEach(function (x) { x.checked = !all; }); }); });
  $$("[data-col-all]").forEach(function (b) { b.addEventListener("click", function () { var boxes = $$("input[data-act='" + b.dataset.colAll + "']"); var all = boxes.every(function (x) { return x.checked; }); boxes.forEach(function (x) { x.checked = !all; }); }); });

  /* ---------- email provider presets ---------- */
  var preset = $("#id_provider");
  if (preset) {
    // window.__presets is defined by a script that loads AFTER this file, so it is read when the choice changes (not at load time)
    preset.addEventListener("change", function () {
      var all = window.__presets || {}, p = all[preset.value]; if (!p) return;
      var set = function (id, v) { var el = $(id); if (el && v !== "" && v != null) { el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); } };
      set("#id_smtp_host", p.host); set("#id_smtp_port", p.port); set("#id_smtp_security", p.security);
      set("#id_imap_host", p.imap_host); set("#id_imap_port", p.imap_port); set("#id_imap_security", p.imap_security);
      var un = $("#id_smtp_username"), from = $("#id_from_email");
      if (un && !un.value && from && from.value) un.value = from.value;
      var note = $("#provider-note"); if (note) note.textContent = p.note || "";
    });
  }
})();

/* ---- Outbound sales: pipeline drag & drop, busy buttons ---- */
(function () {
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  $$("form").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      var b = e.submitter || f.querySelector("[data-busy]"); if (!b || !b.hasAttribute("data-busy")) return;
      setTimeout(function () { b.classList.add("is-busy"); b.setAttribute("aria-busy", "true"); b.dataset.label = b.textContent; b.textContent = b.getAttribute("data-busy"); }, 0);
    });
  });
  var board = document.querySelector(".kanban"); if (!board || board.dataset.can !== "1") return;
  var csrf = (document.querySelector("input[name=csrfmiddlewaretoken]") || {}).value || (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
  var dragged = null;
  board.addEventListener("dragstart", function (e) { var c = e.target.closest(".kcard"); if (!c) return; dragged = c; c.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", c.dataset.id); } catch (x) {} });
  board.addEventListener("dragend", function () { if (dragged) dragged.classList.remove("dragging"); dragged = null; $$(".kcards.over").forEach(function (z) { z.classList.remove("over"); }); });
  board.addEventListener("dragover", function (e) { var z = e.target.closest("[data-drop]"); if (!z || !dragged) return; e.preventDefault(); $$(".kcards.over").forEach(function (x) { if (x !== z) x.classList.remove("over"); }); z.classList.add("over"); });
  board.addEventListener("drop", function (e) {
    var z = e.target.closest("[data-drop]"); if (!z || !dragged) return; e.preventDefault(); z.classList.remove("over");
    var from = dragged.closest(".kcol"), to = z.closest(".kcol"); if (from === to) return;
    var empty = z.querySelector(".kempty"); if (empty) empty.remove(); z.insertBefore(dragged, z.firstChild);
    var fd = new FormData(); fd.append("kind", board.dataset.kind); fd.append("id", dragged.dataset.id); fd.append("to", to.dataset.col); fd.append("csrfmiddlewaretoken", csrf);
    var card = dragged;
    fetch(board.dataset.move, { method: "POST", body: fd, credentials: "same-origin", headers: { "X-Requested-With": "fetch" } }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); }).then(function (res) {
      if (!res.ok) { from.querySelector("[data-drop]").appendChild(card); alert((res.j && res.j.error) || "Could not move this card."); return; }
      [from, to].forEach(function (col) { var n = col.querySelector(".kcount"); if (n) n.textContent = col.querySelectorAll(".kcard").length; });
    }).catch(function () { from.querySelector("[data-drop]").appendChild(card); alert("Network problem – the card was not moved."); });
  });
})();

/* ---------- searchable country / city pickers (real GeoNames list in geo.json) ---------- */
(function () {
  "use strict";
  var els = document.querySelectorAll("[data-geo-country], [data-geo-city], [data-geo-multi]");
  if (!els.length) return;
  var src = (document.querySelector("meta[name=geo-src]") || {}).content || "/static/dashboard/geo.json";
  var cache = null, waiting = [];
  function load(cb) {
    if (cache) return cb(cache);
    waiting.push(cb);
    if (waiting.length > 1) return;
    fetch(src, { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (d) {
      cache = d.countries; cache.byName = {}; cache.forEach(function (c) { cache.byName[c.n.toLowerCase()] = c; });
      waiting.splice(0).forEach(function (f) { f(cache); });
    }).catch(function () { cache = []; cache.byName = {}; waiting.splice(0).forEach(function (f) { f(cache); }); });
  }
  function flag(iso) { try { return String.fromCodePoint.apply(null, iso.toUpperCase().split("").map(function (ch) { return 127397 + ch.charCodeAt(0); })); } catch (e) { return ""; } }
  function esc(s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function rank(items, q, key) {
    q = q.trim().toLowerCase(); if (!q) return items.slice(0, 80);
    var a = [], b = [];
    items.forEach(function (it) { var k = key(it).toLowerCase(); if (k.indexOf(q) === 0) a.push(it); else if (k.indexOf(q) > -1) b.push(it); });
    return a.concat(b).slice(0, 80);
  }

  /* generic dropdown attached to an <input> */
  function combo(input, getItems, render, onPick, emptyText, opts) {
    opts = opts || {};
    var wrap = document.createElement("div"); wrap.className = "combo";
    input.parentNode.insertBefore(wrap, input); wrap.appendChild(input);
    var list = document.createElement("ul"); list.className = "combo__list"; list.setAttribute("role", "listbox"); list.hidden = true; wrap.appendChild(list);
    var caret = document.createElement("span"); caret.className = "combo__caret"; caret.setAttribute("aria-hidden", "true"); wrap.appendChild(caret);
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list"); input.setAttribute("aria-expanded", "false"); input.autocomplete = "off";
    var items = [], idx = -1;
    function open() { items = getItems(input.value); idx = -1; paint(); list.hidden = false; input.setAttribute("aria-expanded", "true"); }
    function close() { list.hidden = true; input.setAttribute("aria-expanded", "false"); }
    function paint() {
      list.innerHTML = items.length ? items.map(function (it, i) { return '<li role="option" data-i="' + i + '" class="' + (i === idx ? "on" : "") + '">' + render(it) + "</li>"; }).join("") : '<li class="combo__empty">' + esc(emptyText(input.value)) + "</li>";
      var on = list.querySelector(".on"); if (on && on.scrollIntoView) on.scrollIntoView({ block: "nearest" });
    }
    function pick(i) { if (items[i] === undefined) return; onPick(items[i]); close(); }
    input.addEventListener("focus", open); input.addEventListener("click", function () { if (list.hidden) open(); });
    input.addEventListener("input", open);
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); if (list.hidden) open(); idx = Math.min(items.length - 1, idx + 1); paint(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); idx = Math.max(0, idx - 1); paint(); }
      else if (e.key === "Enter") {
        var visible = !list.hidden && items.length > 0;
        if (visible && idx > -1) { e.preventDefault(); pick(idx); }
        else if (visible && opts.pickFirst && input.value.trim()) { e.preventDefault(); pick(0); }
        else if (opts.noSubmit) { e.preventDefault(); }
      }
      else if (e.key === "Escape") { close(); }
    });
    list.addEventListener("mousedown", function (e) { var li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); pick(+li.dataset.i); } });
    document.addEventListener("mousedown", function (e) { if (!wrap.contains(e.target)) close(); });
    input.addEventListener("blur", function () { setTimeout(close, 120); });
    return { open: open, close: close, wrap: wrap };
  }

  load(function (countries) {
    function countryItems(q) { return rank(countries, q, function (c) { return c.n; }); }
    function countryRow(c) { return '<span class="combo__flag">' + flag(c.c) + "</span><span>" + esc(c.n) + '</span><small>' + (c.ci.length ? c.ci.length + " cities" : "") + "</small>"; }
    function find(name) { return countries.byName[(name || "").trim().toLowerCase()]; }

    /* single country (+ linked city) */
    document.querySelectorAll("[data-geo-country]").forEach(function (cin) {
      var form = cin.form || document, cityIn = form.querySelector("[data-geo-city]"), hint = null;
      var cityCombo = null;
      function setCities() {
        var c = find(cin.value);
        if (cityIn) {
          cityIn.placeholder = c ? "Search " + c.n + " cities, or type your own" : "Choose a country first (or type any city)";
          cityIn.dataset.country = c ? c.c : "";
        }
        cin.classList.toggle("is-geo-ok", !!c);
        if (hint) hint.textContent = c ? (flag(c.c) + " " + c.n + " — " + c.ci.length + " cities available") : (cin.value.trim() ? "Not in the list – you can still type it." : "Start typing to search 250 countries.");
      }
      combo(cin, countryItems, countryRow, function (c) { var changed = cin.value !== c.n; cin.value = c.n; setCities(); if (changed && cityIn) { cityIn.value = ""; } if (cityIn) cityIn.focus(); cin.dispatchEvent(new Event("change", { bubbles: true })); }, function (q) { return "No country matches “" + q + "”"; }, { pickFirst: true });
      hint = document.createElement("div"); hint.className = "help geo-hint"; cin.closest(".combo").after(hint);
      cin.addEventListener("input", setCities); cin.addEventListener("blur", function () { var c = find(cin.value); if (c) cin.value = c.n; setCities(); });
      if (cityIn) {
        combo(cityIn, function (q) { var c = find(cin.value); var names = c ? c.ci : []; return rank(names, q, function (x) { return x; }); },
          function (n) { return "<span>" + esc(n) + "</span>"; }, function (n) { cityIn.value = n; cityIn.dispatchEvent(new Event("change", { bubbles: true })); },
          function (q) { var c = find(cin.value); return c ? (q ? "No listed city matches – your text will be used" : "No cities listed") : "Choose a country first, or just type the city"; });
      }
      setCities();
    });

    /* stand-alone city input (no country picker on the form) behaves as plain text */

    /* multi-country chips bound to a textarea (one country per line) */
    document.querySelectorAll("[data-geo-multi]").forEach(function (ta) {
      var box = document.createElement("div"); box.className = "chips";
      var inp = document.createElement("input"); inp.type = "text"; inp.className = "input chips__in"; inp.placeholder = "Add a country…";
      ta.style.display = "none"; ta.parentNode.insertBefore(box, ta);
      var chipList = document.createElement("div"); chipList.className = "chips__list"; box.appendChild(chipList); box.appendChild(inp);
      var sel = ta.value.split(/\n/).map(function (s) { return s.trim(); }).filter(Boolean);
      function sync() {
        ta.value = sel.join("\n");
        chipList.innerHTML = sel.map(function (n, i) { var c = find(n); return '<span class="chip">' + (c ? flag(c.c) + " " : "") + esc(n) + '<button type="button" data-rm="' + i + '" aria-label="Remove ' + esc(n) + '">×</button></span>'; }).join("") || '<span class="muted small">No countries yet – cold email stays blocked for everyone.</span>';
      }
      chipList.addEventListener("click", function (e) { var b = e.target.closest("[data-rm]"); if (b) { sel.splice(+b.dataset.rm, 1); sync(); } });
      combo(inp, function (q) { return rank(countries.filter(function (c) { return sel.indexOf(c.n) < 0; }), q, function (c) { return c.n; }); }, countryRow,
        function (c) { if (sel.indexOf(c.n) < 0) sel.push(c.n); inp.value = ""; sync(); }, function (q) { return "No country matches “" + q + "”"; }, { pickFirst: true, noSubmit: true });
      sync();
    });
  });
})();

