import mixpanel from 'mixpanel-browser';

const TOKEN = import.meta.env.VITE_MIXPANEL_TOKEN || '0a6068b376632aba002d010e84fd9f26';
const CONSENT_KEY = 'mixpanel_consent';

export function initMixpanel() {
  if (!TOKEN) return;
  mixpanel.init(TOKEN, {
    debug: import.meta.env.DEV,
    opt_out_tracking_by_default: true,
    track_pageview: false,
    persistence: 'localStorage',
  });
  if (localStorage.getItem(CONSENT_KEY) === 'true') {
    mixpanel.opt_in_tracking();
  }
}

export function giveConsent() {
  localStorage.setItem(CONSENT_KEY, 'true');
  mixpanel.opt_in_tracking();
}

export function revokeConsent() {
  localStorage.removeItem(CONSENT_KEY);
  mixpanel.opt_out_tracking();
}

export function hasConsent() {
  return localStorage.getItem(CONSENT_KEY) === 'true';
}

export function track(event, properties = {}) {
  if (!TOKEN) return;
  mixpanel.track(event, properties);
}

export function identify(id) {
  if (!TOKEN) return;
  mixpanel.identify(id);
}

export function peopleSet(properties) {
  if (!TOKEN) return;
  mixpanel.people.set(properties);
}

export function reset() {
  if (!TOKEN) return;
  mixpanel.reset();
}

export function register(properties) {
  if (!TOKEN) return;
  mixpanel.register(properties);
}
