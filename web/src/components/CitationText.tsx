import { Fragment, type ReactNode } from "react";
import "./CitationText.css";

const CITATION_RE = /\[q(\d+)\]/g;

export default function CitationText({
  body,
  queryIds,
  onCite,
}: {
  body: string;
  queryIds: string[];
  onCite: (queryId: string) => void;
}) {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  CITATION_RE.lastIndex = 0;

  while ((match = CITATION_RE.exec(body)) !== null) {
    if (match.index > lastIndex) {
      parts.push(
        <Fragment key={`t-${lastIndex}`}>{body.slice(lastIndex, match.index)}</Fragment>,
      );
    }
    const n = Number(match[1]);
    const queryId = queryIds[n - 1];
    parts.push(
      <button
        key={`c-${match.index}`}
        type="button"
        className={`citation-chip mono${queryId ? "" : " citation-chip-dead"}`}
        disabled={!queryId}
        onClick={() => queryId && onCite(queryId)}
        title={queryId ? `view evidence for ${queryId}` : "evidence unavailable"}
      >
        q{n}
      </button>,
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < body.length) {
    parts.push(<Fragment key={`t-end`}>{body.slice(lastIndex)}</Fragment>);
  }

  return <p className="citation-body">{parts}</p>;
}
