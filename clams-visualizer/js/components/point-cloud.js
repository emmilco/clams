/**
 * Point Cloud Component
 *
 * Manages 3D point visualization for GHAP entries in vector space.
 * - Points have soft radial gradient glow (sprite with radial texture)
 * - Depth cues: size scaling and opacity fade based on distance
 * - Default color: blue (#4A9EFF)
 */
import { CONFIG } from '../config.js';

/**
 * Create a radial gradient texture for point sprites
 * @param {number} size - Texture size in pixels
 * @param {THREE.Color} color - Point color
 * @returns {THREE.CanvasTexture} Radial gradient texture
 */
function createGlowTexture(size = 64, color = null) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  // Create radial gradient from center
  const gradient = ctx.createRadialGradient(
    size / 2, size / 2, 0,      // Inner circle (center)
    size / 2, size / 2, size / 2 // Outer circle (edge)
  );

  // Default to blue color if not specified
  const r = color ? Math.floor(color.r * 255) : 74;
  const g = color ? Math.floor(color.g * 255) : 158;
  const b = color ? Math.floor(color.b * 255) : 255;

  // Gradient stops: bright center, fading edges
  gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 1.0)`);
  gradient.addColorStop(0.2, `rgba(${r}, ${g}, ${b}, 0.8)`);
  gradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, 0.3)`);
  gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

/**
 * Point Cloud Manager
 * Creates and manages a collection of 3D glowing points
 */
export class PointCloud {
  /**
   * Create a new PointCloud
   * @param {Object} threeScene - The Three.js scene API from three-setup.js
   * @param {Object} options - Configuration options
   * @param {number} options.color - Point color as hex (default: blue)
   * @param {number} options.baseSize - Base point size (default from config)
   * @param {number} options.glowIntensity - Glow intensity (default from config)
   */
  constructor(threeScene, options = {}) {
    this.threeScene = threeScene;
    this.color = new THREE.Color(options.color ?? CONFIG.colorsHex.accent.blue);
    this.baseSize = options.baseSize ?? CONFIG.pointCloud.baseSize;
    this.glowIntensity = options.glowIntensity ?? CONFIG.pointCloud.glowIntensity;

    // Container group for all points
    this.group = new THREE.Group();
    this.threeScene.addObject(this.group);

    // Store individual point sprites for manipulation
    this.points = [];

    // Create glow texture
    this.glowTexture = createGlowTexture(64, this.color);

    // Create material for sprites
    this.spriteMaterial = new THREE.SpriteMaterial({
      map: this.glowTexture,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
  }

  /**
   * Add a single point to the cloud
   * @param {number} x - X position
   * @param {number} y - Y position
   * @param {number} z - Z position
   * @param {Object} options - Point options
   * @param {number} options.scale - Size multiplier (default: 1)
   * @param {number} options.opacity - Initial opacity (default: 1)
   * @param {number} options.color - Override color as hex
   * @returns {Object} Point object with sprite and metadata
   */
  addPoint(x, y, z, options = {}) {
    const scale = options.scale ?? 1;
    const opacity = options.opacity ?? 1;

    // Create sprite for this point
    let material = this.spriteMaterial;

    // If custom color, create new material
    if (options.color !== undefined) {
      const customColor = new THREE.Color(options.color);
      const customTexture = createGlowTexture(64, customColor);
      material = new THREE.SpriteMaterial({
        map: customTexture,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        opacity: opacity
      });
    } else {
      // Clone the shared material for independent opacity control
      material = this.spriteMaterial.clone();
      material.opacity = opacity;
    }

    const sprite = new THREE.Sprite(material);
    sprite.position.set(x, y, z);

    // Size based on distance for depth cue (will be updated in updateDepthCues)
    const size = this.baseSize * scale;
    sprite.scale.set(size, size, 1);

    // Store original scale for depth calculations
    sprite.userData = {
      originalScale: scale,
      baseOpacity: opacity
    };

    this.group.add(sprite);
    this.points.push(sprite);

    return {
      sprite,
      index: this.points.length - 1,
      position: new THREE.Vector3(x, y, z)
    };
  }

  /**
   * Add multiple points at once
   * @param {Array<{x: number, y: number, z: number, options?: Object}>} positions
   * @returns {Array<Object>} Array of point objects
   */
  addPoints(positions) {
    return positions.map(({ x, y, z, options }) => this.addPoint(x, y, z, options));
  }

  /**
   * Generate random points within a spherical volume
   * @param {number} count - Number of points to generate
   * @param {number} radius - Maximum radius from center
   * @param {Object} options - Options for each point
   * @returns {Array<Object>} Array of point objects
   */
  generateRandomPoints(count, radius, options = {}) {
    const points = [];
    for (let i = 0; i < count; i++) {
      // Generate random point in sphere using rejection sampling
      let x, y, z;
      do {
        x = (Math.random() - 0.5) * 2 * radius;
        y = (Math.random() - 0.5) * 2 * radius;
        z = (Math.random() - 0.5) * 2 * radius;
      } while (x * x + y * y + z * z > radius * radius);

      points.push(this.addPoint(x, y, z, options));
    }
    return points;
  }

  /**
   * Update depth cues based on camera position
   * Call this each frame or when camera moves
   */
  updateDepthCues() {
    if (!this.threeScene.camera) return;

    const cameraPosition = this.threeScene.camera.position;

    this.points.forEach(sprite => {
      // Calculate distance from camera
      const distance = sprite.position.distanceTo(cameraPosition);

      // Normalize distance (0-1 based on fog range)
      const normalizedDistance = Math.max(0, Math.min(1,
        (distance - CONFIG.fog.near) / (CONFIG.fog.far - CONFIG.fog.near)
      ));

      // Apply depth cues
      // Size scaling: closer = larger, farther = smaller
      const depthScale = 1 - normalizedDistance * 0.5; // Scale from 1.0 to 0.5
      const originalScale = sprite.userData.originalScale || 1;
      const size = this.baseSize * originalScale * depthScale;
      sprite.scale.set(size, size, 1);

      // Opacity fade: closer = more opaque, farther = more transparent
      const baseOpacity = sprite.userData.baseOpacity || 1;
      const depthOpacity = 1 - normalizedDistance * 0.7; // Fade from 1.0 to 0.3
      sprite.material.opacity = baseOpacity * depthOpacity;
    });
  }

  /**
   * Animate a point's opacity
   * @param {number} index - Point index
   * @param {number} opacity - Target opacity (0-1)
   * @returns {Object} Animatable object for GSAP
   */
  getPointOpacityAnimatable(index) {
    const sprite = this.points[index];
    if (!sprite) return null;

    return {
      get opacity() {
        return sprite.userData.baseOpacity || 1;
      },
      set opacity(value) {
        sprite.userData.baseOpacity = value;
        sprite.material.opacity = value;
      }
    };
  }

  /**
   * Animate a point's scale
   * @param {number} index - Point index
   * @returns {Object} Animatable object for GSAP
   */
  getPointScaleAnimatable(index) {
    const sprite = this.points[index];
    if (!sprite) return null;

    const baseSize = this.baseSize;
    return {
      get scale() {
        return sprite.userData.originalScale || 1;
      },
      set scale(value) {
        sprite.userData.originalScale = value;
        const size = baseSize * value;
        sprite.scale.set(size, size, 1);
      }
    };
  }

  /**
   * Animate a point's position
   * @param {number} index - Point index
   * @returns {Object} Animatable object for GSAP with x, y, z properties
   */
  getPointPositionAnimatable(index) {
    const sprite = this.points[index];
    if (!sprite) return null;

    return sprite.position;
  }

  /**
   * Get all point positions as an array
   * @returns {Array<THREE.Vector3>} Array of position vectors
   */
  getPositions() {
    return this.points.map(sprite => sprite.position.clone());
  }

  /**
   * Set visibility of all points
   * @param {boolean} visible
   */
  setVisible(visible) {
    this.group.visible = visible;
  }

  /**
   * Set visibility of a specific point
   * @param {number} index - Point index
   * @param {boolean} visible
   */
  setPointVisible(index, visible) {
    if (this.points[index]) {
      this.points[index].visible = visible;
    }
  }

  /**
   * Remove a specific point
   * @param {number} index - Point index
   */
  removePoint(index) {
    const sprite = this.points[index];
    if (sprite) {
      this.group.remove(sprite);
      if (sprite.material !== this.spriteMaterial) {
        sprite.material.dispose();
      }
      this.points.splice(index, 1);
    }
  }

  /**
   * Clear all points
   */
  clear() {
    this.points.forEach(sprite => {
      this.group.remove(sprite);
      if (sprite.material !== this.spriteMaterial) {
        sprite.material.dispose();
      }
    });
    this.points = [];
  }

  /**
   * Dispose of resources
   */
  dispose() {
    this.clear();
    this.threeScene.removeObject(this.group);
    this.glowTexture.dispose();
    this.spriteMaterial.dispose();
  }

  /**
   * Get the total number of points
   * @returns {number}
   */
  get count() {
    return this.points.length;
  }
}

/**
 * Create a PointCloud instance
 * @param {Object} threeScene - The Three.js scene API from three-setup.js
 * @param {Object} options - Configuration options
 * @returns {PointCloud}
 */
export function createPointCloud(threeScene, options = {}) {
  return new PointCloud(threeScene, options);
}
