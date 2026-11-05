---
name: auto-reels
description: Automatically edit a private MP4 or MOV into a voiced vertical Reel in Codex Cloud or Claude. Ingest an authorized Google Drive download or local upload, transcribe Brazilian Portuguese with Groq word timestamps, choose one of the eleven editing treatments, render with HyperFrames and validate audio, captions and safe areas. Use for $auto-reels, /auto-reels, or a request to automatically edit a raw video without writing a spec manually.
---

# Automatic Reels in the Cloud

Resolve this SKILL.md to its real directory, then locate the repository two levels
above it. Read `AGENTS.md` and `docs/AUTO_REELS.md`. Invoke `$auto-reels` in Codex
(or `$editing-skills:auto-reels` if namespaced), `/auto-reels` in Claude.

Use the URL only with the user's existing Drive permissions. Do not share files,
make them public, upload them to GitHub, or print signed URLs/OAuth tokens. Store
an input link in `AUTO_REELS_INPUT_URL` through the task's secret/input mechanism.
Never commit it. Real GROQ_API_KEY and network access must be present in this task.
If absent, report the task-bound executor's actual state; don't invent credentials
or claim you switched to another environment.

Before processing, inspect `./auto-reels --doctor`. Diagnostic and help commands
never install dependencies; report missing Python dependencies if inspection fails. If the user
asks only for installation, discovery or validation, stop after those checks.
Do not download, transcribe, render or upload video without an editing request.
Discovery uses `.agents/skills/auto-reels/`; start a new Codex task inside this
checkout if the running task's skill catalog has not refreshed.

One command from the repository root:

```bash
./auto-reels --url-env AUTO_REELS_INPUT_URL
# Or an actual uploaded file in the Cloud workspace:
./auto-reels /workspace/private/clip.mov
```

To send the result to an authorized Drive folder, add
`--drive-folder-env AUTO_REELS_DRIVE_FOLDER_ID`. This additionally needs a real
`GOOGLE_DRIVE_ACCESS_TOKEN` authorized for the source/destination. No sharing
permissions are changed by the code. Existing shared-folder permissions still apply.

The command creates an ignored private `.autoreels/JOB/` containing the MP4,
word-timed transcript, extractive plan, captions, contact sheet and QA report.
Return the actual MP4 using the client's attachment support if available; otherwise
return the authorized Drive file link. Never assume a workspace path is already a
registered downloadable artifact. Do not claim an artifact was attached if the
client does not expose that capability.

Selection is deterministic and evidence-based, not a claim of creative judgement.
Photos use only supplied images; missing assets rule out photo templates. Never
invent social proof, analytics, tiers or quoted words. Original `/trial-reels` still
produces three versions; the automatic single-file workflow uses its original v1.

`--no-transcription` is only an explicit render test with audio; it skips speech
analysis and captions and must never be reported as successful Groq transcription.
Inspect contact sheets for face obstruction and image crops after machine QA.
Stop and report failed validation; do not deliver a failed output as approved.
