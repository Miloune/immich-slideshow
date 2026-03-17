# <img src="https://github.com/Miloune/immich-slideshow/raw/master/brand/logo.png" width="32" height="32" align="center"> Immich Slideshow

A Home Assistant custom integration that displays a photo slideshow from your [Immich](https://immich.app) server directly in your Lovelace dashboard.

All API calls are proxied through the **Home Assistant backend** — no CORS issues, no credentials exposed to the browser.

![Preview](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/preview.gif)
![Preview](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/settings.png)

---

## Requirements

- A running [Immich](https://immich.app) instance
- Home Assistant with HACS (recommended) or manual installation

> [!IMPORTANT]
> This is a **full Custom Integration**, not just a Lovelace card. It must be installed into `custom_components/`, not `www/`.

---

## Installation

### Method 1 — HACS (Recommended)

1. Open **HACS** → **Integrations**
2. Click the three-dot menu → **Custom repositories**
3. Add `https://github.com/Miloune/immich-slideshow` with category **Integration**
4. Find **Immich Slideshow** and click **Download**
5. **Restart Home Assistant**

### Method 2 — Manual

1. Download or clone this repository
2. Copy `custom_components/immich_slideshow/` into your HA `config/custom_components/` directory
3. **Restart Home Assistant**

---

## Setup

### 1. Create an Immich API Key

In your Immich web interface, go to **Account Settings → API Keys** and create a new key.

![API Key](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/apikey.jpg)

### 2. Configure the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Immich Slideshow**
3. Fill in the form and click **Submit**

| Field | Description |
|---|---|
| **Host** | Your Immich server URL (e.g. `http://192.168.1.10:2283`) |
| **API Key** | The key created in the previous step |
| **Batch size** | Number of images fetched per batch (default: `50`, max: `1000`) |
| **Default image size** | `thumbnail` (~50 kB, fast) or `preview` (~300 kB, higher quality) |
| **Refill threshold** | Background cache refill triggers when this many images remain (default: `3`) |

> [!TIP]
> You can update these settings at any time via **Settings → Devices & Services → Immich Slideshow → Configure** — no need to delete and re-add the integration.

### 3. Add the Card to your Dashboard

The Lovelace card resource is registered automatically after setup. Add a new card via the visual editor or YAML:

```yaml
type: custom:immich-slideshow
slideshow_interval: 10
height: 500
albums:
  - your_album_id_here
  - another_album_id_here
```

#### Card Parameters

| Parameter | Required | Default | Description |
|---|---|---|---|
| `slideshow_interval` | No | `10` | Seconds between images (minimum `6`) |
| `height` | No | `400` | Card height in pixels — enter a number, e.g. `400` for 400 px |
| `albums` | No | All photos | List of Immich album IDs to restrict the slideshow to |

> [!NOTE]
> The server URL and API key are securely stored by the integration backend and never appear in card YAML.

---

## Local Development

If you want to test your changes locally, a `docker-compose.yml` is provided at the root of the repository. It starts a Home Assistant instance with the `custom_components` folder pre-loaded as a volume.

1. Start the stack:
   ```bash
   docker compose up -d
   ```
2. Open Home Assistant at `http://localhost:8123`.
3. After any code modification, you just need to restart Home Assistant via the UI (**Settings → System → Restart**) or via command line:
   ```bash
   docker compose restart homeassistant
   ```

---

## How It Works

The card never contacts your Immich server directly. All image requests go through Home Assistant:

```
Lovelace card  →  Home Assistant backend  →  Immich server
```

This eliminates CORS issues regardless of your network configuration, and keeps your API key out of the browser.

**Under the hood:**
- A batch of random asset IDs is fetched from Immich and cached in HA memory
- Each slideshow tick pops one ID from the cache and fetches its thumbnail
- When the cache drops below the configured threshold, a background task silently refills it — the user never waits
- Images are decoded before the crossfade starts, preventing any resize or layout flash
- Blob URLs are revoked as soon as they are no longer needed


---

[![Buy me a coffee](https://cdn.buymeacoffee.com/buttons/default-orange.png)](https://buymeacoffee.com/miloune)