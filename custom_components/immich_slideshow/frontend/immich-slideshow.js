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
      _modalOpen: { state: true },
      _modalSrc: { state: true },
      _modalDate: { state: true },
      _modalLoading: { state: true },
    };
  }

  constructor() {
    super();
    this._slotA = { src: PlaceholderSrc, active: false };
    this._slotB = { src: PlaceholderSrc, active: false };
    this._modalOpen = false;
    this._modalSrc = null;
    this._modalDate = null;
    this._modalLoading = false;
  }

  static getConfigElement() {
    return document.createElement("immich-slideshow-editor");
  }

  static getStubConfig() {
    return {
      slideshow_interval: 10,
      height: 400,
      show_date: true,
      albums: []
    };
  }

  render() {
    return html`
      <ha-card style="overflow:hidden;">
        <div
          class="wrapper ${this.config.open_on_tap !== false ? 'clickable' : ''}"
          style="height:${this.config.height}px"
          @click="${this._openModal}"
        >
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
          ${this.config.show_date && this._activeSlot.date ? html`
            <div class="date-overlay">${this._formatDate(this._activeSlot.date)}</div>
          ` : ''}
        </div>
      </ha-card>

      ${this._modalOpen ? html`
        <div class="modal-backdrop" @click="${this._closeModal}">
          <div class="modal-content" @click="${e => e.stopPropagation()}">
            <img
              src="${this._modalSrc}"
              class="${this._modalLoading ? 'loading' : ''}"
              alt="immich-slideshow-full"
            >
            ${this.config.show_date && this._modalDate ? html`
              <div class="modal-date">${this._formatDate(this._modalDate)}</div>
            ` : ''}
            <button class="modal-close" @click="${this._closeModal}">✕</button>
          </div>
        </div>
      ` : ''}
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
      const { blobUrl: url, date, assetId } = this._prefetchedUrl ?? await this._fetchImageUrl();
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
        this._slotA = { src: url, active: true, assetId, date };
        this._slotB = { ...this._slotB, active: false };
      } else {
        this._slotB = { src: url, active: true, assetId, date };
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

  get _activeSlot() {
    return this._slotA.active ? this._slotA : this._slotB;
  }

  async _openModal() {
    if (this.config.open_on_tap === false) return;
    const { assetId, src, date } = this._activeSlot;

    this._modalSrc = src;
    this._modalDate = date;
    this._modalOpen = true;
    this._modalLoading = true;

    if (assetId) {
      try {
        const response = await this.hass.fetchWithAuth(
          `/api/immich_slideshow/random_image?asset_id=${assetId}&size=preview`
        );
        if (response.ok) {
          const blob = await response.blob();
          if (this._modalPreviewBlob) URL.revokeObjectURL(this._modalPreviewBlob);
          this._modalPreviewBlob = URL.createObjectURL(blob);
          this._modalSrc = this._modalPreviewBlob;
        }
      } catch (e) {
        this._log("Modal preview fetch error: " + e.message);
      }
    }

    this._modalLoading = false;
  }

  _closeModal() {
    this._modalOpen = false;
    if (this._modalPreviewBlob) {
      URL.revokeObjectURL(this._modalPreviewBlob);
      this._modalPreviewBlob = null;
    }
    this._modalSrc = null;
  }

  // ── Network ────────────────────────────────────────────────────────────────

  async _fetchImageUrl() {
    let url = "/api/immich_slideshow/random_image";
    if (this.config.albums?.length > 0) {
      url += "?albums=" + this.config.albums.join(",");
    }
    const response = await this.hass.fetchWithAuth(url);
    if (!response.ok) throw new Error(`Immich proxy error: ${response.status}`);

    const date = response.headers.get("X-Immich-Date") ?? null;
    const assetId = response.headers.get("X-Immich-Asset-Id") ?? null;
    const blob = await response.blob();
    return { blobUrl: URL.createObjectURL(blob), date, assetId };
  }

  // ── Config ─────────────────────────────────────────────────────────────────

  _formatDate(isoString) {
    if (!isoString) return "";
    return new Date(isoString).toLocaleDateString(undefined, {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  setConfig(config) {
    const isconfig = { ...config };

    if (!isconfig.height || isNaN(isconfig.height))
      isconfig.height = 400;
    isconfig.height = parseInt(isconfig.height, 10);

    if (!isconfig.slideshow_interval || isconfig.slideshow_interval < 6)
      isconfig.slideshow_interval = 6;

    if (isconfig.show_date === undefined) isconfig.show_date = true;
    if (isconfig.open_on_tap === undefined) isconfig.open_on_tap = true;

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
      .wrapper.clickable {
        cursor: pointer;
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

      .date-overlay {
        position: absolute;
        bottom: 4px;
        right: 4px;
        z-index: 2;
        color: #fff;
        font-size: 0.78rem;
        font-family: sans-serif;
        letter-spacing: 0.03em;
        background: rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(4px);
        padding: 3px 8px;
        border-radius: 4px;
        pointer-events: none;
        user-select: none;
      }

      .modal-backdrop {
        position: fixed;
        inset: 0;
        z-index: 9999;
        background: rgba(0, 0, 0, 0.85);
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.2s ease;
      }

      .modal-content {
        position: relative;
        max-width: 92vw;
        max-height: 92vh;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .modal-content img {
        position: static;
        width: auto;
        height: auto;
        max-width: 92vw;
        max-height: 92vh;
        object-fit: contain;
        opacity: 1;
        transition: none;
        border-radius: 4px;
        box-shadow: 0 8px 40px rgba(0, 0, 0, 0.6);
      }

      .modal-content img.loading {
        filter: blur(4px);
        transition: filter 0.3s ease;
      }

      .modal-date {
        position: absolute;
        bottom: 10px;
        right: 12px;
        color: #fff;
        font-size: 0.78rem;
        font-family: sans-serif;
        background: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(4px);
        padding: 3px 8px;
        border-radius: 4px;
        pointer-events: none;
      }

      .modal-close {
        position: absolute;
        top: -36px;
        right: 0;
        background: none;
        border: none;
        color: #fff;
        font-size: 1.2rem;
        cursor: pointer;
        opacity: 0.8;
        line-height: 1;
        padding: 4px 8px;
      }

      .modal-close:hover {
        opacity: 1;
      }

      @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
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
  get _show_date() { return this._config?.show_date ?? true; }
  get _open_on_tap() { return this._config?.open_on_tap ?? true; }
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
        selector: { number: { min: 100, mode: "box", unit_of_measurement: "px" } },
        default: 400
      },
      {
        name: "show_date",
        required: false,
        selector: { boolean: {} },
        default: true
      },
      {
        name: "open_on_tap",
        required: false,
        selector: { boolean: {} },
        default: true
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
      show_date: this._show_date,
      open_on_tap: this._open_on_tap,
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
      height: "Card Height (px, e.g. 500)",
      show_date: "Show Date",
      open_on_tap: "Open modal on tap",
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