import { Component } from 'react';

/**
 * Containment for one molecule's render.
 *
 * Wraps each molecule individually so a throw costs that band and not the whole
 * section. The fallback is itself a design-system band, so a failure still looks
 * like the product rather than like a broken page.
 *
 * The error detail goes to the console, never to the user: a component stack or an
 * upstream exception message is internal detail, and the payload that caused it
 * came from a model.
 *
 * Boundaries catch render errors only — not async work or event handlers. Those
 * need their own try/catch at the call site.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error('molecule failed to render', error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="callout alert">
          <span className="lead">Could not draw this.</span> The component failed to
          render. The browser console has the detail.
        </div>
      );
    }
    return this.props.children;
  }
}
