/* SledSpecs: table filtering, sorting and compare. Pages work without this script. */
(function () {
  "use strict";
  var KEY = "sledspecs-compare", MAX = 3;
  var store = {
    get: function () { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; } },
    set: function (v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} }
  };
  var data = null;
  function loadData(cb) {
    if (data) return cb(data);
    fetch("/assets/sleds.json").then(function (r) { return r.json(); }).then(function (d) { data = d; cb(d); }).catch(function () { cb([]); });
  }

  /* ---------- filter + sort ---------- */
  document.querySelectorAll(".tools[data-for]").forEach(function (tools) {
    var table = document.getElementById(tools.getAttribute("data-for"));
    if (!table) return;
    var tbody = table.tBodies[0], rows = Array.prototype.slice.call(tbody.rows);
    var sheet = table.closest(".sheet"), empty = sheet && sheet.querySelector(".empty");
    var count = table.querySelector("[data-count]");
    var q = tools.querySelector('[data-filter="q"]'), b = tools.querySelector('[data-filter="brand"]'),
        t = tools.querySelector('[data-filter="type"]'), sort = tools.querySelector("[data-sort]");
    var params = new URLSearchParams(location.search);
    var hero = document.getElementById("q");
    /* "Ski-Doo", "skidoo" and "ski doo" should all match, same for E-TEC/etec, X-RS/xrs */
    function norm(v) { return (v || "").toLowerCase().replace(/[-'’.\/]/g, ""); }
    rows.forEach(function (r) { r._s = norm(r.dataset.search); });
    function goToList() {
      var cat = document.getElementById("catalogue") || table;
      cat.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    }
    var startQ = params.get("q");
    if (startQ) { if (q) q.value = startQ; if (hero) hero.value = startQ; }

    function apply() {
      var words = (q && q.value.trim().split(/\s+/).map(norm).filter(Boolean)) || [];
      var shown = 0;
      rows.forEach(function (r) {
        var ok = (!b || !b.value || r.dataset.brand === b.value) && (!t || !t.value || r.dataset.type === t.value) &&
          words.every(function (w) { return r._s.indexOf(w) > -1; });
        r.hidden = !ok; if (ok) shown++;
      });
      if (sort) {
        var k = sort.value, asc = (k === "weight" || k === "lbhp");
        var sorted = rows.slice().sort(function (x, y) {
          var a = +x.dataset[k] || (asc ? 1e9 : -1), c = +y.dataset[k] || (asc ? 1e9 : -1);
          return asc ? a - c : c - a;
        });
        sorted.forEach(function (r) { tbody.appendChild(r); });
      }
      if (count) count.textContent = shown === rows.length ? rows.length + " sleds" : "Showing " + shown + " of " + rows.length + " sleds";
      table.hidden = shown === 0;
      if (empty) {
        empty.hidden = shown !== 0;
        if (shown === 0 && q && q.value.trim()) empty.textContent = "Nothing matches “" + q.value.trim() + "”. Try fewer words, a model name like Summit or RMK, an engine size like 850, or a belt number.";
      }
    }
    [q, b, t, sort].forEach(function (el) { if (el) el.addEventListener(el.tagName === "INPUT" ? "input" : "change", apply); });
    if (hero && q) {
      hero.addEventListener("input", function () { q.value = hero.value; apply(); });
      hero.form.addEventListener("submit", function (e) {
        e.preventDefault();
        if (!hero.value.trim()) { hero.focus(); return; }
        q.value = hero.value; apply();
        try { history.replaceState(null, "", "?q=" + encodeURIComponent(hero.value.trim()) + "#catalogue"); } catch (x) {}
        goToList();
      });
    }
    apply();
    if (startQ) goToList();
  });

  /* ---------- compare tray ---------- */
  var tray = document.getElementById("tray");
  function syncButtons() {
    var set = store.get();
    document.querySelectorAll("[data-compare]").forEach(function (btn) {
      var on = set.indexOf(btn.getAttribute("data-compare")) > -1;
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.textContent = btn.classList.contains("wide") ? (on ? "Added to compare" : "Add to compare") : (on ? "Added" : "Compare");
    });
    if (!tray || location.pathname.indexOf("/compare") === 0) return;
    if (!set.length) { tray.hidden = true; return; }
    loadData(function (d) {
      var names = set.map(function (id) { var s = d.filter(function (x) { return x.key === id; })[0]; return s ? s.full : id; });
      document.getElementById("trayNames").textContent = names.join(" vs ") + (set.length < 2 ? ". Pick one more." : "");
      var go = document.getElementById("trayGo");
      go.href = "/compare/?s=" + set.join(",");
      go.setAttribute("aria-disabled", set.length < 2 ? "true" : "false");
      tray.hidden = false;
    });
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-compare]");
    if (!btn) return;
    var id = btn.getAttribute("data-compare"), set = store.get(), i = set.indexOf(id);
    if (i > -1) set.splice(i, 1); else { if (set.length >= MAX) set.shift(); set.push(id); }
    store.set(set); syncButtons();
  });
  var clear = document.getElementById("trayClear");
  if (clear) clear.addEventListener("click", function () { store.set([]); syncButtons(); });
  syncButtons();

  /* ---------- compare page ---------- */
  var out = document.getElementById("cmpOut");
  if (out) {
    var p = new URLSearchParams(location.search).get("s");
    var ids = p ? p.split(",").slice(0, MAX) : store.get();
    if (p) store.set(ids);
    loadData(function (d) {
      var ms = ids.map(function (id) { return d.filter(function (x) { return x.key === id; })[0]; }).filter(Boolean);
      if (ms.length < 2) {
        out.innerHTML = '<p>You have ' + ms.length + ' sled' + (ms.length === 1 ? "" : "s") + ' picked. <a href="/#catalogue">Go to the catalogue</a> and tap Compare on two or three sleds.</p>';
        return;
      }
      document.getElementById("cmpLede").textContent = "Highlighted cells mark the strongest figure in each row. A dash means the figure isn't on file.";
      function best(vals, mode) {
        var bi = -1, bv = null;
        vals.forEach(function (v, i) { if (v == null) return; if (bv === null || (mode === "max" ? v > bv : v < bv)) { bv = v; bi = i; } });
        return vals.filter(function (v) { return v === bv; }).length > 1 ? -1 : bi;
      }
      function f(v, u) { return v == null ? "—" : v + (u || ""); }
      var rows = [
        ["Engine", ms.map(function (m) { return m.engine + ", " + m.cc + " cc"; }), -1],
        ["Horsepower", ms.map(function (m) { return m.hp ? m.hp + " hp" : "Not published"; }), best(ms.map(function (m) { return m.hp; }), "max")],
        ["Dry weight", ms.map(function (m) { return f(m.dry_weight_lb, " lb"); }), best(ms.map(function (m) { return m.dry_weight_lb; }), "min")],
        ["Power-to-weight", ms.map(function (m) { return f(m.lb_per_hp, " lb per hp"); }), best(ms.map(function (m) { return m.lb_per_hp; }), "min")],
        ["Track", ms.map(function (m) { return f(m.track); }), best(ms.map(function (m) { return m.track_length_in; }), "max")],
        ["Fuel", ms.map(function (m) { return f(m.fuel_gal, " gal"); }), best(ms.map(function (m) { return m.fuel_gal; }), "max")],
        ["Drive belt", ms.map(function (m) { return f(m.belt_pn); }), -1],
        ["Type", ms.map(function (m) { return m.category; }), -1]
      ];
      var esc = function (s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
      var head = ms.map(function (m) { return '<th scope="col"><a href="' + m.url + '">' + esc(m.full) + '</a><br><button class="btn small rm" type="button" data-compare="' + m.key + '">Remove</button></th>'; }).join("");
      var body = rows.map(function (r) {
        return "<tr><th scope=row>" + r[0] + "</th>" + r[1].map(function (v, i) { return '<td' + (i === r[2] ? ' class="best"' : "") + ">" + esc(v) + "</td>"; }).join("") + "</tr>";
      }).join("");
      out.innerHTML = '<div class="sheet cmp-scroll"><table class="cmp"><thead><tr><td></td>' + head + "</tr></thead><tbody>" + body + "</tbody></table></div>";
      out.querySelectorAll(".rm").forEach(function (b) { b.addEventListener("click", function () { setTimeout(function () { location.href = "/compare/?s=" + store.get().join(","); }, 0); }); });
    });
  }
})();
