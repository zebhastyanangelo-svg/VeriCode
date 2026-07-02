const PLATFORMS = [
  { name: 'Netflix', svg: 'https://svgl.app/library/netflix-icon.svg' },
  { name: 'Spotify', svg: 'https://svgl.app/library/spotify.svg' },
  { name: 'Disney+', svg: 'https://svgl.app/library/disneyplus.svg' },
  { name: 'Prime Video', svg: 'https://svgl.app/library/prime-video.svg' },
  { name: 'HBO Max', icon: 'fa-play' },
  { name: 'OpenAI', svg: 'https://svgl.app/library/openai.svg' },
  { name: 'Midjourney', svg: 'https://svgl.app/library/midjourney.svg' },
  { name: 'Claude', svg: 'https://svgl.app/library/claude-ai-icon.svg' },
  { name: 'Hulu', svg: 'https://svgl.app/library/hulu.svg' },
  { name: 'YouTube', svg: 'https://svgl.app/library/youtube.svg' },
  { name: 'Apple Music', svg: 'https://svgl.app/library/apple-music-icon.svg' },
  { name: 'Tidal', svg: 'https://svgl.app/library/tidal_light.svg' },
  { name: 'Gemini', svg: 'https://svgl.app/library/gemini.svg' },
  { name: 'Paramount+', icon: 'fa-star' },
  { name: 'Twitch', svg: 'https://svgl.app/library/twitch.svg' },
  { name: 'Perplexity', svg: 'https://svgl.app/library/perplexity.svg' },
  { name: 'Notion', svg: 'https://svgl.app/library/notion.svg' },
  { name: 'Canva', svg: 'https://svgl.app/library/canva.svg' },
  { name: 'Shopify', svg: 'https://svgl.app/library/shopify.svg' },
  { name: 'Dropbox', svg: 'https://svgl.app/library/dropbox.svg' },
];

export default function LogoSphere() {
  const radius = 240;
  const count = PLATFORMS.length;

  return (
    <div className="sphere-scene">
      <div className="sphere-ring">
        {PLATFORMS.map((p, i) => {
          const angle = (360 / count) * i;
          return (
            <div
              key={p.name}
              className="sphere-item"
              style={{
                transform: `rotateY(${angle}deg) translateZ(${radius}px)`,
              }}
            >
              <div className="sphere-logo-box">
                {p.svg ? (
                  <img src={p.svg} alt={p.name} className="sphere-logo-img" loading="lazy" />
                ) : (
                  <div className="sphere-logo-fallback">
                    <i className={`fas ${p.icon}`}></i>
                  </div>
                )}
              </div>
              <span className="sphere-label">{p.name}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}