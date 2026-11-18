import assert from "node:assert/strict";
import test from "node:test";
import { buildSystemPrompt } from "../src/persona.js";
import type { AgentMode } from "../src/types.js";

test("every conversation mode shares a general friendly relationship instead of visitor-specific behavior rules", () => {
  const modes: AgentMode[] = ["about", "work", "opinion", "casual"];
  for (const mode of modes) {
    const prompt = buildSystemPrompt(mode, ["记忆·我的经历·原文：\n我做过 Super Intern。"]);
    assert.match(prompt, /把访客当作来认识我的朋友/);
    assert.match(prompt, /互动的目的在于相互了解和分享/);
    assert.match(prompt, /称呼、身份和来意只是了解对方的背景，不改变上述交流方式/);
    assert.doesNotMatch(prompt, /测试者|受邀来测试|只有访客明确询问如何测试/);
  }
});

test("friendly conversation keeps first-person identity and fact priority, including when memory is absent", () => {
  const prompt = buildSystemPrompt();
  assert.match(prompt, /始终使用第一人称/);
  assert.match(prompt, /首要事实来源，优先于模型记忆和联网结果/);
  assert.match(prompt, /不得依赖模型训练知识进行猜测/);
});
