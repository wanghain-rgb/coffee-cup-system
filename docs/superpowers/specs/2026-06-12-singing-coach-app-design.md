# Singing Coach App MVP Design

## Purpose

Build a mobile-first web app that helps adult beginners learn singing through pop-song-oriented vocal foundations. The MVP should help users understand their current weaknesses, follow a short daily practice plan, and receive simple feedback that is useful without sounding technical or intimidating.

## Target User

- Adult beginner with little or no formal vocal training.
- Wants to sing pop songs better, especially for karaoke, casual performance, or personal confidence.
- Needs guidance that feels safe, encouraging, and practical.
- May not understand music theory, solfege, pitch names, or vocal technique terms.

## MVP Approach

Use a "light diagnosis plus 7-day plan" model.

The first session gives the user a quick baseline. The app then assigns a 7-day beginner plan with daily 10-15 minute lessons. Each session updates the user's profile and suggests the next focus area.

This balances personalization with buildability. It avoids trying to become a full AI vocal teacher in the first release.

## First-Run Experience

1. User selects a goal:
   - Sing pop songs more steadily.
   - Reduce pitch issues in karaoke.
   - Learn basic vocal technique.
2. User completes a 3-minute light diagnosis:
   - Listen to a reference note and repeat it.
   - Follow a short 3-5 note melody.
   - Sing a fixed practice phrase.
3. The app creates an initial profile:
   - Pitch accuracy: stable, sometimes off, or often off.
   - Rhythm: steady, slightly early or late, or unstable.
   - Comfortable range: low, middle, or higher area for the user.
   - Recommended starting focus: pitch, breath stability, or relaxed sound.
4. User enters a 7-day training plan.

## Core Modules

### Onboarding And Goal Selection

Collect the user's goal, experience level, and preferred practice frequency. The MVP can avoid a full account system at first by storing progress locally, then later add login through Supabase or another backend.

### Light Diagnosis

Play reference sounds, request microphone access, record user responses, extract pitch information, and produce a simple beginner-friendly profile.

The diagnosis should not claim clinical or professional precision. It should frame results as a starting point for practice.

### Daily Training

Provide a fixed 7-day beginner sequence. Each day should include:

- Warm-up.
- Pitch practice.
- Breath or relaxed phonation practice.
- Short phrase singing.
- Feedback and next-step suggestion.

### Real-Time Practice View

During simple exercises, show:

- Current pitch line.
- Target pitch or target zone.
- Whether the user is above, below, or close to the target.

The display should be clear rather than decorative. It should help the user adjust while singing.

### Post-Recording Feedback

After a phrase or exercise, show:

- Pitch stability score.
- Rhythm stability score.
- One or two plain-language suggestions.
- A short encouragement tied to the user's actual performance.

Feedback should avoid harsh wording and avoid unsafe vocal advice such as pushing for high notes.

### Progress And Voice Profile

Track:

- Practice streak.
- Completed lessons.
- Recent pitch trend.
- Comfortable range estimate.
- Current focus area.

The profile should update gradually based on sessions, not overreact to one bad recording.

## MVP Scope

Included:

- Mobile-first web app.
- Built-in exercises only.
- Light diagnosis.
- 7-day beginner plan.
- Browser microphone recording.
- Basic real-time pitch display.
- Post-recording feedback.
- Local progress storage at first.

Excluded from MVP:

- Full commercial song library.
- User-uploaded songs.
- Lyrics alignment.
- Social features.
- Payments.
- Complex AI chat teacher.
- Professional vocal health diagnosis.
- Native iOS or Android app.

## Technical Architecture

### Frontend

Recommended first implementation:

- Vite + React.
- Web Audio API for microphone capture and reference tone playback.
- Canvas or SVG for pitch visualization.
- Local storage or IndexedDB for early user progress.

Vite + React is enough for a focused prototype and keeps setup simple. Next.js can be considered later if server-side routing, content publishing, or SEO becomes important.

### Audio Analysis

Run basic pitch detection in the browser for the MVP.

Potential approaches:

- YIN-style pitch detection.
- Autocorrelation-based pitch detection.
- A mature JavaScript pitch detection package if quality and maintenance are acceptable.

Real-time feedback should be used for simple exercises only. Post-recording analysis can be a little more forgiving and can smooth noisy measurements.

### Backend

Phase 1 can be pure frontend with local persistence.

Phase 2 can add Supabase for:

- Authentication.
- User profiles.
- Practice session history.
- Lesson content.
- Optional audio metadata.

Avoid storing raw audio by default until privacy, storage, and consent rules are clearly designed.

## Data Model

Initial entities:

- `user_profile`: goal, experience level, comfortable range, current focus.
- `diagnostic_session`: diagnostic tasks, pitch results, rhythm result, generated profile.
- `practice_session`: lesson id, completed steps, scores, feedback, timestamp.
- `lesson_step`: exercise type, instruction text, reference pitch or pattern, duration.
- `voice_profile_snapshot`: pitch trend, range estimate, stability trend, focus recommendation.

For local-only MVP, these can be represented as JSON records. If Supabase is added, they can become database tables with stable IDs.

## Feedback Principles

- Use plain language.
- Give one clear correction at a time.
- Reward consistency, not only high scores.
- Prefer "try singing it a little lighter" over technical phrasing like "reduce laryngeal tension."
- Avoid telling users to push louder, force high notes, or ignore throat discomfort.
- Encourage stopping if singing causes pain.

## Main Risks

- Mobile browser microphone permission can be inconsistent across devices.
- Pitch detection may be noisy in loud rooms.
- Bluetooth headphones can introduce latency.
- Users may misunderstand scores as fixed talent judgments.
- Overly technical feedback may reduce motivation.
- Unsafe vocal coaching language could encourage strain.

## Testing Strategy

Manual device testing:

- iPhone Safari.
- Android Chrome.
- Desktop Chrome for development.

Functional tests:

- Microphone permission flow.
- Reference tone playback.
- Recording start and stop.
- Pitch detection with a known tone.
- Lesson step completion.
- Local progress persistence.

User experience tests:

- Can a first-time user finish diagnosis in under 3 minutes?
- Can a beginner understand their feedback without musical vocabulary?
- Can a daily lesson be completed in 10-15 minutes?
- Does the real-time pitch display help rather than distract?

## Success Criteria

The MVP is successful if:

- A new user can complete diagnosis and Day 1 without help.
- The app produces understandable beginner feedback after recording.
- The user can see what to practice tomorrow.
- The core loop works on mobile browsers.
- The product feels like a gentle daily coach, not a judgment machine.

## Recommended Build Order

1. Static mobile-first app shell and lesson flow.
2. Reference tone playback.
3. Microphone permission and recording.
4. Basic pitch detection and visualization.
5. Light diagnosis tasks and profile generation.
6. 7-day lesson content.
7. Post-recording feedback.
8. Local progress tracking.
9. Device testing and UX polishing.
10. Optional Supabase persistence.
