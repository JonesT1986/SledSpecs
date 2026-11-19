/* SledSpecs search: forgiving matching, a drop-down of the 20 closest sleds, and the /search/ results page.
   Handles typos (sumit, artic, polars), joined or split words (skidoo, ski doo, summit850), and stray words (specs, belt). */
(function () {
  "use strict";
  var LIMIT = 20;
  var STOP = { sled: 1, sleds: 1, snowmobile: 1, snowmobiles: 1, spec: 1, specs: 1, specification: 1, specifications: 1,
    the: 1, for: 1, of: 1, and: 1, a: 1, an: 1, model: 1, models: 1, year: 1, belt: 1, belts: 1, drive: 1, hp: 1,
    horsepower: 1, weight: 1, dry: 1, track: 1, size: 1, engine: 1, in: 1, inch: 1, cc: 1, new: 1, used: 1, my: 1 };
  var ALIAS = { doo: "skidoo", skidoos: "skidoo", bombardier: "skidoo", brp: "skidoo", ski: "skidoo",
    yammy: "yamaha", yammie: "yamaha", yammi: "yamaha", yammer: "yamaha", ac: "arctic",
    arcticcat: "arctic", polly: "polaris" };

  function norm(s) { return (s || "").toLowerCase().replace(/[-'’.\/,()×"]/g, function (c) { return c === "×" || c === "," || c === "(" || c === ")" || c === '"' ? " " : ""; }); }
  function splitMixed(t) { var m = t.match(/[a-z]+|\d+/g); return m && m.length > 1 ? m : null; }
  function tokens(s) {
    var out = [];
    norm(s).split(/\s+/).forEach(function (t) {
      if (!t) return;
      out.push(t);
      var m = splitMixed(t); if (m) m.forEach(function (x) { out.push(x); });
    });
    return out;
  }

  /* ---------- index ---------- */
  var idx = null, vocab = null, waiting = [];
  function load(cb) {
    if (idx) return cb();
    waiting.push(cb);
    if (waiting.length > 1) return;
    fetch("/assets/search.json").then(function (r) { return r.json(); }).then(function (rows) {
      var seen = {};
      idx = rows.map(function (r) {
        /* r = [full, url, category, engine, track, belt, year] */
        var toks = {}, list = tokens(r[0] + " " + r[2] + " " + r[3] + " " + r[4] + " " + (r[5] || ""));
        list.forEach(function (t) { toks[t] = 1; seen[t] = (seen[t] || 0) + 1; });
        if (toks.skidoo) { toks.ski = 1; toks.doo = 1; }
        return { full: r[0], url: r[1], cat: r[2], eng: r[3], trk: r[4], belt: r[5], year: r[6], toks: Object.keys(toks) };
      });
      vocab = Object.keys(seen);
      var w = waiting; waiting = []; w.forEach(function (f) { f(); });
    }).catch(function () { idx = []; vocab = []; var w = waiting; waiting = []; w.forEach(function (f) { f(); }); });
  }

  function dist(a, c, max) {
    if (Math.abs(a.length - c.length) > max) return max + 1;
    var pp = null, prev = [], cur, i, j;
    for (j = 0; j <= c.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      cur = [i]; var low = i;
      for (j = 1; j <= c.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === c[j - 1] ? 0 : 1));
        if (pp && i > 1 && j > 1 && a[i - 1] === c[j - 2] && a[i - 2] === c[j - 1]) cur[j] = Math.min(cur[j], pp[j - 2] + 1);
        if (cur[j] < low) low = cur[j];
      }
      if (low > max) return max + 1;
      pp = prev; prev = cur;
    }
    return prev[c.length];
  }

  /* score every catalogue word against one typed word */
  function wordScores(q) {
    var sc = {}, any = false, isNum = /^\d+$/.test(q), max = q.length >= 6 ? 2 : 1;
    vocab.forEach(function (v) {
      var s = 0;
      if (v === q) s = 3;
      else if (isNum) { if (q.length >= 3 && v.indexOf(q) === 0) s = 2; }          /* numbers are never guessed */
      else if (q.length === 1) s = 0;
      else if (v.indexOf(q) === 0) s = 2.5;
      else if (q.length >= 3 && v.indexOf(q) > -1) s = 2;
      else if (q.length >= 4 && !/\d/.test(v)) {
        var d = dist(q, v, max);
        if (d > max && v.length > q.length) d = dist(q, v.slice(0, q.length), max) + 0.5; /* still typing */
        if (d <= max) s = d <= 1 ? 1.5 : 1;
      }
      if (s) { sc[v] = s; any = true; }
    });
    return any ? sc : null;
  }

  function search(text) {
    var raw = [];
    tokens(text).forEach(function (t, i, all) {
      if (STOP[t]) return;
      if (ALIAS[t]) t = ALIAS[t];
      if (raw.indexOf(t) === -1) raw.push(t);
    });
    /* drop the pieces of a split word when the whole word is present ("summit850" -> summit, 850) */
    var words = raw.filter(function (t) { var m = splitMixed(t); return !m; });
    raw.forEach(function (t) { var m = splitMixed(t); if (m) m.forEach(function (x) { if (words.indexOf(x) === -1) words.push(x); }); });
    var used = [], ignored = [], maps = [];
    words.forEach(function (w) { var m = wordScores(w); if (m) { used.push(w); maps.push(m); } else ignored.push(w); });
    if (!used.length) return { hits: [], used: used, ignored: ignored, partial: false, fixed: null };

    function rank(minMatch) {
      var out = [];
      idx.forEach(function (s) {
        var total = 0, n = 0;
        maps.forEach(function (m) {
          var best = 0;
          for (var i = 0; i < s.toks.length; i++) { var v = m[s.toks[i]]; if (v > best) best = v; }
          if (best) { total += best; n++; }
        });
        if (n >= minMatch) out.push({ s: s, score: total + n * 2 + (s.year || 0) / 10000 });
      });
      out.sort(function (a, b) { return b.score - a.score; });
      return out;
    }
    var hits = rank(maps.length), partial = false;
    if (!hits.length && maps.length > 1) { hits = rank(Math.ceil(maps.length / 2)); partial = hits.length > 0; }

    /* report what a typo was read as, when no word in the catalogue was typed exactly */
    var fixed = [];
    used.forEach(function (w, i) {
      var m = maps[i], best = null, bs = 0;
      Object.keys(m).forEach(function (v) { if (m[v] > bs) { bs = m[v]; best = v; } });
      fixed.push(bs < 2 && best ? best : w);
    });
    fixed = fixed.filter(function (w, i) { return fixed.indexOf(w) === i; });
    var fixedText = fixed.join(" ") !== used.join(" ") ? fixed.join(" ") : null;
    return { hits: hits.map(function (h) { return h.s; }), used: used, ignored: ignored, partial: partial, fixed: fixedText };
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function detail(s) { return [s.cat, s.eng, s.trk, s.belt ? "belt " + s.belt : ""].filter(Boolean).map(esc).join(", "); }

  /* ---------- drop-down on every search box ---------- */
  var n = 0;
  document.querySelectorAll("form.find, form.msearch, form.srform").forEach(function (form) {
    var input = form.querySelector("input[name=q]");
    if (!input) return;
    var id = "sugg" + (n++);
    var box = document.createElement("div");
    box.className = "sugg"; box.id = id; box.setAttribute("role", "listbox"); box.hidden = true;
    form.classList.add("has-sugg");
    form.appendChild(box);
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", id); input.setAttribute("aria-expanded", "false");
    var items = [], active = -1, timer = null;

    function close() { box.hidden = true; input.setAttribute("aria-expanded", "false"); active = -1; input.removeAttribute("aria-activedescendant"); }
    function mark(i) {
      items.forEach(function (el, k) { el.classList.toggle("on", k === i); el.setAttribute("aria-selected", k === i ? "true" : "false"); });
      active = i;
      if (i > -1) { input.setAttribute("aria-activedescendant", items[i].id); items[i].scrollIntoView({ block: "nearest" }); }
      else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      var text = input.value.trim();
      if (!text) { box.innerHTML = '<p class="sugg-note">Type a model, engine size, track length or belt number. Spelling doesn’t have to be perfect.</p>'; items = []; box.hidden = false; input.setAttribute("aria-expanded", "true"); return; }
      load(function () {
        if (input.value.trim() !== text) return;
        var r = search(text), top = r.hits.slice(0, LIMIT), html = "";
        if (r.fixed && top.length) html += '<p class="sugg-note">Showing results for “' + esc(r.fixed) + '”</p>';
        else if (r.partial) html += '<p class="sugg-note">No sled matches every word. Closest matches:</p>';
        if (!top.length) html += '<p class="sugg-note">No sled matches “' + esc(text) + '”. Try a model name like Summit or RMK, an engine size like 850, or a belt number.</p>';
        html += top.map(function (s, i) {
          return '<a class="sugg-item" role="option" id="' + id + "-" + i + '" href="' + esc(s.url) + '"><b>' + esc(s.full) + "</b><span>" + detail(s) + "</span></a>";
        }).join("");
        if (r.hits.length > LIMIT) html += '<a class="sugg-all" href="/search/?q=' + encodeURIComponent(text) + '">See all ' + r.hits.length + " results</a>";
        box.innerHTML = html;
        items = Array.prototype.slice.call(box.querySelectorAll(".sugg-item"));
        active = -1;
        box.hidden = false; input.setAttribute("aria-expanded", "true");
      });
    }
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(render, 90); });
    input.addEventListener("focus", function () { load(function () {}); render(); });
    input.addEventListener("keydown", function (e) {
      if (box.hidden && (e.key === "ArrowDown" || e.key === "ArrowUp")) { render(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) mark(Math.min(active + 1, items.length - 1)); }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) mark(Math.max(active - 1, -1)); }
      else if (e.key === "Escape") { close(); }
      else if (e.key === "Enter" && active > -1 && items[active]) { e.preventDefault(); location.href = items[active].getAttribute("href"); }
    });
    form.addEventListener("submit", function (e) {
      if (!input.value.trim()) { e.preventDefault(); input.focus(); render(); }
      /* otherwise the browser goes to /search/?q=... */
    });
    document.addEventListener("click", function (e) { if (!form.contains(e.target)) close(); });
  });

  /* ---------- /search/ results page ---------- */
  var out = document.getElementById("srOut");
  if (out) {
    var q = new URLSearchParams(location.search).get("q") || "";
    var head = document.getElementById("srHead");
    var field = document.getElementById("srq");
    if (field) field.value = q;
    if (!q.trim()) { head.textContent = "Search snowmobile specs"; out.innerHTML = '<p class="lede">Type a model, engine size, track length or belt number above.</p>'; return; }
    document.title = q + " snowmobile specs | SledSpecs";
    load(function () {
      var r = search(q), hits = r.hits.slice(0, 300), note = "";
      head.textContent = hits.length ? (r.hits.length === 1 ? "1 sled" : r.hits.length + " sleds") + " for “" + q + "”" : "Nothing found for “" + q + "”";
      if (r.fixed && hits.length) note = "Showing results for “" + esc(r.fixed) + "”. ";
      if (r.partial) note += "No sled matches every word, so these match most of them. ";
      if (r.ignored.length) note += "Not found anywhere in the catalogue: " + r.ignored.map(function (w) { return "“" + esc(w) + "”"; }).join(", ") + ".";
      if (!hits.length) {
        out.innerHTML = (note ? '<p class="srnote">' + note + "</p>" : "") +
          '<p class="lede">Try fewer words, a model name like Summit, RMK or Riot, an engine size like 850, or a belt number. Or <a href="/#catalogue">browse every sled</a>.</p>';
        return;
      }
      out.innerHTML = (note ? '<p class="srnote">' + note + "</p>" : "") + '<ol class="srlist">' + hits.map(function (s) {
        return '<li><a href="' + esc(s.url) + '">' + esc(s.full) + "</a><span>" + detail(s) + "</span></li>";
      }).join("") + "</ol>" + (r.hits.length > hits.length ? '<p class="srnote">Showing the closest ' + hits.length + ". Add a year or engine size to narrow it down.</p>" : "");
    });
  }
})();
