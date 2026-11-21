import assert from "node:assert/strict";
import test from "node:test";
import { researchCitationStream } from "../src/research-citations.js";

test("research references render from the allowlist even when split across deltas", () => {
  const url = "https://example.com/filing?year=2026";
  const stream = researchCitationStream(new Map([[1, { title: "公开文件", url, basis: "primary" }]]));
  assert.deepEqual(stream.push("这里是历史数字。[["), { text: "这里是历史数字。", citations: [] });
  assert.deepEqual(stream.push("R1]"), { text: "", citations: [] });
  assert.deepEqual(stream.push("]下一句。[[R999]]"), {
    text: ` [出处 1](<${url}>)下一句。`,
    citations: [{ type: "citation", title: "公开文件", url, origin: "research" }],
  });
  assert.deepEqual(stream.push("第二处。[[R1]]"), { text: `第二处。 [出处 1](<${url}>)`, citations: [] });
  assert.equal(stream.push("到此为止。[[R12").text, "到此为止。");
  assert.equal(stream.finish(), "");
});
