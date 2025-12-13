/**
 * Timeline Controller
 *
 * Manages the UI controls for the animation timeline:
 * - Play/Pause button
 * - Scrubber (draggable timeline)
 * - Act markers (jump to Act 1/2/3)
 * - Time display
 */
import { CONFIG, ACT_TIMES, TOTAL_DURATION } from './config.js';

/**
 * Format seconds as MM:SS
 * @param {number} seconds - Time in seconds
 * @returns {string} Formatted time string
 */
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Initialize timeline controls and bind them to a GSAP timeline
 * @param {gsap.core.Timeline} timeline - The master GSAP timeline
 */
export function initTimelineControls(timeline) {
  const playPauseBtn = document.getElementById('play-pause');
  const scrubber = document.getElementById('scrubber');
  const currentTimeEl = document.getElementById('current-time');
  const totalTimeEl = document.getElementById('total-time');
  const actMarkers = document.querySelectorAll('.act-marker');

  // Display total time
  totalTimeEl.textContent = formatTime(TOTAL_DURATION);

  // Track if user is currently scrubbing
  let isScrubbing = false;

  // Play/Pause button handler
  playPauseBtn.addEventListener('click', () => {
    if (timeline.paused()) {
      timeline.play();
      playPauseBtn.textContent = 'Pause';
    } else {
      timeline.pause();
      playPauseBtn.textContent = 'Play';
    }
  });

  // Scrubber input handler (fires continuously while dragging)
  scrubber.addEventListener('input', (e) => {
    const progress = parseFloat(e.target.value) / 100;
    const targetTime = progress * TOTAL_DURATION;

    // Seek timeline to the specified time
    timeline.time(targetTime);
  });

  // Scrubber mousedown - pause playback while scrubbing
  scrubber.addEventListener('mousedown', () => {
    isScrubbing = true;
    if (!timeline.paused()) {
      timeline.pause();
      playPauseBtn.textContent = 'Play';
    }
  });

  // Scrubber mouseup - done scrubbing
  scrubber.addEventListener('mouseup', () => {
    isScrubbing = false;
  });

  // Also handle touch events for mobile
  scrubber.addEventListener('touchstart', () => {
    isScrubbing = true;
    if (!timeline.paused()) {
      timeline.pause();
      playPauseBtn.textContent = 'Play';
    }
  });

  scrubber.addEventListener('touchend', () => {
    isScrubbing = false;
  });

  // Act marker click handlers
  actMarkers.forEach(marker => {
    marker.addEventListener('click', () => {
      const targetTime = parseFloat(marker.dataset.time);

      // Seek to act start time
      timeline.time(targetTime);

      // Pause if playing
      if (!timeline.paused()) {
        timeline.pause();
        playPauseBtn.textContent = 'Play';
      }

      console.log(`Jumped to ${marker.dataset.act} at ${targetTime}s`);
    });
  });

  // Return an update function to be called on each frame
  return {
    /**
     * Update the timeline UI (called on each GSAP timeline update)
     * @param {number} time - Current time in seconds
     * @param {number} duration - Total duration in seconds
     */
    update(time, duration) {
      // Update time display
      currentTimeEl.textContent = formatTime(time);

      // Update scrubber position (only if not currently scrubbing)
      if (!isScrubbing) {
        const progress = (time / duration) * 100;
        scrubber.value = progress;
      }
    },

    /**
     * Update play/pause button state
     * @param {boolean} isPlaying - Whether timeline is currently playing
     */
    setPlaying(isPlaying) {
      playPauseBtn.textContent = isPlaying ? 'Pause' : 'Play';
    }
  };
}
