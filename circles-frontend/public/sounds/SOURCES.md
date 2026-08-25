# Sound effect sources

All four effects are from [Mixkit](https://mixkit.co/free-sound-effects/), under the
Mixkit Sound Effects Free License — free for personal and commercial use, no
attribution required, no account needed to download.

| File          | Mixkit title                  | Source                                                             |
| ------------- | ------------------------------ | ------------------------------------------------------------------- |
| `correct.wav` | Correct answer tone            | https://mixkit.co/free-sound-effects/notification/ (item 2870)      |
| `wrong.wav`   | Wrong answer fail notification | https://mixkit.co/free-sound-effects/notification/ (item 946)       |
| `flip.wav`    | Page forward single chime      | https://mixkit.co/free-sound-effects/paper/ (item 1107), trimmed    |
| `complete.wav`| Game level completed           | https://mixkit.co/free-sound-effects/game/ (item 2059), trimmed     |

`flip.wav` and `complete.wav` were trimmed with a fade-out from the original
downloads to keep them snappy for repeated UI use; `correct.wav` and
`wrong.wav` are used near-verbatim.

## Missing: `start.wav`, `tick.wav`

`circles-frontend/src/lib/sound.ts` references `start.wav` (played when a live-quiz
question begins) and `tick.wav` (played once per second for the last 3 seconds of a
question's timer), but neither file has been added to this folder yet. Live quiz will
silently no-op on these two cues (`playSound` ignores a failed/missing-file `.play()`)
until they're sourced the same way as the set above and dropped in here.
