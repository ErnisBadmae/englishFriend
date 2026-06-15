---
last_updated: 2026-02-12
---

# Go-to-Market Strategy

**Summary**: Launch through Russian-speaking IT communities via Telegram and Habr, leveraging 200ms full-duplex latency as the primary differentiator. Bootstrapped budget ~$170-330/month.

## Ideal Customer Profile (ICP)

### Primary: Russian-Speaking IT Professionals (25-40)

| Attribute | Detail |
|-----------|--------|
| Pain | Need English for work/interviews, shy to speak |
| Budget | $10-20/month (price of a coffee per day) |
| Channels | Telegram, Habr, YouTube (IT bloggers) |
| TAM | ~2-5M developers from CIS countries |
| Motivation | Career growth, relocation, international teams |

**Why IT professionals first**:
- High willingness to pay (above-average salaries)
- Early adopter mentality (will try Telegram Mini App)
- Strong community (Telegram chats, Habr, conferences)
- Clear use case (technical interviews, team communication)

### Secondary: Russian-Speaking Emigrants / Pre-Relocation

| Attribute | Detail |
|-----------|--------|
| Pain | Everyday English, interviews, IELTS |
| Budget | $15-30/month |
| Channels | Facebook emigration groups, YouTube |
| TAM | ~1-2M (active emigrants + preparing) |

## Launch Strategy (4 Stages)

### Stage 1: Closed Beta (Week 1-2)

**Goal**: Find critical bugs, collect quality feedback

| Item | Detail |
|------|--------|
| Users | 20-50 testers |
| Source | Personal contacts, dev Telegram chats |
| Format | Direct invite link, feedback form |
| KPI | 80% of testers complete 3+ sessions |

**Actions**:
- Recruit from personal network + 2-3 developer chats
- Create feedback form (Google Forms / Typeform)
- Daily monitoring: errors, session length, drop-off points
- 1-on-1 interviews with 5-10 active testers

### Stage 2: Soft Launch (Week 3-4)

**Goal**: 100 DAU, validate retention

| Item | Detail |
|------|--------|
| Users | 200-500 |
| Source | Habr article + Telegram channels |
| KPI | 100 DAU, 30% 7-day retention |

**Actions**:
- **Habr article**: "Как мы сделали AI-репетитора английского с задержкой 200ms"
  - Technical deep-dive: architecture, PersonaPlex, LangGraph
  - Include latency comparison screenshots (us vs competitors)
  - Expected reach: 10-30K views
- **Telegram channel**: Create @EnglishFriendAI
  - Content: English tips + product updates + bot link
  - Target: 500 subscribers in first month
- **Partner posts**: 2-3 IT Telegram channels (paid placement $50-100 each)

### Stage 3: Public Launch (Week 5-8)

**Goal**: 1000 registered users, international visibility

| Item | Detail |
|------|--------|
| Users | 1000+ registered |
| Source | Product Hunt, HN, Reddit, YouTube |
| KPI | 1000 registered, 300 WAU |

**Actions**:
- **Product Hunt**: English-facing launch
  - Tagline: "AI English tutor with 200ms full-duplex voice"
  - Prepare assets: demo video, screenshots, GIF
- **Hacker News**: "Show HN: Open-source AI English tutor with 200ms latency"
  - Emphasize: self-hosted Moshi, LangGraph, open architecture
- **YouTube demo**: Record comparison video (EnglishFriend vs TalkPal vs SPEAK)
  - Show: interrupt the AI mid-sentence → instant response
  - Show: AI remembering previous conversation context
- **Reddit**: Post in r/languagelearning, r/EnglishLearning, r/learnprogramming

### Stage 4: Growth (Month 3+)

**Goal**: Sustainable growth engine

**Actions**:
- **SEO blog**: Articles targeting "English for developers", "IELTS preparation tips", "AI language learning"
- **YouTube channel**: English lessons + product promotion (Russian-speaking audience)
- **Referral program**: Invite friend → both get +30 min free daily
- **Partnerships**:
  - IT education platforms: GeekBrains, Hexlet, Yandex.Practicum
  - IT companies with English-speaking clients (B2B outreach)
  - English language bloggers on YouTube/Instagram
- **Content marketing**: "English for ML interviews", "Technical English vocabulary" series

## Key Messaging

### Headline
**"AI-репетитор, который слушает пока ты говоришь"**

### Pain-Point Messages

| Pain | Message | Feature |
|------|---------|---------|
| "AI doesn't listen" | "Перебивай, поправляй себя, думай вслух — как с живым человеком" | Full-duplex |
| "AI forgets everything" | "Помнит твои цели, интересы и ошибки" | Memory (Qdrant + Neo4j) |
| "I forget new words" | "Запоминает слова за тебя — FSRS повторение в диалоге" | Vocabulary |
| "Generic corrections" | "Специально для русскоговорящих: W/V, TH, артикли" | L1 specialization |

### Killer Demo Concept

**Video**: Split-screen comparison
- Left: EnglishFriend — user interrupts AI, AI instantly adapts (200ms)
- Right: TalkPal — same scenario, 2-second pause, no interruption support

**Why this works**: Visual latency contrast = immediately obvious value prop. High viral potential.

### Positioning Statement

> For Russian-speaking professionals who need to speak English confidently,
> EnglishFriend is an AI mentor that listens while you speak,
> unlike TalkPal or SPEAK which make you wait in silence.
> We offer full-duplex conversation with 200ms response time,
> powered by self-hosted AI that remembers your goals and mistakes.

## Budget (Bootstrapped)

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| GPU server (RTX 5060 Ti) | $50-100 | Already owned, electricity + internet |
| VPS hosting (FastAPI) | $20-50 | DigitalOcean / Hetzner |
| Domain + SSL | $5 | Annual ÷ 12 |
| Telegram channel ads | $100-200 | Seed posts in IT channels |
| Product Hunt | $0 | Free launch |
| Habr article | $0 | Organic post |
| **Total** | **$175-355/month** | |

### When to Increase Budget
- After reaching 500+ users: consider $500-1000/month for targeted ads
- After first 20 paying users: reinvest MRR into growth
- After Product Hunt: if traction is strong, consider press/media outreach

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Low initial traction | Double down on personal outreach, iterate on messaging |
| High churn after trial | Analyze drop-off points, improve onboarding flow |
| Negative reviews | Fast bug fixes, personal responses to feedback |
| Competitor response | Focus on niche (Russian speakers), speed advantage |
| GPU server scaling | Pre-plan additional GPU capacity at 100+ concurrent |

---

*For pricing and margins, see [Unit Economics](./UNIT_ECONOMICS.md)*
*For product roadmap, see [Roadmap](./ROADMAP.md)*
*For competitive positioning, see [Business Strategy](./BUSINESS_STRATEGY.md)*
