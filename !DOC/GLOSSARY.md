# Glossary - Technical Terms

---
last_updated: 2025-01-31
---

## Summary

This glossary defines technical terms and acronyms used throughout the EnglishFriend documentation.

---

## AI & Machine Learning

### CDC (Change Data Capture)
Technology for tracking and capturing changes in database tables in real-time. Used to synchronize data between PostgreSQL, Neo4j, and Qdrant.

### Embedding
Vector representation of text or other data that captures semantic meaning. Used for similarity search in vector databases.

### FSRS (Free Spaced Repetition Scheduler)
Modern spaced repetition algorithm that predicts optimal review intervals for vocabulary learning. Successor to SM-2 (SuperMemo 2).

### JEPA (Joint Embedding Predictive Architecture)
Self-supervised learning architecture proposed by Yann LeCun. Predicts in embedding space rather than generating pixels/tokens directly.

### LangGraph
Framework for building stateful, multi-actor applications with LLMs. Used for orchestrating our AI agent's conversation flow.

### LLM (Large Language Model)
AI model trained on vast amounts of text data. Examples: GPT-4, Claude, Llama.

### RAG (Retrieval-Augmented Generation)
Technique that enhances LLM responses by retrieving relevant information from a knowledge base before generating answers.

### RLS (Row-Level Security)
PostgreSQL feature that restricts which rows users can access based on policies. Used to isolate user data.

### SRS (Spaced Repetition System)
Learning technique that schedules review of information at increasing intervals. Proven to improve long-term retention.

### VAD (Voice Activity Detection)
Algorithm that detects when a person is speaking vs silence. Critical for natural conversation flow.

### WER (Word Error Rate)
Metric for measuring speech recognition accuracy. Lower is better. Vosk: ~10-15%, Deepgram: ~5.8%.

---

## Voice AI Technologies

### Deepgram Nova-3
State-of-the-art speech-to-text API with 5.8% WER. Used in Premium Tier.

### edge-tts
Microsoft's text-to-speech service. Free, good quality, used in Free Tier.

### ElevenLabs
Premium text-to-speech service with natural voices and low latency (75ms). Used in Premium/Ultra Tiers.

### Groq
Fast LLM inference API. Free tier available, used in MVP.

### Hume AI EVI (Empathic Voice Interface)
Voice AI with emotional intelligence. Detects user emotions and adapts responses.

### Moshi
Open-source full-duplex voice AI from Kyutai lab. 160-200ms latency, self-hostable.

### OpenAI Realtime API
Speech-to-speech API that processes audio directly without separate STT/TTS steps. Used in Ultra Tier.

### Pipecat
Open-source voice AI framework for orchestrating STT/LLM/TTS pipelines.

### Ultravox
Speech-native LLM that understands audio directly. Alternative to traditional STT→LLM→TTS cascade.

### Vosk
Open-source speech recognition that runs in browser via WASM. Used in Free Tier.

---

## Database Technologies

### Neo4j
Graph database used for storing relationships between users, topics, emotions, and interests.

### Partition
Database technique for splitting large tables into smaller, more manageable pieces. Used for `sessions`, `utterances`, `xp_events`.

### pgvector
PostgreSQL extension for vector similarity search. Fallback option if Qdrant unavailable.

### Qdrant
Vector database optimized for similarity search. Used for semantic search over user memories.

### PostgreSQL
Primary relational database. Source of truth for all user data.

---

## Architecture Patterns

### CDC Pipeline
Change Data Capture pipeline: PostgreSQL → Debezium → Kafka → sync-vector/sync-graph → Qdrant/Neo4j

### DLQ (Dead Letter Queue)
Queue for messages that failed processing. Allows retry without blocking main pipeline.

### Materialized View
Pre-computed query result stored as a table. Used for analytics dashboards.

### Microservices
Architecture pattern where application is composed of small, independent services.

### WebRTC
Real-time communication protocol for audio/video in browsers. Used for voice calls.

### WebSocket
Protocol for bidirectional communication between client and server. Used for real-time chat.

---

## Learning Methodologies

### CEFR (Common European Framework of Reference)
Standard for measuring language proficiency: A1, A2, B1, B2, C1, C2.

### EPI (Extensive Processing Instruction)
Language teaching methodology: Input processing → Fluency → Listening → Pronunciation → Grammar.

### Socratic Method
Teaching technique using questions to guide students to discover answers themselves.

### SLA (Second Language Acquisition)
Academic field studying how people learn second languages.

---

## Business Terms

### Churn Rate
Percentage of subscribers who cancel their subscription in a given period.

### COGS (Cost of Goods Sold)
Direct costs of producing a service. For us: API costs (STT, LLM, TTS).

### Freemium
Business model with free basic tier and paid premium features.

### LTV (Lifetime Value)
Total revenue expected from a customer over their entire relationship with the product.

### NPS (Net Promoter Score)
Customer satisfaction metric: "How likely are you to recommend us?" (-100 to +100).

### Retention
Percentage of users who continue using the product after a given period.

---

## Development Tools

### Debezium
Open-source platform for change data capture (CDC).

### Docker Compose
Tool for defining and running multi-container Docker applications.

### FastAPI
Modern Python web framework for building APIs.

### Flyway / Liquibase
Database migration tools for version control of database schemas.

### Grafana
Visualization platform for metrics and logs.

### Kafka
Distributed event streaming platform. Used for CDC events.

### pgTAP
Unit testing framework for PostgreSQL.

### Prometheus
Monitoring system and time series database.

### pytest
Python testing framework.

---

## Acronyms

| Acronym | Full Name | Description |
|---------|-----------|-------------|
| AI | Artificial Intelligence | Computer systems that mimic human intelligence |
| API | Application Programming Interface | Interface for software components to communicate |
| CDC | Change Data Capture | Real-time database change tracking |
| CEFR | Common European Framework of Reference | Language proficiency standard |
| COGS | Cost of Goods Sold | Direct production costs |
| DLQ | Dead Letter Queue | Failed message queue |
| EPI | Extensive Processing Instruction | Language teaching methodology |
| FSRS | Free Spaced Repetition Scheduler | Spaced repetition algorithm |
| JEPA | Joint Embedding Predictive Architecture | Self-supervised learning architecture |
| LLM | Large Language Model | AI trained on text data |
| LTV | Lifetime Value | Customer lifetime revenue |
| MVP | Minimum Viable Product | Simplest version of product |
| NPS | Net Promoter Score | Customer satisfaction metric |
| RAG | Retrieval-Augmented Generation | LLM + knowledge base |
| RLS | Row-Level Security | Database access control |
| SLA | Second Language Acquisition | Language learning research field |
| SRS | Spaced Repetition System | Learning technique |
| STT | Speech-to-Text | Voice recognition |
| TTS | Text-to-Speech | Voice synthesis |
| VAD | Voice Activity Detection | Speech detection algorithm |
| WER | Word Error Rate | Speech recognition accuracy metric |

---

**Last Updated**: 2025-01-31
