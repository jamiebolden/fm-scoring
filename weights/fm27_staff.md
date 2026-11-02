# FM27 staff weights

Scores staff by role the same way as players: **role score = Σ(attribute × weight) / Σ(weights)**, on the 1–20 scale.
FM shows staff attributes as words. Convert each word to the midpoint of its range:

| Word | Range | Value used |
|---|---|---|
| Elite | 20 | 20 |
| Outstanding | 18–19 | 18.5 |
| Very Good | 15–17 | 16 |
| Good | 12–14 | 13 |
| Average | 10–11 | 10.5 |
| Competent | 7–9 | 8 |
| Reasonable | 4–6 | 5 |
| Unsuited | 1–3 | 2 |

Source: a community FM24 rating grid (weights 0–4), relabelled for FM27 and with these changes.

## FM24 → FM27 labels

Checked against FM27 staff profiles (31/3/2029, an FM27 save).

| FM24 (grid) | FM27 | Notes |
|---|---|---|
| GK Distribution, GK Handling, GK Shot Stopping | Goalkeeping | Merged into one attribute, weight 4 |
| Mental (coaching) | Possession | Mental coaching is gone, Possession is new. Possession sits in the same coaching block and feeds the Possession training groups |
| Level of Discipline | Authority | Discipline is gone, Authority is new. Grid weight was 0. FM27 marks Authority key for every coaching role, so coaches get 2 |
| everything else | unchanged | |

## FM27 key attributes (highlighted green on a profile)

| Preferred job | Key attributes |
|---|---|
| Manager | Motivating, People Management, Judging Player Ability, Judging Player Potential, Tactical Knowledge |
| Assistant Manager | People Management, Judging Player Ability, Judging Player Potential |
| Head of Youth Development | Working With Youngsters, Judging Player Ability, Judging Player Potential |
| Coach | Attacking, Defending, Fitness, Tactical, Technical, Authority, Determination, Motivating |
| Goalkeeping Coach | Goalkeeping, Authority, Determination, Motivating |
| Fitness Coach | Fitness, Authority, Motivating |
| Set Piece Coach | Set Pieces, Authority, Determination, Motivating, Tactical Knowledge |
| Director of Football | Judging Player Ability, Judging Player Potential, Negotiating |
| Scout | Adaptability, Judging Player Ability, Judging Player Potential |
| Physio | Physiotherapy |
| Sports Scientist | Sports Science |
| Performance Analyst | not yet checked |

## Other changes from the grid

- **Coach groups.** The grid has one general Coach column. These weights split it into FM's nine training groups: each group gets its two coaching attributes at 4, plus the coach mentals and Working With Youngsters.
- **Training only.** The coach groups leave out the Judging, Negotiating and Tactical Knowledge attributes. Those cover a coach's player reports, not their training.
- **Left out.** Business is hidden, so it's left out of the Director of Football weights.
- **Not scored.** Hidden personality isn't on this view. FM Arena testing suggests it matters more than any attribute for a Head of Youth Development: their Professionalism shifts the intake's. Check it by hand.

Where the weights still disagree with FM27's key attributes (candidates to amend):
- Scout: FM marks Adaptability key; it has weight 0 here.
- Set Piece Coach: FM marks Tactical Knowledge key; it has weight 0 here.
- Coach groups: FM's generic Coach key list leaves out Possession, Set Pieces, Goalkeeping and Working With Youngsters.
- Fitness Coach: FM doesn't mark Determination key; it has weight 2 here.

## What each coaching group trains

From the hover popups on FM27's Set Coach Assignments screen (9/4/2029). **Share of position weight** is how much of
`weights/fm27.toml` each group's player attributes make up, per position (GK: of the `[gk]` weights).

| Coaching group | Player attributes trained | CB | WB/6 | 10 | 9 | Avg |
|---|---|---|---|---|---|---|
| Fitness | Acceleration, Agility, Balance, Jumping Reach, Natural Fitness, Pace, Stamina, Strength, Work Rate | 50% | 51% | 36% | 47% | **46%** |
| Possession Technical | Dribbling, First Touch, Heading, Passing, Technique | 19% | 18% | 27% | 14% | **20%** |
| Possession Tactical | Anticipation, Decisions, Teamwork, Vision | 11% | 18% | 15% | 14% | **15%** |
| Attacking Tactical | Composure, Flair, Off The Ball | 8% | 3% | 18% | 17% | **11%** |
| Defending Tactical | Aggression, Concentration, Positioning | 8% | 8% | 0% | 0% | **4%** |
| Attacking Technical | Crossing, Finishing, Long Shots | 0% | 0% | 3% | 8% | **3%** |
| Defending Technical | Marking, Tackling | 3% | 3% | 0% | 0% | **1%** |
| Set Pieces (Overall) | Corners, Free Kick Taking, Long Throws, Penalty Taking | 0% | 0% | 0% | 0% | **0%** |
| Goalkeeping (Overall) | Aerial Reach, Anticipation, Command Of Area, Communication, Composure, Concentration, Decisions, First Touch, Handling, Kicking, One On Ones, Passing, Positioning, Reflexes, Rushing Out (Tendency), Technique, Throwing, Vision | GK: 72% (Fitness covers the other 28%: Acceleration, Agility) | | | | |

- No coach trains Bravery, Determination or Leadership (none are in the position weights).
- Goalkeepers get outfield-named attributes (Anticipation, Passing, First Touch…) from the GK coach, not the Possession coaches.

## Columns for the staff view (alphabetical)

Also add Name, Club, Age and Role. Adaptability, Judging Staff Ability and Negotiating are left off: they have weight 0 in every role.

- Analysing Data
- Attacking
- Authority
- Defending
- Determination
- Fitness
- Goalkeeping
- Judging Player Ability
- Judging Player Potential
- Motivating
- People Management
- Physiotherapy
- Possession
- Set Pieces
- Sports Science
- Tactical
- Tactical Knowledge
- Technical
- Working With Youngsters

## Impact across all 17 roles (high → low)

**Impact** = an attribute's average share of a role's total weight, averaged over all 17 roles
(nine of them are coach groups). It is the % of an average role score that the attribute decides.
**Top weight in** lists the roles where the attribute has that role's highest weight.
Cutting such an attribute guts that role, even when its overall impact is low.

| # | Attribute | Impact | Roles using it | Top weight in |
|---|---|---|---|---|
| 1 | Determination | 11.9% | 17 |  |
| 2 | Motivating | 11.5% | 15 | Manager, Assistant Manager |
| 3 | Judging Player Ability | 8.1% | 6 | Manager, Assistant Manager, Head of Youth Development, Director of Football, Scout |
| 4 | People Management | 8.1% | 15 | Manager, Assistant Manager |
| 5 | Authority | 6.8% | 9 |  |
| 6 | Tactical | 6.3% | 7 | Coach: Attacking Tactical, Coach: Defending Tactical, Coach: Possession Tactical |
| 7 | Judging Player Potential | 6.0% | 5 | Head of Youth Development, Director of Football, Scout |
| 8 | Technical | 5.9% | 7 | Coach: Attacking Technical, Coach: Defending Technical, Coach: Possession Technical |
| 9 | Working With Youngsters | 4.8% | 12 | Head of Youth Development |
| 10 | Possession | 4.8% | 6 | Coach: Possession Tactical, Coach: Possession Technical |
| 11 | Tactical Knowledge | 4.1% | 6 | Manager |
| 12 | Attacking | 4.0% | 5 | Coach: Attacking Tactical, Coach: Attacking Technical |
| 13 | Defending | 4.0% | 5 | Coach: Defending Tactical, Coach: Defending Technical |
| 14 | Physiotherapy | 2.8% | 2 | Physio |
| 15 | Fitness | 2.8% | 3 | Coach: Fitness |
| 16 | Sports Science | 2.7% | 2 | Sports Scientist |
| 17 | Analysing Data | 2.4% | 1 | Performance Analyst |
| 18 | Set Pieces | 1.6% | 1 | Coach: Set Pieces |
| 19 | Goalkeeping | 1.5% | 1 | Coach: Goalkeeping |
| 20 | Adaptability | 0.0% | 0 |  |
| 21 | Judging Staff Ability | 0.0% | 0 |  |
| 22 | Negotiating | 0.0% | 0 |  |

## Weights by role

The weights themselves are in `weights/fm27.toml` (`[staff_words]` and `[staff.<role>]`); `score.py` reads them from there.
Attributes weighted 0 (Judging Staff Ability, Negotiating, Adaptability) are left out.
