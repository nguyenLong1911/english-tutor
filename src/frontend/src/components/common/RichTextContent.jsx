import { useMemo } from 'react'

const DEFAULT_VARIANTS = {
  article: 'space-y-4 text-sm leading-relaxed text-[var(--ink)]',
  heading1: 'font-display text-3xl font-semibold leading-tight',
  heading2: 'mt-6 text-xl font-semibold',
  heading3: 'mt-5 text-base font-semibold',
  paragraph: 'text-[var(--muted)]',
  list: 'space-y-2 pl-5 text-[var(--muted)]',
  tableWrap: 'overflow-x-auto rounded-xl border border-[var(--line)] bg-white',
  table: 'min-w-full border-collapse text-left text-xs',
  tableHead: 'bg-[var(--cream-2)]',
  tableHeaderCell: 'border-b border-[var(--line)] px-3 py-2 font-semibold',
  tableRow: 'border-t border-[var(--line)]',
  tableCell: 'min-w-[130px] px-3 py-2 align-top text-[var(--muted)]',
  details: 'rounded-xl border border-[var(--line)] bg-[var(--cream-0)] p-4',
  summary: 'cursor-pointer font-semibold text-[var(--ochre)]',
  detailsBody: 'mt-4 space-y-3',
  code: 'rounded bg-[var(--cream-2)] px-1 py-0.5 font-mono-ui text-[var(--ochre)]',
  strong: 'font-semibold text-[var(--ink)]',
  emphasis: 'italic text-[var(--ink)]',
}

export default function RichTextContent({ content, variant = {} }) {
  const classes = { ...DEFAULT_VARIANTS, ...variant }
  const blocks = useMemo(() => parseMarkdown(content), [content])

  if (!String(content || '').trim()) return null

  return (
    <article className={classes.article}>
      {blocks.map((block, index) => renderBlock(block, index, classes))}
    </article>
  )
}

export function parseMarkdown(content) {
  const source = String(content || '').replace(/^---[\s\S]*?---\s*/, '')
  const lines = source.split(/\r?\n/)
  const blocks = []
  let index = 0
  let nextOrderedStart = 1

  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) {
      index += 1
      continue
    }

    if (line.trim() === '<details>') {
      const detailLines = []
      let summary = 'Đáp án'
      index += 1
      while (index < lines.length && lines[index].trim() !== '</details>') {
        const summaryMatch = lines[index].match(/^<summary>(.*)<\/summary>$/)
        if (summaryMatch) summary = summaryMatch[1]
        else detailLines.push(lines[index])
        index += 1
      }
      blocks.push({ type: 'details', summary, blocks: parseMarkdown(detailLines.join('\n')) })
      index += 1
      continue
    }

    if (/^\|.+\|$/.test(line.trim())) {
      const tableLines = []
      while (index < lines.length && /^\|.+\|$/.test(lines[index].trim())) {
        tableLines.push(lines[index])
        index += 1
      }
      blocks.push({ type: 'table', lines: tableLines })
      continue
    }

    const heading = line.match(/^(#{1,4})\s+(.*)$/)
    if (heading) {
      blocks.push({ type: 'heading', level: heading[1].length, text: heading[2] })
      nextOrderedStart = 1
      index += 1
      continue
    }

    if (/^[-*]\s+/.test(line.trim())) {
      const items = []
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*]\s+/, ''))
        index += 1
      }
      blocks.push({ type: 'list', ordered: false, items })
      continue
    }

    if (/^\d+\.\s+/.test(line.trim())) {
      const items = []
      const firstNumber = Number(line.trim().match(/^(\d+)\.\s+/)?.[1] || 1)
      const start = firstNumber === 1 && nextOrderedStart > 1 ? nextOrderedStart : firstNumber
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ''))
        index += 1
      }
      blocks.push({ type: 'list', ordered: true, start, items })
      nextOrderedStart = start + items.length
      continue
    }

    const paragraph = [line.trim()]
    index += 1
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
      paragraph.push(lines[index].trim())
      index += 1
    }
    blocks.push({ type: 'paragraph', text: paragraph.join(' ').replace(/\s{2,}/g, ' ') })
  }

  return blocks
}

function isBlockStart(line) {
  const value = line.trim()
  return /^(#{1,4})\s+/.test(value) || /^[-*]\s+/.test(value) || /^\d+\.\s+/.test(value) || /^\|.+\|$/.test(value) || value === '<details>'
}

function renderBlock(block, index, classes) {
  if (block.type === 'heading') {
    const Tag = block.level === 1 ? 'h1' : block.level === 2 ? 'h2' : 'h3'
    const className = block.level === 1 ? classes.heading1 : block.level === 2 ? classes.heading2 : classes.heading3
    return <Tag className={className} key={index}>{renderInline(block.text, classes)}</Tag>
  }

  if (block.type === 'paragraph') {
    return <p className={classes.paragraph} key={index}>{renderInline(block.text, classes)}</p>
  }

  if (block.type === 'list') {
    const Tag = block.ordered ? 'ol' : 'ul'
    return (
      <Tag className={`${block.ordered ? 'list-decimal' : 'list-disc'} ${classes.list}`} key={index} start={block.ordered ? block.start : undefined}>
        {block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item, classes)}</li>)}
      </Tag>
    )
  }

  if (block.type === 'table') {
    const rows = block.lines
      .filter((row) => !/^\|\s*-+/.test(row))
      .map((row) => row.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim()))
    const [head = [], ...body] = rows
    return (
      <div className={classes.tableWrap} key={index}>
        <table className={classes.table}>
          <thead className={classes.tableHead}>
            <tr>{head.map((cell, cellIndex) => <th className={classes.tableHeaderCell} key={cellIndex}>{renderInline(cell, classes)}</th>)}</tr>
          </thead>
          <tbody>
            {body.map((row, rowIndex) => (
              <tr className={classes.tableRow} key={rowIndex}>
                {row.map((cell, cellIndex) => <td className={classes.tableCell} key={cellIndex}>{renderInline(cell, classes)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (block.type === 'details') {
    return (
      <details className={classes.details} key={index}>
        <summary className={classes.summary}>{block.summary}</summary>
        <div className={classes.detailsBody}>{block.blocks.map((child, childIndex) => renderBlock(child, childIndex, classes))}</div>
      </details>
    )
  }

  return null
}

function renderInline(text, classes) {
  return String(text)
    .split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*\n]+\*)/g)
    .filter(Boolean)
    .map((part, index) => {
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code className={classes.code} key={index}>{part.slice(1, -1)}</code>
      }
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong className={classes.strong} key={index}>{part.slice(2, -2)}</strong>
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return <em className={classes.emphasis} key={index}>{part.slice(1, -1)}</em>
      }
      return <span key={index}>{part}</span>
    })
}
