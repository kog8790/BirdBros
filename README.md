# BirdBros Recycle Co

**BirdBros Recycle Co** is an experimental AI reinforcement system designed to observe a live visual scene, detect meaningful behavior, evaluate that behavior with AI, and trigger a reward when the configured condition is met.

The original BirdBros use case is simple to describe and wildly complex to execute:

> Teach wild crows to voluntarily collect and deposit litter in exchange for treats.

No captivity.  
No taming.  
No direct human training.  

Just a camera, configurable regions of interest, AI behavior evaluation, and a reward loop.

BirdBros Alpha is intentionally modular. The crow-and-litter use case is the starting point, but the underlying framework is broader: observe an event, evaluate whether the target behavior happened, and trigger a user-defined action.

---

## Current Status

BirdBros is currently in **Alpha**.

That means:

- The app is functional.
- The core visual event → AI judgment → reward/no-reward loop is working.
- The macOS app packaging flow is active.
- The interface is still evolving.
- Some controls and alternate trigger options are present as planned functionality but are not fully live yet.

Expect rough edges. This is an early working build, not a polished commercial release.

---

## What BirdBros Does

BirdBros watches a selected screen/video area and looks for activity inside a configurable trigger region.

When meaningful motion or visual change is detected, BirdBros captures the event, builds visual context, sends the relevant imagery to AI, and asks whether the configured reward condition was satisfied.

If the AI determines the target behavior happened, BirdBros can trigger a reward action.

Example:

```text
A bird enters the scene.
The bird interacts with an object.
The object enters the deposit area.
BirdBros analyzes the event.
If the behavior matches the reward condition, BirdBros triggers the reward.
```

---

## Requirements

### For Normal Testers

- macOS
- A signed BirdBros `.dmg` release
- An OpenAI API key
- A visible camera feed or video feed on screen
- macOS Screen Recording permission enabled for BirdBros
- Accessibility permission if using mouse-click or keyboard-shortcut reward actions

### For Developers

- macOS
- Python 3
- Git
- OpenAI API key
- Apple Developer signing credentials if building official signed/notarized macOS releases

---

## Installing BirdBros from GitHub

### Recommended: Install the macOS Release DMG

1. Go to the BirdBros GitHub repository:

   ```text
   https://github.com/kog8790/BirdBros
   ```

2. Open the **Releases** section.

3. Download the latest macOS `.dmg` file.

4. Open the `.dmg`.

5. Drag **BirdBros Recycle Co.app** into the **Applications** folder.

6. Open BirdBros from Applications.

Because BirdBros uses screen capture and optional automation actions, macOS may ask for permissions the first time you run it.

---

## First Launch

On first launch, BirdBros will ask for your OpenAI API key.

BirdBros uses your API key to send event images to OpenAI for behavior analysis.

Your key is stored locally using macOS Keychain.

BirdBros first checks:

```text
OPENAI_API_KEY environment variable
```

Then it checks the macOS Keychain entry for:

```text
Service: BirdBros Recycle Co
Account: OpenAI API Key
```

If no key is found, the app will prompt you.

---

## Required macOS Permissions

BirdBros may need a few macOS permissions depending on how you use it.

### Screen Recording

Required for BirdBros to watch the selected area of your screen.

When macOS prompts you:

1. Open **System Settings**
2. Go to **Privacy & Security**
3. Open **Screen Recording**
4. Enable BirdBros Recycle Co
5. Quit and reopen BirdBros

Without Screen Recording permission, BirdBros cannot analyze your video feed.

### Accessibility

Required only for reward actions that control the computer, such as:

- Mouse click reward
- Keyboard shortcut reward

To enable:

1. Open **System Settings**
2. Go to **Privacy & Security**
3. Open **Accessibility**
4. Enable BirdBros Recycle Co
5. Quit and reopen BirdBros

If you are only testing visual detection and AI judgment, Accessibility may not be required.

---

## Basic Use Flow

1. Open your camera feed, browser-based video feed, or other visual source.
2. Open BirdBros.
3. Position the BirdBros capture overlay over the video feed.
4. Choose Simple Mode or Advanced Mode.
5. Adjust the region boxes.
6. Set your behavior prompt.
7. Choose your reward action.
8. Start observing.
9. BirdBros will watch for trigger activity, capture event context, analyze the behavior, and decide whether to reward.

---

## Simple Mode

Simple Mode is the recommended starting point.

In Simple Mode, BirdBros uses:

- The full capture area for overall visual context
- One trigger/object region as the event focus
- A behavior prompt to decide whether the observed event should be rewarded

Simple Mode is best when you want BirdBros to watch one main area where the important behavior happens.

Example setup:

```text
Capture Area:
The full camera/video feed.

Trigger/Object ROI:
The trash deposit zone, food platform, object area, or behavior target area.

Prompt:
Reward when a crow deposits a piece of litter into the receptacle.
```

In Simple Mode, the trigger/object region acts as the attention anchor. Motion or meaningful visual change in that region tells BirdBros that something worth analyzing may have happened.

The AI still receives broader visual context from the capture area, so it can understand more than just the small trigger box.

### Simple Mode Recommended Use Cases

- First-time setup
- Testing with a single camera feed
- Trash deposit detection
- Treat platform interaction
- Object entering a specific area
- Basic reward/no-reward experiments

---

## Advanced Mode

Advanced Mode gives more control over how BirdBros separates the subject from the target behavior area.

In Advanced Mode, BirdBros uses:

- A Subject ROI
- An Object/Trigger ROI
- The full capture area for broader context
- A behavior prompt
- Motion/change signals to determine when to analyze an event

Example setup:

```text
Subject ROI:
Where the bird, animal, or actor is expected to appear.

Object/Trigger ROI:
Where the object interaction or deposit event should happen.

Prompt:
Reward only if the bird places trash into the receptacle.
```

Advanced Mode is useful when the subject and the action area are visually separate.

For example:

```text
The bird enters from the upper part of the frame.
The litter or receptacle is in the lower part of the frame.
BirdBros watches both areas together to understand the event.
```

### Advanced Mode Recommended Use Cases

- Bird + object workflows
- Animal + target-zone experiments
- More controlled field testing
- Scenes where the subject and reward condition happen in different areas
- Experiments that need tighter region separation

---

## Regions of Interest

BirdBros uses configurable regions of interest, also called ROIs.

### Capture Area

The overall area BirdBros watches.

This should contain your full video feed or experiment scene.

### Trigger/Object ROI

The region that tells BirdBros, “Pay attention here.”

This is usually where the important behavior happens, such as:

- Trash entering a receptacle
- A bird interacting with an object
- A treat platform being touched
- A target zone changing visually

### Subject ROI

Used in Advanced Mode.

This is where the subject is expected to appear.

Examples:

- Bird perch
- Entry zone
- Feeding area
- Animal approach path

---

## Behavior Prompt

The behavior prompt tells BirdBros what counts as success.

Good prompts are direct and specific.

Example:

```text
Reward only if a bird places a piece of litter into the receptacle.
Do not reward if the bird is merely standing near the receptacle.
Do not reward if the object was already there before the event.
```

Another example:

```text
Reward if the animal moves the target object into the marked zone.
Do not reward random motion, shadows, or unrelated movement.
```

For best results, describe:

- The subject
- The target object
- The desired action
- What should not count as success

---

## Reward Actions

BirdBros can trigger an action when the AI determines the reward condition was met.

Available or planned reward action types may include:

- Visual success indication
- Mouse click
- Keyboard shortcut
- Webhook
- Shell command
- Hardware reward bridge

Not all alternate trigger and reward options are fully live in the current Alpha.

Some options may appear in the interface as part of the planned architecture but are not yet active or fully tested.

For Alpha testing, use the simplest reward action that fits your setup.

---

## Alternate Trigger Options

BirdBros Alpha currently focuses on the main visual-change/motion-triggered workflow.

Some alternate trigger options are planned but not yet live.

These may include future or partially implemented trigger styles such as:

- More advanced object-specific triggers
- Additional external trigger sources
- More hardware-driven trigger methods
- Expanded automation hooks
- Alternate reward-condition pipelines

If a trigger option appears unfinished, assume it is not ready unless specifically documented in a release note.

---

## Building from Source

Developers can clone the repository:

```bash
git clone https://github.com/kog8790/BirdBros.git
cd BirdBros
```

Install dependencies as needed for local development.

The official macOS release build process is handled through the packaging script:

```bash
packaging/build_macos_release.sh
```

The release builder is intended for signed, notarized, stapled macOS builds.

It requires valid Apple Developer signing credentials and notarization credentials.

This script is not intended as a casual unsigned local fallback builder.

---

## Alpha Testing Notes

When testing BirdBros, please note:

- Lighting changes can affect motion and visual-change detection.
- The capture area should be stable.
- The video feed should remain visible on screen.
- macOS permissions may require quitting and reopening the app.
- Behavior prompts strongly affect reward decisions.
- False positives and false negatives are expected during Alpha testing.
- Simple Mode should be tested before Advanced Mode.
- Some interface options are present before the underlying feature is fully active.

---

## Troubleshooting

### BirdBros cannot see the screen

Enable Screen Recording permission:

```text
System Settings → Privacy & Security → Screen Recording
```

Then quit and reopen BirdBros.

### Mouse click or keyboard reward does not work

Enable Accessibility permission:

```text
System Settings → Privacy & Security → Accessibility
```

Then quit and reopen BirdBros.

### API key prompt does not appear

BirdBros may already have an API key saved in macOS Keychain.

The app checks for:

```text
Service: BirdBros Recycle Co
Account: OpenAI API Key
```

### The app opens but does not reward

Check:

- Is the capture area over the video feed?
- Is the trigger/object ROI placed correctly?
- Is your prompt specific enough?
- Is the behavior actually visible in the captured area?
- Are you using Simple Mode first?
- Is the reward action configured?

### macOS says the app cannot be opened

For official releases, BirdBros should be signed, notarized, and stapled.

If macOS shows warnings such as:

```text
Apple cannot check it for malicious software
Unidentified developer
App is damaged and can’t be opened
Cannot verify developer
```

do not continue with that build. Download the latest official release or contact the maintainer.

---

## Project Philosophy

BirdBros is built around a simple idea:

> Reinforcement can be made observable, configurable, and voluntary.

The crow litter experiment is the first expression of that idea.

The broader framework is an AI-mediated behavior reinforcement loop:

```text
Observe → Detect → Analyze → Decide → Reward
```

BirdBros Alpha is the first working step toward that system.

---

## Repository

```text
https://github.com/kog8790/BirdBros
```

---

## Maintainer

Created and maintained by Kevin Green.
