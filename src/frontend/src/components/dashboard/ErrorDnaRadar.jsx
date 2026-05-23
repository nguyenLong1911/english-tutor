import { useEffect, useState } from 'react'
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts'

import { dnaAPI, getErrorMessage } from '../../services/api.js'

const LABELS = {
  grammar: 'Ngữ pháp',
  vocab: 'Từ vựng',
  preposition: 'Giới từ',
  writing: 'Viết',
  collocations: 'Collocations',
  pronunciation: 'Phát âm',
}

export default function ErrorDnaRadar({ userId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    dnaAPI
      .forUser(userId)
      .then((res) => { if (!cancelled) setData(res) })
      .catch((err) => { if (!cancelled) setError(getErrorMessage(err, 'dashboard.dna')) })
    return () => { cancelled = true }
  }, [userId])

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>
  }
  if (!data) {
    return <p className="text-sm text-gray-500 dark:text-slate-400">Đang tải Error DNA...</p>
  }

  const rows = Object.keys(LABELS).map((key) => ({
    dimension: LABELS[key],
    you: Number(data.dimensions?.[key] || 0),
    average: Number(data.average?.[key] || 0),
  }))

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Error DNA · 6 chiều</h3>
          <p className="text-xs text-gray-500 dark:text-slate-400">Tuần bắt đầu {data.week_start}</p>
        </div>
      </header>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={rows} outerRadius="70%">
            <PolarGrid />
            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
            <PolarRadiusAxis tick={{ fontSize: 10 }} />
            <Radar name="Bạn" dataKey="you" stroke="#2563eb" fill="#3b82f6" fillOpacity={0.45} />
            <Radar name="Trung bình" dataKey="average" stroke="#9ca3af" fill="#9ca3af" fillOpacity={0.2} />
            <Tooltip />
            <Legend />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
