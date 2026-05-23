import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error) {
    // Keep minimal logging so runtime crashes can be debugged in development.
    console.error('Unhandled UI error:', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-3 p-6 text-center bg-gray-50 text-gray-900 dark:bg-slate-950 dark:text-slate-100">
          <p className="text-xl font-semibold">Giao diện gặp sự cố. Vui lòng tải lại trang.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-xl bg-brand-700 px-4 py-2 text-white hover:bg-brand-600"
          >
            Tải lại trang
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
