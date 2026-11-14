const LUNAR_MONTHS: Record<string, number> = {
  "正月": 1, "一月": 1, "二月": 2, "三月": 3, "四月": 4, "五月": 5, "六月": 6,
  "七月": 7, "八月": 8, "九月": 9, "十月": 10, "十一月": 11, "冬月": 11, "十二月": 12, "腊月": 12,
};

const SOLAR_FESTIVALS: Record<string, string> = {
  "01-01": "元旦",
  "02-14": "情人节",
  "03-08": "国际妇女节",
  "04-01": "愚人节",
  "05-01": "劳动节",
  "06-01": "儿童节",
  "10-01": "国庆节",
  "12-24": "平安夜",
  "12-25": "圣诞节",
  "12-31": "跨年夜",
};

const isTimeZone = (value: string | undefined): value is string => {
  if (!value) return false;
  try {
    new Intl.DateTimeFormat("zh-CN", { timeZone: value }).format();
    return true;
  } catch {
    return false;
  }
};

function zoneParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  return Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
}

function lunarParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("zh-CN-u-ca-chinese", {
    timeZone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(date);
  const month = parts.find((part) => part.type === "month")?.value;
  const day = parts.find((part) => part.type === "day")?.value;
  return { month: month ? LUNAR_MONTHS[month] : undefined, monthLabel: month, day: day ? Number(day) : undefined };
}

function festivals(date: Date, timeZone: string): string[] {
  const current = zoneParts(date, timeZone);
  const names: string[] = [];
  const solar = `${current.month}-${current.day}`;
  if (SOLAR_FESTIVALS[solar]) names.push(SOLAR_FESTIVALS[solar]);
  const lunar = lunarParts(date, timeZone);
  const lunarFestivals: Record<string, string> = {
    "1-1": "春节",
    "1-15": "元宵节",
    "2-2": "龙抬头",
    "5-5": "端午节",
    "7-7": "七夕",
    "8-15": "中秋节",
    "9-9": "重阳节",
    "12-8": "腊八节",
  };
  if (lunar.month && lunar.day && lunarFestivals[`${lunar.month}-${lunar.day}`]) names.push(lunarFestivals[`${lunar.month}-${lunar.day}`]);
  return names;
}

export function buildRuntimeContext(now: Date, primaryTimeZone: string, visitorTimeZone?: string): string {
  const serverZone = isTimeZone(primaryTimeZone) ? primaryTimeZone : "Asia/Shanghai";
  const server = zoneParts(now, serverZone);
  const serverDate = `${server.year}-${server.month}-${server.day} ${server.hour}:${server.minute}:${server.second}`;
  const lines = [
    "运行时上下文（这是当前时间信息，不是 MouT 的个人经历）：",
    `- 服务器当前时间：${serverDate}（${serverZone}，${server.weekday}）`,
    `- 服务器当前节日提示：${festivals(now, serverZone).join("、") || "未识别到常见节日"}`,
  ];
  if (isTimeZone(visitorTimeZone) && visitorTimeZone !== serverZone) {
    const visitor = zoneParts(now, visitorTimeZone);
    lines.push(`- 访客当前时间：${visitor.year}-${visitor.month}-${visitor.day} ${visitor.hour}:${visitor.minute}:${visitor.second}（${visitorTimeZone}，${visitor.weekday}）`);
  }
  lines.push("- 回答“今天、现在、昨天、最近”等相对时间问题时，必须以以上时间为准；不要依赖模型训练数据中的当前日期。", "- 中国法定节假日调休和工作日安排不在此处推断，除非本轮联网搜索得到可信来源。");
  return lines.join("\n");
}
