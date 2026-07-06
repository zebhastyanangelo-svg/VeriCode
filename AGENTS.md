# Mixpanel Analytics

## Stack
- **SDK:** `mixpanel-browser` (v2.x)
- **Tracking method:** Client-side (browser)
- **CDP:** None
- **Consent:** Opt-out by default (`opt_out_tracking_by_default: true`). Consent stored in localStorage under `mixpanel_consent`. Export functions `giveConsent()` / `revokeConsent()` / `hasConsent()` from `src/utils/analytics.js`.

## Token
- **Env var:** `VITE_MIXPANEL_TOKEN`
- **Default:** `0a6068b376632aba002d010e84fd9f26` (production)
- **Location:** `src/utils/analytics.js:3`

## Initialization
- **File:** `src/main.jsx` — `initMixpanel()` called at module import
- **Config:** `debug: true` in dev, `track_pageview: false` (manual page tracking)

## Events

| Event | Trigger | File | Properties |
|---|---|---|---|
| `page_viewed` | Hash route change | `src/App.jsx:35` | `page` (string, e.g. `/dashboard`) |
| `sign_up_completed` | Admin login success | `src/context/AuthContext.jsx:30` | (tracked after identify) |
| `code_received` | New code via WebSocket | `src/pages/Dashboard.jsx:86` | `platform_name`, `email_account`, `is_delivered` |
| `code_requested` | Public code request form | `src/pages/PublicCodeRequestPage.jsx:49,57` | `platform_name`, `email_account`, `success` |

## Identity
| Action | Call | Location |
|---|---|---|
| Login | `identify(user.id)` + `people.set()` + `register({ platform })` | `src/context/AuthContext.jsx:30-33` |
| Logout | `reset()` | `src/context/AuthContext.jsx:48` |

## Utils
- **File:** `src/utils/analytics.js`
- **Exports:** `initMixpanel`, `giveConsent`, `revokeConsent`, `hasConsent`, `track`, `identify`, `peopleSet`, `reset`, `register`

## Naming
- Event names: `snake_case`, past_tense_verb + noun
- Property names: `snake_case`, no abbreviations
- Never use `$` or `mp_` prefix on custom properties
- Never track PII as event properties (use `people.set()` for user profile data)
