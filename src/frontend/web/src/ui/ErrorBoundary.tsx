import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from './primitives';

interface Props {
  children: ReactNode;
  /** Any change (e.g. the route path) clears a caught error and renders the children again. */
  resetKey?: unknown;
  /** What failed, for the message ("This panel failed to render"). */
  what?: string;
  className?: string;
}

interface State {
  error: Error | null;
  attempt: number;
}

/**
 * Contains a render crash to one page or panel so the shell, the navigation and the other panels stay
 * usable. "Reload panel" remounts the children; a route change (resetKey) clears the error too.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, attempt: 0 };

  static getDerivedStateFromError(error: unknown): Partial<State> {
    return { error: error instanceof Error ? error : new Error(String(error)) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[TRIDENT] render error', error, info.componentStack);
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && !Object.is(prev.resetKey, this.props.resetKey)) this.reset();
  }

  reset = () => this.setState((s) => ({ error: null, attempt: s.attempt + 1 }));

  render() {
    const { error, attempt } = this.state;
    if (!error) return <ErrorBoundaryKey key={attempt}>{this.props.children}</ErrorBoundaryKey>;
    return (
      <div className={`state-block state-block--error boundary ${this.props.className ?? ''}`} role="alert">
        <AlertTriangle aria-hidden="true" />
        <strong>This {this.props.what ?? 'panel'} failed to render</strong>
        <span>The rest of the console still works. Reloading usually fixes it; if it keeps failing, report the message below.</span>
        <Button size="sm" icon={<RotateCcw />} onClick={this.reset}>Reload panel</Button>
        <details className="boundary-details">
          <summary>Error details</summary>
          <pre className="mono">{error.message || error.name}{error.stack ? `\n\n${error.stack}` : ''}</pre>
        </details>
      </div>
    );
  }
}

/** Keyed wrapper so "Reload panel" remounts the subtree instead of reusing its broken state. */
function ErrorBoundaryKey({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
