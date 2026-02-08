/**
 * Act 3: Context Injection (135-180 seconds)
 *
 * This act shows how CALM injects learned context into new Claude sessions.
 * It is entirely 2D (no Three.js required).
 *
 * Scenes:
 * 1. Session Start (135-147s): Claude Code session begins, user prompt arrives, hook triggers
 * 2. Semantic Retrieval (147-162s): User prompt embedded, similar values retrieved
 * 3. Context Injection (162-175s): Context assembled and injected into Claude's view
 * 4. Closing (175-180s): Tagline and fade to black
 */
import { CONFIG } from '../config.js';

/**
 * Setup Act 3 animations on the master timeline
 * @param {gsap.core.Timeline} timeline - The master GSAP timeline
 * @param {number} startTime - When this act starts (in seconds)
 * @returns {number} The end time of this act (for verification)
 */
export function setupAct3(timeline, startTime) {
  const timing = CONFIG.timing.act3;
  const scenes = CONFIG.scenes.act3;

  console.log(`[Act 3] Setting up at ${startTime}s`);

  // ========================================
  // Scene 3.1: Session Start (135-147s)
  // ========================================
  const sessionStart = startTime + scenes.sessionStart.start;
  const sessionEnd = sessionStart + scenes.sessionStart.duration;

  timeline.call(() => {
    console.log(`[Act 3] Scene 1 (Session Start) started at ${timeline.time().toFixed(2)}s`);
  }, [], sessionStart);

  // Show act 3 content container
  timeline.to('#act3-content', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, sessionStart);

  // Fade in session container
  timeline.to('#session-container', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, sessionStart + 0.5);

  // Animate typing effect for user prompt (fade in)
  timeline.to('#user-prompt', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, sessionStart + 3);

  // Show hook trigger with highlight effect
  timeline.to('#hook-trigger', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5,
    ease: 'power2.out'
  }, sessionStart + 6);

  // Pulse the hook trigger to draw attention
  timeline.to('#hook-trigger', {
    scale: 1.05,
    duration: 0.3,
    ease: 'power2.inOut',
    yoyo: true,
    repeat: 2
  }, sessionStart + 7);

  // Fade out session container before next scene
  timeline.to('#session-container', {
    opacity: 0,
    duration: 0.8,
    ease: 'power2.in'
  }, sessionEnd - 1);

  timeline.call(() => {
    console.log(`[Act 3] Scene 1 (Session Start) ended at ${timeline.time().toFixed(2)}s`);
  }, [], sessionEnd);

  // ========================================
  // Scene 3.2: Semantic Retrieval (147-162s)
  // ========================================
  const retrievalStart = startTime + scenes.semanticRetrieval.start;
  const retrievalEnd = retrievalStart + scenes.semanticRetrieval.duration;

  timeline.call(() => {
    console.log(`[Act 3] Scene 2 (Semantic Retrieval) started at ${timeline.time().toFixed(2)}s`);
  }, [], retrievalStart);

  // Show retrieval container
  timeline.to('#retrieval-container', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, retrievalStart);

  // Animate prompt to vector transformation
  timeline.to('#prompt-vector', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, retrievalStart + 0.5);

  // Show search animation
  timeline.to('#retrieval-animation', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, retrievalStart + 3);

  // Pulse the search label
  timeline.to('.search-label', {
    opacity: 0.5,
    duration: 0.5,
    ease: 'power1.inOut',
    yoyo: true,
    repeat: 3
  }, retrievalStart + 3.5);

  // Show retrieved items
  timeline.to('#retrieved-items', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, retrievalStart + 6);

  // Stagger in retrieved items
  timeline.to('#retrieved-1', {
    opacity: 1,
    visibility: 'visible',
    y: 0,
    duration: 0.6,
    ease: 'power2.out'
  }, retrievalStart + 6.5);

  timeline.to('#retrieved-2', {
    opacity: 1,
    visibility: 'visible',
    y: 0,
    duration: 0.6,
    ease: 'power2.out'
  }, retrievalStart + 7.5);

  timeline.to('#retrieved-3', {
    opacity: 1,
    visibility: 'visible',
    y: 0,
    duration: 0.6,
    ease: 'power2.out'
  }, retrievalStart + 8.5);

  // Fade out retrieval container before injection scene
  timeline.to('#retrieval-container, #prompt-vector, #retrieval-animation, #retrieved-items', {
    opacity: 0,
    duration: 0.8,
    ease: 'power2.in'
  }, retrievalEnd - 1);

  timeline.call(() => {
    console.log(`[Act 3] Scene 2 (Semantic Retrieval) ended at ${timeline.time().toFixed(2)}s`);
  }, [], retrievalEnd);

  // ========================================
  // Scene 3.3: Context Injection (162-175s)
  // ========================================
  const injectionStart = startTime + scenes.contextInjection.start;
  const injectionEnd = injectionStart + scenes.contextInjection.duration;

  timeline.call(() => {
    console.log(`[Act 3] Scene 3 (Context Injection) started at ${timeline.time().toFixed(2)}s`);
  }, [], injectionStart);

  // Show injection container
  timeline.to('#injection-container', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.5
  }, injectionStart);

  // Fade in Claude's view container
  timeline.to('#claude-view', {
    opacity: 1,
    visibility: 'visible',
    duration: 1,
    ease: 'power2.out'
  }, injectionStart + 0.5);

  // Animate context items appearing
  timeline.to('#context-1', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, injectionStart + 2);

  timeline.to('#context-2', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, injectionStart + 4);

  // Show agent working indicator
  timeline.to('#agent-working', {
    opacity: 1,
    visibility: 'visible',
    duration: 0.8,
    ease: 'power2.out'
  }, injectionStart + 6);

  // Fade out injection container before closing
  timeline.to('#injection-container, #claude-view, #agent-working', {
    opacity: 0,
    duration: 1,
    ease: 'power2.in'
  }, injectionEnd - 1.5);

  // Hide act3 content container
  timeline.to('#act3-content', {
    opacity: 0,
    duration: 0.5
  }, injectionEnd - 0.5);

  timeline.call(() => {
    console.log(`[Act 3] Scene 3 (Context Injection) ended at ${timeline.time().toFixed(2)}s`);
  }, [], injectionEnd);

  // ========================================
  // Scene 3.4: Closing (175-180s)
  // ========================================
  const closingStart = startTime + scenes.closing.start;
  const closingEnd = closingStart + scenes.closing.duration;

  timeline.call(() => {
    console.log(`[Act 3] Scene 4 (Closing) started at ${timeline.time().toFixed(2)}s`);
  }, [], closingStart);

  // Show tagline
  timeline.to('#tagline', {
    opacity: 1,
    visibility: 'visible',
    duration: 1.5,
    ease: 'power2.out'
  }, closingStart + 0.5);

  // Subtle pulse effect on tagline
  timeline.to('#tagline', {
    scale: 1.02,
    duration: 0.8,
    ease: 'power1.inOut',
    yoyo: true,
    repeat: 1
  }, closingStart + 2);

  // Final fade to black (fade content layer)
  timeline.to('#content-layer', {
    opacity: 0,
    duration: 1
  }, closingEnd - 1);

  timeline.call(() => {
    console.log(`[Act 3] Scene 4 (Closing) ended at ${timeline.time().toFixed(2)}s`);
  }, [], closingEnd);

  // Log act completion
  timeline.call(() => {
    console.log(`[Act 3] COMPLETE at ${timeline.time().toFixed(2)}s`);
    console.log('='.repeat(50));
    console.log('Animation complete! Total runtime: 180 seconds');
    console.log('='.repeat(50));
  }, [], timing.end);

  // Return end time for verification
  return timing.end;
}
