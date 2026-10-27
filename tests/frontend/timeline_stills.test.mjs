// node --test tests/frontend/timeline_stills.test.mjs   (Node 24 runs the .ts helper directly; the frontend has no other test runner)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { stillsOfScene, sceneFilmstrip, stillAt } from '../../UI/frontend/src/components/timeline-build/timelineStills.ts';

const mk = (scene_id, kind, frame) => ({ scene_id, kind, frame, time_s: frame / 30, url: `/s/${scene_id}_${kind}.png` });
const samples = [mk('scene_02', 'entry', 368), mk('scene_01', 'mid', 170), mk('scene_01', 'entry', 41), mk('scene_01', 'transition', 334), mk('scene_01', 'pre_exit', 306)];

test('the timeline id scene_001 finds the stills of scene_01, in frame order', () => {
  assert.deepEqual(stillsOfScene(samples, 'scene_001').map(s => s.frame), [41, 170, 306, 334]);
});

test('the filmstrip leaves out the transition blend', () => {
  assert.deepEqual(sceneFilmstrip(samples, 'scene_001').map(s => s.kind), ['entry', 'mid', 'pre_exit']);
});

test('the frame shown is the nearest one of the playing scene, never one of its neighbour', () => {
  assert.equal(stillAt(samples, 'scene_001', 0).kind, 'entry');
  assert.equal(stillAt(samples, 'scene_001', 200).kind, 'mid');
  assert.equal(stillAt(samples, 'scene_001', 340).kind, 'transition');          // frame 340 is closest to the transition still of scene 1, not to scene 2's entry (368)
  assert.equal(stillAt(samples, 'scene_003', 700), null);                        // a scene without stills shows none
});
