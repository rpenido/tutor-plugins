"""Test harness for the Text (HTML) XBlock's ``include_theme`` setting.

With ``include_theme`` on, ``xblocks_contrib.html`` renders the block into a
shadow root and attaches the stylesheets advertised by ``PARAGON_THEME_URLS`` in
the MFE config API (see ``xblocks_contrib/html/static/js/html_block.js``). That
config normally comes from tutor-indigo, pointing at a CDN build. That is fine
in production but useless for iteration, because editing a CDN-hosted file is
not something you can do.

So this plugin repoints the brand override at a local stylesheet:

    plugins/xblock-themes/my-theme.css   <- edit this
    /static/xblock-themes/my-theme.css   <- served, ends up in the block

Edit the CSS, run ``tutor config save``, reload.

Studio's text editor previews the same stylesheets, from the same key: its
``contentStyle`` (openedx/frontend-app-authoring#3271) reads ``PARAGON_THEME_URLS``
and layers Paragon's core, Paragon's theme and the brand override ahead of the
editor's own styles, in the same order the block applies them.

It also fills two gaps that otherwise make the feature look broken in Studio,
where the block is served from the CMS origin:

* ``/openedx/config/static`` is added to ``STATICFILES_DIRS``. Deliberately not
  ``env/build``: in dev, Django serves ``/static/`` from the application source
  trees and ``STATICFILES_DIRS``, and ignores ``env/build`` entirely.
* the Studio origin is added to ``CORS_ORIGIN_WHITELIST``, so the block's
  cross-origin fetch of the config API is not blocked. Tutor's ``development.py``
  only whitelists MFE origins -- the production template also appends
  ``CMS_HOST`` -- so without this the block's ``.catch()`` swallows the error and
  it silently falls back to the CDN.

Enable with::

    tutor plugins enable xblock_themes
    tutor config save
    tutor dev start -d

The ``PARAGON_THEME_URLS`` override is patched onto the *mfe* settings, which
tutor-indigo also patches. Tutor applies the patches for a target in plugin load
order, so this plugin must stay listed after ``indigo`` in ``PLUGINS``, or
indigo overwrites the value.
"""

import os
import shutil

from tutor import hooks

# The single theme this plugin serves.
_THEME = "my-theme"

# Paragon's own layers, mirroring the CDN constants hardcoded in
# ``xblocks_contrib/html/static/js/html_block.js``. The block keeps those as the
# base it always applies; publishing them here as well makes the config the one
# place that knows the theme URLs, so the Studio editor can build the same
# stylesheet list the block builds instead of guessing at its own.
_PARAGON_CORE = "https://cdn.jsdelivr.net/npm/@openedx/paragon@23/dist/core.min.css"
_PARAGON_THEME = "https://cdn.jsdelivr.net/npm/@openedx/paragon@23/dist/light.min.css"

_THEME_SRC = os.path.join(os.path.dirname(__file__), "xblock-themes", f"{_THEME}.css")
# Relative to the *env* directory, which is what ENV_SAVED is handed -- not the
# project root, despite what Tutor's docstring says. env/apps/openedx/config is
# already bind-mounted at /openedx/config.
_STATIC_DEST = os.path.join("apps", "openedx", "config", "static", "xblock-themes")
_STATIC_URL = f"/static/xblock-themes/{_THEME}.css"


@hooks.Actions.ENV_SAVED.add()
def _copy_theme(root: str, config: dict) -> None:
    dest = os.path.join(root, _STATIC_DEST)
    os.makedirs(dest, exist_ok=True)
    shutil.copy(_THEME_SRC, os.path.join(dest, f"{_THEME}.css"))


# __THEME_URL__ is substituted with str.replace, not %-formatting: this patch
# contains Jinja tags whose % would be read as a printf conversion and raise
# during import, taking the rest of this module's registrations with it.
_PATCH = """
# --- xblock_themes: serve a local theme to themed blocks ---------------------
STATICFILES_DIRS = [*STATICFILES_DIRS, "/openedx/config/static"]
CORS_ORIGIN_WHITELIST.append(
    "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ CMS_HOST }}:8001"
)

# Layer the local theme on top of whatever tutor-indigo configured rather than
# replacing it, so the MFE theme keeps working.
_theme_urls = MFE_CONFIG.get("PARAGON_THEME_URLS") or {}

# Paragon's layers, under the keys the XBlock and the editor both read. `core` is
# already read by the block (pickUrl(themeUrls.core)); `paragonTheme` is read by
# the Studio editor so its preview carries the same Paragon base the block
# applies. Both are setdefault: a deployment that already publishes its own wins.
_theme_urls.setdefault("core", {"url": "__PARAGON_CORE__"})
_theme_urls.setdefault("paragonTheme", {"url": "__PARAGON_THEME__"})

_light = _theme_urls.setdefault("variants", {}).setdefault("light", {})
_light.setdefault("urls", {})["brandOverride"] = LMS_ROOT_URL + "__THEME_URL__"
MFE_CONFIG["PARAGON_THEME_URLS"] = _theme_urls

# The block theme needs no key of its own. Both the block and the Studio editor
# read PARAGON_THEME_URLS, so one key carries the whole stylesheet list and the
# MFEs are untouched by it.
#
# Note that the `theme` key the newer frontend-base MFEs read is a different thing
# entirely: it lives in FRONTEND_SITE_CONFIG (served by /api/frontend_site_config/v1/),
# not in the MFE_CONFIG that getConfig() returns, and it has no brandOverride slot
# to iterate against. When frontend-app-authoring is converted to a frontend-base
# app and getConfig() starts reading the site config, revisit which key this should
# come from -- that is the one case where `theme` becomes the right answer.
# --------------------------------------------------------------------------
"""

# Patched onto the LMS only: /api/mfe_config/v1 is routed by lms/urls.py and 404s
# on the CMS, so the LMS is the only place the block ever reads these values
# from. tutor-mfe defines no mfe-cms-common-settings, so a CMS target here would
# be a silent no-op.
hooks.Filters.ENV_PATCHES.add_item(
    ("mfe-lms-common-settings",
     _PATCH.replace("__THEME_URL__", _STATIC_URL)
          .replace("__PARAGON_CORE__", _PARAGON_CORE)
          .replace("__PARAGON_THEME__", _PARAGON_THEME))
)
