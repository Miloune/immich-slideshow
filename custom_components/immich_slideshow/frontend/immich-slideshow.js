var ImmichSlideshowVersion = "2.1.0";
var PlaceholderSrc = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

import {
  LitElement,
  html,
  css,
} from "https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js";

// ─── ImmichSlideshow ──────────────────────────────────────────────────────────

class ImmichSlideshow extends LitElement {

  static get properties() {
    return {
      hass: {},
      config: {},
      // Reactive slot state — LitElement re-renders from these, not from direct DOM manipulation.
      // This survives the frequent hass updates without wiping img.src or classes.
      _slotA: { state: true },
      _slotB: { state: true },
    };
  }

  constructor() {
    super();
    this._slotA = { src: PlaceholderSrc, active: false };
    this._slotB = { src: PlaceholderSrc, active: false };
  }

  static getConfigElement() {
    return document.createElement("immich-slideshow-editor");
  }

  static getStubConfig() {
    return {
      slideshow_interval: 10,
      height: "100%",
      albums: []
    };
  }

  render() {
    return html`
      <ha-card style="overflow:hidden;">
        <div class="wrapper" style="height:${this.config.height}">
          <img
            src="${this._slotA.src}"
            class="${this._slotA.active ? 'active' : ''}"
            alt="immich-slideshow"
          >
          <img
            src="${this._slotB.src}"
            class="${this._slotB.active ? 'active' : ''}"
            alt="immich-slideshow"
          >
        </div>
      </ha-card>
    `;
  }

  // ── Internal state (not reactive, no re-render needed) ─────────────────────

  _currentSlot = 'b';  // 'b' so first advance switches to 'a'
  _slotBlobs = { a: null, b: null };
  _prefetchedUrl = null;
  _isAdvancing = false;
  _timer = null;

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  firstUpdated() {
    this._advance().then(() => {
      this._scheduleNext();
      this._prefetch();
    });
  }

  shouldUpdate(changedProperties) {
    if (changedProperties.size === 1 && changedProperties.has('hass')) return false;
    return true;
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }

    for (const slot of ['a', 'b']) {
      if (this._slotBlobs[slot]) {
        URL.revokeObjectURL(this._slotBlobs[slot]);
        this._slotBlobs[slot] = null;
      }
    }

    if (this._prefetchedUrl) {
      URL.revokeObjectURL(this._prefetchedUrl);
      this._prefetchedUrl = null;
    }

    this._log("Slideshow stopped, all blobs revoked.");
  }

  // ── Slideshow loop ─────────────────────────────────────────────────────────

  _scheduleNext() {
    this._timer = setTimeout(async () => {
      this._timer = null;
      await this._advance();
      this._scheduleNext();
      this._prefetch();
    }, this.config.slideshow_interval * 1000);
  }

  async _advance() {
    if (this._isAdvancing) return;
    this._isAdvancing = true;

    try {
      const nextSlot = this._currentSlot === 'a' ? 'b' : 'a';
      const currentSlot = this._currentSlot;

      // Use pre-fetched URL if available, otherwise fetch now.
      const url = this._prefetchedUrl ?? await this._fetchImageUrl();
      this._prefetchedUrl = null;

      if (!url) return;

      // Pre-load via a throwaway Image object to decode dimensions BEFORE
      // updating reactive state. This prevents any resize flash on first paint.
      await new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = resolve;
        img.onerror = () => reject(new Error("Image decode failed"));
        img.src = url;
      });

      // Revoke the blob previously held by the incoming slot.
      if (this._slotBlobs[nextSlot]) {
        URL.revokeObjectURL(this._slotBlobs[nextSlot]);
      }
      this._slotBlobs[nextSlot] = url;
      this._currentSlot = nextSlot;

      // Update reactive state → LitElement re-renders safely.
      if (nextSlot === 'a') {
        this._slotA = { src: url, active: true };
        this._slotB = { ...this._slotB, active: false };
      } else {
        this._slotB = { src: url, active: true };
        this._slotA = { ...this._slotA, active: false };
      }

    } catch (e) {
      this._log("Advance error: " + e.message);
    } finally {
      this._isAdvancing = false;
    }
  }

  async _prefetch() {
    if (this._prefetchedUrl) return;
    try {
      this._prefetchedUrl = await this._fetchImageUrl();
    } catch (e) {
      this._log("Prefetch error: " + e.message);
    }
  }

  // ── Network ────────────────────────────────────────────────────────────────

  async _fetchImageUrl() {
    let url = "/api/immich_slideshow/random_image";
    if (this.config.albums?.length > 0) {
      url += "?albums=" + this.config.albums.join(",");
    }
    const response = await this.hass.fetchWithAuth(url);
    if (!response.ok) throw new Error(`Immich proxy error: ${response.status}`);
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  }

  // ── Config ─────────────────────────────────────────────────────────────────

  setConfig(config) {
    const isconfig = { ...config };

    if (!isconfig.height)
      isconfig.height = "100%";
    if (!isconfig.slideshow_interval || isconfig.slideshow_interval < 6)
      isconfig.slideshow_interval = 6;

    const albums = isconfig.albums;
    if (albums) {
      isconfig.albums = Array.isArray(albums) ? albums : [albums];
    }

    this.config = isconfig;
  }

  getCardSize() { return 1; }

  _log(message) {
    console.log(`Immich-Slideshow -> ${message}`);
  }

  // ── Styles ─────────────────────────────────────────────────────────────────

  static get styles() {
    return css`
      .wrapper {
        position: relative;
        width: 100%;
        overflow: hidden;
      }

      img {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: contain;
        opacity: 0;
        z-index: 0;
        transition: opacity 3s ease-in-out;
      }

      img.active {
        opacity: 1;
        z-index: 1;
      }
    `;
  }
}

customElements.define("immich-slideshow", ImmichSlideshow);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "immich-slideshow",
  name: "Immich Slideshow",
  description: "A custom card that displays a slideshow of images from an Immich server."
});

// ─── ImmichSlideshowEditor ────────────────────────────────────────────────────

class ImmichSlideshowEditor extends LitElement {
  setConfig(config) {
    this._config = { ...config };
  }

  static get properties() {
    return { hass: {}, _config: {} };
  }

  get _slideshow_interval() { return this._config?.slideshow_interval ?? 10; }
  get _height() { return this._config?.height ?? "100%"; }
  get _albums() { return this._config?.albums ?? []; }

  render() {
    if (!this.hass || !this._config) return html``;

    const schema = [
      {
        name: "slideshow_interval",
        required: false,
        selector: { number: { min: 6, mode: "box" } },
        default: 10
      },
      {
        name: "height",
        required: false,
        selector: { text: {} },
        default: "100%"
      },
      {
        name: "albums",
        required: false,
        selector: { object: {} }
      }
    ];

    const data = {
      slideshow_interval: this._slideshow_interval,
      height: this._height,
      albums: this._albums,
    };

    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${schema}
        .computeLabel=${this._computeLabel}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `;
  }

  _computeLabel(schema) {
    const labels = {
      slideshow_interval: "Slideshow Interval (seconds, min 6)",
      height: "Card Height (e.g. 500px, 100vh)",
      albums: "Album IDs (Optional List)"
    };
    return labels[schema.name] ?? schema.name;
  }

  _valueChanged(ev) {
    if (!this._config || !this.hass) return;
    if (ev.detail.value) {
      this._config = { ...this._config, ...ev.detail.value };
    }
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true
    }));
  }
}

customElements.define("immich-slideshow-editor", ImmichSlideshowEditor);

// ─── Info ─────────────────────────────────────────────────────────────────────

console.info(
  "%cImmichSlideshow Version:" + ImmichSlideshowVersion,
  "color:#fff;background-color:#444"
);