# MapGame — Design Document

## Overview

A turn-based, single-player strategy game inspired by Civ 4. The player manages a command economy in a pre-industrial setting, directly controlling population assignments and logistics. There is no tech tree — the challenge is extracting maximum value from your terrain and solving the supply problems that come with expansion.

---

## Core Principles

### 1. Command Economy
The player has direct, total control over every worker. All new population (pops) are auto-assigned to the highest-yield available tile, but the player can override any assignment. Happiness and wage mechanics are omitted.

### 2. Local Logistics
Food is stockpiled **per city**, not globally. Moving food between cities costs labor (transport workers). This means projecting military power or founding new cities requires solving a genuine supply problem first. Concentrating all resources at one location is inefficient — the main strategic challenge is organizing campaigns and expansions within logistical limits.

---

## Map

- **Grid type:** Hex (pointy-top, horizontal rows — odd rows offset right by half a hex)
- **Default size:** 14 × 14 tiles
- **Terrain types (implemented):**

| Terrain  | Move Cost | Notes                                          |
|----------|-----------|------------------------------------------------|
| Desert   | 1.0       | Default terrain                                |
| Hills    | 2.0       | Slower movement                                |
| River    | 1.0 along / 2.0 cross | Moving along river costs 1.0; entering or leaving costs avg of 2.0 + neighbour |
| Mountain | —         | Impassable                                     |

  Movement between two non-river tiles uses the average of their individual costs (symmetric).
  River tiles in a city's range each contribute **5 farm job slots** to that city.

- **Terrain types (planned):** Plains, Forest, Water — to be added when resource and naval systems are designed.
- **Resources (planned):** Wood (Forest), Ore (Hills), Stone (Mountains) — worked by labor workers.

---

## Population

- Each **pop** represents 100 workers.
- Pops are either **farming** (assigned to a job slot) or **unassigned**.
- A city starts with **5 pops**, all unassigned.
- Each pop tracks its current job via `assigned_job` (a `Job` instance, or `None`).

### Assignment
- The player manually assigns pops to job slots via the **Assign Pops** popup (one input per job type).
- A pop occupies exactly one slot; a job can have multiple slots.
- Unassigned pops sit idle and produce nothing.

### Planned
- **Food consumption:** 2 food per pop per turn (deducted from stockpile).
- **Population growth:** `growth_progress += pops × 5` per turn; new pop spawned at 100, auto-assigned to highest-yield slot.
- **Max pops per tile:** 10 (farming only).
- **Labor jobs:** mining, transport, woodcutting, building, crafting.

---

## Cities

- Each city has:
  - A **food stockpile** (local, not global) — grows each End Turn from farm yield
  - A **pop list** (5 pops at start)
  - A **job list** — populated at city creation based on terrain in range
  - A **growth progress** counter *(planned)*
- The city tile acts as the central stockpile point.
- In future multi-city play, each city manages its own stockpile independently.

### City Range
- On creation, the map runs a terrain-based Dijkstra from the city tile out to **move distance 3.0** (same cost model as unit movement).
- Every **river tile** within that range (including the city tile if it is a river) contributes **5 farm job slots** to the city.
- Range and job slots are recalculated fresh on every load (not persisted).

### Save / Load
- Saves persist **terrain only** (tile types and river edges).
- Units, cities, pops, and job assignments are always regenerated fresh on load.

---

## Turn Structure

Each turn processes in this order:
1. Pops work their assigned jobs → yields collected and added to stockpile *(implemented)*
2. Food consumed by pops deducted *(planned)*
3. Growth progress updated *(planned)*
4. If growth ≥ 100 → new pop spawned and auto-assigned *(planned)*

Unit moves are also reset on End Turn.

---

## Jobs

### Implemented

| Job   | Slots source                        | Yield per pop | Output          |
|-------|-------------------------------------|---------------|-----------------|
| Farm  | 5 slots per river tile in city range | 1.25          | Food → stockpile |

Jobs are defined by a `Job` base class with `slots`, `assigned`, `on_turn(city)`, and `yield_display()`.
`FarmJob` adds `food_yield()` and calls `city.food_stockpile += food_yield()` each turn.

### Planned

| Job         | Effect                                      |
|-------------|---------------------------------------------|
| Mining      | Extracts Ore from Hills tiles               |
| Woodcutting | Extracts Wood from Forest tiles             |
| Quarrying   | Extracts Stone from Mountain tiles          |
| Transport   | Moves food between cities (costs labor)     |
| Building    | Constructs improvements or new cities       |
| Crafting    | Converts raw resources into goods           |

---

## Logistics (Planned)

- Food transport between cities requires **transport pops** assigned to a route.
- Transport cost scales with distance.
- This makes long supply lines expensive and over-extended empires fragile.
- Military campaigns require staging food stockpiles along the route before advancing.

---

## Out of Scope (Intentionally Omitted)

- Tech tree — pre-industrial setting; change is slow and incremental, not researched
- Happiness / wages — handwaved for simplicity
- AI opponents — single player to start; teaching an AI to solve these logistics problems is deferred
- Global food stockpile — always local per city
- Combat (planned later, after city economy loop is solid)
