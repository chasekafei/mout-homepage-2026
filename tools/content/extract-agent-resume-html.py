import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class Element:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()


class ResumeParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("root", [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "button"}:
            return
        node = Element(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag not in {"script", "style", "button"}:
            self.stack[-1].children.append(Element(tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].children.append(data)


def descendants(node, tag=None, class_name=None):
    for child in node.children:
        if isinstance(child, Element):
            if (tag is None or child.tag == tag) and (class_name is None or child.has_class(class_name)):
                yield child
            yield from descendants(child, tag, class_name)


def text_content(node):
    def collect(current):
        parts = []
        for child in current.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag == "br":
                parts.append(" ")
            else:
                value = collect(child)
                if child.tag in {"p", "li", "div", "h1", "h2", "h3"}:
                    parts.append(" " + value + " ")
                else:
                    parts.append(value)
        return "".join(parts)

    value = collect(node)
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([，。；：！？、）》】])", r"\1", value)


def section_label(section):
    labels = list(descendants(section, class_name="label"))
    return text_content(labels[0]) if labels else ""


def project_title(project):
    headings = list(descendants(project, "h3"))
    return text_content(headings[0]) if headings else ""


def project_body(project):
    blocks = []
    for child in project.children:
        if isinstance(child, Element) and child.tag in {"p", "ul", "ol"}:
            if child.tag == "p":
                value = text_content(child)
                if value:
                    blocks.append(value)
            else:
                for item in descendants(child, "li"):
                    value = text_content(item)
                    if value:
                        blocks.append(value)
    return "\n\n".join(blocks)


def page_number(sheet):
    footer = list(descendants(sheet, class_name="footer-note"))
    if not footer:
        return 0
    match = re.search(r"\b(\d{2})\s*/\s*\d{2}", text_content(footer[0]))
    return int(match.group(1)) if match else 0


def main(path):
    parser = ResumeParser()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    records = []

    def add(title, body, page, section, group, keywords=None):
        body = body.strip()
        if not body:
            return
        index = len(records) + 1
        records.append({
            "id": f"resume-2026-html-{index:02d}",
            "groupId": f"resume-2026-html-{group}",
            "recordType": "resume_source",
            "sourceVersion": "2026",
            "sourceFormat": "html",
            "page": page,
            "section": section,
            "title": title,
            "body": body,
            "tags": ["简历原文", "2026", "工作与项目经历"],
            "keywords": list(dict.fromkeys(["2026 AI 产品负责人简历", title, *(keywords or [])])),
            "source": f"ref/AI产品负责人_设计版简历_v6-打印修复.html#sheet={page}",
            "visibility": "public",
        })

    sheets = list(descendants(parser.root, "section", "sheet"))
    for sheet in sheets:
        page = page_number(sheet)
        for section in descendants(sheet, "section", "section"):
            label = section_label(section)
            if label.startswith("01 /"):
                paragraphs = [text_content(item) for item in descendants(section, "p")]
                skills = [text_content(item) for item in descendants(section, class_name="chip")]
                body = "\n\n".join(item for item in paragraphs if item)
                if skills:
                    body += "\n\n" + " / ".join(skills)
                add("个人简介与能力", body, page, label, "profile", ["个人简介", "AI 产品负责人", *skills])
            elif label.startswith("02 /") or label.startswith("03 /"):
                for job in descendants(section, "article", "job"):
                    orgs = list(descendants(job, class_name="org"))
                    titles = list(descendants(job, class_name="title"))
                    dates = list(descendants(job, class_name="date"))
                    org = text_content(orgs[0]) if orgs else ""
                    role = text_content(titles[0]) if titles else ""
                    date = text_content(dates[0]) if dates else ""
                    job_prefix = " · ".join(value for value in [org, role, date] if value)
                    job_key = re.sub(r"[^\w\u4e00-\u9fff]+", "-", org or label).strip("-").lower()
                    summaries = [text_content(node) for node in descendants(job, "p", "summary")]
                    if summaries:
                        add(job_prefix or label, "\n\n".join(summaries), page, label, job_key, [org, role, date])
                    for project in descendants(job, "div", "project"):
                        title = project_title(project)
                        body = project_body(project)
                        if title and body:
                            add(title, body, page, label, job_key + "-" + title, [org, role, date, title])
            elif label.startswith("04 /") or label.startswith("05 /") or label.startswith("06 /"):
                for mini in descendants(section, "div", "mini"):
                    strong = list(descendants(mini, "strong"))
                    spans = [text_content(node) for node in descendants(mini, "span")]
                    title = text_content(strong[0]) if strong else label
                    body = "\n".join(value for value in spans if value)
                    add(title, body or title, page, label, re.sub(r"[^\w\u4e00-\u9fff]+", "-", title).strip("-").lower(), [title])

    print(json.dumps(records, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
