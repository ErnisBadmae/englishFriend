// reference_seed.cypher
// Prime Topic and Emotion nodes from Postgres dims.

:param topics => [
  {id:'11111111-1111-1111-1111-111111111111', slug:'technology', name:'Technology'},
  {id:'22222222-2222-2222-2222-222222222222', slug:'movies', name:'Movies & TV'},
  {id:'33333333-3333-3333-3333-333333333333', slug:'sports', name:'Sports'}
];

:param emotions => [
  {code:'joy', valence:4, arousal:3},
  {code:'calm', valence:2, arousal:1},
  {code:'sadness', valence:-3, arousal:2},
  {code:'anxiety', valence:-2, arousal:4}
];

unwind $topics as topic
merge (t:Topic {id:topic.id})
  on create set t.slug = topic.slug, t.name = topic.name;

unwind $emotions as emo
merge (e:Emotion {code:emo.code})
  on create set e.valence = emo.valence, e.arousal = emo.arousal;
