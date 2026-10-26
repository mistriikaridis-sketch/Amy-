"""Landing-page HTML — local product shell 「阅稿」.

Copy is fully i18n-driven (t()). No local-upload marketing when uploads are off.
"""

from __future__ import annotations

import os as _os

from ...i18n import LANGUAGE_DISPLAY_NAMES, SUPPORTED_LANGUAGES, get_ui_language, t

APP_NAME = _os.environ.get("VTA_APP_NAME") or _os.environ.get("APP_NAME") or "阅稿"


def _uploads_enabled() -> bool:
    return (_os.environ.get("VTA_UPLOADS_ENABLED") or "").strip().lower() == "true"


def render_home_html() -> str:
    """Return the landing page HTML for the current UI language."""
    lang = get_ui_language()
    uploads = _uploads_enabled()
    lead = t("web.home.lead_with_upload") if uploads else t("web.home.lead")
    step1_title = t("web.home.step1_title_upload") if uploads else t("web.home.step1_title")
    step1_desc = t("web.home.step1_desc_upload") if uploads else t("web.home.step1_desc")

    options = []
    for code in SUPPORTED_LANGUAGES:
        label = LANGUAGE_DISPLAY_NAMES.get(code, code)
        sel = " selected" if code == lang else ""
        options.append(f'<option value="{code}" lang="{code}"{sel}>{label}</option>')
    options_html = "\n            ".join(options)

    return f"""<!DOCTYPE html>
<html lang="{lang}" data-theme="light" class="yg-shell">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{APP_NAME} · {t("web.home.meta_title")}</title>
    <meta name="description" content="{t("web.home.meta_description")}">
    <meta name="theme-color" content="#fafaf7">
    <meta name="robots" content="noindex">
    <link rel="stylesheet" href="/static/css/view-japanese-minimal.css?v=yg7">
</head>
<body class="yg-home">
  <header class="yg-mast">
    <a class="yg-brand" href="/">
      <span class="yg-seal" aria-hidden="true">阅</span>
      <span class="yg-brand-name">{APP_NAME}</span>
    </a>
    <label class="yg-lang-switch" style="margin-inline-end:.5rem">
      <span class="yg-lang-label">{t("web.ui.language_label")}</span>
      <select id="yg-home-lang" aria-label="{t("web.ui.language_switch_aria")}" onchange="(function(s){{try{{localStorage.setItem('vta_ui_lang',s.value)}}catch(e){{}}location.href='/?lang='+encodeURIComponent(s.value)}})(this)">
            {options_html}
      </select>
    </label>
    <nav class="yg-mast-links" aria-label="{t("web.home.nav_aria")}">
      <a href="/add_task_by_web">{t("web.nav.submit")}</a>
      <a href="/static/history.html">{t("web.nav.history")}</a>
      <a href="#advanced">{t("web.nav.advanced")}</a>
    </nav>
  </header>

  <main class="yg-main">
    <div class="yg-hero">
      <aside class="yg-hero-tategaki" aria-hidden="true">{t("web.home.tategaki")}</aside>
      <div>
        <p class="yg-kicker">{t("web.home.kicker")}</p>
        <h1 class="yg-hero-title">{t("web.home.title")}</h1>
        <p class="yg-hero-lead">{lead}</p>
      </div>
    </div>

    <ol class="yg-steps" aria-label="{t("web.home.steps_aria")}">
      <li>
        <span class="yg-step-num">{t("web.home.step1_num")}</span>
        <div>
          <div class="yg-step-title">{step1_title}</div>
          <div class="yg-step-desc">{step1_desc}</div>
        </div>
      </li>
      <li>
        <span class="yg-step-num">{t("web.home.step2_num")}</span>
        <div>
          <div class="yg-step-title">{t("web.home.step2_title")}</div>
          <div class="yg-step-desc">{t("web.home.step2_desc")}</div>
        </div>
      </li>
      <li>
        <span class="yg-step-num">{t("web.home.step3_num")}</span>
        <div>
          <div class="yg-step-title">{t("web.home.step3_title")}</div>
          <div class="yg-step-desc">{t("web.home.step3_desc")}</div>
        </div>
      </li>
    </ol>

    <div class="yg-cta-row">
      <a class="yg-cta-primary" href="/add_task_by_web">{t("web.home.cta_start")}</a>
      <a class="yg-cta-secondary" href="/static/history.html">{t("web.home.cta_history")}</a>
    </div>

    <section class="yg-panel" id="advanced">
      <details>
        <summary>{t("web.home.advanced_summary")}</summary>
        <div class="yg-adv">
          <p>{t("web.home.advanced_intro")}</p>
          <p><strong>{t("web.home.advanced_health")}</strong></p>
          <pre>curl -s http://127.0.0.1:8200/livez
curl -s http://127.0.0.1:8200/health</pre>
          <p><strong>{t("web.home.advanced_submit")}</strong></p>
          <pre>curl -s -X POST http://127.0.0.1:8200/api/transcribe \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{{"url":"https://example.com/video"}}'</pre>
          <p>{t("web.home.advanced_config")}</p>
          <p>{t("web.home.advanced_more")} <a href="/static/help-advanced.html">{t("web.nav.advanced")}</a> · <a href="/docs">OpenAPI /docs</a></p>
        </div>
      </details>
    </section>
  </main>

  <footer class="yg-foot">{APP_NAME} · {t("web.home.footer_local")}</footer>
  <script>
  (function(){{
    try {{
      var u=new URL(location.href); var q=u.searchParams.get("lang");
      if(q) localStorage.setItem("vta_ui_lang", q);
    }} catch(e) {{}}
  }})();
  </script>
</body>
</html>
"""
