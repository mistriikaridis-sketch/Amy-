/**
 * Resolve UI language for static pages (index / history / help).
 * Prefer ?lang= then localStorage vta_ui_lang; fall back to catalog default via /i18n.js.
 */
(function (root) {
  var SUPPORTED = ["zh-CN","en","ja","ko","es","fr","pt","de","ru","ar"];
  var LABELS = {
    "zh-CN": "中文", "en": "English", "ja": "日本語", "ko": "한국어",
    "es": "Español", "fr": "Français", "pt": "Português", "de": "Deutsch",
    "ru": "Русский", "ar": "العربية"
  };
  function pickLang() {
    try {
      var u = new URL(root.location.href);
      var q = u.searchParams.get("lang");
      if (q && SUPPORTED.indexOf(q) >= 0) {
        try { root.localStorage.setItem("vta_ui_lang", q); } catch (e) {}
        return q;
      }
      var stored = root.localStorage.getItem("vta_ui_lang");
      if (stored && SUPPORTED.indexOf(stored) >= 0) return stored;
    } catch (e) {}
    return "";
  }
  function mountSwitcher(selectId) {
    var sel = root.document.getElementById(selectId || "yg-static-lang-select");
    if (!sel) return;
    var current = root.__VTA_LANG__ || pickLang() || "zh-CN";
    sel.innerHTML = "";
    SUPPORTED.forEach(function (code) {
      var opt = root.document.createElement("option");
      opt.value = code;
      opt.textContent = LABELS[code] || code;
      opt.lang = code;
      if (code === current) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.addEventListener("change", function () {
      var next = sel.value;
      try { root.localStorage.setItem("vta_ui_lang", next); } catch (e) {}
      var u = new URL(root.location.href);
      u.searchParams.set("lang", next);
      root.location.href = u.toString();
    });
  }
  root.__VTA_UI_LANG_BOOT__ = pickLang();
  root.ygMountLanguageSwitcher = mountSwitcher;
  root.ygSupportedLanguages = SUPPORTED;
  root.ygLanguageLabels = LABELS;
})(window);
