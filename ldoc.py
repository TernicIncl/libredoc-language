#!/usr/bin/env python3
import os
import re
import argparse

TEMPLATE_PATH = "templates/base.html"

def parse_ldoc(text, base_dir=None, vars_dict=None, platform=None):
    vars_dict = vars_dict or {}
    codeblocks = {}

    # -------------------------------
    # Handle @include (recursive)
    include_pattern = re.compile(r'@include (.+)')
    while re.search(include_pattern, text):
        match = re.search(include_pattern, text)
        if match:
            include_path = match.group(1).strip()
            full_path = os.path.join(base_dir or "", include_path)
            if os.path.exists(full_path):
                with open(full_path) as f:
                    included_content = f.read()
                text = text.replace(match.group(0), included_content)
            else:
                text = text.replace(match.group(0), f"<div class='error'>Missing include: {include_path}</div>")

    # -------------------------------
    # Extract metadata
    title_match = re.search(r'@title:\s*(.+)', text)
    title = title_match.group(1) if title_match else "Documentation"
    text = re.sub(r'@title:\s*.+', '', text)

    # -------------------------------
    # Handle variables (@var NAME=VALUE)
    for match in re.findall(r'@var (\w+)=(.+)', text):
        vars_dict[match[0]] = match[1].strip()
    text = re.sub(r'@var \w+=.+', '', text)

    for key, val in vars_dict.items():
        text = text.replace(f"@{key}", val)

    # -------------------------------
    # Handle conditionals (@if / @endif)
    if_pattern = re.compile(r'@if (\w+)=(.+?)\n(.*?)@endif', re.S)
    for cond in re.findall(if_pattern, text):
        var, value, block = cond
        if platform and var == "PLATFORM" and platform == value:
            text = text.replace(f"@if {var}={value}\n{block}@endif", block)
        else:
            text = text.replace(f"@if {var}={value}\n{block}@endif", "")

    # -------------------------------
    # Handle code blocks for reuse
    block_pattern = re.compile(r'@codeblock (\w+) (\w+)\n(.*?)@endcodeblock', re.S)
    for lang, name, code in re.findall(block_pattern, text):
        codeblocks[name] = f'<pre><code class="{lang}">{code.strip()}</code></pre>'
    text = re.sub(block_pattern, '', text)

    # Handle @usecode
    for name in codeblocks:
        text = text.replace(f"@usecode {name}", codeblocks[name])

    # -------------------------------
    # Table of Contents
    toc_entries = []
    for h_match in re.finditer(r'^(#{1,3}) (.+)$', text, flags=re.M):
        level = len(h_match.group(1))
        heading_text = h_match.group(2)
        anchor = heading_text.lower().replace(" ", "-")
        toc_entries.append((level, heading_text, anchor))

    toc_html = "<nav class='toc'><h3>Table of Contents</h3><ul>"
    for level, heading_text, anchor in toc_entries:
        toc_html += f"<li class='level-{level}'><a href='#{anchor}'>{heading_text}</a></li>"
    toc_html += "</ul></nav>"
    text = text.replace("@toc", toc_html)

    # -------------------------------
    # Syntax replacements

    # Headings with anchors
    text = re.sub(r'^### (.+)$', lambda m: f'<h3 id="{m.group(1).lower().replace(" ","-")}">{m.group(1)}</h3>', text, flags=re.M)
    text = re.sub(r'^## (.+)$', lambda m: f'<h2 id="{m.group(1).lower().replace(" ","-")}">{m.group(1)}</h2>', text, flags=re.M)
    text = re.sub(r'^# (.+)$', lambda m: f'<h1 id="{m.group(1).lower().replace(" ","-")}">{m.group(1)}</h1>', text, flags=re.M)

    # --- @command: handling ---
    def command_replacer(match):
        cmd = match.group(1)
        cmd = cmd.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<pre><code class="command">{cmd}</code></pre>'

    text = re.sub(r'^@command: (.+)$', command_replacer, text, flags=re.M)

    # Code blocks
    text = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code class="\1">\2</code></pre>', text, flags=re.S)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Bold & italic
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

    # Horizontal rules
    text = re.sub(r'^\-\-\-$', r'<hr>', text, flags=re.M)

    # -------------------------------
    # Task lists and normal lists
    def tasklist_replacer(match):
        checked = match.group(1).lower() == 'x'
        item = match.group(2)
        checkbox = '<input type="checkbox" disabled{}>'.format(' checked' if checked else '')
        return f'<li class="task-item">{checkbox} {item}</li>'

    # Task list items first
    text = re.sub(r'^\- \[( |x|X)\] (.+)$', tasklist_replacer, text, flags=re.M)

    # Normal list items (that are not task lists)
    text = re.sub(r'^\- (.+)$', r'<li>\1</li>', text, flags=re.M)

    # Wrap consecutive <li> blocks with <ul>
    text = re.sub(r'(<li>.*?</li>)', r'<ul>\1</ul>', text, flags=re.S)

    # Links
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)

    # -------------------------------
    # @image and @video
    text = re.sub(r'@image: (.+?) "(.*?)"', r'<img src="\1" alt="\2">', text)
    text = re.sub(r'@video: (.+)', r'<iframe src="\1" frameborder="0" allowfullscreen></iframe>', text)

    # -------------------------------
    # Special blocks: note, warning, info, tip, todo
    text = re.sub(r'@note: (.+)', r'<div class="note">\1</div>', text)
    text = re.sub(r'@warning: (.+)', r'<div class="warning">\1</div>', text)
    text = re.sub(r'@info: (.+)', r'<div class="info">\1</div>', text)
    text = re.sub(r'@tip: (.+)', r'<div class="tip">\1</div>', text)
    text = re.sub(r'@todo: (.+)', r'<div class="todo">TODO: \1</div>', text)

    # -------------------------------
    # Alert blocks: @alert TYPE ... @endalert
    def alert_replacer(match):
        alert_type = match.group(1).strip()
        content = match.group(2).strip()
        allowed = {"info", "warning", "error", "success"}
        css_class = alert_type if alert_type in allowed else "info"
        return f'<div class="alert {css_class}">{content}</div>'

    text = re.sub(r'@alert (\w+)\n(.*?)@endalert', alert_replacer, text, flags=re.S)

    # -------------------------------
    # @badge
    text = re.sub(r'@badge: (\w+)\|(\w+)\|(\w+)', r'<span class="badge \3">\1: \2</span>', text)

    # -------------------------------
    # Tables (@table ... @endtable)
    def table_replacer(match):
        rows = match.group(1).strip().splitlines()
        html = "<table>"
        for i, row in enumerate(rows):
            cols = [c.strip() for c in row.split('|')]
            if i == 0:
                html += "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"
            else:
                html += "<tr>" + "".join(f"<td>{c}</td>" for c in cols) + "</tr>"
        html += "</table>"
        return html
    text = re.sub(r'@table:\s*(.*?)@endtable', table_replacer, text, flags=re.S)

    # -------------------------------
    # Paragraphs (convert double newlines to <p>)
    text = re.sub(r'\n{2,}', '</p><p>', text)
    text = f"<p>{text}</p>"

    return text, title


def build_html(content, title="Documentation"):
    with open(TEMPLATE_PATH) as f:
        template = f.read()
    return template.replace("{title}", title).replace("{content}", content)

def build_file(input_path, output_path):
    base_dir = os.path.dirname(input_path)
    with open(input_path) as f:
        text = f.read()
    parsed, title = parse_ldoc(text, base_dir)
    html = build_html(parsed, title)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"✅ Built {output_path}")

def build_directory(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    for file in os.listdir(input_dir):
        if file.endswith(".ldoc"):
            in_path = os.path.join(input_dir, file)
            out_path = os.path.join(output_dir, file.replace(".ldoc", ".html"))
            build_file(in_path, out_path)

def main():
    parser = argparse.ArgumentParser(description="LDOC - LibreGrad Documentation Compiler")
    parser.add_argument("command", choices=["build"], help="Build documentation")
    parser.add_argument("input", help="Input file or directory")
    parser.add_argument("-o", "--output", default="build", help="Output directory")
    parser.add_argument("--platform", help="Platform for conditional blocks")
    args = parser.parse_args()

    if args.command == "build":
        if os.path.isdir(args.input):
            build_directory(args.input, args.output)
        else:
            if not os.path.exists(args.output):
                os.makedirs(args.output)
            output_file = os.path.join(args.output, os.path.basename(args.input).replace(".ldoc", ".html"))
            build_file(args.input, output_file)

if __name__ == "__main__":
    main()
