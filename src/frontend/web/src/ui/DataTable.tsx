import type { KeyboardEvent, ReactNode } from 'react';
import { ApiError } from '../api/client';
import { Empty, ErrorState, Skeleton } from './primitives';

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
  width?: number | string;
}

/** Compact table with sticky header; rows are keyboard-activatable when `onRowClick` is set. */
export function DataTable<T>({ rows, columns, rowKey, onRowClick, selectedKey, loading, error, onRetry, empty, caption, rowClass }: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (r: T) => string;
  onRowClick?: (r: T) => void;
  selectedKey?: string | null;
  loading?: boolean;
  error?: ApiError | Error | null;
  onRetry?: () => void;
  empty?: ReactNode;
  caption?: string;
  rowClass?: (r: T) => string;
}) {
  if (error && rows.length === 0) return <ErrorState error={error} onRetry={onRetry} />;
  if (loading && rows.length === 0) return <Skeleton rows={6} />;

  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, r: T) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick?.(r); }
  };

  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={caption ?? 'Table'}>
      <table className="table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>{columns.map((c) => <th key={c.key} scope="col" className={c.className} style={{ width: c.width }}>{c.header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const k = rowKey(r);
            return (
              <tr key={k} data-key={k}
                className={[onRowClick && 'is-clickable', selectedKey === k && 'is-selected', rowClass?.(r)].filter(Boolean).join(' ')}
                tabIndex={onRowClick ? 0 : undefined}
                aria-selected={onRowClick ? selectedKey === k : undefined}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                onKeyDown={onRowClick ? (e) => onKey(e, r) : undefined}>
                {columns.map((c) => <td key={c.key} className={c.className}>{c.render(r)}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && (empty ?? <Empty title="Nothing here" />)}
    </div>
  );
}
