/**
 * Act 2: The Value Formation Pipeline (45-135 seconds)
 *
 * Visualizes the GHAP -> Embedding -> Clustering -> Value Formation pipeline.
 * Integrates 3D components for immersive visualization.
 *
 * Scenes:
 * 1. GHAP Demo (45-70s): Show GHAP structure with animated fields
 * 2. Embedding (70-90s): Transform experiences to vector space (3D point cloud)
 * 3. Clustering (90-115s): HDBSCAN clustering (cluster spheres form)
 * 4. Value Extraction (115-135s): Extract values from clusters (centroids appear)
 */
import { CONFIG } from '../config.js';
import { createPointCloud } from '../components/point-cloud.js';
import { createClusterSphereManager } from '../components/cluster-sphere.js';
import { createCentroidManager } from '../components/centroid.js';

// Store 3D components for cleanup
let pointCloud = null;
let clusterManager = null;
let centroidManager = null;
let centroidLines = null; // Lines connecting cluster points to centroid

// Pre-defined cluster positions (5 clusters spread in 3D space)
const CLUSTER_CENTERS = [
  { x: -25, y: 15, z: -10 },
  { x: 20, y: -10, z: 15 },
  { x: -10, y: -20, z: -20 },
  { x: 15, y: 20, z: -15 },
  { x: 0, y: 0, z: 25 }
];

// Cluster radii (varying sizes)
const CLUSTER_RADII = [12, 10, 14, 11, 13];

/**
 * Create lines connecting cluster points to the centroid
 * @param {Object} threeScene - The Three.js scene API
 * @param {Array} pointData - Array of point data with clusterIndex
 * @param {number} clusterIndex - Which cluster to create lines for
 * @param {Object} centroidPosition - The centroid position {x, y, z}
 * @returns {Object} Object with THREE.LineSegments mesh and control methods
 */
function createCentroidLines(threeScene, pointData, clusterIndex, centroidPosition) {
  // Filter points belonging to this cluster
  const clusterPoints = pointData.filter(p => p.clusterIndex === clusterIndex);

  // Create geometry with line segments from each point to centroid
  const positions = [];
  clusterPoints.forEach(point => {
    // Get the point's position from the sprite
    const sprite = point.sprite;
    if (sprite) {
      // Line start: point position
      positions.push(sprite.position.x, sprite.position.y, sprite.position.z);
      // Line end: centroid position
      positions.push(centroidPosition.x, centroidPosition.y, centroidPosition.z);
    }
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

  // Purple material matching the cluster color scheme
  const material = new THREE.LineBasicMaterial({
    color: CONFIG.colorsHex.accent.purple,
    transparent: true,
    opacity: 0,
    linewidth: 1 // Note: linewidth > 1 only works on some platforms
  });

  const lineSegments = new THREE.LineSegments(geometry, material);
  lineSegments.visible = false;

  threeScene.addObject(lineSegments);

  return {
    mesh: lineSegments,
    material: material,
    geometry: geometry,
    pointCount: clusterPoints.length,

    setVisible(visible) {
      lineSegments.visible = visible;
    },

    setOpacity(opacity) {
      material.opacity = opacity;
    },

    dispose() {
      threeScene.removeObject(lineSegments);
      geometry.dispose();
      material.dispose();
    }
  };
}

/**
 * Generate points clustered around the predefined centers
 * @param {number} totalPoints - Total number of points to generate
 * @returns {Array<{x: number, y: number, z: number, clusterIndex: number}>}
 */
function generateClusteredPoints(totalPoints) {
  const points = [];
  const pointsPerCluster = Math.floor(totalPoints / CLUSTER_CENTERS.length);

  CLUSTER_CENTERS.forEach((center, clusterIndex) => {
    const radius = CLUSTER_RADII[clusterIndex] * 0.6; // Points within 60% of sphere radius

    for (let i = 0; i < pointsPerCluster; i++) {
      // Generate random point within sphere using rejection sampling
      let x, y, z;
      do {
        x = (Math.random() - 0.5) * 2 * radius;
        y = (Math.random() - 0.5) * 2 * radius;
        z = (Math.random() - 0.5) * 2 * radius;
      } while (x * x + y * y + z * z > radius * radius);

      points.push({
        x: center.x + x,
        y: center.y + y,
        z: center.z + z,
        clusterIndex
      });
    }
  });

  return points;
}

/**
 * Setup Act 2 animations on the master timeline
 * @param {gsap.core.Timeline} timeline - The master GSAP timeline
 * @param {number} startTime - When this act starts (in seconds)
 * @param {Object} [threeScene] - Three.js scene object (optional, for 3D visualization)
 * @returns {number} The end time of this act (for verification)
 */
export function setupAct2(timeline, startTime, threeScene = null) {
  const timing = CONFIG.timing.act2;
  const scenes = CONFIG.scenes.act2;

  console.log(`[Act 2] Setting up at ${startTime}s`);

  // ========================================
  // Initialize 3D Components (if threeScene provided)
  // ========================================
  const pointData = [];
  let has3D = false;

  if (threeScene) {
    has3D = true;
    console.log('[Act 2] Initializing 3D components');

    // Create point cloud
    pointCloud = createPointCloud(threeScene, {
      color: CONFIG.colorsHex.accent.blue
    });

    // Generate clustered points
    const clusteredPoints = generateClusteredPoints(CONFIG.pointCloud.count);

    // Add points (initially invisible via opacity 0)
    clusteredPoints.forEach((pt, index) => {
      const point = pointCloud.addPoint(pt.x, pt.y, pt.z, {
        opacity: 0,
        scale: 0.8 + Math.random() * 0.4 // Slight size variation
      });
      pointData.push({
        ...point,
        clusterIndex: pt.clusterIndex
      });
    });

    // Create cluster sphere manager
    clusterManager = createClusterSphereManager(threeScene);

    // Create cluster spheres (initially with radius 0)
    CLUSTER_CENTERS.forEach((center, index) => {
      clusterManager.addSphere({
        x: center.x,
        y: center.y,
        z: center.z,
        radius: 0, // Will animate from 0
        opacity: 0
      });
    });

    // Create centroid manager
    centroidManager = createCentroidManager(threeScene);

    // Create centroids at cluster centers (initially invisible)
    CLUSTER_CENTERS.forEach((center) => {
      centroidManager.addCentroid({
        x: center.x,
        y: center.y,
        z: center.z,
        opacity: 0,
        size: CONFIG.clusters.centroidSize
      });
    });
  }

  // ========================================
  // Scene 2.1: GHAP Demo (45-70s)
  // ========================================
  const ghapStart = startTime + scenes.ghapDemo.start;
  const ghapEnd = ghapStart + scenes.ghapDemo.duration;

  // Log when scene starts
  timeline.call(() => {
    console.log(`[Act 2] Scene 1 (GHAP Demo) started at ${timeline.time().toFixed(2)}s`);
  }, [], ghapStart);

  // Camera orbit during GHAP demo (120 degrees over 25 seconds)
  if (has3D && threeScene) {
    const ghapCameraState = { orbit: 0 };
    timeline.to(ghapCameraState, {
      orbit: 120,
      duration: 23,
      ease: 'none',
      onUpdate: () => threeScene.setCameraOrbit(ghapCameraState.orbit)
    }, ghapStart + 1);
  }

  // Fade in GHAP card
  timeline.to('#ghap-card', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, ghapStart);

  // Animate fields appearing sequentially
  timeline.to('#ghap-goal', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, ghapStart + 2);

  timeline.to('#ghap-hypothesis', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, ghapStart + 5);

  timeline.to('#ghap-action', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, ghapStart + 8);

  timeline.to('#ghap-prediction', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, ghapStart + 11);

  timeline.to('#ghap-resolution', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, ghapStart + 15);

  // Fade out GHAP card before embedding scene
  timeline.to('#ghap-card, #ghap-goal, #ghap-hypothesis, #ghap-action, #ghap-prediction, #ghap-resolution', {
    opacity: 0,
    duration: 1,
    ease: 'power2.in'
  }, ghapEnd - 2);

  timeline.call(() => {
    console.log(`[Act 2] Scene 1 (GHAP Demo) ended at ${timeline.time().toFixed(2)}s`);
  }, [], ghapEnd);

  // ========================================
  // Scene 2.2: Embedding (70-90s)
  // ========================================
  const embeddingStart = startTime + scenes.embedding.start;
  const embeddingEnd = embeddingStart + scenes.embedding.duration;

  timeline.call(() => {
    console.log(`[Act 2] Scene 2 (Embedding) started at ${timeline.time().toFixed(2)}s`);
  }, [], embeddingStart);

  // Camera orbit during embedding (120 degrees over 20 seconds)
  if (has3D && threeScene) {
    const embeddingCameraState = { orbit: 120 }; // Continue from GHAP scene
    timeline.to(embeddingCameraState, {
      orbit: 240,
      duration: 18,
      ease: 'none',
      onUpdate: () => threeScene.setCameraOrbit(embeddingCameraState.orbit)
    }, embeddingStart + 1);
  }

  // 3D: Animate points appearing in space
  if (has3D && pointData.length > 0) {
    // Points appear in a staggered wave over 10 seconds
    const pointAppearDuration = 10;
    const staggerDelay = pointAppearDuration / pointData.length;

    // Store animation states for each point
    const pointStates = pointData.map(() => ({ opacity: 0, scale: 0.1 }));

    pointData.forEach((point, index) => {
      const state = pointStates[index];
      const targetScale = 0.8 + Math.random() * 0.4;

      // Fade in with slight scale pop
      timeline.to(state, {
        opacity: 1,
        duration: 0.8,
        ease: 'power2.out',
        onUpdate: () => {
          const sprite = pointCloud.points[index];
          if (sprite) {
            sprite.userData.baseOpacity = state.opacity;
            sprite.material.opacity = state.opacity;
          }
        }
      }, embeddingStart + 2 + (index * staggerDelay));

      // Scale animation: start small, grow to full size
      timeline.to(state, {
        scale: targetScale,
        duration: 0.6,
        ease: 'back.out(1.7)',
        onUpdate: () => {
          const sprite = pointCloud.points[index];
          if (sprite) {
            sprite.userData.originalScale = state.scale;
            const size = pointCloud.baseSize * state.scale;
            sprite.scale.set(size, size, 1);
          }
        }
      }, embeddingStart + 2 + (index * staggerDelay));
    });

    // Store states for later fade out
    pointCloud.pointStates = pointStates;

    // Continuous render during point animation
    timeline.call(() => {
      if (threeScene) threeScene.render();
    }, [], embeddingStart + 2);
  }

  // Show explanation text
  timeline.to('#cluster-explanation', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, embeddingStart + 5);

  timeline.call(() => {
    console.log(`[Act 2] Scene 2 (Embedding) ended at ${timeline.time().toFixed(2)}s`);
  }, [], embeddingEnd);

  // ========================================
  // Scene 2.3: Clustering (90-115s)
  // ========================================
  const clusterStart = startTime + scenes.clustering.start;
  const clusterEnd = clusterStart + scenes.clustering.duration;

  timeline.call(() => {
    console.log(`[Act 2] Scene 3 (Clustering) started at ${timeline.time().toFixed(2)}s`);
  }, [], clusterStart);

  // Update explanation text
  timeline.to('#cluster-explanation', {
    opacity: 0,
    duration: 0.5
  }, clusterStart);

  timeline.set('#cluster-explanation', {
    textContent: 'Similar experiences cluster together'
  }, clusterStart + 0.5);

  timeline.to('#cluster-explanation', {
    opacity: 1,
    duration: 0.5
  }, clusterStart + 1);

  // 3D: Enhanced camera movement during clustering - 120 degrees orbit
  if (has3D && threeScene) {
    const clusterCameraState = { orbit: 240 }; // Continue from embedding scene
    timeline.to(clusterCameraState, {
      orbit: 360,
      duration: 23,
      ease: 'none',
      onUpdate: () => threeScene.setCameraOrbit(clusterCameraState.orbit)
    }, clusterStart + 1);
  }

  // 3D: Animate cluster spheres forming
  if (has3D && clusterManager) {
    // Make spheres visible and animate them forming
    CLUSTER_CENTERS.forEach((_, index) => {
      const sphere = clusterManager.getSphere(index);
      if (sphere) {
        const targetRadius = CLUSTER_RADII[index];

        // Stagger sphere appearances
        const sphereDelay = index * 2;

        // First make visible
        timeline.call(() => {
          sphere.setVisible(true);
        }, [], clusterStart + 3 + sphereDelay);

        // Use plain object for GSAP to animate, then apply via onUpdate
        const sphereState = { radius: 0, opacity: 0 };
        timeline.to(sphereState, {
          radius: targetRadius,
          duration: 3,
          ease: 'elastic.out(1, 0.5)',
          onUpdate: () => sphere.setRadius(sphereState.radius)
        }, clusterStart + 3 + sphereDelay);

        timeline.to(sphereState, {
          opacity: CONFIG.clusters.sphereOpacity,
          duration: 1.5,
          ease: 'power2.out',
          onUpdate: () => sphere.setOpacity(sphereState.opacity)
        }, clusterStart + 3 + sphereDelay);
      }
    });

    // Continuous render during cluster animation
    timeline.call(() => {
      if (threeScene) threeScene.render();
    }, [], clusterStart + 3);
  }

  timeline.call(() => {
    console.log(`[Act 2] Scene 3 (Clustering) ended at ${timeline.time().toFixed(2)}s`);
  }, [], clusterEnd);

  // ========================================
  // Scene 2.4: Value Extraction (115-135s)
  // ========================================
  const valueStart = startTime + scenes.valueExtraction.start;
  const valueEnd = valueStart + scenes.valueExtraction.duration;

  timeline.call(() => {
    console.log(`[Act 2] Scene 4 (Value Extraction) started at ${timeline.time().toFixed(2)}s`);
  }, [], valueStart);

  // Fade out cluster explanation
  timeline.to('#cluster-explanation', {
    opacity: 0,
    duration: 0.5
  }, valueStart);

  // Focus cluster for zoom-in (use cluster 0: {x: -25, y: 15, z: -10})
  const focusCluster = CLUSTER_CENTERS[0];

  // 3D: Zoom in on a specific cluster to show centroid computation
  if (has3D && threeScene) {
    const zoomState = {
      distance: 100,
      lookAtX: 0,
      lookAtY: 0,
      lookAtZ: 0,
      orbit: 360 // Continue from clustering scene
    };

    // Zoom in and focus on the first cluster
    timeline.to(zoomState, {
      distance: 40, // Zoom in closer
      lookAtX: focusCluster.x,
      lookAtY: focusCluster.y,
      lookAtZ: focusCluster.z,
      orbit: 390, // Continue orbiting
      duration: 3,
      ease: 'power2.inOut',
      onUpdate: () => {
        threeScene.setCameraDistance(zoomState.distance);
        threeScene.setCameraLookAt(zoomState.lookAtX, zoomState.lookAtY, zoomState.lookAtZ);
        threeScene.setCameraOrbit(zoomState.orbit);
      }
    }, valueStart + 1);

    // Continue orbit while zoomed in (120 degrees total for this scene)
    timeline.to(zoomState, {
      orbit: 480,
      duration: 15,
      ease: 'none',
      onUpdate: () => threeScene.setCameraOrbit(zoomState.orbit)
    }, valueStart + 4);

    // Zoom back out before end
    timeline.to(zoomState, {
      distance: 100,
      lookAtX: 0,
      lookAtY: 0,
      lookAtZ: 0,
      duration: 3,
      ease: 'power2.inOut',
      onUpdate: () => {
        threeScene.setCameraDistance(zoomState.distance);
        threeScene.setCameraLookAt(zoomState.lookAtX, zoomState.lookAtY, zoomState.lookAtZ);
      }
    }, valueEnd - 5);
  }

  // Fade out cluster spheres when zooming in for centroid computation
  if (has3D && clusterManager) {
    CLUSTER_CENTERS.forEach((_, index) => {
      const sphere = clusterManager.getSphere(index);
      if (sphere) {
        const sphereFadeState = { opacity: CONFIG.clusters.sphereOpacity };
        timeline.to(sphereFadeState, {
          opacity: 0,
          duration: 2,
          ease: 'power2.out',
          onUpdate: () => sphere.setOpacity(sphereFadeState.opacity)
        }, valueStart + 1);
      }
    });
  }

  // Show centroid computation process UI
  timeline.to('#centroid-process', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, valueStart + 1);

  // Step 1: Find cluster center
  timeline.to('#centroid-step1', {
    opacity: 1,
    visibility: 'visible',
    x: 0,
    duration: 0.6,
    ease: 'power2.out'
  }, valueStart + 2);

  // 3D: Animate centroids appearing at cluster centers
  // Store centroid states for animations
  const centroidStates = [];

  if (has3D && centroidManager) {
    // Only animate the focus cluster centroid first (index 0)
    const focusCentroid = centroidManager.getCentroid(0);
    if (focusCentroid) {
      const focusState = { scale: 0, opacity: 0 };
      centroidStates[0] = focusState;

      // Make the focus centroid visible when step 1 appears
      timeline.call(() => {
        focusCentroid.setVisible(true);
      }, [], valueStart + 3);

      // Animate focus centroid appearing with pulse
      timeline.to(focusState, {
        scale: 1.5,
        opacity: 1,
        duration: 1,
        ease: 'back.out(2)',
        onUpdate: () => {
          focusCentroid.setScale(focusState.scale);
          focusCentroid.setOpacity(focusState.opacity);
        }
      }, valueStart + 3);

      // Settle to normal scale
      timeline.to(focusState, {
        scale: 1,
        duration: 0.5,
        ease: 'power2.out',
        onUpdate: () => focusCentroid.setScale(focusState.scale)
      }, valueStart + 4);

      // Create and animate lines from cluster points to centroid
      // Lines appear after centroid, showing the connection
      centroidLines = createCentroidLines(threeScene, pointData, 0, focusCluster);

      if (centroidLines) {
        const linesState = { opacity: 0 };

        // Make lines visible and fade in after centroid appears
        timeline.call(() => {
          centroidLines.setVisible(true);
        }, [], valueStart + 3.5);

        timeline.to(linesState, {
          opacity: 0.6,
          duration: 1.5,
          ease: 'power2.out',
          onUpdate: () => centroidLines.setOpacity(linesState.opacity)
        }, valueStart + 3.5);

        // Fade out lines before zoom out
        timeline.to(linesState, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in',
          onUpdate: () => centroidLines.setOpacity(linesState.opacity)
        }, valueEnd - 5);
      }
    }

    // Step 2: Agent proposes value (after centroid appears)
    timeline.to('#centroid-step2', {
      opacity: 1,
      visibility: 'visible',
      x: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, valueStart + 5);

    // Step 3: Embed and compare
    timeline.to('#centroid-step3', {
      opacity: 1,
      visibility: 'visible',
      x: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, valueStart + 7);

    // Pulse the centroid to show comparison
    if (focusCentroid && centroidStates[0]) {
      timeline.to(centroidStates[0], {
        scale: 1.3,
        duration: 0.3,
        ease: 'power2.out',
        onUpdate: () => focusCentroid.setScale(centroidStates[0].scale)
      }, valueStart + 7.5);

      timeline.to(centroidStates[0], {
        scale: 1,
        duration: 0.3,
        ease: 'power2.in',
        onUpdate: () => focusCentroid.setScale(centroidStates[0].scale)
      }, valueStart + 7.8);
    }

    // Step 4: Value validated
    timeline.to('#centroid-step4', {
      opacity: 1,
      visibility: 'visible',
      x: 0,
      duration: 0.6,
      ease: 'power2.out'
    }, valueStart + 9);

    // Now show the other centroids appearing
    CLUSTER_CENTERS.forEach((_, index) => {
      if (index === 0) return; // Skip focus cluster, already shown

      const centroid = centroidManager.getCentroid(index);
      if (centroid) {
        const state = { scale: 0, opacity: 0 };
        centroidStates[index] = state;

        // Stagger other centroid appearances
        const centroidDelay = (index - 1) * 0.8;

        timeline.call(() => {
          centroid.setVisible(true);
        }, [], valueStart + 10 + centroidDelay);

        timeline.to(state, {
          scale: 1.2,
          opacity: 1,
          duration: 0.6,
          ease: 'back.out(2)',
          onUpdate: () => {
            centroid.setScale(state.scale);
            centroid.setOpacity(state.opacity);
          }
        }, valueStart + 10 + centroidDelay);

        timeline.to(state, {
          scale: 1,
          duration: 0.3,
          ease: 'power2.out',
          onUpdate: () => centroid.setScale(state.scale)
        }, valueStart + 10.6 + centroidDelay);
      }
    });

    // Continuous render during value extraction
    timeline.call(() => {
      if (threeScene) threeScene.render();
    }, [], valueStart + 2);
  }

  // Show value statement (moved later to follow UI steps)
  timeline.to('#value-statement', {
    opacity: 1,
    visibility: 'visible',
    duration: 1.5,
    ease: 'power2.out'
  }, valueStart + 11);

  // Fade out centroid process UI
  timeline.to('#centroid-process, #centroid-step1, #centroid-step2, #centroid-step3, #centroid-step4', {
    opacity: 0,
    duration: 1,
    ease: 'power2.in'
  }, valueEnd - 6);

  // Fade out 3D elements before Act 3
  if (has3D) {
    // Fade out all points using stored states
    if (pointCloud.pointStates) {
      pointCloud.pointStates.forEach((state, index) => {
        timeline.to(state, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in',
          onUpdate: () => {
            const sprite = pointCloud.points[index];
            if (sprite) {
              sprite.userData.baseOpacity = state.opacity;
              sprite.material.opacity = state.opacity;
            }
          }
        }, valueEnd - 3);
      });
    }

    // Fade out cluster spheres
    CLUSTER_CENTERS.forEach((_, index) => {
      const sphere = clusterManager.getSphere(index);
      if (sphere) {
        const fadeOutState = { opacity: sphere.opacity, radius: sphere.radius };
        timeline.to(fadeOutState, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in',
          onUpdate: () => sphere.setOpacity(fadeOutState.opacity)
        }, valueEnd - 3);

        timeline.to(fadeOutState, {
          radius: 0,
          duration: 2,
          ease: 'power2.in',
          onUpdate: () => sphere.setRadius(fadeOutState.radius)
        }, valueEnd - 3);
      }
    });

    // Fade out centroids
    CLUSTER_CENTERS.forEach((_, index) => {
      const centroid = centroidManager.getCentroid(index);
      const state = centroidStates[index];
      if (centroid && state) {
        timeline.to(state, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in',
          onUpdate: () => centroid.setOpacity(state.opacity)
        }, valueEnd - 3);

        timeline.to(state, {
          scale: 0,
          duration: 2,
          ease: 'power2.in',
          onUpdate: () => centroid.setScale(state.scale)
        }, valueEnd - 3);
      }
    });
  }

  // Fade out value statement before Act 3
  timeline.to('#value-statement', {
    opacity: 0,
    duration: 1,
    ease: 'power2.in'
  }, valueEnd - 2);

  timeline.call(() => {
    console.log(`[Act 2] Scene 4 (Value Extraction) ended at ${timeline.time().toFixed(2)}s`);
  }, [], valueEnd);

  // Log act completion
  timeline.call(() => {
    console.log(`[Act 2] COMPLETE at ${timeline.time().toFixed(2)}s`);
  }, [], timing.end);

  // Return end time for verification
  return timing.end;
}

/**
 * Cleanup Act 2 3D components
 * Call this when disposing of the animation
 */
export function cleanupAct2() {
  if (pointCloud) {
    pointCloud.dispose();
    pointCloud = null;
  }
  if (clusterManager) {
    clusterManager.dispose();
    clusterManager = null;
  }
  if (centroidManager) {
    centroidManager.dispose();
    centroidManager = null;
  }
  if (centroidLines) {
    centroidLines.dispose();
    centroidLines = null;
  }
  console.log('[Act 2] Cleaned up 3D components');
}
