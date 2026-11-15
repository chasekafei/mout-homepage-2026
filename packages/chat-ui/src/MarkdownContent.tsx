import { Marked } from "marked";
import { memo, type ReactNode, useMemo } from "react";

type TokenLike = {
  type: string;
  text?: string;
  raw?: string;
  depth?: number;
  href?: string;
  title?: string | null;
  ordered?: boolean;
  start?: number;
  items?: TokenLike[];
  tokens?: TokenLike[];
  header?: TokenLike[];
  rows?: TokenLike[][];
};

const parser = new Marked({ gfm: true, breaks: true });
const SAFE_PROTOCOLS = new Set(["http:", "https:", "mailto:", "tel:"]);

function safeHref(href: string | undefined): { href: string; external: boolean } | null {
  if (!href) return null;
  try {
    const url = new URL(href, window.location.origin);
    if (!SAFE_PROTOCOLS.has(url.protocol)) return null;
    return { href, external: url.protocol === "http:" || url.protocol === "https:" };
  } catch {
    return null;
  }
}

function inline(tokens: TokenLike[] | undefined, key: string): ReactNode[] {
  if (!tokens) return [];
  return tokens.map((token, index) => {
    const childKey = `${key}-${index}`;
    switch (token.type) {
      case "strong": return <strong key={childKey}>{inline(token.tokens, childKey)}</strong>;
      case "em": return <em key={childKey}>{inline(token.tokens, childKey)}</em>;
      case "del": return <del key={childKey}>{inline(token.tokens, childKey)}</del>;
      case "codespan": return <code key={childKey}>{token.text ?? ""}</code>;
      case "br": return <br key={childKey} />;
      case "link": {
        const target = safeHref(token.href);
        const content = inline(token.tokens, childKey);
        return target
          ? <a key={childKey} href={target.href} title={token.title ?? undefined} target={target.external ? "_blank" : undefined} rel={target.external ? "noopener noreferrer nofollow" : undefined}>{content}</a>
          : <span key={childKey}>{content}</span>;
      }
      case "image":
      case "html": return null;
      case "escape":
      case "text":
      case "inlineText":
      case "autolink":
      case "url": return token.tokens
        ? <span key={childKey}>{inline(token.tokens, childKey)}</span>
        : <span key={childKey}>{token.text ?? token.raw ?? ""}</span>;
      default: return token.text ? <span key={childKey}>{token.text}</span> : null;
    }
  });
}

function blocks(tokens: TokenLike[], key: string): ReactNode[] {
  return tokens.map((token, index) => {
    const childKey = `${key}-${index}`;
    switch (token.type) {
      case "heading": {
        const children = inline(token.tokens, childKey);
        if (token.depth === 1) return <h1 key={childKey}>{children}</h1>;
        if (token.depth === 2) return <h2 key={childKey}>{children}</h2>;
        if (token.depth === 3) return <h3 key={childKey}>{children}</h3>;
        return <h4 key={childKey}>{children}</h4>;
      }
      case "paragraph": return <p key={childKey}>{inline(token.tokens, childKey)}</p>;
      case "blockquote": return <blockquote key={childKey}>{blocks(token.tokens ?? [], childKey)}</blockquote>;
      case "list": {
        const children = (token.items ?? []).map((item, itemIndex) => <li key={`${childKey}-${itemIndex}`}>{blocks(item.tokens ?? [], `${childKey}-${itemIndex}`)}</li>);
        return token.ordered
          ? <ol key={childKey} start={token.start ?? 1}>{children}</ol>
          : <ul key={childKey}>{children}</ul>;
      }
      case "code": return <pre key={childKey}><code>{token.text ?? ""}</code></pre>;
      case "hr": return <hr key={childKey} />;
      case "table": return (
        <div className="markdown-table-scroll" key={childKey}>
          <table>
            <thead><tr>{(token.header ?? []).map((cell, cellIndex) => <th key={`${childKey}-h${cellIndex}`}>{inline(cell.tokens, `${childKey}-h${cellIndex}`)}</th>)}</tr></thead>
            <tbody>{(token.rows ?? []).map((row, rowIndex) => <tr key={`${childKey}-r${rowIndex}`}>{row.map((cell, cellIndex) => <td key={`${childKey}-r${rowIndex}-${cellIndex}`}>{inline(cell.tokens, `${childKey}-r${rowIndex}-${cellIndex}`)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      );
      case "space":
      case "def":
      case "html": return null;
      case "text": return <p key={childKey}>{inline(token.tokens, childKey)}</p>;
      default: return token.text ? <p key={childKey}>{token.text}</p> : null;
    }
  });
}

function renderMarkdown(source: string): ReactNode[] {
  const tokens = parser.lexer(source) as unknown as TokenLike[];
  return blocks(tokens, "md");
}

export const MarkdownContent = memo(function MarkdownContent({ content, className = "" }: { content: string; className?: string }) {
  const children = useMemo(() => renderMarkdown(content), [content]);
  return <div className={`markdown-content ${className}`}>{children}</div>;
});
