# tutor-plugins

Tutor plugins for an Open edX devstack: a test harness for the Text (HTML) XBlock's
`include_theme` setting.

Single-file plugins in the Tutor v1 plugins root. Enable them with
`tutor plugins enable <name>`, then `tutor config save`.

| Plugin | What it does |
| --- | --- |
| [`xblock_themes.py`](xblock_themes.py) | Serves a local, hand-editable theme to themed Text blocks, and publishes its URL where both the block and Studio's editor can read it |

## xblock_themes

The Text (HTML) XBlock's `include_theme` setting renders the block into a shadow
root and attaches the stylesheets advertised by `PARAGON_THEME_URLS` in the MFE
config API. That config normally comes from tutor-indigo pointing at a CDN build,
which is fine in production but useless for iteration — you cannot edit a
CDN-hosted file.

This plugin repoints the brand override at a local stylesheet:

```
plugins/xblock-themes/my-theme.css   <- edit this
/static/xblock-themes/my-theme.css   <- served, ends up in the block
```

Edit the CSS, run `tutor config save`, reload.

It also fills two gaps that otherwise make the feature look broken in Studio,
where the block is served from the CMS origin:

- `/openedx/config/static` is added to `STATICFILES_DIRS`. Deliberately not
  `env/build`: in dev, Django serves `/static/` from the application source trees
  and `STATICFILES_DIRS`, and ignores `env/build` entirely.
- The Studio origin is added to `CORS_ORIGIN_WHITELIST`, so the block's
  cross-origin fetch of the config API is not blocked. Tutor's `development.py`
  only whitelists MFE origins — the production template also appends `CMS_HOST` —
  so without this the block's `.catch()` swallows the error and it silently falls
  back to the CDN.

Everything is published under **`PARAGON_THEME_URLS`** — the same MFE config key
the block itself fetches. That key carries the whole list: Paragon's core,
Paragon's theme, and the local brand override. Studio's text editor reads the
same key and layers them in the same order, so the editor preview and the
learner view cannot drift apart.

Note that the `theme` key the newer frontend-base MFEs read is a different thing:
it lives in `FRONTEND_SITE_CONFIG`, served by `/api/frontend_site_config/v1/`,
not in the `MFE_CONFIG` that `getConfig()` returns, and it has no
`brandOverride` slot to iterate against. When `frontend-app-authoring` converts
to a frontend-base app — and `getConfig()` starts reading the site config — that
becomes the key to revisit. See the comment in the plugin.

> `xblock_themes` patches the same `PARAGON_THEME_URLS` value that tutor-indigo
> patches. Tutor applies patches for a target in plugin load order, so this plugin
> must stay listed **after** `indigo` in `PLUGINS`.

## Requirements

- `tutor-mfe` (`xblock_themes`)
- tutor-indigo (`xblock_themes` — must load first)
