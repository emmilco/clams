/**
 * Centroid Component
 *
 * Manages cluster center markers (centroids).
 * - Brighter/larger point marker at cluster center
 * - Purple color (#9E4AFF)
 * - Animatable scale and opacity
 */
import { CONFIG } from '../config.js';

/**
 * Create a radial gradient texture for centroid sprites (brighter than regular points)
 * @param {number} size - Texture size in pixels
 * @param {THREE.Color} color - Centroid color
 * @returns {THREE.CanvasTexture} Radial gradient texture
 */
function createCentroidGlowTexture(size = 128, color = null) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  // Default to purple color if not specified
  const r = color ? Math.floor(color.r * 255) : 158;
  const g = color ? Math.floor(color.g * 255) : 74;
  const b = color ? Math.floor(color.b * 255) : 255;

  // Create radial gradient from center - brighter than regular points
  const gradient = ctx.createRadialGradient(
    size / 2, size / 2, 0,      // Inner circle (center)
    size / 2, size / 2, size / 2 // Outer circle (edge)
  );

  // Gradient stops: very bright center, extended glow
  gradient.addColorStop(0, `rgba(255, 255, 255, 1.0)`); // White hot center
  gradient.addColorStop(0.1, `rgba(${r}, ${g}, ${b}, 1.0)`);
  gradient.addColorStop(0.3, `rgba(${r}, ${g}, ${b}, 0.7)`);
  gradient.addColorStop(0.6, `rgba(${r}, ${g}, ${b}, 0.3)`);
  gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

/**
 * Centroid
 * A brighter, larger marker at a cluster's center
 */
export class Centroid {
  /**
   * Create a new Centroid
   * @param {Object} threeScene - The Three.js scene API from three-setup.js
   * @param {Object} options - Configuration options
   * @param {number} options.x - Center X position (default: 0)
   * @param {number} options.y - Center Y position (default: 0)
   * @param {number} options.z - Center Z position (default: 0)
   * @param {number} options.size - Centroid size (default from config)
   * @param {number} options.color - Centroid color as hex (default: purple)
   * @param {number} options.opacity - Initial opacity (default: 1)
   */
  constructor(threeScene, options = {}) {
    this.threeScene = threeScene;

    // Position
    this.x = options.x ?? 0;
    this.y = options.y ?? 0;
    this.z = options.z ?? 0;

    // Appearance
    this.size = options.size ?? CONFIG.clusters.centroidSize;
    this.color = new THREE.Color(options.color ?? CONFIG.colorsHex.accent.purple);
    this.opacity = options.opacity ?? 1;
    this.scale = 1;

    // Create glow texture
    this.glowTexture = createCentroidGlowTexture(128, this.color);

    // Create material
    this.material = new THREE.SpriteMaterial({
      map: this.glowTexture,
      transparent: true,
      opacity: this.opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    // Create sprite
    this.sprite = new THREE.Sprite(this.material);
    this.sprite.position.set(this.x, this.y, this.z);
    this.updateSpriteScale();

    // Initially hidden
    this.sprite.visible = false;

    // Add to scene
    this.threeScene.addObject(this.sprite);
  }

  /**
   * Update sprite scale based on size and scale multiplier
   */
  updateSpriteScale() {
    const totalSize = this.size * this.scale;
    this.sprite.scale.set(totalSize, totalSize, 1);
  }

  /**
   * Set centroid visibility
   * @param {boolean} visible
   */
  setVisible(visible) {
    this.sprite.visible = visible;
  }

  /**
   * Set centroid position
   * @param {number} x
   * @param {number} y
   * @param {number} z
   */
  setPosition(x, y, z) {
    this.x = x;
    this.y = y;
    this.z = z;
    this.sprite.position.set(x, y, z);
  }

  /**
   * Set centroid scale multiplier
   * @param {number} scale - Scale multiplier (1 = default size)
   */
  setScale(scale) {
    this.scale = scale;
    this.updateSpriteScale();
  }

  /**
   * Set centroid opacity
   * @param {number} opacity - Opacity (0-1)
   */
  setOpacity(opacity) {
    this.opacity = opacity;
    this.material.opacity = opacity;
  }

  /**
   * Set centroid size (base size before scale multiplier)
   * @param {number} size - New base size
   */
  setSize(size) {
    this.size = size;
    this.updateSpriteScale();
  }

  /**
   * Get animatable object for scale (for GSAP)
   * @returns {Object} Object with scale property
   */
  getScaleAnimatable() {
    const self = this;
    return {
      get scale() {
        return self.scale;
      },
      set scale(value) {
        self.setScale(value);
      }
    };
  }

  /**
   * Get animatable object for opacity (for GSAP)
   * @returns {Object} Object with opacity property
   */
  getOpacityAnimatable() {
    const self = this;
    return {
      get opacity() {
        return self.opacity;
      },
      set opacity(value) {
        self.setOpacity(value);
      }
    };
  }

  /**
   * Get animatable object for position (for GSAP)
   * @returns {Object} Object with x, y, z properties
   */
  getPositionAnimatable() {
    const self = this;
    return {
      get x() { return self.x; },
      set x(value) { self.x = value; self.sprite.position.x = value; },
      get y() { return self.y; },
      set y(value) { self.y = value; self.sprite.position.y = value; },
      get z() { return self.z; },
      set z(value) { self.z = value; self.sprite.position.z = value; }
    };
  }

  /**
   * Dispose of resources
   */
  dispose() {
    this.threeScene.removeObject(this.sprite);
    this.glowTexture.dispose();
    this.material.dispose();
  }
}

/**
 * Centroid Manager
 * Manages multiple centroids
 */
export class CentroidManager {
  /**
   * Create a new CentroidManager
   * @param {Object} threeScene - The Three.js scene API from three-setup.js
   */
  constructor(threeScene) {
    this.threeScene = threeScene;
    this.centroids = [];
  }

  /**
   * Add a new centroid
   * @param {Object} options - Centroid options
   * @returns {Centroid}
   */
  addCentroid(options = {}) {
    const centroid = new Centroid(this.threeScene, options);
    this.centroids.push(centroid);
    return centroid;
  }

  /**
   * Add multiple centroids at once
   * @param {Array<Object>} centroidConfigs - Array of centroid configurations
   * @returns {Array<Centroid>}
   */
  addCentroids(centroidConfigs) {
    return centroidConfigs.map(config => this.addCentroid(config));
  }

  /**
   * Get a centroid by index
   * @param {number} index
   * @returns {Centroid|null}
   */
  getCentroid(index) {
    return this.centroids[index] || null;
  }

  /**
   * Set visibility for all centroids
   * @param {boolean} visible
   */
  setAllVisible(visible) {
    this.centroids.forEach(centroid => centroid.setVisible(visible));
  }

  /**
   * Clear all centroids
   */
  clear() {
    this.centroids.forEach(centroid => centroid.dispose());
    this.centroids = [];
  }

  /**
   * Dispose of all resources
   */
  dispose() {
    this.clear();
  }

  /**
   * Get the total number of centroids
   * @returns {number}
   */
  get count() {
    return this.centroids.length;
  }
}

/**
 * Create a CentroidManager instance
 * @param {Object} threeScene - The Three.js scene API from three-setup.js
 * @returns {CentroidManager}
 */
export function createCentroidManager(threeScene) {
  return new CentroidManager(threeScene);
}

/**
 * Create a single Centroid instance
 * @param {Object} threeScene - The Three.js scene API from three-setup.js
 * @param {Object} options - Configuration options
 * @returns {Centroid}
 */
export function createCentroid(threeScene, options = {}) {
  return new Centroid(threeScene, options);
}
