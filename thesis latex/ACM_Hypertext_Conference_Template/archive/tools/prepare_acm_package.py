import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCX_PATH = ROOT / "my thesis" / "my thesis document.docx"

DRAFT_TEX_PATH = ROOT / "draft-from-docx.tex"
MEDIA_DIR = ROOT / "docx-media"
IMAGES_DIR = ROOT / "images"

CONTENT_TEX_PATH = ROOT / "paper-content.tex"
MAIN_TEX_PATH = ROOT / "main.tex"
REFERENCES_BIB_PATH = ROOT / "references.bib"

ZIP_OUT_PATH = ROOT / "Lim_JoseMarie_ACM_source.zip"


FIGURE_MAP: dict[str, dict[str, str]] = {
    "1": {
        "filename": "ipo.png",
        "label": "fig:ipo",
        "caption": "Input--Process--Output (IPO) conceptual framework.",
    },
    "4.0": {
        "filename": "sdlc.png",
        "label": "fig:sdlc",
        "caption": "Iterative Software Development Life Cycle (SDLC) used in the project.",
    },
    "4.1": {
        "filename": "context-diagram.png",
        "label": "fig:context-diagram",
        "caption": "Context diagram of the PH Eye news sentiment analysis system.",
    },
    "4.2": {
        "filename": "data-flow-diagram.png",
        "label": "fig:data-flow-diagram",
        "caption": "Data flow diagram of the PH Eye news sentiment analysis system.",
    },
    "4.3": {
        "filename": "system-flowchart.png",
        "label": "fig:system-flowchart",
        "caption": "System flowchart of the PH Eye news sentiment analysis system.",
    },
    "4.4": {
        "filename": "program-flowchart.png",
        "label": "fig:program-flowchart",
        "caption": "Program flowchart of the PH Eye news sentiment analysis system.",
    },
    "4.5": {
        "filename": "ui-homepage.png",
        "label": "fig:ui-homepage",
        "caption": "Homepage of collected articles in the dashboard.",
    },
    "4.6": {
        "filename": "weekly-sentiment-trends.png",
        "label": "fig:weekly-sentiment-trends",
        "caption": "Weekly sentiment trends across sources.",
    },
    "4.6.1": {
        "filename": "inquirer-sentiment-distribution.png",
        "label": "fig:inquirer-sentiment-distribution",
        "caption": "Sentiment distribution of Inquirer articles.",
    },
    "4.6.2": {
        "filename": "rappler-sentiment-distribution.png",
        "label": "fig:rappler-sentiment-distribution",
        "caption": "Sentiment distribution of Rappler articles.",
    },
    "4.7": {
        "filename": "source-correlation-heatmap.png",
        "label": "fig:source-correlation-heatmap",
        "caption": "Heatmap of cross-source sentiment correlation.",
    },
    "4.8": {
        "filename": "gma-timeline.png",
        "label": "fig:gma-timeline",
        "caption": "Sentiment data and timeline (GMA).",
    },
    "4.9": {
        "filename": "manila-times-timeline.png",
        "label": "fig:manila-times-timeline",
        "caption": "Sentiment data and timeline (Manila Times).",
    },
    "4.10": {
        "filename": "entity-rank-list.png",
        "label": "fig:entity-rank-list",
        "caption": "Entity rank list and associated sentiment summary.",
    },
    "4.11": {
        "filename": "search-crime.png",
        "label": "fig:search-crime",
        "caption": "Search results example for the keyword ``crime''.",
    },
    "4.12": {
        "filename": "quick-view-modal.png",
        "label": "fig:quick-view-modal",
        "caption": "Quick view modal for inspecting an article.",
    },
    "4.13": {
        "filename": "erd.png",
        "label": "fig:erd",
        "caption": "Entity relationship diagram (ERD) of the system database.",
    },
}


def run_pandoc() -> None:
    MEDIA_DIR.mkdir(exist_ok=True)
    # Use -o to ensure UTF-8 output, avoiding PowerShell redirection UTF-16.
    subprocess.run(
        [
            "pandoc",
            str(DOCX_PATH),
            "-t",
            "latex",
            "--wrap=none",
            f"--extract-media={MEDIA_DIR.name}",
            "-o",
            str(DRAFT_TEX_PATH),
        ],
        cwd=str(ROOT),
        check=True,
    )


def cite_key(n: int) -> str:
    return f"ref{n:02d}"


def replace_citations(text: str) -> str:
    # Pandoc emits citations like "{[}3, 4{]}".
    def repl(match: re.Match) -> str:
        raw = match.group(1)
        nums = [int(x) for x in re.findall(r"\d+", raw)]
        if not nums:
            return match.group(0)
        keys = ",".join(cite_key(n) for n in nums)
        return rf"\cite{{{keys}}}"

    # Typical cases: "{[}21{]}" or "{[}3, 4, 11{]}". Occasionally pandoc leaves stray TeX
    # inside the brackets; we still extract the digits.
    text = re.sub(r"\{\[\}([0-9,\s]+)\{\]\}", repl, text)
    text = re.sub(r"\{\[\}([^\}]+)\{\]\}", repl, text)
    return text


def longtable_to_itemize(block: str) -> str:
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.endswith(r"\\"):
            continue
        if " & " not in line:
            continue
        parts = [p.strip() for p in line[:-2].split(" & ")]
        if len(parts) < 2:
            continue
        # Keep up to 4 columns; extra columns get folded.
        while len(parts) < 4:
            parts.append("")
        method, use_cases, advantages, limitations = parts[:4]
        item = rf"\item {method}: {use_cases} "
        if advantages:
            item += rf"(Advantages: {advantages}.) "
        if limitations:
            item += rf"(Limitations: {limitations}.)"
        rows.append(item.strip())

    if not rows:
        return ""
    return "\\begin{itemize}\n" + "\n".join(rows) + "\n\\end{itemize}\n"


def cleanup_structure(text: str) -> str:
    # Remove quote environments used for chapter headings (we convert headings separately).
    text = re.sub(r"\\begin\{quote\}\s*", "", text)
    text = re.sub(r"\s*\\end\{quote\}\s*", "\n\n", text)

    # Convert bolded heading wrappers produced by pandoc.
    text = re.sub(
        r"\\section\{\\texorpdfstring\{\\textbf\{([^}]+)\}\}\{[^}]+\}\}\\label\{([^}]+)\}",
        r"\\section{\1}\n\\label{\2}",
        text,
    )
    text = re.sub(
        r"\\subsection\{\\texorpdfstring\{\\textbf\{([^}]+)\}\}\{[^}]+\}\}\\label\{([^}]+)\}",
        r"\\subsection{\1}\n\\label{\2}",
        text,
    )
    text = re.sub(
        r"\\subsubsection\{\\texorpdfstring\{\\textbf\{([^}]+)\}\}\{[^}]+\}\}\\label\{([^}]+)\}",
        r"\\subsection{\1}\n\\label{\2}",
        text,
    )
    text = re.sub(
        r"\\paragraph\{\\texorpdfstring\{\\textbf\{([^}]+)\}\}\{[^}]+\}\}\\label\{([^}]+)\}",
        r"\\subsection{\1}\n\\label{\2}",
        text,
    )

    # Fix accidental section/subsection headings containing full sentences (common pandoc artifact).
    def flatten_long_heading(match: re.Match) -> str:
        cmd = match.group(1)
        heading = match.group(2).strip()
        label = match.group(3)
        if len(heading) < 120 and not re.search(r"\\cite\{|ref\d", heading):
            return match.group(0)
        # Turn into paragraph text.
        return f"{heading}\n\n"

    text = re.sub(
        r"\\(section|subsection|subsubsection)\{([^}]+)\}\\label\{([^}]+)\}",
        flatten_long_heading,
        text,
    )

    # Normalize "METHODOLOGY" title and some bold section headers.
    text = re.sub(r"^\\textbf\{METHODOLOGY\}\s*$", r"\\section{Methodology}", text, flags=re.M)
    text = re.sub(
        r"^\\textbf\{Statement of the Problem\}\s*$",
        r"\\subsection{Statement of the Problem}",
        text,
        flags=re.M,
    )
    text = re.sub(
        r"^\\textbf\{Objectives of the Study\}\s*$",
        r"\\subsection{Objectives of the Study}",
        text,
        flags=re.M,
    )
    text = re.sub(
        r"^\\textbf\{Scope and Delimitations\}\s*$",
        r"\\subsection{Scope and Delimitations}",
        text,
        flags=re.M,
    )
    text = re.sub(
        r"^\\textbf\{Functional Requirements\}\s*$",
        r"\\subsection{Functional Requirements}",
        text,
        flags=re.M,
    )
    text = re.sub(
        r"^\\textbf\{Non-Functional Requirements\}\s*$",
        r"\\subsection{Non-Functional Requirements}",
        text,
        flags=re.M,
    )

    # Convert longtable blocks to itemize (longtable is problematic in two-column).
    def lt_repl(match: re.Match) -> str:
        block = match.group(0)
        return longtable_to_itemize(block)

    text = re.sub(r"\{\s*\\def\\LTcaptype\{none\}.*?\\end\{longtable\}\s*\}\s*", lt_repl, text, flags=re.S)
    text = re.sub(r"\\begin\{longtable\}.*?\\end\{longtable\}", lt_repl, text, flags=re.S)

    # Convert bold label paragraphs into LaTeX paragraphs where appropriate.
    text = re.sub(
        r"^\\textbf\{([^}]+)\}\.\s*$",
        r"\\paragraph{\1.}",
        text,
        flags=re.M,
    )

    # Replace some Unicode punctuation with LaTeX-safe ASCII equivalents.
    text = text.replace("−", "-")
    text = text.replace("‑", "-")

    # Fix occasional stray braces after citation conversion.
    text = re.sub(r"(\\cite\{[^}]+\})\}+", r"\1", text)

    return text


def convert_objectives_to_list(text: str) -> str:
    # Objectives are frequently formatted as a heading plus a "Specifically..." line,
    # followed by multiple single-sentence items. Convert that run into an itemize list.
    text = text.replace(r"\textbf{Objectives of the Study}", r"\subsection{Objectives of the Study}")

    start = text.find(r"\subsection{Objectives of the Study}")
    if start == -1:
        return text

    end = text.find(r"\subsection{Conceptual Framework of the Study}", start)
    if end == -1:
        return text

    pre = text[:start]
    mid = text[start:end]
    post = text[end:]

    # Remove labels and the "Specifically..." subheading.
    mid = re.sub(r"\\label\{[^}]+\}\s*", "", mid)
    mid = mid.replace(r"\subsection{Specifically, it aims to:}", "")

    # Remove any section commands inside the objective block, keeping just the text.
    mid = re.sub(r"\\subsubsection\{([^}]+)\}", r"\1", mid)
    mid = re.sub(r"\\subsection\{([^}]+)\}", r"\1", mid)

    chunks = [c.strip() for c in re.split(r"\n\s*\n", mid) if c.strip()]
    items: list[str] = []
    for c in chunks:
        if c.startswith("Objectives of the Study"):
            continue
        if c.startswith("This study aims"):
            continue
        if len(c) < 25:
            continue
        items.append(c.splitlines()[0].strip())

    if not items:
        return text

    objectives_block = "\n".join(
        [
            r"\subsection{Objectives of the Study}",
            "This study aims to design and develop an automated system that collects, processes, and analyzes sentiment in Philippine online news using Natural Language Processing (NLP) techniques. Specifically, it aims to:",
            r"\begin{itemize}",
            *[rf"\item {it}" for it in items],
            r"\end{itemize}",
            "",
        ]
    )

    return pre + objectives_block + post


def extract_bibliography_entries(draft: str) -> tuple[str, list[tuple[int, str]]]:
    bib_marker = r"\textbf{Bibliography}"
    idx = draft.find(bib_marker)
    if idx == -1:
        return draft, []
    body = draft[:idx].rstrip() + "\n"
    bib = draft[idx:]

    entries: list[tuple[int, str]] = []
    # Pattern: {[}n{]} then quote block.
    pattern = re.compile(
        r"\{\[\}(\d+)\{\]\}\s*\\begin\{quote\}(.*?)\\end\{quote\}",
        flags=re.S,
    )
    for m in pattern.finditer(bib):
        n = int(m.group(1))
        txt = m.group(2).strip().replace("\n", " ")
        txt = re.sub(r"\s+", " ", txt).strip()
        entries.append((n, txt))
    return body, entries


def bib_escape(s: str) -> str:
    # Keep BibTeX stable: escape bare braces and quotes minimally.
    s = s.replace("\n", " ").strip()
    s = re.sub(r"\s+", " ", s)
    # Classic BibTeX is not reliably UTF-8; convert common non-ASCII characters to LaTeX.
    unicode_map = {
        "·": "-",
        "É": r"{\'E}",
        "á": r"{\'a}",
        "ä": r"{\"a}",
        "é": r"{\'e}",
        "ë": r"{\"e}",
        "í": r"{\'\i}",
        "ô": r"{\^o}",
        "ö": r"{\"o}",
        "ü": r"{\"u}",
        "č": r"{\v{c}}",
        "İ": r"{\.I}",
    }
    s = "".join(unicode_map.get(ch, ch) for ch in s)
    return s


def strip_latex_markup(s: str) -> str:
    # Remove simple LaTeX markup emitted in the DOCX bibliography conversion.
    s = s.replace("Â·", "·")
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = s.replace(r"\textbar{}", "|")
    s = re.sub(r"\\textbar\s*\{\s*\}", "|", s)
    return s


def parse_author_list(author_part: str) -> str:
    author_part = author_part.strip().rstrip(".").strip()
    if not author_part:
        return ""
    # Common formatting: "A, B, and C"
    author_part = author_part.replace(", and ", ", ")
    parts = [p.strip() for p in author_part.split(",") if p.strip()]
    authors: list[str] = []
    for p in parts:
        # Handle any remaining "and".
        if " and " in p:
            authors.extend([x.strip() for x in p.split(" and ") if x.strip()])
        else:
            authors.append(p)
    authors = [a.rstrip(",").strip() for a in authors if a.strip()]
    # Corporate author heuristic: preserve as a single unit with braces.
    out: list[str] = []
    for a in authors:
        if re.search(r"\b(Foundation|Group|Staff|Contributors|Inc|Ltd|Monitor|University)\b", a) or re.search(r"\d", a):
            out.append("{" + a + "}")
        else:
            out.append(a)
    return " and ".join(out)


def entry_to_bib(n: int, raw: str) -> str:
    # Extract URLs and DOIs from \url{...} or plain.
    urls = re.findall(r"\\url\{([^}]+)\}", raw)
    text = re.sub(r"\\url\{[^}]+\}", "", raw)
    text = strip_latex_markup(text)

    url = urls[0] if urls else ""
    doi = ""
    if url.startswith("https://doi.org/") or url.startswith("http://doi.org/"):
        doi = url.split("doi.org/")[-1]

    text = re.sub(r"\s+", " ", text).strip()

    # Handle "Retrieved ..." web references (no explicit author/year).
    m_retr = re.search(r"^(.*?)\.\s*Retrieved\s+(.+?)\s+from\s*$", text)
    if m_retr and url:
        title = m_retr.group(1).strip()
        note = "Retrieved " + m_retr.group(2).strip()
        year_match = re.search(r"\b(19|20)\d{2}\b", note)
        year = year_match.group(0) if year_match else ""
        fields = {
            "title": title,
            "year": year,
            "note": note,
            "url": url,
        }
        if doi:
            fields["doi"] = doi
        fields = {k: v for k, v in fields.items() if v}
        bib = [f"@misc{{{cite_key(n)},"]
        for k, v in fields.items():
            bib.append(f"  {k} = {{{bib_escape(v)}}},")
        bib.append("}\n")
        return "\n".join(bib)

    # Handle entries that start with a year (e.g., "2025. Digital 2025: ...").
    m_year_lead = re.match(r"^((19|20)\d{2})\.\s*(.*)$", text)
    if m_year_lead:
        year = m_year_lead.group(1)
        rest = m_year_lead.group(3).strip()
        # title is first sentence
        parts = [p.strip() for p in rest.split(".") if p.strip()]
        title = parts[0] if parts else rest
        how = ". ".join(parts[1:]).strip() if len(parts) > 1 else ""
        fields = {
            "title": title,
            "year": year,
            "howpublished": how,
            "url": url,
        }
        if doi:
            fields["doi"] = doi
        fields = {k: v for k, v in fields.items() if v}
        bib = [f"@misc{{{cite_key(n)},"]
        for k, v in fields.items():
            bib.append(f"  {k} = {{{bib_escape(v)}}},")
        bib.append("}\n")
        return "\n".join(bib)

    # Default: assume "Author(s). YEAR. Title. Rest..."
    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    year = year_match.group(0) if year_match else ""
    author = ""
    title = ""
    how = ""
    if year:
        pre, post = text.split(year, 1)
        author = parse_author_list(pre.strip().rstrip("."))
        post = post.strip().lstrip(".").strip()
        parts = [p.strip() for p in post.split(".") if p.strip()]
        if parts:
            title = parts[0]
            how = ". ".join(parts[1:]).strip()
    else:
        title = text.strip().rstrip(".")

    if not title:
        title = f"Reference {n}"

    fields = {
        "title": title,
        "year": year,
        "howpublished": how,
        "url": url,
        "doi": doi,
    }
    if author:
        fields["author"] = author
    # Remove empty fields.
    fields = {k: v for k, v in fields.items() if v}

    bib = [f"@misc{{{cite_key(n)},"]
    for k, v in fields.items():
        bib.append(f"  {k} = {{{bib_escape(v)}}},")
    bib.append("}\n")
    return "\n".join(bib)


def write_references_bib(entries: list[tuple[int, str]]) -> None:
    # Build up to max entry, then append missing 37-40 referenced in text.
    entries_sorted = sorted(entries, key=lambda x: x[0])
    bib_parts = []
    for n, txt in entries_sorted:
        bib_parts.append(entry_to_bib(n, txt))

    # Add missing references referenced in-text but absent from the DOCX bibliography.
    extra = {
        37: (
            "Python Software Foundation. Python 3 Documentation. Retrieved March 14, 2026 from "
            "https://docs.python.org/3/"
        ),
        38: "OpenJS Foundation. Node.js Documentation. Retrieved March 14, 2026 from https://nodejs.org/en/docs",
        39: "Leonard Richardson. Beautiful Soup Documentation. Retrieved March 14, 2026 from https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
        40: "npm, Inc. npm Documentation. Retrieved March 14, 2026 from https://docs.npmjs.com/",
        41: "Kenneth Reitz. Requests: HTTP for Humans Documentation. Retrieved March 14, 2026 from https://docs.python-requests.org/",
    }
    for n, txt in extra.items():
        if any(en == n for en, _ in entries_sorted):
            continue
        # Convert to a bib entry using the same heuristics.
        bib_parts.append(entry_to_bib(n, txt))

    REFERENCES_BIB_PATH.write_text("\n".join(bib_parts).strip() + "\n", encoding="utf-8")


def stage_images_from_media(draft: str) -> dict[str, str]:
    IMAGES_DIR.mkdir(exist_ok=True)
    # Find includegraphics occurrences and map them to known figures by the nearest preceding Figure heading.
    lines = draft.splitlines()
    media_to_target: dict[str, str] = {}

    last_fig_num: str | None = None
    fig_heading_re = re.compile(r"\\textbf\{Figure\s+([0-9]+(?:\.[0-9]+)*)")
    for i, line in enumerate(lines):
        # IMPORTANT: some DOCX captions put "\textbf{Figure 4.0}" on the same line
        # *after* the \includegraphics for a different figure. So for mapping, always
        # use the most recent caption *from previous lines* and ignore any caption-like
        # tokens on the same line as \includegraphics.
        if "\\includegraphics" in line:
            img_m = re.search(r"\{([^}]+)\}", line)
            if not img_m:
                continue
            src = img_m.group(1).strip()
            if not last_fig_num or last_fig_num not in FIGURE_MAP:
                continue
            dst_name = FIGURE_MAP[last_fig_num]["filename"]
            media_to_target[src] = str(IMAGES_DIR / dst_name)
            continue

        m = fig_heading_re.search(line)
        if m:
            last_fig_num = m.group(1)

    # Figure 4.13 is a section heading, not a \textbf line; handle it specially.
    if "4.13" in FIGURE_MAP:
        for line in lines:
            if "\\label{figure-4.13" in line:
                last_fig_num = "4.13"
                continue
            if last_fig_num == "4.13" and "\\includegraphics" in line:
                img_m = re.search(r"\{([^}]+)\}", line)
                if img_m:
                    src = img_m.group(1).strip()
                    dst_name = FIGURE_MAP["4.13"]["filename"]
                    media_to_target[src] = str(IMAGES_DIR / dst_name)
                break

    # Copy files.
    for src_rel, dst in media_to_target.items():
        src_path = (ROOT / src_rel).resolve()
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.exists():
            shutil.copyfile(src_path, dst_path)

    return {k: Path(v).name for k, v in media_to_target.items()}


def build_figure_blocks(image_basename_by_src: dict[str, str]) -> dict[str, str]:
    # Build figure environments keyed by figure number.
    blocks: dict[str, str] = {}
    for fig_num, meta in FIGURE_MAP.items():
        filename = meta["filename"]
        label = meta["label"]
        caption = meta["caption"]
        blocks[fig_num] = "\n".join(
            [
                r"\begin{figure*}[t]",
                r"  \centering",
                rf"  \includegraphics[width=\textwidth]{{{filename}}}",
                rf"  \caption{{{caption}}}",
                rf"  \label{{{label}}}",
                r"\end{figure*}",
                "",
            ]
        )
    return blocks


def integrate_figures(text: str) -> str:
    # Replace inline Figure headings + includegraphics with proper figure environments.
    figure_blocks = build_figure_blocks({})

    # Replace the main heading lines and nearby includegraphics lines.
    def replace_simple(fig_num: str, pattern_caption: str) -> None:
        nonlocal text
        block = figure_blocks[fig_num]
        # Pattern: \textbf{Figure X ...}\s*\n\s*\includegraphics...
        text = re.sub(
            rf"\\textbf\{{Figure {re.escape(fig_num)}(?![0-9\.])[^\}}]*\}}\s*\\includegraphics\[.*?\]\{{[^\}}]+\}}\s*",
            lambda _m, b=block: b,
            text,
            flags=re.S,
        )

    for fig_num in FIGURE_MAP.keys():
        replace_simple(fig_num, "")

    # Handle Figure 4.13 where pandoc may represent it as a section heading.
    if "4.13" in FIGURE_MAP:
        block = figure_blocks["4.13"]
        text = re.sub(
            r"^\\section\{[^\n]*Figure 4\.13[^\n]*\}\s*\\label\{[^}]+\}\s*\n\s*\\includegraphics\[.*?\]\{[^\}]+\}\s*",
            lambda _m, b=block: b,
            text,
            flags=re.M,
        )

    # Special case: some includegraphics are followed by text on the same line (Figures 4.1–4.3, 4.2 etc).
    for fig_num in ["4.1", "4.2", "4.3"]:
        label = FIGURE_MAP[fig_num]["label"]
        text = re.sub(
            rf"\\includegraphics\[.*?\]\{{[^\}}]+\}}\s*\\textbf\{{Figure {re.escape(fig_num)}\}}",
            rf"Figure~\\ref{{{label}}}",
            text,
        )

    # Replace remaining bold figure references like \textbf{Figure 4.6} with Figure~\ref{...}
    for fig_num, meta in FIGURE_MAP.items():
        label = meta["label"]
        text = text.replace(rf"\textbf{{Figure {fig_num}}}", rf"Figure~\ref{{{label}}}")
        text = text.replace(rf"\textbf{{Figure {fig_num}.}}", rf"Figure~\ref{{{label}}}")
        text = re.sub(rf"\\textbf\{{Figure {re.escape(fig_num)}\.\}}", rf"Figure~\\ref{{{label}}}", text)
        text = re.sub(rf"\\textbf\{{Figure {re.escape(fig_num)}\}}", rf"Figure~\\ref{{{label}}}", text)

    # Replace lowercased "see figure 4.8" patterns.
    for fig_num, meta in FIGURE_MAP.items():
        label = meta["label"]
        text = re.sub(
            rf"(?i)see figure {re.escape(fig_num)}",
            rf"see Figure~\\ref{{{label}}}",
            text,
        )
        text = re.sub(
            rf"(?i)figure {re.escape(fig_num)}",
            rf"Figure~\\ref{{{label}}}",
            text,
        )

    # Common combined reference pattern from the DOCX.
    if "4.6.1" in FIGURE_MAP and "4.6.2" in FIGURE_MAP:
        text = re.sub(
            r"\\textbf\{Figures 4\.6\.1 and 4\.6\.2\}",
            rf"Figures~\\ref{{{FIGURE_MAP['4.6.1']['label']}}} and~\\ref{{{FIGURE_MAP['4.6.2']['label']}}}",
            text,
        )

    return text


def build_content_tex(body: str) -> str:
    # Add top-level sections explicitly.
    # Insert Introduction at the start.
    body = body.lstrip()
    if not body.startswith(r"\section{Introduction}"):
        body = r"\section{Introduction}" + "\n\n" + body

    # Replace chapter markers with section headings.
    body = body.replace(r"\textbf{CHAPTER II}", r"\section{Review of Related Literature}")
    body = body.replace(r"\textbf{Review of Related Literature}", "")

    body = body.replace(r"\textbf{CHAPTER III}", r"\section{Project Technicality}")
    body = body.replace(r"\section{Technicality of the Project}", r"\section{Project Technicality}")

    body = body.replace(r"\textbf{CHAPTER IV}", r"\section{Methodology}")

    # Convert any remaining standalone bold "Introduction" right after section to subsection.
    body = re.sub(r"^\\textbf\{Introduction\}\s*$", r"\\subsection{Introduction}", body, flags=re.M)

    # Merge Conclusions + Recommendations into a single section.
    body = re.sub(r"\\subsection\{Conclusions\}", r"\\section{Conclusion and Future Work}", body)
    body = re.sub(r"\\subsection\{Recommendations\}", r"\\subsection{Future Work Recommendations}", body)

    return body.strip() + "\n"


def update_main_tex() -> None:
    # Minimal, school-friendly topmatter. Keep sigconf.
    new_main = r"""%%
%% Capstone paper packaged using ACM 'acmart' (HT template)
\documentclass[sigconf]{acmart}

% School submission (not ACM): hide ACM reference format & rights blocks.
\setcopyright{none}
\settopmatter{printacmref=false,printccs=false,printfolios=true}
\renewcommand\footnotetextcopyrightpermission[1]{}
\pagestyle{plain}

% Location of your graphics files for figures
\graphicspath{{./images/}}

\begin{document}

\title{Sentiment Analysis of the Philippine News Using Natural Language Processing}

\author{Jose Marie G.\ Lim}
\affiliation{%
  \institution{Guimaras State University}
  \department{College of Science and Technology}
  \city{Jordan}
  \country{Philippines}
}

\begin{abstract}
This paper presents PH Eye, an automated media sentiment monitoring system for Philippine online news. The system continuously collects articles from major news outlets, normalizes and preprocesses text, and applies Natural Language Processing techniques to produce sentiment and entity-level summaries. Sentiment polarity is estimated using the VADER rule-based model, while named entities are extracted using spaCy. The processed outputs are stored in a relational database and presented through an interactive dashboard that supports trend exploration, cross-source comparison, and query-based inspection.
\end{abstract}

\keywords{sentiment analysis, natural language processing, Philippine news, web scraping, VADER, named entity recognition, analytics dashboard}

\maketitle

\input{paper-content.tex}

\begin{acks}
The author thanks Dr.\ Lea P.\ Ymalay for guidance and supervision during this capstone project.
\end{acks}

\bibliographystyle{ACM-Reference-Format}
\bibliography{references.bib}

\end{document}
"""
    MAIN_TEX_PATH.write_text(new_main, encoding="utf-8")


def create_zip() -> None:
    # Create a capsule zip suitable for Overleaf upload.
    if ZIP_OUT_PATH.exists():
        ZIP_OUT_PATH.unlink()
    import zipfile

    include_files = [
        "main.tex",
        "paper-content.tex",
        "references.bib",
        "acmart.cls",
        "ACM-Reference-Format.bst",
        "acmnumeric.bbx",
        "acmnumeric.cbx",
    ]

    with zipfile.ZipFile(ZIP_OUT_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for rel in include_files:
            p = ROOT / rel
            if p.exists():
                z.write(p, arcname=rel)
        if IMAGES_DIR.exists():
            for p in IMAGES_DIR.glob("*"):
                if p.is_file():
                    z.write(p, arcname=str(Path("images") / p.name))


def main() -> None:
    if not DOCX_PATH.exists():
        raise SystemExit(f"Missing DOCX: {DOCX_PATH}")

    run_pandoc()
    draft = DRAFT_TEX_PATH.read_text(encoding="utf-8")

    # Split bibliography away from body and convert to BibTeX.
    draft_body, bib_entries = extract_bibliography_entries(draft)
    write_references_bib(bib_entries)

    # Stage images and keep only the staged names in figure blocks.
    stage_images_from_media(draft)

    # Content selection: start at the line that introduces "Background of the Study"
    # (avoid slicing mid-line which can leave broken TeX).
    lines = draft_body.splitlines(keepends=True)
    start_line = 0
    for i, line in enumerate(lines):
        if "Background of the Study" in line:
            start_line = i
            break
    body = "".join(lines[start_line:])

    body = replace_citations(body)
    body = cleanup_structure(body)
    body = convert_objectives_to_list(body)
    body = integrate_figures(body)
    body = build_content_tex(body)

    CONTENT_TEX_PATH.write_text(body, encoding="utf-8")
    update_main_tex()
    create_zip()


if __name__ == "__main__":
    main()
