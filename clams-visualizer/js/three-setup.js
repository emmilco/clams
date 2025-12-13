/**
 * Three.js Scene Setup
 *
 * Initializes and manages the Three.js 3D scene for CLAMS visualizer.
 * - Creates scene with black background
 * - Sets up perspective camera with orbit capability
 * - Manages WebGL renderer attached to #three-canvas
 * - Handles window resize
 * - Provides timeline-controlled camera orbit
 */
import { CONFIG } from './config.js';

// Scene state (module-level for access by components)
let scene = null;
let camera = null;
let renderer = null;
let isInitialized = false;

// Camera orbit state
let cameraOrbitAngle = 0;
const cameraOrbitRadius = CONFIG.camera.initialPosition.z;

/**
 * Wait for Three.js to be available
 * @returns {Promise<void>}
 */
function waitForThree() {
  return new Promise((resolve, reject) => {
    if (typeof THREE !== 'undefined') {
      resolve();
      return;
    }

    // Poll for Three.js (in case CDN is slow)
    let attempts = 0;
    const maxAttempts = 50; // 5 seconds max wait
    const interval = setInterval(() => {
      attempts++;
      if (typeof THREE !== 'undefined') {
        clearInterval(interval);
        resolve();
      } else if (attempts >= maxAttempts) {
        clearInterval(interval);
        reject(new Error('Three.js failed to load'));
      }
    }, 100);
  });
}

/**
 * Initialize the Three.js scene
 * @returns {Promise<Object>} Scene API object
 */
export async function initThreeScene() {
  if (isInitialized) {
    console.warn('[Three] Scene already initialized');
    return getSceneAPI();
  }

  try {
    await waitForThree();
    console.log('[Three] Three.js loaded successfully');
  } catch (e) {
    console.error('[Three] Failed to load Three.js:', e);
    throw e;
  }

  // Get canvas element
  const canvas = document.getElementById('three-canvas');
  if (!canvas) {
    throw new Error('Canvas element #three-canvas not found');
  }

  // Create scene with black background
  scene = new THREE.Scene();
  scene.background = new THREE.Color(CONFIG.colorsHex.background);

  // Add fog for depth cues (makes distant objects fade)
  scene.fog = new THREE.Fog(
    CONFIG.colorsHex.background,
    CONFIG.fog.near,
    CONFIG.fog.far
  );

  // Create perspective camera
  camera = new THREE.PerspectiveCamera(
    CONFIG.camera.fov,
    window.innerWidth / window.innerHeight,
    CONFIG.camera.near,
    CONFIG.camera.far
  );
  camera.position.set(
    CONFIG.camera.initialPosition.x,
    CONFIG.camera.initialPosition.y,
    CONFIG.camera.initialPosition.z
  );
  camera.lookAt(0, 0, 0);

  // Create WebGL renderer
  renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    antialias: true,
    alpha: false
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // Handle window resize
  window.addEventListener('resize', handleResize);

  isInitialized = true;
  console.log('[Three] Scene initialized successfully');

  return getSceneAPI();
}

/**
 * Handle window resize
 */
function handleResize() {
  if (!camera || !renderer) return;

  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

/**
 * Set camera orbit angle (controlled by timeline)
 * @param {number} degrees - Orbit angle in degrees (0-360)
 */
function setCameraOrbit(degrees) {
  if (!camera) return;

  cameraOrbitAngle = degrees;
  const radians = (degrees * Math.PI) / 180;
  const tiltRadians = (CONFIG.orbit.tiltAngle * Math.PI) / 180;

  // Calculate camera position on orbit circle
  camera.position.x = Math.sin(radians) * cameraOrbitRadius;
  camera.position.z = Math.cos(radians) * cameraOrbitRadius;
  camera.position.y = Math.sin(tiltRadians) * cameraOrbitRadius * 0.2;

  camera.lookAt(0, 0, 0);
}

/**
 * Get current camera orbit angle
 * @returns {number} Current orbit angle in degrees
 */
function getCameraOrbit() {
  return cameraOrbitAngle;
}

/**
 * Render the scene (call this each frame)
 */
function render() {
  if (!renderer || !scene || !camera) return;
  renderer.render(scene, camera);
}

/**
 * Start the render loop
 * This is for real-time rendering; timeline animations will call render() directly
 */
function startRenderLoop() {
  function animate() {
    requestAnimationFrame(animate);
    render();
  }
  animate();
}

/**
 * Get the Scene API object for external use
 * @returns {Object} API object with scene access and controls
 */
function getSceneAPI() {
  return {
    // Core Three.js objects (for components to add objects)
    scene,
    camera,
    renderer,

    // Camera controls (for timeline)
    setCameraOrbit,
    getCameraOrbit,

    // Rendering
    render,
    startRenderLoop,

    // State
    isInitialized: () => isInitialized,

    // Utility: Add object to scene
    addObject(object) {
      if (scene && object) {
        scene.add(object);
      }
    },

    // Utility: Remove object from scene
    removeObject(object) {
      if (scene && object) {
        scene.remove(object);
      }
    },

    // Utility: Get scene center
    getCenter() {
      return new THREE.Vector3(0, 0, 0);
    },

    // Utility: Get camera look direction
    getCameraDirection() {
      const dir = new THREE.Vector3();
      camera.getWorldDirection(dir);
      return dir;
    }
  };
}

/**
 * Dispose of Three.js resources (call on cleanup)
 */
export function disposeThreeScene() {
  if (renderer) {
    renderer.dispose();
  }

  window.removeEventListener('resize', handleResize);

  scene = null;
  camera = null;
  renderer = null;
  isInitialized = false;

  console.log('[Three] Scene disposed');
}

/**
 * Integration helpers for GSAP timeline
 *
 * These functions return objects that GSAP can animate.
 * Example usage in timeline:
 *   timeline.to(threeScene.getOrbitAnimatable(), {
 *     angle: 30,
 *     duration: 60,
 *     onUpdate: () => threeScene.render()
 *   }, 45);
 */

/**
 * Get an animatable object for camera orbit
 * GSAP can animate the 'angle' property
 * @returns {Object} Object with angle property
 */
export function createOrbitAnimatable() {
  const animatable = { angle: 0 };

  // Create a proxy that updates camera when angle changes
  return new Proxy(animatable, {
    set(target, prop, value) {
      if (prop === 'angle') {
        target[prop] = value;
        setCameraOrbit(value);
      }
      return true;
    }
  });
}
