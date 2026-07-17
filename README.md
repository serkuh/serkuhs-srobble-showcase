# Manakin Last.fm Now Playing Widget

A Vercel-hosted dynamic PNG for AniList. The image is rendered when requested and cached for about five minutes.

## Required Vercel environment variable

- `LASTFM_API_KEY` — your Last.fm API key

Optional:

- `LASTFM_USER` — defaults to `manakin_zZ`

## Image URL

After deployment, use:

`https://YOUR-PROJECT.vercel.app/now-playing.png`

The confirmed album-art boundary is hard-coded as `(138, 299, 471, 646)` with an 18 px corner radius.
