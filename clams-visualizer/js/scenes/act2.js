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

  // 3D: Animate points appearing in space
  if (has3D && pointData.length > 0) {
    // Points appear in a staggered wave over 10 seconds
    const pointAppearDuration = 10;
    const staggerDelay = pointAppearDuration / pointData.length;

    pointData.forEach((point, index) => {
      const pointOpacity = pointCloud.getPointOpacityAnimatable(index);
      const pointScale = pointCloud.getPointScaleAnimatable(index);

      if (pointOpacity && pointScale) {
        // Fade in with slight scale pop
        timeline.to(pointOpacity, {
          opacity: 1,
          duration: 0.8,
          ease: 'power2.out'
        }, embeddingStart + 2 + (index * staggerDelay));

        // Scale animation: start small, grow to full size
        timeline.fromTo(pointScale, {
          scale: 0.1
        }, {
          scale: 0.8 + Math.random() * 0.4,
          duration: 0.6,
          ease: 'back.out(1.7)'
        }, embeddingStart + 2 + (index * staggerDelay));
      }
    });

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

  // 3D: Animate cluster spheres forming
  if (has3D && clusterManager) {
    // Make spheres visible and animate them forming
    CLUSTER_CENTERS.forEach((_, index) => {
      const sphere = clusterManager.getSphere(index);
      if (sphere) {
        const radiusAnim = sphere.getRadiusAnimatable();
        const opacityAnim = sphere.getOpacityAnimatable();
        const targetRadius = CLUSTER_RADII[index];

        // Stagger sphere appearances
        const sphereDelay = index * 2;

        // First make visible
        timeline.call(() => {
          sphere.setVisible(true);
        }, [], clusterStart + 3 + sphereDelay);

        // Animate radius from 0 to target
        timeline.to(radiusAnim, {
          radius: targetRadius,
          duration: 3,
          ease: 'elastic.out(1, 0.5)'
        }, clusterStart + 3 + sphereDelay);

        // Fade in opacity
        timeline.to(opacityAnim, {
          opacity: CONFIG.clusters.sphereOpacity,
          duration: 1.5,
          ease: 'power2.out'
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

  // 3D: Animate centroids appearing at cluster centers
  if (has3D && centroidManager) {
    CLUSTER_CENTERS.forEach((_, index) => {
      const centroid = centroidManager.getCentroid(index);
      if (centroid) {
        const scaleAnim = centroid.getScaleAnimatable();
        const opacityAnim = centroid.getOpacityAnimatable();

        // Stagger centroid appearances
        const centroidDelay = index * 1.5;

        // Make visible
        timeline.call(() => {
          centroid.setVisible(true);
        }, [], valueStart + 2 + centroidDelay);

        // Animate scale with a pulse effect
        timeline.fromTo(scaleAnim, {
          scale: 0
        }, {
          scale: 1.2,
          duration: 0.8,
          ease: 'back.out(2)'
        }, valueStart + 2 + centroidDelay);

        // Settle to normal scale
        timeline.to(scaleAnim, {
          scale: 1,
          duration: 0.4,
          ease: 'power2.out'
        }, valueStart + 2.8 + centroidDelay);

        // Fade in
        timeline.to(opacityAnim, {
          opacity: 1,
          duration: 0.6,
          ease: 'power2.out'
        }, valueStart + 2 + centroidDelay);
      }
    });

    // After centroids appear, slightly fade cluster spheres to emphasize centroids
    CLUSTER_CENTERS.forEach((_, index) => {
      const sphere = clusterManager.getSphere(index);
      if (sphere) {
        const opacityAnim = sphere.getOpacityAnimatable();
        timeline.to(opacityAnim, {
          opacity: CONFIG.clusters.sphereOpacity * 0.5,
          duration: 2,
          ease: 'power2.out'
        }, valueStart + 10);
      }
    });

    // Continuous render during value extraction
    timeline.call(() => {
      if (threeScene) threeScene.render();
    }, [], valueStart + 2);
  }

  // Show value statement
  timeline.to('#value-statement', {
    opacity: 1,
    visibility: 'visible',
    duration: 1.5,
    ease: 'power2.out'
  }, valueStart + 5);

  // Fade out 3D elements before Act 3
  if (has3D) {
    // Fade out all points
    pointData.forEach((point, index) => {
      const pointOpacity = pointCloud.getPointOpacityAnimatable(index);
      if (pointOpacity) {
        timeline.to(pointOpacity, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in'
        }, valueEnd - 3);
      }
    });

    // Fade out cluster spheres
    CLUSTER_CENTERS.forEach((_, index) => {
      const sphere = clusterManager.getSphere(index);
      if (sphere) {
        const opacityAnim = sphere.getOpacityAnimatable();
        const radiusAnim = sphere.getRadiusAnimatable();

        timeline.to(opacityAnim, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in'
        }, valueEnd - 3);

        timeline.to(radiusAnim, {
          radius: 0,
          duration: 2,
          ease: 'power2.in'
        }, valueEnd - 3);
      }
    });

    // Fade out centroids
    CLUSTER_CENTERS.forEach((_, index) => {
      const centroid = centroidManager.getCentroid(index);
      if (centroid) {
        const opacityAnim = centroid.getOpacityAnimatable();
        const scaleAnim = centroid.getScaleAnimatable();

        timeline.to(opacityAnim, {
          opacity: 0,
          duration: 2,
          ease: 'power2.in'
        }, valueEnd - 3);

        timeline.to(scaleAnim, {
          scale: 0,
          duration: 2,
          ease: 'power2.in'
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
  console.log('[Act 2] Cleaned up 3D components');
}
