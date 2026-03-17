var ImmichSlideshowVersion = "2.0.0";
var PlaceholderSrc = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";

import {
  LitElement,
  html,
  css,
} from "https://cdn.jsdelivr.net/gh/lit/dist@3/core/lit-core.min.js";

class ImmichSlideshow extends LitElement {

  static get properties() {
    return {
      hass: {},
      config: {}
    };
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
       <img class="bottom" @load="${this._onBottomLoad}" src="${PlaceholderSrc}" alt="immich-slideshow">
       <img class="top hidden" @error="${this._onTopError}" @load="${this._onTopLoad}" @transitionend="${this._onTopTransitionEnd}" src="${PlaceholderSrc}" alt="immich-slideshow">
      </div>
     </ha-card>
    `;
  }

  firstUpdated() {
    this._doSlideshow();
  }

  _getImg(className) {
    return this.renderRoot.querySelector(".wrapper img." + className);
  }

  _onBottomLoad(e) {
    var bottom = this._getImg("bottom");
    if (bottom.src.startsWith("blob:")) {
      URL.revokeObjectURL(bottom.src);
    }
  }

  _imgErrorCount = 0;
  _maxImgErrorCount = 10;

  _onTopError(e) {
    this._imgErrorCount++;
    if (this._imgErrorCount <= this._maxImgErrorCount) {
      this._log(`Emergency image reloading, attempt ${this._imgErrorCount} of ${this._maxImgErrorCount}.`);
      var top = this._getImg("top");
      URL.revokeObjectURL(top.src);
      top.classList.replace("visible", "hidden");
      setTimeout(()=>{this._nextImage()},500);
    }
    else {
      this._log(`Emergency, reloading image, maximum number of attempts reached (${this._maxImgErrorCount}).`);
    }
  }

  _onTopLoad(e) {
    this._imgErrorCount = 0;
  }

  _onTopTransitionEnd(e) {
    var top = this._getImg("top");
    var bottom = this._getImg("bottom");
    bottom.src = top.src;
    top.classList.replace("visible", "hidden");
  }

  _slideshow = null;
  _doSlideshow() {
    if (this._slideshow != null) {
      clearTimeout(this._slideshow);
      this._slideshow = null;
    }

    this._nextImage();

    this._slideshow = setTimeout(() => {
      this._slideshow = null;
      this._doSlideshow();
    }, this.config.slideshow_interval * 1000);
  }

  async _nextImage() {
    var top = this._getImg("top");
    top.src = await this._getNextImageURL();
    top.classList.replace("hidden", "visible");
  }

  setConfig(config) {
    var isconfig = Object.create(config);

    if (!isconfig.height)
      isconfig.height = "100%";
    if (!isconfig.slideshow_interval || isconfig.slideshow_interval < 6)
      isconfig.slideshow_interval = 6;

    let albums = isconfig.albums;
    if (albums) {
      isconfig.albums = Array.isArray(albums) ? albums : [albums];
    }

    this.config = isconfig;
  }

  getCardSize() {
    return 1;
  }

  //--------------------------------------------------------------------------------------------------
  // Image fetching via Home Assistant backend proxy (no CORS!)

  async _getNextImageURL() {
    let url = "/api/immich_slideshow/random_image";

    if (this.config.albums && this.config.albums.length > 0) {
      url += "?albums=" + this.config.albums.join(",");
    }

    const response = await this.hass.fetchWithAuth(url);
    if (!response.ok) {
      throw new Error(`Immich proxy error: ${response.status}`);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  }

  //--------------------------------------------------------------------------------------------------
  //Common functions

  _log(message) {
    console.log(`Immich-Slideshow -> ${message}`);
  }

  static get styles() {
    return css`
    .wrapper {
     position: relative;
     width: 100%;
     overflow: hidden;
    }

    img {
     width: 100%;
     height: 100%;
     object-fit: cover;
    }

    img.bottom {
     position: relative;
    }

    img.top {
     position: absolute;
     top: 0;
     left: 0;
    }

    img.visible {
     transition: all 5s ease-in;
     opacity: 1;
     filter: grayscale(0%);
    }

    img.hidden {
     transition: none;
     opacity: 0;
     filter: grayscale(100%);
    }`;
  }
}//End of ImmichSlideshow class

customElements.define("immich-slideshow", ImmichSlideshow);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "immich-slideshow",
  name: "Immich Slideshow",
  description: "A custom card that displays a slideshow of images from an Immich server."
});

class ImmichSlideshowEditor extends LitElement {
  setConfig(config) {
    this._config = { ...config };
  }

  static get properties() {
    return { hass: {}, _config: {} };
  }

  get _slideshow_interval() { return this._config.slideshow_interval || 10; }
  get _height() { return this._config.height || "100%"; }
  get _albums() { return this._config.albums || []; }

  render() {
    if (!this.hass) {
      return html``;
    }

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
      albums: this._albums
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
    return labels[schema.name] || schema.name;
  }

  _valueChanged(ev) {
    if (!this._config || !this.hass) {
      return;
    }
    if (ev.detail.value) {
      this._config = { ...ev.detail.value };
    }
    const event = new CustomEvent("config-changed", {
      detail: { config: this._config },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }
}

customElements.define("immich-slideshow-editor", ImmichSlideshowEditor);

//--------------------------------------------------------------------------------------------------
//INFO
let infoStyles = [
  "color: #fff",
  "background-color: #444"
].join(";");
console.info("%cImmichSlideshow Version:" + ImmichSlideshowVersion, infoStyles);
