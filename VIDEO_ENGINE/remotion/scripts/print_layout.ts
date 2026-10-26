// npx tsx scripts/print_layout.ts
// Prints the frame-dependent layout for 16:9 and 9:16, so tests/test_m9_portrait.py can compare it with theme.json and the Python side.
import { layoutFor } from "../src/theme";

console.log(JSON.stringify({ landscape: layoutFor(1920, 1080), portrait: layoutFor(1080, 1920) }));
