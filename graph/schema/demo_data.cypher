// demo_data.cypher
// Demo data for Neo4j graph testing

// Create demo user
merge (u1:User {userId: 1})

// Create demo sessions
merge (s1:Session {id: '00000000-0000-0000-0000-000000000001'})
  on create set s1.startedAt = datetime('2025-01-10T10:00:00Z')
merge (s2:Session {id: '00000000-0000-0000-0000-000000000002'})
  on create set s2.startedAt = datetime('2025-01-10T11:00:00Z')

// Create demo utterances
merge (utt1:Utterance {id: '00000000-0000-0000-0000-000000000010'})
  on create set utt1.tStart = 0, utt1.tEnd = 1200, utt1.speaker = 'user'
merge (utt2:Utterance {id: '00000000-0000-0000-0000-000000000011'})
  on create set utt2.tStart = 1200, utt2.tEnd = 2400, utt2.speaker = 'assistant'
merge (utt3:Utterance {id: '00000000-0000-0000-0000-000000000012'})
  on create set utt3.tStart = 0, utt3.tEnd = 800, utt3.speaker = 'user'

// Create demo topics
merge (t1:Topic {id: '11111111-1111-1111-1111-111111111111'})
  on create set t1.slug = 'technology', t1.name = 'Technology'
merge (t2:Topic {id: '22222222-2222-2222-2222-222222222222'})
  on create set t2.slug = 'movies', t2.name = 'Movies & TV'
merge (t3:Topic {id: '33333333-3333-3333-3333-333333333333'})
  on create set t3.slug = 'sports', t3.name = 'Sports'

// Create demo emotions
merge (e1:Emotion {code: 'joy'})
  on create set e1.valence = 4, e1.arousal = 3
merge (e2:Emotion {code: 'calm'})
  on create set e2.valence = 2, e2.arousal = 1
merge (e3:Emotion {code: 'sadness'})
  on create set e3.valence = -3, e3.arousal = 2

// Create relationships
merge (u1)-[:PARTICIPATED_IN]->(s1)
merge (u1)-[:PARTICIPATED_IN]->(s2)
merge (s1)-[:CONTAINS]->(utt1)
merge (s1)-[:CONTAINS]->(utt2)
merge (s2)-[:CONTAINS]->(utt3)
merge (utt1)-[:ABOUT {score: 0.8, first_seen: datetime(), last_seen: datetime(), count: 1}]->(t1)
merge (utt2)-[:ABOUT {score: 0.6, first_seen: datetime(), last_seen: datetime(), count: 1}]->(t1)
merge (utt3)-[:ABOUT {score: 0.9, first_seen: datetime(), last_seen: datetime(), count: 1}]->(t2)
merge (utt1)-[:EXPRESSES {score: 0.8}]->(e1)
merge (utt2)-[:EXPRESSES {score: 0.6}]->(e2)
merge (utt3)-[:EXPRESSES {score: 0.7}]->(e1)
merge (u1)-[:INTEREST_IN {weight: 0.8, first_seen: datetime(), last_seen: datetime(), count: 1}]->(t1)
merge (u1)-[:INTEREST_IN {weight: 0.6, first_seen: datetime(), last_seen: datetime(), count: 1}]->(t2)
merge (u1)-[:INTEREST_IN {weight: 0.9, first_seen: datetime(), last_seen: datetime(), count: 1}]->(t3)

// Create topic relationships
merge (t1)-[:RELATED_TO {weight: 0.7}]->(t2)
merge (t2)-[:RELATED_TO {weight: 0.7}]->(t1)
merge (t1)-[:RELATED_TO {weight: 0.5}]->(t3)
merge (t3)-[:RELATED_TO {weight: 0.5}]->(t1)
