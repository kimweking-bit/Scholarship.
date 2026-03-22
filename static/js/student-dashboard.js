(function () {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const storageKeys = {
    theme: "student-dashboard-theme",
    saved: "studentDashboard.savedScholarships.v2",
    legacySaved: "savedScholarships.v1",
  };

  const dom = {
    root: document.documentElement,
    themeButtons: $$("[data-theme-toggle]"),
    sidebarOpen: $("#sidebarOpen"),
    sidebarOverlay: $("#sidebarOverlay"),
    searchInput: $("#scholarshipSearch"),
    countryFilter: $("#countryFilter"),
    degreeFilter: $("#degreeFilter"),
    fundingFilter: $("#fundingFilter"),
    clearFilters: $("#clearFilters"),
    catalogEmpty: $("#catalogEmpty"),
    catalogResultsCount: $("#catalogResultsCount"),
    savedList: $("#savedList"),
    savedEmpty: $("#savedEmpty"),
    savedCount: $("#savedCount"),
    heroSavedCount: $("#heroSavedCount"),
    clearSaved: $("#clearSaved"),
    savedSkeleton: $("#savedSkeleton"),
    toastStack: $("#toastStack"),
  };

  function normalize(value) {
    return String(value || "").toLowerCase().trim();
  }

  function formatNumber(value) {
    return new Intl.NumberFormat().format(Number(value || 0));
  }

  function setTheme(theme) {
    const nextTheme = theme === "dark" ? "dark" : "light";
    dom.root.dataset.theme = nextTheme;
    try {
      localStorage.setItem(storageKeys.theme, nextTheme);
    } catch (e) {}
    updateThemeButton();
  }

  function updateThemeButton() {
    const isDark = dom.root.dataset.theme === "dark";
    dom.themeButtons.forEach((button) => {
      const icon = $("i", button);
      const label = $("span", button);
      if (icon) icon.className = `bi ${isDark ? "bi-sun-fill" : "bi-moon-stars"}`;
      if (label) label.textContent = isDark ? "Light mode" : "Dark mode";
      button.setAttribute("aria-pressed", String(isDark));
    });
  }

  function initTheme() {
    const currentTheme = dom.root.dataset.theme || "light";
    setTheme(currentTheme);
    dom.themeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setTheme(dom.root.dataset.theme === "dark" ? "light" : "dark");
      });
    });
  }

  function openSidebar() {
    if (window.innerWidth > 991) return;
    document.body.classList.add("sidebar-open");
    if (dom.sidebarOverlay) dom.sidebarOverlay.hidden = false;
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    if (dom.sidebarOverlay) dom.sidebarOverlay.hidden = true;
  }

  function initSidebar() {
    dom.sidebarOpen?.addEventListener("click", openSidebar);
    dom.sidebarOverlay?.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeSidebar();
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 991) closeSidebar();
    });
  }

  function initNav() {
    const routeLinks = $$("[data-route-link]");
    const sectionLinks = $$("[data-section-link]");

    routeLinks.forEach((link) => {
      const href = link.getAttribute("href");
      if (!href) return;
      try {
        const url = new URL(href, window.location.origin);
        link.classList.toggle("is-active", url.pathname === window.location.pathname);
      } catch (e) {}
      link.addEventListener("click", closeSidebar);
    });

    if (!sectionLinks.length) return;

    const activateSection = (id) => {
      sectionLinks.forEach((link) => {
        link.classList.toggle("is-active", link.dataset.sectionLink === id);
      });
    };

    sectionLinks.forEach((link) => {
      link.addEventListener("click", () => {
        activateSection(link.dataset.sectionLink);
        closeSidebar();
      });
    });

    activateSection(window.location.hash ? window.location.hash.slice(1) : "overview");

    if (!("IntersectionObserver" in window)) return;

    const observedTargets = sectionLinks
      .map((link) => ({ link, target: document.getElementById(link.dataset.sectionLink) }))
      .filter((entry) => entry.target);

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) activateSection(visible.target.id);
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: [0.2, 0.45, 0.75] }
    );

    observedTargets.forEach(({ target }) => observer.observe(target));
  }

  function animateCounter(element) {
    const endValue = Number(element.dataset.end || 0);
    const duration = 1200;
    const startTime = performance.now();

    function step(now) {
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = formatNumber(Math.round(endValue * eased));
      if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
  }

  function initCounters() {
    $$(".counter-value").forEach(animateCounter);
  }

  function initFilters() {
    const cards = $$("#discoverGrid [data-catalog-card]");
    if (!cards.length) return;

    const chips = $$("[data-filter-chip]");
    const controls = {
      country: dom.countryFilter,
      degree: dom.degreeFilter,
      funding: dom.fundingFilter,
    };

    function setCardVisibility(card, visible) {
      clearTimeout(card.hideTimer);
      if (visible) {
        card.hidden = false;
        requestAnimationFrame(() => card.classList.remove("is-filtered-out"));
        return;
      }

      card.classList.add("is-filtered-out");
      card.hideTimer = window.setTimeout(() => {
        if (card.classList.contains("is-filtered-out")) card.hidden = true;
      }, 180);
    }

    function syncChips() {
      chips.forEach((chip) => {
        const control = controls[chip.dataset.filterType];
        const active = !!control && normalize(control.value) === normalize(chip.dataset.filterValue);
        chip.classList.toggle("is-active", active);
        chip.setAttribute("aria-pressed", String(active));
      });
    }

    function matches(card) {
      const search = normalize(dom.searchInput?.value);
      const country = normalize(dom.countryFilter?.value);
      const degree = normalize(dom.degreeFilter?.value);
      const funding = normalize(dom.fundingFilter?.value);
      const haystack = [
        card.dataset.title,
        card.dataset.org,
        card.dataset.country,
        card.dataset.degree,
        card.dataset.funding,
        card.dataset.category,
      ]
        .map(normalize)
        .join(" ");

      if (search && !haystack.includes(search)) return false;
      if (country && normalize(card.dataset.country) !== country) return false;
      if (degree && normalize(card.dataset.degree) !== degree) return false;
      if (funding && normalize(card.dataset.funding) !== funding) return false;
      return true;
    }

    function updateResults(count) {
      if (!dom.catalogResultsCount) return;
      dom.catalogResultsCount.textContent = count === 1 ? "Showing 1 scholarship" : `Showing ${count} scholarships`;
    }

    function applyFilters() {
      let visibleCount = 0;
      cards.forEach((card) => {
        const visible = matches(card);
        setCardVisibility(card, visible);
        if (visible) visibleCount += 1;
      });

      updateResults(visibleCount);
      if (dom.catalogEmpty) dom.catalogEmpty.hidden = visibleCount !== 0;
      syncChips();
    }

    dom.searchInput?.addEventListener("input", applyFilters);
    dom.countryFilter?.addEventListener("change", applyFilters);
    dom.degreeFilter?.addEventListener("change", applyFilters);
    dom.fundingFilter?.addEventListener("change", applyFilters);

    chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        const control = controls[chip.dataset.filterType];
        if (!control) return;
        const value = normalize(chip.dataset.filterValue);
        control.value = normalize(control.value) === value ? "" : value;
        applyFilters();
      });
    });

    dom.clearFilters?.addEventListener("click", () => {
      if (dom.searchInput) dom.searchInput.value = "";
      if (dom.countryFilter) dom.countryFilter.value = "";
      if (dom.degreeFilter) dom.degreeFilter.value = "";
      if (dom.fundingFilter) dom.fundingFilter.value = "";
      applyFilters();
    });

    applyFilters();
  }

  function toast(title, message, tone = "info") {
    if (!dom.toastStack) return;

    const iconMap = {
      success: "bi-check2-circle",
      info: "bi-stars",
      warning: "bi-exclamation-circle",
      danger: "bi-exclamation-octagon",
    };

    const toastEl = document.createElement("article");
    toastEl.className = `toast-card toast-card--${tone}`;

    const iconWrap = document.createElement("span");
    iconWrap.className = "toast-card__icon";
    iconWrap.innerHTML = `<i class="bi ${iconMap[tone] || iconMap.info}"></i>`;

    const content = document.createElement("div");
    content.className = "toast-card__content";

    const strong = document.createElement("strong");
    strong.textContent = title;

    const paragraph = document.createElement("p");
    paragraph.textContent = message;

    content.append(strong, paragraph);

    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-card__close";
    close.setAttribute("aria-label", "Dismiss notification");
    close.innerHTML = '<i class="bi bi-x-lg"></i>';

    const remove = () => {
      toastEl.style.opacity = "0";
      toastEl.style.transform = "translateY(-8px) translateX(8px)";
      window.setTimeout(() => toastEl.remove(), 180);
    };

    close.addEventListener("click", remove);
    toastEl.append(iconWrap, content, close);
    dom.toastStack.appendChild(toastEl);
    window.setTimeout(remove, 3800);
  }

  function loadSaved() {
    try {
      const raw = localStorage.getItem(storageKeys.saved) || localStorage.getItem(storageKeys.legacySaved);
      const parsed = raw ? JSON.parse(raw) : {};
      if (!localStorage.getItem(storageKeys.saved) && raw) {
        localStorage.setItem(storageKeys.saved, JSON.stringify(parsed));
      }
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function writeSaved(payload) {
    try {
      localStorage.setItem(storageKeys.saved, JSON.stringify(payload || {}));
    } catch (e) {}
  }

  function savedEntries(savedMap) {
    return Object.entries(savedMap || {}).sort((a, b) => {
      const aTime = new Date(a[1]?.savedAt || 0).getTime();
      const bTime = new Date(b[1]?.savedAt || 0).getTime();
      return bTime - aTime;
    });
  }

  function updateSavedCounts(count) {
    if (dom.savedCount) dom.savedCount.textContent = count === 1 ? "1 saved" : `${count} saved`;
    if (dom.heroSavedCount) dom.heroSavedCount.textContent = String(count);
  }

  function payloadFromButton(button) {
    return {
      title: button.getAttribute("data-title") || "Saved scholarship",
      org: button.getAttribute("data-org") || "Organization not provided",
      country: button.getAttribute("data-country") || "Global",
      level: button.getAttribute("data-level") || "Open level",
      amount: button.getAttribute("data-amount") || "Funding available",
      summary: button.getAttribute("data-summary") || "Opportunity saved from your scholarship dashboard.",
      deadline: button.getAttribute("data-deadline") || "Rolling deadline",
      applyUrl: button.getAttribute("data-apply-url") || "#",
      savedAt: new Date().toISOString(),
    };
  }

  function setSaveButtonState(button, savedMap) {
    if (button.dataset.saveKind === "remove") return;

    const id = button.getAttribute("data-sch-id") || "";
    const isSaved = !!savedMap[id];

    button.classList.toggle("is-saved", isSaved);
    button.setAttribute("aria-pressed", String(isSaved));

    const icon = $("i", button);
    const label = $("span", button);
    if (icon) icon.className = `bi ${isSaved ? "bi-bookmark-check-fill" : "bi-bookmark"}`;
    if (label) label.textContent = isSaved ? "Saved" : "Save";
  }

  function createSavedFact(iconName, value) {
    const fact = document.createElement("span");
    const icon = document.createElement("i");
    icon.className = `bi ${iconName}`;
    const text = document.createElement("span");
    text.textContent = value;
    fact.append(icon, text);
    return fact;
  }

  function createSavedCard(id, item) {
    const article = document.createElement("article");
    article.className = "saved-card";

    const eyebrow = document.createElement("span");
    eyebrow.className = "saved-card__eyebrow";
    eyebrow.textContent = "Saved pick";

    const title = document.createElement("h3");
    title.textContent = item.title || "Saved scholarship";

    const org = document.createElement("p");
    org.className = "saved-card__org";
    org.textContent = item.org || "Organization not provided";

    const summary = document.createElement("p");
    summary.className = "saved-card__summary";
    summary.textContent = item.summary || "Return to this opportunity whenever you are ready to apply.";

    const facts = document.createElement("div");
    facts.className = "saved-card__facts";
    facts.append(
      createSavedFact("bi-cash-coin", item.amount || "Funding available"),
      createSavedFact("bi-globe2", item.country || "Global"),
      createSavedFact("bi-mortarboard", item.level || "Open level"),
      createSavedFact("bi-alarm", item.deadline || "Rolling deadline")
    );

    const actions = document.createElement("div");
    actions.className = "saved-card__actions";

    const applyLink = document.createElement("a");
    applyLink.className = "action-btn action-btn--primary action-btn--small";
    applyLink.href = item.applyUrl || "#";
    applyLink.innerHTML = '<i class="bi bi-arrow-up-right-circle"></i><span>Apply</span>';

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "action-btn action-btn--ghost action-btn--small js-save";
    removeButton.setAttribute("data-save-kind", "remove");
    removeButton.setAttribute("data-sch-id", id);
    removeButton.innerHTML = '<i class="bi bi-trash3"></i><span>Remove</span>';

    actions.append(applyLink, removeButton);
    article.append(eyebrow, title, org, summary, facts, actions);
    return article;
  }

  function renderSaved(savedMap) {
    if (!dom.savedList) return;

    const entries = savedEntries(savedMap);
    dom.savedList.replaceChildren();

    entries.forEach(([id, item]) => {
      dom.savedList.appendChild(createSavedCard(id, item));
    });

    if (dom.savedSkeleton) dom.savedSkeleton.hidden = true;
    if (dom.savedEmpty) dom.savedEmpty.hidden = entries.length !== 0;
    updateSavedCounts(entries.length);
  }

  function refreshSaved() {
    const savedMap = loadSaved();
    $$(".js-save").forEach((button) => setSaveButtonState(button, savedMap));
    renderSaved(savedMap);
  }

  function initSaved() {
    if (dom.savedSkeleton) dom.savedSkeleton.hidden = false;

    document.addEventListener("click", (event) => {
      const button = event.target.closest(".js-save");
      if (!button) return;

      const id = button.getAttribute("data-sch-id") || "";
      if (!id) return;

      const savedMap = loadSaved();
      const exists = !!savedMap[id];
      const removeOnly = button.dataset.saveKind === "remove";

      if (exists) {
        delete savedMap[id];
        writeSaved(savedMap);
        refreshSaved();
        toast("Removed from shortlist", "This scholarship has been removed from your saved list.", "warning");
        return;
      }

      if (removeOnly) return;

      savedMap[id] = payloadFromButton(button);
      writeSaved(savedMap);
      refreshSaved();
      toast("Saved to shortlist", `${savedMap[id].title} is now ready in your saved list.`, "success");
    });

    dom.clearSaved?.addEventListener("click", () => {
      const count = savedEntries(loadSaved()).length;
      if (!count) return;
      writeSaved({});
      refreshSaved();
      toast("Shortlist cleared", "Your saved scholarship list has been reset.", "info");
    });

    window.setTimeout(refreshSaved, 160);
  }

  function initStorageSync() {
    window.addEventListener("storage", (event) => {
      if (event.key === storageKeys.saved) refreshSaved();
      if (event.key === storageKeys.theme && event.newValue) {
        dom.root.dataset.theme = event.newValue;
        updateThemeButton();
      }
    });
  }

  function init() {
    initTheme();
    initSidebar();
    initNav();
    initCounters();
    initFilters();
    initSaved();
    initStorageSync();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
