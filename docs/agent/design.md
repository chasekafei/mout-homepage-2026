# 独立 Agent 页视觉方向

`im.mout.me` 不采用通用客服或 SaaS 仪表盘的样式，而是把聊天页当成 MouT.me 里的一间夜间工作室。

## 借鉴的交互骨架

- ChatGPT：首屏只保留一个明确的提问动作，推荐问题围绕输入区展开；
- Claude：把与回答有关的上下文放在对话旁边，后续可以扩展成文章、项目或原型的侧栏；
- Perplexity：需要联网时显示搜索状态和来源，让访客知道哪些内容来自外部网络；
- Agent 工作台：长任务只显示必要的阶段状态，不把模型内部思考过程完整倾倒给访客。

## MouT.me 的独有部分

- 深色工作室背景，沿用网站的薄青、珊瑚和太阳黄；
- 左侧是 MouT 的真实照片、像素头像和一句个人表达；
- 中间保持单一对话焦点，回答使用自然文本，不做气泡堆叠；
- 右侧只在有来源或搜索状态时承担上下文角色；
- 移动端收起身份栏和来源栏，把头像、欢迎文案和输入区保留在一条垂直路径上；
- 首页 3D 场景使用同一套消息语义，但通过 Sheet 和 DOM overlay 呈现，不把聊天内容写入纹理。

参考入口：[ChatGPT](https://chatgpt.com/)、[Claude Artifacts](https://support.anthropic.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them)、[Perplexity](https://www.perplexity.ai/)。
