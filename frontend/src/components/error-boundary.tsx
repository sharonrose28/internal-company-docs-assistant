import { Component, type ErrorInfo, type ReactNode } from "react";
import { CircleAlert } from "lucide-react";
import { Button } from "./ui/button";

type BoundaryState = { failed: boolean; error?: Error };

export class ErrorBoundary extends Component<{ children: ReactNode; resetKey?: string }, BoundaryState> {
  state: BoundaryState = { failed: false };
  static getDerivedStateFromError(error: Error): BoundaryState { return { failed: true, error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI boundary failure", error, info.componentStack);
    try { sessionStorage.setItem("atlas:last-ui-error", `${error.name}: ${error.message}\n${info.componentStack ?? ""}`); } catch { /* storage may be disabled */ }
  }
  componentDidUpdate(previous: Readonly<{ children: ReactNode; resetKey?: string }>) {
    if (this.state.failed && previous.resetKey !== this.props.resetKey) this.setState({ failed: false, error: undefined });
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="grid min-h-dvh place-items-center p-6"><section className="max-w-md text-center">
      <CircleAlert className="mx-auto size-10 text-red-500" aria-hidden="true" /><h1 className="mt-4 text-xl font-semibold">Something went wrong</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">The page encountered an unexpected problem. Your data has not been changed.</p>
      {this.state.error?.message && <pre className="mt-4 max-h-32 overflow-auto rounded-lg border bg-[var(--surface-muted)] p-3 text-left text-xs text-red-600" data-testid="ui-error-message">{this.state.error.message}</pre>}
      <div className="mt-6 flex justify-center gap-2"><Button variant="secondary" onClick={() => this.setState({ failed: false, error: undefined })}>Try again</Button><Button onClick={() => window.location.reload()}>Reload application</Button></div>
    </section></main>;
  }
}
