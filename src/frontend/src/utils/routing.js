export function isOnboardingComplete(user) {
  if (!user) return false
  if (user.role === 'admin') return true

  const goals = Array.isArray(user.learning_goals) ? user.learning_goals.filter(Boolean) : []
  return Boolean(
    user.cefr_level &&
    user.industry &&
    goals.length > 0 &&
    user.preferred_study_time
  )
}

export function getPostAuthPath(user) {
  if (user?.role === 'admin') return '/admin'
  return isOnboardingComplete(user) ? '/app' : '/onboarding'
}
