# Self-Dogfood 30-Day Plan
Last updated: 2026-05-25
Status: active local execution plan
## Purpose
This plan turns EnglishFriend into a daily preparation tool for the founder's own job search.
Primary goal:
`Prepare for the first remote hard-currency job while using EnglishFriend as the main interview-prep system.`
Secondary goal:
Use every real preparation session to harden the product loop:
`profile -> vacancy -> mission -> text session -> evidence -> next mission`
## Operating Rules
- Text-first is the default path.
- Voice is optional and only used after the text loop is useful.
- Every session must produce an artifact or evidence.
- Every implementation task must have a verification step.
- Do not refactor for elegance unless a gate fails or a boundary is blocking self-dogfood.
- Prefer one end-to-end slice over several disconnected improvements.
## Success Criteria
By day 30, EnglishFriend should help produce:
- a clear target-role profile
- a vacancy-backed gap map
- a reusable self-introduction
- 2-3 project walkthrough answers
- 3-5 STAR stories
- a recruiter-screen answer bank
- a visible next mission after each session
- at least 10 session evidence records or replayable practice artifacts
Product success is not measured by code volume. It is measured by whether the system becomes useful enough to open every day during job search preparation.
## Daily Protocol
Each dogfood session should follow the same lightweight protocol:
1. Choose one real job-search input.
2. Run one text-first session.
3. Save or inspect evidence.
4. Update one interview artifact.
5. Decide the next mission.
6. Record what broke.
Real job-search inputs can be:
- a vacancy
- a recruiter screen question
- a project from the CV
- a weak English answer
- a behavioral story
- a technical tradeoff answer
## Tracking Format
Each run should be recorded with:
- date
- session_id when available
- input type
- mission
- artifact updated
- evidence saved: yes/no
- next mission clear: yes/no
- blocker
- product fix needed
Keep this tracking lightweight. The goal is to expose product gaps, not create paperwork.
## Phase 0: Setup and Baseline
Target: days 1-3
Goal: make the first self-dogfood run possible without building new large features.
Tasks:
- verify dev environment and database state
- apply and verify `memory_kind` migration if still pending
- run existing product synthetic evals for interview scenarios
- create or identify the founder user profile in the local/dev database
- collect 5-10 target vacancies manually
- write a short current candidate profile in plain text
Verification:
- product eval command completes or produces a specific failure
- one user can start a typed/composer session
- at least one `session_id` can be replayed or diagnosed
- candidate profile exists as an artifact, even if not yet fully modeled in DB
Exit criteria:
- we know whether the current app can support a real text-first preparation session today
- the next code task is based on an observed failure, not speculation
## Phase 1: CareerProfile Slice
Target: days 4-7
Goal: make the system understand the candidate's target job context.
Tasks:
- define the minimal `CareerProfile` shape needed for self-dogfood
- decide whether the first implementation uses existing `LearningPlan` state or a small new artifact
- make session bootstrap include target role and job-search constraints
- add or update an eval scenario for first remote job preparation
- run one self-intro session
Verification:
- session prompt/context includes target role and constraints
- assistant does not ask generic onboarding questions repeatedly
- self-intro feedback references the candidate's real target role
- evidence or artifact captures the weak part of the answer
Exit criteria:
- the system can answer: "who is this candidate and what job is he preparing for?"
## Phase 2: VacancyContext Slice
Target: days 8-12
Goal: turn real vacancies into preparation missions.
Tasks:
- choose 3 representative vacancies
- create a minimal manual vacancy input path
- extract requirements and interview risks manually or with an LLM helper
- generate one mission from a vacancy
- run one vacancy-specific practice session
Verification:
- mission references the vacancy context
- mission is interview-prep specific
- assistant asks for a relevant answer, not a generic English exercise
- next mission reflects a real gap from the answer
Exit criteria:
- pasted vacancy can lead to a useful practice task.
## Phase 3: InterviewPack Slice
Target: days 13-18
Goal: create reusable artifacts for actual job search.
Tasks:
- produce self-introduction v1
- produce project walkthrough v1 for the strongest project
- produce project walkthrough v1 for a second project
- produce 3 STAR stories
- store improved answer versions where the current data model allows it
Verification:
- each artifact can be used outside the app
- each artifact has a source session or manual source
- weak answers are not lost after correction
- next mission can point to an artifact that needs improvement
Exit criteria:
- the candidate has a first usable interview pack.
## Phase 4: Evidence and Session 2 Loop
Target: days 19-24
Goal: make repeated sessions better than starting over in ChatGPT.
Tasks:
- run at least 5 sessions across self-intro, project, behavioral, and recruiter-screen scenarios
- inspect replay or session evidence after each run
- fix the highest-impact evidence continuity issue
- make next mission visible and explainable
- add eval coverage for any repeated regression
Verification:
- session 2 uses session 1 evidence
- next mission is linked to a specific weakness
- replay explains the transition from answer to next mission
- no duplicate completion or stale mission state blocks the flow
Exit criteria:
- returning to the product feels better than opening a blank chat.
## Phase 5: Pressure and Voice Check
Target: days 25-30
Goal: decide whether voice is needed yet.
Tasks:
- run text mock interview sessions under time pressure
- identify where speaking pressure matters
- run optional voice only for one already-useful text scenario
- compare text and voice usefulness manually
- do not integrate new voice providers in this phase
Verification:
- voice is evaluated against a known text baseline
- voice adds a specific value such as pressure, pacing, or confidence
- voice friction is recorded separately from product logic failures
Exit criteria:
- decision: keep text-first, add limited voice practice, or design voice benchmark later
## First Implementation Queue
Start here unless a newer user instruction overrides this list.
1. Verify `memory_kind` migration and DB state.
2. Run interview product synthetic evals.
3. Run one typed/composer session as the founder user.
4. Replay or inspect that session by `session_id`.
5. Capture the first observed blocker.
6. Fix only that blocker.
7. Re-run the same scenario.
## Verification Commands
Use existing commands first.
Product eval:
```powershell
venv\Scripts\python.exe scripts\run_managed_product_eval.py --scenario interview_self_intro_gap --turn-timeout 120 --session-timeout 120
```
Expanded product eval:
```powershell
venv\Scripts\python.exe scripts\run_managed_product_eval.py --scenario-set expanded --turn-timeout 120 --session-timeout 120
```
Replay session:
```powershell
venv\Scripts\python.exe scripts\replay_session.py --session-id <session_id> --output replay.json
```
STT benchmark is not part of the first loop unless voice/STT becomes the observed blocker.
## Failure Classification
Use one primary failure class per run:
- `profile_missing`
- `vacancy_not_used`
- `mission_too_generic`
- `feedback_too_generic`
- `evidence_not_saved`
- `next_mission_unclear`
- `session_runtime_error`
- `voice_or_stt_friction`
- `ui_blocks_flow`
This classification should drive implementation priority.
## Stop Conditions
Stop building new features and inspect evidence if:
- three sessions in a row produce generic feedback
- next mission is unclear twice in a row
- evidence is not saved or cannot be replayed
- the system cannot explain the target role
- the user would rather use a blank ChatGPT thread for the same task
## Definition Of Done For This Plan
The 30-day cycle is done when:
- the founder can prepare daily inside the product
- the product has a real interview pack artifact
- session 2 is better than session 1 because evidence is reused
- the next architecture or product step is backed by dogfood evidence
## Related Documents
- [../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md)
- [../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md)
- [CURRENT_PRODUCT_STATE.md](./CURRENT_PRODUCT_STATE.md)
- [PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md](./PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md)
