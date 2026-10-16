import { forwardRef } from 'react'

export interface HelpEntry {
  command: string
  description: string
}

export interface HelpGroup {
  title: string
  entries: HelpEntry[]
}

export type TranscriptEntry = string | { type: 'help'; groups: HelpGroup[] }

export function isHelpGroups(value: unknown): value is HelpGroup[] {
  return Array.isArray(value) && value.length > 0 && value.every(group => {
    if (!group || typeof group !== 'object') return false
    const candidate = group as Partial<HelpGroup>
    return typeof candidate.title === 'string' && candidate.title.length > 0
      && Array.isArray(candidate.entries) && candidate.entries.length > 0
      && candidate.entries.every(entry => Boolean(entry)
        && typeof entry.command === 'string' && entry.command.length > 0
        && typeof entry.description === 'string' && entry.description.length > 0)
  })
}

interface TranscriptProps {
  lines: TranscriptEntry[]
}

const Transcript = forwardRef<HTMLDivElement, TranscriptProps>(({ lines }, ref) => {
  return (
    <div className="transcript" data-testid="transcript">
      {lines.map((line, index) => (
        <div key={index} className="transcript-line">
          {typeof line === 'string'
            ? line.split('\n').map((part, lineIndex) => (
                <div key={lineIndex}>{part || '\u00a0'}</div>
              ))
            : <section className="help-reference" aria-labelledby={`help-title-${index}`}>
                <h2 id={`help-title-${index}`}>Available Commands</h2>
                <div className="help-groups">
                  {line.groups.map((group, groupIndex) => (
                    <section className="help-group" key={group.title}>
                      <h3 id={`help-group-${index}-${groupIndex}`}>{group.title}</h3>
                      <table
                        className="help-table"
                        aria-labelledby={`help-group-${index}-${groupIndex}`}
                      >
                        <thead>
                          <tr><th scope="col">Command</th><th scope="col">Description</th></tr>
                        </thead>
                        <tbody>
                          {group.entries.map(entry => (
                            <tr key={entry.command}>
                              <th scope="row"><code>{entry.command}</code></th>
                              <td>{entry.description}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </section>
                  ))}
                </div>
              </section>}
        </div>
      ))}
      <div ref={ref} />
    </div>
  )
})

Transcript.displayName = 'Transcript'

export default Transcript
