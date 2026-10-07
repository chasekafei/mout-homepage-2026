export type StateId = "now" | "create" | "play" | "work" | "depart" | "chat";

export const STATES: { id: StateId; label: string; ready: boolean; teaser: string }[] = [
  { id: "now", label: "此刻", ready: true, teaser: "" },
  { id: "create", label: "创作", ready: true, teaser: "" },
  { id: "play", label: "游戏", ready: false, teaser: "游戏场景还在搭：GBA 婚礼请柬小游戏、FC 与 MD 的童年电视，以及一千多款游戏的存档架。" },
  { id: "work", label: "工作", ready: true, teaser: "" },
  { id: "depart", label: "出发", ready: false, teaser: "出发场景还在搭：同一个座位，车窗外换成新疆、巴统、福冈或多哈。" },
  { id: "chat", label: "和我聊聊", ready: true, teaser: "" },
];

export type HotspotId =
  | "writing" | "podcast" | "products" | "rubik" | "cat_shaojiu" | "cat_xiaoba" | "me" | "books" | "window"
  | "project" | "thought"
  | "agent" | "social" | "games" | "brand" | "gov";

export type Hotspot = { id: HotspotId; route: string; label: string; hint: string; kind: string };

/** Order matches the mask encoding in tools/scene/scene_create.py: R = (index + 1) * 16. */
export const HOTSPOTS: Hotspot[] = [
  { id: "writing", route: "writing", kind: "WRITING", label: "日记与报纸", hint: "写作、Newsletter 和短想法。从《社思现场》开始。" },
  { id: "podcast", route: "podcast", kind: "PODCAST", label: "麦克风", hint: "CrossPod 串台：用你和朋友的声音开一期播客。" },
  { id: "products", route: "products", kind: "PROTOTYPES", label: "原型卡带仓", hint: "Find Muse、Dimensional Inn、stpHQ，还有一个空插槽。" },
  { id: "rubik", route: "legacy", kind: "WEB EXPERIMENT", label: "三阶魔方", hint: "大学时用纯 CSS3 写的旧首页，会像魔方一样翻面。" },
  { id: "cat_shaojiu", route: "cats/shaojiu", kind: "CAT", label: "烧酒", hint: "狸花猫，在桌角卷成一团。" },
  { id: "cat_xiaoba", route: "cats/xiaoba", kind: "CAT", label: "小八", hint: "英短蓝白，摊在麦克风旁边晒太阳。" },
  { id: "me", route: "me", kind: "MOUT.ME", label: "MouT.me", hint: "表面情绪稳定，脑子里一直在施工。" },
  { id: "books", route: "books", kind: "METHOD", label: "四本书", hint: "Write、Podcast、Prototype、A Kinder Internet。" },
  { id: "window", route: "window", kind: "OUTSIDE", label: "窗外", hint: "远程工作之后，我常常一边工作一边出发。" },
];

/** Order matches tools/scene/scene_now.py. */
export const NOW_HOTSPOTS: Hotspot[] = [
  { id: "project", route: "project", kind: "NOW BUILDING", label: "笔记本上的 MouT.me", hint: "现在在做的，就是你正在看的这个网站。" },
  { id: "thought", route: "thought", kind: "LATELY", label: "杯垫上的一句话", hint: "最近一直在想的一个问题。" },
  { id: "me", route: "me", kind: "AI CLONE", label: "MouT.me", hint: "我在写东西。你可以先和我的分身聊聊。" },
  { id: "cat_shaojiu", route: "cats/shaojiu", kind: "CAT", label: "烧酒", hint: "狸花猫，在窗台上卷成一团晒太阳。" },
  { id: "cat_xiaoba", route: "cats/xiaoba", kind: "CAT", label: "小八", hint: "英短蓝白，霸占了笔记本旁边的半张桌子。" },
  { id: "window", route: "window", kind: "OUTSIDE", label: "窗外的街", hint: "远程工作之后，换个地方坐坐也算出发。" },
];

/** Order matches tools/scene/scene_work.py. */
export const WORK_HOTSPOTS: Hotspot[] = [
  { id: "agent", route: "agent", kind: "AI AGENT", label: "AI Agent 核心", hint: "正前方这颗方块：Super Intern、fakers 和超参数的那几年。" },
  { id: "social", route: "social", kind: "SOCIAL", label: "语音房", hint: "荔枝 TIYA 的熟人语音房，和《社思现场》。" },
  { id: "games", route: "games", kind: "GAMES", label: "游戏关卡", hint: "三年游戏创业：定制小游戏、自研，和互动营销。" },
  { id: "brand", route: "brand", kind: "BRAND", label: "品牌营销", hint: "省广集团的 H5，和微信全年 campaign 里的 Fendi、迪士尼、长城。" },
  { id: "gov", route: "gov", kind: "E-GOV", label: "电子政务", hint: "第一份工作：把政务搬上微信和小程序。" },
  { id: "me", route: "me", kind: "MOUT.ME", label: "MouT.me", hint: "一根线从最上面的政务大楼接下来，一直接到正前方的 Agent。" },
  { id: "cat_shaojiu", route: "cats/shaojiu", kind: "CAT", label: "烧酒", hint: "狸花猫，睡在台灯底下最暖的那一块。" },
  { id: "cat_xiaoba", route: "cats/xiaoba", kind: "CAT", label: "小八", hint: "英短蓝白，在窗台上看夜景。" },
  { id: "window", route: "window", kind: "OUTSIDE", label: "窗外", hint: "远程工作的那几年，大部分时间是在这扇窗前度过的。" },
];

/** States that have their own 3D room. Every room shares the character, seat and camera. */
export type SceneId = "now" | "create" | "work";

export type SceneDef = {
  id: SceneId;
  label: string;
  hotspots: Hotspot[];
  /** One line under the scene; `{act}` becomes the hover / tap instruction. */
  caption: string;
  /** Pre-rendered 2.5D fallback exists in public/scene/<id>/. */
  flat: boolean;
};

export const SCENES: Record<SceneId, SceneDef> = {
  now: { id: "now", label: "此刻", hotspots: NOW_HOTSPOTS, caption: "最近在做的、在想的，和两只猫今天的样子。{act}", flat: true },
  create: { id: "create", label: "创作", hotspots: HOTSPOTS, caption: "写作、播客和独立产品。{act}", flat: true },
  work: { id: "work", label: "工作", hotspots: WORK_HOTSPOTS, caption: "做过的每一个行业，都接进了现在的 AI Agent。{act}", flat: true },
};

export const isScene = (s: string): s is SceneId => s in SCENES;

export const hotspotByRoute = (scene: SceneId, r: string) =>
  SCENES[scene].hotspots.find((h) => r === h.route || r.startsWith(h.route + "/"));

export const NOW = {
  project: {
    name: "MouT.me",
    status: "三个场景已经搭好",
    oneLine: "一个可以坐进去的个人网站：同一个我、同一个座位，导航换的是房间。",
    notes: [
      "房间在 Blender 里程序化建模，Cycles 把光照烘焙进贴图，浏览器里用 three.js 实时渲染。",
      "每个场景只换环境、灯光和物件，角色的坐姿和镜头永远不变，切换时只有房间在变。",
      "目前完成了「此刻」「创作」和「工作」，接下来是「游戏」和「出发」。",
    ],
  },
  thought: {
    q: "AI 让做东西变得这么容易之后，什么才是值得做的？",
    body: [
      "以前一个想法从脑子里到能用，中间隔着设计、开发、上线。现在一个人一个周末就能走完。",
      "门槛没了以后，我发现自己更常问的是：这个东西是为谁做的？它会让谁的一天好一点？",
    ],
  },
};

export type WorkId = "gov" | "brand" | "games" | "social" | "agent";

export type WorkStop = {
  id: WorkId;
  name: string;
  where: string;
  role: string;
  oneLine: string;
  items: { t: string; d: string }[];
  /** What this stop handed to the next one. */
  carry: string;
};

/** Oldest first: the order the cable runs through the modules into the Agent. */
export const WORK: WorkStop[] = [
  {
    id: "gov",
    name: "电子政务",
    where: "中山 → 广州的创业公司",
    role: "设计、前端，后来是项目经理和售前",
    oneLine: "第一份工作。政府软件还是死板的桌面客户端，我们往里面嵌网页，再把整套政务搬上微信。",
    items: [
      { t: "身兼数职", d: "白天跟老板见客户、讲方案，晚上回去改 PPT，连夜用设计和前端赶出能演示的 demo。" },
      { t: "海珠区政务微信", d: "给广州海珠区政务办做了一套微信上的政务系统，后来又做了小程序，让市民在手机上办事。" },
      { t: "一次采访", d: "因为这套模式，作为代表接受了《南方日报》关于微信政务生态的采访。" },
    ],
    carry: "学会了先听懂客户要什么，再决定做什么、怎么讲。",
  },
  {
    id: "brand",
    name: "品牌营销",
    where: "省广集团 → 子公司创业",
    role: "技术开发 → 业务 coordinator → 产品经理",
    oneLine: "趁着 HTML5 高速发展，用 H5 和小游戏做那些会被转发到群里和朋友圈的营销玩法。",
    items: [
      { t: "打通各岗位", d: "设计、开发、项目都做过，创意会上能当场评估方案的可行性和成本，内部竞选成了业务 coordinator。" },
      { t: "产品化", d: "跟着老板出来创业，把定制项目里的共性抽成一个 to B 的 SaaS 平台，开始做产品经理。" },
    ],
    carry: "从执行走进了创意策划，也第一次把项目抽象成产品。",
  },
  {
    id: "games",
    name: "游戏",
    where: "和两位前同事合伙创业，三年",
    role: "合伙人、游戏策划，忙起来也自己做",
    oneLine: "从小玩到大的东西，终于变成了工作：定制小游戏、自研游戏，和游戏化互动营销。",
    items: [
      { t: "定制小游戏", d: "第一年给缺内容的小游戏平台快速定制，同时开发很多款。" },
      { t: "微信全年 campaign", d: "拿下微信年度品牌营销里的小游戏章节，十几版整合方案后落地：Fendi 罗马大秀预热的跑酷、迪士尼《玩具总动员 4》、中国长城的烧砖小游戏。" },
      { t: "之后", d: "QQ 的贝多芬诞辰文创项目、萧邦的游戏化项目。后来资金压力太大，公司停了。" },
    ],
    carry: "几十款小游戏的经验，成了进入社交团队的敲门砖。",
  },
  {
    id: "social",
    name: "社交",
    where: "荔枝 · TIYA",
    role: "产品经理",
    oneLine: "面向美国青少年游戏玩家的熟人语音房：一起开黑，玩完接着聊。",
    items: [
      { t: "语音房小游戏", d: "从房间内互动游戏的策划做起，帮团队理解游戏开发和 App 开发的不同。" },
      { t: "Figma 原型", d: "大家还在用 Axure 的时候，我拿出了带交互和动效的 Figma 原型。" },
      { t: "《社思现场》", d: "为了补齐社交行业认知，每周整理熟人社交产品的动态，先在公司内部发，后来公开成 Newsletter。" },
    ],
    carry: "ChatGPT 出来之前，我在内部创业比赛里提了一个 AI 社交项目。",
  },
  {
    id: "agent",
    name: "AI Agent",
    where: "超参数 → 英国团队",
    role: "产品经理",
    oneLine: "从 AI 拍照社交、AI 主播，一路做到能调用几百个工具的通用 Agent。",
    items: [
      { t: "超参数", d: "起司 AI 拍照社交；读 B 站弹幕、会主动怼人的 AI 主播，做到过 B 站 AI 主播前三；还有 AI 陪玩。" },
      { t: "fakers", d: "AI 资讯社区：每个 AI 博主有自己的人格和关注方向，替你从信息洪流里筛出可靠的内容。" },
      { t: "Super Intern", d: "住在 Discord、Telegram 里的通用 Agent：搜索、文档、生图、邮件、数据库、日程，用自然语言写成 Skill，再上架到 Skill Marketplace。" },
    ],
    carry: "做 AI 产品最重要的，是让用户更主动、更完整地交出他的 context。",
  },
];

export type Product = {
  id: string;
  name: string;
  zh: string;
  slot: "cream" | "mint" | "orange" | "teal";
  status: string;
  oneLine: string;
  why: string;
  notes: string[];
  url?: string;
};

export const PRODUCTS: Product[] = [
  {
    id: "find-muse",
    name: "Find Muse",
    zh: "长篇创作工作室",
    slot: "cream",
    status: "第一版已交给朋友内测",
    oneLine: "AI 辅助的结构化长篇创作：剧情大纲、角色一致性、伏笔回收，全部可追踪、可控制。",
    why: "单靠模型写长篇，内容一多就前后照不上。我想让它先和作者把类型、原则和节奏讨论清楚，再按管线往下写。",
    notes: [
      "开写之前先生成角色、世界观、关键事件和伏笔，整本书的节奏也提前排好。",
      "小说、短剧和跑团剧本的节奏规则各不相同，比如短剧第一集就要有明显的冲突和反转。",
      "现在在做网文风格和节奏的蒸馏：AI 写得太像文学作品，场景和心理描写过多。",
    ],
    url: "https://findmuse.com",
  },
  {
    id: "dimensional-inn",
    name: "Dimensional Inn",
    zh: "次元客栈",
    slot: "mint",
    status: "在我自己的 Discord 里天天运行",
    oneLine: "一个住在 Discord 里的 AI Agent，让不会搭 SillyTavern 的人也能直接在群里玩角色扮演。",
    why: "酒馆玩家大多在 Discord，但很多人不会搭建，也没法一直开着电脑。那就把客栈直接开在群里。",
    notes: [
      "兼容 SillyTavern 的角色卡和预设，可以对话，也能生成图片、语音和音乐。",
      "后来又加了每天收集 AI、游戏日报的能力。",
      "基本是一个人，用另一种思路复刻了前公司 Agent 的一部分能力。",
    ],
  },
  {
    id: "stphq",
    name: "stpHQ",
    zh: "薯条情报局",
    slot: "orange",
    status: "实验中，不确定性最强的一个",
    oneLine: "给莎头粉丝做的乒乓球数据工具：积分、排名、赛程、名次变化推演，一个地方全查到。",
    why: "看王楚钦和孙颖莎在低谷里一次次把自己打回来，给了我很多继续往前走的力量。于是想替同样在追比赛的人做一个顺手的工具。",
    notes: [
      "可以查积分，并推算某场比赛拿到特定名次后的积分变化。",
      "可以看接下来的赛程，以及和 STP 有关的内容。",
      "品牌原则只有一句：功能名先让人看懂，品牌感是调味料不是主菜。",
    ],
  },
];

export const CATS = {
  shaojiu: {
    name: "烧酒",
    breed: "狸花猫",
    spot: { create: "桌子左角", now: "窗台", work: "台灯底下" },
    lines: ["深棕色虎斑，白下巴、白爪子。", "在创作场景里，它卷成一团睡在桌子的左角；在咖啡馆里，它占了窗台上最晒的那一块。"],
  },
  xiaoba: {
    name: "小八",
    breed: "英短蓝白",
    spot: { create: "麦克风旁边", now: "笔记本旁边", work: "窗台" },
    lines: ["蓝灰色的背，白色的胸口和爪子。", "在创作场景里，它摊开躺在麦克风旁边，正好压着一块阳光；在咖啡馆里，它直接占了笔记本旁边的半张桌子。"],
  },
} as const;

export const ABOUT = {
  lead: "我喜欢把看起来不相关的东西连在一起，然后把它做出来。",
  words: ["好奇", "突破", "不设限", "共情"],
  chain: "好奇让我注意到新的可能；突破让我不满足于已有答案；不设限让我愿意跨过岗位和能力边界亲手实现；共情决定这些探索最终应该为谁服务。",
  timeline: [
    { t: "3 岁", d: "跟着爸爸和舅舅去游戏厅。家里先后有了 FC、MD 和电脑，放学后同学们会围在我家的小电视前轮流玩。" },
    { t: "初中起", d: "在中国博客网、百度空间写博客；大学和朋友用 WordPress 建站，用纯 CSS3 写了一个会像魔方翻面的个人首页。" },
    { t: "游戏与品牌", d: "做过游戏创业和商业小游戏，也拿下过微信年度营销 Campaign 的比稿，对接 FENDI、迪士尼和中国长城。" },
    { t: "社交", d: "在荔枝做熟人社交与语音房。为了补齐行业认知，开始写 Newsletter《社思现场》，后来公开发布。" },
    { t: "AI", d: "在 ChatGPT 之前就在内部创业比赛里押注 AI；后来做 AI VTuber、Super Intern，一路做到通用 Agent。" },
    { t: "现在", d: "暂时没去找新工作，用 AI web coding 做自己的产品：CrossPod、Find Muse、Dimensional Inn、stpHQ，还有这个网站。" },
  ],
  life: "远程工作那几年，我去了两次日本、多哈、港澳、成都、重庆、大连、长沙，自驾走完北疆大环线，最近又在格鲁吉亚待了 13 天。上午的电影院经常只有我一个人。",
  contact: [] as { label: string; href: string }[],
};

export const BOOKS = [
  { spine: "Write", zh: "写下来", d: "强迫自己输出，逼自己做更多的思考和输入。《社思现场》就是这么开始的。" },
  { spine: "Podcast", zh: "说出来", d: "我更想听身边某个人的看法，因为他会站在我的角度想问题。" },
  { spine: "Prototype", zh: "做出来", d: "从 Figma 交互原型到 AI web coding，先把东西做出来，再一起讨论。" },
  { spine: "A Kinder Internet", zh: "为谁做", d: "看到人的处境、关系和表达方式。不给访客增加负担，也是一种体验上的较真。" },
];

export const PODCAST = {
  show: "串台 CrossPod",
  slogan: "随时召唤好友分身，开一期只属于你们的播客。",
  episode: { title: "AI 扯淡夜话局", src: "/audio/crosspod-ai-night-talk.mp3", note: "一期用 CrossPod 生成的串台节目。" },
  pitch: [
    "看到一篇文章时，我们常常会想：要是能听听某某某怎么说就好了。他不一定是最懂的专家，但他会从你的角度帮你想。",
    "NotebookLM 生成的播客很好，但它始终不是你的。用你和朋友的声音完成一期节目之后，你会觉得它属于你们。",
    "所以 CrossPod 不和大厂拼音质，而是做成一种社交：你不在的时候，你的分身替你出现；朋友召唤它，它替你参与。",
  ],
};
