// node --test tests/frontend/timeline_captions.test.mjs   (Node 24 runs the .ts helper directly)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { captionBlocks, sceneNarration, sceneTransitions } from '../../UI/frontend/src/components/timeline-build/timelineCaptions.ts';

const segs = [
  { id: 0, start: 0.0, end: 4.12, text: 'business owners మరి freelancers' },
  { id: 1, start: 4.12, end: 5.02, text: '' },                                 // noise: no words
  { id: 2, start: 5.05, end: 10.97, text: ' virtual assistant ' },
  { id: 3, start: 11.35, end: 11.35, text: 'zero length' },
];

test('a caption per spoken segment, in frames, and none for noise or a zero-length segment', () => {
  const c = captionBlocks(segs, 30);
  assert.deepEqual(c.map(b => [b.id, b.startFrame, b.endFrame, b.text]), [[0, 0, 124, 'business owners మరి freelancers'], [2, 152, 329, 'virtual assistant']]);
});

test('the narration of a scene is the segments whose middle is inside its frames', () => {
  assert.equal(sceneNarration(segs, 0, 330, 30), 'business owners మరి freelancers virtual assistant');
  assert.equal(sceneNarration(segs, 130, 330, 30), 'virtual assistant');          // segment 0 is centred at frame 62: not in this scene
  assert.equal(sceneNarration(segs, 400, 500, 30), '');
});

test('the transition into and out of a scene', () => {
  const t = [{ transition_id: 'a', from_scene: 'scene_001', to_scene: 'scene_002', start_frame: 152, end_frame: 165, boundary_frame: 152, type: 'fade' },
             { transition_id: 'b', from_scene: 'scene_002', to_scene: 'scene_003', start_frame: 341, end_frame: 354, boundary_frame: 341, type: 'wipe' }];
  assert.deepEqual([sceneTransitions(t, 'scene_002').into?.type, sceneTransitions(t, 'scene_002').out?.type], ['fade', 'wipe']);
  assert.deepEqual([sceneTransitions(t, 'scene_001').into, sceneTransitions(t, 'scene_003').out], [null, null]);
});
