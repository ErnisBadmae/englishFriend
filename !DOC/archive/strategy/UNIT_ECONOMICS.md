---
last_updated: 2026-02-12
---

# Unit Economics

**Summary**: Self-hosted PersonaPlex gives us 90%+ gross margin vs 70-80% for API-dependent competitors. Break-even at ~300 active free + 20 pro users.

## Cost Structure by Tier

### Free Tier (30 min/day limit)

| Component | Cost | Notes |
|-----------|------|-------|
| Vosk STT | $0 | Browser WASM, offline |
| Groq LLM | ~$0.001/request | llama-3.3-70b-versatile |
| edge-tts | $0 | Microsoft, free |
| **Total per hour** | **~$0.10-0.50** | |
| Daily limit | 30 min | |
| **Monthly COGS per active user** | **~$1.50-7.50** | Assuming 15-30 min/day avg |

### Pro Tier ($12.99/month)

| Component | Cost | Notes |
|-----------|------|-------|
| PersonaPlex (self-hosted) | $0 | NVIDIA Moshi 7B, already deployed |
| GPU server (RTX 5060 Ti) | ~$50/month | Electricity + amortization |
| Per-user at 50 concurrent | ~$1/month | $50 / 50 users |
| Per-user at 200 concurrent | ~$0.25/month | $50 / 200 users |
| **Gross margin** | **$11.99-12.74 (92-98%)** | |

**Key advantage**: PersonaPlex replaces the entire Deepgram ($0.0059/15s) + ElevenLabs ($0.30/1K chars) stack with $0 marginal cost.

### Team Tier ($99/month, up to 10 people)

| Metric | Value |
|--------|-------|
| Effective price per seat | $9.90/month |
| COGS per team | ~$2.50-10/month |
| **Gross margin** | **$89-96.50 (90-97%)** |

## Break-Even Analysis

**Fixed monthly costs**:

| Item | Cost |
|------|------|
| GPU server (RTX 5060 Ti) | ~$50 |
| VPS hosting (FastAPI + DB) | ~$50-100 |
| Domain + misc | ~$20 |
| **Total fixed** | **~$120-170/month** |

**Variable costs**: ~$3-5/month per active free user (Groq API)

**Break-even scenarios**:

| Scenario | Free Users | Pro Users | Revenue | Costs | Net |
|----------|-----------|-----------|---------|-------|-----|
| Minimum viable | 300 | 20 | $260 | ~$250 | +$10 |
| Healthy | 500 | 35 | $455 | ~$320 | +$135 |
| Growth | 1000 | 70 | $909 | ~$470 | +$439 |
| Scale | 3000 | 200 | $2,598 | ~$870 | +$1,728 |

**Break-even point**: ~300 active free users + 20 pro subscribers ($260 MRR)

## Revenue Projections

### Year 1 Targets

| Quarter | Free Users | Pro Users | Team Accts | MRR |
|---------|-----------|-----------|------------|-----|
| Q1 (launch) | 100-300 | 5-15 | 0 | $65-195 |
| Q2 | 500-1000 | 25-50 | 1-2 | $424-749 |
| Q3 | 1000-2000 | 50-100 | 3-5 | $947-1,795 |
| Q4 | 2000-5000 | 100-250 | 5-10 | $1,794-3,740 |

### Key Assumptions
- Free → Pro conversion: 5-10%
- Monthly churn (Pro): 10-15%
- Average free user daily usage: 15-20 min
- Average pro user daily usage: 30-45 min

## Competitor Margin Comparison

| | EnglishFriend Pro | TalkPal Premium | Gliglish | SPEAK |
|---|---|---|---|---|
| **Price** | $12.99/month | $9.99/month | $29/month | ~$20/month |
| **COGS/user** | ~$0.25-1 | ~$2-3 (API) | ~$3-5 (OpenAI) | ~$3-5 (custom ML) |
| **Gross margin** | **92-98%** | ~70% | ~83% | ~75% |
| **Voice stack** | Self-hosted | API-dependent | API-dependent | API-dependent |
| **Latency** | 200-400ms | 500-800ms | 500-1000ms | 300-500ms |
| **Full-duplex** | Yes | No | No | No |

## Strategic Advantage: Self-Hosted Economics

**Why self-hosted PersonaPlex changes the game**:

1. **Higher free tier generosity**: We can offer 30 min/day free vs 10 min at competitors — because our Pro tier margin covers it
2. **Lower price, better quality**: $12.99 with 200ms latency vs $20-29 with 500ms+ at competitors
3. **No API vendor risk**: TalkPal/Gliglish margins collapse if OpenAI raises prices; ours don't
4. **Linear scaling**: Adding GPU capacity ($50/month per server) scales to 200+ concurrent users each

**Trade-off**: Higher upfront complexity (GPU server management) but dramatically better unit economics at any scale.

## Sensitivity Analysis

| Factor | Optimistic | Base | Pessimistic |
|--------|-----------|------|-------------|
| Free→Pro conversion | 10% | 7% | 3% |
| Monthly churn | 8% | 12% | 20% |
| Avg free COGS | $1.50/month | $3/month | $7.50/month |
| GPU server cost | $50/month | $75/month | $150/month |
| Break-even (months) | 2 | 4 | 8+ |

---

*For pricing strategy, see [Business Strategy](./BUSINESS_STRATEGY.md)*
*For technical cost details, see [Technical Strategy](./TECHNICAL_STRATEGY.md)*
*For growth plan, see [Go-to-Market](./GO_TO_MARKET.md)*
