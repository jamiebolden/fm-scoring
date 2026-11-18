# Youth intake (FM24): how intakes are made

By **LightningFlik** on FM-Arena, in the thread
["Summary of recent findings for optimal play in FM24"](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/page-2#post-841)
(page 2, posts #21–#26, 18 Nov 2026). Direct links:
[#21](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/post-811) ·
[#22](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/post-812) ·
[#23](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/post-813) ·
[#24](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/post-815) ·
[#25](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/post-816) ·
[#26](https://fm-arena.com/threads/summary-of-recent-findings-for-optimal-play-in-fm24.152/post-824).
All credit to its author. It's copied here as a reference (formatting tidied, the text unchanged, notes marked *[Note: …]*).

This is **FM24**, reverse-engineered from the game code and checked against one save (Aston Villa, EPL-only database).
None of it has been tested on FM27.

---

## Youth intake stuff

Strap in.

### tl;dr

- Your youth intake players are **created on preview day**. Their names, ages, nationalities, positions and a hidden "quality tier" are decided then and never change.
- Their **CA and PA are not decided until intake day**. The preview is the Head of Youth Development judging a practice roll of each player, not the real thing.
- PA is driven mostly by **junior coaching** and your **nation's youth rating**, with youth facilities a distant third. Training facilities play no part.
- A hidden **nation-wide PA quota** then moves players up or down. In England it pushes many players up, but it's **first come, first served**: once the country's quota for a PA band is used up, later clubs miss out.
- CA is mostly set at **roughly 40–55% of the final PA**, adjusted for age.

### Where this comes from

I spent a long time pulling apart FM24's game code to trace exactly how youth intakes are made. I then checked it against a real save (Aston Villa) by watching the preview arrive in December and the intake land on 15 March. Everything below matches what the game actually did. Where a number is an **example**, it uses Villa's values from that save.

A few caveats:

- This is FM24. Other versions may differ.
- I've described the rules that apply in a normal save at a club in a big footballing nation. There are a handful of special cases for particular countries, clubs and US academy leagues that I mostly skip (because I've been at this for ages).
- Anything random is a dice roll. When I say "1 in 20", that's the actual roll in the code.

## Part 1: The timeline

| When | What happens |
| --- | --- |
| **93 days before your nation's intake window opens**, at 09:00 (mid-December for England) | The game creates every youth player for clubs with a human manager, and sends you the **Youth Intake Preview** |
| **The intake window** (mid-March for England, spread over several days) | Each club in the nation gets its own day. On your day, the players created in December become real players and **their CA and PA are rolled**. |
| **End of the window** | Clean-up, and the game tops up the pool of unattached youngsters. |

AI clubs don't get anything in December. Their whole intake is generated from scratch on their intake day.

## Part 2: Preview day — creating the players

On preview day the game builds a "blueprint" for each incoming player. A blueprint contains:

- name, nationality (and any second nationality), place of birth and date of birth;
- positions (which positions they're natural in);
- a hidden **quality tier**.

It contains **no CA, no PA and no attributes**. Those don't exist yet.

### How many players

The number depends on how short of players your nation is. The game compares the number of players it wants in the nation with how many it has.

- England in my save wanted 4,860 and had 4,539, so it was **321 short**. A gap that big gives league clubs **14–16** players.
- A smaller gap (150–299 short) gives **10–12**, and smaller still gives fewer.
- Reserve and affiliate teams get **3–6**. Top-division clubs always get **at least 7**.

Villa got 16.

### The hidden quality tier

Each regular player rolls a tier. This is the most important hidden number in the whole process.

|  | Chance | What it means later |
| --- | --- | --- |
| **Elite** | 0.5% | Best PA odds, best CA range, and it skips the quota (see Part 5) |
| **Good** | 18% | Strong PA odds |
| **Standard** | 54% | Middling PA odds |
| **Weak** | 27.5 | Poor PA odds |
| **Gap-filler** | (see below) | Fills empty positions; PA kept low |

Some adjustments apply:

- In lower leagues, Elite and Good players can be swapped to Standard.
- At low-reputation clubs, Weak players have a 1 in 3 chance of becoming Standard.

**Gap-fillers** are added afterwards to cover any position group your intake has nobody in. They always get the poorest PA treatment.

Villa's 16 were: 4 Good, 4 Standard, 3 Weak and 5 gap-fillers.

## Part 3: The preview itself

To fill in the preview, the game takes each blueprint and makes a **temporary practice copy** of the player. It then runs the full intake-day CA and PA generation on that copy (Parts 4–6). Your **HoYD** rates each practice player. The real CA and PA are rolled again on intake day.

**This is the key point:** the preview grades a practice roll from the same dice the real players will use. It is a good guide to the odds, not a promise.

### Step 1: Your club's benchmark

The game works out a **benchmark (B)** from your senior squad:

```
B = average over your best 13 players of (CA + PA) / 2
```

A stronger first team means a higher bar for youngsters to clear.

### Step 2: Judge each practice player

The HoYD gives each practice player a rating **R** on the 0–200 scale. Each player is then labelled:

- **Good** if `R > 159`, or if `R ≥ B × g`, where `g = 1.4 − 0.4 × (B − 50) / 110`, kept between 1.0 and 1.4.
- **Poor** if `R < B × p`, where `p = 1.0 − 0.2 × (B − 50) / 110`, kept between 0.8 and 1.0.
- **Average** otherwise.

> **Example.** With a benchmark of B = 120:
>
> - g = 1.4 − 0.4 × 70/110 ≈ 1.15, so a player needs **R ≥ 138** to be "good"
> - p = 1.0 − 0.2 × 70/110 ≈ 0.87, so **R < 105** is "poor".
>
> With a weaker squad (B = 80), the bars are 1.29 × 80 ≈ 103 for "good" and 0.95 × 80 = 76 for "poor". In proportion to the squad, the bar for "good" is higher at a smaller club. In absolute terms it's far lower.

### Step 3: Grades per position group

Players are grouped by their natural position: GK, full-backs, centre-backs, DM, central mids, wide mids, AMC, wingers, strikers and wing-backs. For each group:

```
score = 4 × (good players) + (average players) − (poor players), kept between −4 and +4
```

| Score | −4, −3 | −2, −1 | 0 | 1, 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- | --- |
| **Grade** | F | E | D | C | B | A |

A group with no players shows "–".

> **Examples.**
>
> - Full-backs with one good and two average players: 4 + 2 = 6, capped at 4 → **A**.
> - A single good player on his own also gets an **A**.
> - Centre-backs with one average and one poor player: 1 − 1 = 0 → **D**.
> - A lone poor goalkeeper: −1 → **E**.

### Step 4: The star rating

Take the average R of your **top 6** practice players and call it **T**. Then:

```
if T > B:  rating = 20                                  (5 stars)
else:      rating = 11 + 36 × (min(T/B, 1) − 0.75)       (T/B no lower than 0.75)
stars = (rating − 10) / 2
```

Next, a little **HoYD noise** is added. It depends on the HoYD's judging ability (1–20):

| HoYD judging | Noise on the rating | Noise on the player count |
| --- | --- | --- |
| 16–20 | none | exact |
| 6–15 | ±1 (half a star) | ±1 |
| 1–5 | ±2 (one star) | ±2 |

> **Example.** B = 120 and the top six average T = 110:
>
> - T/B = 0.917, so rating = 11 + 36 × 0.167 = **17**, which is 3½ stars.
> - A HoYD with judging 10 could show 3, 3½ or 4 stars.
>
> If the top six averaged above 120, you'd see **5 stars** before any noise.

A HoYD with better judging gives you a **more accurate preview**. Nothing I traced suggests he changes the **players** themselves.

## Part 4: Intake day — PA

On your club's intake day each blueprint becomes a real player. Name, age, nationality, positions and tier come from the blueprint. Everything ability-related is **rolled fresh**.

### Step 1: The club's youth score

```
youth score = ( YF/5 (rounded down) + YR × (JC/20) × 0.5 ) × 1.5
```

- **YF** = youth facilities (1–20).
- **JC** = junior coaching (1–20).
- **YR** = your nation's hidden **youth rating** (0–200). England's is 135.
- For a player born outside your nation, YR can be boosted by **youth recruitment**: `YR × recruitment/20`, used only if it's bigger.

> **Villa example.** YF 18, JC 14, England's YR 135:
>
> (18/5 rounded down = 3, plus 135 × 0.7 × 0.5 = 47.25) × 1.5 = **75**.

Look at the weights:

- **Each point of junior coaching is worth about 5 points of youth score** in England.
- **Each 5 points of youth facilities is worth only about 1.5.**
- Training facilities aren't in the formula at all.

The score is then nudged by a small random amount (−2 to +1).

### Step 2: Lucky boosts (Elite and Good tiers only)

Elite and Good players get extra chances to have their youth score bumped up:

- **Top-flight lift.** In the top division, `rand(100) < youth recruitment` raises the score to a minimum based on national reputation (between 45 and 80).
- **The "wonderkid lottery".** At a club in England, France, Germany, Italy, the Netherlands, Portugal, Russia, Spain, Türkiye or Ivory Coast, with a score of at least 31 (This is the main route to a genuinely world-class prospect):
  - **1 in 21**: the score becomes a random number from 0–119, if that's higher;
  - otherwise **1 in 5**: a random number from 0–69, if that's higher.
- **Continent bonuses.**
  - South America: 1 in 20 → at least 60–89.
  - Africa: 1 in 32 → at least 35–64.
  - Europe gets none.
  - Argentina, Brazil and a couple of specific clubs have their own extra bonuses.

### Step 3: The youth score picks a PA range

The score falls into a band. The band plus the tier decides the odds of landing in each PA range. The game rolls from the best range down; the first hit wins. The bands are 0–9, 10–24, 25–39, 40–54, 55–74, 75–89 and 90+. Here are the top three:

*[Note: this first table has no heading in the post; from the text after it, it's the 90+ band.]*

| Tier | 170–200 | 150–180 | 130–160 | 110–140 | 90–120 | 70–100 | 50–80 | 30–60 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Elite (90–99) | 6% | 47% | 47% |  |  |  |  |  |
| Elite (100+) | 12% | 44% | 44% |  |  |  |  |  |
| Good (90–99) | 5% | 32% | 63% |  |  |  |  |  |
| Good (100+) | 10% | 45% | 45% |  |  |  |  |  |
| Standard |  | 8% | 31% | 31% | 30% |  |  |  |
| Weak/filler |  |  |  |  |  | 74% | 11% | 15% |

The worst result for an Elite or Good player in this band is 130–160, compared with 110–140 in the band below. Oddly, a Standard player here has a 30% chance of the lower 90–120 range, which can't happen at 75–89.

**Youth score 75–89**

| Tier | 170–200 | 150–180 | 130–160 | 110–140 | 90–120 | 70–100 | 50–80 | 30–60 | 10–40 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Elite | 3% | 32% | 33% | 32% |  |  |  |  |  |
| Good | 2% | 25% | 37% | 36% |  |  |  |  |  |
| Standard |  |  |  | 100% |  |  |  |  |  |
| Weak/filler |  |  |  |  | 3% | 7% | 58% | 22% | 10% |

**Youth score 55–74**

| Tier | 150–180 | 130–160 | 110–140 | 90–120 | 70–100 | 50–80 | 30–60 | 10–40 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Elite | 17% | 28% | 55% |  |  |  |  |  |
| Good | 13% | 22% | 65% |  |  |  |  |  |
| Standard |  |  |  | 100% |  |  |  |  |
| Weak/filler |  |  |  |  | 4% | 63% | 24% | 9% |

Then a few **promotion rolls**:

- A short ladder of 1-in-N rolls (1 in 20, 1 in 6, 1 in 3, then 1 in 5, 1 in 4 …) can move a player up one or more ranges. It mostly lifts Weak players from 30–60 or 50–80 to 70–100.
- Part of the ladder only runs if `rand(50) + 50 ≤ the nation's youth rating`. That always passes in England.
- Part only runs if `rand(15) ≤ junior coaching`, so **better junior coaching means more promotions**.
- **Youth recruitment jump.** A player in the 70–100 or 90–120 range, with a youth score of at least 61, jumps straight to **130–160** if `rand(90) + 12 < youth recruitment`.
  - Villa (recruitment 17): about **5.6%**.
  - Recruitment 20: about 8.9%.
- A sanity cap usually (19 in 20) stops a player rising more than two ranges above where the first roll put him.

### Step 4: Pick the PA value inside the range

| Chance | Lands in |
| --- | --- |
| 1 in 4 | the top 10 points of the range |
| 1 in 4 | the bottom 10 points |
| 1 in 2 | the middle |

Then +0 or +1 is added. Values of 180 or more are usually re-rolled (half the time from 180, 49 times in 50 from 190).

> **Example.** A Good player lands in 130–160:
>
> - 25% chance of 150–160;
> - 25% chance of 130–140;
> - 50% chance of 140–150.

### Step 5: Gap-filler cap

Gap-fillers whose PA comes out at 121 or more are pulled back to **120–130**.

**Before the quota**, Villa's chances of PA 140+ were about **64%** for a Good player, **2%** for Standard and **0.2%** for Weak. Villa's real intake had 10 of 16 players at 140+, including Standard and Weak ones. That's because of the next part.

## Part 5: The nation PA quota (the big hidden one)

### What the quota is

When you start a new game, FM counts how many players of each nationality sit in each **20-point PA band** (0–19, 20–39, … 140–159, 160–179, 180+). That snapshot becomes the nation's **target** for each band. The game then keeps a **live count**:

- new players add to it;
- retirements and deletions take away from it.

By the time of the first intake, plenty of players have retired, so many bands are **below target**. England in my save, the day before Villa's intake:

| PA band | 40–59 | 60–79 | 80–99 | 100–119 | 120–139 | **140–159** | 160–179 | 180+ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Target** | 326 | 602 | 1058 | 1460 | 1016 | **288** | 55 | 6 |
| **Live** | 130 | 403 | 886 | 1317 | 894 | **275** | 57 | 7 |

### What it does to a new player

Your club's **junior coaching** sets a floor and ceiling for how far the quota can move a player:

| Junior coaching | Can't be pushed below | Can't be lifted above |
| --- | --- | --- |
| 15–20 | 80–99 | 180+ |
| 12–14 | 60–79 | 160–179 |
| 9–11 | 40–59 | 140–159 |
| 1–8 | 20–39 | 120–139 |

1. **If the player's band is over-full**, he's pushed down one band at a time until he reaches a band with room, or the floor. "Over-full" means the live count is well above target, roughly 10–30% over.
2. **If he wasn't pushed down**, the game tries to **lift him up**, one band at a time, until he reaches the ceiling. Each step happens only if:
   - the next band's live count is below **target − 5**; and
   - he survives a **"stop here" roll** that depends on his position:

   | Player is a natural | Chance of stopping at each step |
   | --- | --- |
   | Striker or attacking midfielder | 1 in 12 |
   | Defender | 1 in 8 |
   | Midfielder, wing-back or other | 1 in 10 |
   | Goalkeeper | 1 in 5 |

3. **If his band changed**, his PA is re-rolled in a range around the new band (for example 130–160 for the 140–159 band).

There are some exceptions:

- **Elite** players skip the quota entirely.
- **Gap-fillers** can be pushed down but never lifted.
- The quota for your **club's** nation is used, even for a foreign-born player. Villa's foreign-born goalkeeper got lifted to PA 158 by England's room, even though his own nation's band was already full.

> **Worked example (Villa, junior coaching 14, so the ceiling is the 160–179 band).**
>
> A Standard central midfielder rolls PA 124, in the 120–139 band. England's 140–159 band has 275 against a target of 288. That's below 288 − 5 = 283, so there's room.
>
> - He survives the 1 in 10 stop roll and moves up to 140–159.
> - Next step: 160–179 has 57 against a target of 55, which is not below 50. He stops.
> - His PA is re-rolled in **130–160**. He ends up with something like PA 147.

### The catch: first come, first served

There's one quota per **nation**, shared by every club whose intake falls in that window, and it fills as clubs are processed.

England's 140–159 band had room for exactly **8 more players** (283 − 275) for the whole country. Villa happened to be one of the first clubs processed and took **5 of those 8**. A club processed later that week would have found the band full. Its Standard and Weak players would have stayed around 60–130.

My simulation for Villa of the chance of PA 140+:

| Tier | No quota | Quota with room | Quota with the 140–159 band full |
| --- | --- | --- | --- |
| Good | 64% | 88% | — |
| Standard | 2% | **66%** | 2% |
| Weak | 0.2% | **52%** | 1% |
| Gap-filler | unchanged | unchanged | unchanged |

**This is the single biggest effect on a typical intake, and most of it is luck of the draw on your intake day.**

The preview's practice players also go through the quota, using the room available **on preview day**. Three months later that room may be very different. That's another reason a 5-star preview can lead to a disappointing intake, or the other way round.

## Part 6: Intake day — CA

CA is worked out in two stages.

### Stage 1: A rough CA from the club

```
CA score = (4 × junior coaching + youth facilities + first-team reputation / 100) / 2
```

> **Villa:** (4 × 14 + 18 + 7000/100) / 2 = **72**.

That score picks a CA range by tier:

| CA score | Elite | Good | Standard/filler | Weak |
| --- | --- | --- | --- | --- |
| 90+ | 105–135 | 65–100 | 45–75 | 30–50 |
| 75–89 | 95–125 | 60–90 | 40–70 | 30–45 |
| 55–74 | 85–125 | 45–80 | 35–60 | 25–40 |
| 35–54 | 65–95 | 40–60 | 30–50 | 20–35 |

**Club reputation counts here.** A bigger first-team reputation means better starting CAs.

### Stage 2: CA is reset from the final PA

For most players, once PA is settled (including any quota lift), CA is recalculated as a **percentage of PA**.

**1. Base percentage.**

| Final PA | Normal club | "Strong club" |
| --- | --- | --- |
| Over 145 | usually 50% (sometimes 52 or 55, rarely 45) | 52% or 55% |
| 100–145 | usually 40% (sometimes 45 or 50) | 45–55% |
| Under 100 | 20–29% | 20–29% |

A **"strong club"** is one flagged as big in the database, or whose first team is in the top two divisions. Even then the bonus only applies with chance **CA score / 125**. For Villa that's 72/125 = **57.6%** of the time.

**2. Age adjustment.**

| Age | 14 | 15 | 16 | 17 | 18 |
| --- | --- | --- | --- | --- | --- |
| **Adjustment** | −5 | −2.5 | **−5** | 0 | +5 |

Yes, 15-year-olds really do get a smaller penalty than 16-year-olds.

**3. Target.**

```
target = PA × percentage / 100
```

If the target is above the rough CA, then `CA = target + a random number from −5 to +4`.

**4. Low-PA players keep their rough CA.** For players under 100 PA, the target usually comes out lower than the rough CA from Stage 1, so they keep it.

**5. CA always ends below PA.**

> **Examples (Villa, real players from the save).**
>
> - **Good tier, age 16, PA 161, normal-club roll.** 50% − 5 = 45%, and 45% of 161 = 72, giving CA 67–76. **Actual: 68.**
> - **Weak tier, age 15, PA 157, strong-club roll of 55%.** 55 − 2.5 = 52.5%, and 52.5% of 157 = 82, giving CA 77–86. **Actual: 81.**
> - **Weak tier, age 16, PA 158, the rare 45% roll.** 45 − 5 = 40%, and 40% of 158 = 63, giving CA 58–67. **Actual: 59.** That's about a 1% chance per player.
> - **Gap-filler, PA 75.** 20–29% of 75 is below his rough CA, so he keeps the rough CA from Stage 1. **Actual: 55.**

**Rule of thumb:** a high-PA youngster arrives with CA at about **40–55% of his PA**.

## Part 7: Putting it together — Villa's real intake

| Tier | Age | CA | PA |
| --- | --- | --- | --- |
| Weak | 16 | 59 | 18 *[Note: as posted; probably 158, the "Weak, age 16, PA 158, CA 59" player in Part 6]* |
| Standard | 16 | 69 | 146 |
| Standard | 16 | 76 | 160 |
| Good | 16 | 68 | 161 |
| Weak | 15 | 31 | 73 |
| Good | 15 | 61 | 145 |
| Standard | 16 | 53 | 114 |
| Good | 16 | 67 | 141 |
| Weak | 15 | 81 | 157 |
| Good | 15 | 56 | 145 |
| Standard | 16 | 75 | 153 |
| Gap-filler | 15 | 55 | 75 |
| Gap-filler | 15 | 47 | 81 |
| Gap-filler | 15 | 37 | 65 |
| Gap-filler | 15 | 55 | 62 |
| Gap-filler | 15 | 36 | 99 |

- **10 of 16 had PA 140+.** That's practically impossible without the quota.
- England's 140–159 band went from 275 to 283 and stopped at exactly target − 5.

## Part 8: What this means for you

### Facilities and staff

- **Junior coaching is king.** It's the biggest single factor in the youth score. It also gates the promotion rolls, sets how high the quota can lift players (15+ unlocks lifts all the way to 180+), and counts four times in the CA score. If you can only upgrade one thing, upgrade this.
- **Youth facilities help, but much less.** They add about 1.5 youth score per 5 points, and a little to CA.
- **Youth recruitment matters more than it looks.** It drives:
  - the top-flight lift for Elite and Good players;
  - the jump straight to 130–160;
  - the boost for foreign-born youngsters.
- **Training facilities don't affect the intake at all.**
- **Your HoYD's judging only affects how accurate the preview is.** Within what I traced, he doesn't make the players better. Hire one with good judging if you want a trustworthy preview.

### League and reputation

- **League level and reputation matter.**
  - Top-division clubs get the top-flight lift.
  - "Strong clubs" get the higher CA percentages.
  - First-team reputation raises the rough CA.
  - Lower-league clubs can have their best tiers swapped down.

### Reading the preview

- **Treat the preview as a weather forecast.** It's built from the right ingredients (real ages, positions and tiers) but a random practice roll. Re-opening it can change the grades; that's a fresh practice roll each time.
- **Grades are relative to your squad.** A great squad makes "good" grades harder to earn in the preview. It doesn't make the real players any worse.

### Luck you can't control

- **Your intake day matters.** The nation's quota room is shared and first come, first served. Clubs early in the window can scoop up the high-PA room. As far as I can tell you can't choose your day.
- **Goalkeepers lose out.** They're the most likely to stop early when the quota lifts players, so expect fewer high-PA keepers.
- **Nation matters a lot.** Your nation's youth rating feeds straight into the youth score. Big European nations and South American and African sides get extra "lottery" chances at a wonderkid. Your nation's deficit also sets how many players you get.

### Myths

- **Nation wealth** isn't used anywhere in this process.
- **Training facilities** aren't used.
- **"The preview stars are locked in"** is false. Only the people are locked in. Their ability is rolled again on intake day.

## Open questions (post #26)

Things I've not dug in yet to (because this took hours) but want to:

- Where does a player's nationality and personality come from? I've heard for years it's HoYD but now I have my doubts.
- What influences when you get your intake compared to other teams in your country?

Note that this investigation occurred in a save with only the EPL loaded on a small database (to make sinming quicker) so actual quota numbers will be higher in most cases (this is why it says every team gets 14-16 from a pool of ~300: I only have 20 teams loaded.)
