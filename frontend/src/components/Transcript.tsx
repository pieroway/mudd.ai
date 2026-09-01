import { forwardRef } from 'react'

interface TranscriptProps {
  lines: string[]
}

const Transcript = forwardRef<HTMLDivElement, TranscriptProps>(({ lines }, ref) => {
  return (
    <div className="transcript" data-testid="transcript">
      {lines.map((line, index) => (
        <div key={index} className="transcript-line">
          {line.split('\n').map((part, lineIndex) => (
            <div key={lineIndex}>{part}</div>
          ))}
        </div>
      ))}
      <div ref={ref} />
    </div>
  )
})

Transcript.displayName = 'Transcript'

export default Transcript
