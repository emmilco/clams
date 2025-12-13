/**
 * Act 1: The Value Proposition (0-45 seconds)
 *
 * Scenes:
 * 1. Problem statement (0-15s): AI agents lose context between sessions
 * 2. CLAMS pillars (15-45s): Three solution pillars appear sequentially
 */
import { CONFIG } from '../config.js';

/**
 * Setup Act 1 animations on the master timeline
 * @param {gsap.core.Timeline} timeline - The master GSAP timeline
 * @param {number} startTime - When this act starts (in seconds)
 * @returns {number} The end time of this act (for verification)
 */
export function setupAct1(timeline, startTime) {
  const timing = CONFIG.timing.act1;
  const scenes = CONFIG.scenes.act1;

  console.log('[Act 1] Setting up at ' + startTime + 's');

  // ========================================
  // Scene 1: Problem Statement (0-15s)
  // ========================================
  const problemStart = startTime + scenes.problemStatement.start;
  const problemEnd = problemStart + scenes.problemStatement.duration;

  // Log when scene starts
  timeline.call(() => {
    console.log('[Act 1] Scene 1 (Problem Statement) started at ' + timeline.time().toFixed(2) + 's');
  }, [], problemStart);

  // Fade in title at 0s
  timeline.to('#problem-text', {
    opacity: 1,
    visibility: 'visible',
    duration: 1.5,
    ease: 'power2.out'
  }, problemStart);

  // Show subtitles container
  timeline.to('#problem-subtitles', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, problemStart + 1.5);

  // Subtitle 1: "They repeat the same mistakes" (appears at 2s)
  timeline.to('#subtitle-1', {
    opacity: 1,
    visibility: 'visible',
    y: 0,
    duration: 0.8,
    ease: 'power2.out'
  }, problemStart + 2);

  // Subtitle 2: "They cannot learn from experience" (appears at 4.5s)
  timeline.to('#subtitle-2', {
    opacity: 1,
    visibility: 'visible',
    y: 0,
    duration: 0.8,
    ease: 'power2.out'
  }, problemStart + 4.5);

  // Subtitle 3: "They lose context between sessions" (appears at 7s)
  timeline.to('#subtitle-3', {
    opacity: 1,
    visibility: 'visible',
    y: 0,
    duration: 0.8,
    ease: 'power2.out'
  }, problemStart + 7);

  // Hold for reading time, then fade out everything (starts at 12s)
  timeline.to('#problem-text', {
    opacity: 0,
    duration: 1.5,
    ease: 'power2.in'
  }, problemEnd - 3);

  timeline.to('#problem-subtitles, #subtitle-1, #subtitle-2, #subtitle-3', {
    opacity: 0,
    duration: 1.5,
    ease: 'power2.in'
  }, problemEnd - 3);

  // Log when scene ends
  timeline.call(() => {
    console.log('[Act 1] Scene 1 (Problem Statement) ended at ' + timeline.time().toFixed(2) + 's');
  }, [], problemEnd);

  // ========================================
  // Scene 2: CLAMS Pillars (15-45s)
  // ========================================
  const pillarsStart = startTime + scenes.pillars.start;
  const pillarsEnd = pillarsStart + scenes.pillars.duration;

  // Log when scene starts
  timeline.call(() => {
    console.log('[Act 1] Scene 2 (Pillars) started at ' + timeline.time().toFixed(2) + 's');
  }, [], pillarsStart);

  // Show pillars intro "CLAMS: Three Pillars of Persistent Memory"
  timeline.to('#pillars-intro', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, pillarsStart);

  // Show pillars container
  timeline.to('#pillars', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, pillarsStart + 1);

  // Pillar 1: Semantic Code Search (appears at 16s - 2s into scene)
  // Animate with scale and fade for more visual interest
  timeline.fromTo('#pillar-1', 
    { opacity: 0, visibility: 'hidden', y: 30, scale: 0.95 },
    { 
      opacity: 1, 
      visibility: 'visible', 
      y: 0, 
      scale: 1,
      duration: 1.2, 
      ease: 'power2.out' 
    }, 
    pillarsStart + 2);

  // Pillar 2: Layered Working Memory (appears at 23s - 8s into scene)
  timeline.fromTo('#pillar-2',
    { opacity: 0, visibility: 'hidden', y: 30, scale: 0.95 },
    { 
      opacity: 1, 
      visibility: 'visible', 
      y: 0, 
      scale: 1,
      duration: 1.2, 
      ease: 'power2.out' 
    }, 
    pillarsStart + 8);

  // Pillar 3: Hook-Based Injection (appears at 30s - 15s into scene)
  timeline.fromTo('#pillar-3',
    { opacity: 0, visibility: 'hidden', y: 30, scale: 0.95 },
    { 
      opacity: 1, 
      visibility: 'visible', 
      y: 0, 
      scale: 1,
      duration: 1.2, 
      ease: 'power2.out' 
    }, 
    pillarsStart + 15);

  // Hold pillars visible for reading (pillars visible from ~30s to 42s)

  // Fade out intro first
  timeline.to('#pillars-intro', {
    opacity: 0,
    duration: 1,
    ease: 'power2.in'
  }, pillarsEnd - 4);

  // Fade out all pillars (starts at 42s for 3s duration)
  timeline.to('#pillars, #pillar-1, #pillar-2, #pillar-3', {
    opacity: 0,
    duration: 2,
    ease: 'power2.in'
  }, pillarsEnd - 3);

  // Log when scene ends
  timeline.call(() => {
    console.log('[Act 1] Scene 2 (Pillars) ended at ' + timeline.time().toFixed(2) + 's');
  }, [], pillarsEnd);

  // Log act completion
  timeline.call(() => {
    console.log('[Act 1] COMPLETE at ' + timeline.time().toFixed(2) + 's');
  }, [], timing.end);

  // Return end time for verification
  return timing.end;
}
