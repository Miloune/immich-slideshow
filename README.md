# immich-slideshow
Custom card for Home Assistant's UI Lovelace which displays an image slideshow from an Immich server. The integration runs its API calls through the **Home Assistant backend**, completely avoiding any browser CORS issues.

![Screenshot](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/preview.gif)

![Screenshot](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/preview2.gif)

# Plugin installation

> [!IMPORTANT]
> This is a **full Custom Integration** (not just a Lovelace plugin). It must be installed into `custom_components/`, not `www/`.

## Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Go to **Integrations**, click the three dots in the top right corner, and select **Custom repositories**.
3. Add the URL of this repository (`https://github.com/Miloune/immich-slideshow`) and select **Integration** as the category.
4. Click **Add**, find **Immich Slideshow** in the list, and download it.
5. **Restart Home Assistant**.

## Method 2: Manual Installation

1. Download or clone this repository.
2. Copy the `custom_components/immich_slideshow/` folder into your Home Assistant `config/custom_components/` directory.
3. **Restart Home Assistant**.

# Immich server configuration
1. Log in to your Immich server and create a new API Key:

![Screenshot](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/apikey.jpg)

# HomeAssistant configuration

## Step 1: Set up the integration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Immich Slideshow**.
3. Enter your Immich server URL and API Key in the form and click **Submit**.

The integration will validate the connection and register itself automatically.

## Step 2: Add the Lovelace card

The Lovelace card resource is registered automatically. Add a new custom card to your dashboard using the visual editor or YAML:

### Card parameters

Parameter name | Required | Default value | Description
--- | --- | ---- | ---
slideshow_interval | NO | 10 | Time (in seconds) between images (minimum 6)
height | NO | 100% | Card height (e.g. `500px`, `100vh`)
albums | NO | all images | A list of album IDs to restrict the slideshow to

### YAML Configuration Example

```yaml
type: custom:immich-slideshow
slideshow_interval: 10
height: 500px
albums:
  - 'first_album_id_here'
  - 'second_album_id_here'
```

> [!NOTE]
> The `host` and `apikey` are no longer configured in the card YAML. They are securely stored by the integration backend (set up in Step 1 above).

# How it works

Unlike a traditional Lovelace card that calls the Immich API directly from your browser, this integration acts as a **proxy**:

```
Browser → Home Assistant backend → Immich server
```

The browser only ever talks to Home Assistant (same origin), which eliminates all CORS issues regardless of network setup.

# Preview in Chromium browser (Kiosk mode)

Run Chromium using the following commands:

1. Linux:

```console
/usr/bin/chromium-browser --noerrdialogs --disable-infobars --ignore-certificate-errors --allow-running-insecure-content --user-data-dir=PATH_TO_PROFILE_DIRECTORY --kiosk DASHBOARD_URL
```

2. Windows:
```console
start "C:\Program Files\Google\Chrome\Application\" chrome.exe --user-data-dir=PATH_TO_PROFILE_DIRECTORY --kiosk DASHBOARD_URL
```
> [!TIP]
> Replace `PATH_TO_PROFILE_DIRECTORY` and `DASHBOARD_URL` with valid values.




[![buycoffee](https://buycoffee.to/static/img/share/share-button-primary.png)](https://buycoffee.to/mulder82)
