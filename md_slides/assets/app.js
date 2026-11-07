/* md-slides: навигация и интерфейс презентации. Без зависимостей. */
(function () {
  "use strict";

  const config = JSON.parse(document.getElementById("md-slides-config").textContent);
  const body = document.body;
  const stage = document.querySelector(".stage");
  const viewport = document.querySelector(".viewport");
  const slides = Array.from(stage.querySelectorAll(":scope > .slide"));
  const progress = document.querySelector(".progress > span");
  const counter = document.querySelector(".counter");
  const overlays = {
    help: document.getElementById("help"),
    goto: document.getElementById("goto"),
    overview: document.getElementById("overview"),
  };
  const gotoInput = document.getElementById("goto-input");
  const presNotes = document.querySelector(".pres-notes");
  const presNext = document.querySelector(".pres-next");
  const presTimer = document.getElementById("pres-timer");
  const presClock = document.getElementById("pres-clock");

  const W = config.width, H = config.height;
  const total = slides.length;
  let current = 0;
  let timerStart = null;

  // ---------------------------------------------------------------- состояние
  const fragmentsOf = (i) => Array.from(slides[i].querySelectorAll(".fragment"));

  function setFragments(i, count) {
    fragmentsOf(i).forEach((el, k) => el.classList.toggle("visible", k < count));
  }
  function visibleFragments(i) {
    return fragmentsOf(i).filter((el) => el.classList.contains("visible")).length;
  }

  function show(index, { fragments = "none", updateHash = true } = {}) {
    if (!total) return;
    index = Math.max(0, Math.min(total - 1, index));
    slides[current].classList.remove("active");
    current = index;
    const slide = slides[current];
    slide.classList.add("active");
    setFragments(current, fragments === "all" ? Infinity : 0);
    progress.style.width = (total > 1 ? (current / (total - 1)) * 100 : 100) + "%";
    counter.textContent = current + 1 + " / " + total;
    document.title = (slide.dataset.title ? slide.dataset.title + " — " : "") + config.title;
    if (updateHash) {
      const hash = "#" + (current + 1);
      if (location.hash !== hash) history.replaceState(null, "", hash);
    }
    updatePresenter();
  }

  function next() {
    const frags = fragmentsOf(current);
    const shown = visibleFragments(current);
    if (shown < frags.length) {
      setFragments(current, shown + 1);
      return;
    }
    if (current < total - 1) show(current + 1);
  }

  function prev() {
    const shown = visibleFragments(current);
    if (shown > 0) {
      setFragments(current, shown - 1);
      return;
    }
    if (current > 0) show(current - 1, { fragments: "all" });
  }

  // ----------------------------------------------------------- масштабирование
  function fit() {
    const rect = viewport.getBoundingClientRect();
    const scale = Math.min(rect.width / W, rect.height / H) * 0.96;
    stage.style.setProperty("--scale", String(Math.max(scale, 0.05)));
    if (body.classList.contains("presenter")) fitPreview();
  }

  // ---------------------------------------------------------------- оверлеи
  function closeOverlays() {
    Object.values(overlays).forEach((o) => o.classList.remove("open"));
    // иначе фокус остаётся в скрытом поле ввода и «съедает» нажатия клавиш
    const focused = document.activeElement;
    if (focused && focused.closest && focused.closest(".overlay")) focused.blur();
    gotoInput.removeAttribute("aria-invalid");
  }
  function isOpen(name) {
    return overlays[name].classList.contains("open");
  }
  function anyOpen() {
    return Object.keys(overlays).some(isOpen);
  }

  function openGoto() {
    closeOverlays();
    overlays.goto.classList.add("open");
    gotoInput.value = "";
    gotoInput.placeholder = "1–" + total + " или часть заголовка";
    gotoInput.focus();
  }

  function resolveGoto(value) {
    value = value.trim();
    if (!value) return null;
    if (/^\d+$/.test(value)) return parseInt(value, 10) - 1;
    const needle = value.toLowerCase();
    const found = slides.findIndex((s) => (s.dataset.title || "").toLowerCase().includes(needle));
    return found >= 0 ? found : null;
  }

  function thumbnail(index) {
    const inner = document.createElement("div");
    inner.className = "thumb-inner";
    const clone = slides[index].cloneNode(true);
    clone.classList.add("active");
    clone.removeAttribute("id");
    inner.appendChild(clone);
    return inner;
  }

  function openOverview() {
    closeOverlays();
    const grid = overlays.overview.querySelector(".overview-grid");
    grid.textContent = "";
    slides.forEach((_, i) => {
      const t = document.createElement("div");
      t.className = "thumb" + (i === current ? " current" : "");
      t.tabIndex = 0;
      t.dataset.index = String(i);
      t.title = slides[i].dataset.title || "";
      const inner = thumbnail(i);
      inner.style.transform = "scale(" + 256 / W + ")";
      t.appendChild(inner);
      const num = document.createElement("span");
      num.className = "thumb-num";
      num.textContent = String(i + 1);
      t.appendChild(num);
      grid.appendChild(t);
    });
    overlays.overview.classList.add("open");
    const cur = grid.querySelector(".thumb.current");
    if (cur) {
      cur.focus();
      if (cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
    }
  }

  overlays.overview.addEventListener("click", (e) => {
    const t = e.target.closest(".thumb");
    if (t) {
      closeOverlays();
      show(parseInt(t.dataset.index, 10));
    } else if (e.target === overlays.overview) closeOverlays();
  });
  overlays.help.addEventListener("click", (e) => {
    if (e.target === overlays.help) closeOverlays();
  });

  gotoInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const idx = resolveGoto(gotoInput.value);
      if (idx !== null) {
        closeOverlays();
        show(idx);
      } else {
        gotoInput.select();
        gotoInput.setAttribute("aria-invalid", "true");
      }
      e.preventDefault();
    } else if (e.key === "Escape") {
      closeOverlays();
    }
    e.stopPropagation();
  });

  // --------------------------------------------------------- режим докладчика
  function fmt(ms) {
    const s = Math.floor(ms / 1000);
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return (h ? h + ":" : "") + pad(m) + ":" + pad(sec);
  }

  function tick() {
    if (!body.classList.contains("presenter")) return;
    presTimer.textContent = fmt(Date.now() - timerStart);
    const now = new Date();
    presClock.textContent = String(now.getHours()).padStart(2, "0") + ":" + String(now.getMinutes()).padStart(2, "0");
  }

  function fitPreview() {
    const inner = presNext.querySelector(".thumb-inner");
    if (inner) inner.style.transform = "scale(" + presNext.clientWidth / W + ")";
  }

  function updatePresenter() {
    if (!body.classList.contains("presenter")) return;
    const notes = slides[current].querySelector(".notes");
    presNotes.innerHTML = notes ? notes.innerHTML : "";
    presNext.textContent = "";
    if (current + 1 < total) {
      presNext.appendChild(thumbnail(current + 1));
      fitPreview();
    } else {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "Конец презентации";
      presNext.appendChild(empty);
    }
  }

  function togglePresenter() {
    const on = body.classList.toggle("presenter");
    if (on && timerStart === null) timerStart = Date.now();
    fit();
    updatePresenter();
    tick();
  }

  setInterval(tick, 500);

  // ---------------------------------------------------------------- темы
  // ключ учитывает тему сборки: пересборка с другой темой не «перебивается» старым выбором
  const themeKey = "md-slides-theme:" + config.title + ":" + body.dataset.theme;

  function cycleTheme() {
    const themes = config.themes;
    const idx = themes.indexOf(body.dataset.theme);
    body.dataset.theme = themes[(idx + 1) % themes.length];
    try { localStorage.setItem(themeKey, body.dataset.theme); } catch (e) { /* нет хранилища */ }
  }

  try {
    const saved = localStorage.getItem(themeKey);
    if (saved && config.themes.includes(saved)) body.dataset.theme = saved;
  } catch (e) { /* нет хранилища */ }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(() => {});
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }

  // ---------------------------------------------------------------- клавиатура
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const key = e.key;

    if (anyOpen()) {
      if (key === "Escape" || (key === "?" && isOpen("help")) || ((key === "o" || key === "O") && isOpen("overview"))) {
        closeOverlays();
        e.preventDefault();
      } else if (isOpen("overview") && (key === "Enter" || key === " ")) {
        const t = document.activeElement && document.activeElement.closest(".thumb");
        if (t) { closeOverlays(); show(parseInt(t.dataset.index, 10)); e.preventDefault(); }
      } else if (isOpen("overview") && key.startsWith("Arrow")) {
        const thumbs = Array.from(overlays.overview.querySelectorAll(".thumb"));
        const pos = thumbs.indexOf(document.activeElement);
        const cols = Math.max(1, Math.round(overlays.overview.querySelector(".overview-grid").clientWidth / 274));
        const delta = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols }[key];
        const target = thumbs[Math.max(0, Math.min(thumbs.length - 1, (pos < 0 ? current : pos) + delta))];
        if (target) target.focus();
        e.preventDefault();
      }
      return;
    }

    switch (key) {
      case "ArrowRight": case "ArrowDown": case "PageDown": case " ": case "Enter": case "l": case "j":
        next(); break;
      case "ArrowLeft": case "ArrowUp": case "PageUp": case "Backspace": case "h": case "k":
        prev(); break;
      case "Home": show(0); break;
      case "End": show(total - 1, { fragments: "all" }); break;
      case "f": case "F": toggleFullscreen(); break;
      case "p": case "P": togglePresenter(); break;
      case "t": case "T": cycleTheme(); break;
      case "g": case "G": openGoto(); break;
      case "o": case "O": openOverview(); break;
      case "b": case "B": case ".": body.classList.toggle("blackout"); break;
      case "r": case "R": timerStart = Date.now(); tick(); break;
      case "?": closeOverlays(); overlays.help.classList.add("open"); break;
      default: return;
    }
    e.preventDefault();
  });

  // ------------------------------------------------------- мышь и свайпы
  let touchX = null, touchY = null;
  viewport.addEventListener("touchstart", (e) => {
    touchX = e.touches[0].clientX;
    touchY = e.touches[0].clientY;
  }, { passive: true });
  viewport.addEventListener("touchend", (e) => {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    const dy = e.changedTouches[0].clientY - touchY;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) (dx < 0 ? next : prev)();
    touchX = touchY = null;
  });
  viewport.addEventListener("click", (e) => {
    if (e.target.closest("a, input, pre, button")) return;
    const rect = viewport.getBoundingClientRect();
    (e.clientX - rect.left < rect.width / 3 ? prev : next)();
  });

  window.addEventListener("resize", fit);
  window.addEventListener("hashchange", () => {
    const n = parseInt(location.hash.slice(1), 10);
    if (!isNaN(n) && n - 1 !== current) show(n - 1, { updateHash: false });
  });

  // ------------------------------------------------------- живая перезагрузка
  if (config.live) {
    let version = null;
    setInterval(() => {
      fetch("/__version", { cache: "no-store" })
        .then((r) => r.text())
        .then((v) => {
          if (version !== null && v !== version) location.reload();
          version = v;
        })
        .catch(() => {});
    }, 1000);
  }

  // ---------------------------------------------------------------- старт
  const start = parseInt(location.hash.slice(1), 10);
  current = 0;
  fit();
  show(isNaN(start) ? 0 : start - 1);

  // API для отладки и тестов.
  window.mdSlides = {
    next, prev, show, total,
    get current() { return current; },
    get visibleFragments() { return visibleFragments(current); },
  };
})();
