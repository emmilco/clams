/**
 * Cluster Sphere Component
 *
 * Manages translucent spherical boundaries around cluster groups.
 * - Purple color (#9E4AFF) with low opacity
 * - Animatable radius (for forming/dissolving)
 */
import { CONFIG } from '../config.js';

/**
 * Cluster Sphere
 * Creates a translucent spherical boundary to visualize a cluster
 */
export class ClusterSphere {
  /**
   * Create a new ClusterSphere
   * @param {Object} threeScene - The Three.js scene API from three-setup.js
   * @param {Object} options - Configuration options
   * @param {number} options.x - Center X position (default: 0)
   * @param {number} options.y - Center Y position (default: 0)
   * @param {number} options.z - Center Z position (default: 0)
   * @param {number} options.radius - Initial radius (default: 5)
   * @param {number} options.color - Sphere color as hex (default: purple)
   * @param {number} options.opacity - Sphere opacity (default from config)
   * @param {number} options.segments - Sphere geometry detail (default: 32)
   */
  constructor(threeScene, options = {}) {
    this.threeScene = threeScene;

    // Position
    this.x = options.x ?? 0;
    this.y = options.y ?? 0;
    this.z = options.z ?? 0;

    // Appearance
    this.radius = options.radius ?? 5;
    this.color = new THREE.Color(options.color ?? CONFIG.colorsHex.accent.purple);
    this.opacity = options.opacity ?? CONFIG.clusters.sphereOpacity;
    this.segments = options.segments ?? 32;

    // Create geometry
    this.geometry = new THREE.SphereGeometry(1, this.segments, this.segments);

    // Create material - translucent with double-sided rendering
    this.material = new THREE.MeshBasicMaterial({
      color: this.color,
      transparent: true,
      opacity: this.opacity,
      side: THREE.DoubleSide,
      depthWrite: false
    });

    // Create mesh
    this.mesh = new THREE.Mesh(this.geometry, this.material);
    this.mesh.position.set(this.x, this.y, this.z);
    this.mesh.scale.set(this.radius, this.radius, this.radius);

    // Add wireframe for better visibility
    this.wireframeMaterial = new THREE.MeshBasicMaterial({
      color: this.color,
      transparent: true,
      opacity: this.opacity * 2, // Slightly more visible
      wireframe: true
    });
    this.wireframeMesh = new THREE.Mesh(this.geometry, this.wireframeMaterial);
    this.wireframeMesh.position.copy(this.mesh.position);
    this.wireframeMesh.scale.copy(this.mesh.scale);

    // Group to hold both solid and wireframe
    this.group = new THREE.Group();
    this.group.add(this.mesh);
    this.group.add(this.wireframeMesh);

    // Initially hidden
    this.group.visible = false;

    // Add to scene
    this.threeScene.addObject(this.group);
  }

  /**
   * Set sphere visibility
   * @param {boolean} visible
   */
  setVisible(visible) {
    this.group.visible = visible;
  }

  /**
   * Set sphere radius
   * @param {number} radius - New radius
   */
  setRadius(radius) {
    this.radius = radius;
    this.mesh.scale.set(radius, radius, radius);
    this.wireframeMesh.scale.set(radius, radius, radius);
  }

  /**
   * Set sphere position
   * @param {number} x
   * @param {number} y
   * @param {number} z
   */
  setPosition(x, y, z) {
    this.x = x;
    this.y = y;
    this.z = z;
    this.mesh.position.set(x, y, z);
    this.wireframeMesh.position.set(x, y, z);
  }

  /**
   * Set sphere opacity
   * @param {number} opacity - New opacity (0-1)
   */
  setOpacity(opacity) {
    this.opacity = opacity;
    this.material.opacity = opacity;
    this.wireframeMaterial.opacity = opacity * 2;
  }

  /**
   * Set sphere color
   * @param {number|string} color - Color as hex number or string
   */
  setColor(color) {
    this.color.set(color);
    this.material.color.copy(this.color);
    this.wireframeMaterial.color.copy(this.color);
  }

  /**
   * Get animatable object for radius (for GSAP)
   * @returns {Object} Object with radius property
   */
  getRadiusAnimatable() {
    const self = this;
    return {
      get radius() {
        return self.radius;
      },
      set radius(value) {
        self.setRadius(value);
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
      set x(value) { self.x = value; self.mesh.position.x = value; self.wireframeMesh.position.x = value; },
      get y() { return self.y; },
      set y(value) { self.y = value; self.mesh.position.y = value; self.wireframeMesh.position.y = value; },
      get z() { return self.z; },
      set z(value) { self.z = value; self.mesh.position.z = value; self.wireframeMesh.position.z = value; }
    };
  }

  /**
   * Dispose of resources
   */
  dispose() {
    this.threeScene.removeObject(this.group);
    this.geometry.dispose();
    this.material.dispose();
    this.wireframeMaterial.dispose();
  }
}

/**
 * Cluster Sphere Manager
 * Manages multiple cluster spheres
 */
export class ClusterSphereManager {
  /**
   * Create a new ClusterSphereManager
   * @param {Object} threeScene - The Three.js scene API from three-setup.js
   */
  constructor(threeScene) {
    this.threeScene = threeScene;
    this.spheres = [];
  }

  /**
   * Add a new cluster sphere
   * @param {Object} options - ClusterSphere options
   * @returns {ClusterSphere}
   */
  addSphere(options = {}) {
    const sphere = new ClusterSphere(this.threeScene, options);
    this.spheres.push(sphere);
    return sphere;
  }

  /**
   * Add multiple spheres at once
   * @param {Array<Object>} sphereConfigs - Array of sphere configurations
   * @returns {Array<ClusterSphere>}
   */
  addSpheres(sphereConfigs) {
    return sphereConfigs.map(config => this.addSphere(config));
  }

  /**
   * Get a sphere by index
   * @param {number} index
   * @returns {ClusterSphere|null}
   */
  getSphere(index) {
    return this.spheres[index] || null;
  }

  /**
   * Set visibility for all spheres
   * @param {boolean} visible
   */
  setAllVisible(visible) {
    this.spheres.forEach(sphere => sphere.setVisible(visible));
  }

  /**
   * Clear all spheres
   */
  clear() {
    this.spheres.forEach(sphere => sphere.dispose());
    this.spheres = [];
  }

  /**
   * Dispose of all resources
   */
  dispose() {
    this.clear();
  }

  /**
   * Get the total number of spheres
   * @returns {number}
   */
  get count() {
    return this.spheres.length;
  }
}

/**
 * Create a ClusterSphereManager instance
 * @param {Object} threeScene - The Three.js scene API from three-setup.js
 * @returns {ClusterSphereManager}
 */
export function createClusterSphereManager(threeScene) {
  return new ClusterSphereManager(threeScene);
}

/**
 * Create a single ClusterSphere instance
 * @param {Object} threeScene - The Three.js scene API from three-setup.js
 * @param {Object} options - Configuration options
 * @returns {ClusterSphere}
 */
export function createClusterSphere(threeScene, options = {}) {
  return new ClusterSphere(threeScene, options);
}
