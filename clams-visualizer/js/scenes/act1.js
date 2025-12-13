/**
 * Act 1: The Value Proposition (0-45 seconds)
 *
 * This is a placeholder implementation that logs timestamps.
 * Full implementation will be done in SPEC-009-02.
 *
 * Scenes:
 * 1. Problem statement (0-15s): AI agents lose context between sessions
 * 2. CLAMS pillars (15-45s): Three solution pillars
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

  console.log(`[Act 1] Setting up at ${startTime}s`);

  // ========================================
  // Scene 1: Problem Statement (0-15s)
  // ========================================
  const problemStart = startTime + scenes.problemStatement.start;
  const problemEnd = problemStart + scenes.problemStatement.duration;

  // Log when scene starts
  timeline.call(() => {
    console.log(`[Act 1] Scene 1 (Problem Statement) started at ${timeline.time().toFixed(2)}s`);
  }, [], problemStart);

  // Fade in title
  timeline.to('#problem-text', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, problemStart);

  // Fade out title before next scene
  timeline.to('#problem-text', {
    opacity: 0,
    duration: 0.5,
    ease: 'power2.in'
  }, problemEnd - 1);

  // Log when scene ends
  timeline.call(() => {
    console.log(`[Act 1] Scene 1 (Problem Statement) ended at ${timeline.time().toFixed(2)}s`);
  }, [], problemEnd);

  // ========================================
  // Scene 2: CLAMS Pillars (15-45s)
  // ========================================
  const pillarsStart = startTime + scenes.pillars.start;
  const pillarsEnd = pillarsStart + scenes.pillars.duration;

  // Log when scene starts
  timeline.call(() => {
    console.log(`[Act 1] Scene 2 (Pillars) started at ${timeline.time().toFixed(2)}s`);
  }, [], pillarsStart);

  // Show pillars container
  timeline.to('#pillars', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, pillarsStart);

  // Animate pillars appearing one by one
  timeline.to('#pillar-1', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, pillarsStart + 1);

  timeline.to('#pillar-2', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, pillarsStart + 5);

  timeline.to('#pillar-3', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, pillarsStart + 9);

  // Fade out all pillars before Act 2
  timeline.to('#pillars, #pillar-1, #pillar-2, #pillar-3', {
    opacity: 0,
    duration: 1,
    ease: 'power2.in'
  }, pillarsEnd - 2);

  // Log when scene ends
  timeline.call(() => {
    console.log(`[Act 1] Scene 2 (Pillars) ended at ${timeline.time().toFixed(2)}s`);
  }, [], pillarsEnd);

  // Log act completion
  timeline.call(() => {
    console.log(`[Act 1] COMPLETE at ${timeline.time().toFixed(2)}s`);
  }, [], timing.end);

  // Return end time for verification
  return timing.end;
}
