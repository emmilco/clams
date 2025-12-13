/**
 * CLAMS Animated Explainer - Main Entry Point
 *
 * This is the main JavaScript file that:
 * 1. Checks for WebGL support
 * 2. Creates the master GSAP timeline
 * 3. Sets up timeline controls
 * 4. Initializes all act scenes
 */
import { CONFIG, TOTAL_DURATION, ACT_TIMES } from './config.js';
import { initTimelineControls } from './timeline-controller.js';
import { setupAct1 } from './scenes/act1.js';
import { setupAct2 } from './scenes/act2.js';
import { setupAct3 } from './scenes/act3.js';

// Check WebGL support (additional check in case module loads before inline script)
function checkWebGLSupport() {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    return !!gl;
  } catch (e) {
    return false;
  }
}

// Wait for GSAP to be available
function waitForGSAP() {
  return new Promise((resolve, reject) => {
    if (typeof gsap !== 'undefined') {
      resolve();
      return;
    }

    // Poll for GSAP (in case CDN is slow)
    let attempts = 0;
    const maxAttempts = 50; // 5 seconds max wait
    const interval = setInterval(() => {
      attempts++;
      if (typeof gsap !== 'undefined') {
        clearInterval(interval);
        resolve();
      } else if (attempts >= maxAttempts) {
        clearInterval(interval);
        reject(new Error('GSAP failed to load'));
      }
    }, 100);
  });
}

// Main initialization
async function init() {
  console.log('CLAMS Visualizer: Initializing...');

  // Check WebGL
  if (!checkWebGLSupport()) {
    console.error('WebGL not supported');
    return;
  }

  // Wait for GSAP
  try {
    await waitForGSAP();
    console.log('GSAP loaded successfully');
  } catch (e) {
    console.error('Failed to load GSAP:', e);
    return;
  }

  // Create master timeline (paused initially)
  const master = gsap.timeline({
    paused: true,
    onUpdate: () => {
      // Update timeline UI on each frame
      timelineUI.update(master.time(), master.duration());
    },
    onComplete: () => {
      console.log('Animation complete!');
      timelineUI.setPlaying(false);
    }
  });

  // Initialize timeline controls
  const timelineUI = initTimelineControls(master);
  console.log('Timeline controls initialized');

  // Setup each act
  // Each act function adds its animations to the master timeline
  // and returns the end time for verification

  console.log('Setting up Act 1...');
  const act1End = setupAct1(master, ACT_TIMES.act1);
  console.log(`Act 1 setup complete (ends at ${act1End}s)`);

  console.log('Setting up Act 2...');
  const act2End = setupAct2(master, ACT_TIMES.act2);
  console.log(`Act 2 setup complete (ends at ${act2End}s)`);

  console.log('Setting up Act 3...');
  const act3End = setupAct3(master, ACT_TIMES.act3);
  console.log(`Act 3 setup complete (ends at ${act3End}s)`);

  // Add labels for act seeking
  master.addLabel('act1', ACT_TIMES.act1);
  master.addLabel('act2', ACT_TIMES.act2);
  master.addLabel('act3', ACT_TIMES.act3);

  // Log total duration
  console.log(`Master timeline duration: ${master.duration()}s (expected: ${TOTAL_DURATION}s)`);

  // Initial UI update
  timelineUI.update(0, TOTAL_DURATION);

  console.log('CLAMS Visualizer: Ready!');
  console.log('Click "Play" to start the animation, or use the scrubber to navigate.');
}

// Run initialization when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
