/* Dashboard → Media library: grid/list view, multi-select + bulk actions, details dialog (name, link, download, usage, delete). */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var lib = $("#mlib"); if (!lib) return;
  var esc = (window.Dash && window.Dash.esc) || function (s) { return String(s == null ? "" : s); };
  var store = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };

  /* ---- view toggle (remembered) ---- */
  function setView(v) { lib.dataset.view = v; $$("[data-mview]").forEach(function (b) { b.classList.toggle("on", b.dataset.mview === v); }); store.set("aub.mediaview", v); }
  $$("[data-mview]").forEach(function (b) { b.addEventListener("click", function () { setView(b.dataset.mview); }); });
  var saved = store.get("aub.mediaview"); setView(saved === "list" ? "list" : "grid");

  /* ---- selection + bulk bar ---- */
  var bar = $("#mbulk"), ids = $("#mbulk-ids"), nEl = $("#mbulk-n"), all = $("#mcheck-all");
  function sync() {
    var on = $$(".js-mcheck:checked"); if (!bar) return;
    bar.hidden = on.length === 0; nEl.textContent = on.length;
    ids.textContent = ""; on.forEach(function (c) { var i = document.createElement("input"); i.type = "hidden"; i.name = "ids"; i.value = c.value; ids.appendChild(i); });
    $$(".mrow").forEach(function (r) { var c = $(".js-mcheck", r); r.classList.toggle("sel", !!(c && c.checked)); });
    if (all) { var boxes = $$(".js-mcheck"); all.checked = boxes.length > 0 && on.length === boxes.length; all.indeterminate = on.length > 0 && on.length < boxes.length; }
  }
  lib.addEventListener("change", function (e) { if (e.target.classList.contains("js-mcheck")) sync(); });
  if (all) all.addEventListener("change", function () { $$(".js-mcheck").forEach(function (c) { c.checked = all.checked; }); sync(); });
  var clr = $("#mbulk-clear"); if (clr) clr.addEventListener("click", function () { $$(".js-mcheck").forEach(function (c) { c.checked = false; }); sync(); });

  /* ---- details dialog ---- */
  var dlg = $("#mdetail"); if (!dlg) return;
  var cur = null;
  function row(el) { return el.closest(".mrow"); }
  function fill(r) {
    cur = r; var d = r.dataset, img = d.kind === "image";
    $("#md-title").textContent = d.name;
    var pv = $("#md-preview"); pv.textContent = "";
    if (img) { var im = document.createElement("img"); im.src = d.url; im.alt = d.alt || ""; pv.appendChild(im); }
    else { pv.innerHTML = '<div class="md__doc"><b></b><span>Document</span></div>'; $("b", pv).textContent = (d.mime || "FILE").split("/").pop().toUpperCase().slice(0, 12); }
    $("#md-orig").textContent = d.orig || d.name; $("#md-type").textContent = d.mime || "—"; $("#md-size").textContent = d.size || "—";
    $("#md-dim").textContent = d.dim || "—"; $("#md-dim").style.display = $("#md-dim-l").style.display = d.dim ? "" : "none"; $("#md-date").textContent = d.date + (d.by ? " · " + d.by : "");
    $("#md-url").value = d.url; $("#md-full").value = window.location.origin + d.url;
    $("#md-download").href = d.download; $("#md-open").href = d.url;
    var f = $("#md-form"); if (f) { f.action = d.edit; $("#md-f-title").value = d.title; $("#md-f-alt").value = d.alt; $("#md-f-cap").value = d.caption; }
    var del = $("#md-del"); if (del) { del.action = d.delete; var fc = $("#md-force"); fc.hidden = true; $("input", fc).checked = false; }
    var u = $("#md-usage"); u.className = "md__usage"; u.innerHTML = '<span class="muted small">Checking where this file is used…</span>';
    if (window.Dash && window.Dash.api) window.Dash.api(d.usage).then(function (res) {
      if (cur !== r) return; var list = res.usage || [];
      if (!list.length) { u.className = "md__usage md__usage--free"; u.innerHTML = "<b>Not used anywhere</b><span>Safe to delete.</span>"; return; }
      u.className = "md__usage md__usage--used";
      u.innerHTML = "<b>Used in " + list.length + " place" + (list.length > 1 ? "s" : "") + "</b><ul>" + list.slice(0, 8).map(function (x) { return "<li>" + esc(x.model) + " · " + esc(x.object) + " <em>(" + esc(x.field) + ")</em></li>"; }).join("") + "</ul>";
      if (del) $("#md-force").hidden = false;
    }).catch(function () { u.innerHTML = '<span class="muted small">Couldn\'t check usage. Deleting is still protected on the server.</span>'; });
  }
  lib.addEventListener("click", function (e) { var b = e.target.closest("[data-details]"); if (!b) return; var r = row(b); if (r) { fill(r); window.Dash.openModal("mdetail"); } });
  function copy(text) { (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { window.Dash.toast("Copied to clipboard", "success"); }).catch(function () { window.Dash.toast("Couldn't copy — select and copy manually.", "warning"); }); }
  $("#md-copy").addEventListener("click", function () { copy($("#md-url").value); });
  $("#md-copy-full").addEventListener("click", function () { copy($("#md-full").value); });
  ["#md-url", "#md-full"].forEach(function (s) { $(s).addEventListener("focus", function () { this.select(); }); });
})();
