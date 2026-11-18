# Docs

- `训练excel Training excel.xlsx`: FM training spreadsheet by harvestgreen22 on [FM-Arena](https://fm-arena.com/). Kept here as a reference for future development; all credit to its author.
- `Harvestgreen training.pptx` / `.pdf`: slides explaining harvestgreen22's training test, then my own FM27 test of tactical training setups, compared with other people's results.
- `FM27 attibute 属性表…xlsx`: harvestgreen22's FM27 attribute test ([sortitoutsi thread](https://sortitoutsi.net/content/78219/fm27-attribute-test-tactical-understanding-training-system-preset-tactics-ai-reverse-engineering-engine-for-test), 3 Nov 2026). All 18-year-olds with every attribute at 12, one attribute at a time changed to 1, 6 or 18 for the whole team, preset Gegenpress 4-4-2, 5 opponents × 100 matches each.
- `attribute_test_fm27.csv`: that spreadsheet's tables as one CSV. Values are the win-rate change in percentage points: `to_1`/`to_6`/`to_18` against the all-12 base, then the gain over each range, and FM24's for comparison. A blank means not tested.
- `gk_attribute_test_fm27.csv`: Purity's FM27 goalkeeper attribute test ([FM-Arena thread, post #15](https://fm-arena.com/threads/fm27-match-engine-what-we-know-so-far.122/#post-367), Nov 2026), the keeper equivalent of harvestgreen22's. 72,000 simulated matches (38-game seasons), the keeper's 48 visible attributes each set to their real level plus a random shift, outfielders at their real levels. Values are league points per season (not win rate): the gain over each range of the attribute's level (1→8, 8→12, 12→16, 16→20), the total and the average per level over 8→20. Attributes with no measurable effect (total within ±0.05) are left out: Communication, Kicking, Punching, Throwing, First Touch, Passing, Technique, Aggression, Teamwork, Bravery, Off the Ball, Determination, Flair, Leadership, Composure, Vision, Jumping Reach, Natural Fitness, Important Matches, Versatility, Adaptability, Ambition, Loyalty, Pressure, Professionalism, Sportsmanship, Temperament. Purity calls this an old campaign, with a new one planned. caiograco's one-attribute tests in the same thread found no single keeper attribute clearly mattered alone.
- `FM27 attributes.pptx` / `.pdf`: my slides on which outfielder attributes matter most (from harvestgreen22's test), the median of the key attributes by English division, and the other FM leagues at about each division's level by league reputation.
- `FM playable league reputations.xlsx`: FM23's playable leagues and their reputations, from PatrickReynolds' [SI forums thread](https://community.sigames.com/forums/topic/569954-fm23-list-of-playable-leagues-and-reputations/). All credit to its author.
- `ca_costs_fm27.csv`: CA cost of each attribute by position.
- `training_focuses_fm27.csv`: the attributes each training session works on.
- `match_experience.md`: how match experience feeds monthly CA growth (from a YouTube comment by the FM-Arena AI tester).
- `youth_intake_fm24.md`: how FM24 makes youth intakes (blueprints, preview, PA from junior coaching and the nation PA quota, CA as a share of PA), by LightningFlik on [FM-Arena](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/page-2#post-841), reverse-engineered from FM24's code. All credit to its author.

My test's schedules are in `schedules/`. Each setup has one schedule per week of a 4-week cycle, plus a matching `u18` version for the youth team:

- `A minimal`: no tactical sessions (one schedule, repeated every week)
- `B1`–`B4 min+8TE`: 8 tactical sessions a month
- `C1`–`C4 min+24TE`: 24 tactical sessions a month
