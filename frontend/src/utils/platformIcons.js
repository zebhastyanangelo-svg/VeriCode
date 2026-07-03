const PLATFORM_ICON_MAP = {
  netflix: 'https://svgl.app/library/netflix-icon.svg',
  disney: 'https://svgl.app/library/disneyplus.svg',
  hbo: null,
  prime: 'https://svgl.app/library/prime-video.svg',
  spotify: 'https://svgl.app/library/spotify.svg',
  openai: 'https://svgl.app/library/openai.svg',
  anthropic: 'https://svgl.app/library/claude-ai-icon.svg',
  midjourney: 'https://svgl.app/library/midjourney.svg',
  paramount: null,
  crunchyroll: null,
};

const PLATFORM_FALLBACK_ICON = {
  netflix: 'fa-film',
  disney: 'fa-magic',
  hbo: 'fa-play',
  prime: 'fa-video',
  spotify: 'fa-music',
  openai: 'fa-robot',
  anthropic: 'fa-brain',
  midjourney: 'fa-paint-brush',
  paramount: 'fa-star',
  crunchyroll: 'fa-tv',
  default: 'fa-cube',
};

export function getPlatformIconUrl(icon) {
  if (!icon) return null;
  return PLATFORM_ICON_MAP[icon] || null;
}

export function getPlatformFallbackIcon(icon) {
  return PLATFORM_FALLBACK_ICON[icon] || PLATFORM_FALLBACK_ICON.default;
}
