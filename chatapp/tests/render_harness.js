// Reads a JSON list of texts on stdin, writes the rendered HTML for each as a JSON list.
const { renderMarkdown } = require("../app/static/render.js");
let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  const cases = JSON.parse(input);
  process.stdout.write(JSON.stringify(cases.map((c) => renderMarkdown(c.text, c.mentions ? new Set(c.mentions) : null))));
});
