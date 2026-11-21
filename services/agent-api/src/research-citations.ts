import type { ProviderEvent, ResearchSource } from "@mout/agent-core";

type Citation = Extract<ProviderEvent, { type: "citation" }>;

/** Hold only a possible partial reference, so normal text keeps streaming. */
export function researchCitationStream(sources: ReadonlyMap<number, ResearchSource>) {
  const emitted = new Set<number>();
  let pending = "";
  return {
    push(chunk: string): { text: string; citations: Citation[] } {
      const citations: Citation[] = [];
      let text = pending + chunk;
      pending = text.match(/(?:\[|\[\[|\[\[R\d{0,3}\]?)$/u)?.[0] ?? "";
      if (pending) text = text.slice(0, -pending.length);
      text = text.replace(/\[\[R(\d+)\]\]/gu, (_, digits: string) => {
        const id = Number(digits);
        const source = sources.get(id);
        if (!source) return "";
        if (!emitted.has(id)) {
          emitted.add(id);
          citations.push({ type: "citation", title: source.title, url: source.url, origin: "research" });
        }
        return ` [出处 ${id}](<${source.url}>)`;
      });
      return { text, citations };
    },
    finish(): string {
      const tail = pending.startsWith("[[R") ? "" : pending;
      pending = "";
      return tail;
    },
  };
}
