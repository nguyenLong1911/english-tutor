export default function SM2FeedbackButtons({ onSelect, disabled }) {
  return (
    <div className="flex flex-wrap justify-center gap-3">
      <button
        type="button"
        onClick={() => onSelect(1)}
        disabled={disabled}
        className="rounded-xl bg-red-500 px-4 py-2 text-white hover:bg-red-600 disabled:opacity-50"
      >
        Kho
      </button>
      <button
        type="button"
        onClick={() => onSelect(3)}
        disabled={disabled}
        className="rounded-xl bg-amber-500 px-4 py-2 text-white hover:bg-amber-600 disabled:opacity-50"
      >
        On
      </button>
      <button
        type="button"
        onClick={() => onSelect(5)}
        disabled={disabled}
        className="rounded-xl bg-emerald-500 px-4 py-2 text-white hover:bg-emerald-600 disabled:opacity-50"
      >
        De
      </button>
    </div>
  )
}
