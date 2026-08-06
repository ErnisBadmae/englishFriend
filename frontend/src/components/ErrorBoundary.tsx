import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  onReset?: () => void;
}

interface State {
  error: Error | null;
}

/**
 * Without this, any render error blanks the whole page and the learner loses
 * the screen mid-session (observed 2026-08-06: a white screen during a voice
 * mission, while the backend had already stored the evidence). Keep the error
 * visible and the app recoverable instead of silently losing the run.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[UI] Render error:", error, info.componentStack);
  }

  private handleReset = () => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render() {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    return (
      <div className="empty-state-card">
        <h2>Something broke on this screen</h2>
        <p>
          Your session data is saved on the server. This is a UI error, not lost
          progress.
        </p>
        <p className="muted-line">{error.message}</p>
        <button className="primary-action" onClick={this.handleReset}>
          Back to home
        </button>
      </div>
    );
  }
}
