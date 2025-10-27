// constraints.cypher
// Apply via: cypher-shell -f graph/schema/constraints.cypher

create constraint user_id_unique if not exists
for (u:User) require u.userId is unique;

create constraint topic_id_unique if not exists
for (t:Topic) require t.id is unique;

create constraint topic_slug_unique if not exists
for (t:Topic) require t.slug is unique;

create constraint session_id_unique if not exists
for (s:Session) require s.id is unique;

create constraint utterance_id_unique if not exists
for (u:Utterance) require u.id is unique;

create constraint memory_id_unique if not exists
for (m:Memory) require m.id is unique;

create constraint persona_trait_unique if not exists
for (p:Persona) require (p.userId, p.trait) is unique;

create constraint emotion_code_unique if not exists
for (e:Emotion) require e.code is unique;
