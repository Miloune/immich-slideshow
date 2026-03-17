# immich-slideshow
Custom card for Home Assistant's UI LoveLace which will display images slideshow from Immich server. Card is designed for Chromium running in kiosk mode.

![Screenshot](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/preview.gif)

![Screenshot](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/preview2.gif)

# Plugin installation

## Method 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Go to **Frontend**, click the three dots in the top right corner, and select **Custom repositories**.
3. Add the URL of this repository (`https://github.com/Miloune/immich-slideshow`) and select **Dashboard** as the category.
4. Click **Add**, find **Immich Slideshow** in the list, and download it.
5. Reload your browser if prompted.

## Method 2: Manual Installation

1. Download the `immich-slideshow.js` file.
2. Install the plugin (For more details, see [Thomas Loven's Install Guide](https://github.com/thomasloven/hass-config/wiki/Lovelace-Plugins)).
> [!IMPORTANT]  
> Place the downloaded file under the `/config/www/immich-slideshow/` directory.

# Immich server configuration
1. Login into your immich server and create new apiKey

![Screenshot](https://github.com/Miloune/immich-slideshow/raw/master/screenshots/apikey.jpg)

# HomeAssistant configuration
1. Login into HomeAssistant server and add new custom card to the dashboard with the following configuration parameters:

Parameter name | Required | Default value | Description
--- | --- | ---- | ---
host | YES | - | URL to immich server
apikey | YES | - | Immich apiKey
slideshow_interval | NO | 6 | Time (in seconds) after new image is loaded (minimum 6)
height| NO | auto | Card height (eg. 500px)
albums | NO | - | Single album ID or list of album IDs to restrict the slideshow to

# Preview in chromium browser
Run chromium using fallowing commands:

1. Linux:

```console
/usr/bin/chromium-browser --noerrdialogs --disable-infobars --ignore-certificate-errors --allow-running-insecure-content --disable-web-security --user-data-dir=PATH_TO_PROFILE_DIRECORY --kiosk DASHBOARD_URL
```

2. Windows:
```console
start "C:\Program Files\Google\Chrome\Application\" chrome.exe --allow-running-insecure-content --disable-web-security --user-data-dir=PATH_TO_PROFILE_DIRECORY --kiosk DASHBOARD URL
```
> [!TIP]
> Replace PATH_TO_PROFILE_DIRECORY and DASHBOARD_URL with valid values.





[![buycoffee](https://buycoffee.to/static/img/share/share-button-primary.png)](https://buycoffee.to/mulder82)
