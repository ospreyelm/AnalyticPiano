# Play Stage Piano Redesign

## Goal

Upgrade the Play-mode lower half into a focused performance surface that makes the piano feel larger, more dimensional, and more polished without redesigning the entire player.

The redesign should be visually inspired by premium virtual pianos, but implemented as original HarmonyLab UI. The keyboard should become the centerpiece of the page, with the instruction and status area integrated into the same visual stage rather than appearing as separate utility elements.

## Scope

In scope:

- Restyle the piano region in student Play mode
- Enlarge the keyboard presentation within the existing renderer
- Improve the keyboard's perceived depth using color, shadows, contrast, and proportion
- Clean up the computer-keyboard labels so they feel embedded and intentional
- Integrate the instruction text, readiness/status pill, and start prompt into the same visual stage
- Lightly harmonize the upper player typography and color treatment so it fits the redesigned stage
- Preserve existing Play-mode functionality and control flow

Out of scope:

- Full top-level player redesign
- Navigation or settings information architecture changes
- Replacing Raphael with a new rendering system
- Rebuilding MIDI or keyboard input logic
- Redesigning identification mode UI beyond incidental shared styling

## Design Direction

The play surface should read as a `dark performance stage` embedded inside the current page.

Visual characteristics:

- Piano sits on a dark, instrument-like base rather than on a plain page background
- White keys are warmer and slightly ivory-tinted, not pure white
- Black keys are taller, darker, and more sculpted
- A thin accent line above the keybed reinforces the instrument edge
- Key labels feel inset and tidy rather than overlaid as utility tags
- The area above the keys has stronger hierarchy and less visual fragmentation

The result should feel more professional and deliberate, not flashy or game-like.

## User Experience Changes

### Stage Composition

The lower play area becomes a coherent stage with:

1. Instruction/status strip
2. Piano instrument surface
3. Embedded prompt/keyboard affordances

The rest of the page remains structurally familiar so the redesign feels like a refinement, not a workflow change.

### Upper-Page Harmonization

The upper portion of the player should receive a restrained visual cleanup so it does not feel disconnected from the darker, more premium stage below.

This is not a structural redesign. It is a harmonization pass:

- keep the current header, nav, toolbar, and settings model
- refine typography so it feels less generic and less Artusi-adjacent
- rebalance color so the upper screen is less teal-forward and more neutral
- reduce the sense that the top and bottom halves belong to different products

### Piano Presentation

The keyboard should appear larger through a combination of:

- Increased effective vertical footprint
- More generous surrounding spacing
- A darker frame that visually supports the instrument
- Revised key proportions that increase depth

This does not require changing the number of keys or user settings behavior. It is a presentation change layered onto the existing keyboard component.

### Labels

Computer-keyboard badges should remain visible in QWERTY mode but feel cleaner:

- Smaller visual noise
- Better placement within the key faces
- Stronger contrast against each key type
- Consistent handling of special keys such as backtick

### Start Prompt

The start prompt remains visible before first interaction and should feel like part of the stage rather than a floating debug element. It should remain legible over the redesigned surface and continue to disappear after the first valid interaction.

## Implementation Approach

### Keep Existing Architecture

Use the existing student player template and current piano/keyboard Raphael renderer.

Reasoning:

- Lowest functional risk
- Existing input and note-highlighting behavior remains untouched
- Visual quality can be improved substantially without a renderer rewrite

### Files Likely Touched

- `apps/student/templates/student/player.html`
- `lab/static/js/src/components/piano/keyboard.js`
- `lab/static/js/src/components/piano/key.js`
- `lab/static/css/harmony.css` if global keyboard styles need refinement

Additional touch-ups may be needed in nearby Play-mode CSS only if the stage needs better spacing or containment.
The upper player CSS can also be adjusted where needed for typographic and tonal harmonization.

## Detailed UI Plan

### 1. Stage Container

Create a darker, more intentional container around the piano region in the student player template.

Expected treatment:

- Deep charcoal or brown-black stage background
- Subtle gradient or tonal variation, not flat black
- Soft outer shadow and restrained inner edge highlights
- Rounded outer shell that frames the keyboard

### 1a. Upper Player Harmonization

Apply a restrained polish pass to the top section so it visually supports the stage redesign.

Expected treatment:

- stronger, more intentional title typography
- quieter and more consistent secondary text
- more neutral button and toolbar treatment
- less resemblance to the current Artusi visual vocabulary
- no major layout changes

### 2. Instruction and Status Strip

Move the visual emphasis of instruction text and readiness state into a compact strip visually tied to the stage.

Expected treatment:

- Instruction line centered or left-weighted above the keyboard
- Status pill visually harmonized with the dark stage
- Less empty whitespace between instruction area and keyboard

### 3. Keyboard Chassis

Improve the perceived instrument body around the SVG keyboard:

- Stronger dark chassis behind the keys
- Thin accent line above the keybed
- Better bottom shadow to ground the instrument
- Slightly richer contrast between chassis and page background

### 4. White Keys

Adjust white keys to feel more physical:

- Warmer ivory gradient
- Slight edge shading
- Cleaner stroke treatment
- More convincing pressed state

### 5. Black Keys

Adjust black keys for depth and polish:

- Darker top-to-bottom gradient
- Slightly taller and more substantial visual presence
- Stronger pressed-state contrast
- Cleaner shadow separation from white keys

### 6. QWERTY Labels

Keep the labels but make them more premium:

- Smaller, tidier badges
- More intentional placement
- Better alignment across both white and black keys
- Reduced visual clutter while preserving readability

## Behavior Preservation

The redesign must preserve:

- Mouse interaction on keys
- MIDI interaction
- QWERTY interaction
- Keyboard-size and octave-offset preferences
- Existing note on/off visual state changes
- Start prompt dismissal behavior

This is a visual redesign, not a behavior redesign.

## Risks

### Risk 1: Visual polish breaks label positioning

Because label positions are computed from key geometry, any sizing or offset changes could make the badges drift.

Mitigation:

- Keep label positioning derived from the same keyboard geometry
- Tune offsets conservatively
- Verify at the target student-player URL in-browser

### Risk 2: Bigger keyboard overwhelms small screens

Increasing stage and key presence can crowd mobile or narrow widths.

Mitigation:

- Keep horizontal scrolling support
- Use responsive padding and stage spacing
- Increase perceived size primarily through height, framing, and contrast rather than dramatically wider layout

### Risk 3: Player screen becomes visually too dark

A dark stage can fight with the current light page if overdone.

Mitigation:

- Localize the dark treatment to the lower performance surface
- Keep the rest of the player largely unchanged
- Use restrained accent color and warm neutrals

### Risk 4: Upper-page cleanup drifts into full redesign

Typography and color cleanup at the top could expand into larger UI changes if not constrained.

Mitigation:

- limit changes to tone, type, and surface styling
- avoid changing information architecture or control placement
- evaluate upper-section changes only by whether they better support the stage below

## Testing

### Functional Verification

- Load the target student Play URL and confirm the page renders
- Confirm the start prompt appears before interaction and disappears after interaction
- Confirm QWERTY mode remains the visible default
- Confirm keyboard labels remain legible
- Confirm mouse click, QWERTY input, and MIDI input still register

### Visual Verification

- Check the stage at desktop width
- Check a narrower viewport where horizontal piano scroll is used
- Confirm no badge overlaps or clipped labels
- Confirm key pressed/released states still read clearly

## Success Criteria

The redesign is successful if:

- The piano immediately reads as the visual centerpiece of Play mode
- The keyboard looks larger and more premium without changing workflow
- The stage area feels cohesive instead of pieced together
- The upper portion of the player feels visually related to the stage rather than borrowed from a different screen
- Labels are cleaner and easier to read
- Existing play interactions continue to work unchanged
