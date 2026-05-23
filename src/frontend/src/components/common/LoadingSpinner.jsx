export default function LoadingSpinner({ label = 'Dang tai...' }) {
  return (
    <div className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-slate-300" role="status" aria-live="polite">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-brand-500 dark:border-slate-600 dark:border-t-sky-400" />
      <span>{label}</span>
    </div>
  )
}
