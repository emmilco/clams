/**
 * Act 2: The Value Formation Pipeline (45-135 seconds)
 *
 * This is a placeholder implementation that logs timestamps.
 * Full implementation will be done in SPEC-009-04.
 *
 * Scenes:
 * 1. GHAP Demo (45-70s): Show GHAP structure
 * 2. Embedding (70-90s): Transform to vector space
 * 3. Clustering (90-115s): HDBSCAN clustering
 * 4. Value Extraction (115-135s): Extract values from clusters
 */
import { CONFIG } from '../config.js';

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
    console.log('[Act 2] Points would appear in 3D space here (placeholder)');
  }, [], embeddingStart);

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
    console.log('[Act 2] Cluster spheres would form here (placeholder)');
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
    console.log('[Act 2] Centroids and values would appear here (placeholder)');
  }, [], valueStart);

  // Fade out cluster explanation
  timeline.to('#cluster-explanation', {
    opacity: 0,
    duration: 0.5
  }, valueStart);

  // Show value statement
  timeline.to('#value-statement', {
    opacity: 1,
    visibility: 'visible',
    duration: 1.5,
    ease: 'power2.out'
  }, valueStart + 5);

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
