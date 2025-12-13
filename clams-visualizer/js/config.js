/**
 * Configuration constants for the CLAMS Animated Explainer
 *
 * All timing, colors, and position constants are centralized here
 * to make the animation easier to tune and maintain.
 */
export const CONFIG = {
  // Timing (in seconds)
  timing: {
    act1: { start: 0, end: 45 },
    act2: { start: 45, end: 135 },
    act3: { start: 135, end: 180 },
    total: 180
  },

  // Scene-specific timing within acts (relative to act start)
  scenes: {
    act1: {
      problemStatement: { start: 0, duration: 15 },
      pillars: { start: 15, duration: 30 }
    },
    act2: {
      ghapDemo: { start: 0, duration: 25 },
      embedding: { start: 25, duration: 20 },
      clustering: { start: 45, duration: 25 },
      valueExtraction: { start: 70, duration: 20 }
    },
    act3: {
      sessionStart: { start: 0, duration: 12 },
      semanticRetrieval: { start: 12, duration: 15 },
      contextInjection: { start: 27, duration: 13 },
      closing: { start: 40, duration: 5 }
    }
  },

  // Colors (from spec)
  colors: {
    background: '#000000',
    primary: '#FFFFFF',
    secondary: '#CCCCCC',
    accent: {
      blue: '#4A9EFF',     // GHAP/memory elements
      green: '#4AFF9E',    // Success/confirmations
      orange: '#FFAA4A',   // Attention/warnings
      purple: '#9E4AFF'    // Clustering/values
    }
  },

  // Colors as hex numbers (for Three.js)
  colorsHex: {
    background: 0x000000,
    primary: 0xFFFFFF,
    secondary: 0xCCCCCC,
    accent: {
      blue: 0x4A9EFF,
      green: 0x4AFF9E,
      orange: 0xFFAA4A,
      purple: 0x9E4AFF
    }
  },

  // 3D Scene Configuration
  camera: {
    fov: 60,
    near: 0.1,
    far: 1000,
    initialPosition: { x: 0, y: 0, z: 100 }
  },

  // Point cloud settings
  pointCloud: {
    count: 50,           // Number of GHAP points
    spread: 40,          // Spread radius
    baseSize: 0.8,
    glowIntensity: 0.6
  },

  // Cluster visualization settings
  clusters: {
    count: 5,
    sphereOpacity: 0.15,
    centroidSize: 2.0
  },

  // Camera orbit settings
  orbit: {
    radiusPerMinute: 20,  // Degrees per minute
    tiltAngle: 15
  },

  // Fog for depth cues
  fog: {
    near: 80,   // Fog begins (units from camera)
    far: 200    // Fog fully opaque (objects invisible beyond this)
  },

  // DOM element positions (for reference)
  positions: {
    title: { x: '50%', y: '15%' },
    subtitle: { x: '50%', y: '25%' },
    ghapCard: { x: '10%', y: '25%' },
    explanation: { x: '50%', y: '80%' }
  }
};

// Convenience: Act start times in seconds
export const ACT_TIMES = {
  act1: CONFIG.timing.act1.start,
  act2: CONFIG.timing.act2.start,
  act3: CONFIG.timing.act3.start
};

// Total animation duration
export const TOTAL_DURATION = CONFIG.timing.total;
