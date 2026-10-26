import { iconOf } from "../src/motion/diagram";
console.log(JSON.stringify(iconOf({ id: "c", type: "graphic", role: "primary", required: true, desc: "One group of astronaut silhouettes in cream standing", region: "right" })));
console.log(iconOf.toString().slice(0, 600));
